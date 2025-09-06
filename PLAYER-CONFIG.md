# Player Configuration Guide

This guide covers advanced player configuration, troubleshooting, and security considerations for TwitchAdAvoider.

## Table of Contents

- [Overview](#overview)
- [Supported Players](#supported-players)
- [Configuration Methods](#configuration-methods)
- [Player-Specific Configuration](#player-specific-configuration)
- [Advanced Settings](#advanced-settings)
- [Security Considerations](#security-considerations)
- [Troubleshooting](#troubleshooting)
- [Performance Optimization](#performance-optimization)

## Overview

TwitchAdAvoider supports multiple video players and provides flexible configuration options. The application automatically detects installed players and can be configured for optimal performance and security.

### Player Detection Hierarchy

The application searches for players in this order:

1. **Environment Variables** (`TWITCH_PLAYER_PATH`, `TWITCH_PLAYER_NAME`)
2. **Manual Configuration** (`player_path` and `player` in settings)
3. **System PATH** (searches for player executables)
4. **Common Installation Paths** (OS-specific default locations)
5. **Auto Fallback** (lets streamlink choose)

## Supported Players

### VLC Media Player (Recommended)

**Pros**:
- Excellent format support
- Stable and reliable
- Cross-platform availability
- Good performance with streams

**Cons**:
- Larger resource footprint
- More complex interface

**Installation**:
```bash
# Windows (Chocolatey)
choco install vlc

# macOS (Homebrew)
brew install --cask vlc

# Ubuntu/Debian
sudo apt install vlc

# Fedora
sudo dnf install vlc
```

### MPV (Lightweight)

**Pros**:
- Minimal resource usage
- Fast startup times
- Excellent performance
- Keyboard-friendly controls

**Cons**:
- Minimal GUI interface
- Steeper learning curve

**Installation**:
```bash
# Windows (Chocolatey)
choco install mpv

# macOS (Homebrew)
brew install mpv

# Ubuntu/Debian
sudo apt install mpv

# Fedora
sudo dnf install mpv
```

### MPC-HC (Windows Only)

**Pros**:
- Native Windows integration
- Low resource usage
- Good format support

**Cons**:
- Windows-only
- Development discontinued
- Security concerns with old versions

**Installation**:
- Download from [mpc-hc.org](https://mpc-hc.org/)
- Use package managers like Chocolatey

## Configuration Methods

### Method 1: Environment Variables

Set environment variables for automatic detection:

```bash
# Windows (PowerShell)
$env:TWITCH_PLAYER_PATH = "C:\Program Files\VideoLAN\VLC\vlc.exe"
$env:TWITCH_PLAYER_NAME = "VLC"

# Windows (Command Prompt)
set TWITCH_PLAYER_PATH=C:\Program Files\VideoLAN\VLC\vlc.exe
set TWITCH_PLAYER_NAME=VLC

# macOS/Linux (Bash)
export TWITCH_PLAYER_PATH="/usr/bin/vlc"
export TWITCH_PLAYER_NAME="VLC"
```

### Method 2: Configuration File

Edit `config/settings.json`:

```json
{
    "player": "vlc",
    "player_path": "/usr/bin/vlc",
    "player_args": "--fullscreen --volume=75"
}
```

### Method 3: GUI Configuration

The GUI allows easy player selection and automatically saves configuration.

## Player-Specific Configuration

### VLC Configuration

**Basic Configuration**:
```json
{
    "player": "vlc",
    "player_path": "C:\\Program Files\\VideoLAN\\VLC\\vlc.exe",
    "player_args": "--fullscreen --volume=50"
}
```

**Recommended Arguments**:
```bash
--fullscreen              # Start in fullscreen mode
--volume=50               # Set volume (0-100)
--no-video-title-show     # Hide filename overlay
--no-osd                  # Disable on-screen display
--intf=dummy              # Minimal interface
--play-and-exit           # Exit after playback
--cache=5000              # Buffer size (milliseconds)
```

**Advanced VLC Options**:
```bash
--network-caching=5000    # Network cache (ms)
--live-caching=1000       # Live stream cache (ms)
--no-stats                # Disable statistics
--no-sub-autodetect-file  # Disable subtitle detection
--preferred-resolution=720 # Prefer specific resolution
```

### MPV Configuration

**Basic Configuration**:
```json
{
    "player": "mpv",
    "player_path": "/usr/bin/mpv",
    "player_args": "--fs --volume=50"
}
```

**Recommended Arguments**:
```bash
--fs                      # Fullscreen
--volume=50               # Volume level
--cache-secs=30           # Cache duration
--no-osc                  # Disable on-screen controller
--no-border               # Remove window border
--ontop                   # Keep window on top
--profile=low-latency     # Low latency profile
```

**MPV Performance Options**:
```bash
--hwdec=auto              # Hardware decoding
--vo=gpu                  # GPU video output
--cache=yes               # Enable cache
--demuxer-max-bytes=50M   # Maximum demux buffer
--demuxer-readahead-secs=10 # Readahead seconds
```

### MPC-HC Configuration

**Basic Configuration**:
```json
{
    "player": "mpc-hc",
    "player_path": "C:\\Program Files\\MPC-HC\\mpc-hc64.exe",
    "player_args": "/fullscreen /volume 50"
}
```

**Recommended Arguments**:
```bash
/fullscreen               # Start fullscreen
/volume 50                # Set volume
/close                    # Close after playback
/minimized                # Start minimized
/new                      # Open in new instance
```

## Advanced Settings

### Custom Player Integration

For unsupported players, you can specify custom paths and arguments:

```json
{
    "player": "auto",
    "player_path": "/path/to/custom/player",
    "player_args": "--custom-args"
}
```

**Requirements for Custom Players**:
- Must accept stream URL as last argument
- Should support HTTP/HTTPS streams
- Must handle HLS (HTTP Live Streaming) format

### PowerShell Integration

TwitchAdAvoider includes PowerShell utilities for Windows users:

```powershell
# Import the module
Import-Module .\scripts\TwitchUtilities.psm1

# Set player preferences
Set-TwitchPlayer -Name "VLC" -Path "C:\Program Files\VideoLAN\VLC\vlc.exe"

# Launch stream
Start-TwitchStream -Channel "ninja" -Quality "720p"
```

### Configuration Validation

All player configurations are validated for security:

```python
# Safe configuration
{
    "player_args": "--fullscreen --volume=50"  # ✓ Safe
}

# Blocked configuration
{
    "player_args": "--volume=50; rm -rf /"     # ✗ Command injection
}
```

## Security Considerations

### Player Path Security

**Best Practices**:
1. Use absolute paths to prevent PATH hijacking
2. Verify player executables are from trusted sources
3. Keep players updated for security patches
4. Avoid temporary directories for player executables

**Secure Path Examples**:
```json
{
    "player_path": "C:\\Program Files\\VideoLAN\\VLC\\vlc.exe",     // ✓ Secure
    "player_path": "/usr/bin/vlc",                                   // ✓ Secure
    "player_path": "/Applications/VLC.app/Contents/MacOS/VLC"       // ✓ Secure
}
```

**Insecure Paths**:
```json
{
    "player_path": "../../../etc/passwd",           // ✗ Path traversal
    "player_path": "vlc",                           // ✗ Relative path
    "player_path": "%TEMP%\\vlc.exe"                // ✗ Temporary directory
}
```

### Player Arguments Security

**Safe Arguments**:
- Standard player options (volume, fullscreen, etc.)
- Quoted string values
- Numeric parameters

**Dangerous Patterns** (automatically blocked):
- Command separators (`;`, `&`, `|`)
- Redirection operators (`>`, `<`)
- Command substitution (`$()`, backticks)
- Path traversal sequences

**Validation Examples**:
```bash
# Safe arguments
--fullscreen --volume=50              # ✓ Safe
--cache=yes --no-osd                  # ✓ Safe
--user-agent="Custom Agent"           # ✓ Safe

# Blocked arguments
--volume=50; rm -rf /                 # ✗ Command injection
--cache=yes && whoami                 # ✗ Command chaining
--volume=50`id`                       # ✗ Command substitution
```

## Troubleshooting

### Common Issues

#### Player Not Found

**Symptoms**:
- "Video player not found" error
- Application falls back to "auto" mode

**Solutions**:
1. **Install a supported player**:
   ```bash
   # Ubuntu/Debian
   sudo apt install vlc
   
   # Windows (Chocolatey)
   choco install vlc
   ```

2. **Set manual configuration**:
   ```json
   {
       "player": "vlc",
       "player_path": "/full/path/to/vlc"
   }
   ```

3. **Check PATH environment**:
   ```bash
   # Windows
   where vlc
   
   # macOS/Linux
   which vlc
   ```

#### Player Starts But No Video

**Possible Causes**:
- Incorrect player arguments
- Player doesn't support stream format
- Network connectivity issues

**Solutions**:
1. **Test with minimal arguments**:
   ```json
   {
       "player_args": null
   }
   ```

2. **Check player compatibility**:
   ```bash
   # Test direct stream
   vlc "https://example.com/stream.m3u8"
   ```

3. **Enable debug logging**:
   ```json
   {
       "debug": true,
       "log_to_file": true
   }
   ```

#### Performance Issues

**Symptoms**:
- Buffering or stuttering
- High CPU/memory usage
- Poor video quality

**Solutions**:

1. **Optimize cache settings**:
   ```bash
   # VLC
   --cache=10000 --network-caching=10000
   
   # MPV
   --cache-secs=30 --demuxer-readahead-secs=10
   ```

2. **Enable hardware decoding**:
   ```bash
   # VLC
   --avcodec-hw=any
   
   # MPV
   --hwdec=auto
   ```

3. **Reduce quality if needed**:
   ```json
   {
       "preferred_quality": "720p"
   }
   ```

#### Security Validation Errors

**Symptoms**:
- "Player arguments contain forbidden characters"
- Configuration validation failures

**Solutions**:
1. **Review argument syntax**:
   - Use only documented player options
   - Quote complex values properly
   - Avoid shell metacharacters

2. **Test arguments separately**:
   ```bash
   # Test VLC arguments
   vlc --help | grep fullscreen
   ```

3. **Use minimal configuration**:
   ```json
   {
       "player_args": "--fullscreen"
   }
   ```

### Debug Mode

Enable detailed logging for troubleshooting:

```json
{
    "debug": true,
    "log_to_file": true,
    "log_level": "DEBUG"
}
```

**Debug Information Includes**:
- Player detection process
- Configuration validation steps
- Stream URL resolution
- Player launch commands
- Error details

### Log Analysis

Check logs for common patterns:

```bash
# View recent logs
tail -f logs/twitch_ad_avoider.log

# Search for player issues
grep -i "player" logs/twitch_ad_avoider.log

# Check validation errors
grep -i "validation" logs/twitch_ad_avoider.log
```

## Performance Optimization

### Player-Specific Optimizations

#### VLC Optimization

```bash
# Low-latency streaming
--network-caching=1000 --live-caching=500 --clock-jitter=0

# High-quality playback  
--network-caching=5000 --avcodec-hw=any --vout=direct3d11

# Minimal resource usage
--intf=dummy --no-osd --no-stats --no-sub-autodetect-file
```

#### MPV Optimization

```bash
# Performance profile
--profile=low-latency --hwdec=auto --vo=gpu

# Quality profile
--profile=gpu-hq --scale=ewa_lanczossharp --cscale=ewa_lanczossoft

# Low resource profile
--vo=x11 --hwdec=no --cache-secs=5
```

### System Optimization

1. **Network Settings**:
   - Use wired connection when possible
   - Optimize router QoS settings
   - Close bandwidth-heavy applications

2. **System Resources**:
   - Close unnecessary applications
   - Ensure adequate RAM/CPU
   - Update graphics drivers

3. **Stream Quality**:
   - Choose appropriate quality for connection
   - Use "best" only on fast connections
   - Consider "720p" for most users

### Monitoring Performance

```bash
# Monitor resource usage
top -p $(pgrep vlc)
htop

# Network monitoring
netstat -i
iftop
```

---

**Note**: Always prioritize security when configuring players. Use the latest versions and validate all custom configurations.