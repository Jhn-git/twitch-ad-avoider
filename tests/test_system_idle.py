"""Tests for system-wide input idle time detection."""

import unittest
from unittest.mock import patch

from src.system_idle import _idle_millis, get_system_idle_seconds


class TestIdleMillis(unittest.TestCase):
    def test_normal_forward_difference(self):
        self.assertEqual(_idle_millis(1000, 900), 100)
        self.assertEqual(_idle_millis(1000, 1000), 0)

    def test_handles_32_bit_tick_count_wraparound(self):
        # Last input was 96ms before the 32-bit tick counter wrapped to 0;
        # 100ms have elapsed since the wrap, so total idle time is 196ms.
        self.assertEqual(_idle_millis(100, 4294967200), 196)


class TestGetSystemIdleSeconds(unittest.TestCase):
    def test_returns_zero_on_non_windows(self):
        with patch("src.system_idle.os.name", "posix"):
            self.assertEqual(get_system_idle_seconds(), 0.0)


if __name__ == "__main__":
    unittest.main()
