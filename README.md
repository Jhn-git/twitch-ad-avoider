# TwitchAdAvoider

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Documentation Status](https://img.shields.io/badge/docs-sphinx-brightgreen.svg)](docs/)
[![Build Status](https://img.shields.io/badge/build-passing-brightgreen.svg)](#testing)

A Python implementation for watching Twitch streams while avoiding ads, featuring both GUI and command-line interfaces with comprehensive security validation.

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
  - [GUI Mode](#gui-mode)
  - [Command Line Mode](#command-line-mode)
- [Configuration](#configuration)
- [Security Features](#security-features)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

## Features

- **Stream Viewing**: Watch Twitch streams through external players (VLC, MPV, MPC-HC)
- **Ad Avoidance**: Utilizes streamlink to bypass advertisements
- **Dual Interface**: Both graphical and command-line interfaces available
- **Player Auto-Detection**: Automatically detects installed video players
- **Favorites Management**: Save and manage your favorite channels
- **Quality Selection**: Choose stream quality (best, worst, 720p, 480p, 360p, 160p)
- **Security Validation**: Comprehensive input validation and sanitization
- **Real-time Validation**: GUI provides immediate feedback on input validity
- **Flexible Configuration**: JSON-based configuration with validation

## Prerequisites

- **Python 3.7+** (recommended: Python 3.8 or higher)
- **Streamlink** (automatically installed via requirements)
- **Video Player**: At least one of the following:
  - **VLC Media Player** (recommended)
  - **MPV**
  - **MPC-HC** (Windows only)

### Installing Video Players

#### Windows
- **VLC**: Download from [videolan.org](https://www.videolan.org/vlc/)
- **MPV**: `choco install mpv` (via Chocolatey) or download from [mpv.io](https://mpv.io/)
- **MPC-HC**: Download from [mpc-hc.org](https://mpc-hc.org/)

#### macOS
- **VLC**: `brew install --cask vlc` or download from [videolan.org](https://www.videolan.org/vlc/)
- **MPV**: `brew install mpv`

#### Linux
- **VLC**: `sudo apt install vlc` (Ubuntu/Debian) or `sudo dnf install vlc` (Fedora)
- **MPV**: `sudo apt install mpv` (Ubuntu/Debian) or `sudo dnf install mpv` (Fedora)

## Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/twitch-viewer.git
   cd twitch-viewer
   ```

2. **Create virtual environment** (recommended):
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -e .
   ```

4. **Verify installation**:
   ```bash
   python main.py --help
   ```

## Usage

### GUI Mode

Launch the graphical interface for easy stream management:

```bash
python main.py
```

**GUI Features**:
- Real-time channel name validation with visual feedback
- Dropdown quality selection
- Favorites management with add/remove functionality
- Player detection status display
- One-click stream launching

### Command Line Mode

Watch a specific channel directly:

```bash
python main.py --channel CHANNEL_NAME [OPTIONS]
```

**Examples**:
```bash
# Watch a channel with default settings
python main.py --channel ninja

# Watch with specific quality
python main.py --channel shroud --quality 720p

# Enable debug mode
python main.py --channel pokimane --debug
```

**Available Options**:
- `--channel, -c`: Channel name to watch
- `--quality, -q`: Stream quality (default: best)
- `--debug`: Enable debug logging
- `--help`: Show help message

### Running as Module

You can also run TwitchAdAvoider as a Python module:

```bash
python -m twitch_ad_avoider --channel ninja
```

## Configuration

TwitchAdAvoider uses a JSON configuration file located at `config/settings.json`. The configuration is automatically created with default values on first run.

### Default Configuration

```json
{
    "preferred_quality": "best",
    "player": "vlc",
    "cache_duration": 30,
    "debug": false,
    "log_to_file": false,
    "log_level": "INFO",
    "player_path": null,
    "player_args": null,
    "enable_status_monitoring": true,
    "status_check_interval": 300,
    "status_cache_duration": 60
}
```

### Configuration Options

| Setting | Type | Description | Valid Values |
|---------|------|-------------|--------------|
| `preferred_quality` | String | Default stream quality | `best`, `worst`, `720p`, `480p`, `360p`, `160p` |
| `player` | String | Video player choice | `vlc`, `mpv`, `mpc-hc`, `auto` |
| `cache_duration` | Integer | Stream cache duration (seconds) | 0-3600 |
| `debug` | Boolean | Enable debug logging | `true`, `false` |
| `log_to_file` | Boolean | Write logs to file | `true`, `false` |
| `log_level` | String | Logging verbosity | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `player_path` | String/null | Custom player executable path | Valid file path or `null` |
| `player_args` | String/null | Additional player arguments | Validated string or `null` |
| `enable_status_monitoring` | Boolean | Enable stream status monitoring | `true`, `false` |
| `status_check_interval` | Integer | Status check frequency (seconds) | 10-86400 |
| `status_cache_duration` | Integer | Status cache duration (seconds) | 1-3600 |

### Manual Player Configuration

If automatic player detection fails, you can manually configure the player:

```json
{
    "player": "vlc",
    "player_path": "C:\\Program Files\\VideoLAN\\VLC\\vlc.exe",
    "player_args": "--fullscreen --volume=50"
}
```

**Security Note**: Player arguments are validated to prevent command injection attacks.

## Security Features

TwitchAdAvoider implements comprehensive security measures:

### Input Validation
- **Channel Names**: Validated against Twitch username patterns (4-25 characters, alphanumeric + underscores)
- **Path Traversal Protection**: File paths are validated to prevent directory traversal attacks
- **Command Injection Prevention**: Player arguments are sanitized to prevent command execution
- **Control Character Filtering**: Removes potentially dangerous control characters

### Security Patterns Blocked
- Path traversal sequences (`../`, `..\\`)
- Command separators (`;`, `|`, `&`)
- Command substitution (`$()`, backticks)
- Redirection operators (`<`, `>`)
- Script injection patterns
- Windows reserved names
- Control characters and null bytes

### Real-time Validation
The GUI provides immediate feedback for:
- Invalid channel names
- Malicious input patterns
- Configuration validation errors

## Troubleshooting

### Common Issues

#### "streamlink command not found"
**Solution**: Ensure streamlink is installed:
```bash
pip install streamlink
```

#### "Video player not found"
**Solutions**:
1. Install a supported video player (see [Prerequisites](#prerequisites))
2. Set custom player path in configuration
3. Ensure player is in system PATH

#### "No streams available for channel"
**Possible Causes**:
- Channel is offline
- Channel name is incorrect
- Network connectivity issues
- Streamlink version compatibility

**Solutions**:
1. Verify channel name spelling
2. Check if channel is live on twitch.tv
3. Update streamlink: `pip install --upgrade streamlink`

#### GUI Validation Errors
**Common Issues**:
- Channel names too short (minimum 4 characters)
- Invalid characters in channel name
- Malicious input patterns detected

**Solution**: Use valid Twitch usernames (letters, numbers, underscores only)

### Debug Mode

Enable debug mode for detailed logging:

```bash
python main.py --debug
```

Or set in configuration:
```json
{
    "debug": true,
    "log_to_file": true
}
```

Debug logs are written to `logs/twitch_ad_avoider.log` when file logging is enabled.

### Getting Help

1. Check this documentation
2. Review error messages in debug mode
3. Verify your configuration file
4. Ensure all dependencies are installed

## Architecture Overview

TwitchAdAvoider follows a modular architecture with clear separation of concerns:

### Core Components

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   GUI Layer     │    │   CLI Interface  │    │  Configuration  │
│                 │    │                  │    │                 │
│ • StreamGUI     │    │ • main.py        │    │ • ConfigManager │
│ • Favorites     │    │ • Argument       │    │ • Validation    │
│   Manager       │    │   Parsing        │    │ • Persistence   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │     Core Engine         │
                    │                         │
                    │ • TwitchViewer          │
                    │ • Player Detection      │
                    │ • Stream Management     │
                    │ • Process Control       │
                    └─────────────────────────┘
                                 │
               ┌─────────────────┼─────────────────┐
               │                 │                 │
    ┌──────────▼──────────┐ ┌────▼────┐ ┌─────────▼─────────┐
    │   Security Layer    │ │ Logging │ │  External APIs    │
    │                     │ │         │ │                   │
    │ • Input Validation  │ │ • Multi │ │ • Streamlink      │
    │ • Sanitization      │ │   Level │ │ • Twitch Status   │
    │ • Attack Prevention │ │ • File  │ │ • Player Process  │
    └─────────────────────┘ └─────────┘ └───────────────────┘
```

### Data Flow

1. **User Input** → Validation → Sanitization → Processing
2. **Configuration** → Validation → Storage → Runtime Use
3. **Stream Request** → Channel Validation → Player Detection → Process Launch
4. **Status Monitoring** → API Calls → Caching → GUI Updates

### Security Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Security Perimeter                       │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ Input       │  │ Path        │  │ Command Injection   │  │
│  │ Validation  │  │ Traversal   │  │ Prevention          │  │
│  │             │  │ Protection  │  │                     │  │
│  │ • Patterns  │  │ • Absolute  │  │ • Argument          │  │
│  │ • Length    │  │   Paths     │  │   Sanitization      │  │
│  │ • Character │  │ • Bounds    │  │ • Shell Parsing     │  │
│  │   Filtering │  │   Checking  │  │ • Pattern Blocking  │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Security Role |
|-----------|---------------|---------------|
| **TwitchViewer** | Core stream management, player detection | Input validation coordination |
| **ConfigManager** | Settings persistence and validation | Configuration security enforcement |
| **Validators** | Input sanitization and security checks | Primary security enforcement |
| **StreamGUI** | User interface and real-time feedback | User input validation and feedback |
| **StatusMonitor** | Channel status tracking and caching | API rate limiting and error handling |

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup

1. Fork the repository
2. Create a virtual environment
3. Install dependencies: `pip install -r requirements.txt`
4. Run tests: `python -m pytest tests/`
5. Follow the code style guidelines

### Security Considerations

When contributing, please:
- Validate all user inputs
- Use the existing validation functions
- Add tests for security scenarios
- Document security implications

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- **Streamlink**: For providing the core streaming functionality
- **Python Community**: For excellent libraries and tools
- **Contributors**: Thank you to all who have contributed to this project