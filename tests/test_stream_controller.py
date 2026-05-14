"""Tests for Qt stream controller lifecycle handling."""

from PySide6.QtCore import QCoreApplication, QObject, QThread

from gui_qt.controllers import stream_controller
from gui_qt.controllers.stream_controller import StreamController


class DummyTwitchViewer:
    """Minimal TwitchViewer stand-in for controller tests."""

    def __init__(self, config):
        self.config = config


class FakeSignal:
    """Minimal Qt signal stand-in for connection-only tests."""

    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)


class FakeThread:
    """Minimal QThread stand-in that does not start background work."""

    def __init__(self):
        self.started = FakeSignal()
        self.finished = FakeSignal()
        self.started_called = False

    def start(self):
        self.started_called = True

    def quit(self):
        pass

    def isRunning(self):
        return False

    def deleteLater(self):
        pass


class FakeStreamWorker:
    """Minimal StreamWorker stand-in for start_stream wiring tests."""

    def __init__(self, twitch_viewer, channel, quality):
        self.twitch_viewer = twitch_viewer
        self.channel = channel
        self.quality = quality
        self.process = None
        self.started = FakeSignal()
        self.finished = FakeSignal()
        self.error = FakeSignal()

    def moveToThread(self, thread):
        self.thread = thread

    def run(self):
        pass

    def deleteLater(self):
        pass


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


def test_start_stream_writes_preferred_quality(monkeypatch, mock_config_manager):
    """Starting a stream updates the preferred_quality config key."""
    QCoreApplication.instance() or QCoreApplication([])
    monkeypatch.setattr(stream_controller, "TwitchViewer", DummyTwitchViewer)
    monkeypatch.setattr(stream_controller, "StreamWorker", FakeStreamWorker)
    monkeypatch.setattr(stream_controller, "QThread", FakeThread)

    controller = StreamController(mock_config_manager)

    controller.start_stream("ninja", "720p")

    assert mock_config_manager.get("preferred_quality") == "720p"
    assert "quality" not in mock_config_manager.get_all()


def test_start_stream_rejects_invalid_quality(monkeypatch, mock_config_manager):
    """Invalid quality does not create a worker or update config."""
    QCoreApplication.instance() or QCoreApplication([])
    monkeypatch.setattr(stream_controller, "TwitchViewer", DummyTwitchViewer)
    monkeypatch.setattr(stream_controller, "StreamWorker", FakeStreamWorker)
    monkeypatch.setattr(stream_controller, "QThread", FakeThread)

    controller = StreamController(mock_config_manager)

    controller.start_stream("ninja", "1080p")

    assert controller.current_worker is None
    assert mock_config_manager.get("preferred_quality") == "best"
    assert "quality" not in mock_config_manager.get_all()
