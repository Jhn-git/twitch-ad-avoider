"""State and filename helpers for the recent-clip trim editor."""

from __future__ import annotations

import re
import threading
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

_NON_SLUG_RE = re.compile(r"[^a-z0-9]+")


def kebab_slug(value: str) -> str:
    """Return a filesystem-safe, lowercase ASCII kebab slug."""
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    return _NON_SLUG_RE.sub("-", ascii_value).strip("-")


def clip_base_name(channel: str, captured_at: datetime) -> str:
    channel_slug = kebab_slug(channel) or "clip"
    return f"{channel_slug}-{captured_at.strftime('%Y%m%d-%H%M%S')}"


def clip_filename(channel: str, captured_at: datetime, title: str = "") -> str:
    base = clip_base_name(channel, captured_at)
    title_slug = kebab_slug(title)[:80]
    suffix = f"-{title_slug}" if title_slug else ""
    return f"{base}{suffix}.mp4"


def collision_safe_path(directory: Path, filename: str, current: Optional[Path] = None) -> Path:
    """Choose `filename`, then `-2`, `-3`, ... without overwriting another clip."""
    candidate = directory / filename
    current_resolved = current.resolve() if current else None
    if not candidate.exists() or (
        current_resolved is not None and candidate.resolve() == current_resolved
    ):
        return candidate

    stem = Path(filename).stem
    suffix = Path(filename).suffix
    index = 2
    while True:
        candidate = directory / f"{stem}-{index}{suffix}"
        if not candidate.exists() or (
            current_resolved is not None and candidate.resolve() == current_resolved
        ):
            return candidate
        index += 1


@dataclass
class ClipEditSession:
    """One in-memory editable clip backed by a retained raw recording."""

    id: str
    channel: str
    captured_at: datetime
    source_path: Path
    source_start_time: datetime
    output_path: Path
    duration_seconds: float
    anchor_seconds: float
    rendered_start_seconds: float
    rendered_end_seconds: float
    selected_start_seconds: float
    selected_end_seconds: float
    preview_start_seconds: float
    preview_end_seconds: float
    preview_token: str
    preview_path: Path
    status: str = "capturing_postroll"
    message: str = "Capturing 5s post-roll..."
    error: Optional[str] = None
    title: str = ""
    tail_seconds: float = 5.0
    preview_revision: int = 1
    operation_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    cancel_event: threading.Event = field(default_factory=threading.Event, repr=False)

    @property
    def base_name(self) -> str:
        return clip_base_name(self.channel, self.captured_at)

    def to_dict(self, preview_url: str) -> dict[str, Any]:
        preview_duration = max(0.0, self.preview_end_seconds - self.preview_start_seconds)
        selection_start = max(0.0, self.selected_start_seconds - self.preview_start_seconds)
        selection_end = max(selection_start, self.selected_end_seconds - self.preview_start_seconds)
        selected_start = min(selection_start, preview_duration)
        selected_end = min(selection_end, preview_duration)
        return {
            "id": self.id,
            "channel": self.channel,
            "captured_at": self.captured_at.isoformat(),
            "click_timestamp": self.captured_at.isoformat(),
            "path": str(self.output_path),
            "saved_path": str(self.output_path),
            "base_name": self.base_name,
            "filename": self.output_path.name,
            "computed_filename": self.output_path.name,
            "title": self.title,
            "status": self.status,
            "message": self.message,
            "error": self.error,
            "preview_url": preview_url,
            "preview_revision": self.preview_revision,
            "preview_duration_seconds": preview_duration,
            "available_start_seconds": 0.0,
            "available_end_seconds": preview_duration,
            "selection_start_seconds": selected_start,
            "selection_end_seconds": selected_end,
            "selected_start_seconds": selected_start,
            "selected_end_seconds": selected_end,
            "tail_seconds": self.tail_seconds,
        }
