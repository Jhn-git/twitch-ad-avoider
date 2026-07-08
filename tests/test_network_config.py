"""Tests for network and Streamlink playback configuration."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src.config_manager import ConfigManager
from src.web_stream_service import WebStreamService


class TestNetworkConfiguration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "test_settings.json"
        self.config = ConfigManager(self.config_path)

    def tearDown(self):
        if self.config_path.exists():
            self.config_path.unlink()
        os.rmdir(self.temp_dir)

    def test_network_timeout_validation(self):
        for timeout in (10, 15, 30, 60, 120):
            self.assertTrue(self.config.set("network_timeout", timeout))
            self.assertEqual(self.config.get("network_timeout"), timeout)

        for timeout in (5, 9, 121, -1, 0, "30", None):
            self.assertFalse(self.config.set("network_timeout", timeout))

    def test_retry_settings_validation(self):
        for attempts in (1, 3, 10):
            self.assertTrue(self.config.set("connection_retry_attempts", attempts))
        for attempts in (0, 11, -1, "3", None):
            self.assertFalse(self.config.set("connection_retry_attempts", attempts))

        for delay in (1, 5, 30):
            self.assertTrue(self.config.set("retry_delay", delay))
        for delay in (0, 31, -1, "5", None):
            self.assertFalse(self.config.set("retry_delay", delay))

    def test_network_diagnostics_setting(self):
        self.assertTrue(self.config.set("enable_network_diagnostics", True))
        self.assertTrue(self.config.set("enable_network_diagnostics", False))

        for value in ("true", "false", 1, 0, None):
            self.assertFalse(self.config.set("enable_network_diagnostics", value))

    def test_default_network_settings(self):
        self.assertEqual(self.config.get("network_timeout"), 30)
        self.assertEqual(self.config.get("connection_retry_attempts"), 3)
        self.assertEqual(self.config.get("retry_delay"), 5)
        self.assertTrue(self.config.get("enable_network_diagnostics"))

    @patch("src.web_stream_service.streamlink.Streamlink")
    def test_stream_service_configures_streamlink_session(self, mock_streamlink):
        mock_session = Mock()
        mock_streamlink.return_value = mock_session
        self.config.set("network_timeout", 45)
        self.config.set("hls_live_edge", 4)
        self.config.set("twitch_low_latency", True)

        service = WebStreamService(self.config, lambda _event: None, lambda *_args: None)
        service._new_streamlink_session()

        mock_session.set_option.assert_any_call("http-timeout", 45)
        mock_session.set_option.assert_any_call("hls-live-edge", 4)
        mock_session.set_plugin_option.assert_any_call("twitch", "disable-ads", True)
        mock_session.set_plugin_option.assert_any_call("twitch", "low-latency", True)

    @patch("src.web_stream_service.streamlink.Streamlink")
    def test_stream_service_does_not_enable_low_latency_when_disabled(self, mock_streamlink):
        mock_session = Mock()
        mock_streamlink.return_value = mock_session
        self.config.set("twitch_low_latency", False)

        service = WebStreamService(self.config, lambda _event: None, lambda *_args: None)
        service._new_streamlink_session()

        self.assertNotIn(
            (("twitch", "low-latency", True),),
            [call.args for call in mock_session.set_plugin_option.call_args_list],
        )


if __name__ == "__main__":
    unittest.main()
