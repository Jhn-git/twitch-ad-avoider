"""Tests for input validation and sanitization helpers."""

import os
import tempfile
import unittest

from src.exceptions import ValidationError
from src.validators import (
    sanitize_string_input,
    validate_channel_name,
    validate_file_path,
    validate_log_level,
    validate_numeric_range,
    validate_quality_option,
)


class TestChannelNameValidation(unittest.TestCase):
    def test_valid_channel_names(self):
        for channel in ("ninja", "shroud", "test_channel", "test123", "gaming_pro"):
            self.assertEqual(validate_channel_name(channel), channel.lower())

    def test_case_and_whitespace_normalization(self):
        self.assertEqual(validate_channel_name("  NINJA  "), "ninja")
        self.assertEqual(validate_channel_name("\t Test_Channel \n"), "test_channel")

    def test_invalid_channel_names(self):
        invalid_channels = [
            "",
            "abc",
            "a" * 26,
            "test$channel",
            "test space",
            "../../../etc/passwd",
            "<script>alert(1)</script>",
            "$(whoami)",
            "`id`",
            "test|id",
            "test;whoami",
            "con",
            "nul",
            "test\x00name",
            "test\nname",
        ]
        for channel in invalid_channels:
            with self.subTest(channel=channel):
                with self.assertRaises(ValidationError):
                    validate_channel_name(channel)


class TestFilePathValidation(unittest.TestCase):
    def test_valid_file_paths(self):
        for path in ("/usr/bin/ffmpeg", r"C:\Tools\ffmpeg\bin\ffmpeg.exe"):
            result = validate_file_path(path, must_exist=False)
            self.assertIsInstance(result, str)
            self.assertTrue(os.path.isabs(result))

    def test_none_and_empty_paths(self):
        self.assertIsNone(validate_file_path(None))
        self.assertIsNone(validate_file_path(""))
        self.assertIsNone(validate_file_path("   "))

    def test_path_traversal_prevention(self):
        for path in (
            "../../../etc/passwd",
            r"..\..\windows\system32\cmd.exe",
            "/usr/bin/../../../etc/shadow",
            "normal/path/../../../../etc/hosts",
        ):
            with self.subTest(path=path):
                with self.assertRaises(ValidationError):
                    validate_file_path(path)

    def test_forbidden_characters(self):
        for path in (
            "/usr/bin/ffmpeg\x00hidden",
            "C:\\Tools\\ffmpeg.exe\x01",
            '/usr/bin/ffmpeg"quotes"',
            r"C:\test<redirect>ffmpeg",
            "/usr/bin/ffmpeg|pipe",
            r"C:\test*wildcard.exe",
            "/usr/bin/ffmpeg?query",
        ):
            with self.subTest(path=path):
                with self.assertRaises(ValidationError):
                    validate_file_path(path)

    def test_existence_checking(self):
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            existing_path = tmp.name

        try:
            self.assertIsNotNone(validate_file_path(existing_path, must_exist=True))
            os.unlink(existing_path)
            with self.assertRaises(ValidationError):
                validate_file_path(existing_path, must_exist=True)
        except FileNotFoundError:
            pass


class TestNumericRangeValidation(unittest.TestCase):
    def test_valid_integers(self):
        self.assertEqual(validate_numeric_range(5, 0, 10), 5)
        self.assertEqual(validate_numeric_range("7", 0, 10), 7)

    def test_valid_floats(self):
        self.assertEqual(validate_numeric_range(5.5, 0.0, 10.0, float), 5.5)
        self.assertEqual(validate_numeric_range("7.2", 0, 10, float), 7.2)

    def test_range_violations(self):
        with self.assertRaises(ValidationError):
            validate_numeric_range(-1, 0, 10)
        with self.assertRaises(ValidationError):
            validate_numeric_range(11, 0, 10)
        with self.assertRaises(ValidationError):
            validate_numeric_range("not_a_number", 0, 10)


class TestQualityValidation(unittest.TestCase):
    def test_valid_quality_options(self):
        for quality in ("best", "worst", "720p", "480p", "360p", "160p"):
            self.assertEqual(validate_quality_option(quality), quality)
            self.assertEqual(validate_quality_option(quality.upper()), quality)

    def test_invalid_quality_options(self):
        for quality in ("1080p", "4k", "ultra", "", None, "720P_60"):
            with self.assertRaises(ValidationError):
                validate_quality_option(quality)


class TestLogLevelValidation(unittest.TestCase):
    def test_valid_log_levels(self):
        for level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            self.assertEqual(validate_log_level(level), level)
            self.assertEqual(validate_log_level(level.lower()), level)

    def test_invalid_log_levels(self):
        for level in ("TRACE", "FATAL", "VERBOSE", "", None):
            with self.assertRaises(ValidationError):
                validate_log_level(level)


class TestStringSanitization(unittest.TestCase):
    def test_basic_sanitization(self):
        self.assertEqual(sanitize_string_input("  test  "), "test")
        self.assertIsNone(sanitize_string_input(None))
        self.assertIsNone(sanitize_string_input(""))

    def test_control_character_removal(self):
        dirty_string = "test\x00\x01\x08\x1f\x7f\x9fstring"
        self.assertEqual(sanitize_string_input(dirty_string), "teststring")

    def test_length_and_type_validation(self):
        self.assertEqual(sanitize_string_input("a" * 100, max_length=100), "a" * 100)
        with self.assertRaises(ValidationError):
            sanitize_string_input("a" * 101, max_length=100)
        with self.assertRaises(ValidationError):
            sanitize_string_input(123)


if __name__ == "__main__":
    unittest.main()
