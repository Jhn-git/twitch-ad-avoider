"""Day-scoped recording segment bookkeeping.

Tracks which stretches of a channel's recording day were actually captured
(one ``RecordingSegment`` per app run that recorded something), persisted as
``index.json`` next to the raw ``.ts`` files so it survives app restarts.
Every function here takes ``now``/times explicitly rather than calling
``datetime.now()`` internally, so this module has no wall-clock dependency
and needs no time-mocking in tests.
"""

from __future__ import annotations

import json
import os
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Optional

DAY_DIR_FORMAT = "%Y-%m-%d"


@dataclass
class RecordingSegment:
    """One continuous recording run (from a `start()` call until it stopped)."""

    id: str
    start: datetime
    end: Optional[datetime]
    raw_filename: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "start": self.start.isoformat(),
            "end": self.end.isoformat() if self.end else None,
            "raw_filename": self.raw_filename,
        }

    @staticmethod
    def from_dict(data: dict) -> "RecordingSegment":
        return RecordingSegment(
            id=data["id"],
            start=datetime.fromisoformat(data["start"]),
            end=datetime.fromisoformat(data["end"]) if data.get("end") else None,
            raw_filename=data["raw_filename"],
        )


@dataclass
class DayIndex:
    """All segments recorded for one channel on one calendar day."""

    stream_created_at: Optional[datetime] = None
    segments: list[RecordingSegment] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "stream_created_at": (
                self.stream_created_at.isoformat() if self.stream_created_at else None
            ),
            "segments": [segment.to_dict() for segment in self.segments],
        }

    @staticmethod
    def from_dict(data: dict) -> "DayIndex":
        created_at = data.get("stream_created_at")
        return DayIndex(
            stream_created_at=datetime.fromisoformat(created_at) if created_at else None,
            segments=[RecordingSegment.from_dict(s) for s in data.get("segments", [])],
        )


@dataclass
class ResolvedOffset:
    """Where an absolute target timestamp lands within a day's segments."""

    segment: RecordingSegment
    offset_seconds: float
    snapped: bool


INDEX_FILENAME = "index.json"


def index_path(day_dir: Path) -> Path:
    return day_dir / INDEX_FILENAME


def load_index(day_dir: Path) -> DayIndex:
    """Load index.json from day_dir, or return an empty index if absent/unreadable."""
    path = index_path(day_dir)
    if not path.exists():
        return DayIndex()
    try:
        return DayIndex.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, KeyError):
        return DayIndex()


def save_index(day_dir: Path, index: DayIndex) -> None:
    """Write index.json atomically (temp file + os.replace) so a crash mid-write
    can never leave a corrupt/partial index behind."""
    day_dir.mkdir(parents=True, exist_ok=True)
    path = index_path(day_dir)
    tmp_path = path.with_suffix(f".json.{uuid.uuid4().hex}.tmp")
    tmp_path.write_text(json.dumps(index.to_dict(), indent=2), encoding="utf-8")
    os.replace(tmp_path, path)


def start_segment(index: DayIndex, now: datetime) -> RecordingSegment:
    """Create and register a new open (unfinished) segment starting at `now`."""
    segment_id = uuid.uuid4().hex[:12]
    segment = RecordingSegment(
        id=segment_id,
        start=now,
        end=None,
        raw_filename=f"raw_{segment_id}.ts",
    )
    index.segments.append(segment)
    return segment


def close_segment(index: DayIndex, segment_id: str, end: datetime) -> None:
    """Mark a segment finished. No-op if the id isn't found (already closed/unknown)."""
    for segment in index.segments:
        if segment.id == segment_id:
            segment.end = end
            return


def close_dangling_segments(index: DayIndex, day_dir: Path, now: datetime) -> None:
    """Close any segment left with `end: None` by a crash/kill instead of a clean
    stop, using the raw file's own last-write time (falling back to `now` if the
    file is missing) - the same "trust the file over wall clock" approach used to
    fix the post-stream-end clip offset bug."""
    for segment in index.segments:
        if segment.end is not None:
            continue
        raw_path = day_dir / segment.raw_filename
        if raw_path.exists():
            segment.end = datetime.fromtimestamp(raw_path.stat().st_mtime)
        else:
            segment.end = now


def resolve_timestamp(index: DayIndex, target: datetime, now: datetime) -> Optional[ResolvedOffset]:
    """Map an absolute target timestamp to (segment, offset within it).

    A still-open segment (`end is None`) is treated as extending to `now` for
    containment purposes. If `target` doesn't fall inside any segment, it snaps
    to the nearest edge of the closest segment (never lands in a gap). Returns
    None only if there are no segments at all.
    """
    if not index.segments:
        return None

    best: Optional[ResolvedOffset] = None
    best_distance = None
    for segment in index.segments:
        segment_end = segment.end or now
        if segment.start <= target <= segment_end:
            offset = (target - segment.start).total_seconds()
            return ResolvedOffset(segment=segment, offset_seconds=offset, snapped=False)

        if target < segment.start:
            distance = (segment.start - target).total_seconds()
            offset = 0.0
        else:
            distance = (target - segment_end).total_seconds()
            offset = (segment_end - segment.start).total_seconds()

        if best_distance is None or distance < best_distance:
            best_distance = distance
            best = ResolvedOffset(segment=segment, offset_seconds=offset, snapped=True)

    return best


def purge_old_days(channel_dir: Path, keep_days: int, now: datetime) -> list[Path]:
    """Delete day-directories under channel_dir older than keep_days. Returns the
    list of removed directories. Directory names that aren't a valid YYYY-MM-DD
    date are left alone (not this module's concern)."""
    if not channel_dir.exists():
        return []

    removed: list[Path] = []
    today = now.date()
    for entry in channel_dir.iterdir():
        if not entry.is_dir():
            continue
        try:
            day = datetime.strptime(entry.name, DAY_DIR_FORMAT).date()
        except ValueError:
            continue
        if (today - day).days > keep_days:
            shutil.rmtree(entry, ignore_errors=True)
            removed.append(entry)
    return removed


def day_dir_name(day: date) -> str:
    return day.strftime(DAY_DIR_FORMAT)
