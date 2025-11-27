"""
Comprehensive tests for input validation and security controls
Tests cover normal usage, edge cases, and security attack scenarios.
"""

import unittest
import os
import tempfile

from src.validators import (
    validate_channel_name,
    sanitize_player_args,
    validate_file_path,
    validate_numeric_range,
    validate_quality_option,
    validate_player_choice,
    validate_log_level,
    sanitize_string_input,
)
from src.exceptions import ValidationError


class TestChannelNameValidation(unittest.TestCase):
    """Test channel name validation with security controls"""

    def test_valid_channel_names(self):
        """Test valid Twitch channel names"""
        valid_channels = [
            "ninja",
            "shroud",
            "test_channel",
            "test123",
            "user_name_123",
            "streamer2024",
            "gaming_pro",
        ]
        for channel in valid_channels:
            result = validate_channel_name(channel)
            self.assertEqual(result, channel.lower())

    def test_case_normalization(self):
        """Test that channel names are normalized to lowercase"""
        self.assertEqual(validate_channel_name("NINJA"), "ninja")
        self.assertEqual(validate_channel_name("Test_Channel"), "test_channel")
        self.assertEqual(validate_channel_name("MiXeD_CaSe"), "mixed_case")

    def test_whitespace_handling(self):
        """Test whitespace removal"""
        self.assertEqual(validate_channel_name("  ninja  "), "ninja")
        self.assertEqual(validate_channel_name("\t test \n"), "test")

    def test_empty_channel_names(self):
        """Test empty channel name validation"""
        with self.assertRaises(ValidationError):
            validate_channel_name("")
        with self.assertRaises(ValidationError):
            validate_channel_name("   ")
        with self.assertRaises(ValidationError):
            validate_channel_name("\t\n")

    def test_length_validation(self):
        """Test channel name length constraints"""
        # Too short
        with self.assertRaises(ValidationError):
            validate_channel_name("ab")
        with self.assertRaises(ValidationError):
            validate_channel_name("abc")

        # Too long (>25 characters)
        with self.assertRaises(ValidationError):
            validate_channel_name("a" * 26)

        # Valid lengths
        self.assertEqual(validate_channel_name("abcd"), "abcd")  # 4 chars
        self.assertEqual(validate_channel_name("a" * 25), "a" * 25)  # 25 chars

    def test_invalid_characters(self):
        """Test rejection of invalid characters"""
        invalid_channels = [
            "test$channel",
            "user@name",
            "stream#er",
            "channel!",
            "user%name",
            "test space",
            "user-name",
            "stream.er",
            "test+name",
            "channel=name",
            "user(name)",
            "test[name]",
        ]
        for channel in invalid_channels:
            with self.assertRaises(ValidationError):
                validate_channel_name(channel)

    def test_security_patterns(self):
        """Test rejection of security attack patterns"""
        malicious_patterns = [
            "../../../etc/passwd",  # Path traversal
            "<script>alert(1)</script>",  # XSS
            "$(rm -rf /)",  # Command injection
            "`id`",  # Backtick command execution
            "test|id",  # Pipe command
            "test;whoami",  # Command separator
            "test&sleep 5",  # Background command
            "test>file.txt",  # Output redirection
            "test<input.txt",  # Input redirection
            "con",  # Windows reserved name
            "prn",  # Windows reserved name
            "aux",  # Windows reserved name
            "nul",  # Windows reserved name
            "com1",  # Windows reserved name
            "\x00test",  # Null byte
            "test\x0aecho",  # Newline injection
            "test\recho",  # Carriage return injection
        ]
        for pattern in malicious_patterns:
            with self.assertRaises(ValidationError):
                validate_channel_name(pattern)

    def test_control_characters(self):
        """Test rejection of control characters"""
        control_chars = [
            "test\x00name",  # Null
            "test\x01name",  # SOH
            "test\x08name",  # Backspace
            "test\x1fname",  # Unit separator
            "test\x7fname",  # DEL
            "test\x9fname",  # Application program command
        ]
        for char_test in control_chars:
            with self.assertRaises(ValidationError):
                validate_channel_name(char_test)


class TestPlayerArgsValidation(unittest.TestCase):
    """Test player arguments sanitization for command injection prevention"""

    def test_valid_player_args(self):
        """Test valid player arguments"""
        valid_args = [
            "--fullscreen",
            "--volume=50",
            "--no-video",
            "--cache=yes",
            '--user-agent="VLC/3.0.0"',
            '--http-user-agent "Custom Agent"',
            "--start-time=30",
            "-fs --volume 75",
        ]
        for args in valid_args:
            result = sanitize_player_args(args)
            self.assertEqual(result, args)

    def test_none_and_empty_args(self):
        """Test None and empty argument handling"""
        self.assertIsNone(sanitize_player_args(None))
        self.assertIsNone(sanitize_player_args(""))
        self.assertIsNone(sanitize_player_args("   "))

    def test_command_injection_prevention(self):
        """Test prevention of command injection attacks"""
        malicious_args = [
            "--volume=50; rm -rf /",  # Command separator
            "--fullscreen && whoami",  # Command chaining
            "--cache=yes | id",  # Pipe command
            "--volume=50`id`",  # Backtick execution
            "--user=$(whoami)",  # Command substitution
            "--cache=yes > /tmp/test",  # Output redirection
            "--volume < /etc/passwd",  # Input redirection
            '--fullscreen; echo "pwned"',  # Multiple commands
            "--cache=yes & sleep 10",  # Background execution
            "--volume=50\\x41",  # Hex escape
        ]
        for args in malicious_args:
            with self.assertRaises(ValidationError):
                sanitize_player_args(args)

    def test_control_characters_rejection(self):
        """Test rejection of control characters"""
        control_char_args = [
            "--volume=50\x00",  # Null byte
            "--fullscreen\x01test",  # SOH
            "--cache\x08yes",  # Backspace
            "--volume\x1f50",  # Unit separator
            "--test\x7farg",  # DEL
        ]
        for args in control_char_args:
            with self.assertRaises(ValidationError):
                sanitize_player_args(args)

    def test_shell_parsing_validation(self):
        """Test shell parsing validation for malformed quotes"""
        malformed_args = [
            '--user-agent="unclosed quote',
            "--cache='unclosed single quote",
            # Note: Some complex quote nesting might be valid in shlex
            # so we focus on clearly malformed cases
        ]
        for args in malformed_args:
            with self.assertRaises(ValidationError):
                sanitize_player_args(args)

    def test_length_validation(self):
        """Test argument length limits"""
        # Valid length (just under limit)
        valid_long_args = "--cache=" + "a" * 485  # Total ~493 chars, under 500
        result = sanitize_player_args(valid_long_args)
        self.assertEqual(result, valid_long_args)

        # Too long (over 500 chars)
        too_long_args = "--cache=" + "a" * 495  # Total ~503 chars, over 500
        with self.assertRaises(ValidationError):
            sanitize_player_args(too_long_args)


class TestFilePathValidation(unittest.TestCase):
    """Test file path validation for security"""

    def test_valid_file_paths(self):
        """Test valid file paths"""
        valid_paths = [
            "/usr/bin/vlc",
            "C:\\Program Files\\VLC\\vlc.exe",
            "/Applications/VLC.app/Contents/MacOS/VLC",
            r"C:\ProgramData\chocolatey\lib\mpv\tools\mpv.exe",
        ]
        for path in valid_paths:
            result = validate_file_path(path, must_exist=False)
            self.assertIsInstance(result, str)
            self.assertTrue(os.path.isabs(result))

    def test_none_and_empty_paths(self):
        """Test None and empty path handling"""
        self.assertIsNone(validate_file_path(None))
        self.assertIsNone(validate_file_path(""))
        self.assertIsNone(validate_file_path("   "))

    def test_path_traversal_prevention(self):
        """Test prevention of path traversal attacks"""
        traversal_paths = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\cmd.exe",
            "/usr/bin/../../../etc/shadow",
            "C:\\Program Files\\..\\..\\Windows\\System32\\calc.exe",
            "./../../sensitive/file.txt",
            "normal/path/../../../../../../etc/hosts",
        ]
        for path in traversal_paths:
            with self.assertRaises(ValidationError):
                validate_file_path(path)

    def test_forbidden_characters(self):
        """Test rejection of forbidden characters"""
        forbidden_paths = [
            "/usr/bin/vlc\x00hidden",  # Null byte
            "C:\\Program Files\\VLC\\vlc.exe\x01",  # Control char
            '/usr/bin/vlc"quotes"',  # Quotes
            "C:\\test<redirect>vlc",  # Redirection chars
            "/usr/bin/vlc|pipe",  # Pipe character
            "C:\\test*wildcard.exe",  # Wildcard
            "/usr/bin/vlc?query",  # Question mark
        ]
        for path in forbidden_paths:
            with self.assertRaises(ValidationError):
                validate_file_path(path)

    def test_length_limits(self):
        """Test path length limits"""
        # Create a very long path
        long_path = "/usr/bin/" + "a" * 1000
        with self.assertRaises(ValidationError):
            validate_file_path(long_path)

    def test_absolute_path_conversion(self):
        """Test conversion to absolute paths"""
        # Test with absolute paths (which should work fine)
        abs_path = "/usr/bin/test"
        result = validate_file_path(abs_path, must_exist=False)
        self.assertTrue(os.path.isabs(result))

        # Note: Relative paths with .. are blocked by our security validation
        # which is the intended behavior for security

    def test_existence_checking(self):
        """Test file existence validation"""
        # Test with existing file
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            existing_path = tmp.name

        try:
            # Should succeed when file exists
            result = validate_file_path(existing_path, must_exist=True)
            self.assertIsNotNone(result)

            # Should fail when file doesn't exist
            os.unlink(existing_path)
            with self.assertRaises(ValidationError):
                validate_file_path(existing_path, must_exist=True)
        except FileNotFoundError:
            pass  # File already deleted


class TestNumericRangeValidation(unittest.TestCase):
    """Test numeric range validation"""

    def test_valid_integers(self):
        """Test valid integer values"""
        self.assertEqual(validate_numeric_range(5, 0, 10), 5)
        self.assertEqual(validate_numeric_range("7", 0, 10), 7)
        self.assertEqual(validate_numeric_range(0, 0, 10), 0)
        self.assertEqual(validate_numeric_range(10, 0, 10), 10)

    def test_valid_floats(self):
        """Test valid float values"""
        self.assertEqual(validate_numeric_range(5.5, 0.0, 10.0, float), 5.5)
        self.assertEqual(validate_numeric_range("7.2", 0, 10, float), 7.2)
        self.assertEqual(validate_numeric_range(0.0, 0, 10, float), 0.0)

    def test_range_violations(self):
        """Test range boundary violations"""
        # Below minimum
        with self.assertRaises(ValidationError):
            validate_numeric_range(-1, 0, 10)

        # Above maximum
        with self.assertRaises(ValidationError):
            validate_numeric_range(11, 0, 10)

        # Float range violations
        with self.assertRaises(ValidationError):
            validate_numeric_range(-0.1, 0.0, 10.0, float)

        with self.assertRaises(ValidationError):
            validate_numeric_range(10.1, 0.0, 10.0, float)

    def test_type_conversion_errors(self):
        """Test invalid type conversions"""
        with self.assertRaises(ValidationError):
            validate_numeric_range("not_a_number", 0, 10)

        with self.assertRaises(ValidationError):
            validate_numeric_range(None, 0, 10)

        with self.assertRaises(ValidationError):
            validate_numeric_range([], 0, 10)

    def test_no_limits(self):
        """Test validation without min/max limits"""
        self.assertEqual(validate_numeric_range(100), 100)
        self.assertEqual(validate_numeric_range(-50), -50)
        self.assertEqual(validate_numeric_range(3.14159, data_type=float), 3.14159)


class TestQualityAndPlayerValidation(unittest.TestCase):
    """Test quality and player choice validation"""

    def test_valid_quality_options(self):
        """Test valid quality options"""
        valid_qualities = ["best", "worst", "720p", "480p", "360p", "160p"]
        for quality in valid_qualities:
            self.assertEqual(validate_quality_option(quality), quality)
            # Test case insensitivity
            self.assertEqual(validate_quality_option(quality.upper()), quality)

    def test_invalid_quality_options(self):
        """Test invalid quality options"""
        invalid_qualities = ["1080p", "4k", "ultra", "", None, "720P_60"]
        for quality in invalid_qualities:
            with self.assertRaises(ValidationError):
                validate_quality_option(quality)

    def test_valid_player_choices(self):
        """Test valid player choices"""
        valid_players = ["vlc", "mpv", "mpc-hc", "auto"]
        for player in valid_players:
            self.assertEqual(validate_player_choice(player), player)
            # Test case normalization
            self.assertEqual(validate_player_choice(player.upper()), player)

    def test_invalid_player_choices(self):
        """Test invalid player choices"""
        invalid_players = ["chrome", "firefox", "", None, "unknown_player"]
        for player in invalid_players:
            with self.assertRaises(ValidationError):
                validate_player_choice(player)


class TestLogLevelValidation(unittest.TestCase):
    """Test log level validation"""

    def test_valid_log_levels(self):
        """Test valid log levels"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        for level in valid_levels:
            self.assertEqual(validate_log_level(level), level)
            # Test case normalization
            self.assertEqual(validate_log_level(level.lower()), level)

    def test_invalid_log_levels(self):
        """Test invalid log levels"""
        invalid_levels = ["TRACE", "FATAL", "VERBOSE", "", None, "CUSTOM"]
        for level in invalid_levels:
            with self.assertRaises(ValidationError):
                validate_log_level(level)


class TestStringSanitization(unittest.TestCase):
    """Test general string sanitization"""

    def test_basic_sanitization(self):
        """Test basic string sanitization"""
        self.assertEqual(sanitize_string_input("  test  "), "test")
        self.assertEqual(sanitize_string_input("normal string"), "normal string")
        self.assertIsNone(sanitize_string_input(None))
        self.assertIsNone(sanitize_string_input(""))

    def test_control_character_removal(self):
        """Test removal of control characters"""
        dirty_string = "test\x00\x01\x08\x1f\x7f\x9fstring"
        clean_string = sanitize_string_input(dirty_string)
        self.assertEqual(clean_string, "teststring")

    def test_length_validation(self):
        """Test string length validation"""
        # Valid length
        valid_string = "a" * 100
        result = sanitize_string_input(valid_string, max_length=100)
        self.assertEqual(result, valid_string)

        # Too long
        too_long = "a" * 101
        with self.assertRaises(ValidationError):
            sanitize_string_input(too_long, max_length=100)

    def test_empty_string_handling(self):
        """Test empty string handling"""
        # Allow empty
        self.assertIsNone(sanitize_string_input("   ", allow_empty=True))

        # Disallow empty
        with self.assertRaises(ValidationError):
            sanitize_string_input("   ", allow_empty=False)

    def test_type_validation(self):
        """Test input type validation"""
        with self.assertRaises(ValidationError):
            sanitize_string_input(123)

        with self.assertRaises(ValidationError):
            sanitize_string_input(["list"])

        with self.assertRaises(ValidationError):
            sanitize_string_input({"dict": "value"})


if __name__ == "__main__":
    unittest.main()
