"""
Configuration management controller for TwitchAdAvoider GUI.

This module provides centralized configuration handling, extracted from the
monolithic StreamGUI class to improve maintainability and separation of concerns.

The :class:`ConfigController` handles:
    - Configuration updates and persistence
    - Debug mode management and logging reconfiguration
    - Theme preference management
    - Settings validation and defaults

Key Features:
    - Centralized configuration logic
    - Automatic logging reconfiguration
    - Event-driven configuration updates
    - Integration with status management
"""

from typing import Callable, Optional, Any

from ..status_manager import StatusManager
from src.config_manager import ConfigManager
from src.logging_config import get_logger, reconfigure_logging_from_config

logger = get_logger(__name__)


class ConfigController:
    """
    Manages application configuration and settings for the GUI.
    
    This controller extracts configuration management logic from the main GUI class,
    providing a clean separation between UI presentation and configuration handling.
    """

    def __init__(self, config: ConfigManager, status_manager: StatusManager):
        """
        Initialize the ConfigController.

        Args:
            config: Core configuration manager instance
            status_manager: Status manager for user feedback
        """
        self.config = config
        self.status_manager = status_manager
        
        # Callbacks for configuration changes (set by GUI components)
        self.on_debug_changed: Optional[Callable[[bool], None]] = None
        self.on_theme_changed: Optional[Callable[[str], None]] = None

    def set_callbacks(self, 
                     on_debug_changed: Optional[Callable[[bool], None]] = None,
                     on_theme_changed: Optional[Callable[[str], None]] = None) -> None:
        """
        Set callback functions for configuration change events.
        
        Args:
            on_debug_changed: Called when debug mode changes
            on_theme_changed: Called when theme changes
        """
        self.on_debug_changed = on_debug_changed
        self.on_theme_changed = on_theme_changed

    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration setting value.
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        return self.config.get(key, default)

    def set_setting(self, key: str, value: Any, save: bool = True) -> None:
        """
        Set a configuration setting value.
        
        Args:
            key: Configuration key
            value: Value to set
            save: Whether to immediately persist to file
        """
        self.config.set(key, value)
        if save:
            self.config.save_settings()

    def update_stream_settings(self, player: str, quality: str) -> None:
        """
        Update stream-related settings.
        
        Args:
            player: Player executable name
            quality: Preferred stream quality
        """
        self.config.set("player", player)
        self.config.set("preferred_quality", quality)

    def toggle_debug_mode(self, enabled: bool) -> None:
        """
        Toggle debug mode and handle related configuration.
        
        Args:
            enabled: Whether to enable debug mode
        """
        old_debug = self.config.get("debug", False)
        
        if old_debug != enabled:
            # Update debug flag
            self.config.set("debug", enabled)
            
            # Synchronize log_level setting to match debug state
            if enabled:
                self.config.set("log_level", "DEBUG")
            else:
                self.config.set("log_level", "INFO")  # Reset to default
            
            self.config.save_settings()  # Persist debug and log_level settings
            self._reconfigure_logging()

            # Provide user feedback
            if enabled:
                self.status_manager.add_system_message(
                    "Debug mode enabled - verbose logging active"
                )
                logger.debug("Debug mode enabled via configuration")
            else:
                self.status_manager.add_system_message("Debug mode disabled")
                logger.info("Debug mode disabled via configuration")

            # Notify callbacks
            if self.on_debug_changed:
                self.on_debug_changed(enabled)

    def change_theme(self, theme_name: str) -> bool:
        """
        Change the application theme.
        
        Args:
            theme_name: Name of theme to apply ('light' or 'dark')
            
        Returns:
            True if theme was changed, False if already current theme
        """
        old_theme = self.config.get("current_theme", "light")
        
        if old_theme != theme_name:
            # Update theme preference
            self.config.set("current_theme", theme_name)
            self.config.save_settings()

            self.status_manager.add_system_message(f"Switched to {theme_name} theme")
            logger.info(f"Theme changed via configuration: {old_theme} -> {theme_name}")

            # Notify callbacks
            if self.on_theme_changed:
                self.on_theme_changed(theme_name)
                
            return True
        
        return False

    def get_current_theme(self) -> str:
        """
        Get the current theme name.
        
        Returns:
            Current theme name ('light' or 'dark')
        """
        return self.config.get("current_theme", "light")

    def is_debug_enabled(self) -> bool:
        """
        Check if debug mode is enabled.
        
        Returns:
            True if debug mode is active
        """
        return self.config.get("debug", False)

    def get_player_setting(self) -> str:
        """
        Get the configured player.
        
        Returns:
            Player executable name
        """
        return self.config.get("player", "vlc")

    def get_quality_setting(self) -> str:
        """
        Get the preferred quality setting.
        
        Returns:
            Quality preference string
        """
        return self.config.get("preferred_quality", "best")

    def reset_to_defaults(self) -> None:
        """Reset configuration to default values"""
        defaults = {
            "player": "vlc",
            "preferred_quality": "best", 
            "debug": False,
            "log_level": "INFO",
            "current_theme": "light"
        }
        
        for key, value in defaults.items():
            self.config.set(key, value)
        
        self.config.save_settings()
        self._reconfigure_logging()
        
        self.status_manager.add_system_message("Configuration reset to defaults")
        logger.info("Configuration reset to default values")

    def _reconfigure_logging(self) -> None:
        """Reconfigure logging based on current debug settings"""
        try:
            reconfigure_logging_from_config(self.config)
        except Exception as e:
            logger.error(f"Failed to reconfigure logging: {e}")
            self.status_manager.add_error(f"Logging reconfiguration failed: {str(e)}")