"""Tests for StreamGUI handler-level validation."""

from PySide6.QtWidgets import QInputDialog

from gui_qt.stream_gui import StreamGUI
from src.favorites_manager import FavoriteChannelInfo


class RecordingFavoritesPanel:
    def __init__(self):
        self.added = []

    def add_favorite(self, channel, is_live, is_pinned=False):
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


class RefreshFavoritesPanel:
    def __init__(self, statuses):
        self.statuses = statuses.copy()
        self.recently_live_marked = []

    def get_favorites(self):
        return list(self.statuses)

    def update_favorite_status(self, channel, is_live):
        self.statuses[channel] = is_live

    def mark_recently_live(self, channels):
        if channels:
            self.recently_live_marked.append(list(channels))


class RefreshFavoritesManager:
    def __init__(self, statuses):
        self.statuses = statuses.copy()
        self.updated = []

    def get_channel_info(self, channel):
        if channel not in self.statuses:
            return None
        return FavoriteChannelInfo(channel_name=channel, is_live=self.statuses[channel])

    def update_channel_status(self, channel, is_live):
        self.statuses[channel] = is_live
        self.updated.append((channel, is_live))


class RefreshStatusMonitor:
    def __init__(self, results):
        self.results = results

    def check_channels(self, favorites):
        return self.results.copy()


class RecordingToast:
    def __init__(self):
        self.shown = []

    def show_live_channels(self, channels):
        self.shown.append(list(channels))


class RecordingSoundManager:
    def __init__(self):
        self.live_notifications = 0

    def play_live_notification(self):
        self.live_notifications += 1


class RecordingConfig:
    def __init__(self, values=None):
        self.values = values or {}

    def get(self, key, default=None):
        return self.values.get(key, default)


def make_refresh_gui(previous_statuses, refreshed_statuses, config_values=None):
    gui = StreamGUI.__new__(StreamGUI)
    gui.favorites_panel = RefreshFavoritesPanel(previous_statuses)
    gui.favorites_manager = RefreshFavoritesManager(previous_statuses)
    gui.status_monitor = RefreshStatusMonitor(refreshed_statuses)
    gui.status_display = RecordingStatusDisplay()
    gui.live_notification_toast = RecordingToast()
    gui.sound_manager = RecordingSoundManager()
    gui.config = RecordingConfig(config_values)
    return gui


def test_refresh_notifies_when_favorite_changes_from_offline_to_live():
    """Offline -> live triggers one toast and one live sound."""
    gui = make_refresh_gui({"ninja": False}, {"ninja": True})

    gui._on_refresh_favorites()

    assert gui.favorites_panel.recently_live_marked == [["ninja"]]
    assert gui.live_notification_toast.shown == [["ninja"]]
    assert gui.sound_manager.live_notifications == 1
    assert ("ninja is live", "FAVORITES") in gui.status_display.info
    assert gui.favorites_manager.updated == [("ninja", True)]


def test_refresh_does_not_renotify_favorite_that_was_already_live():
    """Live -> live refreshes status without repeating the notification."""
    gui = make_refresh_gui({"ninja": True}, {"ninja": True})

    gui._on_refresh_favorites()

    assert gui.favorites_panel.recently_live_marked == []
    assert gui.live_notification_toast.shown == []
    assert gui.sound_manager.live_notifications == 0
    assert gui.favorites_manager.updated == [("ninja", True)]


def test_refresh_test_mode_rehighlights_currently_live_channels_without_renotifying():
    """Testing mode retriggers the visual highlight for live channels on every refresh."""
    gui = make_refresh_gui(
        {"ninja": True, "shroud": False},
        {"ninja": True, "shroud": True},
        {"favorite_live_highlight_test_mode": True},
    )

    gui._on_refresh_favorites()

    assert gui.favorites_panel.recently_live_marked == [["ninja", "shroud"]]
    assert gui.live_notification_toast.shown == [["shroud"]]
    assert gui.sound_manager.live_notifications == 1
    assert gui.favorites_manager.updated == [("ninja", True), ("shroud", True)]


def test_refresh_does_not_notify_when_favorite_goes_offline():
    """Live -> offline refreshes status without notifying."""
    gui = make_refresh_gui({"ninja": True}, {"ninja": False})

    gui._on_refresh_favorites()

    assert gui.favorites_panel.recently_live_marked == []
    assert gui.live_notification_toast.shown == []
    assert gui.sound_manager.live_notifications == 0
    assert gui.favorites_manager.updated == [("ninja", False)]


def test_refresh_respects_disabled_live_notifications():
    """Disabled live notifications suppress both toast and sound."""
    gui = make_refresh_gui(
        {"ninja": False},
        {"ninja": True},
        {"favorite_live_notifications_enabled": False},
    )

    gui._on_refresh_favorites()

    assert gui.favorites_panel.recently_live_marked == [["ninja"]]
    assert gui.live_notification_toast.shown == []
    assert gui.sound_manager.live_notifications == 0
    assert ("ninja is live", "FAVORITES") not in gui.status_display.info
    assert gui.favorites_manager.updated == [("ninja", True)]


def test_refresh_marks_multiple_newly_live_favorites_together():
    """Multiple offline -> live transitions are highlighted in one refresh."""
    gui = make_refresh_gui(
        {"ninja": False, "shroud": False, "pokimane": True},
        {"ninja": True, "shroud": True, "pokimane": True},
    )

    gui._on_refresh_favorites()

    assert gui.favorites_panel.recently_live_marked == [["ninja", "shroud"]]
    assert gui.live_notification_toast.shown == [["ninja", "shroud"]]
    assert gui.sound_manager.live_notifications == 1
