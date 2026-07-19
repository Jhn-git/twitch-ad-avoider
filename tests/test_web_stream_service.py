"""Tests for the Streamlink-backed embedded playback service."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from scripts.gui_test_support import patch_temp_dir
from src import recording_index
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

    def _recording_file_with_elapsed(
        self, name: str, elapsed_seconds: int
    ) -> tuple[Path, datetime]:
        recording = Path(self.temp_dir) / name
        recording.write_bytes(b"x" * 2048)
        start_time = datetime.now() - timedelta(seconds=elapsed_seconds)
        mtime = start_time + timedelta(seconds=elapsed_seconds)
        os.utime(recording, (mtime.timestamp(), mtime.timestamp()))
        return recording, start_time

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

    def test_rewrite_playlist_turns_twitch_prefetch_into_playable_segment(self):
        self.service._ensure_proxy()
        playlist = """#EXTM3U
#EXTINF:4.000,
segment001.ts
#EXTINF:6.000,
segment002.ts
#EXT-X-TWITCH-PREFETCH:prefetch001.ts
"""

        rewritten = self.service._rewrite_playlist(
            playlist,
            "https://example.test/live/master.m3u8",
            "abc",
        )

        self.assertIn("#EXTINF:5.000,", rewritten)
        self.assertIn("prefetch001.ts", rewritten)
        self.assertIn("/resource/abc?url=", rewritten)
        self.assertNotIn("EXT-X-TWITCH-PREFETCH", rewritten)

    def test_rewrite_playlist_chains_duration_across_consecutive_prefetch_segments(self):
        self.service._ensure_proxy()
        playlist = """#EXTM3U
#EXTINF:4.000,
segment001.ts
#EXTINF:6.000,
segment002.ts
#EXT-X-TWITCH-PREFETCH:prefetch001.ts
#EXT-X-TWITCH-PREFETCH:prefetch002.ts
"""

        rewritten = self.service._rewrite_playlist(
            playlist,
            "https://example.test/live/master.m3u8",
            "abc",
        )

        self.assertEqual(rewritten.count("#EXTINF:5.000,"), 2)

    def test_rewrite_playlist_leaves_prefetch_tag_untouched_when_low_latency_disabled(self):
        self.service._ensure_proxy()
        self.config.set("twitch_low_latency", False)
        playlist = """#EXTM3U
#EXTINF:4.000,
segment001.ts
#EXT-X-TWITCH-PREFETCH:prefetch001.ts
"""

        rewritten = self.service._rewrite_playlist(
            playlist,
            "https://example.test/live/master.m3u8",
            "abc",
        )

        self.assertIn("#EXT-X-TWITCH-PREFETCH:prefetch001.ts", rewritten)

    def test_create_clip_requires_active_recording(self):
        result = self.service.create_clip(30)

        self.assertFalse(result["ok"])
        self.assertIn("No active recording", result["error"])

    def test_state_reports_clip_not_ready_until_selected_duration_recorded(self):
        self.config.set("stream_manager_clip_duration_seconds", 30)
        recording, start_time = self._recording_file_with_elapsed("recording.ts", 10)
        self.service._session = WebStreamSession(
            session_id="abc",
            channel="testuser",
            quality="best",
            stream_url="https://example.test/live.m3u8",
            stream_args={},
            playback_url="http://127.0.0.1/playlist/abc.m3u8",
            recording_path=str(recording),
            recording_start_time=start_time,
            last_recorded_at=start_time + timedelta(seconds=10),
            status="live",
        )

        state = self.service.get_state()

        self.assertFalse(state["clip_ready"])
        self.assertAlmostEqual(state["clip_ready_seconds"], 10.0, delta=1.0)
        self.assertIn("warming up", state["clip_warmup_reason"])

    def test_state_reports_clip_ready_after_selected_duration_recorded(self):
        self.config.set("stream_manager_clip_duration_seconds", 30)
        recording, start_time = self._recording_file_with_elapsed("recording.ts", 45)
        self.service._session = WebStreamSession(
            session_id="abc",
            channel="testuser",
            quality="best",
            stream_url="https://example.test/live.m3u8",
            stream_args={},
            playback_url="http://127.0.0.1/playlist/abc.m3u8",
            recording_path=str(recording),
            recording_start_time=start_time,
            last_recorded_at=start_time + timedelta(seconds=45),
            status="live",
        )

        state = self.service.get_state()

        self.assertTrue(state["clip_ready"])
        self.assertAlmostEqual(state["clip_ready_seconds"], 45.0, delta=1.0)
        self.assertIsNone(state["clip_warmup_reason"])

    @patch("src.web_stream_service.subprocess.run")
    @patch("src.web_stream_service.shutil.which", return_value="ffmpeg")
    def test_create_clip_invokes_ffmpeg(self, _mock_which, mock_run):
        recording, start_time = self._recording_file_with_elapsed("recording.ts", 60)
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
            recording_start_time=start_time,
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

    @patch("src.web_stream_service.subprocess.run")
    @patch("src.web_stream_service.shutil.which", return_value="ffmpeg")
    def test_create_clip_offsets_start_time_by_behind_live_seconds(self, _mock_which, mock_run):
        recording, start_time = self._recording_file_with_elapsed("recording.ts", 100)
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
            recording_start_time=start_time,
            status="live",
        )

        def write_output(cmd, **_kwargs):
            Path(cmd[-1]).write_bytes(b"x" * 2048)
            return Mock(stderr=b"")

        mock_run.side_effect = write_output

        result = self.service.create_clip(30, behind_live_seconds=20)

        self.assertTrue(result["ok"])
        cmd = mock_run.call_args.args[0]
        start_offset = float(cmd[cmd.index("-ss") + 1])
        # elapsed (~100s) - behind_live_seconds (20) - duration (30) = ~50s
        self.assertAlmostEqual(start_offset, 50.0, delta=1.0)

    @patch("src.web_stream_service.subprocess.run")
    @patch("src.web_stream_service.shutil.which", return_value="ffmpeg")
    def test_create_clip_clamps_behind_live_seconds_to_elapsed(self, _mock_which, mock_run):
        recording, start_time = self._recording_file_with_elapsed("recording.ts", 60)
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
            recording_start_time=start_time,
            status="live",
        )

        def write_output(cmd, **_kwargs):
            Path(cmd[-1]).write_bytes(b"x" * 2048)
            return Mock(stderr=b"")

        mock_run.side_effect = write_output

        result = self.service.create_clip(30, behind_live_seconds=100000)

        self.assertTrue(result["ok"])
        cmd = mock_run.call_args.args[0]
        start_offset = float(cmd[cmd.index("-ss") + 1])
        self.assertEqual(start_offset, 0.0)

    @patch("src.web_stream_service.subprocess.run")
    @patch("src.web_stream_service.shutil.which", return_value="ffmpeg")
    def test_create_clip_fails_when_active_recorder_lags_requested_endpoint(
        self, _mock_which, mock_run
    ):
        recording, start_time = self._recording_file_with_elapsed("recording.ts", 80)
        recorded_until = datetime.now() - timedelta(seconds=20)
        os.utime(recording, (recorded_until.timestamp(), recorded_until.timestamp()))
        self.service._session = WebStreamSession(
            session_id="abc",
            channel="testuser",
            quality="best",
            stream_url="https://example.test/live.m3u8",
            stream_args={},
            playback_url="http://127.0.0.1/playlist/abc.m3u8",
            recording_path=str(recording),
            recording_start_time=start_time,
            last_recorded_at=recorded_until,
            status="live",
        )

        result = self.service.create_clip(30, behind_live_seconds=0)

        self.assertFalse(result["ok"])
        self.assertIn("catching up", result["error"])
        mock_run.assert_not_called()

    @patch("src.web_stream_service.subprocess.run")
    @patch("src.web_stream_service.shutil.which", return_value="ffmpeg")
    def test_create_clip_uses_file_mtime_not_wall_clock_after_stream_ended(
        self, _mock_which, mock_run
    ):
        """A stream that ended a while ago must not have "elapsed" inflated by
        however long the user spends browsing afterward before clicking Clip -
        the recording file's own last-write time is what actually bounds it."""
        recording = Path(self.temp_dir) / "recording.ts"
        recording.write_bytes(b"x" * 2048)
        clip_dir = Path(self.temp_dir) / "clips"
        self.config.set("clip_directory", str(clip_dir))

        # Recording "started" 700 real seconds ago, but the stream actually
        # only ran for 400 of those seconds before ending - the file hasn't
        # been written to since. Simulated by backdating the file's mtime.
        start_time = datetime.now() - timedelta(seconds=700)
        stream_end_time = start_time + timedelta(seconds=400)
        mtime_epoch = stream_end_time.timestamp()
        os.utime(recording, (mtime_epoch, mtime_epoch))

        self.service._session = WebStreamSession(
            session_id="abc",
            channel="testuser",
            quality="best",
            stream_url="https://example.test/live.m3u8",
            stream_args={},
            playback_url="http://127.0.0.1/playlist/abc.m3u8",
            recording_path=str(recording),
            recording_start_time=start_time,
            status="ended",
        )

        def write_output(cmd, **_kwargs):
            Path(cmd[-1]).write_bytes(b"x" * 2048)
            return Mock(stderr=b"")

        mock_run.side_effect = write_output

        result = self.service.create_clip(30, behind_live_seconds=100)

        self.assertTrue(result["ok"])
        cmd = mock_run.call_args.args[0]
        start_offset = float(cmd[cmd.index("-ss") + 1])
        # elapsed must track the file's real content (~400s), not wall-clock
        # "now" (~700s): (400 - 100) - 30 = 270, not (700 - 100) - 30 = 570.
        self.assertAlmostEqual(start_offset, 270.0, delta=1.0)


class TestDayScopedRecording(unittest.TestCase):
    """Stage 1: temp/<channel>/<date>/ storage replaces the old rolling
    recording_<channel>.ts file. Every test here redirects TEMP_DIR to a
    scratch dir via patch_temp_dir() so it never touches the real temp/
    folder (which may have a real recording in progress)."""

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
        # _prepare_recording looks up the true Twitch stream start time (Stage 2) -
        # stub it out so these tests never make a real network call.
        preview_patcher = patch(
            "src.web_stream_service.fetch_stream_preview_info",
            return_value=Mock(stream_created_at=None),
        )
        self.mock_fetch_preview = preview_patcher.start()
        self.addCleanup(preview_patcher.stop)

    def tearDown(self):
        self.service.shutdown()
        shutil.rmtree(self.temp_dir)

    @patch("src.web_stream_service.streamlink.Streamlink")
    def test_stop_then_start_creates_two_distinct_segment_files(self, mock_streamlink):
        mock_session = Mock()
        mock_session.streams.return_value = {"best": FakeStream()}
        mock_streamlink.return_value = mock_session

        with tempfile.TemporaryDirectory() as scratch:
            with patch_temp_dir(Path(scratch)):
                self.service.start("testuser", "best")
                first_path = self.service._session.recording_path
                self.service.stop(join_timeout=2.0)

                self.service.start("testuser", "best")
                second_path = self.service._session.recording_path
                day_dir = self.service._session.day_dir
                self.service.stop(join_timeout=2.0)

                self.assertIsNotNone(first_path)
                self.assertIsNotNone(second_path)
                self.assertNotEqual(first_path, second_path)

                index = recording_index.load_index(day_dir)
                self.assertEqual(len(index.segments), 2)
                self.assertIsNotNone(
                    index.segments[0].end, "first segment should be closed by stop()"
                )
                self.assertIsNotNone(
                    index.segments[1].end, "second segment should be closed by stop()"
                )

    def test_dangling_segment_is_auto_closed_on_next_prepare(self):
        with tempfile.TemporaryDirectory() as scratch:
            with patch_temp_dir(Path(scratch)):
                prep_one = self.service._prepare_recording("testuser")
                Path(prep_one.raw_path).write_bytes(b"x" * 100)

                # No stop() in between - simulates the app being killed instead
                # of closing cleanly, leaving the first segment's `end` unset.
                prep_two = self.service._prepare_recording("testuser")

                self.assertNotEqual(prep_one.raw_path, prep_two.raw_path)
                index = recording_index.load_index(prep_two.day_dir)
                self.assertEqual(len(index.segments), 2)
                self.assertIsNotNone(index.segments[0].end)
                self.assertIsNone(index.segments[1].end)

    def test_prepare_recording_purges_days_older_than_retention(self):
        with tempfile.TemporaryDirectory() as scratch:
            scratch_path = Path(scratch)
            with patch_temp_dir(scratch_path) as temp_dir:
                channel_dir = temp_dir / "testuser"
                old_day = channel_dir / "2020-01-01"
                old_day.mkdir(parents=True)
                (old_day / "raw_old.ts").write_bytes(b"x")

                self.service._prepare_recording("testuser")

            self.assertFalse(old_day.exists())

    def test_prepare_recording_stores_true_stream_start_time(self):
        self.mock_fetch_preview.return_value = Mock(stream_created_at="2026-07-17T09:58:35Z")

        with tempfile.TemporaryDirectory() as scratch:
            with patch_temp_dir(Path(scratch)):
                prep = self.service._prepare_recording("testuser")

                index = recording_index.load_index(prep.day_dir)
                self.assertIsNotNone(index.stream_created_at)
                # Stored as naive local time (converted from the UTC GQL value),
                # matching the naive-local convention used everywhere else here.
                self.assertIsNone(index.stream_created_at.tzinfo)

    def test_prepare_recording_keeps_prior_stream_created_at_when_fetch_fails(self):
        with tempfile.TemporaryDirectory() as scratch:
            with patch_temp_dir(Path(scratch)):
                self.mock_fetch_preview.return_value = Mock(
                    stream_created_at="2026-07-17T09:58:35Z"
                )
                first = self.service._prepare_recording("testuser")

                self.mock_fetch_preview.return_value = Mock(stream_created_at=None)
                self.service._prepare_recording("testuser")

                index = recording_index.load_index(first.day_dir)
                self.assertIsNotNone(index.stream_created_at)

    def test_get_recording_segments_returns_today_index(self):
        with tempfile.TemporaryDirectory() as scratch:
            with patch_temp_dir(Path(scratch)):
                self.mock_fetch_preview.return_value = Mock(
                    stream_created_at="2026-07-17T09:58:35Z"
                )
                self.service._prepare_recording("testuser")

                result = self.service.get_recording_segments("testuser")

                self.assertEqual(result["channel"], "testuser")
                self.assertIsNotNone(result["stream_created_at"])
                self.assertEqual(len(result["segments"]), 1)
                self.assertIsNone(result["segments"][0]["end"])
                self.assertIsNotNone(result["now"])

    def test_get_recording_segments_falls_back_to_earliest_segment_start(self):
        with tempfile.TemporaryDirectory() as scratch:
            with patch_temp_dir(Path(scratch)):
                self.mock_fetch_preview.return_value = Mock(stream_created_at=None)
                self.service._prepare_recording("testuser")

                result = self.service.get_recording_segments("testuser")

                self.assertEqual(result["stream_created_at"], result["segments"][0]["start"])

    def test_get_recording_segments_empty_when_never_recorded(self):
        with tempfile.TemporaryDirectory() as scratch:
            with patch_temp_dir(Path(scratch)):
                result = self.service.get_recording_segments("neverrecorded")

                self.assertEqual(result["segments"], [])
                self.assertIsNone(result["stream_created_at"])

    def test_clip_enabled_false_skips_recording_entirely(self):
        self.config.set("clip_enabled", False)

        with tempfile.TemporaryDirectory() as scratch:
            with patch_temp_dir(Path(scratch)) as temp_dir:
                prep = self.service._prepare_recording("testuser")
                self.assertIsNone(prep.raw_path)
                self.assertEqual(list(temp_dir.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
