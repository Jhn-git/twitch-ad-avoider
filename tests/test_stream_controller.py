"""Tests for Qt stream controller lifecycle handling."""

from PySide6.QtCore import QCoreApplication, QObject, QThread

from gui_qt.controllers import stream_controller
from gui_qt.controllers.stream_controller import StreamController, StreamWorker


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

    def emit(self, *args):
        for callback in self.callbacks:
            callback(*args)


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
        self.reconnecting = FakeSignal()

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


class FakeProcess:
    """Player process stand-in with a configurable wait return code."""

    pid = 1234

    def __init__(self, return_code, on_wait=None, end_reason=None, ended_from_stream=False):
        self.return_code = return_code
        self.on_wait = on_wait
        self.end_reason = end_reason
        self.ended_from_stream = ended_from_stream

    def wait(self, timeout=None):
        if self.on_wait:
            self.on_wait()
        return self.return_code

    def poll(self):
        return self.return_code


class FakeRetryTwitchViewer:
    """TwitchViewer stand-in returning one fake process per watch_stream call."""

    def __init__(self, config, processes):
        self.config = config
        self.processes = list(processes)
        self.watch_calls = 0

    def watch_stream(self, channel):
        self.watch_calls += 1
        return self.processes.pop(0)


def _collect_worker_signals(worker):
    started = []
    finished = []
    errors = []
    reconnecting = []

    worker.started.connect(lambda: started.append(True))
    worker.finished.connect(lambda: finished.append(True))
    worker.error.connect(errors.append)
    worker.reconnecting.connect(reconnecting.append)

    return started, finished, errors, reconnecting


def test_stream_worker_retries_after_nonzero_exit(monkeypatch, mock_config_manager):
    """Unexpected player crashes relaunch the stream and then finish cleanly."""
    QCoreApplication.instance() or QCoreApplication([])
    mock_config_manager.set("connection_retry_attempts", 3)
    mock_config_manager.set("retry_delay", 5)
    viewer = FakeRetryTwitchViewer(mock_config_manager, [FakeProcess(1), FakeProcess(0)])
    worker = StreamWorker(viewer, "ninja", "best")
    started, finished, errors, reconnecting = _collect_worker_signals(worker)
    monkeypatch.setattr(worker, "_wait_before_retry", lambda delay: True)

    worker.run()

    assert viewer.watch_calls == 2
    assert len(started) == 2
    assert len(finished) == 1
    assert errors == []
    assert reconnecting == [
        "Stream ended unexpectedly (exit code 1); reconnecting in 5s (attempt 1/3)"
    ]


def test_stream_worker_errors_after_retries_exhausted(monkeypatch, mock_config_manager):
    """Final error is emitted only after configured reconnect attempts are used."""
    QCoreApplication.instance() or QCoreApplication([])
    mock_config_manager.set("connection_retry_attempts", 2)
    mock_config_manager.set("retry_delay", 1)
    viewer = FakeRetryTwitchViewer(
        mock_config_manager,
        [FakeProcess(1), FakeProcess(1), FakeProcess(1)],
    )
    worker = StreamWorker(viewer, "ninja", "best")
    started, finished, errors, reconnecting = _collect_worker_signals(worker)
    monkeypatch.setattr(worker, "_wait_before_retry", lambda delay: True)

    worker.run()

    assert viewer.watch_calls == 3
    assert len(started) == 3
    assert finished == []
    assert len(reconnecting) == 2
    assert len(errors) == 1
    assert errors[0] == "Stream ended unexpectedly with code 1 after 2 reconnect attempts"


def test_stream_worker_does_not_retry_when_stop_requested(monkeypatch, mock_config_manager):
    """User-initiated stops should not be treated as recoverable crashes."""
    QCoreApplication.instance() or QCoreApplication([])
    viewer = FakeRetryTwitchViewer(mock_config_manager, [])
    worker = StreamWorker(viewer, "ninja", "best")
    viewer.processes.append(FakeProcess(1, on_wait=lambda: setattr(worker, "should_stop", True)))
    started, finished, errors, reconnecting = _collect_worker_signals(worker)
    monkeypatch.setattr(worker, "_wait_before_retry", lambda delay: True)

    worker.run()

    assert viewer.watch_calls == 1
    assert len(started) == 1
    assert finished == []
    assert errors == []
    assert reconnecting == []


def test_stream_worker_does_not_retry_after_normal_exit(monkeypatch, mock_config_manager):
    """A normal player exit finishes the stream lifecycle without reconnect."""
    QCoreApplication.instance() or QCoreApplication([])
    viewer = FakeRetryTwitchViewer(mock_config_manager, [FakeProcess(0)])
    worker = StreamWorker(viewer, "ninja", "best")
    started, finished, errors, reconnecting = _collect_worker_signals(worker)
    monkeypatch.setattr(worker, "_wait_before_retry", lambda delay: True)

    worker.run()

    assert viewer.watch_calls == 1
    assert len(started) == 1
    assert len(finished) == 1
    assert errors == []
    assert reconnecting == []


def test_stream_worker_retries_zero_exit_when_stream_pipe_ended(monkeypatch, mock_config_manager):
    """VLC can exit 0 after Streamlink stops producing input; that should reconnect."""
    QCoreApplication.instance() or QCoreApplication([])
    mock_config_manager.set("connection_retry_attempts", 3)
    mock_config_manager.set("retry_delay", 5)
    viewer = FakeRetryTwitchViewer(
        mock_config_manager,
        [
            FakeProcess(0, end_reason="stream_ended", ended_from_stream=True),
            FakeProcess(0),
        ],
    )
    worker = StreamWorker(viewer, "ninja", "best")
    started, finished, errors, reconnecting = _collect_worker_signals(worker)
    monkeypatch.setattr(worker, "_wait_before_retry", lambda delay: True)

    worker.run()

    assert viewer.watch_calls == 2
    assert len(started) == 2
    assert len(finished) == 1
    assert errors == []
    assert reconnecting == [
        "Stream ended unexpectedly (stream input ended); reconnecting in 5s (attempt 1/3)"
    ]


def test_start_stream_forwards_reconnecting_signal(monkeypatch, mock_config_manager):
    """Controller exposes worker reconnect progress with the active channel."""
    QCoreApplication.instance() or QCoreApplication([])
    monkeypatch.setattr(stream_controller, "TwitchViewer", DummyTwitchViewer)
    monkeypatch.setattr(stream_controller, "StreamWorker", FakeStreamWorker)
    monkeypatch.setattr(stream_controller, "QThread", FakeThread)

    controller = StreamController(mock_config_manager)
    reconnecting = []
    controller.stream_reconnecting.connect(
        lambda channel, message: reconnecting.append((channel, message))
    )

    controller.start_stream("ninja", "720p")
    controller.current_worker.reconnecting.emit("Stream crashed; reconnecting in 5s (attempt 1/3)")

    assert reconnecting == [("ninja", "Stream crashed; reconnecting in 5s (attempt 1/3)")]
