"""
Main GUI orchestrator for TwitchAdAvoider Qt application.

This module coordinates all GUI components, controllers, and business
logic for the Twitch stream viewer application using PySide6.

The StreamGUI class handles:
    - Component initialization and layout
    - Signal/slot connections
    - Business logic coordination
    - Application lifecycle management

Key Features:
    - Clean component-based architecture
    - Signal-driven communication
    - Proper resource cleanup
    - Theme management
"""

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt, QTimer
from typing import Optional
import sys

from gui_qt.main_window import MainWindow
from gui_qt.components.stream_control_panel import StreamControlPanel
from gui_qt.components.favorites_panel import FavoritesPanel
from gui_qt.components.chat_panel import ChatPanel
from gui_qt.components.settings_tab import SettingsTab
from gui_qt.components.status_display import StatusDisplay

from gui_qt.controllers.validation_controller import ValidationController
from gui_qt.controllers.stream_controller import StreamController
from gui_qt.controllers.chat_controller import ChatController

from src.favorites_manager import FavoritesManager
from src.config_manager import ConfigManager
from src.logging_config import get_logger

logger = get_logger(__name__)


class StreamGUI:
    """
    Main GUI application orchestrator.

    This class coordinates all components and controllers, managing
    the complete lifecycle of the TwitchAdAvoider application.
    """

    def __init__(self, config: ConfigManager):
        """
        Initialize the StreamGUI application.

        Args:
            config: Configuration manager instance
        """
        self.config = config

        # Create main window
        self.window = MainWindow(config)

        # Initialize components
        self._create_components()

        # Initialize controllers
        self._create_controllers()

        # Initialize favorites manager
        self.favorites_manager = FavoritesManager()

        # Setup component layout
        self._setup_layout()

        # Connect all signals
        self._connect_signals()

        # Load initial data
        self._load_initial_data()

        # Register cleanup callback
        self.window.register_on_closing_callback(self._cleanup)

        logger.info("StreamGUI initialized successfully")

    def _create_components(self) -> None:
        """Create all GUI components."""
        logger.debug("Creating GUI components")

        # Stream control panel (top)
        self.stream_panel = StreamControlPanel()

        # Favorites panel (left)
        self.favorites_panel = FavoritesPanel()

        # Chat panel (right)
        self.chat_panel = ChatPanel()

        # Settings tab (separate tab)
        self.settings_tab = SettingsTab(self.config)

        # Status display (bottom)
        self.status_display = StatusDisplay()

    def _create_controllers(self) -> None:
        """Create all controllers."""
        logger.debug("Creating controllers")

        # Validation controller
        self.validation_controller = ValidationController()

        # Stream controller
        self.stream_controller = StreamController(self.config)

        # Chat controller
        self.chat_controller = ChatController(self.config)

    def _setup_layout(self) -> None:
        """Setup component layout in main window."""
        logger.debug("Setting up component layout")

        # Stream tab grid layout:
        # Row 0: Stream controls (span both columns)
        # Row 1, Col 0: Favorites panel
        # Row 1, Col 1: Chat panel
        # Row 2: Status display (span both columns)

        self.window.add_component_to_layout(
            self.stream_panel,
            row=0, column=0, row_span=1, column_span=2
        )

        self.window.add_component_to_layout(
            self.favorites_panel,
            row=1, column=0, row_span=1, column_span=1
        )

        self.window.add_component_to_layout(
            self.chat_panel,
            row=1, column=1, row_span=1, column_span=1
        )

        self.window.add_component_to_layout(
            self.status_display,
            row=2, column=0, row_span=1, column_span=2
        )

        # Add settings as a separate tab
        self.window.add_settings_tab(self.settings_tab)

    def _connect_signals(self) -> None:
        """Connect all component and controller signals."""
        logger.debug("Connecting signals")

        # Stream Control Panel
        self.stream_panel.channel_changed.connect(self._on_channel_changed)
        self.stream_panel.watch_stream_requested.connect(self._on_watch_stream)

        # Validation Controller
        self.validation_controller.validation_changed.connect(self._on_validation_changed)
        self.validation_controller.watch_button_state_changed.connect(
            self.stream_panel.set_watch_button_enabled
        )

        # Stream Controller
        self.stream_controller.stream_started.connect(self._on_stream_started)
        self.stream_controller.stream_finished.connect(self._on_stream_finished)
        self.stream_controller.stream_error.connect(self._on_stream_error)

        # Favorites Panel
        self.favorites_panel.favorite_double_clicked.connect(self._on_favorite_double_clicked)
        self.favorites_panel.add_current_requested.connect(self._on_add_current_favorite)
        self.favorites_panel.add_new_requested.connect(self._on_add_new_favorite)
        self.favorites_panel.remove_requested.connect(self._on_remove_favorite)
        self.favorites_panel.refresh_requested.connect(self._on_refresh_favorites)

        # Chat Panel
        self.chat_panel.login_requested.connect(self._on_chat_login)
        self.chat_panel.logout_requested.connect(self._on_chat_logout)
        self.chat_panel.send_message_requested.connect(self._on_send_chat_message)

        # Chat Controller
        self.chat_controller.chat_connected.connect(self._on_chat_connected)
        self.chat_controller.chat_disconnected.connect(self._on_chat_disconnected)
        self.chat_controller.message_received.connect(self._on_chat_message_received)
        self.chat_controller.system_message.connect(self._on_chat_system_message)
        self.chat_controller.auth_success.connect(self._on_auth_success)
        self.chat_controller.auth_failure.connect(self._on_auth_failure)

        # Settings Tab
        self.settings_tab.settings_changed.connect(self._on_settings_changed)
        self.settings_tab.dark_mode_changed.connect(self._on_dark_mode_changed)

    def _load_initial_data(self) -> None:
        """Load initial configuration and data."""
        logger.debug("Loading initial data")

        # Load quality setting
        quality = self.config.get("quality", "best")
        self.stream_panel.set_quality(quality)

        # Load dark mode setting and apply theme
        dark_mode = self.config.get("dark_mode", False)
        self._apply_theme(dark_mode)

        # Settings tab loads its own settings from config in its __init__

        # Load favorites
        self._load_favorites()

        # Check if authenticated
        if self.chat_controller.is_authenticated():
            username = self.chat_controller.get_username()
            self.chat_panel.set_logged_in(True)
            self.status_display.add_system(f"Logged in as {username}")

        # Set focus to channel input
        self.stream_panel.focus_channel_input()

    def _load_favorites(self) -> None:
        """Load favorites from file."""
        try:
            favorites_info = self.favorites_manager.get_favorites_with_status()
            for fav_info in favorites_info:
                self.favorites_panel.add_favorite(fav_info.channel_name, fav_info.is_live)

            count = len(favorites_info)
            logger.info(f"Loaded {count} favorites")
            if count > 0:
                self.status_display.add_info(f"Loaded {count} favorites")
        except Exception as e:
            logger.error(f"Error loading favorites: {e}")
            self.status_display.add_error(f"Failed to load favorites: {e}")

    def _save_favorites(self) -> None:
        """Update favorites status (FavoritesManager auto-saves)."""
        try:
            # FavoritesManager auto-saves when add_favorite() or remove_favorite() is called
            # This method is kept for compatibility but doesn't need to manually save
            logger.debug("Favorites auto-saved by manager")
        except Exception as e:
            logger.error(f"Error updating favorites: {e}")

    # Channel Validation Handlers

    def _on_channel_changed(self, channel: str) -> None:
        """
        Handle channel input change.

        Args:
            channel: Current channel input
        """
        self.validation_controller.validate_channel(channel)

    def _on_validation_changed(self, is_valid: bool, message: str) -> None:
        """
        Handle validation state change.

        Args:
            is_valid: Whether input is valid
            message: Validation message
        """
        self.stream_panel.set_validation_message(message, is_valid)

    # Stream Handlers

    def _on_watch_stream(self, channel: str, quality: str) -> None:
        """
        Handle watch stream request.

        Args:
            channel: Channel to watch
            quality: Quality to request
        """
        logger.info(f"Watch stream requested: {channel} @ {quality}")

        # Update status
        self.status_display.add_info(f"Starting stream: {channel} @ {quality}", "STREAM")

        # Start stream
        self.stream_controller.start_stream(channel, quality)

        # Auto-connect to chat if enabled
        if self.chat_controller.auto_connect and self.chat_controller.is_authenticated():
            self._connect_to_chat(channel)

    def _on_stream_started(self, channel: str) -> None:
        """
        Handle stream started event.

        Args:
            channel: Channel that started
        """
        logger.info(f"Stream started: {channel}")
        self.status_display.add_system(f"Stream started: {channel}", "STREAM")

        # Update window with stream process reference
        process = self.stream_controller.get_current_process()
        self.window.set_stream_process(process)

    def _on_stream_finished(self, channel: str) -> None:
        """
        Handle stream finished event.

        Args:
            channel: Channel that finished
        """
        logger.info(f"Stream finished: {channel}")
        self.status_display.add_info(f"Stream finished: {channel}", "STREAM")
        self.window.set_stream_process(None)

    def _on_stream_error(self, channel: str, error: str) -> None:
        """
        Handle stream error event.

        Args:
            channel: Channel with error
            error: Error message
        """
        logger.error(f"Stream error for {channel}: {error}")
        self.status_display.add_error(f"Stream error: {error}", "STREAM")
        self.window.set_stream_process(None)

    # Favorites Handlers

    def _on_favorite_double_clicked(self, channel: str) -> None:
        """
        Handle favorite double-click (watch stream).

        Args:
            channel: Favorite channel
        """
        logger.info(f"Favorite double-clicked: {channel}")
        self.stream_panel.set_channel(channel)
        quality = self.stream_panel.get_quality()
        self._on_watch_stream(channel, quality)

    def _on_add_current_favorite(self) -> None:
        """Handle add current channel to favorites."""
        channel = self.stream_panel.get_channel()
        if channel and self.validation_controller.get_is_valid():
            self.favorites_panel.add_favorite(channel, False)
            self._save_favorites()
            self.status_display.add_info(f"Added to favorites: {channel}", "FAVORITES")
            logger.info(f"Added favorite: {channel}")
        else:
            self.status_display.add_warning("Enter a valid channel name first", "FAVORITES")

    def _on_add_new_favorite(self) -> None:
        """Handle add new favorite (with dialog)."""
        from PySide6.QtWidgets import QInputDialog

        channel, ok = QInputDialog.getText(
            self.window,
            "Add Favorite",
            "Enter channel name:"
        )

        if ok and channel.strip():
            try:
                from src.validators import validate_channel_name
                validate_channel_name(channel.strip())
                self.favorites_panel.add_favorite(channel.strip(), False)
                self._save_favorites()
                self.status_display.add_info(f"Added to favorites: {channel}", "FAVORITES")
                logger.info(f"Added favorite: {channel}")
            except ValueError as e:
                self.status_display.add_error(f"Invalid channel name: {e}", "FAVORITES")

    def _on_remove_favorite(self, channel: str) -> None:
        """
        Handle remove favorite.

        Args:
            channel: Channel to remove
        """
        self.favorites_panel.remove_favorite(channel)
        self._save_favorites()
        self.status_display.add_info(f"Removed from favorites: {channel}", "FAVORITES")
        logger.info(f"Removed favorite: {channel}")

    def _on_refresh_favorites(self) -> None:
        """Handle refresh favorites status."""
        # TODO: Implement async status checking
        self.status_display.add_info("Refresh favorites feature coming soon", "FAVORITES")
        logger.info("Refresh favorites requested")

    # Chat Handlers

    def _connect_to_chat(self, channel: str) -> None:
        """
        Connect to chat for a channel.

        Args:
            channel: Channel to connect to
        """
        if self.chat_controller.connect_to_channel(channel):
            self.status_display.add_info(f"Connecting to chat: #{channel}", "CHAT")
        else:
            self.status_display.add_error(f"Failed to connect to chat", "CHAT")

    def _on_chat_login(self) -> None:
        """Handle chat login request."""
        logger.info("Chat login requested")
        self.status_display.add_system("Starting authentication...", "CHAT")
        self.chat_controller.start_authentication()

    def _on_chat_logout(self) -> None:
        """Handle chat logout request."""
        logger.info("Chat logout requested")
        self.chat_controller.logout()
        self.chat_panel.set_logged_in(False)
        self.chat_panel.set_connected(False)
        self.status_display.add_system("Logged out", "CHAT")

    def _on_send_chat_message(self, message: str) -> None:
        """
        Handle send chat message request.

        Args:
            message: Message to send
        """
        self.chat_controller.send_message(message)

    def _on_chat_connected(self, channel: str) -> None:
        """
        Handle chat connected event.

        Args:
            channel: Connected channel
        """
        self.chat_panel.set_connected(True)
        self.chat_panel.add_system_message(f"Connected to #{channel}")
        self.status_display.add_system(f"Chat connected: #{channel}", "CHAT")
        logger.info(f"Chat connected to #{channel}")

    def _on_chat_disconnected(self) -> None:
        """Handle chat disconnected event."""
        self.chat_panel.set_connected(False)
        self.chat_panel.add_system_message("Disconnected from chat")
        self.status_display.add_info("Chat disconnected", "CHAT")
        logger.info("Chat disconnected")

    def _on_chat_message_received(self, username: str, message: str, timestamp) -> None:
        """
        Handle received chat message.

        Args:
            username: Message sender
            message: Message text
            timestamp: Message timestamp
        """
        self.chat_panel.add_message(username, message, timestamp)

    def _on_chat_system_message(self, message: str) -> None:
        """
        Handle system message from chat.

        Args:
            message: System message
        """
        self.chat_panel.add_system_message(message)

    def _on_auth_success(self, username: str) -> None:
        """
        Handle authentication success.

        Args:
            username: Authenticated username
        """
        self.chat_panel.set_logged_in(True)
        self.status_display.add_system(f"Logged in as {username}", "CHAT")
        logger.info(f"Authentication successful: {username}")

    def _on_auth_failure(self, error: str) -> None:
        """
        Handle authentication failure.

        Args:
            error: Error message
        """
        self.status_display.add_error(f"Authentication failed: {error}", "CHAT")
        logger.error(f"Authentication failed: {error}")

    # Settings Handlers

    def _on_settings_changed(self) -> None:
        """Handle settings changed event from settings tab."""
        self.status_display.add_info("Settings saved successfully", "SETTINGS")
        logger.info("Settings updated from settings tab")

    def _on_dark_mode_changed(self, enabled: bool) -> None:
        """
        Handle dark mode toggle (from settings tab).

        Note: This provides immediate visual feedback without saving.
        Settings are saved when user clicks "Apply Settings" button.

        Args:
            enabled: Whether dark mode is enabled
        """
        self._apply_theme(enabled)
        theme_name = "dark" if enabled else "light"
        logger.info(f"Dark mode preview: {enabled}")

    def _apply_theme(self, dark_mode: bool) -> None:
        """
        Apply theme to all components.

        Args:
            dark_mode: Whether to use dark theme
        """
        # Apply to window (loads and applies stylesheet)
        self.window.switch_theme(dark_mode)

        # Update component-specific theme settings
        self.favorites_panel.set_dark_mode(dark_mode)
        self.status_display.set_dark_mode(dark_mode)

    # Lifecycle

    def _cleanup(self) -> None:
        """Cleanup resources before shutdown."""
        logger.info("Performing application cleanup")

        # Stop stream
        if self.stream_controller.is_streaming():
            self.stream_controller.stop_stream()

        # Disconnect chat
        if self.chat_controller.is_connected():
            self.chat_controller.disconnect()

        # Save favorites
        self._save_favorites()

        logger.info("Cleanup complete")

    def show(self) -> None:
        """Show the main window."""
        self.window.show()
        logger.info("Main window shown")

    def run(self) -> int:
        """
        Run the application event loop.

        Returns:
            Application exit code
        """
        self.show()
        return QApplication.instance().exec()


def main() -> int:
    """
    Main entry point for Qt GUI application.

    Returns:
        Application exit code
    """
    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("TwitchAdAvoider")
    app.setOrganizationName("TwitchAdAvoider")

    # Load configuration
    config = ConfigManager()

    # Create and show GUI
    gui = StreamGUI(config)

    # Run application
    return gui.run()


if __name__ == "__main__":
    sys.exit(main())
