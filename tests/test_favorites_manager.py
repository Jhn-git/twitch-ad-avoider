"""
Tests for FavoritesManager data persistence.

Critical tests for:
- Favorites CRUD operations
- JSON persistence and atomic saves
- Backward compatibility (format migration)
- Status tracking and datetime handling
- Data integrity
"""

import unittest
import json
import tempfile
import os
from pathlib import Path
from datetime import datetime, timezone

from src.favorites_manager import FavoritesManager, FavoriteChannelInfo


class TestFavoritesManager(unittest.TestCase):
    """Test FavoritesManager functionality"""

    def setUp(self):
        """Set up test with temporary favorites file"""
        self.temp_dir = tempfile.mkdtemp()
        self.favorites_file = Path(self.temp_dir) / "test_favorites.json"
        self.manager = FavoritesManager(self.favorites_file)

    def tearDown(self):
        """Clean up temporary files"""
        if self.favorites_file.exists():
            self.favorites_file.unlink()
        os.rmdir(self.temp_dir)

    def test_initialization_empty(self):
        """Test manager initializes with empty data when no file exists"""
        self.assertEqual(len(self.manager.favorites_data), 0)
        self.assertFalse(self.favorites_file.exists())

    def test_add_favorite(self):
        """Test adding a favorite channel"""
        result = self.manager.add_favorite("ninja")

        self.assertTrue(result)
        self.assertTrue(self.manager.is_favorite("ninja"))
        self.assertIn("ninja", self.manager.favorites_data)

        # Verify file was created
        self.assertTrue(self.favorites_file.exists())

    def test_add_favorite_uppercase(self):
        """Test adding favorite converts to lowercase"""
        self.manager.add_favorite("NINJA")

        self.assertTrue(self.manager.is_favorite("ninja"))
        self.assertTrue(self.manager.is_favorite("NINJA"))
        self.assertIn("ninja", self.manager.favorites_data)

    def test_add_favorite_with_whitespace(self):
        """Test adding favorite strips whitespace"""
        self.manager.add_favorite("  ninja  ")

        self.assertTrue(self.manager.is_favorite("ninja"))
        self.assertIn("ninja", self.manager.favorites_data)

    def test_add_favorite_duplicate(self):
        """Test adding duplicate favorite returns False"""
        self.manager.add_favorite("ninja")
        result = self.manager.add_favorite("ninja")

        self.assertFalse(result)
        # Should still only have one entry
        self.assertEqual(len(self.manager.get_favorites()), 1)

    def test_add_favorite_empty_string(self):
        """Test adding empty string returns False"""
        result = self.manager.add_favorite("")

        self.assertFalse(result)
        self.assertEqual(len(self.manager.get_favorites()), 0)

    def test_add_favorite_rejects_invalid_channel(self):
        """Test adding invalid favorite input returns False and does not persist."""
        result = self.manager.add_favorite("test;whoami")

        self.assertFalse(result)
        self.assertEqual(self.manager.get_favorites(), [])
        self.assertFalse(self.favorites_file.exists())

    def test_remove_favorite(self):
        """Test removing a favorite channel"""
        self.manager.add_favorite("ninja")
        result = self.manager.remove_favorite("ninja")

        self.assertTrue(result)
        self.assertFalse(self.manager.is_favorite("ninja"))
        self.assertNotIn("ninja", self.manager.favorites_data)

    def test_remove_favorite_not_exist(self):
        """Test removing non-existent favorite returns False"""
        result = self.manager.remove_favorite("nonexistent")

        self.assertFalse(result)

    def test_get_favorites_empty(self):
        """Test get_favorites returns empty list when no favorites"""
        favorites = self.manager.get_favorites()

        self.assertEqual(favorites, [])
        self.assertIsInstance(favorites, list)

    def test_get_favorites_sorted(self):
        """Test get_favorites returns sorted list"""
        self.manager.add_favorite("zebra")
        self.manager.add_favorite("alpha")
        self.manager.add_favorite("middle")

        favorites = self.manager.get_favorites()

        self.assertEqual(favorites, ["alpha", "middle", "zebra"])

    def test_clear_favorites(self):
        """Test clearing all favorites"""
        self.manager.add_favorite("ninja")
        self.manager.add_favorite("shroud")

        self.manager.clear_favorites()

        self.assertEqual(len(self.manager.get_favorites()), 0)
        self.assertEqual(len(self.manager.favorites_data), 0)

        # File should still exist but be empty
        self.assertTrue(self.favorites_file.exists())

    def test_save_and_load_persistence(self):
        """Test favorites persist across manager instances"""
        self.manager.add_favorite("ninja")
        self.manager.add_favorite("shroud")

        # Create new manager instance with same file
        manager2 = FavoritesManager(self.favorites_file)

        self.assertEqual(set(manager2.get_favorites()), {"ninja", "shroud"})
        self.assertTrue(manager2.is_favorite("ninja"))
        self.assertTrue(manager2.is_favorite("shroud"))

    def test_update_channel_status(self):
        """Test updating channel status"""
        self.manager.add_favorite("ninja")

        # Update to live
        self.manager.update_channel_status("ninja", is_live=True)

        # Verify status
        info = self.manager.get_channel_info("ninja")
        self.assertIsNotNone(info)
        self.assertTrue(info.is_live)
        self.assertIsNotNone(info.last_checked)
        self.assertIsNotNone(info.last_seen_live)

    def test_update_channel_status_offline(self):
        """Test updating channel status to offline"""
        self.manager.add_favorite("ninja")

        # Update to live first
        self.manager.update_channel_status("ninja", is_live=True)
        first_last_seen = self.manager.get_channel_info("ninja").last_seen_live

        # Update to offline
        self.manager.update_channel_status("ninja", is_live=False)

        info = self.manager.get_channel_info("ninja")
        self.assertFalse(info.is_live)
        self.assertIsNotNone(info.last_checked)
        # last_seen_live should still be set from when it was live
        self.assertEqual(info.last_seen_live, first_last_seen)

    def test_update_channel_status_not_favorite(self):
        """Test updating status of non-favorite does nothing"""
        # Should not crash
        self.manager.update_channel_status("notfavorite", is_live=True)

        # Channel should not be added
        self.assertFalse(self.manager.is_favorite("notfavorite"))

    def test_get_favorites_with_status(self):
        """Test getting favorites with status information"""
        self.manager.add_favorite("ninja")
        self.manager.add_favorite("shroud")

        self.manager.update_channel_status("ninja", is_live=True)

        favorites = self.manager.get_favorites_with_status()

        self.assertEqual(len(favorites), 2)
        self.assertIsInstance(favorites[0], FavoriteChannelInfo)

        # Find ninja in the list
        ninja_info = next(f for f in favorites if f.channel_name == "ninja")
        self.assertTrue(ninja_info.is_live)
        self.assertIsNotNone(ninja_info.last_checked)

    def test_get_favorites_with_status_sorts_live_first(self):
        """Test live favorites are returned before offline favorites."""
        self.manager.add_favorite("zebra")
        self.manager.add_favorite("alpha")
        self.manager.add_favorite("middle")
        self.manager.toggle_pin("middle")

        self.manager.update_channel_status("zebra", is_live=True)

        favorites = self.manager.get_favorites_with_status()

        self.assertEqual([fav.channel_name for fav in favorites], ["zebra", "middle", "alpha"])

    def test_get_channel_info_exists(self):
        """Test getting channel info for existing favorite"""
        self.manager.add_favorite("ninja")
        self.manager.update_channel_status("ninja", is_live=True)

        info = self.manager.get_channel_info("ninja")

        self.assertIsNotNone(info)
        self.assertEqual(info.channel_name, "ninja")
        self.assertTrue(info.is_live)

    def test_get_channel_info_not_exists(self):
        """Test getting channel info for non-existent favorite"""
        info = self.manager.get_channel_info("nonexistent")

        self.assertIsNone(info)

    def test_is_favorite_case_insensitive(self):
        """Test is_favorite is case-insensitive"""
        self.manager.add_favorite("ninja")

        self.assertTrue(self.manager.is_favorite("ninja"))
        self.assertTrue(self.manager.is_favorite("NINJA"))
        self.assertTrue(self.manager.is_favorite("Ninja"))

    def test_datetime_serialization(self):
        """Test datetime objects are properly serialized to JSON"""
        self.manager.add_favorite("ninja")
        self.manager.update_channel_status("ninja", is_live=True)

        # Read raw JSON
        with open(self.favorites_file, "r") as f:
            data = json.load(f)

        # Check that datetimes are strings in JSON
        ninja_data = data["channels"]["ninja"]
        self.assertIsInstance(ninja_data["last_checked"], str)
        self.assertIsInstance(ninja_data["last_seen_live"], str)

        # Verify ISO format
        datetime.fromisoformat(ninja_data["last_checked"])
        datetime.fromisoformat(ninja_data["last_seen_live"])

    def test_datetime_deserialization(self):
        """Test datetime strings are properly loaded as datetime objects"""
        self.manager.add_favorite("ninja")
        self.manager.update_channel_status("ninja", is_live=True)

        # Create new manager to force load
        manager2 = FavoritesManager(self.favorites_file)
        info = manager2.get_channel_info("ninja")

        self.assertIsInstance(info.last_checked, datetime)
        self.assertIsInstance(info.last_seen_live, datetime)

    def test_backward_compatibility_old_format(self):
        """Test loading old format (list of strings) migrates to new format"""
        # Create old format favorites file
        old_format = {"favorites": ["ninja", "shroud", "pokimane", "bad;channel"]}
        with open(self.favorites_file, "w") as f:
            json.dump(old_format, f)

        # Load with FavoritesManager
        manager = FavoritesManager(self.favorites_file)

        # Verify channels were migrated
        favorites = manager.get_favorites()
        self.assertEqual(set(favorites), {"ninja", "shroud", "pokimane"})

        # Verify new format has status fields
        for channel in favorites:
            info = manager.get_channel_info(channel)
            self.assertFalse(info.is_live)
            self.assertIsNone(info.last_checked)
            self.assertIsNone(info.last_seen_live)

        with open(self.favorites_file, "r") as f:
            data = json.load(f)
        self.assertIn("channels", data)
        self.assertNotIn("bad;channel", data["channels"])

    def test_backward_compatibility_corrupted_file(self):
        """Test handling of corrupted favorites file"""
        # Write corrupted JSON
        with open(self.favorites_file, "w") as f:
            f.write("{corrupted json content")

        # Should handle gracefully and start empty
        manager = FavoritesManager(self.favorites_file)
        self.assertEqual(len(manager.get_favorites()), 0)

    def test_version_in_saved_file(self):
        """Test that version is saved in JSON file"""
        self.manager.add_favorite("ninja")

        with open(self.favorites_file, "r") as f:
            data = json.load(f)

        self.assertIn("version", data)
        self.assertEqual(data["version"], "2.0")

    def test_new_format_structure(self):
        """Test that new format has correct structure"""
        self.manager.add_favorite("ninja")

        with open(self.favorites_file, "r") as f:
            data = json.load(f)

        self.assertIn("channels", data)
        self.assertIn("ninja", data["channels"])
        self.assertIn("channel_name", data["channels"]["ninja"])
        self.assertIn("is_live", data["channels"]["ninja"])
        self.assertIn("last_checked", data["channels"]["ninja"])
        self.assertIn("last_seen_live", data["channels"]["ninja"])

    def test_favorite_channel_info_namedtuple(self):
        """Test FavoriteChannelInfo namedtuple properties"""
        now = datetime.now(timezone.utc)
        info = FavoriteChannelInfo(
            channel_name="ninja", is_live=True, last_checked=now, last_seen_live=now
        )

        self.assertEqual(info.channel_name, "ninja")
        self.assertTrue(info.is_live)
        self.assertEqual(info.last_checked, now)
        self.assertEqual(info.last_seen_live, now)

        # Test immutability
        with self.assertRaises(AttributeError):
            info.channel_name = "shroud"

    def test_concurrent_status_updates(self):
        """Test multiple status updates maintain data integrity"""
        self.manager.add_favorite("ninja")

        # Simulate multiple rapid status updates
        for i in range(10):
            self.manager.update_channel_status("ninja", is_live=(i % 2 == 0))

        # Should have consistent data
        info = self.manager.get_channel_info("ninja")
        self.assertIsNotNone(info)
        self.assertIsNotNone(info.last_checked)

    def test_invalid_datetime_handling(self):
        """Test handling of invalid datetime strings in file"""
        # Create file with invalid datetime
        data = {
            "channels": {
                "ninja": {
                    "channel_name": "ninja",
                    "is_live": False,
                    "last_checked": "invalid-datetime",
                    "last_seen_live": "also-invalid",
                }
            },
            "version": "2.0",
        }
        with open(self.favorites_file, "w") as f:
            json.dump(data, f)

        manager = FavoritesManager(self.favorites_file)
        info = manager.get_channel_info("ninja")

        # Should handle gracefully by setting to None
        self.assertIsNone(info.last_checked)
        self.assertIsNone(info.last_seen_live)

    def test_new_format_drops_invalid_channels_and_cleans_file(self):
        """Test invalid new-format favorite records are removed on load."""
        data = {
            "channels": {
                "ninja": {
                    "channel_name": "NINJA",
                    "is_live": True,
                    "is_pinned": True,
                    "last_checked": None,
                    "last_seen_live": None,
                },
                "bad;channel": {
                    "channel_name": "bad;channel",
                    "is_live": True,
                    "is_pinned": False,
                    "last_checked": None,
                    "last_seen_live": None,
                },
            },
            "version": "2.0",
        }
        with open(self.favorites_file, "w") as f:
            json.dump(data, f)

        manager = FavoritesManager(self.favorites_file)

        self.assertEqual(manager.get_favorites(), ["ninja"])
        info = manager.get_channel_info("ninja")
        self.assertTrue(info.is_live)
        self.assertTrue(info.is_pinned)

        with open(self.favorites_file, "r") as f:
            cleaned = json.load(f)
        self.assertEqual(list(cleaned["channels"].keys()), ["ninja"])
        self.assertEqual(cleaned["channels"]["ninja"]["channel_name"], "ninja")


if __name__ == "__main__":
    unittest.main()
