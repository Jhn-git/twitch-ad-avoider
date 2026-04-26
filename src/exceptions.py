"""
Custom exceptions for TwitchAdAvoider
Defines application-specific exception classes for better error handling.
"""

from typing import Optional


class TwitchAdAvoiderError(Exception):
    """Base exception class for TwitchAdAvoider application."""

    def __init__(self, message: str, original_error: Optional[Exception] = None):
        """
        Initialize the exception.

        Args:
            message: Error message
            original_error: Original exception that caused this error (if any)
        """
        super().__init__(message)
        self.message = message
        self.original_error = original_error


class TwitchStreamError(TwitchAdAvoiderError):
    """Exception raised for stream-related errors."""

    pass


class PlayerError(TwitchAdAvoiderError):
    """Exception raised for video player-related errors."""

    pass


class ValidationError(TwitchAdAvoiderError):
    """Exception raised for input validation errors."""

    pass


class StreamlinkError(TwitchAdAvoiderError):
    """Exception raised for streamlink-related errors."""

    pass
