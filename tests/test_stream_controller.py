"""Tests for Qt stream controller lifecycle handling."""

from PySide6.QtCore import QCoreApplication, QObject, QThread

from gui_qt.controllers import stream_controller
from gui_qt.controllers.stream_controller import StreamController


class DummyTwitchViewer:
    """Minimal TwitchViewer stand-in for controller tests."""

    def __init__(self, config):
        self.config = config


def test_stale_thread_cleanup_does_not_clear_current_stream(monkeypatch, mock_config_manager):
    """Old thread cleanup must not delete references for a newer stream."""
    QCoreApplication.instance() or QCoreApplication([])
    monkeypatch.setattr(stream_controller, "TwitchViewer", DummyTwitchViewer)

    controller = StreamController(mock_config_manager)

    old_thread = QThread()
    old_worker = QObject()
    new_thread = QThread()
    new_worker = QObject()
    current_process = object()

    controller._stream_generation = 2
    controller.current_thread = new_thread
    controller.current_worker = new_worker
    controller.current_channel = "newchannel"
    controller.current_process = current_process
    controller.current_quality = "best"

    controller._cleanup_thread(old_thread, old_worker, generation=1)

    assert controller.current_thread is new_thread
    assert controller.current_worker is new_worker
    assert controller.current_channel == "newchannel"
    assert controller.current_process is current_process
    assert controller.current_quality == "best"

    controller._cleanup_thread(new_thread, new_worker, generation=2)
