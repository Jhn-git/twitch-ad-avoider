"""Tests for the Streamlink-backed embedded playback service."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

from src.config_manager import ConfigManager
from src.web_stream_service import WebStreamService, WebStreamSession


class FakeStream:
    url = "https://example.test/live/master.m3u8"
    args = {"headers": {"User-Agent": "streamlink-test"}}

    def open(self):
        return Mock(read=Mock(return_value=b""))


class TestWebStreamService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config = ConfigManager(Path(self.temp_dir) / "settings.json")
        self.events = []
        self.activity = []
        self.service = WebStreamService(
            self.config,
            self.events.append,
            lambda level, message, category=None: self.activity.append((level, message, category)),
        )

    def tearDown(self):
        self.service.shutdown()
        shutil.rmtree(self.temp_dir)

    @patch("src.web_stream_service.streamlink.Streamlink")
    def test_start_exposes_loopback_playback_url_without_recording(self, mock_streamlink):
        self.config.set("clip_enabled", False)
        mock_session = Mock()
        mock_session.streams.return_value = {"best": FakeStream()}
        mock_streamlink.return_value = mock_session

        state = self.service.start("testuser", "best")

        self.assertTrue(state["active"])
        self.assertEqual(state["channel"], "testuser")
        self.assertEqual(state["quality"], "best")
        self.assertEqual(state["status"], "live")
        self.assertFalse(state["recording"])
        self.assertTrue(state["playback_url"].startswith("http://127.0.0.1:"))
        self.assertEqual(self.events[-1]["type"], "started")

    @patch("src.web_stream_service.streamlink.Streamlink")
    def test_start_falls_back_to_best_when_quality_unavailable(self, mock_streamlink):
        self.config.set("clip_enabled", False)
        mock_session = Mock()
        mock_session.streams.return_value = {"best": FakeStream()}
        mock_streamlink.return_value = mock_session

        state = self.service.start("testuser", "720p")

        self.assertEqual(state["quality"], "best")

    def test_stop_clears_state(self):
        self.service._session = WebStreamSession(
            session_id="abc",
            channel="testuser",
            quality="best",
            stream_url="https://example.test/live.m3u8",
            stream_args={},
            playback_url="http://127.0.0.1/playlist/abc.m3u8",
            recording_path=None,
            recording_start_time=None,
            status="live",
        )

        state = self.service.stop()

        self.assertFalse(state["active"])
        self.assertEqual(state["status"], "idle")
        self.assertEqual(self.events[-1]["type"], "stopped")

    def test_rewrite_playlist_proxies_segments_keys_and_nested_playlists(self):
        self.service._ensure_proxy()
        playlist = """#EXTM3U
#EXT-X-KEY:METHOD=AES-128,URI="key.bin"
#EXTINF:4.0,
segment001.ts
#EXT-X-STREAM-INF:BANDWIDTH=1
variant/playlist.m3u8
"""

        rewritten = self.service._rewrite_playlist(
            playlist,
            "https://example.test/live/master.m3u8",
            "abc",
        )

        self.assertIn("/resource/abc?url=", rewritten)
        self.assertIn("key.bin", rewritten)
        self.assertIn("segment001.ts", rewritten)
        self.assertIn("variant%2Fplaylist.m3u8", rewritten)

    def test_create_clip_requires_active_recording(self):
        result = self.service.create_clip(30)

        self.assertFalse(result["ok"])
        self.assertIn("No active recording", result["error"])

    @patch("src.web_stream_service.subprocess.run")
    @patch("src.web_stream_service.shutil.which", return_value="ffmpeg")
    def test_create_clip_invokes_ffmpeg(self, _mock_which, mock_run):
        recording = Path(self.temp_dir) / "recording.ts"
        recording.write_bytes(b"x" * 2048)
        clip_dir = Path(self.temp_dir) / "clips"
        self.config.set("clip_directory", str(clip_dir))
        self.service._session = WebStreamSession(
            session_id="abc",
            channel="testuser",
            quality="best",
            stream_url="https://example.test/live.m3u8",
            stream_args={},
            playback_url="http://127.0.0.1/playlist/abc.m3u8",
            recording_path=str(recording),
            recording_start_time=datetime.now(),
            status="live",
        )

        def write_output(cmd, **_kwargs):
            Path(cmd[-1]).write_bytes(b"x" * 2048)
            return Mock(stderr=b"")

        mock_run.side_effect = write_output

        result = self.service.create_clip(30)

        self.assertTrue(result["ok"])
        self.assertTrue(Path(result["path"]).exists())
        self.assertIn("-c", mock_run.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
