"""Main GUI orchestrator for TwitchAdAvoider Qt application."""

import webbrowser

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QTimer

from gui_qt.main_window import MainWindow
from gui_qt.components.favorites_panel import FavoritesPanel
from gui_qt.components.chat_panel import ChatPanel
from gui_qt.components.settings_tab import SettingsTab
from gui_qt.components.status_display import StatusDisplay
from gui_qt.components.stream_actions import StreamActions

from gui_qt.controllers.stream_controller import StreamController

from src.favorites_manager import FavoritesManager
from src.config_manager import ConfigManager
from src.exceptions import ValidationError
from src.status_monitor import StatusMonitor
from src.logging_config import get_logger

logger = get_logger(__name__)


class StreamGUI:
    """Main GUI application orchestrator."""

    def __init__(self, config: ConfigManager):
        self.config = config

        self.window = MainWindow(config)

        self._create_components()
        self._create_controllers()

        self.favorites_manager = FavoritesManager()

        self._setup_layout()
        self._connect_signals()
        self._load_initial_data()

        timeout = self.config.get("favorites_check_timeout", 5)
        self.status_monitor = StatusMonitor(check_timeout=timeout, max_workers=3)

        self._setup_refresh_timer()

        self.window.register_on_closing_callback(self._cleanup)

        logger.info("StreamGUI initialized successfully")

    def _create_components(self) -> None:
        """Create all GUI components."""
        self.favorites_panel = FavoritesPanel()
        self.chat_panel = ChatPanel()
        self.settings_tab = SettingsTab(self.config)
        self.status_display = StatusDisplay()
        self.stream_actions = StreamActions()

    def _create_controllers(self) -> None:
        """Create all controllers."""
        self.stream_controller = StreamController(self.config)

    def _setup_layout(self) -> None:
        """Setup component layout in main window."""
        self.window.add_component_to_layout(
            self.stream_actions, row=0, column=0, row_span=1, column_span=2
        )
        self.window.add_component_to_layout(
            self.favorites_panel, row=1, column=0, row_span=1, column_span=1
        )
        self.window.add_component_to_layout(
            self.chat_panel, row=1, column=1, row_span=1, column_span=1
        )
        self.window.add_component_to_layout(
            self.status_display, row=2, column=0, row_span=1, column_span=2
        )
        self.window.add_settings_tab(self.settings_tab)

    def _connect_signals(self) -> None:
        """Connect all component and controller signals."""
        self.stream_controller.stream_started.connect(self._on_stream_started)
        self.stream_controller.stream_finished.connect(self._on_stream_finished)
        self.stream_controller.stream_error.connect(self._on_stream_error)
        self.stream_controller.clip_created.connect(self._on_clip_created)
        self.stream_controller.clip_failed.connect(self._on_clip_failed)

        self.stream_actions.clip_requested.connect(self.stream_controller.create_clip)

        self.favorites_panel.favorite_double_clicked.connect(self._on_favorite_double_clicked)
        self.favorites_panel.open_channel_in_browser.connect(self._on_open_channel_in_browser)
        self.favorites_panel.add_new_requested.connect(self._on_add_new_favorite)
        self.favorites_panel.remove_requested.connect(self._on_remove_favorite)
        self.favorites_panel.refresh_requested.connect(self._on_refresh_favorites)
        self.favorites_panel.pin_toggle_requested.connect(self._on_pin_toggle)
        self.favorites_panel.quality_changed.connect(self._on_quality_changed)

        self.chat_panel.open_chat_requested.connect(self._on_open_chat)

        self.settings_tab.settings_changed.connect(self._on_settings_changed)
        self.settings_tab.dark_mode_changed.connect(self._on_dark_mode_changed)

    def _load_initial_data(self) -> None:
        """Load initial configuration and data."""
        quality = self.config.get("preferred_quality", "best")
        self.favorites_panel.set_quality(quality)
        self.stream_actions.set_streaming(False, quality=quality)

        dark_mode = self.config.get("dark_mode", False)
        self._apply_theme(dark_mode)

        self._load_favorites()

    def _setup_refresh_timer(self) -> None:
        """Setup the auto-refresh timer for favorites status checking."""
        self.refresh_timer = QTimer()
        self.refresh_timer.setSingleShot(False)
        self.refresh_timer.timeout.connect(self._on_refresh_favorites)
        self._update_refresh_timer_settings()

        if self.config.get("favorites_auto_refresh", True):
            QTimer.singleShot(0, self._on_refresh_favorites)

    def _update_refresh_timer_settings(self) -> None:
        """Update refresh timer settings from configuration."""
        auto_refresh = self.config.get("favorites_auto_refresh", True)
        interval_seconds = self.config.get("favorites_refresh_interval", 300)
        check_timeout = self.config.get("favorites_check_timeout", 5)

        self.status_monitor.update_timeout(check_timeout)

        self.refresh_timer.setInterval(interval_seconds * 1000)

        if auto_refresh:
            if not self.refresh_timer.isActive():
                self.refresh_timer.start()
                logger.info(f"Auto-refresh enabled (interval: {interval_seconds}s)")
        else:
            if self.refresh_timer.isActive():
                self.refresh_timer.stop()
                logger.info("Auto-refresh disabled")

    def _load_favorites(self) -> None:
        """Load favorites from file."""
        try:
            favorites_info = self.favorites_manager.get_favorites_with_status()
            for fav_info in favorites_info:
                self.favorites_panel.add_favorite(
                    fav_info.channel_name, fav_info.is_live, fav_info.is_pinned
                )

            count = len(favorites_info)
            logger.info(f"Loaded {count} favorites")
            if count > 0:
                self.status_display.add_info(f"Loaded {count} favorites")
        except Exception as e:
            logger.error(f"Error loading favorites: {e}")
            self.status_display.add_error(f"Failed to load favorites: {e}")

    # Stream Handlers

    def _on_watch_stream(self, channel: str, quality: str) -> None:
        logger.info(f"Watch stream requested: {channel} @ {quality}")
        self.status_display.add_info(f"Starting stream: {channel} @ {quality}", "STREAM")
        self.stream_actions.set_streaming(False, channel, quality)
        self.stream_controller.start_stream(channel, quality)

    def _on_stream_started(self, channel: str) -> None:
        logger.info(f"Stream started: {channel}")
        self.status_display.add_system(f"Stream started: {channel}", "STREAM")
        self.status_display.set_streaming(True)
        self.stream_actions.set_streaming(True, channel, self.favorites_panel.get_quality())
        self.chat_panel.set_channel(channel)
        process = self.stream_controller.get_current_process()
        self.window.set_stream_process(process)

    def _on_stream_finished(self, channel: str) -> None:
        logger.info(f"Stream finished: {channel}")
        self.status_display.add_info(f"Stream finished: {channel}", "STREAM")
        self.status_display.set_streaming(False)
        self.stream_actions.set_streaming(False, quality=self.favorites_panel.get_quality())
        self.chat_panel.set_channel("")
        self.stream_controller.twitch_viewer.cleanup_recording()
        self.window.set_stream_process(None)

    def _on_stream_error(self, channel: str, error: str) -> None:
        logger.error(f"Stream error for {channel}: {error}")

        if "No video player found" in error:
            msg = QMessageBox(self.window)
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setWindowTitle("No Video Player Found")
            msg.setText(
                "A video player (VLC or MPV) is required to watch streams.\n\n"
                "Download VLC, install it, then try again."
            )
            download_btn = msg.addButton("Download VLC", QMessageBox.ButtonRole.ActionRole)
            msg.addButton("Close", QMessageBox.ButtonRole.RejectRole)
            msg.exec()
            if msg.clickedButton() == download_btn:
                webbrowser.open("https://www.videolan.org/vlc/")

        self.status_display.add_error(f"Stream error: {error}", "STREAM")
        self.status_display.set_streaming(False)
        self.stream_actions.set_streaming(False, quality=self.favorites_panel.get_quality())
        self.chat_panel.set_channel("")
        self.stream_controller.twitch_viewer.cleanup_recording()
        self.window.set_stream_process(None)

    def _on_clip_created(self, path: str) -> None:
        self.status_display.add_system(f"Clip saved: {path}", "CLIP")

    def _on_clip_failed(self, error: str) -> None:
        self.status_display.add_error(f"Clip failed: {error}", "CLIP")

    # Favorites Handlers

    def _on_favorite_double_clicked(self, channel: str) -> None:
        quality = self.favorites_panel.get_quality()
        logger.info(f"Favorite double-clicked: {channel} @ {quality}")
        self._on_watch_stream(channel, quality)

    def _on_open_channel_in_browser(self, channel: str) -> None:
        url = f"https://www.twitch.tv/{channel}"
        webbrowser.open(url)
        logger.info(f"Opened Twitch channel in browser: {channel}")

    def _on_add_new_favorite(self) -> None:
        from PySide6.QtWidgets import QInputDialog

        channel, ok = QInputDialog.getText(self.window, "Add Favorite", "Enter channel name:")

        if ok and channel.strip():
            try:
                from src.validators import validate_channel_name

                normalized_channel = validate_channel_name(channel)
                self.favorites_panel.add_favorite(normalized_channel, False)
                self.favorites_manager.add_favorite(normalized_channel)
                self.status_display.add_info(
                    f"Added to favorites: {normalized_channel}", "FAVORITES"
                )
                logger.info(f"Added favorite: {normalized_channel}")
            except ValidationError as e:
                self.status_display.add_error(f"Invalid channel name: {e}", "FAVORITES")

    def _on_remove_favorite(self, channel: str) -> None:
        self.favorites_panel.remove_favorite(channel)
        self.favorites_manager.remove_favorite(channel)
        self.status_display.add_info(f"Removed from favorites: {channel}", "FAVORITES")
        logger.info(f"Removed favorite: {channel}")

    def _on_refresh_favorites(self) -> None:
        """Perform lightweight live-status checks for all favourite channels."""
        favorites = self.favorites_panel.get_favorites()

        if not favorites:
            self.status_display.add_info("Refresh skipped: no favorites saved", "FAVORITES")
            return

        logger.info(f"Refreshing status for {len(favorites)} favorite channels")
        self.status_display.add_info(
            f"Refreshing {len(favorites)} favorite channel statuses", "FAVORITES"
        )

        try:
            status_results = self.status_monitor.check_channels(favorites)

            for channel, is_live in status_results.items():
                self.favorites_panel.update_favorite_status(channel, is_live)
                self.favorites_manager.update_channel_status(channel, is_live)

            live_count = sum(status_results.values())
            logger.info(f"Status refresh complete: {live_count}/{len(favorites)} channels live")
            live_channels = sorted(
                channel for channel, is_live in status_results.items() if is_live
            )
            if live_channels:
                live_summary = ", ".join(live_channels[:5])
                if len(live_channels) > 5:
                    live_summary += f", +{len(live_channels) - 5} more"
                message = f"Refresh complete: {live_count}/{len(favorites)} live ({live_summary})"
            else:
                message = f"Refresh complete: 0/{len(favorites)} channels live"
            self.status_display.add_info(message, "FAVORITES")

        except Exception as e:
            logger.error(f"Error during favorites refresh: {e}")
            self.status_display.add_error(f"Failed to refresh favorites: {e}", "FAVORITES")

    def _on_pin_toggle(self, channel: str) -> None:
        new_state = self.favorites_manager.toggle_pin(channel)
        self.favorites_panel.update_pin_status(channel, new_state)
        action = "Pinned" if new_state else "Unpinned"
        logger.info(f"{action}: {channel}")

    def _on_quality_changed(self, quality: str) -> None:
        if not self.config.set("preferred_quality", quality):
            self.status_display.add_error(f"Invalid quality: {quality}", "SETTINGS")
            logger.warning(f"Rejected invalid quality change: {quality}")
            return
        if not self.stream_controller.is_streaming():
            self.stream_actions.set_streaming(False, quality=quality)
        logger.debug(f"Quality changed to: {quality}")

    # Chat Handler

    def _on_open_chat(self) -> None:
        """Open Twitch popout chat in the default browser."""
        channel = self.chat_panel.channel
        if channel:
            url = f"https://www.twitch.tv/popout/{channel}/chat?popout="
            webbrowser.open(url)
            logger.info(f"Opened Twitch chat in browser: {channel}")

    # Settings Handlers

    def _on_settings_changed(self) -> None:
        from src.logging_config import reconfigure_logging_from_config

        reconfigure_logging_from_config(self.config)
        quality = self.config.get("preferred_quality", "best")
        self.favorites_panel.set_quality(quality)
        if not self.stream_controller.is_streaming():
            self.stream_actions.set_streaming(False, quality=quality)
        self._update_refresh_timer_settings()
        self.status_display.add_info("Settings saved successfully", "SETTINGS")
        logger.info("Settings updated from settings tab")

    def _on_dark_mode_changed(self, enabled: bool) -> None:
        self._apply_theme(enabled)
        logger.info(f"Dark mode preview: {enabled}")

    def _apply_theme(self, dark_mode: bool) -> None:
        self.window.switch_theme(dark_mode)
        self.favorites_panel.set_dark_mode(dark_mode)
        self.status_display.set_dark_mode(dark_mode)

    # Lifecycle

    def _cleanup(self) -> None:
        """Cleanup resources before shutdown."""
        logger.info("Performing application cleanup")

        if hasattr(self, "refresh_timer") and self.refresh_timer.isActive():
            self.refresh_timer.stop()

        if self.stream_controller.is_streaming():
            self.stream_controller.stop_stream()
        self.stream_controller.twitch_viewer.cleanup_recording()

        logger.info("Cleanup complete")

        import logging

        log = logging.getLogger("twitch_ad_avoider")
        for handler in log.handlers:
            handler.flush()
            handler.close()

    def show(self) -> None:
        self.window.show()
        logger.info("Main window shown")

    def run(self) -> int:
        self.show()
        return QApplication.instance().exec()
