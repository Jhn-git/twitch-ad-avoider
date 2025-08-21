"""
Configuration management for TwitchAdAvoider
Handles loading, saving, and validation of application settings.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from .constants import (
    DEFAULT_SETTINGS,
    CONFIG_FILE,
    QUALITY_OPTIONS,
    SUPPORTED_PLAYERS,
    MIN_NETWORK_TIMEOUT,
    MAX_NETWORK_TIMEOUT,
    MIN_RETRY_ATTEMPTS,
    MAX_RETRY_ATTEMPTS,
    MIN_RETRY_DELAY,
    MAX_RETRY_DELAY,
    VALIDATION_ERROR_MESSAGES,
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

# Import theme validation from gui module (avoid circular import)
import sys
import os

gui_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "gui")
if gui_path not in sys.path:
    sys.path.insert(0, gui_path)
try:
    from themes import is_valid_theme
except ImportError:
    # Fallback if GUI module not available
    def is_valid_theme(theme: str) -> bool:
        return theme in ["light", "dark"]


from .exceptions import ValidationError

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
        self._settings = {}
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

        except (OSError, json.JSONEncodeError) as e:
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
            logger.warning(f"Failed to update settings due to validation errors")
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

            elif key == "status_check_interval":
                validate_numeric_range(value, min_val=10, max_val=86400, data_type=int)
                return True

            elif key == "status_cache_duration":
                validate_numeric_range(value, min_val=1, max_val=3600, data_type=int)
                return True

            elif key == "debug":
                if not isinstance(value, bool):
                    raise ValidationError("Debug setting must be a boolean")
                return True

            elif key == "log_to_file":
                if not isinstance(value, bool):
                    raise ValidationError("Log to file setting must be a boolean")
                return True

            elif key == "enable_status_monitoring":
                if not isinstance(value, bool):
                    raise ValidationError("Status monitoring setting must be a boolean")
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

            elif key == "current_theme":
                if not isinstance(value, str):
                    raise ValidationError("Theme setting must be a string")
                if not is_valid_theme(value):
                    raise ValidationError(f"Invalid theme '{value}'. Available themes: light, dark")
                return True

            elif key == "network_timeout":
                validate_numeric_range(
                    value, min_val=MIN_NETWORK_TIMEOUT, max_val=MAX_NETWORK_TIMEOUT, data_type=int
                )
                return True

            elif key == "connection_retry_attempts":
                validate_numeric_range(
                    value, min_val=MIN_RETRY_ATTEMPTS, max_val=MAX_RETRY_ATTEMPTS, data_type=int
                )
                return True

            elif key == "retry_delay":
                validate_numeric_range(
                    value, min_val=MIN_RETRY_DELAY, max_val=MAX_RETRY_DELAY, data_type=int
                )
                return True

            elif key == "enable_network_diagnostics":
                if not isinstance(value, bool):
                    raise ValidationError("Network diagnostics setting must be a boolean")
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
