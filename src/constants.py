"""
Constants and default configuration values for TwitchAdAvoider
"""

from pathlib import Path

# Application metadata
APP_NAME = "TwitchAdAvoider"
APP_VERSION = "2.0.13"
APP_DESCRIPTION = "A Python implementation for watching Twitch streams while avoiding ads"

# Default configuration values
DEFAULT_SETTINGS = {
    "preferred_quality": "best",
    # Use Twitch's LL-HLS mode (shorter segments, lower latency)
    "twitch_low_latency": True,
    # HLS segments buffered behind live; lower means less latency and more stutter risk.
    "hls_live_edge": 3,
    "debug": False,
    "log_to_file": True,
    "log_level": "INFO",
    # Clip settings
    "clip_enabled": True,  # Record stream for clipping (near-zero CPU/network overhead)
    "clip_directory": "clips",  # Where to save clips
    "ffmpeg_path": "",  # FFmpeg executable path (empty = auto-detect from PATH)
    # GUI theme settings
    "dark_mode": True,  # Enable dark theme
    # Window settings
    "window_width": 1440,  # Main window width in pixels
    "window_height": 850,  # Main window height in pixels
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
    "favorite_live_notifications_enabled": True,  # Show in-app live notifications
    "favorite_live_highlight_test_mode": False,  # Re-trigger recent-live highlight each refresh
    "favorite_live_notification_sound_enabled": True,  # Play sound for live notifications
    "button_hover_sound_enabled": True,  # Play subtle UI hover sounds
    "show_stream_preview": True,  # Show live thumbnail + title when selecting a favorite
    # Stream Manager screen settings
    "stream_manager_left_sidebar_open": True,  # Favorites rail expanded/collapsed
    "stream_manager_right_sidebar_open": True,  # Options rail expanded/collapsed
    "stream_manager_activity_drawer_open": False,  # Activity drawer expanded/collapsed
    "stream_manager_clip_duration_seconds": 30,  # Last-selected clip duration
}

# Stream quality options
QUALITY_OPTIONS = ["best", "worst", "720p", "480p", "360p", "160p"]

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

# Default network timeout values
MIN_NETWORK_TIMEOUT = 10
MAX_NETWORK_TIMEOUT = 120
MIN_RETRY_ATTEMPTS = 1
MAX_RETRY_ATTEMPTS = 10
MIN_RETRY_DELAY = 1
MAX_RETRY_DELAY = 30
MIN_HLS_LIVE_EDGE = 1
MAX_HLS_LIVE_EDGE = 10
# Startup optimization constants
MIN_STARTUP_DELAY = 0
MAX_STARTUP_DELAY = 30

# Window size validation constants
MIN_WINDOW_WIDTH = 300
MAX_WINDOW_WIDTH = 7680
MIN_WINDOW_HEIGHT = 200
MAX_WINDOW_HEIGHT = 4320

# Favorites refresh validation constants
MIN_REFRESH_INTERVAL = 30  # Minimum 30 seconds
MAX_REFRESH_INTERVAL = 3600  # Maximum 1 hour
MIN_CHECK_TIMEOUT = 3  # Minimum 3 seconds per channel
MAX_CHECK_TIMEOUT = 10  # Maximum 10 seconds per channel
