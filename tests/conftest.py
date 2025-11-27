"""
Shared pytest fixtures and test configuration.

This module provides reusable fixtures for testing TwitchAdAvoider components,
reducing boilerplate and ensuring consistent test setup across the test suite.
"""

import tempfile
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

# Mock streamlink globally for all tests
sys.modules["streamlink"] = MagicMock()


@pytest.fixture
def temp_dir():
    """
    Create a temporary directory for test files.

    Yields:
        Path: Path to temporary directory

    Cleanup:
        Removes directory and all contents after test
    """
    tmp = tempfile.mkdtemp()
    yield Path(tmp)
    # Cleanup
    import shutil

    if os.path.exists(tmp):
        shutil.rmtree(tmp)


@pytest.fixture
def temp_config_path(temp_dir):
    """
    Create a temporary config file path.

    Args:
        temp_dir: Temporary directory fixture

    Returns:
        Path: Path to temporary config file
    """
    return temp_dir / "test_settings.json"


@pytest.fixture
def temp_token_path(temp_dir):
    """
    Create a temporary token file path for auth tests.

    Args:
        temp_dir: Temporary directory fixture

    Returns:
        Path: Path to temporary token file
    """
    return temp_dir / "test_auth_token.enc"


@pytest.fixture
def mock_config_manager(temp_config_path):
    """
    Create a ConfigManager instance with temporary storage.

    Args:
        temp_config_path: Temporary config file path

    Returns:
        ConfigManager: Configured instance for testing
    """
    from src.config_manager import ConfigManager

    return ConfigManager(temp_config_path)


@pytest.fixture
def mock_requests():
    """
    Mock the requests library for HTTP testing.

    Returns:
        MagicMock: Mocked requests module
    """
    with patch("requests.post") as mock_post, patch("requests.get") as mock_get:
        yield {"post": mock_post, "get": mock_get}


@pytest.fixture
def mock_webbrowser():
    """
    Mock webbrowser.open for auth flow testing.

    Returns:
        MagicMock: Mocked webbrowser.open function
    """
    with patch("webbrowser.open") as mock_open:
        yield mock_open


@pytest.fixture
def mock_http_server():
    """
    Mock HTTPServer for OAuth callback testing.

    Returns:
        MagicMock: Mocked HTTPServer
    """
    with patch("http.server.HTTPServer") as mock_server:
        mock_instance = MagicMock()
        mock_server.return_value = mock_instance
        yield mock_instance


# Test data fixtures


@pytest.fixture
def valid_channels():
    """
    List of valid Twitch channel names for testing.

    Returns:
        list: Valid channel names
    """
    return ["ninja", "shroud", "test_channel", "test123", "valid_user"]


@pytest.fixture
def invalid_channels():
    """
    List of invalid channel names for security testing.

    Returns:
        list: Invalid/malicious channel names
    """
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
    """
    List of valid stream quality options.

    Returns:
        list: Valid quality strings
    """
    return ["best", "worst", "720p", "480p", "360p", "160p"]


@pytest.fixture
def invalid_qualities():
    """
    List of invalid quality options for validation testing.

    Returns:
        list: Invalid quality strings
    """
    return ["1080p", "4k", "ultra", "", None, "../../etc", "test;whoami"]


@pytest.fixture
def valid_players():
    """
    List of valid player choices.

    Returns:
        list: Valid player names
    """
    return ["vlc", "mpv", "mpc-hc", "auto"]


@pytest.fixture
def malicious_paths():
    """
    List of malicious file paths for security testing.

    Returns:
        list: Path traversal and command injection attempts
    """
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
    """
    List of malicious command-line arguments for security testing.

    Returns:
        list: Command injection attempts
    """
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


@pytest.fixture
def sample_oauth_token():
    """
    Sample OAuth token data for auth testing.

    Returns:
        dict: OAuth token response structure
    """
    return {
        "access_token": "test_access_token_1234567890",
        "refresh_token": "test_refresh_token_0987654321",
        "expires_in": 3600,
        "scope": ["chat:read", "chat:edit"],
        "token_type": "bearer",
    }


@pytest.fixture
def sample_chat_messages():
    """
    Sample IRC chat messages for parsing tests.

    Returns:
        list: Raw IRC message strings
    """
    return [
        (
            "@badge-info=;badges=;color=#FF0000;display-name=TestUser;emotes=;id=abc-123;"
            "mod=0;room-id=12345;subscriber=0;tmi-sent-ts=1234567890;turbo=0;user-id=67890;"
            "user-type= :testuser!testuser@testuser.tmi.twitch.tv "
            "PRIVMSG #testchannel :Hello, World!"
        ),
        ":tmi.twitch.tv 001 testuser :Welcome to the IRC network",
        ":tmi.twitch.tv 002 testuser :Your host is tmi.twitch.tv",
        ":tmi.twitch.tv 376 testuser :End of /MOTD command",
        ":tmi.twitch.tv CAP * ACK :twitch.tv/tags twitch.tv/commands",
        "PING :tmi.twitch.tv",
    ]


# Utility functions for tests


def create_mock_favorites_file(path: Path, favorites: list = None):
    """
    Create a mock favorites.json file for testing.

    Args:
        path: Path to create the file at
        favorites: List of favorite channel dicts (optional)
    """
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
    """
    Create a mock settings.json file for testing.

    Args:
        path: Path to create the file at
        config: Config dict (optional, uses defaults if not provided)
    """
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


# Export utility functions for use in tests
__all__ = [
    "temp_dir",
    "temp_config_path",
    "temp_token_path",
    "mock_config_manager",
    "mock_requests",
    "mock_webbrowser",
    "mock_http_server",
    "valid_channels",
    "invalid_channels",
    "valid_qualities",
    "invalid_qualities",
    "valid_players",
    "malicious_paths",
    "malicious_args",
    "sample_oauth_token",
    "sample_chat_messages",
    "create_mock_favorites_file",
    "create_mock_config_file",
]
