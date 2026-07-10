"""Tests for ConfigManager validation and legacy setting migration."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from src.config_manager import ConfigManager
from src.constants import DEFAULT_SETTINGS


class TestConfigManagerValidation(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "test_settings.json"
        self.config = ConfigManager(self.config_path)

    def tearDown(self):
        if self.config_path.exists():
            self.config_path.unlink()
        os.rmdir(self.temp_dir)

    def test_defaults_are_the_clean_web_schema(self):
        settings = self.config.get_all()

        self.assertEqual(settings["window_width"], 1440)
        self.assertEqual(settings["window_height"], 850)
        for retired in ("player", "player_path", "player_args", "cache_duration"):
            self.assertNotIn(retired, settings)

    def test_every_default_setting_has_a_validator_branch(self):
        for key, value in DEFAULT_SETTINGS.items():
            with self.subTest(key=key):
                self.assertTrue(self.config._validate_setting(key, value))

    def test_legacy_quality_key_migrates_on_load(self):
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump({"quality": "720p"}, f)

        config = ConfigManager(self.config_path)

        self.assertEqual(config.get("preferred_quality"), "720p")
        self.assertNotIn("quality", config.get_all())

    def test_retired_keys_are_dropped_during_load(self):
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "preferred_quality": "best",
                    "player": "vlc",
                    "player_path": r"C:\Program Files\VideoLAN\VLC\vlc.exe",
                    "player_args": "--fullscreen",
                    "cache_duration": 30,
                    "enable_status_monitoring": True,
                    "status_check_interval": 300,
                    "status_cache_duration": 60,
                },
                f,
            )

        config = ConfigManager(self.config_path)

        for retired in (
            "player",
            "player_path",
            "player_args",
            "cache_duration",
            "enable_status_monitoring",
            "status_check_interval",
            "status_cache_duration",
        ):
            self.assertNotIn(retired, config.get_all())

        self.assertTrue(config.save_settings())
        saved = json.loads(self.config_path.read_text(encoding="utf-8"))
        for retired in ("player", "player_path", "player_args", "cache_duration"):
            self.assertNotIn(retired, saved)

    def test_retired_keys_are_rejected_for_runtime_updates(self):
        for retired in (
            "quality",
            "player",
            "player_path",
            "player_args",
            "cache_duration",
            "enable_status_monitoring",
            "status_check_interval",
            "status_cache_duration",
        ):
            with self.subTest(retired=retired):
                self.assertFalse(self.config.set(retired, "value"))
                self.assertNotIn(retired, self.config.get_all())

    def test_valid_quality_settings(self):
        for quality in ("best", "worst", "720p", "480p", "360p", "160p"):
            self.assertTrue(self.config.set("preferred_quality", quality))
            self.assertEqual(self.config.get("preferred_quality"), quality)

    def test_invalid_quality_settings(self):
        for quality in ("1080p", "4k", "ultra", "", None):
            self.assertFalse(self.config.set("preferred_quality", quality))

    def test_numeric_range_validation(self):
        for timeout in (10, 30, 120):
            self.assertTrue(self.config.set("network_timeout", timeout))
        for timeout in (9, 121, "30", None):
            self.assertFalse(self.config.set("network_timeout", timeout))

        for edge in (1, 3, 10):
            self.assertTrue(self.config.set("hls_live_edge", edge))
        for edge in (0, 11, "3", None):
            self.assertFalse(self.config.set("hls_live_edge", edge))

        for attempts in (1, 3, 10):
            self.assertTrue(self.config.set("connection_retry_attempts", attempts))
        for attempts in (0, 11, "3", None):
            self.assertFalse(self.config.set("connection_retry_attempts", attempts))

        for delay in (1, 5, 30):
            self.assertTrue(self.config.set("retry_delay", delay))
        for delay in (0, 31, "5", None):
            self.assertFalse(self.config.set("retry_delay", delay))

    def test_boolean_validation(self):
        boolean_settings = [
            "debug",
            "log_to_file",
            "dark_mode",
            "enable_network_diagnostics",
            "favorite_live_notifications_enabled",
            "favorite_live_highlight_test_mode",
            "favorite_live_notification_sound_enabled",
            "button_hover_sound_enabled",
            "show_stream_preview",
            "twitch_low_latency",
            "clip_enabled",
            "window_maximized",
            "stream_manager_left_sidebar_open",
            "stream_manager_right_sidebar_open",
            "stream_manager_activity_drawer_open",
            "auto_collapse_panels_enabled",
        ]

        for setting in boolean_settings:
            self.assertTrue(self.config.set(setting, True))
            self.assertTrue(self.config.set(setting, False))
            self.assertFalse(self.config.set(setting, "true"))
            self.assertFalse(self.config.set(setting, 1))
            self.assertFalse(self.config.set(setting, None))

    def test_stream_manager_clip_duration_validation(self):
        for seconds in (30, 60, 120, 300):
            self.assertTrue(self.config.set("stream_manager_clip_duration_seconds", seconds))
        for seconds in (0, 45, 301, "30", None):
            self.assertFalse(self.config.set("stream_manager_clip_duration_seconds", seconds))

    def test_log_level_validation(self):
        for level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            self.assertTrue(self.config.set("log_level", level))
            self.assertTrue(self.config.set("log_level", level.lower()))
        for level in ("TRACE", "FATAL", "", None):
            self.assertFalse(self.config.set("log_level", level))

    def test_batch_update_is_atomic(self):
        self.assertTrue(
            self.config.update(
                {
                    "preferred_quality": "480p",
                    "network_timeout": 45,
                    "debug": True,
                }
            )
        )

        self.assertFalse(
            self.config.update(
                {
                    "preferred_quality": "720p",
                    "network_timeout": 4,
                    "debug": False,
                }
            )
        )
        self.assertEqual(self.config.get("preferred_quality"), "480p")
        self.assertEqual(self.config.get("network_timeout"), 45)
        self.assertTrue(self.config.get("debug"))

    def test_validate_update_reports_failed_keys_without_mutation(self):
        original_quality = self.config.get("preferred_quality")
        failures = self.config.validate_update(
            {
                "preferred_quality": "invalid_quality",
                "quality": "720p",
                "network_timeout": 30,
            }
        )

        self.assertEqual(set(failures), {"preferred_quality", "quality"})
        self.assertEqual(self.config.get("preferred_quality"), original_quality)

    def test_save_settings_writes_valid_json(self):
        self.assertTrue(self.config.set("preferred_quality", "480p"))
        self.assertTrue(self.config.save_settings())

        data = json.loads(self.config_path.read_text(encoding="utf-8"))

        self.assertEqual(data["preferred_quality"], "480p")


if __name__ == "__main__":
    unittest.main()
