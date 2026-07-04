"""
Async, race-safe stream preview fetching for the Qt GUI.

Mirrors the QThread worker pattern used by StreamController/ClipWorker in
stream_controller.py: work happens on a background QObject moved to a
QThread, and results are delivered back via signals.
"""

import time
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QObject, QThread, QTimer, Signal

from src.logging_config import get_logger
from src.stream_preview import StreamPreviewInfo, fetch_image_bytes, fetch_stream_preview_info

logger = get_logger(__name__)

_DEBOUNCE_MS = 250
_CACHE_TTL_SECONDS = 60


@dataclass
class _PreviewCacheEntry:
    """In-memory preview cache entry for the current app session."""

    info: StreamPreviewInfo
    cached_at: float
    image_fetch_attempted: bool = False
    image_bytes: Optional[bytes] = None


class PreviewWorker(QObject):
    """Fetches stream metadata and, if live, its preview thumbnail bytes."""

    finished = Signal(object)  # StreamPreviewInfo
    image_ready = Signal(bytes)
    image_failed = Signal()
    done = Signal()

    def __init__(self, channel: str, timeout_seconds: int):
        super().__init__()
        self.channel = channel
        self.timeout_seconds = timeout_seconds
        self.info = StreamPreviewInfo(channel=channel, is_live=False)
        self.image_bytes: Optional[bytes] = None
        self.image_fetch_attempted = False

    def run(self) -> None:
        self.info = fetch_stream_preview_info(self.channel, timeout=self.timeout_seconds)
        self.finished.emit(self.info)

        if self.info.is_live and self.info.preview_image_url:
            self.image_fetch_attempted = True
            self.image_bytes = fetch_image_bytes(
                self.info.preview_image_url,
                timeout=self.timeout_seconds,
            )
            if self.image_bytes:
                self.image_ready.emit(self.image_bytes)
            else:
                self.image_failed.emit()

        self.done.emit()


class StreamPreviewController(QObject):
    """
    Debounced, race-safe controller for fetching a single channel's preview.

    Each call to request_preview() bumps an internal generation counter so
    late-arriving results from a superseded request are ignored, and restarts
    a short debounce timer so rapid selection changes (e.g. arrow-key
    navigation through the favorites list) only trigger one network fetch.
    """

    preview_ready = Signal(str, object)  # channel, StreamPreviewInfo
    image_ready = Signal(str, bytes)  # channel, image bytes
    image_failed = Signal(str)  # channel

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._thread: Optional[QThread] = None
        self._worker: Optional[PreviewWorker] = None
        self._generation = 0
        self._pending_channel: Optional[str] = None
        self._pending_timeout_seconds = 30
        self._cache: dict[str, _PreviewCacheEntry] = {}

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(_DEBOUNCE_MS)
        self._debounce_timer.timeout.connect(self._start_fetch)

    def request_preview(self, channel: str, timeout_seconds: int) -> None:
        """Schedule a debounced preview fetch, superseding any prior request."""
        self._generation += 1
        self._pending_channel = channel
        self._pending_timeout_seconds = timeout_seconds
        cached = self._get_cached_entry(channel)
        if cached is not None:
            self._debounce_timer.stop()
            self._emit_cached_preview(channel, cached, self._generation)
            return
        self._debounce_timer.start()

    def clear(self) -> None:
        """Cancel any pending or in-flight fetch."""
        self._generation += 1
        self._pending_channel = None
        self._debounce_timer.stop()

    def _start_fetch(self) -> None:
        channel = self._pending_channel
        if not channel:
            return

        generation = self._generation

        worker = PreviewWorker(channel, self._pending_timeout_seconds)
        thread = QThread()
        self._worker = worker
        self._thread = thread

        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(lambda info, gen=generation: self._on_finished(info, gen))
        worker.image_ready.connect(
            lambda data, ch=channel, gen=generation: self._on_image_ready(ch, data, gen)
        )
        worker.image_failed.connect(
            lambda ch=channel, gen=generation: self._on_image_failed(ch, gen)
        )
        worker.done.connect(thread.quit)
        thread.finished.connect(lambda t=thread, w=worker: self._cleanup_thread(t, w))

        thread.start()

    def _on_finished(self, info: StreamPreviewInfo, generation: int) -> None:
        if generation != self._generation:
            logger.debug(f"Ignoring stale preview result for {info.channel}")
            return
        self.preview_ready.emit(info.channel, info)

    def _on_image_ready(self, channel: str, data: bytes, generation: int) -> None:
        if generation != self._generation:
            return
        self.image_ready.emit(channel, data)

    def _on_image_failed(self, channel: str, generation: int) -> None:
        if generation != self._generation:
            return
        self.image_failed.emit(channel)

    def _cleanup_thread(self, thread: QThread, worker: PreviewWorker) -> None:
        self._cache[worker.channel] = _PreviewCacheEntry(
            info=worker.info,
            cached_at=time.monotonic(),
            image_fetch_attempted=worker.image_fetch_attempted,
            image_bytes=worker.image_bytes,
        )
        thread.deleteLater()
        worker.deleteLater()
        if self._thread is thread:
            self._thread = None
        if self._worker is worker:
            self._worker = None

    def _get_cached_entry(self, channel: str) -> Optional[_PreviewCacheEntry]:
        entry = self._cache.get(channel)
        if entry is None:
            return None

        if time.monotonic() - entry.cached_at > _CACHE_TTL_SECONDS:
            self._cache.pop(channel, None)
            return None

        return entry

    def _emit_cached_preview(
        self,
        channel: str,
        entry: _PreviewCacheEntry,
        generation: int,
    ) -> None:
        """Replay a fresh cached preview on the next event-loop turn."""

        def emit() -> None:
            if generation != self._generation:
                return

            self.preview_ready.emit(channel, entry.info)

            if not entry.info.is_live or not entry.info.preview_image_url:
                return

            if entry.image_bytes:
                self.image_ready.emit(channel, entry.image_bytes)
            elif entry.image_fetch_attempted:
                self.image_failed.emit(channel)

        QTimer.singleShot(0, emit)
