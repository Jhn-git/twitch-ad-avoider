"""Streamlink-backed playback and recording services for the web GUI."""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import parse_qs, quote, unquote, urljoin, urlparse

import requests
import streamlink

from src import recording_index
from src.clip_editor import ClipEditSession, clip_filename, collision_safe_path
from src.config_manager import ConfigManager
from src.constants import CLIPS_DIR, TEMP_DIR
from src.exceptions import TwitchStreamError, ValidationError
from src.logging_config import get_logger
from src.stream_preview import fetch_stream_preview_info
from src.validators import validate_channel_name

logger = get_logger(__name__)

StreamEventCallback = Callable[[dict], None]
ActivityCallback = Callable[[str, str, Optional[str]], None]

# How many days of a channel's recorded history to keep before it's auto-deleted.
RECORDING_RETENTION_DAYS = 3
RECORDING_STATE_PUSH_INTERVAL_SECONDS = 5.0
CLIP_RECORDER_LAG_TOLERANCE_SECONDS = 8.0
CLIP_AUTO_POSTROLL_SECONDS = 5.0
CLIP_KEYFRAME_PADDING_SECONDS = 2.0
CLIP_CAPTURE_WAIT_GRACE_SECONDS = 15.0
CLIP_CAPTURE_POLL_SECONDS = 0.25

# Twitch's low-latency manifests advertise not-yet-final segments via this tag
# instead of a normal #EXTINF entry - see streamlink's TwitchM3U8Parser
# (parse_tag_ext_x_twitch_prefetch). hls.js doesn't recognize the tag, so
# without rewriting it into a standard segment entry these are silently
# dropped and the player never benefits from Twitch's actual low-latency feed.
_TWITCH_PREFETCH_TAG_PREFIX = "#EXT-X-TWITCH-PREFETCH:"
_EXTINF_RE = re.compile(r"^#EXTINF:\s*([0-9]*\.?[0-9]+)")


@dataclass
class WebStreamSession:
    """State owned by one embedded playback session."""

    session_id: str
    channel: str
    quality: str
    stream_url: str
    stream_args: dict[str, Any]
    playback_url: str
    recording_path: Optional[str]
    recording_start_time: Optional[datetime]
    stop_event: threading.Event = field(default_factory=threading.Event)
    status: str = "starting"
    end_reason: Optional[str] = None
    last_error: Optional[str] = None
    thread: Optional[threading.Thread] = None
    day_dir: Optional[Path] = None
    segment_id: Optional[str] = None
    recorded_bytes: int = 0
    last_recorded_at: Optional[datetime] = None
    recording_ready_at: Optional[datetime] = None
    last_recording_state_pushed_at: Optional[datetime] = None


@dataclass
class _RecordingPrep:
    """What `_prepare_recording` resolved for a new recording session."""

    raw_path: Optional[str]
    start_time: Optional[datetime]
    day_dir: Optional[Path]
    segment_id: Optional[str]


class _PlaybackProxyHandler(BaseHTTPRequestHandler):
    """Small local proxy that gives WebView2 same-origin HLS URLs."""

    server: "_PlaybackProxyServer"

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        try:
            self.server.service.handle_proxy_request(self)
        except Exception as exc:
            logger.warning("Playback proxy request failed: %s", exc)
            self.send_error(502, str(exc))

    def do_HEAD(self) -> None:  # noqa: N802 - stdlib handler API
        try:
            self.server.service.handle_proxy_request(self, head_only=True)
        except Exception as exc:
            logger.warning("Playback proxy request failed: %s", exc)
            self.send_error(502, str(exc))

    def log_message(self, fmt: str, *args: Any) -> None:
        logger.debug("Playback proxy: " + fmt, *args)


class _PlaybackProxyServer(ThreadingHTTPServer):
    """HTTP server carrying a reference back to the stream service."""

    daemon_threads = True

    def __init__(self, server_address: tuple[str, int], service: "WebStreamService"):
        super().__init__(server_address, _PlaybackProxyHandler)
        self.service = service


class WebStreamService:
    """Owns Streamlink playback resolution, local proxying, recording, and clips."""

    def __init__(
        self,
        config: ConfigManager,
        push_event: StreamEventCallback,
        add_activity: ActivityCallback,
    ) -> None:
        self.config = config
        self._push_event = push_event
        self._add_activity = add_activity
        self._lock = threading.RLock()
        self._session: Optional[WebStreamSession] = None
        self._proxy: Optional[_PlaybackProxyServer] = None
        self._proxy_thread: Optional[threading.Thread] = None
        self._recent_clip: Optional[ClipEditSession] = None
        self._media_files: dict[str, Path] = {}
        self._clip_shutdown_event = threading.Event()

    # ------------------------------------------------------------------
    # Public lifecycle
    # ------------------------------------------------------------------

    def start(self, channel: str, quality: str) -> dict:
        """Start or replace the current embedded playback session."""
        channel = validate_channel_name(channel)
        if not self.config.set("preferred_quality", quality):
            raise ValidationError(f"Invalid stream quality: {quality}")

        self.stop(join_timeout=2.0)
        self._ensure_proxy()

        # Overlaps with `_resolve_stream` below instead of running after it -
        # both are independent Twitch network round-trips on this critical path.
        stream_start_prefetch = self._prefetch_true_stream_start(channel)

        selected_quality, stream_url, stream_args, stream_obj = self._resolve_stream(
            channel, quality
        )
        session_id = uuid.uuid4().hex
        playback_url = self._playlist_url(session_id)
        prep = self._prepare_recording(channel, stream_start_prefetch)

        session = WebStreamSession(
            session_id=session_id,
            channel=channel,
            quality=selected_quality,
            stream_url=stream_url,
            stream_args=stream_args,
            playback_url=playback_url,
            recording_path=prep.raw_path,
            recording_start_time=prep.start_time,
            day_dir=prep.day_dir,
            segment_id=prep.segment_id,
        )

        with self._lock:
            self._session = session

        if prep.raw_path:
            session.thread = threading.Thread(
                target=self._recording_loop,
                args=(session, stream_obj),
                name=f"record-{channel}",
                daemon=True,
            )
            session.thread.start()
        else:
            session.status = "live"

        self._add_activity("info", f"Stream ready: {channel} @ {selected_quality}", "STREAM")
        self._push_event({"type": "started", "state": self.get_state()})
        return self.get_state()

    def stop(self, join_timeout: float = 1.0) -> dict:
        """Stop playback and recording."""
        with self._lock:
            session = self._session
            self._session = None

        if session:
            session.status = "stopped"
            session.end_reason = "stopped"
            session.stop_event.set()
            if session.thread and session.thread.is_alive():
                session.thread.join(timeout=join_timeout)
            self._close_current_segment(session, datetime.now())
            self._add_activity("info", f"Stopped stream: {session.channel}", "STREAM")
            self._push_event({"type": "stopped", "state": self.get_state()})

        return self.get_state()

    def shutdown(self) -> None:
        """Stop all streaming/proxy resources.

        Runs on the window-closing UI thread, so it must not block: the
        recording thread is a daemon and the process is exiting anyway, so
        there is nothing to gain from waiting on session.thread.join() here
        (unlike stop(), which callers may rely on to observe a clean stop).
        """
        self._clip_shutdown_event.set()
        with self._lock:
            recent_clip = self._recent_clip
        if recent_clip:
            recent_clip.cancel_event.set()
            self._remove_preview_file(recent_clip)
        with self._lock:
            self._media_files.clear()
        self.stop(join_timeout=0)
        proxy = self._proxy
        self._proxy = None
        if proxy:
            proxy.shutdown()
            proxy.server_close()

    def get_state(self) -> dict:
        with self._lock:
            session = self._session
            if not session:
                return {
                    "active": False,
                    "channel": None,
                    "quality": self.config.get("preferred_quality", "best"),
                    "playback_url": None,
                    "status": "idle",
                    "recording": False,
                    "clip_ready": False,
                    "clip_ready_seconds": 0.0,
                    "clip_warmup_reason": None,
                    "last_error": None,
                }

            clip_status = self._clip_status(session)
            return {
                "active": session.status in {"starting", "live", "reconnecting"},
                "channel": session.channel,
                "quality": session.quality,
                "playback_url": session.playback_url,
                "status": session.status,
                "recording": bool(session.recording_path),
                "clip_ready": clip_status["ready"],
                "clip_ready_seconds": clip_status["ready_seconds"],
                "clip_warmup_reason": clip_status["reason"],
                "last_error": session.last_error,
            }

    def get_recording_segments(self, channel: str) -> dict:
        """Today's recorded-segment index for `channel`, for the gap-aware seek bar.

        `stream_created_at` falls back to the earliest known segment's start
        time when the true Twitch broadcast start couldn't be resolved (offline
        channel, network failure, etc.) - computed here at read time rather
        than stored, so a later successful fetch can still improve it.
        """
        channel = validate_channel_name(channel)
        now = datetime.now()
        day_dir = TEMP_DIR / channel / recording_index.day_dir_name(now.date())
        index = recording_index.load_index(day_dir)

        stream_created_at = index.stream_created_at
        if stream_created_at is None and index.segments:
            stream_created_at = min(segment.start for segment in index.segments)

        return {
            "channel": channel,
            "stream_created_at": stream_created_at.isoformat() if stream_created_at else None,
            "segments": [
                {
                    "id": segment.id,
                    "start": segment.start.isoformat(),
                    "end": segment.end.isoformat() if segment.end else None,
                }
                for segment in index.segments
            ],
            "now": now.isoformat(),
        }

    def create_clip(
        self,
        duration_seconds: int,
        behind_live_seconds: float = 0.0,
        *,
        prepare_provisional_preview: bool = True,
    ) -> dict:
        """Create a clip from the rolling local recording.

        ``behind_live_seconds`` is how far the caller's playhead is from the
        live edge (e.g. the browser is paused or scrubbed back), so the clip
        ends at the caller's position instead of always ending at "now".

        The first MP4 remains the fast stream-copy safety clip. A background
        editor job then waits until the source recording covers the immutable
        player anchor plus five seconds and atomically upgrades the same file.
        """
        captured_at = datetime.now()
        with self._lock:
            session = self._session

        if not session or not session.recording_path or not session.recording_start_time:
            return {"ok": False, "error": "No active recording to clip"}

        source_path = Path(session.recording_path)
        if not source_path.exists():
            return {"ok": False, "error": "Recording is not ready yet"}
        file_stat = source_path.stat()
        if file_stat.st_size <= 0:
            return {"ok": False, "error": "Recording is not ready yet"}

        with self._lock:
            last_recorded_at = session.last_recorded_at

        # Use the recording file's own last-write time rather than wall-clock
        # "now" - once the stream ends, the file stops growing but "now" keeps
        # advancing for however long the user browses before clicking Clip,
        # which would otherwise inflate "elapsed" well past the file's real
        # content length and skew the clip toward the end of the recording.
        last_write_time = datetime.fromtimestamp(file_stat.st_mtime)
        elapsed = (last_write_time - session.recording_start_time).total_seconds()
        elapsed = max(0.0, elapsed)
        behind = behind_live_seconds if isinstance(behind_live_seconds, (int, float)) else 0.0
        behind = max(0.0, behind)

        if elapsed < duration_seconds:
            return {
                "ok": False,
                "error": (
                    "Recording is still warming up "
                    f"({int(elapsed)}s captured for a {duration_seconds}s clip)."
                ),
            }

        active_recording = session.status in {"starting", "live", "reconnecting"}
        recorded_until = last_recorded_at or last_write_time
        recorder_lag = None
        if active_recording and recorded_until:
            requested_wall_end = captured_at - timedelta(seconds=behind)
            recorder_lag = (requested_wall_end - recorded_until).total_seconds()
            if recorder_lag > CLIP_RECORDER_LAG_TOLERANCE_SECONDS:
                return {
                    "ok": False,
                    "error": (
                        "Recording is still catching up "
                        f"({int(recorder_lag)}s behind the player). Try again in a moment."
                    ),
                }

        ffmpeg_exe = self._get_ffmpeg_executable()
        if not ffmpeg_exe:
            return {
                "ok": False,
                "error": "FFmpeg not found. Set ffmpeg_path or add ffmpeg to PATH.",
            }

        clip_dir = Path(self.config.get("clip_directory", str(CLIPS_DIR)))
        clip_dir.mkdir(parents=True, exist_ok=True)
        output_path = collision_safe_path(
            clip_dir,
            clip_filename(session.channel, captured_at),
        )
        target_end = max(0.0, elapsed - behind)
        start_offset = max(0.0, target_end - duration_seconds)

        cmd = [
            ffmpeg_exe,
            "-fflags",
            "+discardcorrupt",
            "-ss",
            str(start_offset),
            "-i",
            str(source_path),
            "-t",
            str(duration_seconds),
            "-c",
            "copy",
            "-avoid_negative_ts",
            "make_zero",
            "-movflags",
            "+faststart",
            "-y",
            str(output_path),
        ]

        logger.debug(
            "Clip timing: duration=%s behind_live=%.3f elapsed=%.3f file_mtime=%s "
            "file_size=%s recorder_lag=%s target_end=%.3f start_offset=%.3f",
            duration_seconds,
            behind,
            elapsed,
            last_write_time.isoformat(),
            file_stat.st_size,
            f"{recorder_lag:.3f}" if recorder_lag is not None else "n/a",
            target_end,
            start_offset,
        )
        logger.debug("Creating clip: %s", " ".join(cmd))
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=60,
                **self._subprocess_window_kwargs(),
            )
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "FFmpeg timed out creating clip"}
        except Exception as exc:
            return {"ok": False, "error": f"Clip failed: {exc}"}

        output_size = output_path.stat().st_size if output_path.exists() else 0
        if output_size > 1024:
            self._ensure_proxy()
            if active_recording:
                requested_wall_end = captured_at - timedelta(seconds=behind)
                requested_anchor = (
                    requested_wall_end - session.recording_start_time
                ).total_seconds()
            else:
                requested_anchor = target_end
            anchor_seconds = max(0.0, requested_anchor)
            safety_end = min(elapsed, max(float(duration_seconds), target_end))
            safety_start = max(0.0, safety_end - duration_seconds)
            clip_id = uuid.uuid4().hex
            preview_token = uuid.uuid4().hex
            provisional_preview = source_path.parent / f".clip-preview-{clip_id}-1.mp4"
            provisional_error = None
            if prepare_provisional_preview:
                provisional_error = self._copy_provisional_preview(
                    output_path,
                    provisional_preview,
                )
                safety_duration = self._media_duration_seconds(
                    provisional_preview,
                    float(duration_seconds),
                )
            else:
                # Quick Clip still retains a fully editable recent clip once
                # the background post-roll copy is ready. Avoiding this first
                # full-file duplicate keeps the button response fast,
                # especially for the longer clip durations.
                safety_duration = float(duration_seconds)
            edit = ClipEditSession(
                id=clip_id,
                channel=session.channel,
                captured_at=captured_at,
                source_path=source_path,
                source_start_time=session.recording_start_time,
                output_path=output_path,
                duration_seconds=float(duration_seconds),
                anchor_seconds=anchor_seconds,
                rendered_start_seconds=0.0,
                rendered_end_seconds=safety_duration,
                selected_start_seconds=0.0,
                selected_end_seconds=safety_duration,
                preview_start_seconds=0.0,
                preview_end_seconds=safety_duration,
                preview_token=preview_token,
                preview_path=provisional_preview,
                preview_verified=prepare_provisional_preview and provisional_error is None,
                output_verified=False,
                tail_seconds=CLIP_AUTO_POSTROLL_SECONDS,
            )
            if prepare_provisional_preview and provisional_error:
                edit.message = "Preparing clip preview..."
                logger.warning(
                    "Clip provisional preview unavailable: id=%s output=%s preview=%s error=%s",
                    clip_id,
                    output_path,
                    provisional_preview,
                    provisional_error,
                )
            self._set_recent_clip(edit)
            logger.info(
                "Clip editor created: id=%s anchor=%.3f requested_start=%.3f "
                "requested_end=%.3f preview_duration=%.3f preview=%s "
                "preview_verified=%s provisional_requested=%s output=%s",
                clip_id,
                anchor_seconds,
                safety_start,
                safety_end,
                safety_duration,
                provisional_preview,
                edit.preview_verified,
                prepare_provisional_preview,
                output_path,
            )
            self._add_activity("success", f"Clip saved: {output_path}", "CLIP")
            clip_payload = self._clip_payload(edit)
            self._push_event(
                {
                    "type": "clip_created",
                    "path": str(output_path),
                    "clip": clip_payload,
                    "open_editor": prepare_provisional_preview,
                }
            )
            threading.Thread(
                target=self._automatic_postroll_worker,
                args=(edit, session),
                name=f"clip-postroll-{clip_id[:8]}",
                daemon=True,
            ).start()
            return {"ok": True, "path": str(output_path), "clip": clip_payload}

        stderr = result.stderr.decode(errors="replace") if result.stderr else ""
        return {"ok": False, "error": stderr[-500:] or "FFmpeg did not create a usable clip"}

    def get_recent_clip(self) -> dict:
        with self._lock:
            edit = self._recent_clip
        return {"ok": True, "clip": self._clip_payload(edit) if edit else None}

    def request_clip_tail_extension(self, clip_id: str, seconds: float = 5.0) -> dict:
        try:
            edit = self._get_recent_clip(clip_id)
        except ValidationError as exc:
            return {"ok": False, "error": str(exc)}
        if not isinstance(seconds, (int, float)) or not math.isfinite(seconds):
            return {"ok": False, "error": "Invalid tail extension"}
        seconds = float(seconds)
        if seconds <= 0 or seconds > 60:
            return {"ok": False, "error": "Tail extension must be between 1 and 60 seconds"}
        if not edit.operation_lock.acquire(blocking=False):
            return {"ok": False, "error": "The clip editor is already processing"}
        if not edit.preview_verified or not edit.preview_path.exists():
            edit.operation_lock.release()
            return {
                "ok": False,
                "error": "The clip preview is not ready; retry clip preparation.",
                "clip": self._clip_payload(edit),
            }

        with self._lock:
            edit.tail_seconds += seconds
            edit.status = "capturing_tail"
            edit.message = f"Capturing another {int(seconds)}s..."
            edit.error = None
            edit.retry_available = False
        self._push_clip_update(edit)
        threading.Thread(
            target=self._manual_tail_worker,
            args=(edit, seconds),
            name=f"clip-tail-{edit.id[:8]}",
            daemon=True,
        ).start()
        return {"ok": True, "clip": self._clip_payload(edit)}

    def retry_clip_edit_preparation(self, clip_id: str) -> dict:
        try:
            edit = self._get_recent_clip(clip_id)
        except ValidationError as exc:
            return {"ok": False, "error": str(exc)}
        if edit.status != "error" or not edit.retry_available:
            return {"ok": False, "error": "Clip preparation is not waiting for a retry"}
        if not edit.operation_lock.acquire(blocking=False):
            return {"ok": False, "error": "The clip editor is already processing"}

        with self._lock:
            edit.tail_seconds = max(CLIP_AUTO_POSTROLL_SECONDS, edit.tail_seconds)
            edit.status = "capturing_postroll"
            edit.message = "Retrying the fast padded clip..."
            edit.error = None
            edit.retry_available = False
        logger.info(
            "Retrying clip preparation: id=%s anchor=%.3f target_tail=%.3f",
            edit.id,
            edit.anchor_seconds,
            edit.tail_seconds,
        )
        self._push_clip_update(edit)
        threading.Thread(
            target=self._retry_clip_edit_worker,
            args=(edit,),
            name=f"clip-retry-{edit.id[:8]}",
            daemon=True,
        ).start()
        return {"ok": True, "clip": self._clip_payload(edit)}

    def save_clip_edit(
        self,
        clip_id: str,
        start_seconds: float,
        end_seconds: float,
        title: str = "",
    ) -> dict:
        try:
            edit = self._get_recent_clip(clip_id)
        except ValidationError as exc:
            return {"ok": False, "error": str(exc)}
        if not all(
            isinstance(value, (int, float)) and math.isfinite(value)
            for value in (start_seconds, end_seconds)
        ):
            return {"ok": False, "error": "Invalid trim boundaries"}
        if not isinstance(title, str):
            return {"ok": False, "error": "Invalid clip title"}
        if not edit.operation_lock.acquire(blocking=False):
            return {"ok": False, "error": "The clip editor is still preparing"}

        try:
            if not edit.preview_verified:
                return {
                    "ok": False,
                    "error": "The clip preview is not ready. Retry preparation before saving.",
                    "clip": self._clip_payload(edit),
                }
            preview_duration = edit.preview_end_seconds - edit.preview_start_seconds
            start_seconds = float(start_seconds)
            end_seconds = float(end_seconds)
            if start_seconds < 0 or end_seconds > preview_duration + 0.05:
                return {"ok": False, "error": "Trim boundaries are outside the available preview"}
            if end_seconds - start_seconds < 1.0:
                return {"ok": False, "error": "A clip must be at least one second long"}

            logger.info(
                "Saving clip edit: id=%s preview_verified=%s preview=%s "
                "submitted_start=%.3f submitted_end=%.3f preview_duration=%.3f",
                edit.id,
                edit.preview_verified,
                edit.preview_path,
                start_seconds,
                end_seconds,
                preview_duration,
            )
            clip_dir = edit.output_path.parent
            previous_output = edit.output_path
            destination = collision_safe_path(
                clip_dir,
                clip_filename(edit.channel, edit.captured_at, title),
                current=previous_output,
            )
            bounds_changed = (
                abs(start_seconds - edit.rendered_start_seconds) > 0.01
                or abs(end_seconds - edit.rendered_end_seconds) > 0.01
            )

            with self._lock:
                edit.status = "saving"
                edit.message = "Rendering frame-accurate clip..."
                edit.error = None
                edit.retry_available = False
            self._push_clip_update(edit)

            if bounds_changed:
                rendered, error = self._render_final_clip(
                    edit,
                    start_seconds,
                    end_seconds,
                    destination,
                )
                if not rendered:
                    return self._clip_operation_failed(edit, error or "Clip render failed")
            elif destination != edit.output_path:
                error = self._rename_clip_output(edit.output_path, destination)
                if error:
                    return self._clip_operation_failed(edit, error)

            with self._lock:
                edit.output_path = destination
                edit.title = title
                edit.rendered_start_seconds = start_seconds
                edit.rendered_end_seconds = end_seconds
                edit.output_verified = True
                edit.selected_start_seconds = start_seconds
                edit.selected_end_seconds = end_seconds
                edit.status = "ready"
                edit.message = "Clip saved"
                edit.error = None
                edit.retry_available = False
            self._add_activity("success", f"Clip updated: {destination}", "CLIP")
            self._push_clip_update(edit)
            return {"ok": True, "path": str(destination), "clip": self._clip_payload(edit)}
        finally:
            edit.operation_lock.release()

    # ------------------------------------------------------------------
    # Streamlink and recording
    # ------------------------------------------------------------------

    def _new_streamlink_session(self) -> streamlink.Streamlink:
        session = streamlink.Streamlink()
        timeout = self.config.get("network_timeout", 30)
        session.set_option("http-timeout", timeout)
        session.set_option("stream-segment-attempts", 5)
        session.set_option("stream-segment-timeout", 15.0)
        session.set_option("hls-playlist-reload-attempts", 5)
        session.set_option("hls-live-edge", self.config.get("hls_live_edge", 3))
        set_plugin_option = getattr(session, "set_plugin_option", None)
        if callable(set_plugin_option):
            set_plugin_option("twitch", "disable-ads", True)
            if self.config.get("twitch_low_latency", True):
                set_plugin_option("twitch", "low-latency", True)
        return session

    def _resolve_stream(self, channel: str, quality: str) -> tuple[str, str, dict[str, Any], Any]:
        session = self._new_streamlink_session()
        streams = session.streams(f"twitch.tv/{channel}")
        if not streams:
            raise TwitchStreamError(f"No streams available for: {channel}")
        selected_quality = quality if quality in streams else "best"
        if selected_quality not in streams:
            selected_quality = next(iter(streams))
        stream_obj = streams[selected_quality]
        stream_url = self._stream_url(stream_obj)
        stream_args = getattr(stream_obj, "args", {}) or {}
        if not stream_url:
            raise TwitchStreamError("Selected stream could not be translated to a playable URL")
        return selected_quality, stream_url, stream_args, stream_obj

    def _stream_url(self, stream_obj: Any) -> Optional[str]:
        url = getattr(stream_obj, "url", None)
        if isinstance(url, str):
            return url
        to_url = getattr(stream_obj, "to_url", None)
        if callable(to_url):
            translated = to_url()
            return translated if isinstance(translated, str) else None
        return None

    def _prepare_recording(
        self,
        channel: str,
        stream_start_prefetch: Optional[Callable[[], Optional[datetime]]] = None,
    ) -> _RecordingPrep:
        """Start a new day-scoped recording segment for `channel`.

        Every call gets its own uniquely-named raw file under
        temp/<channel>/<date>/ - never reused or appended-to across sessions,
        which is what makes this safe even if a previous segment's file is
        still locked/in-use for some reason (unlike the old single rolling
        `recording_<channel>.ts`, which would silently append onto stale
        content when its unlink failed).

        `stream_start_prefetch`, if given, is the callable returned by
        `_prefetch_true_stream_start` - it blocks until that background fetch
        completes instead of starting a fresh (sequential) one here.
        """
        if not self.config.get("clip_enabled", True):
            return _RecordingPrep(None, None, None, None)

        now = datetime.now()
        channel_dir = TEMP_DIR / channel
        recording_index.purge_old_days(channel_dir, RECORDING_RETENTION_DAYS, now)

        day_dir = channel_dir / recording_index.day_dir_name(now.date())
        index = recording_index.load_index(day_dir)
        recording_index.close_dangling_segments(index, day_dir, now)

        if stream_start_prefetch is not None:
            stream_created_at = stream_start_prefetch()
        else:
            stream_created_at = self._resolve_true_stream_start(channel)
        if stream_created_at is not None:
            index.stream_created_at = stream_created_at

        segment = recording_index.start_segment(index, now)
        recording_index.save_index(day_dir, index)

        raw_path = day_dir / segment.raw_filename
        return _RecordingPrep(str(raw_path), segment.start, day_dir, segment.id)

    def _prefetch_true_stream_start(self, channel: str) -> Callable[[], Optional[datetime]]:
        """Kick off `_resolve_true_stream_start` on a background thread so it
        can overlap with `_resolve_stream`'s network round-trip in `start()`.
        Returns a callable that blocks until the background fetch finishes
        and yields its result."""
        result: list[Optional[datetime]] = [None]

        def _fetch() -> None:
            result[0] = self._resolve_true_stream_start(channel)

        thread = threading.Thread(target=_fetch, daemon=True)
        thread.start()

        def _join() -> Optional[datetime]:
            thread.join()
            return result[0]

        return _join

    def _resolve_true_stream_start(self, channel: str) -> Optional[datetime]:
        """The real moment the broadcast went live on Twitch, independent of
        whenever our own recording happened to start. Best-effort: returns
        None on any failure (offline channel, network error, missing field)
        rather than raising - `_prepare_recording` already has its own
        fallback (the earliest recorded segment's own start time) for when
        this can't be resolved."""
        info = fetch_stream_preview_info(channel, timeout=self._network_timeout())
        if not info.stream_created_at:
            return None
        try:
            aware = datetime.fromisoformat(info.stream_created_at.replace("Z", "+00:00"))
        except ValueError:
            return None
        return datetime.fromtimestamp(aware.timestamp())

    def _close_current_segment(self, session: WebStreamSession, end: datetime) -> None:
        if not session.day_dir or not session.segment_id:
            return
        index = recording_index.load_index(session.day_dir)
        recording_index.close_segment(index, session.segment_id, end)
        recording_index.save_index(session.day_dir, index)

    def purge_expired_recordings(self) -> None:
        """Sweep every channel's recording history, not just the one being
        (re)started - otherwise a channel the user never restarts would keep
        its day-folders forever. Called explicitly once at real app startup
        (see `TwitchViewerAPI.__init__`), not from this class's constructor -
        a constructor shouldn't have filesystem side effects, and tests that
        instantiate `WebStreamService` directly must not touch the real
        on-disk `temp/` directory just by existing.
        """
        if not TEMP_DIR.exists():
            return
        now = datetime.now()
        try:
            channel_dirs = [entry for entry in TEMP_DIR.iterdir() if entry.is_dir()]
        except OSError:
            return
        for channel_dir in channel_dirs:
            recording_index.purge_old_days(channel_dir, RECORDING_RETENTION_DAYS, now)

    def _recording_loop(self, session: WebStreamSession, initial_stream: Any) -> None:
        attempts = self._retry_attempts()
        delay = self._retry_delay()
        current_attempt = 0
        stream_obj = initial_stream

        while not session.stop_event.is_set():
            try:
                session.status = "live"
                self._push_event({"type": "recording_started", "state": self.get_state()})
                ended_cleanly = self._record_once(session, stream_obj)
                if session.stop_event.is_set():
                    break
                session.end_reason = "stream_ended" if ended_cleanly else "stream_error"
                current_attempt += 1
                if current_attempt > attempts:
                    session.status = "ended"
                    session.last_error = "Stream ended after reconnect attempts were exhausted"
                    self._close_current_segment(session, datetime.now())
                    self._add_activity("error", session.last_error, "STREAM")
                    self._push_event({"type": "ended", "state": self.get_state()})
                    break
                session.status = "reconnecting"
                message = (
                    f"Stream input ended; reconnecting in {delay}s "
                    f"(attempt {current_attempt}/{attempts})"
                )
                self._add_activity("warning", message, "STREAM")
                self._push_event(
                    {"type": "reconnecting", "message": message, "state": self.get_state()}
                )
                if not self._sleep_interruptibly(session.stop_event, delay):
                    break
                quality, stream_url, stream_args, stream_obj = self._resolve_stream(
                    session.channel,
                    session.quality,
                )
                session.quality = quality
                session.stream_url = stream_url
                session.stream_args = stream_args
                session.playback_url = self._playlist_url(session.session_id, cache_bust=True)
                self._push_event({"type": "playback_url", "state": self.get_state()})
            except Exception as exc:
                if session.stop_event.is_set():
                    break
                session.last_error = str(exc)
                current_attempt += 1
                if current_attempt > attempts:
                    session.status = "error"
                    self._close_current_segment(session, datetime.now())
                    self._add_activity("error", f"Stream error: {exc}", "STREAM")
                    self._push_event(
                        {"type": "error", "error": str(exc), "state": self.get_state()}
                    )
                    break
                session.status = "reconnecting"
                message = (
                    f"Stream error ({exc}); reconnecting in {delay}s "
                    f"(attempt {current_attempt}/{attempts})"
                )
                self._add_activity("warning", message, "STREAM")
                self._push_event(
                    {"type": "reconnecting", "message": message, "state": self.get_state()}
                )
                if not self._sleep_interruptibly(session.stop_event, delay):
                    break

    def _record_once(self, session: WebStreamSession, stream_obj: Any) -> bool:
        if not session.recording_path:
            return True
        stream_fd = None
        recording_file = None
        try:
            stream_fd = stream_obj.open()
            recording_file = open(session.recording_path, "ab")
            while not session.stop_event.is_set():
                chunk = stream_fd.read(65536)
                if not chunk:
                    return True
                recording_file.write(chunk)
                recording_file.flush()
                if self._mark_recording_write(session, len(chunk)):
                    self._push_event({"type": "recording_progress", "state": self.get_state()})
            return True
        except Exception as exc:
            logger.warning("Recording stream ended with error: %s", exc)
            return False
        finally:
            for handle in (stream_fd, recording_file):
                try:
                    if handle:
                        handle.close()
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Recent clip editor
    # ------------------------------------------------------------------

    def _set_recent_clip(self, edit: ClipEditSession) -> None:
        with self._lock:
            previous = self._recent_clip
            self._recent_clip = edit
            if edit.preview_path != edit.output_path and edit.preview_path.exists():
                self._media_files[edit.preview_token] = edit.preview_path
            if previous:
                self._media_files.pop(previous.preview_token, None)
        if previous:
            previous.cancel_event.set()
            self._schedule_preview_cleanup(previous.preview_path, previous.output_path)

    def _get_recent_clip(self, clip_id: str) -> ClipEditSession:
        with self._lock:
            edit = self._recent_clip
        if not edit or edit.id != clip_id:
            raise ValidationError("Recent clip is no longer available")
        return edit

    def _is_current_clip(self, edit: ClipEditSession) -> bool:
        with self._lock:
            return self._recent_clip is edit

    def _clip_payload(self, edit: Optional[ClipEditSession]) -> Optional[dict]:
        if not edit:
            return None
        preview_url = None
        if edit.preview_path != edit.output_path and edit.preview_path.exists():
            preview_url = self._media_url(edit.preview_token, edit.preview_revision)
        elif edit.preview_path == edit.output_path:
            logger.error(
                "Refusing to serve mutable clip output as editor preview: id=%s path=%s",
                edit.id,
                edit.output_path,
            )
        with self._lock:
            if preview_url:
                self._media_files[edit.preview_token] = edit.preview_path
            else:
                self._media_files.pop(edit.preview_token, None)
            payload = edit.to_dict(preview_url)
            payload["can_edit"] = bool(preview_url) and edit.can_edit
            return payload

    def _push_clip_update(self, edit: ClipEditSession) -> None:
        if not self._is_current_clip(edit):
            return
        self._push_event({"type": "clip_edit_updated", "clip": self._clip_payload(edit)})

    def _clip_operation_failed(
        self,
        edit: ClipEditSession,
        error: str,
        *,
        retryable: bool = False,
    ) -> dict:
        if edit.cancel_event.is_set() or self._clip_shutdown_event.is_set():
            return {"ok": False, "error": error, "clip": None}
        with self._lock:
            edit.status = "error"
            edit.message = error
            edit.error = error
            edit.retry_available = retryable
        logger.warning(
            "Clip editor operation failed: id=%s preview_verified=%s "
            "rendered_start=%.3f rendered_end=%.3f error=%s",
            edit.id,
            edit.preview_verified,
            edit.rendered_start_seconds,
            edit.rendered_end_seconds,
            error,
        )
        self._add_activity("error", error, "CLIP")
        self._push_clip_update(edit)
        return {"ok": False, "error": error, "clip": self._clip_payload(edit)}

    def _automatic_postroll_worker(
        self,
        edit: ClipEditSession,
        source_session: WebStreamSession,
    ) -> None:
        if not edit.operation_lock.acquire(blocking=False):
            return
        try:
            self._run_automatic_postroll(edit, source_session)
        finally:
            edit.operation_lock.release()

    def _retry_clip_edit_worker(self, edit: ClipEditSession) -> None:
        try:
            self._run_automatic_postroll(edit, self._matching_source_session(edit))
        finally:
            edit.operation_lock.release()

    def _run_automatic_postroll(
        self,
        edit: ClipEditSession,
        source_session: Optional[WebStreamSession],
    ) -> None:
        target_end = edit.anchor_seconds + edit.tail_seconds
        available, complete, ended, error = self._wait_for_clip_source(
            edit,
            target_end,
            source_session,
        )
        if error:
            self._clip_operation_failed(edit, error, retryable=True)
            return
        selected_end = target_end if complete else available
        if selected_end <= edit.anchor_seconds and ended:
            self._clip_operation_failed(
                edit,
                "The stream ended before any post-roll could be captured; "
                "the safety clip was kept.",
                retryable=True,
            )
            return

        with self._lock:
            edit.status = "preparing_preview"
            edit.message = "Applying fast padded post-roll..."
            edit.error = None
        self._push_clip_update(edit)
        prepared, prepare_error = self._publish_padded_stream_copy(
            edit,
            selected_end,
            replace_output=not edit.output_verified,
        )
        if not prepared:
            self._clip_operation_failed(
                edit,
                prepare_error or "Could not apply the padded post-roll; the safety clip was kept.",
                retryable=True,
            )
            return

        actual_tail = max(0.0, selected_end - edit.anchor_seconds)
        with self._lock:
            edit.tail_seconds = actual_tail
            edit.status = "ready"
            if ended and not complete:
                edit.message = f"Stream ended; added {actual_tail:.1f}s of available post-roll"
            else:
                edit.message = f"Ready with {actual_tail:.0f}s post-roll and safe early padding"
            edit.error = None
            edit.retry_available = False
        logger.info(
            "Clip editor ready: id=%s anchor=%.3f tail=%.3f "
            "preview_verified=%s preview_duration=%.3f",
            edit.id,
            edit.anchor_seconds,
            edit.tail_seconds,
            edit.preview_verified,
            edit.preview_end_seconds,
        )
        self._push_clip_update(edit)

    def _manual_tail_worker(
        self,
        edit: ClipEditSession,
        requested_seconds: float = CLIP_AUTO_POSTROLL_SECONDS,
    ) -> None:
        try:
            previous_tail = max(0.0, edit.tail_seconds - requested_seconds)
            target_end = edit.anchor_seconds + edit.tail_seconds
            source_session = self._matching_source_session(edit)
            available, complete, ended, error = self._wait_for_clip_source(
                edit,
                target_end,
                source_session,
            )
            if error:
                with self._lock:
                    edit.tail_seconds = previous_tail
                self._clip_operation_failed(edit, error, retryable=True)
                return
            selected_end = target_end if complete else available
            if selected_end <= edit.anchor_seconds + previous_tail + 0.05:
                with self._lock:
                    edit.tail_seconds = previous_tail
                self._clip_operation_failed(
                    edit,
                    "No additional recorded footage is available yet",
                    retryable=True,
                )
                return

            with self._lock:
                edit.status = "preparing_preview"
                edit.message = "Applying the additional padded footage..."
                edit.error = None
            self._push_clip_update(edit)

            preview_ok, preview_error = self._publish_padded_stream_copy(
                edit,
                selected_end,
                replace_output=not edit.output_verified,
            )
            if not preview_ok:
                with self._lock:
                    edit.tail_seconds = previous_tail
                self._clip_operation_failed(
                    edit,
                    preview_error or "Could not refresh the padded trim preview",
                    retryable=True,
                )
                return

            with self._lock:
                edit.tail_seconds = max(0.0, selected_end - edit.anchor_seconds)
                edit.status = "ready"
                edit.message = (
                    f"Extended to {edit.tail_seconds:.1f}s after the original clip point"
                    if ended and not complete
                    else f"Captured {edit.tail_seconds:.0f}s after the original clip point"
                )
                edit.error = None
                edit.retry_available = False
            self._push_clip_update(edit)
        finally:
            edit.operation_lock.release()

    def _matching_source_session(self, edit: ClipEditSession) -> Optional[WebStreamSession]:
        with self._lock:
            session = self._session
        if not session or not session.recording_path:
            return None
        try:
            if Path(session.recording_path).resolve() == edit.source_path.resolve():
                return session
        except OSError:
            return None
        return None

    def _wait_for_clip_source(
        self,
        edit: ClipEditSession,
        target_end_seconds: float,
        source_session: Optional[WebStreamSession],
    ) -> tuple[float, bool, bool, Optional[str]]:
        available = self._source_available_seconds(edit, source_session)
        gap = max(0.0, target_end_seconds - available)
        deadline = time.monotonic() + gap + CLIP_CAPTURE_WAIT_GRACE_SECONDS
        last_reported_second = None

        while available + 0.05 < target_end_seconds:
            if edit.cancel_event.is_set() or self._clip_shutdown_event.is_set():
                return available, False, False, "Clip preparation was cancelled"

            active = bool(
                source_session and source_session.status in {"starting", "live", "reconnecting"}
            )
            if not active:
                return available, False, True, None
            if time.monotonic() >= deadline:
                return (
                    available,
                    False,
                    False,
                    "The recorder did not catch up in time; the last good clip was kept.",
                )

            remaining = max(0, int(round(target_end_seconds - available)))
            if remaining != last_reported_second:
                last_reported_second = remaining
                with self._lock:
                    edit.message = (
                        f"Capturing {remaining}s more..."
                        if remaining
                        else "Waiting for the recorder..."
                    )
                self._push_clip_update(edit)
            time.sleep(CLIP_CAPTURE_POLL_SECONDS)
            available = self._source_available_seconds(edit, source_session)

        return available, True, False, None

    def _source_available_seconds(
        self,
        edit: ClipEditSession,
        source_session: Optional[WebStreamSession] = None,
    ) -> float:
        recorded_at = None
        if source_session and source_session.last_recorded_at:
            recorded_at = source_session.last_recorded_at
        try:
            if edit.source_path.exists() and edit.source_path.stat().st_size > 0:
                file_time = datetime.fromtimestamp(edit.source_path.stat().st_mtime)
                if recorded_at is None or file_time > recorded_at:
                    recorded_at = file_time
        except OSError:
            pass
        if recorded_at is None:
            return 0.0
        return max(0.0, (recorded_at - edit.source_start_time).total_seconds())

    def _publish_padded_stream_copy(
        self,
        edit: ClipEditSession,
        source_end_seconds: float,
        replace_output: bool,
    ) -> tuple[bool, Optional[str]]:
        source_start_seconds = max(
            0.0,
            edit.anchor_seconds - edit.duration_seconds - CLIP_KEYFRAME_PADDING_SECONDS,
        )
        part_path = edit.output_path.with_name(
            f".{edit.output_path.stem}-{uuid.uuid4().hex}.part.mp4"
        )
        preview_path = edit.source_path.parent / (
            f".clip-preview-{edit.id}-{edit.preview_revision + 1}.mp4"
        )
        rendered, preview_duration, error = self._render_stream_copy(
            edit.source_path,
            source_start_seconds,
            source_end_seconds,
            part_path,
            edit.cancel_event,
        )
        if not rendered:
            return False, error

        copy_error = self._copy_provisional_preview(part_path, preview_path)
        if copy_error:
            self._remove_render_artifact(part_path)
            return False, f"Could not prepare the clip preview: {copy_error}"
        if (
            edit.cancel_event.is_set()
            or self._clip_shutdown_event.is_set()
            or not self._is_current_clip(edit)
        ):
            self._remove_render_artifact(part_path)
            self._remove_render_artifact(preview_path)
            return False, "Clip preparation was cancelled"

        if replace_output:
            replace_error = self._replace_file_with_retry(
                part_path,
                edit.output_path,
                edit.cancel_event,
            )
            if replace_error:
                self._remove_render_artifact(part_path)
                self._remove_render_artifact(preview_path)
                logger.warning(
                    "Padded clip replacement failed: id=%s source_start=%.3f "
                    "source_end=%.3f output=%s error=%s",
                    edit.id,
                    source_start_seconds,
                    source_end_seconds,
                    edit.output_path,
                    replace_error,
                )
                return False, replace_error
        else:
            self._remove_render_artifact(part_path)

        previous_preview = edit.preview_path
        previous_preview_duration = max(
            0.0,
            edit.preview_end_seconds - edit.preview_start_seconds,
        )
        added_preview_duration = max(0.0, preview_duration - previous_preview_duration)
        with self._lock:
            edit.preview_start_seconds = 0.0
            edit.preview_end_seconds = preview_duration
            edit.preview_path = preview_path
            edit.preview_revision += 1
            edit.preview_verified = True
            if replace_output:
                edit.rendered_start_seconds = 0.0
                edit.rendered_end_seconds = preview_duration
                edit.selected_start_seconds = 0.0
                edit.selected_end_seconds = preview_duration
                edit.output_verified = False
            else:
                edit.selected_start_seconds = min(
                    edit.selected_start_seconds,
                    max(0.0, preview_duration - 1.0),
                )
                edit.selected_end_seconds = min(
                    preview_duration,
                    edit.selected_end_seconds + added_preview_duration,
                )
            self._media_files[edit.preview_token] = preview_path
        if previous_preview != preview_path:
            self._schedule_preview_cleanup(previous_preview, edit.output_path)
        logger.info(
            "Padded clip published: id=%s revision=%s source_start=%.3f "
            "source_end=%.3f preview_duration=%.3f replaced_output=%s preview=%s",
            edit.id,
            edit.preview_revision,
            source_start_seconds,
            source_end_seconds,
            preview_duration,
            replace_output,
            preview_path,
        )
        return True, None

    def _render_stream_copy(
        self,
        source_path: Path,
        start_seconds: float,
        end_seconds: float,
        destination: Path,
        cancel_event: threading.Event,
    ) -> tuple[bool, float, Optional[str]]:
        ffmpeg_exe = self._get_ffmpeg_executable()
        if not ffmpeg_exe:
            return False, 0.0, "FFmpeg not found. Set ffmpeg_path or add ffmpeg to PATH."
        duration = max(0.0, end_seconds - start_seconds)
        if duration < 1.0:
            return False, 0.0, "A clip must be at least one second long"

        destination.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            ffmpeg_exe,
            "-hide_banner",
            "-loglevel",
            "error",
            "-fflags",
            "+discardcorrupt",
            "-ss",
            f"{start_seconds:.6f}",
            "-i",
            str(source_path),
            "-t",
            f"{duration:.6f}",
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-c",
            "copy",
            "-avoid_negative_ts",
            "make_zero",
            "-movflags",
            "+faststart",
            "-y",
            str(destination),
        ]
        logger.debug("Creating padded stream-copy clip: %s", " ".join(cmd))
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=max(60.0, duration * 2.0),
                **self._subprocess_window_kwargs(),
            )
        except subprocess.TimeoutExpired:
            self._remove_render_artifact(destination)
            return False, 0.0, "FFmpeg timed out creating the padded clip"
        except OSError as exc:
            self._remove_render_artifact(destination)
            return False, 0.0, f"Clip copy failed: {exc}"

        if cancel_event.is_set() or self._clip_shutdown_event.is_set():
            self._remove_render_artifact(destination)
            return False, 0.0, "Clip preparation was cancelled"
        output_size = destination.stat().st_size if destination.exists() else 0
        if result.returncode != 0 or output_size <= 1024:
            stderr = result.stderr.decode(errors="replace")[-500:] if result.stderr else ""
            self._remove_render_artifact(destination)
            return False, 0.0, stderr or "FFmpeg did not create a usable padded clip"

        actual_duration = self._media_duration_seconds(destination, duration)
        if actual_duration < 1.0:
            self._remove_render_artifact(destination)
            return False, 0.0, "The padded clip did not contain usable footage"
        return True, actual_duration, None

    def _render_final_clip(
        self,
        edit: ClipEditSession,
        start_seconds: float,
        end_seconds: float,
        destination: Path,
    ) -> tuple[bool, Optional[str]]:
        part_path = destination.with_name(f".{destination.stem}-{uuid.uuid4().hex}.part.mp4")
        rendered, error = self._render_transcoded_clip(
            edit,
            start_seconds,
            end_seconds,
            part_path,
            preview=False,
            source_path=edit.preview_path,
        )
        if not rendered:
            return False, error
        replace_error = self._replace_file_with_retry(part_path, destination, edit.cancel_event)
        if replace_error:
            logger.warning(
                "Clip atomic replacement failed: id=%s source=%s destination=%s error=%s",
                edit.id,
                part_path,
                destination,
                replace_error,
            )
            try:
                part_path.unlink(missing_ok=True)
            except OSError:
                pass
            return False, replace_error

        if destination != edit.output_path:
            try:
                edit.output_path.unlink(missing_ok=True)
            except OSError as exc:
                logger.warning("Could not remove prior clip after successful rename: %s", exc)
        return True, None

    def _render_transcoded_clip(
        self,
        edit: ClipEditSession,
        start_seconds: float,
        end_seconds: float,
        destination: Path,
        preview: bool,
        source_path: Optional[Path] = None,
    ) -> tuple[bool, Optional[str]]:
        ffmpeg_exe = self._get_ffmpeg_executable()
        if not ffmpeg_exe:
            return False, "FFmpeg not found. Set ffmpeg_path or add ffmpeg to PATH."
        duration = max(0.0, end_seconds - start_seconds)
        if duration < 1.0:
            return False, "A clip must be at least one second long"

        destination.parent.mkdir(parents=True, exist_ok=True)
        bitrate = self._estimated_source_video_bitrate(edit)
        if preview:
            nvenc_video_args = [
                "-c:v",
                "h264_nvenc",
                "-preset",
                "p1",
                "-tune",
                "hq",
                "-rc",
                "vbr",
                "-b:v",
                "4000000",
                "-maxrate",
                "6000000",
                "-bufsize",
                "8000000",
            ]
            cpu_video_args = ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "28"]
            audio_bitrate = "128k"
        else:
            nvenc_video_args = [
                "-c:v",
                "h264_nvenc",
                "-preset",
                "p5",
                "-tune",
                "hq",
                "-profile:v",
                "high",
                "-rc",
                "vbr",
                "-b:v",
                str(bitrate),
                "-maxrate",
                str(int(bitrate * 1.25)),
                "-bufsize",
                str(int(bitrate * 2)),
                "-spatial_aq",
                "1",
                "-temporal_aq",
                "1",
            ]
            cpu_video_args = ["-c:v", "libx264", "-preset", "medium", "-crf", "18"]
            audio_bitrate = "192k"

        render_source = source_path or edit.source_path
        common_prefix = [
            ffmpeg_exe,
            "-hide_banner",
            "-loglevel",
            "error",
            "-fflags",
            "+discardcorrupt",
            "-ss",
            f"{start_seconds:.6f}",
            "-i",
            str(render_source),
            "-t",
            f"{duration:.6f}",
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
        ]
        common_suffix = [
            "-c:a",
            "aac",
            "-b:a",
            audio_bitrate,
            "-avoid_negative_ts",
            "make_zero",
            "-movflags",
            "+faststart",
            "-y",
            str(destination),
        ]

        success, error = self._run_clip_render_command(
            common_prefix + nvenc_video_args + common_suffix,
            destination,
            duration,
            edit.cancel_event,
        )
        if success:
            return True, None
        if edit.cancel_event.is_set() or self._clip_shutdown_event.is_set():
            self._remove_render_artifact(destination)
            return False, "Clip preparation was cancelled"

        logger.warning("NVENC clip render failed; retrying with libx264: %s", error)
        self._remove_render_artifact(destination)
        success, error = self._run_clip_render_command(
            common_prefix + cpu_video_args + common_suffix,
            destination,
            duration,
            edit.cancel_event,
        )
        if not success:
            self._remove_render_artifact(destination)
        return success, error

    def _run_clip_render_command(
        self,
        cmd: list[str],
        destination: Path,
        duration_seconds: float,
        cancel_event: threading.Event,
    ) -> tuple[bool, Optional[str]]:
        logger.debug("Rendering editable clip: %s", " ".join(cmd))
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                **self._subprocess_window_kwargs(),
            )
        except Exception as exc:
            return False, f"Clip render failed: {exc}"

        deadline = time.monotonic() + max(120.0, duration_seconds * 4.0)
        while process.poll() is None:
            if cancel_event.is_set() or self._clip_shutdown_event.is_set():
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                return False, "Clip preparation was cancelled"
            if time.monotonic() >= deadline:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                return False, "FFmpeg timed out rendering the clip"
            time.sleep(0.1)

        _stdout, stderr = process.communicate()
        output_size = destination.stat().st_size if destination.exists() else 0
        if process.returncode == 0 and output_size > 1024:
            usable, validation_error = self._validate_clip_output(
                destination,
                duration_seconds,
            )
            if usable:
                return True, None
            return False, validation_error
        error = stderr.decode(errors="replace")[-500:] if stderr else ""
        return False, error or "FFmpeg did not create a usable clip"

    def _validate_clip_output(
        self,
        destination: Path,
        expected_duration_seconds: float,
    ) -> tuple[bool, Optional[str]]:
        ffprobe_exe = self._get_ffprobe_executable()
        if not ffprobe_exe:
            logger.warning("ffprobe was not found; using file-size clip validation only")
            return True, None
        cmd = [
            ffprobe_exe,
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type,duration,avg_frame_rate:format=duration",
            "-of",
            "json",
            str(destination),
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=15,
                **self._subprocess_window_kwargs(),
            )
            if result.returncode != 0:
                stderr = result.stderr.decode(errors="replace")[-500:] if result.stderr else ""
                return False, stderr or "ffprobe could not validate the rendered clip"
            payload = json.loads(result.stdout.decode("utf-8"))
        except (
            OSError,
            subprocess.TimeoutExpired,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as exc:
            return False, f"Could not validate the rendered clip: {exc}"

        video_stream = next(
            (
                stream
                for stream in payload.get("streams", [])
                if stream.get("codec_type") == "video"
            ),
            None,
        )
        if not video_stream:
            return False, "Rendered clip does not contain a usable video stream"

        actual_duration = None
        for duration_value in (
            video_stream.get("duration"),
            payload.get("format", {}).get("duration"),
        ):
            try:
                actual_duration = float(duration_value)
                break
            except (TypeError, ValueError):
                continue
        if actual_duration is None:
            return False, "Could not determine the rendered clip duration"

        frame_seconds = self._frame_duration_seconds(video_stream.get("avg_frame_rate"))
        tolerance = max(0.02, frame_seconds + 0.005)
        if abs(actual_duration - expected_duration_seconds) > tolerance:
            return (
                False,
                "Rendered clip duration did not match the selected boundaries "
                f"({actual_duration:.3f}s instead of {expected_duration_seconds:.3f}s)",
            )
        return True, None

    def _media_duration_seconds(self, path: Path, fallback: float) -> float:
        ffprobe_exe = self._get_ffprobe_executable()
        if not ffprobe_exe or not path.exists():
            return max(0.0, fallback)
        cmd = [
            ffprobe_exe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=15,
                **self._subprocess_window_kwargs(),
            )
            if result.returncode == 0:
                duration = float(result.stdout.decode("utf-8").strip())
                if math.isfinite(duration) and duration > 0:
                    return duration
        except (
            OSError,
            subprocess.TimeoutExpired,
            AttributeError,
            TypeError,
            UnicodeDecodeError,
            ValueError,
        ) as exc:
            logger.debug("Could not probe clip duration for %s: %s", path, exc)
        return max(0.0, fallback)

    @staticmethod
    def _frame_duration_seconds(frame_rate: Any) -> float:
        try:
            numerator, denominator = str(frame_rate).split("/", 1)
            frames_per_second = float(numerator) / float(denominator)
            if frames_per_second > 0:
                return 1.0 / frames_per_second
        except (TypeError, ValueError, ZeroDivisionError):
            pass
        return 1.0 / 30.0

    def _estimated_source_video_bitrate(self, edit: ClipEditSession) -> int:
        available = max(1.0, self._source_available_seconds(edit))
        try:
            combined = int(edit.source_path.stat().st_size * 8 / available)
        except OSError:
            combined = 8_000_000
        video = combined - 192_000
        return max(2_000_000, min(25_000_000, video))

    @staticmethod
    def _copy_provisional_preview(source: Path, destination: Path) -> Optional[str]:
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            return None
        except OSError as exc:
            try:
                destination.unlink(missing_ok=True)
            except OSError:
                pass
            return str(exc)

    def _replace_file_with_retry(
        self,
        source: Path,
        destination: Path,
        cancel_event: threading.Event,
    ) -> Optional[str]:
        for attempt in range(10):
            if cancel_event.is_set() or self._clip_shutdown_event.is_set():
                return "Clip preparation was cancelled"
            try:
                os.replace(source, destination)
                return None
            except PermissionError as exc:
                if attempt == 9:
                    return f"Could not replace the open clip file: {exc}"
                time.sleep(0.15)
            except OSError as exc:
                return f"Could not save the clip: {exc}"
        return "Could not save the clip"

    def _rename_clip_output(self, source: Path, destination: Path) -> Optional[str]:
        if source == destination:
            return None
        destination.parent.mkdir(parents=True, exist_ok=True)
        return self._replace_file_with_retry(source, destination, threading.Event())

    def _remove_preview_file(self, edit: ClipEditSession) -> None:
        self._schedule_preview_cleanup(edit.preview_path, edit.output_path)

    def _schedule_preview_cleanup(self, path: Path, output_path: Path) -> None:
        if path == output_path:
            return
        threading.Thread(
            target=self._remove_preview_path_with_retry,
            args=(path,),
            name=f"clip-preview-cleanup-{uuid.uuid4().hex[:8]}",
            daemon=True,
        ).start()

    @staticmethod
    def _remove_preview_path_with_retry(path: Path) -> None:
        for attempt in range(20):
            try:
                path.unlink(missing_ok=True)
                return
            except PermissionError:
                if attempt < 19:
                    time.sleep(0.1)
            except OSError as exc:
                logger.warning("Could not remove temporary clip preview %s: %s", path, exc)
                return
        logger.warning("Could not remove open temporary clip preview: %s", path)

    @staticmethod
    def _remove_render_artifact(path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Local HLS proxy
    # ------------------------------------------------------------------

    def _ensure_proxy(self) -> None:
        if self._proxy:
            return
        self._proxy = _PlaybackProxyServer(("127.0.0.1", 0), self)
        self._proxy_thread = threading.Thread(
            target=self._proxy.serve_forever,
            name="playback-proxy",
            daemon=True,
        )
        self._proxy_thread.start()

    def _playlist_url(self, session_id: str, cache_bust: bool = False) -> str:
        if not self._proxy:
            raise RuntimeError("Playback proxy has not started")
        host, port = self._proxy.server_address
        host = str(host)
        suffix = f"?v={int(time.time() * 1000)}" if cache_bust else ""
        return f"http://{host}:{port}/playlist/{session_id}.m3u8{suffix}"

    def _media_url(self, token: str, revision: int) -> str:
        self._ensure_proxy()
        if not self._proxy:
            raise RuntimeError("Playback proxy has not started")
        host, port = self._proxy.server_address
        host = str(host)
        return f"http://{host}:{port}/media/{token}.mp4?v={revision}"

    def handle_proxy_request(
        self,
        handler: BaseHTTPRequestHandler,
        head_only: bool = False,
    ) -> None:
        parsed = urlparse(handler.path)
        if parsed.path.startswith("/media/"):
            token = Path(parsed.path).stem
            with self._lock:
                media_path = self._media_files.get(token)
            if not media_path:
                handler.send_error(404)
                return
            self._serve_media_file(handler, media_path, head_only=head_only)
            return
        if parsed.path.startswith("/playlist/"):
            session_id = Path(parsed.path).stem
            session = self._get_session_for_proxy(session_id)
            self._proxy_playlist(handler, session.stream_url, session)
            return
        if parsed.path.startswith("/resource/"):
            session_id = parsed.path.strip("/").split("/", 1)[1]
            session = self._get_session_for_proxy(session_id)
            query = parse_qs(parsed.query)
            target = unquote(query.get("url", [""])[0])
            if not target:
                handler.send_error(400, "Missing resource URL")
                return
            self._proxy_resource(handler, target, session)
            return
        handler.send_error(404)

    def _serve_media_file(
        self,
        handler: BaseHTTPRequestHandler,
        path: Path,
        head_only: bool = False,
    ) -> None:
        if not path.exists() or not path.is_file():
            handler.send_error(404)
            return
        size = path.stat().st_size
        start = 0
        end = max(0, size - 1)
        status = 200
        range_header = handler.headers.get("Range", "")
        if range_header.startswith("bytes="):
            requested = range_header[6:].split(",", 1)[0]
            start_text, _, end_text = requested.partition("-")
            try:
                if start_text:
                    start = int(start_text)
                    end = int(end_text) if end_text else end
                elif end_text:
                    suffix_length = int(end_text)
                    start = max(0, size - suffix_length)
            except ValueError:
                handler.send_error(416)
                return
            if start < 0 or start >= size or end < start:
                handler.send_response(416)
                handler.send_header("Content-Range", f"bytes */{size}")
                handler.end_headers()
                return
            end = min(end, size - 1)
            status = 206

        content_length = max(0, end - start + 1)
        handler.send_response(status)
        handler.send_header("Access-Control-Allow-Origin", "*")
        handler.send_header("Accept-Ranges", "bytes")
        handler.send_header("Cache-Control", "no-store")
        handler.send_header("Content-Type", "video/mp4")
        handler.send_header("Content-Length", str(content_length))
        if status == 206:
            handler.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        handler.end_headers()
        if head_only:
            return

        remaining = content_length
        with path.open("rb") as source:
            source.seek(start)
            while remaining > 0:
                chunk = source.read(min(65536, remaining))
                if not chunk:
                    break
                handler.wfile.write(chunk)
                remaining -= len(chunk)

    def _get_session_for_proxy(self, session_id: str) -> WebStreamSession:
        with self._lock:
            session = self._session
            if not session or session.session_id != session_id:
                raise FileNotFoundError("Stream session is no longer active")
            return session

    def _proxy_playlist(
        self,
        handler: BaseHTTPRequestHandler,
        playlist_url: str,
        session: WebStreamSession,
    ) -> None:
        response = requests.get(
            playlist_url,
            headers=self._proxy_headers(session),
            timeout=self._network_timeout(),
        )
        response.raise_for_status()
        text = response.text
        rewritten = self._rewrite_playlist(text, playlist_url, session.session_id)
        body = rewritten.encode("utf-8")
        self._send_headers(handler, 200, "application/vnd.apple.mpegurl", len(body))
        handler.wfile.write(body)

    def _proxy_resource(
        self,
        handler: BaseHTTPRequestHandler,
        target_url: str,
        session: WebStreamSession,
    ) -> None:
        response = requests.get(
            target_url,
            headers=self._proxy_headers(session),
            timeout=self._network_timeout(),
            stream=True,
        )
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "application/octet-stream")
        if "mpegurl" in content_type or target_url.split("?", 1)[0].endswith(".m3u8"):
            text = response.text
            rewritten = self._rewrite_playlist(text, target_url, session.session_id)
            body = rewritten.encode("utf-8")
            self._send_headers(handler, 200, "application/vnd.apple.mpegurl", len(body))
            handler.wfile.write(body)
            return

        self._send_headers(handler, 200, content_type, None)
        for chunk in response.iter_content(chunk_size=65536):
            if chunk:
                handler.wfile.write(chunk)

    def _rewrite_playlist(self, text: str, base_url: str, session_id: str) -> str:
        # Reusing the twitch_low_latency setting here is what actually makes it
        # affect playback: previously it only reached the separate recording
        # thread's streamlink reader, never the browser-facing proxy below.
        low_latency = self.config.get("twitch_low_latency", True)
        lines = []
        regular_durations: list[float] = []
        last_prefetch_duration: Optional[float] = None
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                lines.append(raw_line)
                continue
            if low_latency and line.startswith(_TWITCH_PREFETCH_TAG_PREFIX):
                # Chain off the previous prefetch segment's duration if there is
                # one (mirrors TwitchM3U8Parser), otherwise estimate from the
                # average of this playlist's regular segments. With neither
                # available there's nothing sane to synthesize, so drop it -
                # same net effect as today's untouched pass-through.
                duration = last_prefetch_duration
                if duration is None and regular_durations:
                    duration = sum(regular_durations) / len(regular_durations)
                if duration is not None:
                    last_prefetch_duration = duration
                    uri = line[len(_TWITCH_PREFETCH_TAG_PREFIX) :]
                    absolute = urljoin(base_url, uri)
                    lines.append(f"#EXTINF:{duration:.3f},")
                    lines.append(self._resource_url(session_id, absolute))
                continue
            if line.startswith("#"):
                match = _EXTINF_RE.match(line)
                if match:
                    regular_durations.append(float(match.group(1)))
                    last_prefetch_duration = None
                lines.append(self._rewrite_key_uri(raw_line, base_url, session_id))
                continue
            absolute = urljoin(base_url, line)
            lines.append(self._resource_url(session_id, absolute))
        return "\n".join(lines) + "\n"

    def _rewrite_key_uri(self, line: str, base_url: str, session_id: str) -> str:
        def replace(match: re.Match[str]) -> str:
            absolute = urljoin(base_url, match.group(1))
            return f'URI="{self._resource_url(session_id, absolute)}"'

        return re.sub(r'URI="([^"]+)"', replace, line)

    def _resource_url(self, session_id: str, target_url: str) -> str:
        if not self._proxy:
            raise RuntimeError("Playback proxy has not started")
        host, port = self._proxy.server_address
        host = str(host)
        return f"http://{host}:{port}/resource/{session_id}?url={quote(target_url, safe='')}"

    def _send_headers(
        self,
        handler: BaseHTTPRequestHandler,
        status: int,
        content_type: str,
        content_length: Optional[int],
    ) -> None:
        handler.send_response(status)
        handler.send_header("Access-Control-Allow-Origin", "*")
        handler.send_header("Cache-Control", "no-store")
        handler.send_header("Content-Type", content_type)
        if content_length is not None:
            handler.send_header("Content-Length", str(content_length))
        handler.end_headers()

    def _proxy_headers(self, session: WebStreamSession) -> dict[str, str]:
        headers = session.stream_args.get("headers", {}) if session.stream_args else {}
        return dict(headers) if isinstance(headers, dict) else {}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_ffmpeg_executable(self) -> Optional[str]:
        configured = self.config.get("ffmpeg_path", "")
        if configured and Path(configured).exists():
            return configured
        return shutil.which("ffmpeg")

    def _get_ffprobe_executable(self) -> Optional[str]:
        ffmpeg_exe = self._get_ffmpeg_executable()
        if ffmpeg_exe:
            ffmpeg_path = Path(ffmpeg_exe)
            for name in ("ffprobe.exe", "ffprobe"):
                sibling = ffmpeg_path.with_name(name)
                if sibling.exists():
                    return str(sibling)
        return shutil.which("ffprobe")

    @staticmethod
    def _subprocess_window_kwargs() -> dict[str, Any]:
        """Prevent FFmpeg/FFprobe console flashes in the packaged Windows app."""
        if os.name != "nt":
            return {}
        creation_flag = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        return {"creationflags": creation_flag} if creation_flag else {}

    def _int_setting(self, key: str, default: int) -> int:
        value = self.config.get(key, default)
        return value if isinstance(value, int) else default

    def _retry_attempts(self) -> int:
        return self._int_setting("connection_retry_attempts", 3)

    def _retry_delay(self) -> int:
        return self._int_setting("retry_delay", 5)

    def _network_timeout(self) -> int:
        return self._int_setting("network_timeout", 30)

    def _clip_duration_setting(self) -> int:
        return self._int_setting("stream_manager_clip_duration_seconds", 30)

    def _recorded_ready_seconds(self, session: WebStreamSession) -> float:
        if not session.recording_start_time:
            return 0.0
        recorded_at = session.last_recorded_at
        if recorded_at is None and session.recording_path:
            path = Path(session.recording_path)
            if path.exists() and path.stat().st_size > 0:
                recorded_at = datetime.fromtimestamp(path.stat().st_mtime)
        if recorded_at is None:
            return 0.0
        return max(0.0, (recorded_at - session.recording_start_time).total_seconds())

    def _clip_status(self, session: WebStreamSession) -> dict[str, Any]:
        ready_seconds = self._recorded_ready_seconds(session)
        duration = self._clip_duration_setting()
        if not session.recording_path:
            return {"ready": False, "ready_seconds": ready_seconds, "reason": None}
        if ready_seconds < duration:
            return {
                "ready": False,
                "ready_seconds": ready_seconds,
                "reason": (
                    "Recording is warming up "
                    f"({int(ready_seconds)}s captured for a {duration}s clip)."
                ),
            }
        return {"ready": True, "ready_seconds": ready_seconds, "reason": None}

    def _mark_recording_write(self, session: WebStreamSession, byte_count: int) -> bool:
        now = datetime.now()
        with self._lock:
            session.recorded_bytes += byte_count
            session.last_recorded_at = now
            ready_before = session.recording_ready_at is not None
            ready_seconds = self._recorded_ready_seconds(session)
            if not ready_before and ready_seconds >= self._clip_duration_setting():
                session.recording_ready_at = now

            last_push = session.last_recording_state_pushed_at
            should_push = session.recording_ready_at is not None and not ready_before
            if last_push is None:
                should_push = True
            elif (now - last_push).total_seconds() >= RECORDING_STATE_PUSH_INTERVAL_SECONDS:
                should_push = True
            if should_push:
                session.last_recording_state_pushed_at = now
            return should_push

    def _sleep_interruptibly(self, stop_event: threading.Event, seconds: int) -> bool:
        deadline = time.monotonic() + seconds
        while not stop_event.is_set() and time.monotonic() < deadline:
            time.sleep(min(0.1, max(0.0, deadline - time.monotonic())))
        return not stop_event.is_set()

    def cleanup_recording(self) -> None:
        with self._lock:
            session = self._session
        if not session or not session.recording_path:
            return
        try:
            Path(session.recording_path).unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Could not remove recording: %s", exc)


def open_path_in_explorer(path: Path) -> None:
    """Open a path in the platform file browser."""
    resolved = path.resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        os.startfile(str(resolved))  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["xdg-open", str(resolved)])


def reveal_path_in_explorer(path: Path) -> None:
    """Open the platform file browser with a specific file pre-selected."""
    resolved = path.resolve()
    if not resolved.exists():
        open_path_in_explorer(resolved.parent)
        return
    if os.name == "nt":
        subprocess.Popen(["explorer", f"/select,{resolved}"])
    else:
        open_path_in_explorer(resolved.parent)
