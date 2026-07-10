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
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import parse_qs, quote, unquote, urljoin, urlparse

import requests
import streamlink

from src.config_manager import ConfigManager
from src.constants import CLIPS_DIR, TEMP_DIR
from src.exceptions import TwitchStreamError, ValidationError
from src.logging_config import get_logger
from src.validators import validate_channel_name

logger = get_logger(__name__)

StreamEventCallback = Callable[[dict], None]
ActivityCallback = Callable[[str, str, Optional[str]], None]


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

        selected_quality, stream_url, stream_args, stream_obj = self._resolve_stream(
            channel, quality
        )
        session_id = uuid.uuid4().hex
        playback_url = self._playlist_url(session_id)
        recording_path, recording_start = self._prepare_recording(channel)

        session = WebStreamSession(
            session_id=session_id,
            channel=channel,
            quality=selected_quality,
            stream_url=stream_url,
            stream_args=stream_args,
            playback_url=playback_url,
            recording_path=recording_path,
            recording_start_time=recording_start,
        )

        with self._lock:
            self._session = session

        if recording_path:
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
                    "last_error": None,
                }

            return {
                "active": session.status in {"starting", "live", "reconnecting"},
                "channel": session.channel,
                "quality": session.quality,
                "playback_url": session.playback_url,
                "status": session.status,
                "recording": bool(session.recording_path),
                "last_error": session.last_error,
            }

    def create_clip(self, duration_seconds: int) -> dict:
        """Create a clip from the rolling local recording."""
        with self._lock:
            session = self._session

        if not session or not session.recording_path or not session.recording_start_time:
            return {"ok": False, "error": "No active recording to clip"}

        source_path = Path(session.recording_path)
        if not source_path.exists() or source_path.stat().st_size <= 0:
            return {"ok": False, "error": "Recording is not ready yet"}

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
        elapsed = (datetime.now() - session.recording_start_time).total_seconds()
        start_offset = max(0.0, elapsed - duration_seconds)

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

    def _prepare_recording(self, channel: str) -> tuple[Optional[str], Optional[datetime]]:
        if not self.config.get("clip_enabled", True):
            return None, None
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        rec_path = TEMP_DIR / f"recording_{channel}.ts"
        try:
            if rec_path.exists():
                rec_path.unlink()
        except OSError as exc:
            logger.warning("Could not remove stale recording: %s", exc)
        return str(rec_path), datetime.now()

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
        lines = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                lines.append(raw_line)
                continue
            if line.startswith("#"):
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

    def _retry_attempts(self) -> int:
        attempts = self.config.get("connection_retry_attempts", 3)
        return attempts if isinstance(attempts, int) else 3

    def _retry_delay(self) -> int:
        delay = self.config.get("retry_delay", 5)
        return delay if isinstance(delay, int) else 5

    def _network_timeout(self) -> int:
        timeout = self.config.get("network_timeout", 30)
        return timeout if isinstance(timeout, int) else 30

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
