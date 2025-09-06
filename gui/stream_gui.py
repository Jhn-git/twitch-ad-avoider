"""
Refactored Tkinter-based GUI for TwitchAdAvoider Stream Manager.

This module provides a lightweight graphical interface using the new modular architecture
with separated concerns and improved maintainability.

The refactored :class:`StreamGUI` now uses:
    - Component-based UI architecture (MainWindow, FavoritesPanel, StreamControlPanel)
    - Controller-based business logic (StreamController, ConfigController, etc.)
    - Utility classes for common functionality (SpinnerManager, DateTimeUtility)
    - Observer pattern for loose coupling between components

Key Improvements:
    - Single responsibility principle adherence
    - Easier testing and maintenance
    - Clear separation of concerns
    - Reduced code duplication
    - Improved error handling and logging
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional

# Component imports
from .components import MainWindow, FavoritesPanel, StreamControlPanel, ChatPanel
from .controllers import (
    StreamController, 
    ConfigController, 
    ValidationController, 
    ThemeController,
    ChatController
)
from .utils import SpinnerManager, create_watch_button_spinner, create_refresh_button_spinner
from .status_manager import StatusManager
from .favorites_manager import FavoritesManager
from .themes import get_theme

# Core functionality imports
from src.twitch_viewer import TwitchViewer
from src.config_manager import ConfigManager
from src.streamlink_status import StreamlinkStatusChecker
from src.logging_config import get_logger

logger = get_logger(__name__)

# GUI Configuration Constants
GUI_GEOMETRY = "640x650"
GUI_MIN_SIZE = (580, 550)


class StreamGUI:
    """
    Refactored main GUI class using modular component architecture.
    
    This version demonstrates the benefits of component-based design with
    clear separation of concerns and improved maintainability.
    """

    def __init__(self, root: tk.Tk, config_manager: Optional[ConfigManager] = None):
        """
        Initialize the refactored Stream GUI.

        Args:
            root: The main tkinter window
            config_manager: Configuration manager instance
        """
        self.root = root
        
        # Initialize core managers
        self.config = config_manager or ConfigManager()
        self.viewer = TwitchViewer(self.config)
        self.favorites_manager = FavoritesManager()
        
        # Initialize status management (StatusManager will be initialized after UI components)
        self.status_checker = StreamlinkStatusChecker(self.config, progress_callback=self._on_progress_update)
        self.status_manager = None  # Will be initialized after status widget is created
        
        # Initialize controllers (some will be updated after StatusManager is created)
        self._initialize_controllers()
        
        # Initialize main window
        self.main_window = MainWindow(root, self.config)
        
        # Initialize UI components
        self._initialize_components()
        
        # Initialize status manager after UI components are created
        self._initialize_status_manager()
        
        # Initialize utilities
        self._initialize_utilities()
        
        # Setup component communication
        self._setup_component_communication()
        
        # Apply initial theme and setup
        self._finalize_initialization()

    def _initialize_controllers(self) -> None:
        """Initialize all controller instances"""
        # Theme controller
        initial_theme = self.config.get("current_theme", "light")
        self.theme_controller = ThemeController(self.root, initial_theme)
        # StatusManager will be set later in _initialize_status_manager
        
        # Validation controller (doesn't need StatusManager)
        current_theme = get_theme(initial_theme)
        self.validation_controller = ValidationController(current_theme)
        
        # Configuration controller and Stream controller will be initialized
        # in _initialize_status_manager after StatusManager is created

    def _initialize_components(self) -> None:
        """Initialize all UI components"""
        main_frame = self.main_window.get_main_frame()
        
        # Stream control panel
        self.stream_control_panel = StreamControlPanel(
            main_frame,
            self.validation_controller,
            self.theme_controller.get_current_theme()
        )
        
        # Favorites panel (status_manager will be set later)
        self.favorites_panel = FavoritesPanel(
            main_frame,
            self.favorites_manager,
            None,  # status_manager will be set in _initialize_status_manager
            self.theme_controller.get_current_theme()
        )
        
        # Chat panel (status_manager will be set later)
        self.chat_panel = ChatPanel(
            main_frame,
            None,  # status_manager will be set in _initialize_status_manager
            self.theme_controller.get_current_theme()
        )
        
        
        # Settings section (simplified - could be extracted to component later)  
        self._create_settings_section(main_frame)
        
        # Status section
        self._create_status_section(main_frame)
        
        # Configure main layout
        self.main_window.configure_main_layout()

    def _initialize_utilities(self) -> None:
        """Initialize utility managers"""
        # Get references to buttons for spinner management
        stream_frame = self.stream_control_panel.get_main_frame()
        favorites_frame = self.favorites_panel.get_main_frame()
        
        # Create spinner managers (will be enhanced when buttons are accessible)
        self.spinner_manager = SpinnerManager(self.root)

    def _setup_component_communication(self) -> None:
        """Setup callbacks and communication between components"""
        # Stream control panel callbacks
        self.stream_control_panel.set_callbacks(
            on_watch_stream=self._on_watch_stream_requested
        )
        
        # Favorites panel callbacks
        self.favorites_panel.set_callbacks(
            on_channel_selected=self._on_favorite_channel_selected,
            on_watch_favorite=self._on_watch_favorite_requested,
            on_refresh_status=self._on_refresh_status_requested,
            on_cancel_operation=self._on_cancel_operation_requested
        )
        
        # Stream controller callbacks
        self.stream_controller.set_callbacks(
            on_started=self._on_stream_started,
            on_finished=self._on_stream_finished,
            on_error=self._on_stream_error
        )
        
        # Configuration controller callbacks
        self.config_controller.set_callbacks(
            on_debug_changed=self._on_debug_mode_changed,
            on_theme_changed=self._on_theme_changed_from_config
        )
        
        # Theme controller callbacks
        self.theme_controller.set_theme_change_callback(self._on_theme_applied)
        
        # Chat controller callbacks (will be set after initialization)
        # These are set in _finalize_initialization after chat_controller exists

    def _finalize_initialization(self) -> None:
        """Complete initialization with theme application and monitoring"""
        # Apply initial theme
        self.theme_controller.apply_theme()
        
        # Setup chat controller callbacks (now that it's initialized)
        if hasattr(self, 'chat_controller'):
            self.chat_controller.set_callbacks(
                on_connected=self._on_chat_connected,
                on_disconnected=self._on_chat_disconnected,
                on_error=self._on_chat_error
            )
        
        # Simple loading: load favorites immediately
        self.favorites_panel.refresh_favorites_list()
            
        logger.info("Refactored StreamGUI initialized successfully")
        

    # Event Handlers
    def _on_watch_stream_requested(self, channel: str, quality: str) -> None:
        """Handle stream watch request from control panel"""
        # Update configuration from UI
        debug_mode = getattr(self, 'debug_var', tk.BooleanVar()).get()
        player = getattr(self, 'player_var', tk.StringVar(value="vlc")).get()
        
        # Start stream via controller
        success = self.stream_controller.start_stream(channel, player, quality, debug_mode)
        
        if success:
            # Update main window title
            self.main_window.update_title(f"Watching {channel}")
            
            # Auto-connect to chat if enabled
            if hasattr(self, 'chat_controller') and self.chat_controller.should_auto_connect():
                self.chat_controller.connect_to_channel(channel)

    def _on_favorite_channel_selected(self, channel: str) -> None:
        """Handle favorite channel selection"""
        # Update stream control panel with selected channel
        self.stream_control_panel.set_channel_name(channel)

    def _on_watch_favorite_requested(self, channel: str) -> None:
        """Handle watch favorite request"""
        # Set channel in control panel and trigger watch
        self.stream_control_panel.set_channel_name(channel)
        quality = self.stream_control_panel.get_quality()
        self._on_watch_stream_requested(channel, quality)

    def _on_refresh_status_requested(self) -> None:
        """Handle status refresh request"""
        self.status_manager.add_status_message("Refreshing stream status...")
        # Simple manual refresh - check all favorites sequentially
        try:
            favorites = self.favorites_manager.get_favorites()
            if favorites:
                for channel in favorites:
                    try:
                        is_live = self.status_checker.check_stream_status(channel)
                        self.favorites_manager.update_channel_status(channel, is_live)
                    except Exception as e:
                        logger.warning(f"Failed to check status for {channel}: {e}")
                
                # Update UI
                self.favorites_panel.refresh_favorites_list()
                self.favorites_panel.on_refresh_completed()
                self.status_manager.add_status_message("Status refresh completed")
            else:
                self.status_manager.add_status_message("No favorites to refresh")
        except Exception as e:
            logger.error(f"Error during status refresh: {e}")
            self.favorites_panel.on_refresh_completed()
            self.status_manager.add_error(f"Status refresh failed: {str(e)}")

    def _on_cancel_operation_requested(self) -> bool:
        """Handle cancel operation request"""
        # Since we no longer have background operations, nothing to cancel
        self.status_manager.add_status_message("No operation to cancel")
        return False

    def _on_stream_started(self) -> None:
        """Handle stream start event"""
        self.stream_control_panel.set_loading_state(True, "Starting stream...")
        # Update main window reference for cleanup
        current_process = self.stream_controller.current_stream_process
        self.main_window.set_stream_process(current_process)

    def _on_stream_finished(self, message: str) -> None:
        """Handle stream completion"""
        self.stream_control_panel.set_loading_state(False)
        self.main_window.update_title()  # Reset title
        self.main_window.set_stream_process(None)
        
        # Disconnect chat when stream ends
        if hasattr(self, 'chat_controller'):
            self.chat_controller.disconnect_from_chat()

    def _on_stream_error(self, message: str) -> None:
        """Handle stream error"""
        self.stream_control_panel.set_loading_state(False)
        self.main_window.update_title()  # Reset title
        self.main_window.set_stream_process(None)
        
        # Disconnect chat when stream errors
        if hasattr(self, 'chat_controller'):
            self.chat_controller.disconnect_from_chat()

    def _on_debug_mode_changed(self, enabled: bool) -> None:
        """Handle debug mode change"""
        if hasattr(self, 'debug_var'):
            self.debug_var.set(enabled)

    def _on_theme_changed_from_config(self, theme_name: str) -> None:
        """Handle theme change from configuration"""
        self.theme_controller.change_theme(theme_name, animate=True)

    def _on_theme_applied(self, theme_name: str, theme_dict: dict) -> None:
        """Handle theme application completion"""
        # Update components with new theme
        self.stream_control_panel.set_theme(theme_dict)
        self.favorites_panel.set_theme(theme_dict)
        self.validation_controller.set_theme(theme_dict)
        if hasattr(self, 'chat_panel'):
            self.chat_panel.set_theme(theme_dict)
        
        # Refresh favorites to update canvas colors
        self.favorites_panel.refresh_favorites_list()


    # Chat event handlers
    def _on_chat_connected(self, channel: str) -> None:
        """Handle chat connection success"""
        logger.info(f"Chat connected to #{channel}")

    def _on_chat_disconnected(self) -> None:
        """Handle chat disconnection"""
        logger.info("Chat disconnected")

    def _on_chat_error(self, error_message: str) -> None:
        """Handle chat connection errors"""
        logger.warning(f"Chat error: {error_message}")

    def _on_progress_update(self, message: str, current: int, total: int) -> None:
        """Handle progress updates from network operations"""
        # Schedule progress update on main thread
        self.root.after(0, lambda: self._update_progress_display(message, current, total))
        
    def _update_progress_display(self, message: str, current: int, total: int) -> None:
        """Update progress display on main thread"""
        if total > 1:  # Only show progress for multiple operations
            percentage = int((current / total) * 100)
            progress_message = f"{message} ({current}/{total} - {percentage}%)"
        else:
            progress_message = message
            
        self.status_manager.add_status_message(progress_message)

    # Simplified UI creation methods (for sections not yet componentized)

    def _create_settings_section(self, parent: ttk.Frame) -> None:
        """Create the settings section"""
        settings_frame = ttk.LabelFrame(parent, text="Settings", padding="10")
        settings_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Player selection
        ttk.Label(settings_frame, text="Player:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        
        self.player_var = tk.StringVar(value=self.config.get("player", "vlc"))
        player_combo = ttk.Combobox(settings_frame, textvariable=self.player_var, width=15)
        player_combo["values"] = ("vlc", "mpv", "mpc-hc", "potplayer", "firefox", "chrome", "edge")
        player_combo.grid(row=0, column=1, sticky=tk.W, padx=(0, 20))
        player_combo.state(["readonly"])
        
        
        # Dark mode checkbox
        self.dark_mode_var = tk.BooleanVar(value=self.theme_controller.get_current_theme_name() == "dark")
        dark_mode_check = ttk.Checkbutton(
            settings_frame,
            text="Dark Mode", 
            variable=self.dark_mode_var,
            command=self._on_theme_toggle
        )
        dark_mode_check.grid(row=0, column=2, sticky=tk.W, padx=(0, 20))
        

    def _create_status_section(self, parent: ttk.Frame) -> None:
        """Create the status display section"""
        status_frame = ttk.LabelFrame(parent, text="Status", padding="5")
        status_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        # Create status text widget
        self.status_text_widget = tk.Text(
            status_frame,
            height=3,  # Default height, will be configured by StatusManager
            state=tk.DISABLED,
            wrap=tk.WORD,
            relief=tk.SUNKEN,
            borderwidth=1
        )
        self.status_text_widget.pack(fill=tk.BOTH, expand=True)
        
        # Configure frame to expand
        status_frame.columnconfigure(0, weight=1)
        status_frame.rowconfigure(0, weight=1)

    def _initialize_status_manager(self) -> None:
        """Initialize StatusManager after status widget is created"""
        # Initialize StatusManager with the text widget
        self.status_manager = StatusManager(self.status_text_widget)
        
        # Update controllers that need StatusManager
        self.theme_controller.set_status_manager(self.status_manager)
        self.config_controller = ConfigController(self.config, self.status_manager)
        self.stream_controller = StreamController(
            self.viewer, 
            self.config, 
            self.status_manager
        )
        
        # Update favorites panel with the initialized status manager
        self.favorites_panel.set_status_manager(self.status_manager)
        
        # Update chat panel with the initialized status manager
        self.chat_panel.status_manager = self.status_manager
        
        # Initialize ChatController now that StatusManager is available
        self.chat_controller = ChatController(
            self.root,
            self.chat_panel,
            self.config,
            self.status_manager
        )
        

    def _on_debug_toggle(self) -> None:
        """Handle debug mode toggle"""
        enabled = self.debug_var.get()
        self.config_controller.toggle_debug_mode(enabled)

    def _on_theme_toggle(self) -> None:
        """Handle theme toggle"""
        is_dark = self.dark_mode_var.get()
        theme_name = "dark" if is_dark else "light"
        
        if self.theme_controller.change_theme(theme_name, animate=True):
            # Save to configuration
            self.config_controller.change_theme(theme_name)
            


    # Public interface methods (for external usage)
    def get_root(self) -> tk.Tk:
        """Get the root window"""
        return self.root

    def cleanup(self) -> None:
        """Clean up resources"""
        logger.info("Cleaning up refactored StreamGUI")
        
            
        # Clean up controllers
        self.stream_controller.stop_stream()
        self.theme_controller.cleanup()
        if hasattr(self, 'chat_controller'):
            self.chat_controller.cleanup()
        
        # Clean up components
        if hasattr(self.favorites_panel, 'cleanup'):
            self.favorites_panel.cleanup()
        if hasattr(self.stream_control_panel, 'cleanup'):
            self.stream_control_panel.cleanup()
        if hasattr(self, 'chat_panel') and hasattr(self.chat_panel, 'cleanup'):
            self.chat_panel.cleanup()
            
        # Clean up utilities
        self.spinner_manager.cleanup()


def main(config_manager=None):
    """Main GUI entry point"""
    root = tk.Tk()
    app = StreamGUI(root, config_manager)

    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()