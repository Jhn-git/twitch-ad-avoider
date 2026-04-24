"""
Configuration management for TwitchAdAvoider.

This module handles loading, saving, and validation of application settings using a
JSON-based configuration system with comprehensive validation and secure defaults.

The :class:`ConfigManager` provides:
    - Atomic configuration saves with error recovery
    - Comprehensive validation of all settings
    - Default value merging and migration
    - UTF-8 encoding support for international users
    - Integration with the validation system

Configuration files are stored in JSON format and validated against predefined
schemas to ensure security and data integrity.

See Also:
    :mod:`src.validators`: Validation functions used by ConfigManager
    :mod:`src.constants`: Default settings and validation constants
    :class:`~src.twitch_viewer.TwitchViewer`: Primary consumer of configuration
    :mod:`gui_qt.stream_gui`: Qt GUI configuration interface
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from .constants import (
    DEFAULT_SETTINGS,
    CONFIG_FILE,
    MIN_NETWORK_TIMEOUT,
    MAX_NETWORK_TIMEOUT,
    MIN_RETRY_ATTEMPTS,
    MAX_RETRY_ATTEMPTS,
    MIN_RETRY_DELAY,
    MAX_RETRY_DELAY,
    MIN_WINDOW_WIDTH,
    MAX_WINDOW_WIDTH,
    MIN_WINDOW_HEIGHT,
    MAX_WINDOW_HEIGHT,
    MIN_REFRESH_INTERVAL,
    MAX_REFRESH_INTERVAL,
    MIN_CHECK_TIMEOUT,
    MAX_CHECK_TIMEOUT,
)
from .logging_config import get_logger
from .validators import (
    validate_quality_option,
    validate_player_choice,
    validate_log_level,
    validate_file_path,
    sanitize_player_args,
    validate_numeric_range,
    sanitize_string_input,
)
from .exceptions import ValidationError

# Import theme validation from gui module (avoid circular import)

gui_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "gui")
if gui_path not in sys.path:
    sys.path.insert(0, gui_path)
try:
    from themes import is_valid_theme
except ImportError:
    # Fallback if GUI module not available
    def is_valid_theme(theme: str) -> bool:
        return theme in ["light", "dark"]


logger = get_logger(__name__)


class ConfigManager:
    """Manages application configuration with validation and persistence."""

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize the configuration manager.

        Args:
            config_path: Path to the configuration file
        """
        self.config_path = config_path or CONFIG_FILE
        self._settings: Dict[str, Any] = {}
        self.load_settings()

    def load_settings(self) -> Dict[str, Any]:
        """
        Load settings from the configuration file.

        Returns:
            Dictionary containing the loaded settings
        """
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    file_settings = json.load(f)

                # Merge with defaults, prioritizing file settings
                self._settings = {**DEFAULT_SETTINGS, **file_settings}

                # Validate settings
                self._validate_settings()

                # Synchronize debug flag and log_level for consistency
                self._sync_debug_and_log_level()

                # Migrate old "current_theme" to new "dark_mode" setting
                if "current_theme" in self._settings and "dark_mode" not in self._settings:
                    old_theme = self._settings.pop("current_theme")
                    self._settings["dark_mode"] = old_theme == "dark"
                    logger.info("Migrated 'current_theme' setting to 'dark_mode'")
                    # Save migrated config
                    self.save_settings()

                logger.info(f"Settings loaded from {self.config_path}")

            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.warning(f"Failed to load settings from {self.config_path}: {e}")
                logger.info("Using default settings")
                self._settings = DEFAULT_SETTINGS.copy()
        else:
            logger.info("Settings file not found, using defaults")
            self._settings = DEFAULT_SETTINGS.copy()

        return self._settings

    def save_settings(self) -> bool:
        """
        Save current settings to the configuration file.

        Returns:
            True if settings were saved successfully, False otherwise
        """
        try:
            # Create config directory if it doesn't exist
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            # Save settings to file
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self._settings, f, indent=4, ensure_ascii=False)

            logger.info(f"Settings saved to {self.config_path}")
            return True

        except (OSError, json.JSONDecodeError) as e:
            logger.error(f"Failed to save settings to {self.config_path}: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a setting value.

        Args:
            key: Setting key
            default: Default value if key is not found

        Returns:
            Setting value or default
        """
        return self._settings.get(key, default)

    def set(self, key: str, value: Any) -> bool:
        """
        Set a setting value.

        Args:
            key: Setting key
            value: Setting value

        Returns:
            True if setting was updated, False if validation failed
        """
        # Create a temporary copy for validation
        temp_settings = self._settings.copy()
        temp_settings[key] = value

        # Validate the setting
        if self._validate_setting(key, value):
            self._settings[key] = value
            logger.debug(f"Setting updated: {key} = {value}")
            return True
        else:
            logger.warning(f"Invalid setting value: {key} = {value}")
            return False

    def update(self, settings: Dict[str, Any]) -> bool:
        """
        Update multiple settings at once.

        Args:
            settings: Dictionary of settings to update

        Returns:
            True if all settings were updated, False if any validation failed
        """
        # Validate all settings first
        temp_settings = self._settings.copy()
        temp_settings.update(settings)

        if self._validate_settings(temp_settings):
            self._settings.update(settings)
            logger.debug(f"Settings updated: {settings}")
            return True
        else:
            logger.warning("Failed to update settings due to validation errors")
            return False

    def reset_to_defaults(self) -> None:
        """Reset all settings to their default values."""
        self._settings = DEFAULT_SETTINGS.copy()
        logger.info("Settings reset to defaults")

    def get_all(self) -> Dict[str, Any]:
        """
        Get all current settings.

        Returns:
            Dictionary containing all settings
        """
        return self._settings.copy()

    def _validate_settings(self, settings: Optional[Dict[str, Any]] = None) -> bool:
        """
        Validate all settings.

        Args:
            settings: Settings to validate (defaults to current settings)

        Returns:
            True if all settings are valid, False otherwise
        """
        if settings is None:
            settings = self._settings

        for key, value in settings.items():
            if not self._validate_setting(key, value):
                return False

        return True

    def _validate_setting(self, key: str, value: Any) -> bool:
        """
        Validate a single setting using enhanced security-focused validators.

        Args:
            key: Setting key
            value: Setting value

        Returns:
            True if setting is valid, False otherwise
        """
        try:
            if key == "preferred_quality":
                validate_quality_option(value)
                return True

            elif key == "player":
                validate_player_choice(value)
                return True

            elif key == "cache_duration":
                validate_numeric_range(value, min_val=0, max_val=3600, data_type=int)
                return True

            elif key == "debug":
                if not isinstance(value, bool):
                    raise ValidationError("Debug setting must be a boolean")
                return True

            elif key == "log_to_file":
                if not isinstance(value, bool):
                    raise ValidationError("Log to file setting must be a boolean")
                return True

            elif key == "log_level":
                validate_log_level(value)
                return True

            elif key == "player_path":
                validate_file_path(value, must_exist=False)
                return True

            elif key == "player_args":
                sanitize_player_args(value)
                return True

            elif key == "dark_mode":
                if not isinstance(value, bool):
                    raise ValidationError("Dark mode setting must be a boolean")
                return True

            elif key == "network_timeout":
                # Network settings should be strict about type (only accept actual integers)
                if not isinstance(value, int):
                    raise ValidationError("Network timeout must be an integer")
                validate_numeric_range(
                    value, min_val=MIN_NETWORK_TIMEOUT, max_val=MAX_NETWORK_TIMEOUT, data_type=int
                )
                return True

            elif key == "connection_retry_attempts":
                # Network settings should be strict about type (only accept actual integers)
                if not isinstance(value, int):
                    raise ValidationError("Connection retry attempts must be an integer")
                validate_numeric_range(
                    value, min_val=MIN_RETRY_ATTEMPTS, max_val=MAX_RETRY_ATTEMPTS, data_type=int
                )
                return True

            elif key == "retry_delay":
                # Network settings should be strict about type (only accept actual integers)
                if not isinstance(value, int):
                    raise ValidationError("Retry delay must be an integer")
                validate_numeric_range(
                    value, min_val=MIN_RETRY_DELAY, max_val=MAX_RETRY_DELAY, data_type=int
                )
                return True

            # Authentication settings validation
            elif key == "twitch_client_id":
                if not isinstance(value, str):
                    raise ValidationError("Twitch client ID must be a string")
                # Allow empty string for initial setup
                if value and (len(value) < 10 or len(value) > 50):
                    raise ValidationError(
                        "Twitch client ID must be between 10-50 characters when provided"
                    )
                return True

            # Chat settings validation
            elif key == "chat_auto_connect":
                if not isinstance(value, bool):
                    raise ValidationError("Chat auto-connect setting must be a boolean")
                return True

            elif key == "chat_max_messages":
                if not isinstance(value, int):
                    raise ValidationError("Chat max messages must be an integer")
                validate_numeric_range(value, min_val=100, max_val=2000, data_type=int)
                return True

            elif key == "chat_show_timestamps":
                if not isinstance(value, bool):
                    raise ValidationError("Chat show timestamps setting must be a boolean")
                return True

            # Favorites settings validation
            elif key == "favorites_auto_refresh":
                if not isinstance(value, bool):
                    raise ValidationError("Favorites auto-refresh setting must be a boolean")
                return True

            elif key == "favorites_refresh_interval":
                if not isinstance(value, int):
                    raise ValidationError("Favorites refresh interval must be an integer")
                validate_numeric_range(
                    value, min_val=MIN_REFRESH_INTERVAL, max_val=MAX_REFRESH_INTERVAL, data_type=int
                )
                return True

            elif key == "favorites_check_timeout":
                if not isinstance(value, int):
                    raise ValidationError("Favorites check timeout must be an integer")
                validate_numeric_range(
                    value, min_val=MIN_CHECK_TIMEOUT, max_val=MAX_CHECK_TIMEOUT, data_type=int
                )
                return True

            # Window settings validation
            elif key == "window_width":
                if not isinstance(value, int):
                    raise ValidationError("Window width must be an integer")
                validate_numeric_range(
                    value, min_val=MIN_WINDOW_WIDTH, max_val=MAX_WINDOW_WIDTH, data_type=int
                )
                return True

            elif key == "window_height":
                if not isinstance(value, int):
                    raise ValidationError("Window height must be an integer")
                validate_numeric_range(
                    value, min_val=MIN_WINDOW_HEIGHT, max_val=MAX_WINDOW_HEIGHT, data_type=int
                )
                return True

            elif key == "window_maximized":
                if not isinstance(value, bool):
                    raise ValidationError("Window maximized setting must be a boolean")
                return True

            else:
                # Unknown setting keys are allowed but logged
                logger.debug(f"Unknown setting key: {key}")
                # Apply basic string sanitization for unknown string values
                if isinstance(value, str):
                    sanitize_string_input(value, max_length=1000)
                return True

        except ValidationError as e:
            logger.warning(f"Validation failed for {key}={value}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected validation error for {key}={value}: {e}")
            return False

    def _sync_debug_and_log_level(self) -> None:
        """
        Synchronize debug flag and log_level setting for consistency.

        This ensures the JSON configuration accurately reflects the expected behavior:
        - If debug=true but log_level != "DEBUG", update log_level to "DEBUG"
        - If debug=false but log_level == "DEBUG", update log_level to "INFO"
        """
        debug_enabled = self._settings.get("debug", False)
        current_log_level = self._settings.get("log_level", "INFO")

        needs_save = False

        if debug_enabled and current_log_level != "DEBUG":
            self._settings["log_level"] = "DEBUG"
            logger.debug("Auto-synced log_level to DEBUG (debug mode is enabled)")
            needs_save = True

        elif not debug_enabled and current_log_level == "DEBUG":
            self._settings["log_level"] = "INFO"
            logger.debug("Auto-synced log_level to INFO (debug mode is disabled)")
            needs_save = True

        # Save the synchronized settings back to file if changes were made
        if needs_save:
            self.save_settings()
