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
    :class:`~src.web_stream_service.WebStreamService`: Primary stream consumer
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, List
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
    MIN_HLS_LIVE_EDGE,
    MAX_HLS_LIVE_EDGE,
)
from .logging_config import get_logger
from .validators import (
    validate_quality_option,
    validate_log_level,
    validate_file_path,
    validate_numeric_range,
)
from .exceptions import ValidationError

logger = get_logger(__name__)


_LEGACY_LOAD_ONLY_SETTINGS = {
    "cache_duration",
    "current_theme",
    "enable_status_monitoring",
    "player",
    "player_args",
    "player_path",
    "status_check_interval",
    "status_cache_duration",
}
_KNOWN_SETTINGS = set(DEFAULT_SETTINGS)


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
        self._validators = self._setting_validators()
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

                file_settings = self._migrate_loaded_settings(file_settings)

                # Merge with defaults, prioritizing file settings
                self._settings = {**DEFAULT_SETTINGS, **file_settings}

                # Validate settings
                if not self._validate_settings():
                    raise ValueError("Configuration contains invalid settings")

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
        temp_path = None
        try:
            # Create config directory if it doesn't exist
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self.config_path.parent,
                prefix=f".{self.config_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as f:
                temp_path = Path(f.name)
                json.dump(self._settings, f, indent=4, ensure_ascii=False)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())

            os.replace(temp_path, self.config_path)

            logger.info(f"Settings saved to {self.config_path}")
            return True

        except (OSError, TypeError, ValueError) as e:
            logger.error(f"Failed to save settings to {self.config_path}: {e}")
            if temp_path and Path(temp_path).exists():
                try:
                    Path(temp_path).unlink()
                except OSError:
                    logger.warning(f"Failed to remove temp settings file: {temp_path}")
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
        failed_keys = self.validate_update(settings)
        if not failed_keys:
            self._settings.update(settings)
            logger.debug(f"Settings updated: {settings}")
            return True
        else:
            logger.warning(f"Failed to update settings due to validation errors: {failed_keys}")
            return False

    def validate_update(self, settings: Dict[str, Any]) -> List[str]:
        """
        Validate a batch of settings without mutating current settings.

        Args:
            settings: Dictionary of settings to validate

        Returns:
            List of keys that failed validation
        """
        return [key for key, value in settings.items() if not self._validate_setting(key, value)]

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

    def _migrate_loaded_settings(self, file_settings: Dict[str, Any]) -> Dict[str, Any]:
        """Apply legacy key migrations before strict validation."""
        if not isinstance(file_settings, dict):
            raise ValueError("Configuration root must be a JSON object")

        migrated = file_settings.copy()

        if "quality" in migrated:
            if "preferred_quality" not in migrated:
                migrated["preferred_quality"] = migrated["quality"]
                logger.info("Migrated legacy 'quality' setting to 'preferred_quality'")
            migrated.pop("quality", None)

        if "current_theme" in migrated:
            if "dark_mode" not in migrated:
                migrated["dark_mode"] = migrated["current_theme"] == "dark"
                logger.info("Migrated legacy 'current_theme' setting to 'dark_mode'")
            migrated.pop("current_theme", None)

        for legacy_key in _LEGACY_LOAD_ONLY_SETTINGS - {"current_theme"}:
            if legacy_key in migrated:
                migrated.pop(legacy_key, None)
                logger.info(f"Removed retired legacy setting during load: {legacy_key}")

        return migrated

    def _validate_bool_setting(self, value: Any, label: str) -> None:
        """Require an actual bool, not a truthy/falsy stand-in."""
        if type(value) is not bool:
            raise ValidationError(f"{label} must be a boolean")

    def _validate_int_range_setting(
        self,
        value: Any,
        label: str,
        min_val: int,
        max_val: int,
    ) -> None:
        """Require an actual int and validate its allowed range."""
        if type(value) is not int:
            raise ValidationError(f"{label} must be an integer")
        validate_numeric_range(value, min_val=min_val, max_val=max_val, data_type=int)

    def _validate_int_choice_setting(
        self,
        value: Any,
        label: str,
        choices: tuple,
    ) -> None:
        """Require an actual int that is one of a fixed set of allowed values."""
        if type(value) is not int:
            raise ValidationError(f"{label} must be an integer")
        if value not in choices:
            allowed = ", ".join(str(choice) for choice in choices)
            raise ValidationError(f"{label} must be one of: {allowed}")

    def _validate_optional_file_path_setting(self, value: Any) -> None:
        """Validate an optional file path string."""
        validate_file_path(value, must_exist=False)

    def _validate_required_file_path_setting(self, value: Any, label: str) -> None:
        """Validate a required file path string."""
        if not isinstance(value, str):
            raise ValidationError(f"{label} must be a string")
        validate_file_path(value, must_exist=False)

    def _validate_ffmpeg_path_setting(self, value: Any) -> None:
        """Validate FFmpeg path, allowing an empty string for auto-detect."""
        if not isinstance(value, str):
            raise ValidationError("FFmpeg path must be a string")
        if value:
            validate_file_path(value, must_exist=False)

    def _setting_validators(self) -> Dict[str, Any]:
        """Return the runtime-supported validator map for settings."""
        return {
            "preferred_quality": validate_quality_option,
            "twitch_low_latency": lambda value: self._validate_bool_setting(
                value,
                "Twitch low-latency setting",
            ),
            "hls_live_edge": lambda value: self._validate_int_range_setting(
                value,
                "HLS live edge",
                MIN_HLS_LIVE_EDGE,
                MAX_HLS_LIVE_EDGE,
            ),
            "debug": lambda value: self._validate_bool_setting(value, "Debug setting"),
            "log_to_file": lambda value: self._validate_bool_setting(
                value,
                "Log to file setting",
            ),
            "log_level": validate_log_level,
            "clip_enabled": lambda value: self._validate_bool_setting(
                value,
                "Clip enabled setting",
            ),
            "clip_directory": lambda value: self._validate_required_file_path_setting(
                value,
                "Clip directory",
            ),
            "ffmpeg_path": self._validate_ffmpeg_path_setting,
            "dark_mode": lambda value: self._validate_bool_setting(
                value,
                "Dark mode setting",
            ),
            "network_timeout": lambda value: self._validate_int_range_setting(
                value,
                "Network timeout",
                MIN_NETWORK_TIMEOUT,
                MAX_NETWORK_TIMEOUT,
            ),
            "connection_retry_attempts": lambda value: self._validate_int_range_setting(
                value,
                "Connection retry attempts",
                MIN_RETRY_ATTEMPTS,
                MAX_RETRY_ATTEMPTS,
            ),
            "retry_delay": lambda value: self._validate_int_range_setting(
                value,
                "Retry delay",
                MIN_RETRY_DELAY,
                MAX_RETRY_DELAY,
            ),
            "favorites_auto_refresh": lambda value: self._validate_bool_setting(
                value,
                "Favorites auto-refresh setting",
            ),
            "favorites_refresh_interval": lambda value: self._validate_int_range_setting(
                value,
                "Favorites refresh interval",
                MIN_REFRESH_INTERVAL,
                MAX_REFRESH_INTERVAL,
            ),
            "favorites_check_timeout": lambda value: self._validate_int_range_setting(
                value,
                "Favorites check timeout",
                MIN_CHECK_TIMEOUT,
                MAX_CHECK_TIMEOUT,
            ),
            "favorite_live_notifications_enabled": lambda value: self._validate_bool_setting(
                value,
                "Favorite live notifications setting",
            ),
            "favorite_live_highlight_test_mode": lambda value: self._validate_bool_setting(
                value,
                "Favorite live highlight test mode setting",
            ),
            "favorite_live_notification_sound_enabled": (
                lambda value: self._validate_bool_setting(
                    value,
                    "Favorite live notification sound setting",
                )
            ),
            "button_hover_sound_enabled": lambda value: self._validate_bool_setting(
                value,
                "Button hover sound setting",
            ),
            "show_stream_preview": lambda value: self._validate_bool_setting(
                value,
                "Show stream preview setting",
            ),
            "window_width": lambda value: self._validate_int_range_setting(
                value,
                "Window width",
                MIN_WINDOW_WIDTH,
                MAX_WINDOW_WIDTH,
            ),
            "window_height": lambda value: self._validate_int_range_setting(
                value,
                "Window height",
                MIN_WINDOW_HEIGHT,
                MAX_WINDOW_HEIGHT,
            ),
            "window_maximized": lambda value: self._validate_bool_setting(
                value,
                "Window maximized setting",
            ),
            "enable_network_diagnostics": lambda value: self._validate_bool_setting(
                value,
                "Enable network diagnostics",
            ),
            "stream_manager_left_sidebar_open": lambda value: self._validate_bool_setting(
                value,
                "Stream manager left sidebar setting",
            ),
            "stream_manager_right_sidebar_open": lambda value: self._validate_bool_setting(
                value,
                "Stream manager right sidebar setting",
            ),
            "stream_manager_activity_drawer_open": lambda value: self._validate_bool_setting(
                value,
                "Stream manager activity drawer setting",
            ),
            "stream_manager_clip_duration_seconds": lambda value: self._validate_int_choice_setting(
                value,
                "Stream manager clip duration",
                (30, 60, 120, 300),
            ),
            "auto_collapse_panels_enabled": lambda value: self._validate_bool_setting(
                value,
                "Auto-collapse panels setting",
            ),
        }

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
            validator = self._validators.get(key)
            if key not in _KNOWN_SETTINGS or validator is None:
                raise ValidationError(f"Unknown setting key: {key}")
            validator(value)
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
