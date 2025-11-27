"""
Main module for TwitchViewer functionality.

This module provides the core streaming functionality for TwitchAdAvoider, including:
    - Stream detection and quality selection
    - Video player auto-detection and management  
    - Process control and monitoring
    - Integration with streamlink for ad avoidance

The :class:`TwitchViewer` class serves as the primary interface for stream operations,
coordinating between configuration management, input validation, and external processes.

See Also:
    :mod:`src.config_manager`: Configuration and settings management
    :mod:`src.validators`: Input validation and security functions
    :mod:`gui_qt.stream_gui`: Qt graphical user interface integration
"""

import json
import os
import re
import subprocess
import time
import uuid
from pathlib import Path
from typing import Optional, Dict, List, Any
import streamlink
import shutil

from .exceptions import TwitchStreamError, PlayerError, ValidationError, StreamlinkError
from .config_manager import ConfigManager
from .logging_config import get_logger
from .validators import validate_channel_name
from .constants import (
    SUPPORTED_PLAYERS,
    COMMON_PLAYER_PATHS,
    TWITCH_USERNAME_PATTERN,
    ENV_PLAYER_PATH,
    ENV_PLAYER_NAME,
    ERROR_MESSAGES,
)

logger = get_logger(__name__)


class TwitchViewer:
    """
    Main class for watching Twitch streams with ad avoidance.
    
    This class provides the core functionality for stream detection, player management,
    and process control. It integrates with streamlink for ad-free streaming and 
    supports multiple video players with automatic detection.
    
    The class handles the complete streaming workflow:
        1. Input validation via :mod:`src.validators`
        2. Stream detection and quality selection
        3. Player detection and configuration
        4. Process launching and monitoring
    
    Attributes:
        config (:class:`~src.config_manager.ConfigManager`): Configuration manager instance
        player_path (Optional[str]): Path to detected video player executable
        selected_player (Optional[str]): Name of currently selected player
        session (streamlink.Streamlink): Streamlink session for stream operations
    
    Example:
        >>> from src.config_manager import ConfigManager
        >>> config = ConfigManager()
        >>> viewer = TwitchViewer(config)
        >>> viewer.watch_stream("ninja", "720p")
        
    See Also:
        :class:`~src.config_manager.ConfigManager`: Configuration management
        :func:`~src.validators.validate_channel_name`: Channel name validation
        :class:`~gui_qt.stream_gui.StreamGUI`: Qt GUI integration
    """

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """
        Initialize the TwitchViewer with configuration and streamlink session.

        Args:
            config_manager (Optional[ConfigManager]): Configuration manager instance.
                If None, a new ConfigManager will be created with default settings.
                
        Note:
            The streamlink session is configured with timeout settings from the
            configuration manager's network_timeout setting.
        """
        self.config = config_manager or ConfigManager()
        self.player_path: Optional[str] = None
        self.selected_player: Optional[str] = None
        self.session = streamlink.Streamlink()

        # Configure session timeouts
        timeout = self.config.get("network_timeout", 30)
        self.session.set_option("http-timeout", timeout)
        logger.debug(f"TwitchViewer streamlink session configured with {timeout}s timeout")

        # Check streamlink availability on startup
        if not self._check_streamlink_availability():
            logger.warning("Streamlink availability check failed")

        logger.info("TwitchViewer initialized")

    def set_player_choice(self, player_name: str) -> None:
        """
        Set the player choice from GUI selection.

        Args:
            player_name: Name of the player selected in GUI ('vlc', 'mpv', 'mpc-hc', 'auto')
        """
        self.selected_player = player_name
        # Reset player path when player choice changes to force re-detection
        self.player_path = None
        logger.debug(f"Player choice set to: {player_name}")

    def _get_streamlink_executable(self) -> str:
        """
        Get the streamlink executable path, preferring the virtual environment version.
        
        Returns:
            Path to streamlink executable
        """
        # First, try to find streamlink in the current virtual environment
        import sys
        import platform
        
        if hasattr(sys, 'prefix') and sys.prefix != sys.base_prefix:
            # We are in a virtual environment
            if platform.system() == "Windows":
                venv_streamlink = Path(sys.prefix) / "Scripts" / "streamlink.exe"
            else:
                venv_streamlink = Path(sys.prefix) / "bin" / "streamlink"
                
            if venv_streamlink.exists():
                logger.debug(f"Using virtual environment streamlink: {venv_streamlink}")
                return str(venv_streamlink)
        
        # Fallback to system streamlink
        return "streamlink"

    def _check_streamlink_availability(self) -> bool:
        """
        Check if streamlink is available and working

        Returns:
            True if streamlink is functional, False otherwise
        """
        try:
            # Try to create a session and check a non-existent stream
            test_channel = f"twitch.tv/test_{uuid.uuid4().hex[:12]}"
            test_streams = self.session.streams(test_channel)
            # If we get here without exception, streamlink is working
            logger.debug("Streamlink availability check passed")
            return True
        except Exception as e:
            logger.error(f"Streamlink availability check failed: {e}")
            return False

    def is_streamlink_available(self) -> bool:
        """
        Public method to check streamlink availability

        Returns:
            True if streamlink is available, False otherwise
        """
        return self._check_streamlink_availability()

    def _validate_channel(self, channel_name: str) -> str:
        """
        Validate the Twitch channel name using enhanced security controls.
        Args:
            channel_name (str): Name of the channel to validate
        Returns:
            str: Validated channel name
        Raises:
            ValidationError: If channel name is invalid
        """
        return validate_channel_name(channel_name)

    def _get_supported_players(self) -> Dict[str, List[str]]:
        """
        Get supported player configurations.

        Returns:
            Dict[str, List[str]]: Dictionary mapping player names to their executable names
        """
        return SUPPORTED_PLAYERS

    def _get_common_player_paths(self) -> Dict[str, List[str]]:
        """
        Get common installation paths for players.

        Returns:
            Dict[str, List[str]]: Dictionary mapping player names to their common installation paths
        """
        return COMMON_PLAYER_PATHS

    def _check_environment_player(self, debug: bool = False) -> Optional[str]:
        """
        Check for player from environment variables (PowerShell integration).

        Args:
            debug: Enable debug logging

        Returns:
            Optional[str]: Player name if found via environment variables, None otherwise
        """
        exported_player_path = os.environ.get(ENV_PLAYER_PATH)
        exported_player_name = os.environ.get(ENV_PLAYER_NAME)

        if exported_player_path and os.path.exists(exported_player_path):
            if debug:
                logger.debug(
                    f"Found exported player: {exported_player_name} at {exported_player_path}"
                )
            self.player_path = exported_player_path
            return exported_player_name.lower() if exported_player_name else "unknown"
        return None

    def _check_manual_player(self, debug: bool = False) -> Optional[str]:
        """
        Check for manually configured player path.

        Args:
            debug: Enable debug logging

        Returns:
            Optional[str]: Player name if manually configured path exists, None otherwise
        """
        manual_player_path = self.config.get("player_path")
        if manual_player_path and os.path.exists(manual_player_path):
            if debug:
                logger.debug(f"Using manual player path: {manual_player_path}")
            self.player_path = manual_player_path
            return self.config.get("player", "manual")
        return None

    def _check_player_in_path(
        self, player_name: str, executables: List[str], debug: bool = False
    ) -> Optional[str]:
        """
        Check if player is available in system PATH.

        Args:
            player_name: Name of the player to check
            executables: List of executable names to search for
            debug: Enable debug logging

        Returns:
            Optional[str]: Player name if found in PATH, None otherwise
        """
        for exe in executables:
            player_path = shutil.which(exe)
            if player_path:
                if debug:
                    logger.debug(f"Found {player_name} in PATH: {player_path}")
                self.player_path = player_path
                return player_name
        return None

    def _check_player_common_paths(
        self, player_name: str, paths: List[str], debug: bool = False
    ) -> Optional[str]:
        """
        Check player in common installation paths.

        Args:
            player_name: Name of the player to check
            paths: List of paths to check
            debug: Enable debug logging

        Returns:
            Optional[str]: Player name if found in common paths, None otherwise
        """
        for path in paths:
            if os.path.exists(path):
                if debug:
                    logger.debug(f"Found {player_name} at: {path}")
                self.player_path = path
                return player_name
        return None

    def _detect_player(self) -> str:
        """
        Detect available video player based on GUI selection and configuration.

        Uses a priority-based detection system:
        1. Manual player path from configuration
        2. Auto detection if selected
        3. Selected player search in PATH and common locations
        4. Environment variables (PowerShell integration)
        5. Fallback to streamlink auto-detection

        Returns:
            str: Name of the detected player or 'auto' for streamlink auto-detection
        """
        debug = self.config.get("debug", False)
        if debug:
            logger.debug("Starting player detection...")

        # Get player choice (GUI selection takes precedence)
        player_choice = self._get_player_choice(debug)

        # Try different detection methods in priority order
        if self._try_manual_player_detection(debug, player_choice):
            return player_choice

        if self._try_auto_detection(debug, player_choice):
            return "auto"

        if self._try_specific_player_detection(debug, player_choice):
            return player_choice

        if self._try_environment_player_detection(debug):
            return self._check_environment_player(debug)

        # Final fallback
        return self._fallback_to_streamlink_detection(debug, player_choice)

    def _get_player_choice(self, debug: bool) -> str:
        """Get the preferred player choice from GUI or configuration."""
        player_choice = self.selected_player or self.config.get("player", "vlc")
        if debug:
            logger.debug(f"Player choice: {player_choice}")
        return player_choice

    def _try_manual_player_detection(self, debug: bool, player_choice: str) -> bool:
        """Try to use manually configured player path."""
        manual_result = self._check_manual_player(debug)
        return manual_result is not None

    def _try_auto_detection(self, debug: bool, player_choice: str) -> bool:
        """Try auto detection if selected."""
        if player_choice == "auto":
            if debug:
                logger.debug("Using streamlink auto-detection")
            self.player_path = None
            return True
        return False

    def _try_specific_player_detection(self, debug: bool, player_choice: str) -> bool:
        """Try to detect a specific player using multiple methods."""
        players = self._get_supported_players()
        common_paths = self._get_common_player_paths()

        if player_choice not in players:
            return False

        # Search system PATH first
        if self._check_player_in_path(player_choice, players[player_choice], debug):
            return True

        # Search common installation directories
        if player_choice in common_paths:
            return self._check_player_common_paths(
                player_choice, common_paths[player_choice], debug
            ) is not None

        return False

    def _try_environment_player_detection(self, debug: bool) -> bool:
        """Try to detect player from environment variables."""
        return self._check_environment_player(debug) is not None

    def _fallback_to_streamlink_detection(self, debug: bool, player_choice: str) -> str:
        """Fallback to streamlink's built-in player detection."""
        if debug:
            logger.debug(f"Could not find {player_choice}, using streamlink auto-detection")
        self.player_path = None
        return "auto"

    def _get_stream(self, channel_name: str) -> str:
        """
        Get the stream URL for a channel.

        Args:
            channel_name: Name of the channel

        Returns:
            str: Stream URL for the specified quality

        Raises:
            TwitchStreamError: If no streams are available or streamlink fails
        """
        try:
            streams = self.session.streams(f"twitch.tv/{channel_name}")
            if not streams:
                raise TwitchStreamError(f"No streams available for channel: {channel_name}")

            quality = self.config.get("preferred_quality", "best")
            if quality not in streams:
                quality = "best"

            return streams[quality].url
        except streamlink.StreamlinkError as e:
            error_msg = str(e)
            # Check if this is a network/timeout error
            if any(
                keyword in error_msg.lower()
                for keyword in ["timeout", "connection", "unable to open"]
            ):
                logger.error(f"Network error getting stream for {channel_name}: {error_msg}")
                logger.info(f"Network timeout setting: {self.config.get('network_timeout', 30)}s")
                logger.info("Consider increasing network_timeout in settings if this persists")
            else:
                logger.error(f"Streamlink error getting stream for {channel_name}: {error_msg}")
            raise TwitchStreamError(f"Failed to get stream: {error_msg}")

    def watch_stream(self, channel_name: str) -> Optional[subprocess.Popen]:
        """
        Watch a Twitch stream for the specified channel.

        Args:
            channel_name: Name of the Twitch channel to watch

        Returns:
            Optional[subprocess.Popen]: The streamlink process if started successfully, None if error

        Raises:
            ValidationError: If channel name is invalid
            TwitchStreamError: If stream cannot be accessed
            FileNotFoundError: If streamlink is not installed
        """
        logger.info(f"Starting stream for channel: {channel_name}")
        logger.debug(
            f"Configuration: player={self.config.get('player')}, quality={self.config.get('preferred_quality')}, debug={self.config.get('debug')}"
        )

        try:
            # Validate channel name
            channel_name = self._validate_channel(channel_name)
            logger.debug(f"Channel name validated: {channel_name}")

            # Detect player if not already done
            if self.player_path is None:
                player_name = self._detect_player()
                if self.player_path:
                    logger.info(f"Using player: {player_name} ({self.player_path})")
                else:
                    logger.info(f"Using streamlink auto-detection for player: {player_name}")

            # Get stream quality
            quality = self.config.get("preferred_quality", "best")

            # Build streamlink command with proper executable path
            streamlink_exe = self._get_streamlink_executable()
            cmd = [streamlink_exe, f"twitch.tv/{channel_name}", quality]

            # Add player if we found one, otherwise let streamlink auto-detect
            if self.player_path:
                cmd.extend(["--player", self.player_path])

            # Add player arguments if specified
            player_args = self.config.get("player_args")
            if player_args:
                cmd.extend(["--player-args", player_args])

            # Add title if supported
            title = f"Twitch - {channel_name}"
            cmd.extend(["--title", title])

            logger.info(f"Starting stream for channel: {channel_name}")
            logger.info(f"Quality: {quality}")
            logger.debug(f"Command: {' '.join(cmd)}")

            # Start streamlink process (non-blocking)
            process = subprocess.Popen(cmd)
            return process

        except ValueError as e:
            logger.error(f"Validation error: {str(e)}")
            raise ValidationError(f"Invalid input: {str(e)}") from e
        except TwitchStreamError as e:
            logger.error(f"Stream error: {str(e)}")
            raise
        except FileNotFoundError:
            logger.error(
                "streamlink command not found. Please ensure streamlink is installed and in PATH."
            )
            raise StreamlinkError("streamlink command not found") from None
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            raise TwitchStreamError(f"Unexpected error: {str(e)}") from e
