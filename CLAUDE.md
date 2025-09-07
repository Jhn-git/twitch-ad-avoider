# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TwitchAdAvoider is a security-focused Python application for watching Twitch streams while avoiding ads. It features both GUI and command-line interfaces, with comprehensive input validation and cross-platform video player support.

## Architecture

### Core Components
- **`src/twitch_viewer.py`**: Main streaming logic and player detection
- **`src/config_manager.py`**: JSON configuration with comprehensive validation
- **`src/validators.py`**: Security-focused input validation (channel names, file paths, player args)
- **`gui/stream_gui.py`**: Tkinter GUI with real-time validation
- **`gui/favorites_manager.py`**: Channel favorites persistence and management

### Security Architecture
The application implements defense-in-depth security:
- **Input Validation Layer**: All user inputs validated via `src/validators.py`
- **Path Traversal Prevention**: File paths validated for `../` sequences and dangerous characters
- **Command Injection Prevention**: Player arguments sanitized to block shell metacharacters
- **Pattern-based Attack Detection**: Regex patterns detect various attack vectors

### Player Detection System
Multi-priority detection algorithm in `TwitchViewer._detect_player()`:
1. Manual player path from configuration
2. GUI selection override
3. System PATH search
4. Common installation directory search
5. Environment variables (`TWITCH_PLAYER_PATH`, `TWITCH_PLAYER_NAME`)
6. Fallback to streamlink auto-detection

## Development Commands

### Running the Application
```bash
# GUI mode (default)
python main.py

# Command-line mode
python main.py --channel ninja --quality 720p

# Debug mode
python main.py --debug

# PowerShell launcher (Windows)
./run.ps1
```

### Testing
```bash
# Run all tests
python -m unittest discover tests/

# Run specific test file
python -m unittest tests.test_validators

# Run specific test method
python -m unittest tests.test_validators.TestChannelValidation.test_valid_channel_names

# Alternative: Run tests with pytest
python -m pytest tests/

# Run specific test with pytest
python -m pytest tests/test_validators.py::TestChannelValidation::test_valid_channel_names
```

### Code Quality Tools
```bash
# Format code with Black (configured in pyproject.toml)
black --check .

# Lint code with flake8
flake8 .

# Type checking with mypy
python -m mypy src/

# Generate coverage report
python -m coverage run -m unittest discover tests/
python -m coverage report
```

### Building Executable
```bash
# Build Windows executable (includes pycparser fix)
python build_executable.py

# Build with options
python build_executable.py --skip-deps --no-clean
```

**PyInstaller pycparser Fix**: The build process automatically generates pycparser parser tables before building to prevent "Unable to build parser" runtime errors. This fix ensures that the cryptography library (used for OAuth token encryption) works correctly in the compiled executable.

### Configuration
- Configuration file: `config/settings.json`
- Favorites file: `config/favorites.json`
- Log file: `logs/twitch_ad_avoider.log`

### Package Installation
The project is configured as an installable Python package using `pyproject.toml`:

```bash
# Install dependencies (production)
pip install -e .

# Install with development dependencies
pip install -e .[dev]

# Core dependency: streamlink>=5.0.0
# Development dependencies: pytest, black, flake8, mypy, coverage, pre-commit
```

## Key Implementation Details

### Modern Python Project Structure
The project follows modern Python packaging standards:
- **`pyproject.toml`**: Centralized project configuration, dependencies, and tool settings
- **Editable installation**: `pip install -e .` for development workflow
- **Tool configuration**: Black, flake8, pytest, coverage, and mypy configured in pyproject.toml
- **Package metadata**: Version, description, authors, and classifiers defined

### Configuration System
The `ConfigManager` class handles JSON-based configuration with:
- Automatic default value merging
- Comprehensive validation of all settings
- Atomic saves with error recovery
- UTF-8 encoding support

### Validation Pipeline
All inputs flow through `src/validators.py`:
- Channel names: Twitch username pattern validation + security checks
- File paths: Path traversal protection + dangerous character filtering
- Player arguments: Command injection prevention via pattern matching + shell parsing validation

### Error Handling
Custom exception hierarchy in `src/exceptions.py`:
- `ValidationError`: Input validation failures
- `TwitchStreamError`: Stream-related errors
- `PlayerError`: Video player issues
- `StreamlinkError`: Streamlink integration errors

### GUI Architecture
The Tkinter GUI implements:
- Real-time input validation with visual feedback
- Asynchronous status monitoring for favorite channels
- Thread-safe operations for non-blocking UI
- Cross-platform file dialogs and system integration

## Security Considerations

When making changes:
- Always use existing validation functions from `src/validators.py`
- Never concatenate user input into shell commands
- Use subprocess with argument lists instead of shell=True
- Validate all file paths for traversal attacks
- Test security scenarios with malicious inputs
- Use the existing logging system for security events

## Testing Strategy

The test suite covers:
- **Unit tests**: Individual function validation
- **Security tests**: Malicious input patterns
- **Integration tests**: Component interaction
- **GUI tests**: User interface functionality

Focus on security test cases when adding new validation or input handling.