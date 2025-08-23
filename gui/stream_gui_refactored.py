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
from .components import MainWindow, FavoritesPanel, StreamControlPanel
from .controllers import (
    StreamController, 
    ConfigController, 
    ValidationController, 
    ThemeController
)
from .utils import SpinnerManager, create_watch_button_spinner, create_refresh_button_spinner
from .status_manager import StatusManager
from .favorites_manager import FavoritesManager
from .themes import get_theme

# Core functionality imports
from src.twitch_viewer import TwitchViewer
from src.config_manager import ConfigManager
from src.streamlink_status import StreamlinkStatusChecker
from src.status_monitor import StatusMonitor
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
        
        # Initialize status monitoring
        self.status_checker = StreamlinkStatusChecker(self.config)
        self.status_manager = StatusManager()
        self.status_monitor = StatusMonitor(
            status_checker=self.status_checker,
            favorites_manager=self.favorites_manager,
            config_manager=self.config,
            status_callback=self._on_status_updated,
        )
        
        # Initialize controllers
        self._initialize_controllers()
        
        # Initialize main window
        self.main_window = MainWindow(root, self.config)
        self.main_window.set_status_monitor(self.status_monitor)
        
        # Initialize UI components
        self._initialize_components()
        
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
        self.theme_controller.set_status_manager(self.status_manager)
        
        # Configuration controller
        self.config_controller = ConfigController(self.config, self.status_manager)
        
        # Validation controller
        current_theme = get_theme(initial_theme)
        self.validation_controller = ValidationController(current_theme)
        
        # Stream controller
        self.stream_controller = StreamController(
            self.viewer, 
            self.config, 
            self.status_manager
        )

    def _initialize_components(self) -> None:
        """Initialize all UI components"""
        main_frame = self.main_window.get_main_frame()
        
        # Stream control panel
        self.stream_control_panel = StreamControlPanel(
            main_frame,
            self.validation_controller,
            self.theme_controller.get_current_theme()
        )
        
        # Favorites panel
        self.favorites_panel = FavoritesPanel(
            main_frame,
            self.favorites_manager,
            self.status_manager,
            self.theme_controller.get_current_theme()
        )
        
        # Status section (simplified - could be extracted to component later)
        self._create_status_section(main_frame)
        
        # Settings section (simplified - could be extracted to component later)  
        self._create_settings_section(main_frame)
        
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
            on_refresh_status=self._on_refresh_status_requested
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

    def _finalize_initialization(self) -> None:
        """Complete initialization with theme application and monitoring"""
        # Apply initial theme
        self.theme_controller.apply_theme()
        
        # Refresh favorites display
        self.favorites_panel.refresh_favorites_list()
        
        # Check streamlink dependency
        self._check_streamlink_dependency()
        
        # Start status monitoring if available
        if self.status_checker.is_available():
            self.status_monitor.start_monitoring()
            
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
        self.status_monitor.force_refresh()

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

    def _on_stream_error(self, message: str) -> None:
        """Handle stream error"""
        self.stream_control_panel.set_loading_state(False)
        self.main_window.update_title()  # Reset title
        self.main_window.set_stream_process(None)

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
        
        # Refresh favorites to update canvas colors
        self.favorites_panel.refresh_favorites_list()

    def _on_status_updated(self, updated_channels: list) -> None:
        """Handle status monitor updates"""
        # Schedule GUI update on main thread
        self.root.after(0, self.favorites_panel.refresh_favorites_list)
        
        # Provide user feedback
        if len(updated_channels) == 1:
            self.status_manager.add_status_message(
                f"Status updated for {updated_channels[0]}"
            )
        elif len(updated_channels) > 1:
            self.status_manager.add_status_message(
                f"Status updated for {len(updated_channels)} channels"
            )

    # Simplified UI creation methods (for sections not yet componentized)
    def _create_status_section(self, parent: ttk.Frame) -> None:
        """Create the status display section"""
        status_frame = ttk.LabelFrame(parent, text="Status", padding="10")
        status_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        # Create status text widget
        status_text = tk.Text(
            status_frame, 
            height=8, 
            state=tk.DISABLED,
            wrap=tk.WORD
        )
        
        # Create scrollbar
        status_scrollbar = ttk.Scrollbar(status_frame, orient="vertical", command=status_text.yview)
        status_text.configure(yscrollcommand=status_scrollbar.set)
        
        status_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        status_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Configure grid weights
        status_frame.columnconfigure(0, weight=1)
        status_frame.rowconfigure(0, weight=1)
        
        # Initialize status manager with text widget
        self.status_manager.initialize(status_text, self.theme_controller.get_current_theme())

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
        
        # Debug mode checkbox  
        self.debug_var = tk.BooleanVar(value=self.config.get("debug", False))
        debug_check = ttk.Checkbutton(
            settings_frame,
            text="Debug Mode",
            variable=self.debug_var,
            command=self._on_debug_toggle
        )
        debug_check.grid(row=0, column=2, sticky=tk.W, padx=(0, 20))
        
        # Dark mode checkbox
        self.dark_mode_var = tk.BooleanVar(value=self.theme_controller.get_current_theme_name() == "dark")
        dark_mode_check = ttk.Checkbutton(
            settings_frame,
            text="Dark Mode", 
            variable=self.dark_mode_var,
            command=self._on_theme_toggle
        )
        dark_mode_check.grid(row=0, column=3, sticky=tk.W)

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

    def _check_streamlink_dependency(self) -> None:
        """Check streamlink availability and warn if not found"""
        if not self.status_checker.is_available():
            self.status_manager.add_error(
                "Streamlink not found. Please install streamlink for full functionality."
            )
        else:
            self.status_manager.add_system_message("Streamlink detected - all features available")

    # Public interface methods (for external usage)
    def get_root(self) -> tk.Tk:
        """Get the root window"""
        return self.root

    def cleanup(self) -> None:
        """Clean up resources"""
        logger.info("Cleaning up refactored StreamGUI")
        
        # Stop monitoring
        if self.status_monitor:
            self.status_monitor.stop_monitoring()
            
        # Clean up controllers
        self.stream_controller.stop_stream()
        self.theme_controller.cleanup()
        
        # Clean up components
        if hasattr(self.favorites_panel, 'cleanup'):
            self.favorites_panel.cleanup()
        if hasattr(self.stream_control_panel, 'cleanup'):
            self.stream_control_panel.cleanup()
            
        # Clean up utilities
        self.spinner_manager.cleanup()