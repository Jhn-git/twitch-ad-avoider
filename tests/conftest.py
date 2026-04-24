"""Shared pytest fixtures and test configuration."""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
import pytest

# Mock streamlink globally for all tests
sys.modules["streamlink"] = MagicMock()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    tmp = tempfile.mkdtemp()
    yield Path(tmp)
    import shutil

    if os.path.exists(tmp):
        shutil.rmtree(tmp)


@pytest.fixture
def temp_config_path(temp_dir):
    """Create a temporary config file path."""
    return temp_dir / "test_settings.json"


@pytest.fixture
def mock_config_manager(temp_config_path):
    """Create a ConfigManager instance with temporary storage."""
    from src.config_manager import ConfigManager

    return ConfigManager(temp_config_path)


# Test data fixtures


@pytest.fixture
def valid_channels():
    """List of valid Twitch channel names for testing."""
    return ["ninja", "shroud", "test_channel", "test123", "valid_user"]


@pytest.fixture
def invalid_channels():
    """List of invalid channel names for security testing."""
    return [
        "",  # Empty
        "ab",  # Too short
        "abc",  # Still too short (min 4 chars)
        "test$channel",  # Invalid character
        "a" * 26,  # Too long (max 25 chars)
        "../../../etc/passwd",  # Path traversal
        "test;whoami",  # Command injection
        "test`id`",  # Command substitution
        "test\x00name",  # Control character (null byte)
        "test\nname",  # Newline
        "test|whoami",  # Pipe
        "test&&whoami",  # Command chaining
    ]


@pytest.fixture
def valid_qualities():
    """List of valid stream quality options."""
    return ["best", "worst", "720p", "480p", "360p", "160p"]


@pytest.fixture
def invalid_qualities():
    """List of invalid quality options for validation testing."""
    return ["1080p", "4k", "ultra", "", None, "../../etc", "test;whoami"]


@pytest.fixture
def valid_players():
    """List of valid player choices."""
    return ["vlc", "mpv", "mpc-hc", "auto"]


@pytest.fixture
def malicious_paths():
    """List of malicious file paths for security testing."""
    return [
        "../../../etc/passwd",  # Unix path traversal
        "..\\..\\..\\windows\\system32\\config\\sam",  # Windows path traversal
        "/etc/passwd",  # Absolute path
        "C:\\Windows\\System32",  # Windows absolute
        "test;whoami",  # Command injection
        "test`id`",  # Command substitution
        "test$(whoami)",  # Command substitution
        "test|cat /etc/passwd",  # Pipe
        "test\x00",  # Null byte
    ]


@pytest.fixture
def malicious_args():
    """List of malicious command-line arguments for security testing."""
    return [
        "; whoami",  # Command separator
        "| cat /etc/passwd",  # Pipe
        "&& whoami",  # Command chaining
        "|| whoami",  # OR chaining
        "$(whoami)",  # Command substitution
        "`id`",  # Backtick substitution
        "\x00",  # Null byte
        "\n/bin/sh",  # Newline injection
    ]


# Utility functions for tests


def create_mock_favorites_file(path: Path, favorites: list = None):
    """Create a mock favorites.json file for testing."""
    import json
    from datetime import datetime

    if favorites is None:
        favorites = [
            {
                "channel": "test_channel_1",
                "added_at": datetime.now().isoformat(),
                "last_checked": None,
                "is_live": False,
            },
            {
                "channel": "test_channel_2",
                "added_at": datetime.now().isoformat(),
                "last_checked": datetime.now().isoformat(),
                "is_live": True,
            },
        ]

    with open(path, "w") as f:
        json.dump(favorites, f, indent=2)


def create_mock_config_file(path: Path, config: dict = None):
    """Create a mock settings.json file for testing."""
    import json

    if config is None:
        config = {
            "preferred_quality": "best",
            "player": "auto",
            "cache_duration": 300,
            "retry_attempts": 3,
            "retry_delay": 5,
            "log_level": "INFO",
            "debug": False,
            "log_to_file": True,
        }

    with open(path, "w") as f:
        json.dump(config, f, indent=2)
