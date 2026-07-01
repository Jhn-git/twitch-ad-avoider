"""Tests for Katch configuration loading."""

import json
from pathlib import Path

import pytest

from katch.config import load_config
from src.exceptions import ValidationError


def test_load_config_normalizes_keywords_and_paths(tmp_path: Path) -> None:
    config_path = tmp_path / "katch.json"
    payload = {
        "channel_name": "Ninja",
        "keywords": [" Dead by Daylight ", "juice box", "juice box"],
        "preferred_quality": "best",
        "whisper_model": "small.en",
        "language": "en",
        "device": "cuda",
        "compute_type": "float16",
        "chunk_duration_seconds": 3,
        "preroll_seconds": 20,
        "postroll_seconds": 10,
        "keyword_cooldown_seconds": 20,
        "sample_rate": 16000,
        "beam_size": 1,
        "vad_filter": True,
        "ffmpeg_path": None,
        "recording_directory": str(tmp_path / "recordings"),
        "clips_directory": str(tmp_path / "clips"),
        "temp_directory": str(tmp_path / "temp"),
        "event_log_path": str(tmp_path / "events.jsonl"),
    }
    config_path.write_text(json.dumps(payload), encoding="utf-8")

    config = load_config(config_path)

    assert config.channel_name == "ninja"
    assert config.keywords == ["dead by daylight", "juice box"]
    assert config.recording_directory == (tmp_path / "recordings").resolve()
    assert config.event_log_path == (tmp_path / "events.jsonl").resolve()


def test_load_config_rejects_invalid_channel(tmp_path: Path) -> None:
    config_path = tmp_path / "katch.json"
    payload = {
        "channel_name": "../bad",
        "keywords": ["test"],
    }
    config_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValidationError):
        load_config(config_path)


def test_load_config_rejects_control_chars_in_keywords(tmp_path: Path) -> None:
    config_path = tmp_path / "katch.json"
    payload = {
        "channel_name": "validname",
        "keywords": ["ok", "bad\u0000keyword"],
    }
    config_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValidationError):
        load_config(config_path)
