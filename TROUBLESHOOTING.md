<!-- Last Updated: 2025-11-27 | Target Audience: Users experiencing issues -->

# Troubleshooting Guide

Solutions for common problems with TwitchAdAvoider. For historical resolved issues, see **[RESOLVED-ISSUES.md](RESOLVED-ISSUES.md)**.

---

## Table of Contents

- [Before You Start](#before-you-start)
- [Installation Issues](#installation-issues)
- [GUI Issues](#gui-issues)
- [Player Issues](#player-issues)
- [Stream Issues](#stream-issues)
- [Authentication Issues](#authentication-issues)
- [Chat Issues](#chat-issues)
- [Network Issues](#network-issues)
- [Performance Issues](#performance-issues)
- [Getting More Help](#getting-more-help)

---

## Before You Start

### Enable Debug Mode

Debug mode provides detailed logging that helps identify problems:

**Via CLI**:
```bash
python main.py --debug
```

**Via GUI**:
1. Open Settings tab
2. Enable "Debug Mode"
3. Enable "Log to File"
4. Click "Apply Settings"
5. Check logs at `logs/twitch_ad_avoider.log`

**Via Configuration**:
Edit `config/settings.json`:
```json
{
    "debug": true,
    "log_to_file": true,
    "log_level": "DEBUG"
}
```

### Verify Installation

```bash
# Check Python version
python --version
# Expected: Python 3.8.0 or higher

# Check virtual environment is activated
which python  # macOS/Linux
where python  # Windows
# Expected: Path should include "venv"

# Check streamlink
streamlink --version
# Expected: streamlink 5.x.x

# Check application
python main.py --help
# Expected: Usage help message
```

---

## Installation Issues

### "python: command not found"

**Cause**: Python not installed or not in PATH

**Solutions**:
- **Windows**: Use `py` instead of `python`, or reinstall Python with "Add to PATH" checked
- **macOS**: Use `python3` instead of `python`
- **Linux**: Install Python: `sudo apt install python3.11 python3.11-venv python3-pip`

### "No module named 'streamlink'"

**Cause**: Dependencies not installed or virtual environment not activated

**Solutions**:
```bash
# 1. Activate virtual environment
# Windows:
venv\Scripts\Activate.ps1
# macOS/Linux:
source venv/bin/activate

# 2. Reinstall dependencies
pip install -e .

# 3. Verify installation
pip list | grep streamlink
```

### "pip: command not found"

**Cause**: pip not installed

**Solutions**:
```bash
# Use Python module invocation
python -m pip install -e .

# Or install pip
# Windows:
py -m ensurepip --upgrade

# macOS/Linux:
sudo apt install python3-pip
```

### Virtual Environment Won't Activate (Windows)

**Cause**: PowerShell execution policy restriction

**Solutions**:
```powershell
# Option 1: Change execution policy for current user
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Option 2: Bypass for single command
PowerShell -ExecutionPolicy Bypass -File venv\Scripts\Activate.ps1

# Option 3: Use Command Prompt instead
venv\Scripts\activate.bat
```

### Permission Errors During Installation

**Cause**: Incorrect use of sudo or permissions

**Solutions**:
```bash
# NEVER use sudo with pip in virtual environment

# 1. Ensure virtual environment is activated
source venv/bin/activate  # macOS/Linux
venv\Scripts\Activate.ps1  # Windows

# 2. Install without sudo
pip install -e .

# If still having issues, recreate venv
rm -rf venv  # macOS/Linux
Remove-Item -Recurse -Force venv  # Windows
python -m venv venv
```

---

## GUI Issues

### GUI Won't Launch / No Window Appears

**Cause**: PySide6 installation or platform plugin issues

**Solutions**:

**1. Reinstall PySide6**:
```bash
pip install --upgrade --force-reinstall PySide6
```

**2. Verify Qt Works**:
```bash
python -c "from PySide6.QtWidgets import QApplication; import sys; app = QApplication(sys.argv); print('Qt OK')"
```

**3. Linux: Install Additional Packages**:
```bash
# Ubuntu/Debian
sudo apt install libxcb-xinerama0 libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0

# Fedora
sudo dnf install xcb-util-image xcb-util-keysyms xcb-util-renderutil xcb-util-wm
```

**4. Windows: Install Visual C++ Redistributable**:
- Download from [microsoft.com](https://aka.ms/vs/17/release/vc_redist.x64.exe)
- Install and restart

**5. macOS: Install Qt via Homebrew**:
```bash
brew install qt@6
```

### GUI Opens But Is Blank/Corrupted

**Cause**: Graphics driver or theme issues

**Solutions**:

**1. Reset Theme**:
Edit `config/settings.json`:
```json
{
    "current_theme": "light"
}
```

**2. Update Graphics Drivers**:
- **Windows**: Update via Device Manager or manufacturer website
- **Linux**: Update Mesa drivers: `sudo apt upgrade`
- **macOS**: Update macOS to latest version

**3. Disable Hardware Acceleration** (if available in future versions):
Set environment variable:
```bash
# Windows
set QT_OPENGL=software

# macOS/Linux
export QT_OPENGL=software
```

### GUI Freezes When Clicking Buttons

**Cause**: Long-running operations blocking UI thread

**Solutions**:

**1. Check Debug Logs**: Look for errors in console or log file

**2. Update Application**: Ensure you're on the latest version

**3. Restart Application**: Close completely and relaunch

**4. Clear Configuration**:
```bash
# Backup current config
cp config/settings.json config/settings.json.backup

# Delete config to reset
rm config/settings.json  # macOS/Linux
del config\settings.json  # Windows

# Restart application (will create defaults)
python main.py
```

---

## Player Issues

### "Video player not found" Error

**Cause**: No compatible player installed or player not in PATH

**Solutions**:

**1. Install a Player**:
```bash
# Windows - VLC
# Download from https://www.videolan.org/vlc/

# macOS - VLC
brew install --cask vlc

# Linux - VLC
sudo apt install vlc  # Ubuntu/Debian
sudo dnf install vlc  # Fedora
```

**2. Verify Player Installation**:
```bash
# Check if player is in PATH
vlc --version
mpv --version
```

**3. Manual Player Configuration**:

**Via GUI**:
1. Open Settings tab
2. Set "Custom Player Path" to exact executable path
3. Examples:
   - Windows VLC: `C:\Program Files\VideoLAN\VLC\vlc.exe`
   - macOS VLC: `/Applications/VLC.app/Contents/MacOS/VLC`
   - Linux VLC: `/usr/bin/vlc`
4. Click "Apply Settings"

**Via Config File**:
Edit `config/settings.json`:
```json
{
    "player": "vlc",
    "player_path": "C:\\Program Files\\VideoLAN\\VLC\\vlc.exe"
}
```

**4. See [PLAYER-CONFIG.md](PLAYER-CONFIG.md)** for complete player setup guide.

### Player Opens But Stream Doesn't Play

**Cause**: Streamlink or player configuration issues

**Solutions**:

**1. Test Streamlink Directly**:
```bash
streamlink twitch.tv/ninja best
```

**2. Update Streamlink**:
```bash
pip install --upgrade streamlink
```

**3. Try Different Player**:
Change player in Settings tab or config:
```json
{
    "player": "mpv"
}
```

**4. Check Player Arguments**:
Remove custom player arguments temporarily:
```json
{
    "player_args": null
}
```

### Player Opens Multiple Times

**Cause**: Clicking "Watch Stream" multiple times or previous instances not closing

**Solutions**:

**1. Wait for First Instance**: Give player 5-10 seconds to open

**2. Check Running Processes**:
```bash
# Windows
tasklist | findstr vlc

# macOS/Linux
ps aux | grep vlc
```

**3. Kill Existing Processes**:
```bash
# Windows
taskkill /IM vlc.exe /F

# macOS/Linux
killall vlc
```

---

## Stream Issues

### "Channel not found" or "No streams available"

**Cause**: Channel offline, incorrect name, or Twitch API issues

**Solutions**:

**1. Verify Channel Name**:
- Check spelling (case-insensitive)
- Use exact Twitch username
- 4-25 characters, letters/numbers/underscores only

**2. Check if Channel is Live**:
- Visit `https://twitch.tv/channelname` in browser
- Look for live indicator

**3. Test with Known Live Channel**:
```bash
python main.py --channel ninja
```

**4. Check Internet Connection**:
```bash
# Test Twitch connectivity
ping twitch.tv

# Test DNS resolution
nslookup twitch.tv
```

### Stream Buffering / Constant Pausing

**Cause**: Insufficient bandwidth or high stream quality

**Solutions**:

**1. Lower Stream Quality**:
```bash
# Try progressively lower qualities
python main.py --channel ninja --quality 720p
python main.py --channel ninja --quality 480p
python main.py --channel ninja --quality 360p
```

**Via GUI**: Select lower quality from dropdown before watching

**2. Adjust Cache Duration**:
Edit `config/settings.json`:
```json
{
    "cache_duration": 15
}
```

**3. Close Bandwidth-Heavy Applications**: Stop downloads, streaming, etc.

**4. Check Internet Speed**:
- Minimum: 3 Mbps for 480p
- Recommended: 5+ Mbps for 720p, 10+ Mbps for 1080p

### Stream Quality Lower Than Expected

**Cause**: Streamer not broadcasting at requested quality

**Solutions**:

**1. Use "best" Quality**:
```bash
python main.py --channel ninja --quality best
```

**2. Check Available Qualities**:
```bash
streamlink twitch.tv/channelname
# Lists all available stream qualities
```

**3. Verify Streamer Settings**: Some streamers don't enable transcoding (quality options)

---

## Authentication Issues

### OAuth Authentication Fails

**Cause**: Incorrect redirect URI or missing client credentials

**Solutions**:

**1. Verify Twitch App Settings**:
- Go to [dev.twitch.tv/console](https://dev.twitch.tv/console)
- Select your app
- Ensure **OAuth Redirect URLs** is set to **exactly**:
  ```
  http://localhost:8080/auth/callback
  ```
- NOT `http://localhost:8080`

**2. Update Client Credentials**:
Edit `config/settings.json`:
```json
{
    "twitch_client_id": "your_client_id_here",
    "twitch_client_secret": "your_client_secret_here"
}
```

**3. Get Client Secret**:
- In Twitch Developer Console
- Click "New Secret" if none exists
- Copy and save immediately (shown only once)

**4. Restart Application**: After updating credentials

**See [INSTALLATION.md](INSTALLATION.md#post-installation-setup)** for complete OAuth setup.

### "redirect_mismatch" Error

**Cause**: Redirect URI mismatch between app and Twitch settings

**Solution**: Update Twitch app redirect URI to `http://localhost:8080/auth/callback`

**See [RESOLVED-ISSUES.md](RESOLVED-ISSUES.md#issue-2-oauth-authentication-issues)** for detailed solution.

### "Token exchange failed: 400"

**Cause**: Missing or incorrect client_secret

**Solution**: Add client_secret to `config/settings.json`

**See [RESOLVED-ISSUES.md](RESOLVED-ISSUES.md#problem-2b-token-exchange-failed-400-error)** for detailed solution.

---

## Chat Issues

### Chat Doesn't Connect

**Cause**: OAuth not configured or authentication failed

**Solutions**:

**1. Complete OAuth Setup**: See [Authentication Issues](#authentication-issues)

**2. Enable Chat Auto-Connect**:
Settings tab → Chat Settings → "Auto-connect Chat" → Apply

**3. Check Debug Logs**: Look for IRC connection errors

### Messages Don't Send

**Cause**: Not authenticated or IRC connection issues

**Solutions**:

**1. Verify Authentication**: Look for "Authenticated" indicator in GUI

**2. Check IRC Connection**: Debug logs should show successful IRC connection

**3. Restart Chat Connection**: Disconnect and reconnect

**See [RESOLVED-ISSUES.md](RESOLVED-ISSUES.md#issue-3-chat-message-sending-issues)** for historical message sending issues.

### Chat Messages Not Appearing Locally

**Cause**: Historical issue (now resolved)

**Solution**: Update to latest version. See [RESOLVED-ISSUES.md](RESOLVED-ISSUES.md#issue-3-chat-message-sending-issues) for details.

---

## Network Issues

### Connection Timeouts

**Cause**: Slow or unstable internet connection

**Solutions**:

**1. Increase Timeout Values**:
Settings tab → Network Settings:
- Network Timeout: 60 seconds
- Retry Attempts: 5
- Retry Delay: 10 seconds
- Click "Apply Settings"

**Via Config**:
```json
{
    "network_timeout": 60,
    "retry_attempts": 5,
    "retry_delay": 10
}
```

**2. Test Network Stability**:
```bash
# Test Twitch connectivity with multiple pings
ping -c 10 twitch.tv  # macOS/Linux
ping -n 10 twitch.tv  # Windows
```

### "Unable to connect to Twitch"

**Cause**: Network connectivity or firewall issues

**Solutions**:

**1. Check Internet Connection**: Test other websites

**2. Disable VPN Temporarily**: Some VPNs block Twitch

**3. Check Firewall Settings**:
- Allow Python through firewall
- Allow streamlink through firewall

**4. Try Different DNS**:
```bash
# Use Google DNS: 8.8.8.8, 8.8.4.4
# Use Cloudflare DNS: 1.1.1.1, 1.0.0.1
```

---

## Performance Issues

### High CPU Usage

**Cause**: Player settings or stream quality

**Solutions**:

**1. Lower Stream Quality**: Use 720p or 480p instead of best/1080p

**2. Optimize Player Settings**:
See [PLAYER-CONFIG.md](PLAYER-CONFIG.md) for player-specific optimizations

**3. Close Other Applications**: Free up system resources

### High Memory Usage

**Cause**: Chat message accumulation or player cache

**Solutions**:

**1. Limit Chat Messages**:
Settings tab → Chat Settings → Maximum Messages: 500 → Apply

**2. Reduce Cache Duration**:
Settings tab → Stream Settings → Cache Duration: 15 → Apply

**3. Restart Application Periodically**: If running for extended periods

---

## Getting More Help

### Before Asking for Help

1. **Check Debug Logs**: Enable debug mode and review `logs/twitch_ad_avoider.log`
2. **Search Existing Issues**: [GitHub Issues](https://github.com/yourusername/twitch-viewer/issues)
3. **Check Resolved Issues**: [RESOLVED-ISSUES.md](RESOLVED-ISSUES.md)
4. **Verify Installation**: Run verification commands in [Before You Start](#before-you-start)

### Creating a Bug Report

When creating a GitHub issue, include:

**System Information**:
```bash
# Operating System and version
uname -a  # macOS/Linux
systeminfo  # Windows

# Python version
python --version

# Streamlink version
streamlink --version

# Application version
git log -1 --oneline
```

**Error Information**:
- Complete error message
- Debug log excerpt (enable debug mode first)
- Steps to reproduce
- Expected vs actual behavior

**Configuration**:
- Relevant settings from `config/settings.json`
- Player being used
- Stream quality attempted

### Additional Resources

- **[CONFIG-REFERENCE.md](CONFIG-REFERENCE.md)** - Configuration options
- **[PLAYER-CONFIG.md](PLAYER-CONFIG.md)** - Player setup
- **[SECURITY.md](SECURITY.md)** - Security features

---

**Last Updated**: 2025-11-27
**For Resolved Issues**: See [RESOLVED-ISSUES.md](RESOLVED-ISSUES.md)
**For New Issues**: [GitHub Issues](https://github.com/yourusername/twitch-viewer/issues)
