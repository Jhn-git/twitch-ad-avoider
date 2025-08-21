"""
Constants and default configuration values for TwitchAdAvoider
"""
from pathlib import Path
from typing import Dict, List, Any

# Application metadata
APP_NAME = "TwitchAdAvoider"
APP_VERSION = "2.0.0"
APP_DESCRIPTION = "A Python implementation for watching Twitch streams while avoiding ads"

# Default configuration values
DEFAULT_SETTINGS = {
    "preferred_quality": "best",
    "player": "vlc",
    "cache_duration": 30,
    "debug": False,
    "log_to_file": False,
    "log_level": "INFO",
    "player_path": None,
    "player_args": None,
    # Stream status monitoring settings
    "enable_status_monitoring": True,
    "status_check_interval": 300,  # 5 minutes in seconds
    "status_cache_duration": 60  # 1 minute in seconds
}

# Stream quality options
QUALITY_OPTIONS = ["best", "worst", "720p", "480p", "360p", "160p"]

# Supported players and their executable names
SUPPORTED_PLAYERS = {
    'vlc': ['vlc', 'vlc.exe'],
    'mpv': ['mpv', 'mpv.exe', 'mpv.com'],
    'mpc-hc': ['mpc-hc', 'mpc-hc.exe', 'mpc-hc64.exe']
}

# Common player installation paths
COMMON_PLAYER_PATHS = {
    'vlc': [
        r"C:\Program Files\VideoLAN\VLC\vlc.exe",
        r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
        "/usr/bin/vlc",
        "/usr/local/bin/vlc"
    ],
    'mpv': [
        r"C:\ProgramData\chocolatey\lib\mpvio.install\tools\mpv.exe",
        "/usr/bin/mpv",
        "/usr/local/bin/mpv"
    ],
    'mpc-hc': [
        r"C:\Program Files\MPC-HC\mpc-hc64.exe",
        r"C:\Program Files (x86)\MPC-HC\mpc-hc.exe"
    ]
}

# File paths
CONFIG_DIR = Path("config")
CONFIG_FILE = CONFIG_DIR / "settings.json"
FAVORITES_FILE = CONFIG_DIR / "favorites.json"
LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "twitch_ad_avoider.log"

# GUI settings
GUI_TITLE = f"{APP_NAME} - Stream Manager"
GUI_GEOMETRY = "400x500"
GUI_MIN_SIZE = (350, 400)

# Twitch username validation regex
TWITCH_USERNAME_PATTERN = r'^[a-zA-Z0-9_]{4,25}$'

# Environment variable names for PowerShell integration
ENV_PLAYER_PATH = 'TWITCH_PLAYER_PATH'
ENV_PLAYER_NAME = 'TWITCH_PLAYER_NAME'

# Error messages
ERROR_MESSAGES = {
    "empty_channel": "Channel name cannot be empty",
    "invalid_channel": "Invalid channel name format",
    "no_streams": "No streams available for channel: {}",
    "streamlink_error": "Failed to get stream: {}",
    "player_not_found": "Video player not found. Please install VLC, MPV, or MPC-HC",
    "streamlink_not_found": "streamlink command not found. Please ensure streamlink is installed and in PATH"
}

# Enhanced validation error messages
VALIDATION_ERROR_MESSAGES = {
    "channel_too_short": "Channel name must be at least 4 characters long",
    "channel_too_long": "Channel name cannot exceed 25 characters",
    "channel_invalid_chars": "Channel name can only contain letters, numbers, and underscores",
    "channel_security_violation": "Channel name contains forbidden characters or patterns",
    "player_args_injection": "Player arguments contain potentially dangerous content",
    "player_args_malformed": "Player arguments have invalid format or unbalanced quotes",
    "player_args_too_long": "Player arguments are too long (max 500 characters)",
    "file_path_traversal": "File path contains path traversal sequences (..)",
    "file_path_invalid_chars": "File path contains forbidden characters",
    "file_path_too_long": "File path is too long (max 1000 characters)",
    "file_not_exists": "File does not exist: {}",
    "numeric_below_min": "Value {} is below minimum {}",
    "numeric_above_max": "Value {} is above maximum {}",
    "invalid_type": "Invalid {} value: {}",
    "config_validation_failed": "Configuration validation failed: {}",
    "string_too_long": "Input too long (max {} characters)",
    "string_empty_not_allowed": "Input cannot be empty"
}