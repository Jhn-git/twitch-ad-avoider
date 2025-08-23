"""
Stream management controller for TwitchAdAvoider GUI.

This module provides centralized stream control functionality, extracted from the
monolithic StreamGUI class to improve maintainability and separation of concerns.

The :class:`StreamController` handles:
    - Stream launching and process management
    - Thread management for non-blocking operations  
    - Stream lifecycle (start, finish, error handling)
    - Integration with TwitchViewer core functionality

Key Features:
    - Thread-safe stream operations
    - Process lifecycle management
    - Error handling and reporting
    - Integration with status management
"""

import threading
import subprocess
from typing import Optional, Callable

from ..status_manager import StatusManager, StatusLevel, StatusCategory
from src.twitch_viewer import TwitchViewer
from src.exceptions import ValidationError
from src.validators import validate_channel_name
from src.config_manager import ConfigManager
from src.logging_config import get_logger

logger = get_logger(__name__)


class StreamController:
    """
    Manages stream operations and lifecycle for the GUI application.
    
    This controller extracts stream management logic from the main GUI class,
    providing a clean separation between UI presentation and stream business logic.
    """

    def __init__(self, viewer: TwitchViewer, config: ConfigManager, status_manager: StatusManager):
        """
        Initialize the StreamController.

        Args:
            viewer: Core TwitchViewer instance for stream operations
            config: Configuration manager for settings updates
            status_manager: Status manager for user feedback
        """
        self.viewer = viewer
        self.config = config
        self.status_manager = status_manager
        
        # Stream process tracking
        self.current_stream_process: Optional[subprocess.Popen] = None
        self.current_stream_thread: Optional[threading.Thread] = None
        
        # Callbacks for UI updates (set by GUI components)
        self.on_stream_started: Optional[Callable[[], None]] = None
        self.on_stream_finished: Optional[Callable[[str], None]] = None
        self.on_stream_error: Optional[Callable[[str], None]] = None

    def set_callbacks(self, 
                     on_started: Callable[[], None],
                     on_finished: Callable[[str], None], 
                     on_error: Callable[[str], None]) -> None:
        """
        Set callback functions for stream lifecycle events.
        
        Args:
            on_started: Called when stream starts (for UI updates)
            on_finished: Called when stream finishes successfully
            on_error: Called when stream encounters an error
        """
        self.on_stream_started = on_started
        self.on_stream_finished = on_finished
        self.on_stream_error = on_error

    def can_start_stream(self, channel: str) -> tuple[bool, Optional[str]]:
        """
        Check if a stream can be started.
        
        Args:
            channel: Channel name to validate
            
        Returns:
            Tuple of (can_start, error_message). If can_start is False,
            error_message contains the reason.
        """
        if not channel.strip():
            return False, "Please enter a channel name"
            
        # Validate channel name
        try:
            validate_channel_name(channel)
        except ValidationError as e:
            return False, str(e)
            
        # Check for concurrent streams
        if self.current_stream_process and self.current_stream_process.poll() is None:
            return False, "A stream is already running. Please close it first."
            
        return True, None

    def start_stream(self, channel: str, player: str, quality: str, debug: bool) -> bool:
        """
        Start watching a stream.
        
        Args:
            channel: Channel name to watch
            player: Player executable to use
            quality: Stream quality preference
            debug: Debug mode setting
            
        Returns:
            True if stream was started successfully, False otherwise
        """
        # Validate inputs
        can_start, error_msg = self.can_start_stream(channel)
        if not can_start:
            self.status_manager.add_error(error_msg, StatusCategory.STREAM)
            return False

        # Update configuration
        self._update_stream_config(player, quality, debug)

        # Set player choice in TwitchViewer (prioritizes GUI selection)
        self.viewer.set_player_choice(player)

        # Start stream in separate thread
        self.status_manager.add_stream_message(f"Starting stream for {channel}...")
        
        if self.on_stream_started:
            self.on_stream_started()

        self.current_stream_thread = threading.Thread(
            target=self._stream_worker, 
            args=(channel,), 
            daemon=True
        )
        self.current_stream_thread.start()
        
        return True

    def stop_stream(self) -> bool:
        """
        Stop the current stream if running.
        
        Returns:
            True if stream was stopped, False if no stream was running
        """
        if self.current_stream_process and self.current_stream_process.poll() is None:
            try:
                self.current_stream_process.terminate()
                self.current_stream_process = None
                self.status_manager.add_stream_message("Stream stopped by user")
                return True
            except Exception as e:
                logger.error(f"Error stopping stream: {e}")
                self.status_manager.add_error(f"Error stopping stream: {str(e)}", StatusCategory.STREAM)
                return False
        return False

    def is_stream_running(self) -> bool:
        """
        Check if a stream is currently running.
        
        Returns:
            True if stream is active, False otherwise
        """
        return (self.current_stream_process is not None and 
                self.current_stream_process.poll() is None)

    def _update_stream_config(self, player: str, quality: str, debug: bool) -> None:
        """
        Update configuration with stream parameters.
        
        Args:
            player: Player executable
            quality: Stream quality
            debug: Debug mode flag
        """
        self.config.set("player", player)
        self.config.set("preferred_quality", quality)
        
        # Handle debug mode changes with logging reconfiguration
        old_debug = self.config.get("debug", False)
        if old_debug != debug:
            self.config.set("debug", debug)
            self._reconfigure_logging()

    def _reconfigure_logging(self) -> None:
        """Reconfigure logging based on current debug settings"""
        try:
            from src.logging_config import reconfigure_logging_from_config
            reconfigure_logging_from_config(self.config)
        except Exception as e:
            logger.error(f"Failed to reconfigure logging: {e}")

    def _stream_worker(self, channel: str) -> None:
        """
        Worker thread function for stream operations.
        
        Args:
            channel: Channel name to watch
        """
        try:
            # Store the process object
            self.current_stream_process = self.viewer.watch_stream(channel)

            # Wait for the process to complete
            return_code = self.current_stream_process.wait()

            # Clean up
            self.current_stream_process = None

            # Handle completion
            if return_code == 0:
                if self.on_stream_finished:
                    self.on_stream_finished(f"Stream for {channel} ended")
            else:
                if self.on_stream_error:
                    self.on_stream_error(f"Streamlink exited with code {return_code}")

        except Exception as e:
            # Clean up process reference on error
            self.current_stream_process = None
            logger.error(f"Stream error for {channel}: {e}")
            
            if self.on_stream_error:
                self.on_stream_error(f"Error: {str(e)}")