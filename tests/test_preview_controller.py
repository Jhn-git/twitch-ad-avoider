"""Tests for preview-controller caching and timeout wiring."""

import time

from PySide6.QtCore import QCoreApplication

from gui_qt.controllers import preview_controller as preview_controller_module
from gui_qt.controllers.preview_controller import StreamPreviewController
from src.stream_preview import StreamPreviewInfo


def _wait_until(predicate, timeout_seconds: float = 3.0) -> None:
    app = QCoreApplication.instance() or QCoreApplication([])
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("Timed out waiting for preview-controller work to finish")


def test_request_preview_reuses_fresh_cached_result(monkeypatch):
    """A second request for the same channel should replay the in-memory cache."""
    QCoreApplication.instance() or QCoreApplication([])
    calls = {"info": [], "image": []}

    def fake_info(channel: str, timeout: int):
        calls["info"].append((channel, timeout))
        return StreamPreviewInfo(
            channel=channel,
            is_live=True,
            title="Cached title",
            preview_image_url="https://example.com/preview.jpg",
        )

    def fake_image(url: str, timeout: int):
        calls["image"].append((url, timeout))
        return b"preview-bytes"

    monkeypatch.setattr(preview_controller_module, "fetch_stream_preview_info", fake_info)
    monkeypatch.setattr(preview_controller_module, "fetch_image_bytes", fake_image)

    controller = StreamPreviewController()
    preview_events = []
    image_events = []
    controller.preview_ready.connect(lambda channel, info: preview_events.append((channel, info)))
    controller.image_ready.connect(lambda channel, data: image_events.append((channel, data)))

    controller.request_preview("ninja", timeout_seconds=17)
    controller._debounce_timer.stop()
    controller._start_fetch()

    _wait_until(
        lambda: controller._thread is None and len(preview_events) == 1 and len(image_events) == 1
    )

    assert calls["info"] == [("ninja", 17)]
    assert calls["image"] == [("https://example.com/preview.jpg", 17)]
    assert preview_events[0][0] == "ninja"
    assert image_events[0] == ("ninja", b"preview-bytes")

    preview_events.clear()
    image_events.clear()

    controller.request_preview("ninja", timeout_seconds=17)

    _wait_until(lambda: len(preview_events) == 1 and len(image_events) == 1)

    assert calls["info"] == [("ninja", 17)]
    assert calls["image"] == [("https://example.com/preview.jpg", 17)]
    assert preview_events[0][1].title == "Cached title"
    assert image_events[0] == ("ninja", b"preview-bytes")
