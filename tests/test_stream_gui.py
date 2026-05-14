"""Tests for StreamGUI handler-level validation."""

from PySide6.QtWidgets import QInputDialog

from gui_qt.stream_gui import StreamGUI


class RecordingFavoritesPanel:
    def __init__(self):
        self.added = []

    def add_favorite(self, channel, is_live):
        self.added.append((channel, is_live))


class RecordingFavoritesManager:
    def __init__(self):
        self.added = []

    def add_favorite(self, channel):
        self.added.append(channel)
        return True


class RecordingStatusDisplay:
    def __init__(self):
        self.info = []
        self.errors = []

    def add_info(self, message, category=None):
        self.info.append((message, category))

    def add_error(self, message, category=None):
        self.errors.append((message, category))


def test_add_new_favorite_uses_normalized_channel(monkeypatch):
    """Add Favorite stores the validator's normalized channel name."""
    gui = StreamGUI.__new__(StreamGUI)
    gui.window = None
    gui.favorites_panel = RecordingFavoritesPanel()
    gui.favorites_manager = RecordingFavoritesManager()
    gui.status_display = RecordingStatusDisplay()

    monkeypatch.setattr(QInputDialog, "getText", lambda *args: ("  NINJA  ", True))

    gui._on_add_new_favorite()

    assert gui.favorites_panel.added == [("ninja", False)]
    assert gui.favorites_manager.added == ["ninja"]
    assert gui.status_display.errors == []


def test_add_new_favorite_catches_validation_error(monkeypatch):
    """Invalid Add Favorite input is shown as a GUI error instead of escaping."""
    gui = StreamGUI.__new__(StreamGUI)
    gui.window = None
    gui.favorites_panel = RecordingFavoritesPanel()
    gui.favorites_manager = RecordingFavoritesManager()
    gui.status_display = RecordingStatusDisplay()

    monkeypatch.setattr(QInputDialog, "getText", lambda *args: ("bad;channel", True))

    gui._on_add_new_favorite()

    assert gui.favorites_panel.added == []
    assert gui.favorites_manager.added == []
    assert gui.status_display.errors
