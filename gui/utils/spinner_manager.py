"""
Spinner animation manager for TwitchAdAvoider GUI.

This module provides centralized spinner animation functionality, 
consolidating duplicate spinner logic from the monolithic StreamGUI class.

The :class:`SpinnerManager` handles:
    - Spinner animation state management
    - Multiple concurrent spinners
    - Customizable spinner characters and timing
    - Widget text updating with spinner animations

Key Features:
    - Thread-safe spinner operations
    - Multiple spinner instances
    - Configurable animation speed and characters
    - Automatic cleanup and state management
"""

import tkinter as tk
from typing import Dict, Optional, Callable, Any
from threading import Lock

from src.logging_config import get_logger

logger = get_logger(__name__)


class SpinnerInstance:
    """Represents a single spinner animation instance"""
    
    def __init__(self, 
                 widget: Any,
                 message: str,
                 update_interval: int = 100,
                 spinner_chars: Optional[list] = None):
        """
        Initialize a spinner instance.
        
        Args:
            widget: Widget to update with spinner animation
            message: Base message to display with spinner
            update_interval: Animation frame interval in milliseconds
            spinner_chars: Custom spinner characters (optional)
        """
        self.widget = widget
        self.message = message
        self.update_interval = update_interval
        self.spinner_chars = spinner_chars or ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        
        self.is_running = False
        self.current_index = 0
        self.after_id: Optional[str] = None
        self.root_widget: Optional[tk.Tk] = None

    def start(self, root_widget: tk.Tk) -> None:
        """
        Start the spinner animation.
        
        Args:
            root_widget: Root widget for scheduling updates
        """
        if self.is_running:
            return
            
        self.is_running = True
        self.current_index = 0
        self.root_widget = root_widget
        self._update_frame()

    def stop(self, final_text: Optional[str] = None) -> None:
        """
        Stop the spinner animation.
        
        Args:
            final_text: Text to set on widget after stopping (optional)
        """
        self.is_running = False
        
        if self.after_id and self.root_widget:
            try:
                self.root_widget.after_cancel(self.after_id)
            except tk.TclError:
                pass  # Widget may have been destroyed
            self.after_id = None
        
        if final_text is not None:
            try:
                if hasattr(self.widget, 'config'):
                    self.widget.config(text=final_text)
            except tk.TclError:
                pass  # Widget may have been destroyed

    def _update_frame(self) -> None:
        """Update the spinner animation frame"""
        if not self.is_running:
            return
            
        try:
            spinner_char = self.spinner_chars[self.current_index]
            display_text = f"{spinner_char} {self.message}"
            
            if hasattr(self.widget, 'config'):
                self.widget.config(text=display_text)
            
            self.current_index = (self.current_index + 1) % len(self.spinner_chars)
            
            if self.root_widget and self.is_running:
                self.after_id = self.root_widget.after(
                    self.update_interval, 
                    self._update_frame
                )
                
        except tk.TclError:
            # Widget destroyed, stop spinner
            self.is_running = False


class SpinnerManager:
    """
    Manages multiple spinner animations for GUI widgets.
    
    This manager consolidates spinner logic and prevents duplicate
    implementations across the application.
    """

    def __init__(self, root_widget: tk.Tk):
        """
        Initialize the SpinnerManager.
        
        Args:
            root_widget: Root widget for scheduling updates
        """
        self.root_widget = root_widget
        self.spinners: Dict[str, SpinnerInstance] = {}
        self.lock = Lock()
        
        # Default spinner configuration
        self.default_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def start_spinner(self, 
                     spinner_id: str,
                     widget: Any,
                     message: str,
                     update_interval: int = 100,
                     spinner_chars: Optional[list] = None) -> bool:
        """
        Start a spinner animation.
        
        Args:
            spinner_id: Unique identifier for this spinner
            widget: Widget to animate
            message: Message to display with spinner
            update_interval: Animation speed in milliseconds
            spinner_chars: Custom spinner characters (optional)
            
        Returns:
            True if spinner was started, False if already running
        """
        with self.lock:
            if spinner_id in self.spinners and self.spinners[spinner_id].is_running:
                logger.debug(f"Spinner '{spinner_id}' already running")
                return False
            
            # Create and start spinner instance
            spinner = SpinnerInstance(
                widget=widget,
                message=message,
                update_interval=update_interval,
                spinner_chars=spinner_chars or self.default_chars
            )
            
            self.spinners[spinner_id] = spinner
            spinner.start(self.root_widget)
            
            logger.debug(f"Started spinner '{spinner_id}' with message: {message}")
            return True

    def stop_spinner(self, spinner_id: str, final_text: Optional[str] = None) -> bool:
        """
        Stop a spinner animation.
        
        Args:
            spinner_id: Spinner identifier to stop
            final_text: Text to set on widget after stopping
            
        Returns:
            True if spinner was stopped, False if not found or not running
        """
        with self.lock:
            if spinner_id not in self.spinners:
                logger.debug(f"Spinner '{spinner_id}' not found")
                return False
            
            spinner = self.spinners[spinner_id]
            if not spinner.is_running:
                logger.debug(f"Spinner '{spinner_id}' not running")
                return False
            
            spinner.stop(final_text)
            logger.debug(f"Stopped spinner '{spinner_id}'")
            return True

    def is_spinner_running(self, spinner_id: str) -> bool:
        """
        Check if a spinner is currently running.
        
        Args:
            spinner_id: Spinner identifier to check
            
        Returns:
            True if spinner is running, False otherwise
        """
        with self.lock:
            if spinner_id in self.spinners:
                return self.spinners[spinner_id].is_running
            return False

    def stop_all_spinners(self) -> int:
        """
        Stop all running spinners.
        
        Returns:
            Number of spinners that were stopped
        """
        stopped_count = 0
        
        with self.lock:
            for spinner_id, spinner in self.spinners.items():
                if spinner.is_running:
                    spinner.stop()
                    stopped_count += 1
        
        logger.debug(f"Stopped {stopped_count} spinners")
        return stopped_count

    def update_spinner_message(self, spinner_id: str, new_message: str) -> bool:
        """
        Update the message of a running spinner.
        
        Args:
            spinner_id: Spinner identifier
            new_message: New message to display
            
        Returns:
            True if message was updated, False if spinner not found
        """
        with self.lock:
            if spinner_id in self.spinners:
                self.spinners[spinner_id].message = new_message
                return True
            return False

    def get_active_spinners(self) -> list:
        """
        Get list of currently active spinner IDs.
        
        Returns:
            List of active spinner identifiers
        """
        with self.lock:
            return [
                spinner_id for spinner_id, spinner in self.spinners.items()
                if spinner.is_running
            ]

    def cleanup(self) -> None:
        """Clean up all spinners and resources"""
        logger.debug("Cleaning up spinner manager")
        self.stop_all_spinners()
        
        with self.lock:
            self.spinners.clear()


# Convenience functions for common spinner patterns
def create_watch_button_spinner(root: tk.Tk, watch_button: Any) -> SpinnerManager:
    """
    Create a spinner manager configured for watch button animations.
    
    Args:
        root: Root widget
        watch_button: Watch button widget
        
    Returns:
        Configured SpinnerManager instance
    """
    manager = SpinnerManager(root)
    
    # Pre-configure common spinner
    def start_watch_spinner(message: str = "Starting stream..."):
        return manager.start_spinner("watch_button", watch_button, message, 100)
    
    def stop_watch_spinner(final_text: str = "Watch Stream"):
        return manager.stop_spinner("watch_button", final_text)
    
    # Add convenience methods
    manager.start_watch_spinner = start_watch_spinner
    manager.stop_watch_spinner = stop_watch_spinner
    
    return manager

def create_refresh_button_spinner(root: tk.Tk, refresh_button: Any) -> SpinnerManager:
    """
    Create a spinner manager configured for refresh button animations.
    
    Args:
        root: Root widget  
        refresh_button: Refresh button widget
        
    Returns:
        Configured SpinnerManager instance
    """
    manager = SpinnerManager(root)
    
    def start_refresh_spinner(message: str = "Refreshing..."):
        return manager.start_spinner("refresh_button", refresh_button, message, 150)
    
    def stop_refresh_spinner(final_text: str = "🔄 Refresh"):
        return manager.stop_spinner("refresh_button", final_text)
    
    manager.start_refresh_spinner = start_refresh_spinner
    manager.stop_refresh_spinner = stop_refresh_spinner
    
    return manager