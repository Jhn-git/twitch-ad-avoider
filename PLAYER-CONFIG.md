# Player Configuration Guide

This document explains the simplified player detection and configuration options available in TwitchAdAvoider.

## Player Selection Priority

The application uses a straightforward priority system for player selection:

### Priority 1: GUI Selection (Primary)
- The player selected in the GUI dropdown is the primary choice
- Available options: VLC, MPV, MPC-HC, Auto
- This selection takes precedence over configuration files

### Priority 2: Manual Player Path (Override)
- If `player_path` is specified in settings.json, it will be used regardless of GUI selection
- Useful for custom player installations or specific player versions

```json
{
    "player_path": "C:\\Program Files\\VideoLAN\\VLC\\vlc.exe",
    "player": "vlc"
}
```

### Priority 3: Auto Detection
- When "Auto" is selected in GUI, streamlink handles player detection
- Streamlink will find the best available player automatically

### Priority 4: Player Search
- If the selected player isn't found in PATH, the app searches common installation paths
- Searches both system PATH and standard installation directories

### Priority 5: Environment Variables (PowerShell Integration)
- PowerShell script exports `TWITCH_PLAYER_NAME` and `TWITCH_PLAYER_PATH`
- Fallback option when GUI selection can't be found
- Maintains compatibility with PowerShell scripts

### Final Fallback: Streamlink Auto-Detection
- If all else fails, streamlink handles player detection automatically

## Configuration Options (settings.json)

```json
{
    "preferred_quality": "best",           // Stream quality: best, worst, 720p, etc.
    "player": "vlc",                       // Preferred player: vlc, mpv, mpc-hc, etc.
    "cache_duration": 30,                  // Cache duration in seconds
    "debug": true,                         // Enable debug logging
    "player_path": "C:\\path\\to\\player.exe",  // Manual player path override
    "player_args": "--no-border --ontop"   // Custom player arguments
}
```

### Configuration Examples

**Force specific VLC installation:**
```json
{
    "player": "vlc",
    "player_path": "C:\\Program Files\\VideoLAN\\VLC\\vlc.exe"
}
```

**Use MPV with custom arguments:**
```json
{
    "player": "mpv",
    "player_args": "--fs --no-border"
}
```

**Enable debug logging:**
```json
{
    "debug": true
}
```

## How It Works

### Simple Player Selection
1. **Choose in GUI**: Select your preferred player from the dropdown (VLC, MPV, MPC-HC, or Auto)
2. **Start Stream**: The selected player will be used directly
3. **Fallback**: If the selected player isn't found, the app will try to locate it automatically

### Manual Override
If you have a custom installation, specify the exact path in settings.json:
```json
{
    "player_path": "C:\\Custom\\Path\\To\\vlc.exe"
}
```

## Troubleshooting

### Debug Mode
Enable debug mode to see which player is being used:
```json
{
    "debug": true
}
```

Debug output will show:
```
DEBUG: Starting simplified player detection...
DEBUG: Player choice: vlc
DEBUG: Found vlc in PATH: C:\Program Files\VideoLAN\VLC\vlc.exe
```

### Common Issues

| Problem | Solution |
|---------|----------|
| Selected player not working | Check if player is installed and in PATH |
| "Auto" not finding players | Install VLC or MPV from official sources |
| Custom player path not working | Verify the path exists and is executable |

### Manual Player Specification
For reliable operation, specify the exact player path:
```json
{
    "player_path": "C:\\Program Files\\VideoLAN\\VLC\\vlc.exe",
    "player": "vlc"
}
```

## Supported Players

| Player | Executable | Auto-Detection | Notes |
|--------|------------|----------------|-------|
| VLC | vlc.exe | ✓ | Recommended, best compatibility |
| MPV | mpv.exe, mpv.com | ✓ | Lightweight, good performance |
| MPC-HC | mpc-hc.exe, mpc-hc64.exe | ✓ | Windows-specific |
| PotPlayer | PotPlayerMini64.exe | ✓ | Feature-rich |
| Windows Media Player | wmplayer.exe | ✓ | Built into Windows |

## Installation Recommendations

1. **VLC** (Recommended): Download from https://www.videolan.org/
2. **MPV**: Install via `choco install mpv` or `winget install mpv.mpv`
3. **MPC-HC**: Download from https://github.com/clsid2/mpc-hc/releases

## Environment Variables

The application recognizes these environment variables:
- `TWITCH_PLAYER_PATH`: Full path to player executable
- `TWITCH_PLAYER_NAME`: Name of the player
- `VIRTUAL_ENV`: Python virtual environment path

## Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| "No supported video player found" | No players detected | Install VLC or MPV |
| "streamlink command not found" | Streamlink not installed | `pip install streamlink` |
| "Failed to initialize player" | Player path invalid | Check player_path in settings |

## Command Examples

```bash
# Basic usage
python watch_stream.py channelname

# PowerShell script (recommended)
.\run.ps1 channelname

# With custom quality
# (Set in settings.json: "preferred_quality": "720p")
```