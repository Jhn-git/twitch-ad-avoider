"""
Main module for TwitchViewer functionality
"""
import json
import os
import re
import subprocess
import time
from pathlib import Path
import streamlink
import shutil

class TwitchStreamError(Exception):
    """Custom exception for stream-related errors"""
    pass

class TwitchViewer:
    def __init__(self, config_path=None):
        self.config_path = config_path or Path("config/settings.json")
        self.settings = self._load_settings()
        self.player_path = None
        self.session = streamlink.Streamlink()
        
    def _load_settings(self):
        """Load settings from the config file"""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                return json.load(f)
        return {
            "preferred_quality": "best",
            "player": "mpv",
            "cache_duration": 30
        }

    def _validate_channel(self, channel_name):
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
            raise ValueError("Channel name cannot be empty")
        
        # Twitch usernames can only contain letters, numbers, and underscores
        if not re.match(r'^[a-zA-Z0-9_]{4,25}$', channel_name):
            raise ValueError("Invalid channel name format")
        
        return channel_name.lower()

    def _get_supported_players(self):
        """Get supported player configurations"""
        return {
            'vlc': ['vlc', 'vlc.exe'],
            'mpv': ['mpv', 'mpv.exe', 'mpv.com'],
            'mpc-hc': ['mpc-hc', 'mpc-hc.exe', 'mpc-hc64.exe']
        }
    
    def _get_common_player_paths(self):
        """Get common installation paths for players"""
        return {
            'vlc': [
                r"C:\Program Files\VideoLAN\VLC\vlc.exe",
                r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe"
            ],
            'mpv': [
                r"C:\ProgramData\chocolatey\lib\mpvio.install\tools\mpv.exe"
            ],
            'mpc-hc': [
                r"C:\Program Files\MPC-HC\mpc-hc64.exe",
                r"C:\Program Files (x86)\MPC-HC\mpc-hc.exe"
            ]
        }
    
    def _check_environment_player(self, debug=False):
        """Check for player from environment variables (PowerShell integration)"""
        exported_player_path = os.environ.get('TWITCH_PLAYER_PATH')
        exported_player_name = os.environ.get('TWITCH_PLAYER_NAME')
        
        if exported_player_path and os.path.exists(exported_player_path):
            if debug:
                print(f"DEBUG: Found exported player: {exported_player_name} at {exported_player_path}")
            self.player_path = exported_player_path
            return exported_player_name.lower() if exported_player_name else 'unknown'
        return None
    
    def _check_manual_player(self, debug=False):
        """Check for manually configured player path"""
        manual_player_path = self.settings.get('player_path')
        if manual_player_path and os.path.exists(manual_player_path):
            if debug:
                print(f"DEBUG: Using manual player path: {manual_player_path}")
            self.player_path = manual_player_path
            return self.settings.get('player', 'manual')
        return None
    
    def _check_player_in_path(self, player_name, executables, debug=False):
        """Check if player is available in system PATH"""
        for exe in executables:
            player_path = shutil.which(exe)
            if player_path:
                if debug:
                    print(f"DEBUG: Found {player_name} in PATH: {player_path}")
                self.player_path = player_path
                return player_name
        return None
    
    def _check_player_common_paths(self, player_name, paths, debug=False):
        """Check player in common installation paths"""
        for path in paths:
            if os.path.exists(path):
                if debug:
                    print(f"DEBUG: Found {player_name} at: {path}")
                self.player_path = path
                return player_name
        return None

    def _detect_player(self):
        """Detect available video player on the system"""
        debug = self.settings.get('debug', False)
        
        if debug:
            print("DEBUG: Starting player detection...")
        
        # Stage 1: Check environment variables (PowerShell integration)
        result = self._check_environment_player(debug)
        if result:
            return result
        
        # Stage 2: Check manual configuration
        result = self._check_manual_player(debug)
        if result:
            return result
        
        # Stage 3: Check PATH and common installations
        players = self._get_supported_players()
        common_paths = self._get_common_player_paths()
        
        # Check preferred player first
        preferred_player = self.settings.get('player', 'vlc')
        if preferred_player in players:
            # Try PATH first
            result = self._check_player_in_path(preferred_player, players[preferred_player], debug)
            if result:
                return result
            
            # Try common paths for preferred player
            if preferred_player in common_paths:
                result = self._check_player_common_paths(preferred_player, common_paths[preferred_player], debug)
                if result:
                    return result
        
        # Fall back to any available player (in priority order)
        for player_name in ['vlc', 'mpv', 'mpc-hc']:
            # Check PATH
            result = self._check_player_in_path(player_name, players[player_name], debug)
            if result:
                return result
            
            # Check common paths
            if player_name in common_paths:
                result = self._check_player_common_paths(player_name, common_paths[player_name], debug)
                if result:
                    return result
        
        # Final fallback: Let streamlink handle detection
        if debug:
            print("DEBUG: No players found, using streamlink auto-detection")
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
            
            quality = self.settings.get("preferred_quality", "best")
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
        try:
            # Validate channel name
            channel_name = self._validate_channel(channel_name)
            
            # Detect player if not already done
            if self.player_path is None:
                player_name = self._detect_player()
                if self.player_path:
                    print(f"Using player: {player_name} ({self.player_path})")
                else:
                    print(f"Using streamlink auto-detection for player: {player_name}")
            
            # Get stream quality
            quality = self.settings.get("preferred_quality", "best")
            
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
            player_args = self.settings.get('player_args')
            if player_args:
                cmd.extend(['--player-args', player_args])
            
            # Add title if supported
            title = f"Twitch - {channel_name}"
            cmd.extend(['--title', title])
            
            print(f"Starting stream for channel: {channel_name}")
            print(f"Quality: {quality}")
            print(f"Command: {' '.join(cmd)}")
            
            # Start streamlink process
            process = subprocess.run(cmd, capture_output=False)
            
            if process.returncode != 0:
                raise TwitchStreamError(f"Streamlink failed with return code {process.returncode}")
                
        except ValueError as e:
            print(f"Error: {str(e)}")
        except TwitchStreamError as e:
            print(f"Stream Error: {str(e)}")
        except FileNotFoundError:
            print("Error: streamlink command not found. Please ensure streamlink is installed and in PATH.")
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
