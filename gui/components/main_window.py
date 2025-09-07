"""
Main window component for TwitchAdAvoider GUI.

This module provides the primary window management and layout coordination,
extracted from the monolithic StreamGUI class to improve maintainability.

The :class:`MainWindow` handles:
    - Window initialization and configuration
    - Main layout structure and grid management
    - Component coordination and integration
    - Window lifecycle management (closing, cleanup)

Key Features:
    - Centralized window configuration
    - Modular component integration
    - Proper cleanup on window close
    - Theme-aware layout management
"""

import tkinter as tk
from tkinter import ttk
import subprocess
from typing import Optional, Dict, Any, List, Callable

from src.config_manager import ConfigManager
from src.logging_config import get_logger

logger = get_logger(__name__)

# GUI Configuration Constants
GUI_GEOMETRY = "640x650"
GUI_MIN_SIZE = (580, 550)


class MainWindow:
    """
    Main application window manager for TwitchAdAvoider GUI.
    
    This component handles the primary window setup, layout management,
    and coordinates integration between various GUI components.
    """

    def __init__(self, root: tk.Tk, config: ConfigManager):
        """
        Initialize the MainWindow.

        Args:
            root: The main tkinter window
            config: Configuration manager instance
        """
        self.root = root
        self.config = config
        
        # Component references (set by parent)
        self.components: List[Any] = []
        
        # Process tracking for cleanup
        self.current_stream_process: Optional[subprocess.Popen] = None
        
        # Window close callbacks
        self.on_closing_callbacks: List[Callable[[], None]] = []
        
        # Initialize window
        self._setup_window()
        
        # Create main layout structure
        self.main_frame = self._create_main_layout()

    def _setup_window(self) -> None:
        """Configure the main window properties"""
        self.root.title("TwitchAdAvoider - Stream Manager")
        
        # Load saved window size from config or use defaults
        width = self.config.get("window_width", 640)
        height = self.config.get("window_height", 650)
        is_maximized = self.config.get("window_maximized", False)
        
        # Set window geometry
        self.root.geometry(f"{width}x{height}")
        self.root.resizable(True, True)
        self.root.minsize(*GUI_MIN_SIZE)
        self.root.maxsize(1200, 900)  # Set reasonable maximum size
        
        # Apply maximized state if saved
        if is_maximized:
            self.root.state('zoomed')  # Windows/Linux
        
        # Bind window resize event to save size
        self.root.bind('<Configure>', self._on_window_configure)
        
        # Handle window closing
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _create_main_layout(self) -> ttk.Frame:
        """
        Create the main layout structure.
        
        Returns:
            Main container frame for components
        """
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure root grid weights for resizing
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        return main_frame

    def configure_main_layout(self, 
                            stream_input_row: int = 0,
                            favorites_row: int = 1, 
                            settings_row: int = 2,
                            status_row: int = 3) -> None:
        """
        Configure the main grid layout for components.
        
        Args:
            stream_input_row: Row for stream input section
            favorites_row: Row for favorites section
            settings_row: Row for settings section
            status_row: Row for status section
        """
        # Configure column weights for responsive layout
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=1)
        
        # Configure row weights
        self.main_frame.rowconfigure(favorites_row, weight=1)  # Favorites section expands

    def register_component(self, component: Any) -> None:
        """
        Register a GUI component with the main window.
        
        Args:
            component: Component instance to register
        """
        self.components.append(component)

    def set_stream_process(self, process: Optional[subprocess.Popen]) -> None:
        """
        Set reference to current stream process for cleanup.
        
        Args:
            process: Current stream process or None
        """
        self.current_stream_process = process


    def add_closing_callback(self, callback: Callable[[], None]) -> None:
        """
        Add callback to be called when window is closing.
        
        Args:
            callback: Function to call on window close
        """
        self.on_closing_callbacks.append(callback)

    def _on_window_configure(self, event) -> None:
        """Handle window resize/move events"""
        # Only save size if the event is for the root window (not child widgets)
        if event.widget == self.root:
            # Use after_idle to debounce rapid resize events
            self.root.after_idle(self._save_window_state)

    def _save_window_state(self) -> None:
        """Save current window state to configuration"""
        try:
            # Get current window state
            is_maximized = self.root.state() == 'zoomed'
            
            # If not maximized, save current size
            if not is_maximized:
                width = self.root.winfo_width()
                height = self.root.winfo_height()
                
                # Validate dimensions before saving
                if width >= GUI_MIN_SIZE[0] and height >= GUI_MIN_SIZE[1]:
                    self.config.set("window_width", width)
                    self.config.set("window_height", height)
            
            # Always save maximized state
            self.config.set("window_maximized", is_maximized)
            
            # Save config to file
            self.config.save_settings()
            
        except Exception as e:
            logger.debug(f"Error saving window state: {e}")

    def on_closing(self) -> None:
        """Handle window closing with robust cleanup"""
        logger.info("Application closing - performing cleanup")
        
        # Save final window state
        self._save_window_state()
        
        # Call registered closing callbacks
        for callback in self.on_closing_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Error in closing callback: {e}")
        

        # Clean up stream processes
        self._cleanup_stream_process()
        
        # Notify components of shutdown
        for component in self.components:
            if hasattr(component, 'cleanup'):
                try:
                    component.cleanup()
                except Exception as e:
                    logger.error(f"Error cleaning up component {type(component).__name__}: {e}")

        # Finally, destroy the window
        logger.info("Closing application window")
        self.root.destroy()

    def _cleanup_stream_process(self) -> None:
        """Clean up any running stream processes"""
        if self.current_stream_process and self.current_stream_process.poll() is None:
            logger.info("Closing active stream process")
            
            try:
                # 1. Ask it to terminate gracefully
                self.current_stream_process.terminate()
                
                # 2. Wait for a short period (3 seconds) for it to comply
                self.current_stream_process.wait(timeout=3)
                logger.info("Stream process terminated gracefully")
                
            except subprocess.TimeoutExpired:
                # 3. If it doesn't close in time, force-kill it
                logger.warning("Stream process did not terminate in time, forcing shutdown")
                self.current_stream_process.kill()
                logger.info("Stream process killed")
                
            except Exception as e:
                logger.error(f"Error terminating stream process: {e}")

    def get_main_frame(self) -> ttk.Frame:
        """
        Get the main container frame for component placement.
        
        Returns:
            Main container frame
        """
        return self.main_frame

    def update_title(self, subtitle: Optional[str] = None) -> None:
        """
        Update the window title.
        
        Args:
            subtitle: Optional subtitle to append
        """
        base_title = "TwitchAdAvoider - Stream Manager"
        if subtitle:
            self.root.title(f"{base_title} - {subtitle}")
        else:
            self.root.title(base_title)

    def center_window(self) -> None:
        """Center the window on the screen"""
        self.root.update_idletasks()  # Ensure geometry is calculated
        
        # Get window size
        window_width = self.root.winfo_width()
        window_height = self.root.winfo_height()
        
        # Get screen size
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # Calculate center position
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")

    def flash_window(self) -> None:
        """Flash the window to get user attention (platform dependent)"""
        try:
            # Try to bring window to front
            self.root.lift()
            self.root.attributes('-topmost', True)
            self.root.after(100, lambda: self.root.attributes('-topmost', False))
        except Exception as e:
            logger.debug(f"Could not flash window: {e}")

    def minimize_to_tray(self) -> bool:
        """
        Minimize window to system tray if possible.
        
        Returns:
            True if minimized to tray, False if just minimized normally
        """
        # For now, just minimize normally
        # TODO: Implement proper system tray integration
        self.root.iconify()
        return False