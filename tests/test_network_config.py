"""
Tests for network configuration and timeout settings
Tests the new network reliability features added to the application.
"""

import unittest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch

from src.config_manager import ConfigManager
from src.exceptions import ValidationError

# Check for streamlink availability
try:
    import streamlink
    from src.streamlink_status import StreamlinkStatusChecker
    from src.twitch_viewer import TwitchViewer
    HAS_STREAMLINK = True
except ImportError:
    HAS_STREAMLINK = False
    StreamlinkStatusChecker = None
    TwitchViewer = None


class TestNetworkConfiguration(unittest.TestCase):
    """Test network configuration settings"""

    def setUp(self):
        """Set up test with temporary config file"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "test_settings.json"
        self.config = ConfigManager(self.config_path)

    def tearDown(self):
        """Clean up temporary files"""
        if self.config_path.exists():
            self.config_path.unlink()
        os.rmdir(self.temp_dir)

    def test_network_timeout_validation(self):
        """Test network timeout setting validation"""
        # Valid timeout values
        valid_timeouts = [10, 15, 30, 60, 120]
        for timeout in valid_timeouts:
            with self.subTest(timeout=timeout):
                result = self.config.set("network_timeout", timeout)
                self.assertTrue(result, f"Timeout {timeout} should be valid")
                self.assertEqual(self.config.get("network_timeout"), timeout)

        # Invalid timeout values
        invalid_timeouts = [5, 9, 121, 200, -1, 0, "30", None]
        for timeout in invalid_timeouts:
            with self.subTest(timeout=timeout):
                result = self.config.set("network_timeout", timeout)
                self.assertFalse(result, f"Timeout {timeout} should be invalid")

    def test_retry_attempts_validation(self):
        """Test connection retry attempts validation"""
        # Valid retry attempts
        valid_attempts = [1, 3, 5, 10]
        for attempts in valid_attempts:
            with self.subTest(attempts=attempts):
                result = self.config.set("connection_retry_attempts", attempts)
                self.assertTrue(result, f"Retry attempts {attempts} should be valid")
                self.assertEqual(self.config.get("connection_retry_attempts"), attempts)

        # Invalid retry attempts
        invalid_attempts = [0, 11, 15, -1, "3", None]
        for attempts in invalid_attempts:
            with self.subTest(attempts=attempts):
                result = self.config.set("connection_retry_attempts", attempts)
                self.assertFalse(result, f"Retry attempts {attempts} should be invalid")

    def test_retry_delay_validation(self):
        """Test retry delay validation"""
        # Valid retry delays
        valid_delays = [1, 5, 10, 30]
        for delay in valid_delays:
            with self.subTest(delay=delay):
                result = self.config.set("retry_delay", delay)
                self.assertTrue(result, f"Retry delay {delay} should be valid")
                self.assertEqual(self.config.get("retry_delay"), delay)

        # Invalid retry delays
        invalid_delays = [0, 31, 50, -1, "5", None]
        for delay in invalid_delays:
            with self.subTest(delay=delay):
                result = self.config.set("retry_delay", delay)
                self.assertFalse(result, f"Retry delay {delay} should be invalid")

    def test_network_diagnostics_setting(self):
        """Test network diagnostics boolean setting"""
        # Valid boolean values
        self.assertTrue(self.config.set("enable_network_diagnostics", True))
        self.assertTrue(self.config.get("enable_network_diagnostics"))

        self.assertTrue(self.config.set("enable_network_diagnostics", False))
        self.assertFalse(self.config.get("enable_network_diagnostics"))

        # Invalid values
        invalid_values = ["true", "false", 1, 0, None, "yes"]
        for value in invalid_values:
            with self.subTest(value=value):
                result = self.config.set("enable_network_diagnostics", value)
                self.assertFalse(result, f"Value {value} should be invalid for boolean setting")

    def test_default_network_settings(self):
        """Test that default network settings are properly loaded"""
        self.assertEqual(self.config.get("network_timeout"), 30)
        self.assertEqual(self.config.get("connection_retry_attempts"), 3)
        self.assertEqual(self.config.get("retry_delay"), 5)
        self.assertTrue(self.config.get("enable_network_diagnostics"))

    def test_batch_network_settings_update(self):
        """Test updating multiple network settings at once"""
        # Valid batch update
        valid_settings = {
            "network_timeout": 45,
            "connection_retry_attempts": 5,
            "retry_delay": 10,
            "enable_network_diagnostics": False,
        }
        self.assertTrue(self.config.update(valid_settings))

        for key, value in valid_settings.items():
            self.assertEqual(self.config.get(key), value)

        # Invalid batch update (should fail entirely)
        invalid_settings = {
            "network_timeout": 45,
            "connection_retry_attempts": 15,  # Invalid (> 10)
            "retry_delay": 10,
            "enable_network_diagnostics": False,
        }
        self.assertFalse(self.config.update(invalid_settings))

        # Original values should be preserved
        self.assertEqual(self.config.get("network_timeout"), 45)
        self.assertEqual(self.config.get("connection_retry_attempts"), 5)  # Should still be 5


@unittest.skipIf(not HAS_STREAMLINK, 
    "streamlink required - install with 'pip install streamlink>=5.0.0'")
class TestStreamlinkStatusChecker(unittest.TestCase):
    """Test StreamlinkStatusChecker with network configuration"""

    def setUp(self):
        """Set up test with mock config"""
        self.config = Mock()
        self.config.get.side_effect = lambda key, default=None: {
            "network_timeout": 30,
            "connection_retry_attempts": 3,
            "retry_delay": 5,
            "enable_network_diagnostics": True,
        }.get(key, default)

        self.status_checker = StreamlinkStatusChecker(self.config)

    @patch("src.streamlink_status.streamlink.Streamlink")
    def test_streamlink_timeout_configuration(self, mock_streamlink):
        """Test that streamlink session is configured with proper timeout"""
        mock_session = Mock()
        mock_streamlink.return_value = mock_session

        # Create new checker to test initialization
        checker = StreamlinkStatusChecker(self.config)

        # Verify session timeout was set
        mock_session.set_option.assert_called_with("http-timeout", 30)

    @patch("src.streamlink_status.requests")
    def test_network_diagnostics_enabled(self, mock_requests):
        """Test network diagnostics when enabled"""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_requests.get.return_value = mock_response

        # Run diagnostics
        results = self.status_checker.run_network_diagnostics()

        # Should have results for all test endpoints
        self.assertEqual(len(results), 3)  # 3 endpoints in NETWORK_TEST_ENDPOINTS

        # All should be successful
        for url, (success, message) in results.items():
            self.assertTrue(success)
            self.assertIn("OK", message)

    def test_network_diagnostics_disabled(self):
        """Test network diagnostics when disabled"""
        self.config.get.side_effect = lambda key, default=None: {
            "enable_network_diagnostics": False
        }.get(key, default)

        results = self.status_checker.run_network_diagnostics()
        self.assertEqual(results, {})


@unittest.skipIf(not HAS_STREAMLINK, 
    "streamlink required - install with 'pip install streamlink>=5.0.0'")
class TestTwitchViewerNetworkConfig(unittest.TestCase):
    """Test TwitchViewer with network configuration"""

    def setUp(self):
        """Set up test with mock config"""
        self.config = Mock()
        self.config.get.side_effect = lambda key, default=None: {
            "network_timeout": 45,
            "debug": False,
            "player": "vlc",
            "preferred_quality": "best",
        }.get(key, default)

    @patch("src.twitch_viewer.streamlink.Streamlink")
    def test_twitch_viewer_timeout_configuration(self, mock_streamlink):
        """Test that TwitchViewer configures streamlink session timeout"""
        mock_session = Mock()
        mock_streamlink.return_value = mock_session

        # Create viewer
        viewer = TwitchViewer(self.config)

        # Verify session timeout was set
        mock_session.set_option.assert_called_with("http-timeout", 45)


if __name__ == "__main__":
    unittest.main()
