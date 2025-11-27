# TwitchAdAvoider

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Documentation Status](https://img.shields.io/badge/docs-sphinx-brightgreen.svg)](docs/)
[![Build Status](https://img.shields.io/badge/build-passing-brightgreen.svg)](#testing)

A Python implementation for watching Twitch streams while avoiding ads, featuring a modern Qt GUI and command-line interface with comprehensive security validation.

📖 **[Complete Documentation Map](DOCS-MAP.md)** | 🚀 **[Quick Start Guide](QUICKSTART.md)** | 🔧 **[Installation Guide](INSTALLATION.md)**

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
- **Security Validation**: Comprehensive input validation and sanitization ([Details](SECURITY.md))
- **Flexible Configuration**: JSON-based configuration with 16+ settings ([Reference](CONFIG-REFERENCE.md))
- **Attack Prevention**: Protection against path traversal, command injection, and other attacks

---

## Quick Start

### Installation

**Prerequisites**: Python 3.8+, a video player (VLC recommended)

```bash
# Clone repository
git clone https://github.com/yourusername/twitch-viewer.git
cd twitch-viewer

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\Activate.ps1
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -e .
```

**📖 For detailed installation instructions**, see **[INSTALLATION.md](INSTALLATION.md)**.

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

**🚀 For complete usage guide**, see **[QUICKSTART.md](QUICKSTART.md)**.

---

## Documentation

### For Users

| Document | Description |
|----------|-------------|
| **[INSTALLATION.md](INSTALLATION.md)** | Complete installation guide for all platforms |
| **[QUICKSTART.md](QUICKSTART.md)** | Getting started with GUI and CLI |
| **[CONFIG-REFERENCE.md](CONFIG-REFERENCE.md)** | Complete configuration options reference (16+ settings) |
| **[PLAYER-CONFIG.md](PLAYER-CONFIG.md)** | Player setup and optimization guide |
| **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** | Solutions for common problems |
| **[SECURITY.md](SECURITY.md)** | Security features and best practices |

### For Developers

| Document | Description |
|----------|-------------|
| **[CONTRIBUTING.md](CONTRIBUTING.md)** | Contribution guidelines and development workflow |
| **[CLAUDE.md](CLAUDE.md)** | Architecture reference and development commands |
| **[PACKAGING.md](PACKAGING.md)** | Building Windows executables with PyInstaller |

### Navigation

**[📖 DOCS-MAP.md](DOCS-MAP.md)** - Complete documentation navigation guide with user and developer journeys

---

## Configuration

TwitchAdAvoider uses `config/settings.json` for configuration. The file is automatically created with defaults on first run.

**Quick Configuration Examples**:

```json
{
    "preferred_quality": "best",
    "player": "auto",
    "cache_duration": 30,
    "current_theme": "dark",
    "debug": false
}
```

**Common Settings**:
- `preferred_quality` - Default stream quality (`best`, `720p`, `480p`, etc.)
- `player` - Player choice (`auto`, `vlc`, `mpv`, `mpc-hc`)
- `player_path` - Custom player path (leave `null` for auto-detection)
- `current_theme` - UI theme (`light` or `dark`)
- `debug` - Enable debug logging

**For all 16+ configuration options**, see **[CONFIG-REFERENCE.md](CONFIG-REFERENCE.md)**.

**To configure via GUI**: Launch application → Settings tab → Modify → Apply Settings

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
| **AuthManager** | OAuth authentication | `src/auth_manager.py` |
| **TwitchChatClient** | IRC chat integration | `src/twitch_chat_client.py` |

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

**For complete security documentation**, see **[SECURITY.md](SECURITY.md)**.

---

## Troubleshooting

### Common Issues

**"Video player not found"**
- Install VLC, MPV, or MPC-HC ([Installation Guide](INSTALLATION.md#installing-a-video-player))
- Set custom player path in Settings tab or `config/settings.json`

**"streamlink command not found"**
```bash
pip install -e .
```

**GUI won't launch**
```bash
pip install --upgrade --force-reinstall PySide6
```

**Stream buffering/lagging**
- Lower quality: Try `720p`, `480p`, or `360p`
- Settings tab → Preferred Quality → Apply

**For detailed troubleshooting**, see **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** and **[RESOLVED-ISSUES.md](RESOLVED-ISSUES.md)**.

---

## Contributing

Contributions are welcome! TwitchAdAvoider follows modern Python best practices and comprehensive testing standards.

**Quick Start for Contributors**:
1. Fork the repository
2. Install with dev dependencies: `pip install -e .[dev]`
3. Run tests: `pytest tests/`
4. Follow code style: `black . && flake8 . && mypy src/`
5. Submit PR with tests

**Development Tools**:
- **pytest** - Testing framework
- **black** - Code formatter (configured in `pyproject.toml`)
- **flake8** - Linter
- **mypy** - Type checker
- **coverage** - Code coverage analysis

**For complete contributing guide**, see **[CONTRIBUTING.md](CONTRIBUTING.md)**.

**Security Guidelines**: All user inputs must be validated using `src/validators.py`. See **[SECURITY.md](SECURITY.md)** for security requirements.

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

## Getting Help

- **📖 Documentation**: Start with [DOCS-MAP.md](DOCS-MAP.md) for navigation
- **🐛 Issues**: [GitHub Issues](https://github.com/yourusername/twitch-viewer/issues)
- **💬 Discussions**: [GitHub Discussions](https://github.com/yourusername/twitch-viewer/discussions)
- **🔒 Security**: See [SECURITY.md](SECURITY.md) for vulnerability reporting

---

**Last Updated**: 2025-11-27 | **Documentation**: [DOCS-MAP.md](DOCS-MAP.md)
