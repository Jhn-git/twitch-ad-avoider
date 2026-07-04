"""Regression tests for StreamGUI preview-state behavior."""

import logging
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QApplication

from gui_qt import stream_gui as stream_gui_module
from gui_qt.stream_gui import StreamGUI
from src.config_manager import ConfigManager
from src.stream_preview import StreamPreviewInfo


class DummyPreviewController(QObject):
    """Preview controller stand-in that records UI requests."""

    preview_ready = Signal(str, object)
    image_ready = Signal(str, bytes)
    image_failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.request_calls = []
        self.clear_calls = 0

    def request_preview(self, channel: str, timeout_seconds: int) -> None:
        self.request_calls.append((channel, timeout_seconds))

    def clear(self) -> None:
        self.clear_calls += 1


class DummyStreamController(QObject):
    """Minimal stream controller stand-in for StreamGUI tests."""

    stream_started = Signal(str)
    stream_finished = Signal(str)
    stream_error = Signal(str, str)
    stream_reconnecting = Signal(str, str)
    clip_created = Signal(str)
    clip_failed = Signal(str)

    def __init__(self, config: ConfigManager):
        super().__init__()
        self.config = config
        self._is_streaming = False
        self.stop_calls = 0
        self.twitch_viewer = SimpleNamespace(cleanup_recording=lambda: None)

    def create_clip(self, duration_seconds: int) -> None:
        return None

    def start_stream(self, channel: str, quality: str) -> None:
        self._is_streaming = True

    def stop_stream(self) -> bool:
        self.stop_calls += 1
        self._is_streaming = False
        return True

    def is_streaming(self) -> bool:
        return self._is_streaming

    def get_current_process(self):
        return None


class DummyStatusMonitor:
    """Status-monitor stand-in that records refresh attempts."""

    def __init__(self, check_timeout: int = 10):
        self.check_timeout = check_timeout
        self.check_calls = 0

    def update_timeout(self, timeout: int) -> None:
        self.check_timeout = timeout

    def check_channels(self, channels):
        self.check_calls += 1
        return {channel: False for channel in channels}


class DummyFavoritesManager:
    """Favorites manager stand-in that keeps StreamGUI off disk."""

    def get_favorites_with_status(self):
        return []

    def get_channel_info(self, channel: str):
        return None

    def update_channel_status(self, channel: str, is_live: bool) -> None:
        return None

    def toggle_pin(self, channel: str) -> bool:
        return False

    def add_favorite(self, channel: str) -> bool:
        return True

    def remove_favorite(self, channel: str) -> bool:
        return True


class DummySoundManager:
    """Sound manager stand-in that avoids multimedia setup in tests."""

    def __init__(self, config, parent):
        self.config = config
        self.parent = parent

    def install_button_hover_sounds(self, root_widget) -> None:
        return None

    def play_live_notification(self) -> None:
        return None


class DummyLiveNotificationToast:
    """Toast stand-in for refresh-notification tests."""

    def __init__(self, parent):
        self.parent = parent

    def show_live_channels(self, channels) -> None:
        return None


def _build_stream_gui(monkeypatch, tmp_path: Path) -> StreamGUI:
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(stream_gui_module, "StreamController", DummyStreamController)
    monkeypatch.setattr(stream_gui_module, "StreamPreviewController", DummyPreviewController)
    monkeypatch.setattr(stream_gui_module, "StatusMonitor", DummyStatusMonitor)
    monkeypatch.setattr(stream_gui_module, "FavoritesManager", DummyFavoritesManager)
    monkeypatch.setattr(stream_gui_module, "GuiSoundManager", DummySoundManager)
    monkeypatch.setattr(stream_gui_module, "LiveNotificationToast", DummyLiveNotificationToast)

    config = ConfigManager(tmp_path / "settings.json")
    config.set("favorites_auto_refresh", False)

    gui = StreamGUI(config)
    gui.window.show()
    app.processEvents()
    return gui


def _select_favorite(gui: StreamGUI, channel: str) -> None:
    app = QApplication.instance() or QApplication([])
    gui.favorites_panel.add_favorite(channel)
    item = gui.favorites_panel.list_widget.findItems(channel, Qt.MatchExactly)[0]
    gui.favorites_panel.list_widget.setCurrentItem(item)
    app.processEvents()


def test_disabling_previews_clears_visible_preview_immediately(monkeypatch, tmp_path):
    """Turning previews off should clear the current preview and cancel work."""
    app = QApplication.instance() or QApplication([])
    gui = _build_stream_gui(monkeypatch, tmp_path)
    _select_favorite(gui, "ninja")

    gui.chat_panel.set_preview_offline()
    clear_calls_before = gui.preview_controller.clear_calls

    gui.config.set("show_stream_preview", False)
    gui._on_settings_changed()
    app.processEvents()

    assert gui.chat_panel._preview_image_label.text() == ""
    assert gui.preview_controller.clear_calls > clear_calls_before


def test_late_preview_results_are_ignored_after_previews_disabled(monkeypatch, tmp_path):
    """Late results must not repaint the UI after previews are disabled."""
    gui = _build_stream_gui(monkeypatch, tmp_path)
    _select_favorite(gui, "ninja")

    gui.config.set("show_stream_preview", False)
    gui._on_settings_changed()

    gui._on_preview_ready("ninja", StreamPreviewInfo(channel="ninja", is_live=False))
    gui._on_preview_image_ready("ninja", b"not-an-image")
    gui._on_preview_image_failed("ninja")

    assert gui.chat_panel._preview_image_label.text() == ""


def test_reenabling_previews_requests_selected_channel_with_network_timeout(
    monkeypatch,
    tmp_path,
):
    """Settings reapply should request the selected preview using network_timeout."""
    gui = _build_stream_gui(monkeypatch, tmp_path)

    gui.config.set("show_stream_preview", False)
    _select_favorite(gui, "ninja")

    gui.config.set("network_timeout", 17)
    gui.config.set("show_stream_preview", True)
    gui._on_settings_changed()

    assert gui.preview_controller.request_calls[-1] == ("ninja", 17)


def test_cleanup_blocks_late_refresh_calls(monkeypatch, tmp_path):
    """Refresh work should become a no-op once cleanup starts."""
    gui = _build_stream_gui(monkeypatch, tmp_path)
    gui.favorites_panel.add_favorite("ninja")

    original_get_logger = logging.getLogger
    monkeypatch.setattr(
        logging,
        "getLogger",
        lambda name=None: (
            SimpleNamespace(handlers=[])
            if name == "twitch_ad_avoider"
            else original_get_logger(name)
        ),
    )

    gui._cleanup()
    gui._on_refresh_favorites()

    assert gui._is_closing is True
    assert gui.status_monitor.check_calls == 0
