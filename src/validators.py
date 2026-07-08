"""
Input validation and sanitization functions for TwitchAdAvoider.

This module provides security-focused validation to prevent injection attacks
and ensure data integrity. All user inputs should pass through these validation
functions before being processed by the application.

The validation layer implements defense-in-depth security patterns to protect against:
    - Path traversal attacks
    - Control character injection
    - Platform-specific attack vectors

See Also:
    :mod:`src.exceptions`: Custom exception classes for validation errors
    :mod:`src.config_manager`: Configuration validation integration
    :class:`~src.web_stream_service.WebStreamService`: Stream service using these validators
"""

import os
import re
from pathlib import Path
from typing import Optional, Union, Any
from .exceptions import ValidationError
from .constants import TWITCH_USERNAME_PATTERN, QUALITY_OPTIONS


def validate_channel_name(channel_name: str) -> str:
    """
    Validate and sanitize Twitch channel name with enhanced security controls.

    This function implements multi-layered security validation to protect against various
    attack vectors while ensuring compliance with Twitch username requirements.

    Args:
        channel_name (str): Raw channel name input from user

    Returns:
        str: Validated and normalized channel name (lowercase, trimmed)

    Raises:
        ValidationError: If channel name is invalid, too short/long, or potentially malicious

    Example:
        >>> validate_channel_name("Ninja")
        'ninja'
        >>> validate_channel_name("test_channel_123")
        'test_channel_123'

    Note:
        Channel names must be 4-25 characters, contain only alphanumeric characters
        and underscores, and pass security pattern validation.

    See Also:
        :func:`sanitize_string_input`: For general string sanitization
        :class:`~src.exceptions.ValidationError`: Exception raised on validation failure
        :data:`~src.constants.TWITCH_USERNAME_PATTERN`: Regex pattern used for validation
    """
    if not channel_name:
        raise ValidationError("Channel name cannot be empty")

    # Remove whitespace and convert to lowercase
    channel_name = channel_name.strip().lower()

    # Check length constraints (Twitch allows 4-25 characters)
    if len(channel_name) < 4:
        raise ValidationError("Channel name must be at least 4 characters long")
    if len(channel_name) > 25:
        raise ValidationError("Channel name cannot exceed 25 characters")

    # Validate against Twitch username pattern
    if not re.match(TWITCH_USERNAME_PATTERN, channel_name):
        raise ValidationError(
            "Invalid channel name. Must contain only letters, numbers, and underscores"
        )

    # Additional security checks - multi-layered attack prevention
    # These patterns protect against various attack vectors that could exploit channel names
    suspicious_patterns = [
        r"\.\./",  # Path traversal: prevents "../../../etc/passwd" style attacks
        r'[<>"|*?]',  # Shell metacharacters: blocks redirection and wildcards
        r"[\x00-\x1f\x7f-\x9f]",  # Control characters: prevents null bytes and escape sequences
        r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])$",  # Windows reserved device names
    ]

    # Apply each security pattern check
    # Using case-insensitive matching to catch mixed-case evasion attempts
    for pattern in suspicious_patterns:
        if re.search(pattern, channel_name, re.IGNORECASE):
            raise ValidationError("Channel name contains forbidden characters or patterns")

    return channel_name


def validate_file_path(file_path: Optional[str], must_exist: bool = False) -> Optional[str]:
    """
    Validate file path to prevent path traversal attacks and ensure security.

    Args:
        file_path: Raw file path input
        must_exist: Whether the file must exist on the filesystem

    Returns:
        Validated absolute path or None if input is None

    Raises:
        ValidationError: If path is invalid or potentially malicious
    """
    if not file_path:
        return None

    file_path = file_path.strip()
    if not file_path:
        return None

    try:
        # Convert to Path object for validation
        path = Path(file_path)

        # Multi-level path traversal protection
        # Defense in depth: check both Path object analysis and string patterns
        path_str = str(path)

        # Level 1: Check Path object parts for traversal sequences
        # Path().parts splits the path and normalizes it, catching most traversal attempts
        if ".." in path.parts:
            raise ValidationError("Path traversal sequences (..) are not allowed")

        # Level 2: String-based detection for raw traversal patterns
        # Catches cases where Path normalization might not detect traversal
        # Covers both Unix (../) and Windows (..\) path separators
        if "../" in file_path or "..\\" in file_path:
            raise ValidationError("Path traversal sequences (..) are not allowed")

        # Comprehensive path security validation
        # These patterns prevent various file system security issues
        dangerous_patterns = [
            r"[\x00-\x1f\x7f-\x9f]",  # Control chars: null bytes, escape sequences, DEL
            r'[<>"|*?]',  # Windows forbidden chars (except : for drive letters)
            r"^\s*$",  # Empty paths: prevent confusion and potential bypasses
        ]

        # Apply file system security checks
        # Each pattern targets different classes of file system vulnerabilities
        for pattern in dangerous_patterns:
            if re.search(pattern, path_str):
                raise ValidationError("File path contains forbidden characters")

        # Path normalization and bounds checking
        # Convert to absolute path to eliminate ambiguity and prevent relative path attacks
        # resolve() also normalizes the path, removing redundant separators and resolving symlinks
        abs_path = path.resolve()

        # Path length validation - defense against resource exhaustion
        # Extremely long paths can cause issues with:
        # - File system limits
        # - Buffer overflows in native code
        # - Memory exhaustion
        # - UI display problems
        if len(str(abs_path)) > 1000:
            raise ValidationError("File path is too long (max 1000 characters)")

        # Check existence if required
        if must_exist and not abs_path.exists():
            raise ValidationError(f"File does not exist: {abs_path}")

        # For executable paths, do additional validation
        if abs_path.suffix.lower() in {".exe", ".com", ".bat", ".cmd", ".scr"}:
            # For Windows executables, check they're in reasonable locations
            if os.name == "nt":
                allowed_prefixes = [
                    "C:\\Program Files",
                    "C:\\Program Files (x86)",
                    "C:\\Windows\\System32",
                    "C:\\ProgramData\\chocolatey",
                ]
                path_str_upper = str(abs_path).upper()
                if not any(
                    path_str_upper.startswith(prefix.upper()) for prefix in allowed_prefixes
                ):
                    # Allow if it's in PATH or user explicitly set it
                    pass  # We'll allow it but log a warning

        return str(abs_path)

    except (OSError, ValueError) as e:
        raise ValidationError(f"Invalid file path: {e}")


def validate_numeric_range(
    value: Any,
    min_val: Optional[float] = None,
    max_val: Optional[float] = None,
    data_type: type = int,
) -> Union[int, float]:
    """
    Validate numeric values are within acceptable ranges.

    Args:
        value: Value to validate
        min_val: Minimum allowed value (inclusive)
        max_val: Maximum allowed value (inclusive)
        data_type: Expected numeric type (int or float)

    Returns:
        Validated numeric value

    Raises:
        ValidationError: If value is invalid or out of range
    """
    # Type conversion and validation
    try:
        if data_type == int:
            numeric_value: Union[int, float] = int(value)
        elif data_type == float:
            numeric_value = float(value)
        else:
            raise ValidationError(f"Unsupported numeric type: {data_type}")
    except (ValueError, TypeError):
        raise ValidationError(f"Invalid {data_type.__name__} value: {value}")

    # Range validation
    if min_val is not None and numeric_value < min_val:
        raise ValidationError(f"Value {numeric_value} is below minimum {min_val}")

    if max_val is not None and numeric_value > max_val:
        raise ValidationError(f"Value {numeric_value} is above maximum {max_val}")

    return numeric_value


def validate_quality_option(quality: str) -> str:
    """
    Validate stream quality option.

    Args:
        quality: Quality setting to validate

    Returns:
        Validated quality option

    Raises:
        ValidationError: If quality is not supported
    """
    if not quality or not isinstance(quality, str):
        raise ValidationError("Quality option cannot be empty")

    quality = quality.strip().lower()

    if quality not in QUALITY_OPTIONS:
        raise ValidationError(
            f"Invalid quality option: {quality}. "
            f"Supported options: {', '.join(QUALITY_OPTIONS)}"
        )

    return quality


def validate_log_level(log_level: str) -> str:
    """
    Validate logging level.

    Args:
        log_level: Log level to validate

    Returns:
        Validated log level

    Raises:
        ValidationError: If log level is not supported
    """
    if not log_level or not isinstance(log_level, str):
        raise ValidationError("Log level cannot be empty")

    log_level = log_level.strip().upper()

    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if log_level not in valid_levels:
        raise ValidationError(
            f"Invalid log level: {log_level}. " f"Supported levels: {', '.join(valid_levels)}"
        )

    return log_level


def sanitize_string_input(
    input_str: Optional[str], max_length: int = 1000, allow_empty: bool = True
) -> Optional[str]:
    """
    General purpose string sanitization with security controls.

    Args:
        input_str: String to sanitize
        max_length: Maximum allowed length
        allow_empty: Whether empty strings are allowed

    Returns:
        Sanitized string or None

    Raises:
        ValidationError: If string is invalid
    """
    if input_str is None:
        return None

    if not isinstance(input_str, str):
        raise ValidationError("Input must be a string")

    # Normalize whitespace
    sanitized = input_str.strip()

    if not sanitized and not allow_empty:
        raise ValidationError("Input cannot be empty")

    # Check length
    if len(sanitized) > max_length:
        raise ValidationError(f"Input too long (max {max_length} characters)")

    # Remove control characters (except common whitespace)
    sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", sanitized)

    return sanitized if sanitized else None
