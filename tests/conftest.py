"""Shared pytest fixtures and test configuration."""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

# Mock streamlink globally for all tests
sys.modules["streamlink"] = MagicMock()


class TempDirTestCase(unittest.TestCase):
    """Base for unittest.TestCase tests that just need a scratch temp directory.

    The suite is almost entirely unittest.TestCase, which can't receive
    pytest function fixtures - so scratch-directory setup lives here as a
    mixin instead.
    """

    def setUp(self):
        super().setUp()
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp_dir, ignore_errors=True)


class ConfigManagerTestCase(TempDirTestCase):
    """Base for tests that need a temp dir plus a ConfigManager backed by it."""

    def setUp(self):
        super().setUp()
        from src.config_manager import ConfigManager

        self.config_path = Path(self.temp_dir) / "test_settings.json"
        self.config = ConfigManager(self.config_path)
