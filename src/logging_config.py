"""
Logging configuration for TwitchAdAvoider
Provides centralized logging setup with configurable levels and formats.
"""
import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logging(
    level: str = "INFO",
    log_to_file: bool = False,
    log_file_path: Optional[Path] = None,
    enable_debug: bool = False
) -> logging.Logger:
    """
    Setup logging configuration for the application.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: Whether to log to a file in addition to console
        log_file_path: Path to log file (defaults to logs/twitch_ad_avoider.log)
        enable_debug: Enable debug mode with verbose output (overrides level to DEBUG)
        
    Returns:
        Configured logger instance
    """
    # When debug is enabled, override level to DEBUG and enable file logging
    if enable_debug:
        effective_level = "DEBUG"
        effective_log_to_file = True  # Auto-enable file logging in debug mode
    else:
        effective_level = level
        effective_log_to_file = log_to_file
    
    # Convert level string to logging constant
    numeric_level = getattr(logging, effective_level.upper(), logging.INFO)
    
    # Create logger
    logger = logging.getLogger("twitch_ad_avoider")
    logger.setLevel(numeric_level)
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    # Create formatter
    if enable_debug:
        formatter = logging.Formatter(
            '[%(asctime)s] %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    else:
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (optional)
    if effective_log_to_file:
        if log_file_path is None:
            log_file_path = Path("logs/twitch_ad_avoider.log")
        
        # Create logs directory if it doesn't exist
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file_path)
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def reconfigure_logging(
    level: str = "INFO",
    log_to_file: bool = False,
    log_file_path: Optional[Path] = None,
    enable_debug: bool = False
) -> logging.Logger:
    """
    Reconfigure existing logging setup with new parameters.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: Whether to log to a file in addition to console
        log_file_path: Path to log file (defaults to logs/twitch_ad_avoider.log)
        enable_debug: Enable debug mode with verbose output (overrides level to DEBUG)
        
    Returns:
        Reconfigured logger instance
    """
    # Remove existing handlers and reconfigure
    logger = logging.getLogger("twitch_ad_avoider")
    
    # Clear existing handlers
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)
    
    # Reconfigure with new settings using the same logic as setup_logging
    return setup_logging(level, log_to_file, log_file_path, enable_debug)


def configure_logging_from_config(config_manager) -> logging.Logger:
    """
    Configure logging based on settings from ConfigManager.
    
    This is the centralized logging configuration function that eliminates
    duplicate parameter handling across the application.
    
    Args:
        config_manager: ConfigManager instance containing logging settings
        
    Returns:
        Configured logger instance
    """
    # Get settings from config
    debug_enabled = config_manager.get('debug', False)
    log_level = config_manager.get('log_level', 'INFO')
    log_to_file = config_manager.get('log_to_file', False)
    
    # Configure logging with simplified logic
    return setup_logging(
        level=log_level,
        log_to_file=log_to_file,
        enable_debug=debug_enabled
    )


def reconfigure_logging_from_config(config_manager) -> logging.Logger:
    """
    Reconfigure logging based on settings from ConfigManager.
    
    Args:
        config_manager: ConfigManager instance containing logging settings
        
    Returns:
        Reconfigured logger instance
    """
    # Get settings from config
    debug_enabled = config_manager.get('debug', False)
    log_level = config_manager.get('log_level', 'INFO')
    log_to_file = config_manager.get('log_to_file', False)
    
    # Reconfigure logging with simplified logic
    return reconfigure_logging(
        level=log_level,
        log_to_file=log_to_file,
        enable_debug=debug_enabled
    )


def get_logger(name: str = "twitch_ad_avoider") -> logging.Logger:
    """
    Get a logger instance with the specified name.
    
    Args:
        name: Logger name
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)