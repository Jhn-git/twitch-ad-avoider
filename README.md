# TwitchAdAvoider

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Build Status](https://img.shields.io/badge/build-passing-brightgreen.svg)](#testing)

A Python implementation for watching Twitch streams while avoiding ads, featuring a modern Qt GUI and command-line interface with comprehensive security validation.

---

## Features

### Stream Viewing
- **Ad Avoidance**: Watch Twitch streams through external players (VLC, MPV, MPC-HC) via streamlink
- **Quality Selection**: Choose stream quality (best, worst, 720p, 480p, 360p, 160p)
- **Player Auto-Detection**: Automatically finds installed video players
- **Favorites Management**: Save channels with live status monitoring

### User Interfaces
- **Modern Qt GUI**: Professional PySide6 tabbed interface with Stream and Settings tabs
- **Command-Line Interface**: Full CLI support for headless operation and scripting
- **Real-time Validation**: Immediate feedback on input validity with visual indicators
- **Theming Support**: Light and dark themes with custom QSS stylesheets

### Chat & Integration
- **Twitch Chat Integration**: Real-time IRC chat with OAuth authentication
- **Message Sending**: Send messages directly to Twitch chat from the application
- **Live Status Monitoring**: Track when favorite streamers go live

### Security & Configuration
- **Security Validation**: Comprehensive input validation and sanitization (see CLAUDE.md Security section)
- **Flexible Configuration**: JSON-based configuration with essential settings
- **Attack Prevention**: Protection against path traversal, command injection, and other attacks

---

## Quick Start

### Installation

**Prerequisites**: Python 3.8+, a video player (VLC recommended)

```bash
# Clone repository
git clone <your-repo-url>
cd twitch-viewer

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -e .
```

### Basic Usage

**GUI Mode** (Recommended):
```bash
python main.py
```

**Command Line Mode**:
```bash
# Watch a channel
python main.py --channel ninja

# Watch with specific quality
python main.py --channel shroud --quality 720p

# Enable debug mode
python main.py --channel pokimane --debug
```

---

## Documentation

**README.md** - This file: Features, installation, usage, troubleshooting
**CLAUDE.md** - Developer guide: Architecture, security, development commands, code style

---

## Configuration

TwitchAdAvoider uses `config/settings.json` for configuration. Created automatically with defaults on first run.

### Essential Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `preferred_quality` | String | `"best"` | Stream quality (best, 720p, 480p, 360p, 160p) |
| `player` | String | `"vlc"` | Player choice (vlc, mpv, mpc-hc, auto) |
| `player_path` | String/null | `null` | Custom player path (absolute path required) |
| `player_args` | String | `"--network-caching=10000..."` | Player arguments (see note below) |
| `cache_duration` | Integer | `30` | Stream buffer cache (0-3600 seconds) |
| `debug` | Boolean | `false` | Enable debug logging |
| `log_to_file` | Boolean | `false` | Write logs to file |
| `log_level` | String | `"INFO"` | Log level (DEBUG, INFO, WARNING, ERROR) |

**Note on player_args**: The default buffering arguments (10 second cache) help VLC handle stream discontinuities caused by Twitch ads, preventing visual corruption when ads are inserted.

### Configuration Examples

**Minimal Configuration**:
```json
{
    "preferred_quality": "best",
    "player": "auto"
}
```

**High-Quality Setup**:
```json
{
    "preferred_quality": "best",
    "player": "vlc",
    "player_path": "C:\\Program Files\\VideoLAN\\VLC\\vlc.exe",
    "player_args": "--network-caching=10000 --file-caching=10000 --live-caching=10000 --fullscreen",
    "cache_duration": 60
}
```

**Debug Configuration**:
```json
{
    "preferred_quality": "480p",
    "debug": true,
    "log_to_file": true,
    "log_level": "DEBUG"
}
```

### Player Path Security

**✓ Use absolute paths**:
- Windows: `C:\Program Files\VideoLAN\VLC\vlc.exe`
- macOS: `/Applications/VLC.app/Contents/MacOS/VLC`
- Linux: `/usr/bin/vlc`

**✗ Avoid relative paths** (security risk)

**Configuration via GUI**: Launch application → Settings tab → Modify → Apply Settings

---

## Architecture

TwitchAdAvoider follows a modular architecture with clear separation between GUI, core logic, and security layers.

### Component Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Qt GUI Layer    │    │   CLI Interface  │    │  Configuration  │
│ • Stream Tab    │    │ • Arg Parsing    │    │ • Validation    │
│ • Settings Tab  │    │ • Direct Launch  │    │ • Persistence   │
└────────┬────────┘    └────────┬─────────┘    └────────┬────────┘
         │                      │                       │
         └──────────────────────┼───────────────────────┘
                                │
                   ┌────────────▼────────────┐
                   │     Core Engine         │
                   │ • Stream Management     │
                   │ • Player Detection      │
                   │ • OAuth/Chat Client     │
                   └────────────┬────────────┘
                                │
                   ┌────────────▼────────────┐
                   │   Security Layer        │
                   │ • Input Validation      │
                   │ • Attack Prevention     │
                   │ • Sanitization          │
                   └─────────────────────────┘
```

### Key Components

| Component | Responsibility | File Location |
|-----------|---------------|---------------|
| **TwitchViewer** | Stream management, player detection | `src/twitch_viewer.py` |
| **StreamGUI** | Qt interface orchestration | `gui_qt/stream_gui.py` |
| **ConfigManager** | Settings validation & persistence | `src/config_manager.py` |
| **Validators** | Security input validation | `src/validators.py` |

**For detailed architecture**, see **[CLAUDE.md](CLAUDE.md)**.

---

## Security

TwitchAdAvoider implements defense-in-depth security with comprehensive input validation.

**Protected Against**:
- ✅ Path traversal attacks (`../`, `..\\`)
- ✅ Command injection (`;`, `|`, `&`, `$()`)
- ✅ Invalid channel names (pattern validation)
- ✅ Malicious player arguments
- ✅ Control character injection
- ✅ Configuration tampering

**Security Features**:
- Real-time input validation with GUI feedback
- Pattern-based attack detection
- Validated configuration persistence
- Secure OAuth token encryption

**For complete security documentation**, see **CLAUDE.md Security section**.

---

## Troubleshooting

### Enable Debug Mode First

**Via CLI**:
```bash
python main.py --debug
```

**Via GUI**: Settings tab → Enable "Debug Mode" + "Log to File" → Apply Settings → Check `logs/twitch_ad_avoider.log`

**Via Config**: Edit `config/settings.json`:
```json
{
    "debug": true,
    "log_to_file": true,
    "log_level": "DEBUG"
}
```

### Top Issues

**1. "Video player not found"**
- **Install a player**: Download VLC from https://www.videolan.org/vlc/
- **Manual config** (GUI): Settings → Custom Player Path → Set to exact path → Apply
  - Windows: `C:\Program Files\VideoLAN\VLC\vlc.exe`
  - macOS: `/Applications/VLC.app/Contents/MacOS/VLC`
  - Linux: `/usr/bin/vlc`

**2. "streamlink command not found"**
```bash
# Activate virtual environment first
source .venv/bin/activate  # macOS/Linux
.venv\Scripts\Activate.ps1  # Windows

# Reinstall dependencies
pip install -e .
```

**3. GUI won't launch**
```bash
# Reinstall PySide6
pip install --upgrade --force-reinstall PySide6

# Linux: Install Qt dependencies
sudo apt install libxcb-xinerama0 libxcb-cursor0
```

**4. WSL2 Qt/Wayland Error** (`undefined symbol: wl_proxy_marshal_flags`)
- **Issue**: Qt detects Wayland on WSL2 but Wayland support is incomplete
- **Quick fix**: Set environment variable before running:
  ```bash
  export QT_QPA_PLATFORM=xcb
  python main.py
  ```
- **Permanent fix**: Add to `~/.bashrc` or `~/.zshrc`:
  ```bash
  export QT_QPA_PLATFORM=xcb  # Force Qt to use X11 instead of Wayland
  ```
- **Alternative**: Use `make run` which sets this automatically

**5. Stream buffering / constant pausing**
- **Lower quality**: Try 720p → 480p → 360p
- **Adjust cache**: Settings → Stream Settings → Cache Duration: 15 → Apply
- **Check bandwidth**: 3+ Mbps for 480p, 5+ Mbps for 720p, 10+ Mbps for 1080p

**6. Connection timeouts**
- **Increase timeouts**: Settings → Network Settings → Network Timeout: 60 → Apply
- **Via config**:
```json
{
    "network_timeout": 60,
    "retry_attempts": 5,
    "retry_delay": 10
}
```

### Verify Installation

```bash
# Check Python version (need 3.8+)
python --version

# Check virtual environment is activated
which python  # macOS/Linux (should include ".venv")
where python  # Windows (should include ".venv")

# Check streamlink
streamlink --version

# Test application
python main.py --help
```

---

## Contributing

This is a personal project for solo use. Development documentation is in **CLAUDE.md**.

**Quick Development Setup**:
```bash
# Install with dev dependencies
pip install -e .[dev]

# Run tests
make test

# Code quality checks
make check
```

**See CLAUDE.md** for architecture, code style, security guidelines, and development patterns.

---

## Testing

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_validators.py

# Run with coverage
coverage run -m pytest tests/
coverage report

# Code quality checks
black --check .
flake8 .
mypy src/
```

---

## License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## Acknowledgments

- **[Streamlink](https://streamlink.github.io/)** - Core streaming functionality
- **[PySide6](https://doc.qt.io/qtforpython/)** - Modern Qt GUI framework
- **Python Community** - Excellent libraries and tools
- **Contributors** - Thank you to everyone who has contributed to this project

---

**Last Updated**: 2025-11-27
