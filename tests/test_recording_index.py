"""Tests for day-scoped recording segment bookkeeping (src/recording_index.py)."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from src.recording_index import (
    DayIndex,
    close_dangling_segments,
    close_segment,
    load_index,
    purge_old_days,
    resolve_timestamp,
    save_index,
    start_segment,
)


class TestSegmentLifecycle(unittest.TestCase):
    def test_start_segment_appends_and_names_raw_file(self):
        index = DayIndex()
        now = datetime(2026, 7, 18, 10, 0, 0)

        segment = start_segment(index, now)

        self.assertEqual(index.segments, [segment])
        self.assertEqual(segment.start, now)
        self.assertIsNone(segment.end)
        self.assertEqual(segment.raw_filename, f"raw_{segment.id}.ts")

    def test_start_segment_ids_are_unique(self):
        index = DayIndex()
        now = datetime(2026, 7, 18, 10, 0, 0)

        first = start_segment(index, now)
        second = start_segment(index, now)

        self.assertNotEqual(first.id, second.id)

    def test_close_segment_sets_end(self):
        index = DayIndex()
        now = datetime(2026, 7, 18, 10, 0, 0)
        segment = start_segment(index, now)
        end = now + timedelta(seconds=300)

        close_segment(index, segment.id, end)

        self.assertEqual(segment.end, end)

    def test_close_segment_unknown_id_is_noop(self):
        index = DayIndex()
        now = datetime(2026, 7, 18, 10, 0, 0)
        segment = start_segment(index, now)

        close_segment(index, "not-a-real-id", now + timedelta(seconds=10))

        self.assertIsNone(segment.end)


class TestCloseDanglingSegments(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_dangling_segment_closed_using_file_mtime(self):
        index = DayIndex()
        start = datetime(2026, 7, 18, 10, 0, 0)
        segment = start_segment(index, start)
        raw_path = self.temp_dir / segment.raw_filename
        raw_path.write_bytes(b"x" * 100)
        end_time = start + timedelta(seconds=120)
        mtime_epoch = end_time.timestamp()
        os.utime(raw_path, (mtime_epoch, mtime_epoch))

        close_dangling_segments(index, self.temp_dir, now=start + timedelta(hours=5))

        self.assertIsNotNone(segment.end)
        self.assertAlmostEqual(segment.end.timestamp(), end_time.timestamp(), delta=1)

    def test_dangling_segment_falls_back_to_now_when_file_missing(self):
        index = DayIndex()
        start = datetime(2026, 7, 18, 10, 0, 0)
        segment = start_segment(index, start)
        now = start + timedelta(hours=5)

        close_dangling_segments(index, self.temp_dir, now=now)

        self.assertEqual(segment.end, now)

    def test_already_closed_segment_is_untouched(self):
        index = DayIndex()
        start = datetime(2026, 7, 18, 10, 0, 0)
        segment = start_segment(index, start)
        original_end = start + timedelta(seconds=60)
        close_segment(index, segment.id, original_end)

        close_dangling_segments(index, self.temp_dir, now=start + timedelta(hours=5))

        self.assertEqual(segment.end, original_end)


class TestResolveTimestamp(unittest.TestCase):
    def test_no_segments_returns_none(self):
        self.assertIsNone(
            resolve_timestamp(DayIndex(), datetime(2026, 7, 18), datetime(2026, 7, 18))
        )

    def test_target_inside_closed_segment_is_not_snapped(self):
        index = DayIndex()
        start = datetime(2026, 7, 18, 10, 0, 0)
        segment = start_segment(index, start)
        close_segment(index, segment.id, start + timedelta(seconds=600))
        target = start + timedelta(seconds=200)

        result = resolve_timestamp(index, target, now=start + timedelta(hours=5))

        self.assertFalse(result.snapped)
        self.assertEqual(result.segment.id, segment.id)
        self.assertAlmostEqual(result.offset_seconds, 200, delta=0.01)

    def test_target_inside_open_segment_treated_as_extending_to_now(self):
        index = DayIndex()
        start = datetime(2026, 7, 18, 10, 0, 0)
        segment = start_segment(index, start)
        now = start + timedelta(seconds=300)
        target = start + timedelta(seconds=250)

        result = resolve_timestamp(index, target, now=now)

        self.assertFalse(result.snapped)
        self.assertEqual(result.segment.id, segment.id)

    def test_target_before_all_segments_snaps_to_first_start(self):
        index = DayIndex()
        start = datetime(2026, 7, 18, 10, 0, 0)
        segment = start_segment(index, start)
        close_segment(index, segment.id, start + timedelta(seconds=600))
        target = start - timedelta(seconds=100)

        result = resolve_timestamp(index, target, now=start + timedelta(hours=5))

        self.assertTrue(result.snapped)
        self.assertEqual(result.segment.id, segment.id)
        self.assertEqual(result.offset_seconds, 0.0)

    def test_target_in_gap_snaps_to_nearest_edge(self):
        index = DayIndex()
        start = datetime(2026, 7, 18, 10, 0, 0)
        first = start_segment(index, start)
        close_segment(index, first.id, start + timedelta(seconds=600))
        second_start = start + timedelta(seconds=1800)  # 20-minute gap after first ends
        second = start_segment(index, second_start)
        close_segment(index, second.id, second_start + timedelta(seconds=600))

        # closer to the end of the first segment than the start of the second
        target = start + timedelta(seconds=700)
        result = resolve_timestamp(index, target, now=start + timedelta(hours=5))
        self.assertTrue(result.snapped)
        self.assertEqual(result.segment.id, first.id)
        self.assertAlmostEqual(result.offset_seconds, 600, delta=0.01)

        # closer to the start of the second segment
        target = start + timedelta(seconds=1700)
        result = resolve_timestamp(index, target, now=start + timedelta(hours=5))
        self.assertTrue(result.snapped)
        self.assertEqual(result.segment.id, second.id)
        self.assertEqual(result.offset_seconds, 0.0)


class TestIndexPersistence(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_roundtrip_preserves_segments_and_stream_created_at(self):
        index = DayIndex(stream_created_at=datetime(2026, 7, 18, 9, 30, 0))
        start = datetime(2026, 7, 18, 10, 0, 0)
        segment = start_segment(index, start)
        close_segment(index, segment.id, start + timedelta(seconds=600))

        save_index(self.temp_dir, index)
        loaded = load_index(self.temp_dir)

        self.assertEqual(loaded.stream_created_at, index.stream_created_at)
        self.assertEqual(len(loaded.segments), 1)
        self.assertEqual(loaded.segments[0].id, segment.id)
        self.assertEqual(loaded.segments[0].end, segment.end)

    def test_load_missing_index_returns_empty(self):
        loaded = load_index(self.temp_dir / "does-not-exist")
        self.assertEqual(loaded.segments, [])
        self.assertIsNone(loaded.stream_created_at)

    def test_load_corrupt_index_returns_empty(self):
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        (self.temp_dir / "index.json").write_text("not valid json{", encoding="utf-8")

        loaded = load_index(self.temp_dir)

        self.assertEqual(loaded.segments, [])


class TestPurgeOldDays(unittest.TestCase):
    def setUp(self):
        self.channel_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.channel_dir, ignore_errors=True)

    def test_purges_directories_older_than_keep_days(self):
        now = datetime(2026, 7, 18)
        old_day = self.channel_dir / "2026-07-10"
        old_day.mkdir()
        (old_day / "raw_abc.ts").write_bytes(b"x")
        recent_day = self.channel_dir / "2026-07-17"
        recent_day.mkdir()

        removed = purge_old_days(self.channel_dir, keep_days=3, now=now)

        self.assertEqual(removed, [old_day])
        self.assertFalse(old_day.exists())
        self.assertTrue(recent_day.exists())

    def test_ignores_non_date_directories(self):
        now = datetime(2026, 7, 18)
        junk_dir = self.channel_dir / "not-a-date"
        junk_dir.mkdir()

        removed = purge_old_days(self.channel_dir, keep_days=3, now=now)

        self.assertEqual(removed, [])
        self.assertTrue(junk_dir.exists())

    def test_missing_channel_dir_returns_empty(self):
        missing = self.channel_dir / "nope"
        self.assertEqual(purge_old_days(missing, keep_days=3, now=datetime(2026, 7, 18)), [])


if __name__ == "__main__":
    unittest.main()
