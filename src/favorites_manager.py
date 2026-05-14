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
from pathlib import Path
from typing import Dict, List, Optional, NamedTuple, Union
from datetime import datetime, timezone


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
        self.favorites_file = favorites_file or Path("config/favorites.json")
        self.favorites_data: Dict[str, Dict] = self._load_favorites()

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
                            favorites_dict[channel.lower()] = {
                                "channel_name": channel,
                                "is_live": False,
                                "last_checked": None,
                                "last_seen_live": None,
                            }
                        return favorites_dict

                    # Handle new format (dict with status data)
                    elif "channels" in data:
                        return data["channels"]

            except (json.JSONDecodeError, KeyError):
                pass

        return {}

    def _save_favorites(self) -> None:
        """Save favorites to JSON file"""
        os.makedirs(os.path.dirname(self.favorites_file), exist_ok=True)

        # Convert datetime objects to ISO strings for JSON serialization
        serializable_data = {}
        for channel, info in self.favorites_data.items():
            serializable_info = info.copy()
            for key in ["last_checked", "last_seen_live"]:
                if serializable_info.get(key) and isinstance(serializable_info[key], datetime):
                    serializable_info[key] = serializable_info[key].isoformat()
            serializable_data[channel] = serializable_info

        data = {"channels": serializable_data, "version": "2.0"}

        with open(self.favorites_file, "w") as f:
            json.dump(data, f, indent=4)

    def add_favorite(self, channel_name: str) -> bool:
        """Add a channel to favorites"""
        channel_name = channel_name.lower().strip()
        if channel_name and channel_name not in self.favorites_data:
            self.favorites_data[channel_name] = {
                "channel_name": channel_name,
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
        channel_name = channel_name.lower().strip()
        if channel_name in self.favorites_data:
            del self.favorites_data[channel_name]
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
        channel_name = channel_name.lower().strip()
        if channel_name in self.favorites_data:
            now = datetime.now(timezone.utc)

            self.favorites_data[channel_name].update({"is_live": is_live, "last_checked": now})

            # Update last_seen_live if stream is currently live
            if is_live:
                self.favorites_data[channel_name]["last_seen_live"] = now

            self._save_favorites()

    def is_favorite(self, channel_name: str) -> bool:
        """Check if a channel is in favorites"""
        return channel_name.lower().strip() in self.favorites_data

    def get_channel_info(self, channel_name: str) -> Optional[FavoriteChannelInfo]:
        """Get status information for a specific channel"""
        channel_name = channel_name.lower().strip()
        if channel_name in self.favorites_data:
            channel_data = self.favorites_data[channel_name]

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
        channel_name = channel_name.lower().strip()
        if channel_name in self.favorites_data:
            current = self.favorites_data[channel_name].get("is_pinned", False)
            self.favorites_data[channel_name]["is_pinned"] = not current
            self._save_favorites()
            return not current
        return False

    def clear_favorites(self) -> None:
        """Clear all favorites"""
        self.favorites_data = {}
        self._save_favorites()
