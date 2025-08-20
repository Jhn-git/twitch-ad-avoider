"""
Favorites Manager for TwitchAdAvoider GUI
Handles storage and management of favorite channels
"""
import json
import os
from pathlib import Path

class FavoritesManager:
    def __init__(self, favorites_file=None):
        self.favorites_file = favorites_file or Path("config/favorites.json")
        self.favorites = self._load_favorites()
    
    def _load_favorites(self):
        """Load favorites from JSON file"""
        if os.path.exists(self.favorites_file):
            try:
                with open(self.favorites_file, 'r') as f:
                    data = json.load(f)
                    return data.get('favorites', [])
            except (json.JSONDecodeError, KeyError):
                return []
        return []
    
    def _save_favorites(self):
        """Save favorites to JSON file"""
        os.makedirs(os.path.dirname(self.favorites_file), exist_ok=True)
        data = {
            'favorites': sorted(set(self.favorites))
        }
        with open(self.favorites_file, 'w') as f:
            json.dump(data, f, indent=4)
    
    def add_favorite(self, channel_name):
        """Add a channel to favorites"""
        channel_name = channel_name.lower().strip()
        if channel_name and channel_name not in self.favorites:
            self.favorites.append(channel_name)
            self._save_favorites()
            return True
        return False
    
    def remove_favorite(self, channel_name):
        """Remove a channel from favorites"""
        channel_name = channel_name.lower().strip()
        if channel_name in self.favorites:
            self.favorites.remove(channel_name)
            self._save_favorites()
            return True
        return False
    
    def get_favorites(self):
        """Get list of favorite channels"""
        return sorted(self.favorites)
    
    def is_favorite(self, channel_name):
        """Check if a channel is in favorites"""
        return channel_name.lower().strip() in self.favorites
    
    def clear_favorites(self):
        """Clear all favorites"""
        self.favorites = []
        self._save_favorites()