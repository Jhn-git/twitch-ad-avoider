"""
Constants and default configuration values for TwitchAdAvoider
"""

from pathlib import Path

# Application metadata
APP_NAME = "TwitchAdAvoider"
APP_VERSION = "2.0.3"
APP_DESCRIPTION = "A Python implementation for watching Twitch streams while avoiding ads"

# Default configuration values
DEFAULT_SETTINGS = {
    "preferred_quality": "best",
    "player": "vlc",
    "cache_duration": 30,
    "debug": False,
    "log_to_file": True,
    "log_level": "DEBUG",
    "player_path": None,
    "player_args": "--network-caching=10000 --file-caching=10000 --live-caching=10000",
    # Clip settings
    "clip_enabled": True,  # Record stream for clipping (near-zero CPU/network overhead)
    "clip_directory": "clips",  # Where to save clips
    "ffmpeg_path": "",  # FFmpeg executable path (empty = auto-detect from PATH)
    # GUI theme settings
    "dark_mode": False,  # Enable dark theme
    # Window settings
    "window_width": 640,  # Main window width in pixels
    "window_height": 650,  # Main window height in pixels
    "window_maximized": False,  # Whether window is maximized
    # Network settings
    "network_timeout": 30,  # Network timeout in seconds (increased from 20s default)
    "connection_retry_attempts": 3,  # Number of retry attempts for failed connections
    "retry_delay": 5,  # Delay between retry attempts in seconds
    "enable_network_diagnostics": True,  # Enable network diagnostics on connection failure
    # Favorites settings
    "favorites_auto_refresh": True,  # Automatically refresh favorite channels status
    "favorites_refresh_interval": 300,  # Refresh interval in seconds (5 minutes)
    "favorites_check_timeout": 5,  # Timeout per channel check in seconds
}

# Stream quality options
QUALITY_OPTIONS = ["best", "worst", "720p", "480p", "360p", "160p"]

# Supported players and their executable names
SUPPORTED_PLAYERS = {
    "vlc": ["vlc", "vlc.exe"],
    "mpv": ["mpv", "mpv.exe", "mpv.com"],
    "mpc-hc": ["mpc-hc", "mpc-hc.exe", "mpc-hc64.exe"],
}

# Common player installation paths
COMMON_PLAYER_PATHS = {
    "vlc": [
        r"C:\Program Files\VideoLAN\VLC\vlc.exe",
        r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
        "/usr/bin/vlc",
        "/usr/local/bin/vlc",
    ],
    "mpv": [
        r"C:\ProgramData\chocolatey\lib\mpvio.install\tools\mpv.exe",
        "/usr/bin/mpv",
        "/usr/local/bin/mpv",
    ],
    "mpc-hc": [
        r"C:\Program Files\MPC-HC\mpc-hc64.exe",
        r"C:\Program Files (x86)\MPC-HC\mpc-hc.exe",
    ],
}

# File paths
CONFIG_DIR = Path("config")
CONFIG_FILE = CONFIG_DIR / "settings.json"
FAVORITES_FILE = CONFIG_DIR / "favorites.json"
LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "twitch_ad_avoider.log"
CLIPS_DIR = Path("clips")
TEMP_DIR = Path("temp")

# Twitch username validation regex
TWITCH_USERNAME_PATTERN = r"^[a-zA-Z0-9_]{4,25}$"

# Environment variable names for PowerShell integration
ENV_PLAYER_PATH = "TWITCH_PLAYER_PATH"
ENV_PLAYER_NAME = "TWITCH_PLAYER_NAME"

# Default network timeout values
MIN_NETWORK_TIMEOUT = 10
MAX_NETWORK_TIMEOUT = 120
MIN_RETRY_ATTEMPTS = 1
MAX_RETRY_ATTEMPTS = 10
MIN_RETRY_DELAY = 1
MAX_RETRY_DELAY = 30
# Startup optimization constants
MIN_STARTUP_DELAY = 0
MAX_STARTUP_DELAY = 30

# Window size validation constants
MIN_WINDOW_WIDTH = 300
MAX_WINDOW_WIDTH = 1920
MIN_WINDOW_HEIGHT = 200
MAX_WINDOW_HEIGHT = 1080

# Favorites refresh validation constants
MIN_REFRESH_INTERVAL = 30  # Minimum 30 seconds
MAX_REFRESH_INTERVAL = 3600  # Maximum 1 hour
MIN_CHECK_TIMEOUT = 3  # Minimum 3 seconds per channel
MAX_CHECK_TIMEOUT = 10  # Maximum 10 seconds per channel
