# Player Configuration Guide

This document explains the enhanced player detection and configuration options available in TwitchAdAvoider.

## Automatic Player Detection

The application uses a multi-stage approach to find video players:

### Stage 1: Environment Variables (PowerShell Integration)
- PowerShell script exports `TWITCH_PLAYER_NAME` and `TWITCH_PLAYER_PATH`
- Python automatically uses the player found by PowerShell
- Most reliable method for Windows

### Stage 2: Manual Configuration (settings.json)
```json
{
    "player_path": "C:\\Program Files\\VideoLAN\\VLC\\vlc.exe",
    "player": "vlc"
}
```

### Stage 3: PATH Detection
- Uses `shutil.which()` to find players in system PATH
- Checks for: vlc, mpv, mpc-hc, potplayer, wmplayer

### Stage 4: Common Installation Paths
Automatically checks these locations:
- VLC: `C:\Program Files\VideoLAN\VLC\vlc.exe`
- MPV: `C:\ProgramData\chocolatey\lib\mpvio.install\tools\mpv.exe`
- MPC-HC: `C:\Program Files\MPC-HC\mpc-hc64.exe`
- PotPlayer: `C:\Program Files\DAUM\PotPlayer\PotPlayerMini64.exe`
- Windows Media Player: `C:\Program Files\Windows Media Player\wmplayer.exe`

### Stage 5: Streamlink Auto-Detection
- Lets streamlink handle player detection
- Falls back to streamlink's default behavior

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

## Troubleshooting

### Debug Mode
Set `"debug": true` in settings.json to see detailed player detection logs:
```
DEBUG: Starting player detection...
DEBUG: Found exported player: VLC at C:\Program Files\VideoLAN\VLC\vlc.exe
```

### Diagnostic Script
Run the comprehensive diagnostic script:
```powershell
.\diagnose-environment.ps1
```

This will show:
- All available players
- PATH configuration
- Environment variables
- Python vs PowerShell detection differences

### Manual Player Specification
If auto-detection fails, manually specify the player:
```json
{
    "player_path": "C:\\Program Files\\VideoLAN\\VLC\\vlc.exe",
    "player": "vlc"
}
```

### PowerShell Script Options
```powershell
# Skip player detection entirely
.\run.ps1 ChannelName -SkipPlayerCheck

# Normal usage
.\run.ps1 ChannelName
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