"""
DateTime utility functions for TwitchAdAvoider GUI.

This module provides centralized datetime handling functionality,
consolidating duplicate datetime parsing logic from the favorites manager.

The utilities handle:
    - ISO format datetime string parsing with error handling
    - UTC timezone-aware datetime operations
    - Serialization/deserialization for JSON storage
    - Robust error recovery for malformed datetime data

Key Features:
    - Consistent error handling across datetime operations
    - UTC timezone enforcement for consistency
    - Safe parsing with fallback to None for invalid data
    - Optimized for JSON serialization workflows
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any, Union
import logging

from src.logging_config import get_logger

logger = get_logger(__name__)


class DateTimeUtility:
    """
    Centralized datetime handling utilities for favorites and status management.
    
    This class consolidates datetime parsing and serialization logic
    to eliminate duplicate code patterns in the favorites manager.
    """

    @staticmethod
    def parse_datetime_string(datetime_str: Union[str, datetime, None]) -> Optional[datetime]:
        """
        Parse a datetime string to datetime object with error handling.
        
        Args:
            datetime_str: String to parse, existing datetime object, or None
            
        Returns:
            Parsed datetime object or None if invalid/empty
        """
        if datetime_str is None:
            return None
            
        # If already a datetime object, return as-is
        if isinstance(datetime_str, datetime):
            return datetime_str
            
        # Parse string format
        if isinstance(datetime_str, str):
            try:
                return datetime.fromisoformat(datetime_str)
            except ValueError as e:
                logger.debug(f"Failed to parse datetime string '{datetime_str}': {e}")
                return None
        
        # Unsupported type
        logger.warning(f"Unsupported datetime type: {type(datetime_str)}")
        return None

    @staticmethod
    def serialize_datetime(dt: Optional[datetime]) -> Optional[str]:
        """
        Serialize datetime object to ISO format string.
        
        Args:
            dt: Datetime object to serialize
            
        Returns:
            ISO format string or None if input is None
        """
        if dt is None:
            return None
            
        if isinstance(dt, datetime):
            return dt.isoformat()
            
        logger.warning(f"Cannot serialize non-datetime object: {type(dt)}")
        return None

    @staticmethod
    def parse_channel_datetime_fields(channel_data: Dict[str, Any]) -> Dict[str, Optional[datetime]]:
        """
        Parse datetime fields from channel data dictionary.
        
        This method consolidates the duplicate datetime parsing logic
        found in the favorites manager.
        
        Args:
            channel_data: Dictionary containing channel information
            
        Returns:
            Dictionary with parsed datetime objects
        """
        result = {}
        
        # Standard datetime fields in channel data
        datetime_fields = ['last_checked', 'last_seen_live']
        
        for field_name in datetime_fields:
            field_value = channel_data.get(field_name)
            result[field_name] = DateTimeUtility.parse_datetime_string(field_value)
            
        return result

    @staticmethod
    def serialize_channel_datetime_fields(datetime_fields: Dict[str, Optional[datetime]]) -> Dict[str, Optional[str]]:
        """
        Serialize datetime fields for JSON storage.
        
        Args:
            datetime_fields: Dictionary with datetime objects
            
        Returns:
            Dictionary with serialized datetime strings
        """
        result = {}
        
        for field_name, dt_value in datetime_fields.items():
            result[field_name] = DateTimeUtility.serialize_datetime(dt_value)
            
        return result

    @staticmethod
    def get_current_utc() -> datetime:
        """
        Get current UTC datetime.
        
        Returns:
            Current datetime in UTC timezone
        """
        return datetime.now(timezone.utc)

    @staticmethod
    def ensure_utc_timezone(dt: Optional[datetime]) -> Optional[datetime]:
        """
        Ensure datetime has UTC timezone.
        
        Args:
            dt: Datetime object to check
            
        Returns:
            Datetime with UTC timezone or None if input is None
        """
        if dt is None:
            return None
            
        if dt.tzinfo is None:
            # Naive datetime - assume UTC
            return dt.replace(tzinfo=timezone.utc)
        
        # Already has timezone info
        return dt

    @staticmethod
    def format_relative_time(dt: Optional[datetime], reference: Optional[datetime] = None) -> str:
        """
        Format datetime as relative time string (e.g., "2 hours ago").
        
        Args:
            dt: Datetime to format
            reference: Reference time (defaults to current UTC)
            
        Returns:
            Formatted relative time string
        """
        if dt is None:
            return "Never"
            
        if reference is None:
            reference = DateTimeUtility.get_current_utc()
            
        # Ensure both datetimes have timezone info
        dt = DateTimeUtility.ensure_utc_timezone(dt)
        reference = DateTimeUtility.ensure_utc_timezone(reference)
        
        if dt is None or reference is None:
            return "Unknown"
            
        # Calculate time difference
        delta = reference - dt
        
        # Handle future times
        if delta.total_seconds() < 0:
            return "In the future"
            
        # Format based on time difference
        seconds = int(delta.total_seconds())
        
        if seconds < 60:
            return f"{seconds} seconds ago"
        elif seconds < 3600:  # Less than 1 hour
            minutes = seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif seconds < 86400:  # Less than 1 day
            hours = seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        else:  # Days or more
            days = seconds // 86400
            return f"{days} day{'s' if days != 1 else ''} ago"

    @staticmethod
    def is_datetime_recent(dt: Optional[datetime], threshold_minutes: int = 60) -> bool:
        """
        Check if datetime is within a recent threshold.
        
        Args:
            dt: Datetime to check
            threshold_minutes: Minutes threshold for "recent"
            
        Returns:
            True if datetime is recent, False otherwise
        """
        if dt is None:
            return False
            
        current_time = DateTimeUtility.get_current_utc()
        dt = DateTimeUtility.ensure_utc_timezone(dt)
        
        if dt is None:
            return False
            
        delta = current_time - dt
        return delta.total_seconds() < (threshold_minutes * 60)


# Convenience functions for common patterns
def parse_favorites_datetime_data(favorites_data: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Parse datetime fields in favorites data structure.
    
    Args:
        favorites_data: Raw favorites data with string datetime fields
        
    Returns:
        Favorites data with parsed datetime objects
    """
    processed_data = {}
    
    for channel_name, channel_data in favorites_data.items():
        processed_channel = dict(channel_data)  # Copy original data
        
        # Parse datetime fields
        datetime_fields = DateTimeUtility.parse_channel_datetime_fields(channel_data)
        processed_channel.update(datetime_fields)
        
        processed_data[channel_name] = processed_channel
        
    return processed_data

def serialize_favorites_datetime_data(favorites_data: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Serialize datetime fields in favorites data for JSON storage.
    
    Args:
        favorites_data: Favorites data with datetime objects
        
    Returns:
        Favorites data with serialized datetime strings
    """
    serialized_data = {}
    
    for channel_name, channel_data in favorites_data.items():
        serialized_channel = dict(channel_data)  # Copy original data
        
        # Extract and serialize datetime fields
        datetime_fields = {
            'last_checked': channel_data.get('last_checked'),
            'last_seen_live': channel_data.get('last_seen_live')
        }
        
        serialized_datetime_fields = DateTimeUtility.serialize_channel_datetime_fields(datetime_fields)
        serialized_channel.update(serialized_datetime_fields)
        
        serialized_data[channel_name] = serialized_channel
        
    return serialized_data