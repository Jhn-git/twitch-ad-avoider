"""
Tests for the TwitchViewer module
"""

import unittest
import os
import sys
from unittest.mock import patch, MagicMock

# Mock streamlink before importing TwitchViewer
sys.modules["streamlink"] = MagicMock()
sys.modules["shutil"] = MagicMock()

from src.twitch_viewer import TwitchViewer  # noqa: E402
from src.exceptions import ValidationError  # noqa: E402


class TestTwitchViewer(unittest.TestCase):
    def setUp(self):
        self.viewer = TwitchViewer()

    def test_config_manager_integration(self):
        settings = self.viewer.config.get_all()
        self.assertIsInstance(settings, dict)
        self.assertIn("preferred_quality", settings)
        self.assertIn("player", settings)
        self.assertIn("cache_duration", settings)

    def test_validate_channel_valid(self):
        valid_channels = ["ninja", "shroud", "test_channel", "test123"]
        for channel in valid_channels:
            validated = self.viewer._validate_channel(channel)
            self.assertEqual(validated, channel.lower())

    def test_validate_channel_invalid(self):
        # Updated test cases for enhanced validation
        invalid_channels = [
            "",  # Empty
            "ab",  # Too short
            "abc",  # Still too short (min 4 chars)
            "test$channel",  # Invalid character
            "a" * 26,  # Too long (max 25 chars)
            "../../../etc/passwd",  # Path traversal
            "test;whoami",  # Command injection
            "test\x00name",  # Control character
        ]
        for channel in invalid_channels:
            with self.assertRaises(ValidationError):
                self.viewer._validate_channel(channel)

    def test_get_supported_players(self):
        players = self.viewer._get_supported_players()
        self.assertIsInstance(players, dict)
        self.assertIn("vlc", players)
        self.assertIn("mpv", players)
        self.assertIn("mpc-hc", players)

    def test_get_common_player_paths(self):
        paths = self.viewer._get_common_player_paths()
        self.assertIsInstance(paths, dict)
        self.assertIn("vlc", paths)
        self.assertIn("mpv", paths)
        self.assertIn("mpc-hc", paths)

    @patch.dict(
        os.environ, {"TWITCH_PLAYER_PATH": "C:\\fake\\path\\vlc.exe", "TWITCH_PLAYER_NAME": "VLC"}
    )
    @patch("os.path.exists")
    def test_check_environment_player_found(self, mock_exists):
        mock_exists.return_value = True
        result = self.viewer._check_environment_player()
        self.assertEqual(result, "vlc")
        self.assertEqual(self.viewer.player_path, "C:\\fake\\path\\vlc.exe")

    @patch.dict(os.environ, {}, clear=True)
    def test_check_environment_player_not_found(self):
        result = self.viewer._check_environment_player()
        self.assertIsNone(result)

    @patch("os.path.exists")
    def test_check_manual_player_found(self, mock_exists):
        mock_exists.return_value = True
        self.viewer.config.set("player_path", "C:\\manual\\vlc.exe")
        self.viewer.config.set("player", "vlc")
        result = self.viewer._check_manual_player()
        self.assertEqual(result, "vlc")
        self.assertEqual(self.viewer.player_path, "C:\\manual\\vlc.exe")

    @patch("os.path.exists")
    def test_check_manual_player_not_found(self, mock_exists):
        mock_exists.return_value = False
        # Ensure no manual player path is configured
        self.viewer.config.set("player_path", None)
        result = self.viewer._check_manual_player()
        self.assertIsNone(result)

    @patch("shutil.which")
    def test_check_player_in_path_found(self, mock_which):
        mock_which.return_value = "/usr/bin/vlc"
        result = self.viewer._check_player_in_path("vlc", ["vlc", "vlc.exe"])
        self.assertEqual(result, "vlc")
        self.assertEqual(self.viewer.player_path, "/usr/bin/vlc")

    @patch("shutil.which")
    def test_check_player_in_path_not_found(self, mock_which):
        mock_which.return_value = None
        result = self.viewer._check_player_in_path("vlc", ["vlc", "vlc.exe"])
        self.assertIsNone(result)

    @patch("os.path.exists")
    def test_check_player_common_paths_found(self, mock_exists):
        mock_exists.return_value = True
        paths = ["C:\\Program Files\\VideoLAN\\VLC\\vlc.exe"]
        result = self.viewer._check_player_common_paths("vlc", paths)
        self.assertEqual(result, "vlc")
        self.assertEqual(self.viewer.player_path, "C:\\Program Files\\VideoLAN\\VLC\\vlc.exe")

    @patch("os.path.exists")
    def test_check_player_common_paths_not_found(self, mock_exists):
        mock_exists.return_value = False
        paths = ["C:\\Program Files\\VideoLAN\\VLC\\vlc.exe"]
        result = self.viewer._check_player_common_paths("vlc", paths)
        self.assertIsNone(result)

    @patch.object(TwitchViewer, "_check_environment_player")
    def test_detect_player_environment_success(self, mock_env):
        mock_env.return_value = "vlc"
        result = self.viewer._detect_player()
        self.assertEqual(result, "vlc")

    @patch("os.path.exists")
    def test_detect_player_manual_success(self, mock_exists):
        # Set manual player path exists
        mock_exists.return_value = True
        self.viewer.config.set("player_path", "/manual/path/mpv")
        self.viewer.config.set("player", "mpv")
        result = self.viewer._detect_player()
        self.assertEqual(result, "mpv")
        self.assertEqual(self.viewer.player_path, "/manual/path/mpv")

    @patch.object(TwitchViewer, "_check_environment_player")
    @patch.object(TwitchViewer, "_check_manual_player")
    @patch.object(TwitchViewer, "_check_player_in_path")
    @patch.object(TwitchViewer, "_check_player_common_paths")
    def test_detect_player_fallback_to_auto(
        self, mock_common_paths, mock_path, mock_manual, mock_env
    ):
        mock_env.return_value = None
        mock_manual.return_value = None
        mock_path.return_value = None
        mock_common_paths.return_value = None
        result = self.viewer._detect_player()
        self.assertEqual(result, "auto")
        self.assertIsNone(self.viewer.player_path)

    def test_set_player_choice_valid(self):
        valid_players = ["vlc", "mpv", "mpc-hc", "auto"]
        for player in valid_players:
            self.viewer.set_player_choice(player)
            self.assertEqual(self.viewer.selected_player, player)
            self.assertIsNone(self.viewer.player_path)  # Should reset player path

    def test_set_player_choice_resets_path(self):
        # Set initial state
        self.viewer.player_path = "/some/path/vlc.exe"
        self.viewer.selected_player = "vlc"

        # Change player choice
        self.viewer.set_player_choice("mpv")

        # Verify path is reset
        self.assertEqual(self.viewer.selected_player, "mpv")
        self.assertIsNone(self.viewer.player_path)

    @patch.object(TwitchViewer, "_check_streamlink_availability")
    def test_is_streamlink_available_success(self, mock_check):
        mock_check.return_value = True
        result = self.viewer.is_streamlink_available()
        self.assertTrue(result)
        mock_check.assert_called_once()

    @patch.object(TwitchViewer, "_check_streamlink_availability")
    def test_is_streamlink_available_failure(self, mock_check):
        mock_check.return_value = False
        result = self.viewer.is_streamlink_available()
        self.assertFalse(result)
        mock_check.assert_called_once()

    def test_check_streamlink_availability_success(self):
        # Mock the session.streams method to return empty dict (no exception)
        self.viewer.session.streams = MagicMock(return_value={})
        result = self.viewer._check_streamlink_availability()
        self.assertTrue(result)

    def test_check_streamlink_availability_failure(self):
        # Mock the session.streams method to raise an exception
        self.viewer.session.streams = MagicMock(side_effect=Exception("Streamlink error"))
        result = self.viewer._check_streamlink_availability()
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
