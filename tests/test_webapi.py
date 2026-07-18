"""Tests for the JS-callable pywebview API bridge."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src.favorites_manager import FavoritesManager
from src.config_manager import ConfigManager
from src.webapi import TwitchViewerAPI


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

    def create_clip(self, duration_seconds, behind_live_seconds=0.0):
        self.last_clip_args = (duration_seconds, behind_live_seconds)
        return {"ok": True, "path": f"clips/test-{duration_seconds}.mp4"}

    def shutdown(self):
        self.shutdown_called = True

    def purge_expired_recordings(self):
        pass

    def get_recording_segments(self, channel):
        self.last_segments_channel = channel
        return {
            "channel": channel,
            "stream_created_at": None,
            "segments": [],
            "now": "2026-07-18T00:00:00",
        }


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
            patch("src.webapi.FavoritesManager", return_value=manager),
            patch("src.webapi.WebStreamService", FakeStreamService),
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
        patches.append(patch("src.webapi.fetch_stream_preview_info", self.preview_fetch))
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

    def test_create_clip_forwards_behind_live_seconds(self):
        api = self.make_api(launch_channel="testuser")

        clipped = api.create_clip(60, 12.5)

        self.assertTrue(clipped["ok"])
        self.assertEqual(api._stream_service.last_clip_args, (60, 12.5))

    def test_get_recording_segments_forwards_selected_channel(self):
        api = self.make_api(launch_channel="testuser")

        result = api.get_recording_segments()

        self.assertTrue(result["ok"])
        self.assertEqual(api._stream_service.last_segments_channel, "testuser")
        self.assertEqual(result["segments"]["channel"], "testuser")

    def test_get_recording_segments_requires_a_channel(self):
        api = self.make_api()

        result = api.get_recording_segments()

        self.assertFalse(result["ok"])

    def test_settings_validation_rejects_unknown_or_retired_keys(self):
        api = self.make_api()

        self.assertFalse(api.validate_setting("player", "vlc")["ok"])
        self.assertFalse(api.save_settings({"player_args": "--fullscreen"})["ok"])
        self.assertTrue(api.save_settings({"preferred_quality": "480p"})["ok"])

    def test_shutdown_suppresses_js_push_to_avoid_ui_thread_deadlock(self):
        # shutdown() runs synchronously on the closing event's UI thread; any JS
        # push during/after it would call evaluate_js and deadlock waiting on a
        # continuation only that same (blocked) thread could deliver.
        api = self.make_api()
        window = Mock()
        api.set_window(window)

        api.shutdown()
        window.evaluate_js.reset_mock()
        api._add_activity("info", "late push", "TEST")
        api._on_stream_event({"type": "stopped", "state": {}})

        window.evaluate_js.assert_not_called()

    def test_refresh_favorites_updates_status_and_pushes_update(self):
        api = self.make_api()
        api.add_favorite("TestUser")
        window = Mock()
        api.set_window(window)
        with patch.object(api._status_monitor, "check_channels", return_value={"testuser": True}):
            result = api.refresh_favorites()

        self.assertTrue(result["ok"])
        self.assertTrue(result["favorites"][0]["is_live"])
        self.assertTrue(
            any(
                "__onFavoritesUpdated" in call.args[0] for call in window.evaluate_js.call_args_list
            )
        )

    def test_refresh_favorites_preserves_status_on_check_failure(self):
        api = self.make_api()
        api.add_favorite("TestUser")
        with patch.object(api._status_monitor, "check_channels", return_value={"testuser": True}):
            api.refresh_favorites()
        window = Mock()
        api.set_window(window)

        with patch.object(api._status_monitor, "check_channels", return_value={}):
            result = api.refresh_favorites()

        self.assertFalse(result["ok"])
        favorites = api.get_favorites()
        self.assertTrue(favorites[0]["is_live"])
        window.evaluate_js.assert_not_called()

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
