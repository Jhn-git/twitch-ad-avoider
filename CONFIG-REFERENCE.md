# Configuration Reference

This document provides a comprehensive reference for all TwitchAdAvoider configuration options, including examples, valid ranges, and security implications.

## Table of Contents

- [Configuration File](#configuration-file)
- [Core Settings](#core-settings)
- [Player Settings](#player-settings)
- [Logging Settings](#logging-settings)
- [Monitoring Settings](#monitoring-settings)
- [Security Considerations](#security-considerations)
- [Environment Variables](#environment-variables)
- [Configuration Examples](#configuration-examples)
- [Troubleshooting](#troubleshooting)

## Configuration File

TwitchAdAvoider stores its configuration in `config/settings.json`. The file is automatically created with default values on first run.

**Location**: `config/settings.json`  
**Format**: JSON  
**Encoding**: UTF-8  

### File Structure

```json
{
    "preferred_quality": "best",
    "player": "vlc",
    "cache_duration": 30,
    "debug": false,
    "log_to_file": false,
    "log_level": "INFO",
    "player_path": null,
    "player_args": "--network-caching=10000 --file-caching=10000 --live-caching=10000",
    "enable_status_monitoring": true,
    "status_check_interval": 300,
    "status_cache_duration": 60
}
```

## Core Settings

### `preferred_quality`

**Type**: String  
**Default**: `"best"`  
**Description**: Default stream quality to request from Twitch  

**Valid Values**:
- `"best"` - Highest available quality
- `"worst"` - Lowest available quality  
- `"720p"` - 720p resolution (if available)
- `"480p"` - 480p resolution (if available)
- `"360p"` - 360p resolution (if available)
- `"160p"` - 160p resolution (if available)

**Examples**:
```json
{
    "preferred_quality": "720p"
}
```

**Notes**:
- If the requested quality is unavailable, the application falls back to "best"
- Higher qualities require more bandwidth and system resources
- "best" may include 1080p or higher depending on the streamer

**Security**: No security implications

---

### `cache_duration`

**Type**: Integer  
**Default**: `30`  
**Description**: Stream buffer cache duration in seconds  

**Valid Range**: `0` to `3600` (0 seconds to 1 hour)

**Examples**:
```json
{
    "cache_duration": 60
}
```

**Notes**:
- Higher values provide better buffering but use more memory
- Lower values reduce latency but may cause stuttering
- Recommended range: 10-120 seconds
- Set to 0 to disable caching

**Security**: No security implications

## Player Settings

### `player`

**Type**: String  
**Default**: `"vlc"`  
**Description**: Video player to use for stream playback  

**Valid Values**:
- `"vlc"` - VLC Media Player
- `"mpv"` - MPV Player
- `"mpc-hc"` - Media Player Classic (Windows only)
- `"auto"` - Let streamlink choose automatically

**Examples**:
```json
{
    "player": "mpv"
}
```

**Notes**:
- Player must be installed and accessible
- "auto" lets streamlink detect available players
- GUI overrides this setting during stream launch

**Security**: No direct security implications, but ensure players are from trusted sources

---

### `player_path`

**Type**: String or null  
**Default**: `null`  
**Description**: Custom path to video player executable  

**Valid Values**:
- `null` - Use automatic detection
- Valid absolute file path to player executable

**Examples**:
```json
{
    "player_path": "C:\\Program Files\\VideoLAN\\VLC\\vlc.exe"
}
```

```json
{
    "player_path": "/usr/local/bin/mpv"
}
```

**Security Considerations**:
- **Path Traversal Protection**: Paths containing `../` sequences are blocked
- **Absolute Paths Required**: Relative paths are rejected for security
- **Character Validation**: Paths with control characters or shell metacharacters are rejected
- **Length Limits**: Maximum path length is 1000 characters

**Secure Examples**:
```json
// ✓ Secure - absolute path to trusted location
{
    "player_path": "C:\\Program Files\\VideoLAN\\VLC\\vlc.exe"
}

// ✓ Secure - standard system location
{
    "player_path": "/usr/bin/vlc"
}
```

**Insecure Examples**:
```json
// ✗ Insecure - path traversal
{
    "player_path": "../../../usr/bin/vlc"
}

// ✗ Insecure - relative path
{
    "player_path": "vlc.exe"
}
```

---

### `player_args`

**Type**: String or null
**Default**: `"--network-caching=10000 --file-caching=10000 --live-caching=10000"`
**Description**: Additional arguments to pass to the video player

**Default Behavior**:
- The default buffering arguments (10 second cache) help VLC handle stream discontinuities caused by Twitch ads
- These prevent visual corruption/artifacts when ads are inserted into the stream
- Streamlink also uses `--twitch-disable-ads` to minimize ad interruptions

**Valid Values**:
- String containing valid player arguments
- Empty string to disable all player arguments

**Examples**:
```json
{
    "player_args": "--network-caching=10000 --file-caching=10000 --live-caching=10000 --fullscreen --volume=50"
}
```

```json
{
    "player_args": "--fs --cache-secs=30"
}
```

**Security Considerations**:
- **Command Injection Prevention**: Arguments are validated to prevent command execution
- **Shell Metacharacter Blocking**: Characters like `;`, `|`, `&`, `$`, `<`, `>` are blocked
- **Quote Validation**: Proper shell quote parsing is enforced
- **Length Limits**: Maximum argument length is 500 characters

**Safe Arguments**:
```bash
# VLC arguments
--fullscreen              # ✓ Safe
--volume=50               # ✓ Safe
--no-osd                  # ✓ Safe
--cache=5000              # ✓ Safe

# MPV arguments  
--fs                      # ✓ Safe
--volume=50               # ✓ Safe
--cache-secs=30           # ✓ Safe
```

**Dangerous Arguments** (automatically blocked):
```bash
--volume=50; rm -rf /     # ✗ Command injection
--fullscreen && whoami    # ✗ Command chaining
--cache=yes | id          # ✗ Pipe operator
--volume=50`id`           # ✗ Command substitution
```

## Logging Settings

### `debug`

**Type**: Boolean  
**Default**: `false`  
**Description**: Enable debug mode with verbose logging  

**Valid Values**:
- `true` - Enable debug mode
- `false` - Disable debug mode

**Examples**:
```json
{
    "debug": true
}
```

**Notes**:
- Debug mode provides detailed operational information
- Useful for troubleshooting issues
- May impact performance slightly
- Can be overridden by command-line `--debug` flag

**Security**: Debug logs may contain sensitive information in production environments

---

### `log_to_file`

**Type**: Boolean  
**Default**: `false`  
**Description**: Write logs to file in addition to console  

**Valid Values**:
- `true` - Enable file logging
- `false` - Console logging only

**Examples**:
```json
{
    "log_to_file": true
}
```

**Notes**:
- Log file location: `logs/twitch_ad_avoider.log`
- Files are automatically rotated when they become large
- Useful for debugging and monitoring

**Security**: Log files may accumulate sensitive information over time

---

### `log_level`

**Type**: String  
**Default**: `"INFO"`  
**Description**: Minimum logging level to display  

**Valid Values** (in order of verbosity):
- `"DEBUG"` - Most verbose, includes all messages
- `"INFO"` - General information messages
- `"WARNING"` - Warning messages and above
- `"ERROR"` - Error messages and above
- `"CRITICAL"` - Only critical error messages

**Examples**:
```json
{
    "log_level": "WARNING"
}
```

**Notes**:
- Case-insensitive (accepts "debug", "Debug", "DEBUG")
- DEBUG level shows the most information
- CRITICAL level shows only the most serious issues

**Security**: Lower log levels may expose more internal information

## Monitoring Settings

### `enable_status_monitoring`

**Type**: Boolean  
**Default**: `true`  
**Description**: Enable automatic monitoring of favorite channels' live status  

**Valid Values**:
- `true` - Enable status monitoring
- `false` - Disable status monitoring

**Examples**:
```json
{
    "enable_status_monitoring": false
}
```

**Notes**:
- Monitors favorite channels for live/offline status
- Updates GUI with real-time status indicators
- Requires network connectivity
- Minimal performance impact

**Security**: No security implications, but generates network requests

---

### `status_check_interval`

**Type**: Integer  
**Default**: `300`  
**Description**: Interval between status checks in seconds  

**Valid Range**: `10` to `86400` (10 seconds to 24 hours)

**Examples**:
```json
{
    "status_check_interval": 120
}
```

**Notes**:
- Lower values provide more responsive updates
- Higher values reduce network usage
- Recommended range: 60-600 seconds
- Very low values may trigger rate limiting

**Security**: No security implications

---

### `status_cache_duration`

**Type**: Integer  
**Default**: `60`  
**Description**: Duration to cache status results in seconds  

**Valid Range**: `1` to `3600` (1 second to 1 hour)

**Examples**:
```json
{
    "status_cache_duration": 30
}
```

**Notes**:
- Caching reduces redundant network requests
- Lower values provide fresher data
- Should be less than `status_check_interval`
- Helps prevent API rate limiting

**Security**: No security implications

## Security Considerations

### Input Validation

All configuration values undergo strict validation:

1. **Type Checking**: Values must match expected types
2. **Range Validation**: Numeric values must be within acceptable ranges
3. **Character Filtering**: Strings are sanitized to remove dangerous characters
4. **Pattern Matching**: Some values must match specific patterns

### Path Security

File paths are subject to security validation:

- **Path Traversal Prevention**: Sequences like `../` are blocked
- **Absolute Path Requirement**: Relative paths are rejected
- **Character Whitelist**: Only safe characters are allowed
- **Length Limits**: Maximum path length enforced

### Argument Security

Player arguments undergo comprehensive security checks:

- **Command Injection Prevention**: Shell metacharacters are blocked
- **Quote Validation**: Proper shell parsing is enforced
- **Pattern Detection**: Malicious patterns are detected and blocked
- **Length Limits**: Maximum argument length enforced

### Configuration File Security

- **UTF-8 Encoding**: Prevents encoding-based attacks
- **JSON Validation**: Malformed JSON is rejected
- **Backup Creation**: Original files are preserved during updates
- **Permission Checks**: File permissions are validated

## Environment Variables

TwitchAdAvoider supports environment variables for player configuration:

### `TWITCH_PLAYER_PATH`

**Description**: Path to video player executable  
**Example**: `C:\Program Files\VideoLAN\VLC\vlc.exe`  
**Security**: Subject to same path validation as `player_path`

### `TWITCH_PLAYER_NAME`

**Description**: Name of the player for identification  
**Example**: `VLC`  
**Security**: No security implications

**Usage Example** (Windows PowerShell):
```powershell
$env:TWITCH_PLAYER_PATH = "C:\Program Files\VideoLAN\VLC\vlc.exe"
$env:TWITCH_PLAYER_NAME = "VLC"
python main.py --channel ninja
```

**Usage Example** (Unix/Linux):
```bash
export TWITCH_PLAYER_PATH="/usr/bin/vlc"
export TWITCH_PLAYER_NAME="VLC"
python main.py --channel ninja
```

## Configuration Examples

### Minimal Configuration

```json
{
    "preferred_quality": "best",
    "player": "auto"
}
```

### High-Quality Setup

```json
{
    "preferred_quality": "best",
    "player": "vlc",
    "player_path": "C:\\Program Files\\VideoLAN\\VLC\\vlc.exe",
    "player_args": "--network-caching=10000 --file-caching=10000 --live-caching=10000 --fullscreen --volume=75",
    "cache_duration": 60
}
```

### Low-Latency Setup

```json
{
    "preferred_quality": "720p",
    "player": "mpv",
    "player_args": "--profile=low-latency --cache-secs=5",
    "cache_duration": 5,
    "status_check_interval": 60
}
```

### Debug Configuration

```json
{
    "preferred_quality": "480p",
    "player": "vlc",
    "debug": true,
    "log_to_file": true,
    "log_level": "DEBUG",
    "status_check_interval": 30
}
```

### Security-Focused Setup

```json
{
    "preferred_quality": "720p",
    "player": "vlc",
    "player_path": "/usr/bin/vlc",
    "player_args": "--fullscreen --no-network",
    "debug": false,
    "log_to_file": true,
    "log_level": "WARNING"
}
```

### Monitoring Disabled

```json
{
    "preferred_quality": "best",
    "player": "auto",
    "enable_status_monitoring": false,
    "debug": false,
    "log_level": "ERROR"
}
```

## Troubleshooting

### Configuration Not Loading

**Symptoms**: Settings revert to defaults  
**Causes**: Invalid JSON, permission issues, encoding problems  
**Solutions**:
1. Validate JSON syntax using a JSON validator
2. Check file permissions on `config/settings.json`
3. Ensure UTF-8 encoding
4. Review application logs for validation errors

### Validation Errors

**Symptoms**: Configuration changes are rejected  
**Causes**: Invalid values, security violations, type mismatches  
**Solutions**:
1. Check value types match expected types
2. Ensure numeric values are within valid ranges
3. Review security restrictions for paths and arguments
4. Enable debug logging to see detailed validation errors

### Player Configuration Issues

**Symptoms**: Player not found or won't start  
**Causes**: Incorrect paths, security restrictions, missing players  
**Solutions**:
1. Verify player is installed and accessible
2. Use absolute paths for `player_path`
3. Test player arguments independently
4. Check for security validation errors in logs

### Performance Issues

**Symptoms**: High CPU usage, slow response  
**Causes**: Aggressive monitoring, debug mode, high cache values  
**Solutions**:
1. Increase `status_check_interval`
2. Disable `debug` mode
3. Reduce `cache_duration`
4. Disable `enable_status_monitoring` if not needed

### Security Warnings

**Symptoms**: Validation errors, blocked configurations  
**Causes**: Security measures preventing potentially dangerous settings  
**Solutions**:
1. Review security requirements in this document
2. Use safe, documented configuration patterns
3. Avoid shell metacharacters in arguments
4. Use absolute paths for executables

---

**Note**: Always validate configuration changes and test them with non-critical streams before applying to important usage scenarios.