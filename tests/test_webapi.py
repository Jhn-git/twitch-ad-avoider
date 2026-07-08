"""Tests for the JS-callable pywebview API bridge."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src.config_manager import ConfigManager
from src.favorites_manager import FavoritesManager
from webapi import TwitchViewerAPI


class FakeStreamService:
    def __init__(self, *_args, **_kwargs):
        self.state = {
            "active": False,
            "channel": None,
            "quality": "best",
            "playback_url": None,
            "status": "idle",
            "recording": False,
            "last_error": None,
        }
        self.shutdown_called = False

    def get_state(self):
        return self.state.copy()

    def start(self, channel, quality):
        self.state.update(
            {
                "active": True,
                "channel": channel,
                "quality": quality,
                "playback_url": "http://127.0.0.1:1234/playlist/abc.m3u8",
                "status": "live",
                "recording": True,
            }
        )
        return self.get_state()

    def stop(self):
        self.state.update({"active": False, "channel": None, "status": "idle", "recording": False})
        return self.get_state()

    def create_clip(self, duration_seconds):
        return {"ok": True, "path": f"clips/test-{duration_seconds}.mp4"}

    def shutdown(self):
        self.shutdown_called = True


class TestTwitchViewerAPI(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config = ConfigManager(Path(self.temp_dir) / "settings.json")
        self.favorites_path = Path(self.temp_dir) / "favorites.json"

    def tearDown(self):
        for child in Path(self.temp_dir).glob("*"):
            if child.is_file():
                child.unlink()
        os.rmdir(self.temp_dir)

    def make_api(self, **kwargs):
        manager = FavoritesManager(self.favorites_path)
        patches = [
            patch("webapi.FavoritesManager", return_value=manager),
            patch("webapi.WebStreamService", FakeStreamService),
        ]
        self.preview_fetch = Mock(
            return_value=Mock(
                channel="testuser",
                is_live=True,
                title="Live title",
                preview_image_url=None,
                profile_image_url="https://example.com/profile.jpg",
            )
        )
        patches.append(patch("webapi.fetch_stream_preview_info", self.preview_fetch))
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)
        return TwitchViewerAPI(self.config, **kwargs)

    def test_initial_state_contains_clean_settings_and_launch_channel(self):
        api = self.make_api(launch_channel="TestUser")

        state = api.get_initial_state()

        self.assertEqual(state["selected_channel"], "testuser")
        self.assertEqual(state["preview"]["title"], "Live title")
        self.assertEqual(state["preview"]["profile_image_url"], "https://example.com/profile.jpg")
        for retired in ("player", "player_path", "player_args", "cache_duration"):
            self.assertNotIn(retired, state["settings"])

    def test_initial_favorite_payload_uses_cached_profile_image(self):
        api = self.make_api()
        api.add_favorite("TestUser")

        state = api.get_initial_state()

        self.assertEqual(state["favorites"][0]["channel_name"], "testuser")
        self.assertEqual(
            state["favorites"][0]["profile_image_url"],
            "https://example.com/profile.jpg",
        )

    def test_select_channel_does_not_fetch_preview(self):
        api = self.make_api()
        self.preview_fetch.reset_mock()

        result = api.select_channel("TestUser")

        self.assertTrue(result["ok"])
        self.assertEqual(result["selected_channel"], "testuser")
        self.assertIsNone(result["preview"]["profile_image_url"])
        self.preview_fetch.assert_not_called()

    def test_get_preview_caches_profile_for_favorite_payload(self):
        api = self.make_api()
        api.add_favorite("TestUser")

        preview = api.get_preview("testuser")
        favorites = api.get_favorites()

        self.assertTrue(preview["ok"])
        self.assertEqual(preview["preview"]["profile_image_url"], "https://example.com/profile.jpg")
        self.assertEqual(favorites[0]["profile_image_url"], "https://example.com/profile.jpg")

    def test_favorites_crud_and_pin(self):
        api = self.make_api()

        added = api.add_favorite("TestUser")
        pinned = api.toggle_pin("testuser")
        removed = api.remove_favorite("testuser")

        self.assertTrue(added["ok"])
        self.assertTrue(pinned["is_pinned"])
        self.assertTrue(removed["ok"])
        self.assertEqual(removed["favorites"], [])

    def test_start_stop_and_clip_delegate_to_stream_service(self):
        api = self.make_api(launch_channel="testuser")

        started = api.start_stream(quality="best")
        clipped = api.create_clip(60)
        stopped = api.stop_stream()

        self.assertTrue(started["ok"])
        self.assertEqual(started["stream"]["channel"], "testuser")
        self.assertEqual(clipped["path"], "clips/test-60.mp4")
        self.assertFalse(stopped["stream"]["active"])

    def test_settings_validation_rejects_unknown_or_retired_keys(self):
        api = self.make_api()

        self.assertFalse(api.validate_setting("player", "vlc")["ok"])
        self.assertFalse(api.save_settings({"player_args": "--fullscreen"})["ok"])
        self.assertTrue(api.save_settings({"preferred_quality": "480p"})["ok"])

    def test_window_push_uses_json_payload(self):
        api = self.make_api()
        window = Mock()
        api.set_window(window)

        api._add_activity("info", "hello", "TEST")

        script = window.evaluate_js.call_args.args[0]
        self.assertIn("window.__onActivity", script)
        self.assertIn('"message": "hello"', script)


if __name__ == "__main__":
    unittest.main()
