"""
Tests for the TwitchViewer module
"""
import unittest
import os
from unittest.mock import patch, MagicMock
from pathlib import Path
from src.twitch_viewer import TwitchViewer, TwitchStreamError

class TestTwitchViewer(unittest.TestCase):
    def setUp(self):
        self.viewer = TwitchViewer()

    def test_load_settings(self):
        settings = self.viewer._load_settings()
        self.assertIsInstance(settings, dict)
        self.assertIn('preferred_quality', settings)
        self.assertIn('player', settings)
        self.assertIn('cache_duration', settings)

    def test_validate_channel_valid(self):
        valid_channels = ['ninja', 'shroud', 'test_channel', 'test123']
        for channel in valid_channels:
            validated = self.viewer._validate_channel(channel)
            self.assertEqual(validated, channel.lower())

    def test_validate_channel_invalid(self):
        invalid_channels = ['', 'ab', 'test$channel', 'very_very_very_long_channel_name']
        for channel in invalid_channels:
            with self.assertRaises(ValueError):
                self.viewer._validate_channel(channel)

    def test_get_supported_players(self):
        players = self.viewer._get_supported_players()
        self.assertIsInstance(players, dict)
        self.assertIn('vlc', players)
        self.assertIn('mpv', players)
        self.assertIn('mpc-hc', players)

    def test_get_common_player_paths(self):
        paths = self.viewer._get_common_player_paths()
        self.assertIsInstance(paths, dict)
        self.assertIn('vlc', paths)
        self.assertIn('mpv', paths)
        self.assertIn('mpc-hc', paths)

    @patch.dict(os.environ, {'TWITCH_PLAYER_PATH': 'C:\\fake\\path\\vlc.exe', 'TWITCH_PLAYER_NAME': 'VLC'})
    @patch('os.path.exists')
    def test_check_environment_player_found(self, mock_exists):
        mock_exists.return_value = True
        result = self.viewer._check_environment_player()
        self.assertEqual(result, 'vlc')
        self.assertEqual(self.viewer.player_path, 'C:\\fake\\path\\vlc.exe')

    @patch.dict(os.environ, {}, clear=True)
    def test_check_environment_player_not_found(self):
        result = self.viewer._check_environment_player()
        self.assertIsNone(result)

    @patch('os.path.exists')
    def test_check_manual_player_found(self, mock_exists):
        mock_exists.return_value = True
        self.viewer.settings['player_path'] = 'C:\\manual\\vlc.exe'
        self.viewer.settings['player'] = 'vlc'
        result = self.viewer._check_manual_player()
        self.assertEqual(result, 'vlc')
        self.assertEqual(self.viewer.player_path, 'C:\\manual\\vlc.exe')

    def test_check_manual_player_not_found(self):
        result = self.viewer._check_manual_player()
        self.assertIsNone(result)

    @patch('shutil.which')
    def test_check_player_in_path_found(self, mock_which):
        mock_which.return_value = '/usr/bin/vlc'
        result = self.viewer._check_player_in_path('vlc', ['vlc', 'vlc.exe'])
        self.assertEqual(result, 'vlc')
        self.assertEqual(self.viewer.player_path, '/usr/bin/vlc')

    @patch('shutil.which')
    def test_check_player_in_path_not_found(self, mock_which):
        mock_which.return_value = None
        result = self.viewer._check_player_in_path('vlc', ['vlc', 'vlc.exe'])
        self.assertIsNone(result)

    @patch('os.path.exists')
    def test_check_player_common_paths_found(self, mock_exists):
        mock_exists.return_value = True
        paths = ['C:\\Program Files\\VideoLAN\\VLC\\vlc.exe']
        result = self.viewer._check_player_common_paths('vlc', paths)
        self.assertEqual(result, 'vlc')
        self.assertEqual(self.viewer.player_path, 'C:\\Program Files\\VideoLAN\\VLC\\vlc.exe')

    @patch('os.path.exists')
    def test_check_player_common_paths_not_found(self, mock_exists):
        mock_exists.return_value = False
        paths = ['C:\\Program Files\\VideoLAN\\VLC\\vlc.exe']
        result = self.viewer._check_player_common_paths('vlc', paths)
        self.assertIsNone(result)

    @patch.object(TwitchViewer, '_check_environment_player')
    def test_detect_player_environment_success(self, mock_env):
        mock_env.return_value = 'vlc'
        result = self.viewer._detect_player()
        self.assertEqual(result, 'vlc')

    @patch.object(TwitchViewer, '_check_environment_player')
    @patch.object(TwitchViewer, '_check_manual_player')
    def test_detect_player_manual_success(self, mock_manual, mock_env):
        mock_env.return_value = None
        mock_manual.return_value = 'mpv'
        result = self.viewer._detect_player()
        self.assertEqual(result, 'mpv')

    @patch.object(TwitchViewer, '_check_environment_player')
    @patch.object(TwitchViewer, '_check_manual_player')
    @patch.object(TwitchViewer, '_check_player_in_path')
    def test_detect_player_fallback_to_auto(self, mock_path, mock_manual, mock_env):
        mock_env.return_value = None
        mock_manual.return_value = None
        mock_path.return_value = None
        result = self.viewer._detect_player()
        self.assertEqual(result, 'auto')
        self.assertIsNone(self.viewer.player_path)

if __name__ == '__main__':
    unittest.main()
