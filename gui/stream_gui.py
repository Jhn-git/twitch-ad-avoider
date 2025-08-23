"""
Tkinter-based GUI for TwitchAdAvoider Stream Manager.

This module provides a lightweight graphical interface for TwitchAdAvoider with:
    - Real-time input validation and visual feedback
    - Channel favorites management with persistent storage
    - Asynchronous status monitoring for favorite channels  
    - Theme support with light/dark modes
    - Cross-platform compatibility

The :class:`StreamGUI` class serves as the main interface, integrating with the core
streaming functionality while providing a user-friendly experience.

Key Features:
    - Thread-safe operations for non-blocking UI
    - Comprehensive error handling and user feedback
    - Integration with the validation system
    - Status monitoring with visual indicators

See Also:
    :class:`~src.twitch_viewer.TwitchViewer`: Core streaming functionality
    :class:`~src.config_manager.ConfigManager`: Configuration management
    :class:`~gui.favorites_manager.FavoritesManager`: Channel favorites handling
    :class:`~gui.status_manager.StatusManager`: GUI status management
    :mod:`src.validators`: Input validation functions
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, font
import threading
import subprocess
import sys
import os
import platform
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import status manager
from .status_manager import StatusManager, StatusLevel, StatusCategory

from src.twitch_viewer import TwitchViewer
from src.exceptions import TwitchStreamError, ValidationError
from src.config_manager import ConfigManager
from src.validators import validate_channel_name
from src.logging_config import get_logger, reconfigure_logging_from_config
from src.streamlink_status import StreamlinkStatusChecker
from src.status_monitor import StatusMonitor
from src.constants import GUI_GEOMETRY, GUI_MIN_SIZE
from gui.favorites_manager import FavoritesManager, FavoriteChannelInfo
from gui.themes import get_theme

logger = get_logger(__name__)


def get_emoji_font():
    """
    Get an appropriate font for emoji display based on the operating system.

    Returns:
        tuple: (font_family, font_size) for emoji support, or None if no suitable font found
    """
    system = platform.system().lower()

    # Try to create test font objects to see what's available
    try:
        if system == "windows":
            # Windows emoji fonts in order of preference
            font_options = [
                ("Segoe UI Emoji", 10),
                ("Segoe UI Symbol", 10),
                ("Segoe UI", 10),
                ("Arial Unicode MS", 10),
            ]
        elif system == "darwin":  # macOS
            font_options = [("Apple Color Emoji", 10), ("Helvetica", 10)]
        else:  # Linux and other Unix-like systems
            font_options = [
                ("Noto Color Emoji", 10),
                ("DejaVu Sans", 10),
                ("Liberation Sans", 10),
                ("Arial", 10),
            ]

        # Test each font option to see if it's available
        for family, size in font_options:
            try:
                test_font = font.Font(family=family, size=size)
                # If we get here without exception, the font is available
                logger.debug(f"Using emoji font: {family} size {size}")
                return (family, size)
            except tk.TclError:
                continue

    except Exception as e:
        logger.debug(f"Error detecting emoji fonts: {e}")

    # Fallback to default font
    logger.debug("No specific emoji font found, using system default")
    return None


class StreamGUI:
    """
    Main GUI class for TwitchAdAvoider Stream Manager.

    Provides a user-friendly interface for watching Twitch streams with features including:
    - Real-time channel name validation
    - Favorites management
    - Quality selection
    - Status monitoring
    - Player configuration
    """

    def __init__(self, root: tk.Tk, config_manager: Optional[ConfigManager] = None):
        """
        Initialize the Stream GUI.

        Args:
            root: The main tkinter window
            config_manager: Configuration manager instance
        """
        self.root = root
        self.root.title("TwitchAdAvoider - Stream Manager")
        self.root.geometry(GUI_GEOMETRY)
        self.root.resizable(True, True)
        self.root.minsize(*GUI_MIN_SIZE)
        self.root.maxsize(1200, 900)  # Set reasonable maximum size

        # Initialize managers
        self.config = config_manager or ConfigManager()
        self.viewer = TwitchViewer(self.config)
        self.favorites_manager = FavoritesManager()

        # Initialize status checker and monitor
        self.status_checker = StreamlinkStatusChecker(self.config, progress_callback=self._on_progress_update)
        self.status_monitor = StatusMonitor(
            status_checker=self.status_checker,
            favorites_manager=self.favorites_manager,
            config_manager=self.config,
            status_callback=self._on_status_updated,
        )

        # Current stream process and thread
        self.current_stream_thread = None
        self.current_stream_process = None
        
        # Loading spinner state
        self.spinner_running = False
        self.refresh_spinner_running = False
        self.spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.spinner_index = 0
        self.refresh_spinner_index = 0
        
        # Theme animation state
        self.theme_animation_active = False

        # Theme management
        self.current_theme_name = self.config.get("current_theme", "light")
        self.current_theme = get_theme(self.current_theme_name)
        self.themed_widgets = []  # Track widgets that need theming

        # Create GUI components
        self.setup_gui()
        self.apply_theme()  # Apply initial theme
        
        # Implement progressive loading based on configuration
        enable_progressive_loading = self.config.get("enable_progressive_loading", True)
        show_startup_progress = self.config.get("show_startup_progress", True)
        
        if enable_progressive_loading:
            # Phase 1: Load favorites display first (immediate)
            self.refresh_favorites_list()
            
            if show_startup_progress:
                self.status_manager.add_status_message("Favorites loaded. Preparing status monitoring...")
            
            # Phase 2: Initialize status monitoring with delay (background)
            self.root.after(100, self._initialize_status_monitoring_delayed)
        else:
            # Traditional loading: everything at once
            self.refresh_favorites_list()
            self._initialize_status_monitoring_delayed()

        # Handle window closing
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def _initialize_status_monitoring_delayed(self) -> None:
        """Initialize status monitoring with optional startup feedback"""
        show_startup_progress = self.config.get("show_startup_progress", True)
        
        # Check streamlink availability and warn user if not available
        self._check_streamlink_dependency()

        # Start status monitoring if streamlink is available
        if self.status_checker.is_available():
            if show_startup_progress:
                startup_delay = self.config.get("startup_status_check_delay", 2)
                if startup_delay > 0:
                    self.status_manager.add_status_message(
                        f"Starting status monitoring in {startup_delay} seconds..."
                    )
            
            self.status_monitor.start_monitoring(delayed_start=True)
            
            if show_startup_progress:
                self.status_manager.add_status_message("Status monitoring active")

    def setup_gui(self) -> None:
        """
        Setup the GUI layout and components.

        Creates the main interface including:
        - Stream input section with validation
        - Quality selection dropdown
        - Favorites management section
        - Status display
        - Player configuration
        """
        # Create main frame
        main_frame = self._create_main_frame()
        
        # Setup sections
        input_frame = self._setup_stream_input_section(main_frame)
        fav_frame, list_frame, fav_btn_frame = self._setup_favorites_section(main_frame)
        settings_frame = self._setup_settings_section(main_frame)
        self._setup_status_section(main_frame)
        
        # Configure layout and theme management
        self._configure_grid_layout(main_frame, input_frame, fav_frame, list_frame, settings_frame)
        self._register_themed_widgets(main_frame, input_frame, fav_frame, list_frame, fav_btn_frame, settings_frame)

    def _create_main_frame(self) -> ttk.Frame:
        """Create and configure the main container frame."""
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        return main_frame

    def _setup_stream_input_section(self, parent: ttk.Frame) -> ttk.LabelFrame:
        """Setup the stream input section with channel entry and quality selection."""
        input_frame = ttk.LabelFrame(parent, text="Watch Stream", padding="10")
        input_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        # Channel input
        ttk.Label(input_frame, text="Channel:").grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        self.channel_var = tk.StringVar()
        self.channel_entry = ttk.Entry(input_frame, textvariable=self.channel_var, width=25)
        self.channel_entry.grid(row=0, column=1, padx=(10, 0), pady=(0, 5), sticky=(tk.W, tk.E))
        self.channel_entry.bind("<Return>", lambda e: self.watch_stream())

        # Add real-time validation for channel input
        self.channel_var.trace_add("write", self._validate_channel_input)

        # Validation feedback label
        self.validation_label = ttk.Label(input_frame, text="", foreground="red", font=("Arial", 8))
        self.validation_label.grid(row=0, column=2, padx=(5, 0), pady=(0, 5), sticky=tk.W)

        # Quality selection
        ttk.Label(input_frame, text="Quality:").grid(row=1, column=0, sticky=tk.W, pady=(0, 5))
        self.quality_var = tk.StringVar(value="best")
        quality_combo = ttk.Combobox(input_frame, textvariable=self.quality_var, width=22)
        quality_combo["values"] = ("best", "worst", "720p", "480p", "360p")
        quality_combo.grid(row=1, column=1, padx=(10, 0), pady=(0, 5), sticky=(tk.W, tk.E))
        quality_combo.state(["readonly"])

        # Watch button
        self.watch_btn = ttk.Button(input_frame, text="Watch Stream", command=self.watch_stream)
        self.watch_btn.grid(row=2, column=0, columnspan=2, pady=(15, 5))

        return input_frame

    def _setup_favorites_section(self, parent: ttk.Frame) -> tuple[ttk.LabelFrame, ttk.Frame, ttk.Frame]:
        """Setup the favorites section with list display and management buttons."""
        fav_frame = ttk.LabelFrame(parent, text="Favorites", padding="10")
        fav_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))

        # Create and configure favorites list
        list_frame = self._create_favorites_list(fav_frame)
        
        # Create favorites management buttons
        fav_btn_frame = self._create_favorites_buttons(fav_frame)

        return fav_frame, list_frame, fav_btn_frame

    def _create_favorites_list(self, parent: ttk.LabelFrame) -> ttk.Frame:
        """Create the favorites list widget with scrollbar."""
        list_frame = ttk.Frame(parent)
        list_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Configure favorites text widget with emoji-supporting font
        emoji_font_config = get_emoji_font()
        if emoji_font_config:
            family, size = emoji_font_config
            favorites_font = font.Font(family=family, size=size)
            self.favorites_listbox = tk.Text(
                list_frame,
                height=8,
                font=favorites_font,
                state=tk.DISABLED,
                cursor="arrow",
                wrap=tk.NONE,
            )
        else:
            self.favorites_listbox = tk.Text(
                list_frame, height=8, state=tk.DISABLED, cursor="arrow", wrap=tk.NONE
            )

        scrollbar = ttk.Scrollbar(
            list_frame, orient="vertical", command=self.favorites_listbox.yview
        )
        self.favorites_listbox.configure(yscrollcommand=scrollbar.set)

        # Configure text widget appearance to look like a listbox
        self.favorites_listbox.configure(
            bg="white",
            relief=tk.SUNKEN,
            borderwidth=1,
            selectbackground="#0078d4",  # Windows-style selection color
            selectforeground="white",
        )

        self.favorites_listbox.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        # Initialize selection tracking
        self.selected_favorite_line = None
        self.canvas_widgets = []  # Track Canvas widgets for dynamic background updates

        # Bind events for list-like behavior
        self.favorites_listbox.bind("<Button-1>", self._on_favorite_click)
        self.favorites_listbox.bind("<Double-Button-1>", lambda e: self.watch_favorite())

        return list_frame

    def _create_favorites_buttons(self, parent: ttk.LabelFrame) -> ttk.Frame:
        """Create the favorites management buttons."""
        fav_btn_frame = ttk.Frame(parent)
        fav_btn_frame.grid(row=1, column=0, columnspan=3, pady=(10, 0))

        ttk.Button(fav_btn_frame, text="Add Current", command=self.add_favorite).pack(
            side=tk.LEFT, padx=(0, 5)
        )
        ttk.Button(fav_btn_frame, text="Add New", command=self.add_new_favorite).pack(
            side=tk.LEFT, padx=(0, 5)
        )
        ttk.Button(fav_btn_frame, text="Remove", command=self.remove_favorite).pack(
            side=tk.LEFT, padx=(0, 5)
        )
        self.refresh_btn = ttk.Button(fav_btn_frame, text="🔄 Refresh", command=self.refresh_status)
        self.refresh_btn.pack(side=tk.LEFT)

        return fav_btn_frame

    def _setup_settings_section(self, parent: ttk.Frame) -> ttk.LabelFrame:
        """Setup the settings section with player and mode controls."""
        settings_frame = ttk.LabelFrame(parent, text="Settings", padding="10")
        settings_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        # Player selection
        ttk.Label(settings_frame, text="Player:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.player_var = tk.StringVar(value=self.config.get("player", "vlc"))
        player_combo = ttk.Combobox(settings_frame, textvariable=self.player_var, width=12)
        player_combo["values"] = ("vlc", "mpv", "mpc-hc", "auto")
        player_combo.grid(row=0, column=1, padx=(10, 20), pady=5, sticky=tk.W)
        player_combo.state(["readonly"])

        # Debug mode
        self.debug_var = tk.BooleanVar(value=self.config.get("debug", False))
        debug_check = ttk.Checkbutton(
            settings_frame,
            text="Debug Mode",
            variable=self.debug_var,
            command=self._on_debug_toggle,
        )
        debug_check.grid(row=0, column=2, pady=5, sticky=tk.W)

        # Dark mode toggle
        self.dark_mode_var = tk.BooleanVar(value=self.current_theme_name == "dark")
        dark_mode_check = ttk.Checkbutton(
            settings_frame,
            text="Dark Mode",
            variable=self.dark_mode_var,
            command=self._on_theme_toggle,
        )
        dark_mode_check.grid(row=0, column=3, pady=5, sticky=tk.W, padx=(0, 10))

        # Status monitoring toggle
        self.status_monitoring_var = tk.BooleanVar(value=self.config.get("enable_status_monitoring", True))
        status_monitoring_check = ttk.Checkbutton(
            settings_frame,
            text="Auto Status",
            variable=self.status_monitoring_var,
            command=self._on_status_monitoring_toggle,
        )
        status_monitoring_check.grid(row=0, column=4, pady=5, sticky=tk.W)

        return settings_frame

    def _setup_status_section(self, parent: ttk.Frame) -> None:
        """Setup the status display section."""
        self.status_text = tk.Text(parent)
        self.status_manager = StatusManager(self.status_text, max_history=100)
        self.status_text.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 0))

    def _configure_grid_layout(self, main_frame: ttk.Frame, input_frame: ttk.LabelFrame, 
                              fav_frame: ttk.LabelFrame, list_frame: ttk.Frame, 
                              settings_frame: ttk.LabelFrame) -> None:
        """Configure grid weights for responsive layout."""
        # Root window
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # Main frame
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(0, weight=0)  # Input section - fixed size
        main_frame.rowconfigure(1, weight=1)  # Favorites section - expandable
        main_frame.rowconfigure(2, weight=0)  # Settings section - fixed size
        main_frame.rowconfigure(3, weight=0)  # Status bar - fixed size

        # Input frame
        input_frame.columnconfigure(1, weight=1)

        # Favorites frame
        fav_frame.columnconfigure(0, weight=1)
        fav_frame.rowconfigure(0, weight=1)  # List area expandable
        fav_frame.rowconfigure(1, weight=0)  # Button area fixed

        # List frame
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        # Settings frame
        settings_frame.columnconfigure(1, weight=1)
        settings_frame.columnconfigure(2, weight=1)
        settings_frame.columnconfigure(3, weight=1)

    def _register_themed_widgets(self, main_frame: ttk.Frame, input_frame: ttk.LabelFrame,
                                fav_frame: ttk.LabelFrame, list_frame: ttk.Frame,
                                fav_btn_frame: ttk.Frame, settings_frame: ttk.LabelFrame) -> None:
        """Register widgets for theme management."""
        self.themed_widgets.extend(
            [
                main_frame,
                input_frame,
                fav_frame,
                list_frame,
                fav_btn_frame,
                settings_frame,
                self.favorites_listbox,
                self.status_text,
                self.validation_label,
            ]
        )

    def _check_streamlink_dependency(self) -> None:
        """
        Check if streamlink is available and warn user if not.

        Displays an error dialog and disables functionality if streamlink is not available.
        """
        if not self.viewer.is_streamlink_available():
            self.status_manager.add_error(
                "Streamlink not available - install with 'pip install streamlink'",
                StatusCategory.SYSTEM,
            )
            # Disable watch functionality
            self.watch_btn.config(state="disabled", text="Streamlink Required")

    def _disable_watch_buttons(self) -> None:
        """
        Disable watch button during stream.

        Prevents multiple concurrent streams from being started.
        """
        self.watch_btn.config(state="disabled")

    def _enable_watch_buttons(self) -> None:
        """
        Re-enable watch button after stream ends.

        Restores watch functionality after a stream process completes.
        """
        self._stop_spinner()
        self.watch_btn.config(state="normal", text="Watch Stream")
    
    def _start_spinner(self, message: str = "Starting...") -> None:
        """Start the loading spinner animation on the watch button"""
        if not self.spinner_running:
            self.spinner_running = True
            self.spinner_index = 0
            self._update_spinner(message)
    
    def _stop_spinner(self) -> None:
        """Stop the loading spinner animation"""
        self.spinner_running = False
    
    def _update_spinner(self, base_message: str) -> None:
        """Update spinner animation frame"""
        if not self.spinner_running:
            return
        
        spinner_char = self.spinner_chars[self.spinner_index]
        self.watch_btn.config(text=f"{spinner_char} {base_message}")
        self.spinner_index = (self.spinner_index + 1) % len(self.spinner_chars)
        
        # Schedule next frame (update every 100ms for smooth animation)
        self.root.after(100, lambda: self._update_spinner(base_message))
    
    def _start_refresh_spinner(self) -> None:
        """Start the refresh spinner animation"""
        if not self.refresh_spinner_running:
            self.refresh_spinner_running = True
            self.refresh_spinner_index = 0
            self.refresh_btn.config(state="disabled")
            self._update_refresh_spinner()
    
    def _stop_refresh_spinner(self) -> None:
        """Stop the refresh spinner animation"""
        self.refresh_spinner_running = False
        self.refresh_btn.config(state="normal", text="🔄 Refresh")
    
    def _update_refresh_spinner(self) -> None:
        """Update refresh spinner animation frame"""
        if not self.refresh_spinner_running:
            return
        
        spinner_char = self.spinner_chars[self.refresh_spinner_index]
        self.refresh_btn.config(text=f"{spinner_char} Refreshing...")
        self.refresh_spinner_index = (self.refresh_spinner_index + 1) % len(self.spinner_chars)
        
        # Schedule next frame (update every 150ms for refresh button)
        self.root.after(150, self._update_refresh_spinner)

    def _create_status_circle(self, parent, is_live: bool, size: int = 12) -> tk.Canvas:
        """
        Create a small Canvas with a colored circle for status indication.

        Args:
            parent: Parent widget for the Canvas
            is_live: True for live (red circle), False for offline (gray circle)
            size: Size of the Canvas and circle in pixels

        Returns:
            tk.Canvas: Canvas widget with drawn circle
        """
        # Configure Canvas with theme-aware background
        canvas = tk.Canvas(
            parent,
            width=size,
            height=size,
            highlightthickness=0,  # Remove focus highlight ring
            bd=0,  # Remove border
            bg=self.current_theme["canvas_bg"],  # Theme-aware background
            relief=tk.FLAT,
        )  # Ensure no border effects

        # Define colors using current theme
        if is_live:
            fill_color = self.current_theme["circle_live_fill"]
            outline_color = self.current_theme["circle_live_outline"]
        else:
            fill_color = self.current_theme["circle_offline_fill"]
            outline_color = self.current_theme["circle_offline_outline"]

        # Draw circle (with small margin)
        margin = 1
        canvas.create_oval(
            margin,
            margin,
            size - margin,
            size - margin,
            fill=fill_color,
            outline=outline_color,
            width=1,
        )

        return canvas

    def _update_canvas_backgrounds(self) -> None:
        """
        Update Canvas widget backgrounds to match their row selection state.

        This ensures Canvas widgets blend seamlessly with selected/unselected rows.
        """
        # Reset all Canvas widgets to default background
        for canvas in self.canvas_widgets:
            canvas.config(bg=self.current_theme["canvas_bg"])

        # Set selected row Canvas to selection background color
        if self.selected_favorite_line and self.selected_favorite_line <= len(self.canvas_widgets):
            # Canvas widgets are 0-indexed, but line numbers are 1-indexed
            canvas_index = self.selected_favorite_line - 1
            if 0 <= canvas_index < len(self.canvas_widgets):
                selected_canvas = self.canvas_widgets[canvas_index]
                selected_canvas.config(bg=self.current_theme["canvas_selected_bg"])

    def apply_theme(self) -> None:
        """
        Apply current theme to all widgets in the application.

        This is the core of the centralized theming engine.
        """
        theme = self.current_theme

        # Configure root window
        self.root.config(bg=theme["root_bg"])

        # Configure Text widgets (favorites list and status)
        self.favorites_listbox.configure(
            bg=theme["text_bg"],
            fg=theme["text_fg"],
            selectbackground=theme["text_select_bg"],
            selectforeground=theme["text_select_fg"],
            insertbackground=theme["text_fg"],
        )

        # Update favorites selection tag colors
        self.favorites_listbox.tag_configure(
            "selected", background=theme["text_select_bg"], foreground=theme["text_select_fg"]
        )

        # Configure TTK Style for themed widgets
        style = ttk.Style()
        try:
            style.theme_use("clam")  # Use clam theme as base for styling
        except tk.TclError:
            pass  # Fallback to default if clam not available

        # Configure TTK widget styles
        style.configure("TFrame", background=theme["frame_bg"])
        style.configure(
            "TLabelFrame", background=theme["frame_bg"], foreground=theme["labelframe_fg"]
        )
        style.configure(
            "TLabelFrame.Label", background=theme["frame_bg"], foreground=theme["labelframe_fg"]
        )
        style.configure("TLabel", background=theme["label_bg"], foreground=theme["label_fg"])
        style.configure("TButton", background=theme["button_bg"], foreground=theme["button_fg"])
        style.map("TButton", background=[("active", theme["button_active_bg"])])
        style.configure("TEntry", fieldbackground=theme["entry_bg"], foreground=theme["entry_fg"])
        style.configure(
            "TCombobox", fieldbackground=theme["combobox_bg"], foreground=theme["combobox_fg"]
        )

        # Update validation label colors (will be set dynamically during validation)
        # Update Canvas status circles
        self._update_canvas_backgrounds()

        # Update status manager theme
        self.status_manager.update_theme(theme)

        logger.debug(f"Applied theme: {self.current_theme_name}")

    def apply_theme_with_animation(self, duration_ms: int = 250) -> None:
        """
        Apply theme with a smooth transition animation.
        
        Args:
            duration_ms: Duration of the transition in milliseconds
        """
        if self.theme_animation_active:
            return  # Prevent overlapping animations
        
        self.theme_animation_active = True
        
        # Create a semi-transparent overlay for smooth transition effect
        overlay = tk.Toplevel(self.root)
        overlay.withdraw()  # Hide initially
        overlay.overrideredirect(True)  # Remove window decorations
        overlay.attributes('-topmost', True)  # Keep on top
        
        # Position overlay over main window
        self.root.update_idletasks()  # Ensure geometry is updated
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        
        overlay.geometry(f"{width}x{height}+{x}+{y}")
        overlay.configure(bg="white")
        
        # Show overlay with fade-in effect
        overlay.deiconify()
        overlay.attributes('-alpha', 0.6)  # Semi-transparent
        
        # Apply the new theme after brief delay
        def apply_theme_delayed():
            self.apply_theme()
            # Fade out overlay
            self._fade_out_overlay(overlay, duration_ms // 2)
        
        self.root.after(duration_ms // 4, apply_theme_delayed)

    def _fade_out_overlay(self, overlay: tk.Toplevel, duration_ms: int) -> None:
        """Fade out the transition overlay"""
        steps = 10
        step_delay = duration_ms // steps
        alpha_step = 0.6 / steps
        current_alpha = 0.6
        
        def fade_step():
            nonlocal current_alpha
            current_alpha -= alpha_step
            if current_alpha <= 0:
                overlay.destroy()
                self.theme_animation_active = False
            else:
                try:
                    overlay.attributes('-alpha', current_alpha)
                    self.root.after(step_delay, fade_step)
                except tk.TclError:
                    # Handle case where overlay was destroyed
                    self.theme_animation_active = False
        
        fade_step()

    def switch_theme(self) -> None:
        """
        Switch between light and dark themes.

        Toggles the current theme and immediately applies it to all widgets.
        """
        # Toggle theme
        if self.current_theme_name == "light":
            new_theme_name = "dark"
        else:
            new_theme_name = "light"

        # Update theme
        self.current_theme_name = new_theme_name
        self.current_theme = get_theme(new_theme_name)

        # Save preference to config
        self.config.set("current_theme", new_theme_name)
        self.config.save_settings()

        # Apply new theme with animation
        self.apply_theme_with_animation(duration_ms=300)

        # Refresh favorites list to update Canvas circles (after animation delay)
        self.root.after(200, self.refresh_favorites_list)

        logger.info(f"Switched to {new_theme_name} theme")

    def _on_status_monitoring_toggle(self) -> None:
        """Handle status monitoring toggle"""
        enabled = self.status_monitoring_var.get()
        success = self.config.set("enable_status_monitoring", enabled)
        
        if success:
            self.config.save_settings()
            if enabled:
                if self.status_checker.is_available():
                    self.status_monitor.start_monitoring()
                    self.status_manager.add_status_message("Automatic status monitoring enabled")
                else:
                    self.add_error("Streamlink not available for status monitoring")
            else:
                self.status_monitor.stop_monitoring()
                self.status_manager.add_status_message("Automatic status monitoring disabled")
        else:
            # Reset checkbox if config update failed
            self.status_monitoring_var.set(not enabled)
            self.add_error("Failed to update status monitoring setting")

    def refresh_favorites_list(self) -> None:
        """
        Refresh the favorites text widget with status information.

        Updates the display to show current live status for each favorite channel.
        Uses Canvas-drawn circles: red for live channels, gray for offline channels.
        """
        # Clear current content and Canvas tracking
        self.favorites_listbox.configure(state=tk.NORMAL)
        self.favorites_listbox.delete(1.0, tk.END)
        self.selected_favorite_line = None
        
        # Properly destroy Canvas widgets before clearing to prevent memory leaks
        for canvas in self.canvas_widgets:
            canvas.destroy()
        self.canvas_widgets.clear()  # Clear Canvas widget tracking

        # Get favorites with status info
        favorites = self.favorites_manager.get_favorites_with_status()

        for i, fav in enumerate(favorites):
            if i > 0:
                self.favorites_listbox.insert(tk.END, "\n")

            # Create Canvas circle for status indication
            status_circle = self._create_status_circle(self.favorites_listbox, fav.is_live, size=14)

            # Store Canvas widget for dynamic background updates
            self.canvas_widgets.append(status_circle)

            # Insert the Canvas circle at the beginning of the line
            self.favorites_listbox.window_create(tk.END, window=status_circle)

            # Add channel name with a space after the circle
            self.favorites_listbox.insert(tk.END, f" {fav.channel_name}")

        # Update Canvas backgrounds to match current selection state
        self._update_canvas_backgrounds()

        self.favorites_listbox.configure(state=tk.DISABLED)

    def _validate_channel_input(self, *args) -> None:
        """
        Real-time validation for channel input with visual feedback.

        Args:
            *args: Tkinter trace callback arguments (unused)

        Provides immediate visual feedback on channel name validity:
        - Green checkmark for valid names
        - Red X with error message for invalid names
        - Enables/disables watch button based on validity
        """
        channel = self.channel_var.get().strip()

        if not channel:
            self.validation_label.config(
                text="", foreground=self.current_theme["validation_neutral"]
            )
            self.watch_btn.config(state="disabled")
            return

        try:
            validate_channel_name(channel)
            self.validation_label.config(
                text="✓ Valid", foreground=self.current_theme["validation_valid"]
            )
            self.watch_btn.config(state="normal")
        except ValidationError as e:
            self.validation_label.config(
                text=f"✗ {str(e)}", foreground=self.current_theme["validation_invalid"]
            )
            self.watch_btn.config(state="disabled")
        except Exception:
            self.validation_label.config(
                text="✗ Invalid format", foreground=self.current_theme["validation_invalid"]
            )
            self.watch_btn.config(state="disabled")

    def watch_stream(self) -> None:
        """
        Start watching a stream.

        Validates the channel name, updates configuration from GUI settings,
        and starts the stream in a separate thread to prevent GUI blocking.

        Handles:
        - Channel name validation
        - Concurrent stream prevention
        - Configuration updates
        - Debug mode changes
        - Thread management
        """
        channel = self.channel_var.get().strip()
        if not channel:
            self.status_manager.add_error("Please enter a channel name", StatusCategory.STREAM)
            return

        # Validate channel before proceeding
        try:
            validate_channel_name(channel)
        except ValidationError as e:
            self.status_manager.add_error(str(e), StatusCategory.STREAM)
            return

        # Prevent concurrent streams
        if self.current_stream_process and self.current_stream_process.poll() is None:
            self.status_manager.add_warning("A stream is already running. Please close it first.", StatusCategory.STREAM)
            return

        # Update configuration
        self.config.set("player", self.player_var.get())
        self.config.set("preferred_quality", self.quality_var.get())

        # Set player choice in TwitchViewer (prioritizes GUI selection)
        self.viewer.set_player_choice(self.player_var.get())

        # Handle debug mode changes with logging reconfiguration
        old_debug = self.config.get("debug", False)
        new_debug = self.debug_var.get()
        self.config.set("debug", new_debug)

        if old_debug != new_debug:
            self._reconfigure_logging()

        # Start stream in separate thread - disable all watch buttons
        self._disable_watch_buttons()
        self._start_spinner("Starting stream...")
        self.status_manager.add_stream_message(f"Starting stream for {channel}...")

        def stream_worker():
            try:
                # Store the process object
                self.current_stream_process = self.viewer.watch_stream(channel)

                # Now, wait for the process to complete
                return_code = self.current_stream_process.wait()

                # After it's done, clean up
                self.current_stream_process = None

                if return_code == 0:
                    self.root.after(0, lambda: self.stream_finished(f"Stream for {channel} ended"))
                else:
                    self.root.after(
                        0, lambda: self.stream_error(f"Streamlink exited with code {return_code}")
                    )

            except Exception as e:
                # Clean up process reference on error
                self.current_stream_process = None
                self.root.after(0, lambda: self.stream_error(f"Error: {str(e)}"))

        self.current_stream_thread = threading.Thread(target=stream_worker, daemon=True)
        self.current_stream_thread.start()

    def _on_favorite_click(self, event):
        """Handle click events in the favorites text widget for selection"""
        # Get the line that was clicked
        click_index = self.favorites_listbox.index(f"@{event.x},{event.y}")
        line_start = click_index.split(".")[0] + ".0"
        line_end = click_index.split(".")[0] + ".end"

        # Clear previous selection
        self.favorites_listbox.configure(state=tk.NORMAL)
        if self.selected_favorite_line:
            old_start = f"{self.selected_favorite_line}.0"
            old_end = f"{self.selected_favorite_line}.end"
            self.favorites_listbox.tag_remove("selected", old_start, old_end)

        # Add selection to clicked line
        line_num = int(click_index.split(".")[0])
        self.selected_favorite_line = line_num
        self.favorites_listbox.tag_add("selected", line_start, line_end)
        self.favorites_listbox.tag_configure("selected", background="#0078d4", foreground="white")

        # Update Canvas backgrounds to match selection state
        self._update_canvas_backgrounds()

        self.favorites_listbox.configure(state=tk.DISABLED)

    def watch_favorite(self):
        """Watch selected favorite channel"""
        if not self.selected_favorite_line:
            self.status_manager.add_warning("Please select a favorite channel", StatusCategory.FAVORITES)
            return

        # Extract channel name from formatted display text in the selected line
        line_start = f"{self.selected_favorite_line}.0"
        line_end = f"{self.selected_favorite_line}.end"
        display_text = self.favorites_listbox.get(line_start, line_end).strip()

        if not display_text:
            self.status_manager.add_warning("No channel selected", StatusCategory.FAVORITES)
            return

        channel = self._extract_channel_name(display_text)
        self.channel_var.set(channel)
        self.watch_stream()

    def _extract_channel_name(self, display_text: str) -> str:
        """Extract channel name from formatted display text"""
        # Format is now: " channel_name" (Canvas circle + space + channel name)
        # The Canvas circle is embedded as a widget, so text starts with space
        return display_text.strip()

    def _add_channel_to_favorites(self, channel_name: str) -> None:
        """
        Helper method to add a channel to favorites with common validation and UI updates.

        Args:
            channel_name: Name of the channel to add to favorites
        """
        channel_name = channel_name.strip()
        if not channel_name:
            self.status_manager.add_error("Please enter a channel name", StatusCategory.FAVORITES)
            return

        # Validate channel name
        try:
            validated_channel = validate_channel_name(channel_name)
        except ValidationError as e:
            self.status_manager.add_error(str(e), StatusCategory.FAVORITES)
            return

        channel_name = validated_channel

        if self.favorites_manager.add_favorite(channel_name):
            # Add to status monitoring
            self.status_monitor.add_channel_to_monitoring(channel_name)
            self.refresh_favorites_list()
            self.status_manager.add_favorites_message(f"Added {channel_name} to favorites")
        else:
            self.status_manager.add_warning(f"{channel_name} is already in favorites", StatusCategory.FAVORITES)

    def add_favorite(self):
        """Add current channel to favorites"""
        channel = self.channel_var.get()
        self._add_channel_to_favorites(channel)

    def add_new_favorite(self):
        """Add a new favorite channel via dialog"""
        channel = simpledialog.askstring("Add Favorite", "Enter channel name:")
        if channel:
            self._add_channel_to_favorites(channel)

    def remove_favorite(self):
        """Remove selected favorite"""
        if not self.selected_favorite_line:
            self.status_manager.add_warning("Please select a favorite to remove", StatusCategory.FAVORITES)
            return

        # Extract channel name from formatted display text in the selected line
        line_start = f"{self.selected_favorite_line}.0"
        line_end = f"{self.selected_favorite_line}.end"
        display_text = self.favorites_listbox.get(line_start, line_end).strip()

        if not display_text:
            self.status_manager.add_warning("No channel selected", StatusCategory.FAVORITES)
            return

        channel = self._extract_channel_name(display_text)

        if messagebox.askyesno("Confirm", f"Remove {channel} from favorites?"):
            self.favorites_manager.remove_favorite(channel)
            # Remove from status monitoring
            self.status_monitor.remove_channel_from_monitoring(channel)
            self.refresh_favorites_list()
            self.status_manager.add_favorites_message(f"Removed {channel} from favorites")

    def stream_finished(self, message):
        """Handle stream finishing"""
        self._enable_watch_buttons()
        self.status_manager.add_stream_message(message, StatusLevel.INFO)

    def stream_error(self, message):
        """Handle stream error"""
        self._enable_watch_buttons()
        self.status_manager.add_stream_message(message, StatusLevel.ERROR)

    def refresh_status(self):
        """Manually refresh stream status"""
        self._start_refresh_spinner()
        self.status_manager.add_status_message("Refreshing stream status...")
        self.status_monitor.force_refresh()
        
        # Stop spinner after a short delay to show completion
        self.root.after(2000, self._stop_refresh_spinner)

    def _on_status_updated(self, updated_channels):
        """Callback for when stream status is updated"""
        # Schedule GUI update on main thread
        self.root.after(0, self.refresh_favorites_list)
        
        # Stop refresh spinner if it's running
        if hasattr(self, 'refresh_spinner_running') and self.refresh_spinner_running:
            self.root.after(0, self._stop_refresh_spinner)

        # Update status message
        if len(updated_channels) == 1:
            self.root.after(
                0,
                lambda: self.status_manager.add_status_message(
                    f"Status updated for {updated_channels[0]}"
                ),
            )
        else:
            self.root.after(
                0,
                lambda: self.status_manager.add_status_message(
                    f"Status updated for {len(updated_channels)} channels"
                ),
            )

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

    def _on_debug_toggle(self):
        """Handle debug mode checkbox toggle"""
        new_debug = self.debug_var.get()
        old_debug = self.config.get("debug", False)

        if old_debug != new_debug:
            # Update debug flag
            self.config.set("debug", new_debug)
            
            # Synchronize log_level setting to match debug state
            if new_debug:
                self.config.set("log_level", "DEBUG")
            else:
                self.config.set("log_level", "INFO")  # Reset to default
            
            self.config.save_settings()  # Persist debug and log_level settings to JSON file
            self._reconfigure_logging()

            if new_debug:
                self.status_manager.add_system_message(
                    "Debug mode enabled - verbose logging active"
                )
                logger.debug("Debug mode enabled via GUI checkbox")
            else:
                self.status_manager.add_system_message("Debug mode disabled")
                logger.info("Debug mode disabled via GUI checkbox")

    def _on_theme_toggle(self):
        """Handle dark mode checkbox toggle"""
        is_dark_mode = self.dark_mode_var.get()
        old_theme = self.current_theme_name
        new_theme_name = "dark" if is_dark_mode else "light"

        if old_theme != new_theme_name:
            # Update theme
            self.current_theme_name = new_theme_name
            self.current_theme = get_theme(new_theme_name)

            # Save preference to config
            self.config.set("current_theme", new_theme_name)
            self.config.save_settings()

            # Apply new theme with animation
            self.apply_theme_with_animation(duration_ms=300)

            # Refresh favorites list to update Canvas circles (after animation delay)
            self.root.after(200, self.refresh_favorites_list)

            self.status_manager.add_system_message(f"Switched to {new_theme_name} theme")
            logger.info(f"Theme changed via GUI checkbox: {old_theme} -> {new_theme_name}")

    def _reconfigure_logging(self):
        """Reconfigure logging based on current settings"""
        try:
            # Use centralized reconfiguration function
            # Logger reconfiguration happens globally - no need to reassign module logger
            reconfigure_logging_from_config(self.config)

            debug_enabled = self.config.get("debug", False)
            if debug_enabled:
                logger.debug("Logging reconfigured via GUI - debug mode enabled")
                logger.debug("Debug logs will be automatically saved to logs/twitch_ad_avoider.log")
            else:
                logger.info("Logging reconfigured via GUI - debug mode disabled")

        except Exception as e:
            print(f"Error reconfiguring logging: {e}")

    def on_closing(self):
        """Handle window closing with robust process termination."""
        # Stop status monitoring first
        self.status_monitor.stop_monitoring()

        # Check if a stream process is running
        if self.current_stream_process and self.current_stream_process.poll() is None:
            print("Closing active stream...")

            # 1. Ask it to terminate gracefully
            self.current_stream_process.terminate()

            try:
                # 2. Wait for a short period (e.g., 3 seconds) for it to comply
                self.current_stream_process.wait(timeout=3)
                print("Stream process terminated gracefully.")
            except subprocess.TimeoutExpired:
                # 3. If it doesn't close in time, force-kill it
                print("Process did not terminate in time, forcing shutdown...")
                self.current_stream_process.kill()
                print("Stream process killed.")

        # Finally, destroy the window
        self.root.destroy()


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
