"""
Main module for TwitchViewer functionality
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
    """Main class for watching Twitch streams with ad avoidance."""

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """
        Initialize the TwitchViewer.

        Args:
            config_manager: Configuration manager instance
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
            logger.debug("Starting simplified player detection...")

        # Priority 1: Determine player choice from GUI or configuration
        # The GUI selection (self.selected_player) takes precedence over config file
        # This allows users to override the saved preference temporarily
        player_choice = self.selected_player or self.config.get("player", "vlc")

        if debug:
            logger.debug(f"Player choice: {player_choice}")

        # Priority 2: Check for manual player path in settings
        # If user has specified an explicit path, use it without further detection
        # This path has already been validated for security during configuration
        manual_result = self._check_manual_player(debug)
        if manual_result:
            return player_choice

        # Priority 3: Handle 'auto' choice - delegate to streamlink
        # When 'auto' is selected, we don't set a specific player path
        # Streamlink will use its own detection algorithm to find available players
        if player_choice == "auto":
            if debug:
                logger.debug("Using streamlink auto-detection")
            self.player_path = None
            return "auto"

        # Priority 4: Search for the selected player using multiple detection methods
        # This implements a comprehensive search strategy to maximize player detection success
        players = self._get_supported_players()  # Get executable names for each player
        common_paths = self._get_common_player_paths()  # Get OS-specific installation paths

        if player_choice in players:
            # Sub-priority 4a: Search system PATH first
            # PATH search is fastest and most reliable for properly installed software
            # Uses shutil.which() which respects OS-specific executable extensions
            result = self._check_player_in_path(player_choice, players[player_choice], debug)
            if result:
                return result

            # Sub-priority 4b: Search common installation directories
            # Fallback for players installed in standard locations but not in PATH
            # Covers cases where installers don't modify PATH environment variable
            if player_choice in common_paths:
                result = self._check_player_common_paths(
                    player_choice, common_paths[player_choice], debug
                )
                if result:
                    return result

        # Priority 5: Check environment variables (PowerShell integration)
        # Allows PowerShell scripts to override player detection by setting
        # TWITCH_PLAYER_PATH and TWITCH_PLAYER_NAME environment variables
        # This provides a bridge for advanced users and automation scripts
        result = self._check_environment_player(debug)
        if result:
            return result

        # Final fallback: Delegate to streamlink's built-in detection
        # When all our detection methods fail, let streamlink try its own algorithms
        # Streamlink has its own player detection logic that may succeed where ours failed
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

            # Build streamlink command
            cmd = ["streamlink", f"twitch.tv/{channel_name}", quality]

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
