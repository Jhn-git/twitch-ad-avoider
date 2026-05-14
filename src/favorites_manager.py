"""
Favorites Manager for TwitchAdAvoider.

This module provides persistent storage and management of favorite channels with
status tracking capabilities. It handles JSON-based storage with backward
compatibility and atomic operations.

The :class:`FavoritesManager` provides:
    - Persistent channel favorites storage
    - Real-time status tracking integration
    - JSON format migration and backward compatibility
    - Thread-safe operations for GUI integration
    - Automatic data validation and error recovery

Features:
    - Atomic file operations to prevent data corruption
    - UTC timestamp tracking for live status history
    - Flexible data format supporting future extensions
    - Integration with status monitoring system

See Also:
    :class:`~gui_qt.stream_gui.StreamGUI`: Qt GUI integration
    :class:`~src.status_monitor.StatusMonitor`: Status checking integration
    :class:`FavoriteChannelInfo`: Channel information data structure
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, NamedTuple, Union
from datetime import datetime, timezone

from src.exceptions import ValidationError
from src.logging_config import get_logger
from src.validators import validate_channel_name

logger = get_logger(__name__)


class FavoriteChannelInfo(NamedTuple):
    """
    Information about a favorite channel including live status and timing data.

    This data structure holds comprehensive information about a favorited channel,
    including current live status and historical timing information for status tracking.

    Attributes:
        channel_name (str): The Twitch channel name (validated format)
        is_live (bool): Current live status of the channel
        is_pinned (bool): Whether the channel is pinned to the top of the list
        last_checked (Optional[datetime]): UTC timestamp of last status check
        last_seen_live (Optional[datetime]): UTC timestamp when channel was last seen live

    Example:
        >>> info = FavoriteChannelInfo("ninja", True, False, datetime.now(timezone.utc))
        >>> print(f"{info.channel_name} is {'live' if info.is_live else 'offline'}")

    See Also:
        :class:`FavoritesManager`: Manager class that uses this data structure
        :class:`~src.status_monitor.StatusMonitor`: Status checking functionality
    """

    channel_name: str
    is_live: bool = False
    is_pinned: bool = False
    last_checked: Optional[datetime] = None
    last_seen_live: Optional[datetime] = None


class FavoritesManager:
    """Manage persistent storage of favorite Twitch channels."""

    def __init__(self, favorites_file: Optional[Union[Path, str]] = None) -> None:
        self.favorites_file = (
            Path(favorites_file) if favorites_file else Path("config/favorites.json")
        )
        self._needs_cleanup_save = False
        self.favorites_data: Dict[str, Dict] = self._load_favorites()
        if self._needs_cleanup_save:
            self._save_favorites()

    def _load_favorites(self) -> Dict[str, Dict]:
        """Load favorites from JSON file with backward compatibility"""
        if os.path.exists(self.favorites_file):
            try:
                with open(self.favorites_file, "r") as f:
                    data = json.load(f)

                    # Handle old format (list of channel names)
                    if "favorites" in data and isinstance(data["favorites"], list):
                        # Convert old format to new format
                        favorites_dict = {}
                        for channel in data["favorites"]:
                            normalized = self._normalize_channel(channel)
                            if not normalized:
                                self._needs_cleanup_save = True
                                continue
                            favorites_dict[normalized] = {
                                "channel_name": normalized,
                                "is_live": False,
                                "is_pinned": False,
                                "last_checked": None,
                                "last_seen_live": None,
                            }
                        self._needs_cleanup_save = True
                        return favorites_dict

                    # Handle new format (dict with status data)
                    elif "channels" in data:
                        return self._validate_loaded_channels(data["channels"])

            except (json.JSONDecodeError, KeyError):
                pass

        return {}

    def _normalize_channel(self, channel_name: object) -> Optional[str]:
        """Validate and normalize a channel name, returning None for invalid input."""
        try:
            if not isinstance(channel_name, str):
                raise ValidationError("Channel name must be a string")
            return validate_channel_name(channel_name)
        except ValidationError as e:
            logger.warning(f"Dropping invalid favorite channel {channel_name!r}: {e}")
            return None

    def _validate_loaded_channels(self, channels: object) -> Dict[str, Dict]:
        """Validate channels loaded from the versioned favorites format."""
        if not isinstance(channels, dict):
            self._needs_cleanup_save = True
            return {}

        valid_channels = {}
        for key, info in channels.items():
            if not isinstance(info, dict):
                self._needs_cleanup_save = True
                logger.warning(f"Dropping malformed favorite record for {key!r}")
                continue

            normalized = self._normalize_channel(info.get("channel_name", key))
            if not normalized:
                self._needs_cleanup_save = True
                continue

            if key != normalized or info.get("channel_name") != normalized:
                self._needs_cleanup_save = True

            valid_channels[normalized] = {
                "channel_name": normalized,
                "is_live": bool(info.get("is_live", False)),
                "is_pinned": bool(info.get("is_pinned", False)),
                "last_checked": info.get("last_checked"),
                "last_seen_live": info.get("last_seen_live"),
            }

        if len(valid_channels) != len(channels):
            self._needs_cleanup_save = True

        return valid_channels

    def _save_favorites(self) -> None:
        """Save favorites to JSON file"""
        self.favorites_file.parent.mkdir(parents=True, exist_ok=True)

        # Convert datetime objects to ISO strings for JSON serialization
        serializable_data = {}
        for channel, info in self.favorites_data.items():
            serializable_info = info.copy()
            for key in ["last_checked", "last_seen_live"]:
                if serializable_info.get(key) and isinstance(serializable_info[key], datetime):
                    serializable_info[key] = serializable_info[key].isoformat()
            serializable_data[channel] = serializable_info

        data = {"channels": serializable_data, "version": "2.0"}

        temp_path = None
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=self.favorites_file.parent,
            prefix=f".{self.favorites_file.name}.",
            suffix=".tmp",
            delete=False,
        ) as f:
            temp_path = Path(f.name)
            json.dump(data, f, indent=4)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())

        os.replace(temp_path, self.favorites_file)
        self._needs_cleanup_save = False

    def add_favorite(self, channel_name: str) -> bool:
        """Add a channel to favorites"""
        normalized = self._normalize_channel(channel_name)
        if normalized and normalized not in self.favorites_data:
            self.favorites_data[normalized] = {
                "channel_name": normalized,
                "is_live": False,
                "is_pinned": False,
                "last_checked": None,
                "last_seen_live": None,
            }
            self._save_favorites()
            return True
        return False

    def remove_favorite(self, channel_name: str) -> bool:
        """Remove a channel from favorites"""
        normalized = self._normalize_channel(channel_name)
        if normalized and normalized in self.favorites_data:
            del self.favorites_data[normalized]
            self._save_favorites()
            return True
        return False

    def get_favorites(self) -> List[str]:
        """Get list of favorite channel names (for backward compatibility)"""
        return sorted([info["channel_name"] for info in self.favorites_data.values()])

    def get_favorites_with_status(self) -> List[FavoriteChannelInfo]:
        """Get list of favorite channels with their status information"""
        favorites = []
        for channel_data in self.favorites_data.values():
            # Parse datetime strings back to datetime objects
            last_checked = channel_data.get("last_checked")
            if last_checked and isinstance(last_checked, str):
                try:
                    last_checked = datetime.fromisoformat(last_checked)
                except ValueError:
                    last_checked = None

            last_seen_live = channel_data.get("last_seen_live")
            if last_seen_live and isinstance(last_seen_live, str):
                try:
                    last_seen_live = datetime.fromisoformat(last_seen_live)
                except ValueError:
                    last_seen_live = None

            favorites.append(
                FavoriteChannelInfo(
                    channel_name=channel_data["channel_name"],
                    is_live=channel_data.get("is_live", False),
                    is_pinned=channel_data.get("is_pinned", False),
                    last_checked=last_checked,
                    last_seen_live=last_seen_live,
                )
            )

        return sorted(
            favorites,
            key=lambda x: (not x.is_live, not x.is_pinned, x.channel_name.lower()),
        )

    def update_channel_status(self, channel_name: str, is_live: bool) -> None:
        """Update status information for a favorite channel"""
        normalized = self._normalize_channel(channel_name)
        if normalized and normalized in self.favorites_data:
            now = datetime.now(timezone.utc)

            self.favorites_data[normalized].update({"is_live": is_live, "last_checked": now})

            # Update last_seen_live if stream is currently live
            if is_live:
                self.favorites_data[normalized]["last_seen_live"] = now

            self._save_favorites()

    def is_favorite(self, channel_name: str) -> bool:
        """Check if a channel is in favorites"""
        normalized = self._normalize_channel(channel_name)
        return normalized in self.favorites_data if normalized else False

    def get_channel_info(self, channel_name: str) -> Optional[FavoriteChannelInfo]:
        """Get status information for a specific channel"""
        normalized = self._normalize_channel(channel_name)
        if normalized and normalized in self.favorites_data:
            channel_data = self.favorites_data[normalized]

            # Parse datetime strings
            last_checked = channel_data.get("last_checked")
            if last_checked and isinstance(last_checked, str):
                try:
                    last_checked = datetime.fromisoformat(last_checked)
                except ValueError:
                    last_checked = None

            last_seen_live = channel_data.get("last_seen_live")
            if last_seen_live and isinstance(last_seen_live, str):
                try:
                    last_seen_live = datetime.fromisoformat(last_seen_live)
                except ValueError:
                    last_seen_live = None

            return FavoriteChannelInfo(
                channel_name=channel_data["channel_name"],
                is_live=channel_data.get("is_live", False),
                is_pinned=channel_data.get("is_pinned", False),
                last_checked=last_checked,
                last_seen_live=last_seen_live,
            )
        return None

    def toggle_pin(self, channel_name: str) -> bool:
        """Toggle pin status for a channel. Returns new pin state."""
        normalized = self._normalize_channel(channel_name)
        if normalized and normalized in self.favorites_data:
            current = self.favorites_data[normalized].get("is_pinned", False)
            self.favorites_data[normalized]["is_pinned"] = not current
            self._save_favorites()
            return not current
        return False

    def clear_favorites(self) -> None:
        """Clear all favorites"""
        self.favorites_data = {}
        self._save_favorites()
