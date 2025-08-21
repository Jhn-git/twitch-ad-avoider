"""
Main module for TwitchViewer functionality
"""
import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Optional, Dict, List, Any
import streamlink
import shutil

from .exceptions import TwitchStreamError, PlayerError, ValidationError, StreamlinkError
from .config_manager import ConfigManager
from .logging_config import get_logger
from .constants import (
    SUPPORTED_PLAYERS, COMMON_PLAYER_PATHS, TWITCH_USERNAME_PATTERN,
    ENV_PLAYER_PATH, ENV_PLAYER_NAME, ERROR_MESSAGES
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
            test_streams = self.session.streams("twitch.tv/nonexistentchannel123456")
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
        Validate the Twitch channel name
        Args:
            channel_name (str): Name of the channel to validate
        Returns:
            str: Validated channel name
        Raises:
            ValueError: If channel name is invalid
        """
        if not channel_name:
            raise ValidationError(ERROR_MESSAGES["empty_channel"])
        
        # Twitch usernames can only contain letters, numbers, and underscores
        if not re.match(TWITCH_USERNAME_PATTERN, channel_name):
            raise ValidationError(ERROR_MESSAGES["invalid_channel"])
        
        return channel_name.lower()

    def _get_supported_players(self) -> Dict[str, List[str]]:
        """Get supported player configurations"""
        return SUPPORTED_PLAYERS
    
    def _get_common_player_paths(self) -> Dict[str, List[str]]:
        """Get common installation paths for players"""
        return COMMON_PLAYER_PATHS
    
    def _check_environment_player(self, debug=False):
        """Check for player from environment variables (PowerShell integration)"""
        exported_player_path = os.environ.get(ENV_PLAYER_PATH)
        exported_player_name = os.environ.get(ENV_PLAYER_NAME)
        
        if exported_player_path and os.path.exists(exported_player_path):
            if debug:
                logger.debug(f"Found exported player: {exported_player_name} at {exported_player_path}")
            self.player_path = exported_player_path
            return exported_player_name.lower() if exported_player_name else 'unknown'
        return None
    
    def _check_manual_player(self, debug=False):
        """Check for manually configured player path"""
        manual_player_path = self.config.get('player_path')
        if manual_player_path and os.path.exists(manual_player_path):
            if debug:
                logger.debug(f"Using manual player path: {manual_player_path}")
            self.player_path = manual_player_path
            return self.config.get('player', 'manual')
        return None
    
    def _check_player_in_path(self, player_name, executables, debug=False):
        """Check if player is available in system PATH"""
        for exe in executables:
            player_path = shutil.which(exe)
            if player_path:
                if debug:
                    logger.debug(f"Found {player_name} in PATH: {player_path}")
                self.player_path = player_path
                return player_name
        return None
    
    def _check_player_common_paths(self, player_name, paths, debug=False):
        """Check player in common installation paths"""
        for path in paths:
            if os.path.exists(path):
                if debug:
                    logger.debug(f"Found {player_name} at: {path}")
                self.player_path = path
                return player_name
        return None

    def _detect_player(self):
        """Detect available video player based on GUI selection and configuration"""
        debug = self.config.get('debug', False)
        
        if debug:
            logger.debug("Starting simplified player detection...")
        
        # Priority 1: Use GUI selection if available
        player_choice = self.selected_player or self.config.get('player', 'vlc')
        
        if debug:
            logger.debug(f"Player choice: {player_choice}")
        
        # Priority 2: Check for manual player path in settings
        manual_player_path = self.config.get('player_path')
        if manual_player_path and os.path.exists(manual_player_path):
            if debug:
                logger.debug(f"Using manual player path: {manual_player_path}")
            self.player_path = manual_player_path
            return player_choice
        
        # Priority 3: Handle 'auto' choice - let streamlink decide
        if player_choice == 'auto':
            if debug:
                logger.debug("Using streamlink auto-detection")
            self.player_path = None
            return 'auto'
        
        # Priority 4: Try to find the selected player
        players = self._get_supported_players()
        common_paths = self._get_common_player_paths()
        
        if player_choice in players:
            # Try PATH first
            result = self._check_player_in_path(player_choice, players[player_choice], debug)
            if result:
                return result
            
            # Try common paths
            if player_choice in common_paths:
                result = self._check_player_common_paths(player_choice, common_paths[player_choice], debug)
                if result:
                    return result
        
        # Priority 5: Fall back to environment variables (PowerShell integration)
        result = self._check_environment_player(debug)
        if result:
            return result
        
        # Final fallback: Let streamlink handle detection
        if debug:
            logger.debug(f"Could not find {player_choice}, using streamlink auto-detection")
        self.player_path = None
        return 'auto'

    def _get_stream(self, channel_name):
        """
        Get the stream URL for a channel
        Args:
            channel_name (str): Name of the channel
        Returns:
            str: Stream URL
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
            raise TwitchStreamError(f"Failed to get stream: {str(e)}")

    def watch_stream(self, channel_name):
        """
        Watch a Twitch stream for the specified channel
        Args:
            channel_name (str): Name of the Twitch channel to watch
        """
        logger.info(f"Starting stream for channel: {channel_name}")
        logger.debug(f"Configuration: player={self.config.get('player')}, quality={self.config.get('preferred_quality')}, debug={self.config.get('debug')}")
        
        try:
            # Validate channel name
            channel_name = self._validate_channel(channel_name)
            logger.debug(f"Channel name validated: {channel_name}")
            
            # Detect player if not already done
            if self.player_path is None:
                player_name = self._detect_player()
                if self.player_path:
                    print(f"Using player: {player_name} ({self.player_path})")
                else:
                    print(f"Using streamlink auto-detection for player: {player_name}")
            
            # Get stream quality
            quality = self.config.get("preferred_quality", "best")
            
            # Build streamlink command
            cmd = [
                'streamlink',
                f'twitch.tv/{channel_name}',
                quality
            ]
            
            # Add player if we found one, otherwise let streamlink auto-detect
            if self.player_path:
                cmd.extend(['--player', self.player_path])
            
            # Add player arguments if specified
            player_args = self.config.get('player_args')
            if player_args:
                cmd.extend(['--player-args', player_args])
            
            # Add title if supported
            title = f"Twitch - {channel_name}"
            cmd.extend(['--title', title])
            
            print(f"Starting stream for channel: {channel_name}")
            print(f"Quality: {quality}")
            print(f"Command: {' '.join(cmd)}")
            
            # Start streamlink process (non-blocking)
            process = subprocess.Popen(cmd)
            return process
                
        except ValueError as e:
            print(f"Error: {str(e)}")
        except TwitchStreamError as e:
            print(f"Stream Error: {str(e)}")
        except FileNotFoundError:
            print("Error: streamlink command not found. Please ensure streamlink is installed and in PATH.")
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
