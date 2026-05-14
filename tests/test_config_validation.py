"""
Tests for ConfigManager validation enhancements
Tests the enhanced security-focused validation in configuration management.
"""

import unittest
import json
import tempfile
import os
from pathlib import Path

from src.config_manager import ConfigManager


class TestConfigManagerValidation(unittest.TestCase):
    """Test ConfigManager with enhanced validation"""

    def setUp(self):
        """Set up test with temporary config file"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "test_settings.json"
        self.config = ConfigManager(self.config_path)

    def tearDown(self):
        """Clean up temporary files"""
        if self.config_path.exists():
            self.config_path.unlink()
        os.rmdir(self.temp_dir)

    def test_valid_quality_settings(self):
        """Test valid quality settings"""
        valid_qualities = ["best", "worst", "720p", "480p", "360p", "160p"]
        for quality in valid_qualities:
            self.assertTrue(self.config.set("preferred_quality", quality))
            self.assertEqual(self.config.get("preferred_quality"), quality)

    def test_invalid_quality_settings(self):
        """Test invalid quality settings"""
        invalid_qualities = ["1080p", "4k", "ultra", "", None]
        for quality in invalid_qualities:
            self.assertFalse(self.config.set("preferred_quality", quality))

    def test_legacy_quality_key_is_rejected_for_runtime_updates(self):
        """Test old quality key is not accepted after load migration."""
        self.assertFalse(self.config.set("quality", "720p"))
        self.assertNotIn("quality", self.config.get_all())

    def test_legacy_quality_key_migrates_on_load(self):
        """Test legacy quality setting loads into preferred_quality and is removed."""
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump({"quality": "720p"}, f)

        config = ConfigManager(self.config_path)

        self.assertEqual(config.get("preferred_quality"), "720p")
        self.assertNotIn("quality", config.get_all())

    def test_valid_player_settings(self):
        """Test valid player settings"""
        valid_players = ["vlc", "mpv", "mpc-hc", "auto"]
        for player in valid_players:
            self.assertTrue(self.config.set("player", player))
            self.assertEqual(self.config.get("player"), player)

    def test_invalid_player_settings(self):
        """Test invalid player settings"""
        invalid_players = ["chrome", "unknown", "", None]
        for player in invalid_players:
            self.assertFalse(self.config.set("player", player))

    def test_numeric_range_validation(self):
        """Test numeric range validation for various settings"""
        # Cache duration validation (0-3600)
        self.assertTrue(self.config.set("cache_duration", 30))
        self.assertTrue(self.config.set("cache_duration", 0))
        self.assertTrue(self.config.set("cache_duration", 3600))
        self.assertFalse(self.config.set("cache_duration", -1))
        self.assertFalse(self.config.set("cache_duration", 3601))

        # Status check interval validation (10-86400)
        self.assertTrue(self.config.set("status_check_interval", 300))
        self.assertTrue(self.config.set("status_check_interval", 10))
        self.assertTrue(self.config.set("status_check_interval", 86400))
        self.assertFalse(self.config.set("status_check_interval", 9))
        self.assertFalse(self.config.set("status_check_interval", 86401))

        # Status cache duration validation (1-3600)
        self.assertTrue(self.config.set("status_cache_duration", 60))
        self.assertTrue(self.config.set("status_cache_duration", 1))
        self.assertTrue(self.config.set("status_cache_duration", 3600))
        self.assertFalse(self.config.set("status_cache_duration", 0))
        self.assertFalse(self.config.set("status_cache_duration", 3601))

    def test_boolean_validation(self):
        """Test boolean setting validation"""
        boolean_settings = ["debug", "log_to_file", "enable_status_monitoring"]

        for setting in boolean_settings:
            self.assertTrue(self.config.set(setting, True))
            self.assertTrue(self.config.set(setting, False))
            self.assertFalse(self.config.set(setting, "true"))
            self.assertFalse(self.config.set(setting, 1))
            self.assertFalse(self.config.set(setting, 0))
            self.assertFalse(self.config.set(setting, None))

    def test_log_level_validation(self):
        """Test log level validation"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        for level in valid_levels:
            self.assertTrue(self.config.set("log_level", level))
            self.assertTrue(self.config.set("log_level", level.lower()))

        invalid_levels = ["TRACE", "VERBOSE", "FATAL", "", None]
        for level in invalid_levels:
            self.assertFalse(self.config.set("log_level", level))

    def test_player_path_validation(self):
        """Test player path validation"""
        # Valid paths (not checking existence)
        valid_paths = [
            "/usr/bin/vlc",
            "C:\\Program Files\\VLC\\vlc.exe",
            "/Applications/VLC.app/Contents/MacOS/VLC",
        ]
        for path in valid_paths:
            self.assertTrue(self.config.set("player_path", path))

        # None should be allowed
        self.assertTrue(self.config.set("player_path", None))

        # Path traversal should be rejected
        malicious_paths = ["../../../etc/passwd", "..\\..\\windows\\system32\\cmd.exe"]
        for path in malicious_paths:
            self.assertFalse(self.config.set("player_path", path))

    def test_player_args_validation(self):
        """Test player args sanitization"""
        # Valid args
        valid_args = ["--fullscreen", "--volume=50", "--cache=yes", None]  # None should be allowed
        for args in valid_args:
            self.assertTrue(self.config.set("player_args", args))

        # Malicious args should be rejected
        malicious_args = [
            "--volume=50; rm -rf /",  # Command injection
            "--fullscreen && whoami",  # Command chaining
            "--cache=yes | id",  # Pipe command
            "--volume=50`id`",  # Backtick execution
        ]
        for args in malicious_args:
            self.assertFalse(self.config.set("player_args", args))

    def test_unknown_setting_handling(self):
        """Test unknown settings are rejected."""
        self.assertFalse(self.config.set("unknown_setting", "test_value"))
        self.assertFalse(self.config.set("custom_option", True))
        self.assertFalse(self.config.set("number_setting", 42))
        self.assertNotIn("unknown_setting", self.config.get_all())

    def test_validation_error_logging(self):
        """Test that validation errors are properly logged"""
        # This test ensures that validation failures don't raise exceptions
        # but return False and log warnings
        result = self.config.set("preferred_quality", "invalid_quality")
        self.assertFalse(result)

        result = self.config.set("cache_duration", -1)
        self.assertFalse(result)

        result = self.config.set("player_args", "malicious; rm -rf /")
        self.assertFalse(result)

    def test_batch_update_validation(self):
        """Test validation in batch updates"""
        # Valid batch update
        valid_settings = {
            "preferred_quality": "best",
            "player": "vlc",
            "cache_duration": 60,
            "debug": True,
        }
        self.assertTrue(self.config.update(valid_settings))

        # Batch update with invalid setting should fail entirely
        invalid_settings = {
            "preferred_quality": "best",
            "player": "vlc",
            "cache_duration": -1,  # Invalid
            "debug": True,
        }
        self.assertFalse(self.config.update(invalid_settings))

        # Verify original values weren't changed
        self.assertEqual(self.config.get("preferred_quality"), "best")
        self.assertEqual(self.config.get("cache_duration"), 60)  # Should still be 60

    def test_validate_update_reports_failed_keys_without_mutation(self):
        """Test batch validation reports all failed keys before applying settings."""
        original_quality = self.config.get("preferred_quality")
        failures = self.config.validate_update(
            {
                "preferred_quality": "invalid_quality",
                "quality": "720p",
                "cache_duration": 30,
            }
        )

        self.assertEqual(set(failures), {"preferred_quality", "quality"})
        self.assertEqual(self.config.get("preferred_quality"), original_quality)

    def test_save_settings_writes_valid_json(self):
        """Test atomic save path writes a complete JSON settings file."""
        self.assertTrue(self.config.set("preferred_quality", "480p"))
        self.assertTrue(self.config.save_settings())

        with open(self.config_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data["preferred_quality"], "480p")

    def test_theme_validation(self):
        """Test theme setting validation"""
        # Valid themes
        valid_themes = ["light", "dark"]
        for theme in valid_themes:
            with self.subTest(theme=theme):
                result = self.config.set("current_theme", theme)
                self.assertTrue(result, f"Theme '{theme}' should be valid")
                self.assertEqual(self.config.get("current_theme"), theme)

        # Invalid themes
        invalid_themes = ["blue", "green", "invalid", "", None, 123, True]
        for theme in invalid_themes:
            with self.subTest(theme=theme):
                result = self.config.set("current_theme", theme)
                self.assertFalse(result, f"Theme '{theme}' should be invalid")


if __name__ == "__main__":
    unittest.main()
