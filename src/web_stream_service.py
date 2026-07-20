"""Streamlink-backed playback and recording services for the web GUI."""

from __future__ import annotations

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

    def create_clip(self, duration_seconds: int, behind_live_seconds: float = 0.0) -> dict:
        """Create a clip from the rolling local recording.

        ``behind_live_seconds`` is how far the caller's playhead is from the
        live edge (e.g. the browser is paused or scrubbed back), so the clip
        ends at the caller's position instead of always ending at "now".
        """
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
            requested_wall_end = datetime.now() - timedelta(seconds=behind)
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
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = clip_dir / f"{session.channel}_{timestamp}.mp4"
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
            result = subprocess.run(cmd, capture_output=True, timeout=60)
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "FFmpeg timed out creating clip"}
        except Exception as exc:
            return {"ok": False, "error": f"Clip failed: {exc}"}

        output_size = output_path.stat().st_size if output_path.exists() else 0
        if output_size > 1024:
            self._add_activity("success", f"Clip saved: {output_path}", "CLIP")
            self._push_event({"type": "clip_created", "path": str(output_path)})
            return {"ok": True, "path": str(output_path)}

        stderr = result.stderr.decode(errors="replace") if result.stderr else ""
        return {"ok": False, "error": stderr[-500:] or "FFmpeg did not create a usable clip"}

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

    def handle_proxy_request(self, handler: BaseHTTPRequestHandler) -> None:
        parsed = urlparse(handler.path)
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
