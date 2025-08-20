"""
Configuration management for TwitchAdAvoider
Handles loading, saving, and validation of application settings.
"""
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from .constants import DEFAULT_SETTINGS, CONFIG_FILE, QUALITY_OPTIONS, SUPPORTED_PLAYERS
from .logging_config import get_logger

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
                with open(self.config_path, 'r', encoding='utf-8') as f:
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
            with open(self.config_path, 'w', encoding='utf-8') as f:
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
        Validate a single setting.
        
        Args:
            key: Setting key
            value: Setting value
            
        Returns:
            True if setting is valid, False otherwise
        """
        validators = {
            'preferred_quality': lambda v: v in QUALITY_OPTIONS,
            'player': lambda v: v in list(SUPPORTED_PLAYERS.keys()) + ['auto'],
            'cache_duration': lambda v: isinstance(v, int) and v >= 0,
            'debug': lambda v: isinstance(v, bool),
            'log_to_file': lambda v: isinstance(v, bool),
            'log_level': lambda v: v in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
            'player_path': lambda v: v is None or isinstance(v, str),
            'player_args': lambda v: v is None or isinstance(v, str)
        }
        
        validator = validators.get(key)
        if validator:
            try:
                return validator(value)
            except (TypeError, ValueError):
                return False
        
        # Unknown setting keys are allowed but logged
        logger.debug(f"Unknown setting key: {key}")
        return True