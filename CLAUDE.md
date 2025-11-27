<!-- Last Updated: 2025-11-27 | Target Audience: AI Assistants, Developers -->

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## 🎯 Project Context

**This is a PERSONAL PROJECT for solo use** - not intended for distribution or collaboration.

**Development Approach**:
- ✅ Focus on **practical value** (catching bugs, preventing regressions)
- ✅ Test **critical components only** (auth, chat, streaming, data persistence)
- ❌ Skip enterprise bloat (CI/CD, pre-commit hooks, contribution guidelines)
- ❌ Skip GUI tests (manual testing is sufficient for personal use)
- ❌ No strict coverage targets (40-50% on critical paths is fine)

**When suggesting improvements**:
- Prioritize features/fixes the user will actually use
- Avoid over-engineering for hypothetical future needs
- Skip collaboration tooling (issue templates, PR workflows, etc.)
- Keep testing practical, not comprehensive

---

## Project Overview

TwitchAdAvoider is a **security-focused Python application** for watching Twitch streams while avoiding ads. Features GUI (PySide6 Qt) and CLI interfaces with comprehensive input validation.

**Key Characteristics**:
- Security-first design (all inputs validated)
- Modern Python packaging (`pyproject.toml`)
- Cross-platform (Windows, macOS, Linux)
- Modular architecture

---

## Core Components

| Component | File | Responsibility |
|-----------|------|----------------|
| **TwitchViewer** | `src/twitch_viewer.py` | Streaming logic, player detection |
| **ConfigManager** | `src/config_manager.py` | JSON config with validation |
| **Validators** | `src/validators.py` | **Security input validation** |
| **AuthManager** | `src/auth_manager.py` | OAuth authentication |
| **TwitchChatClient** | `src/twitch_chat_client.py` | IRC chat (USERSTATE confirmation) |
| **StreamGUI** | `gui_qt/stream_gui.py` | Qt GUI orchestrator |
| **MainWindow** | `gui_qt/main_window.py` | Tabbed interface |
| **SettingsTab** | `gui_qt/components/settings_tab.py` | Settings interface |

**Data Flow**: `User Input → Validators → ConfigManager → TwitchViewer → Player`

---

## Security Architecture

**Defense-in-depth** security via `src/validators.py`:

**Attack Prevention**:
- **Path Traversal**: Blocks `../`, `..\\` sequences
- **Command Injection**: Blocks `;`, `|`, `&`, `$()`, backticks
- **Control Characters**: Filters null bytes, dangerous chars
- **Pattern Detection**: Regex-based attack detection

**Security Principles** (CRITICAL):
- ✅ Always use validators from `src/validators.py`
- ✅ Use subprocess with argument lists (never `shell=True` with user input)
- ✅ Validate all file paths for traversal
- ✅ Test with malicious inputs
- ❌ Never concatenate user input into shell commands
- ❌ Never trust user input without validation

**For complete security docs**, see [SECURITY.md](SECURITY.md).

---

## Development Commands

### Running
```bash
python main.py                              # GUI mode
python main.py --channel ninja --quality 720p  # CLI mode
python main.py --debug                      # Debug mode
```

### Testing
```bash
python -m pytest tests/                     # All tests
python -m pytest tests/test_validators.py   # Specific file
python -m coverage run -m pytest tests/ && python -m coverage report  # Coverage
```

### Code Quality
```bash
black .                   # Format
flake8 .                  # Lint
python -m mypy src/       # Type check

# Before committing:
black . && flake8 . && mypy src/ && pytest tests/
```

### Building
```bash
python build_executable.py  # Windows executable
```

---

## Key Implementation Details

### Configuration System
`ConfigManager` (`src/config_manager.py`):
- JSON-based (`config/settings.json`)
- Validates all 16+ settings before save
- Atomic saves with error recovery

### Validation Pipeline
All inputs through `src/validators.py`:

```python
from src.validators import validate_channel_name, ValidationError

try:
    channel = validate_channel_name(user_input)
except ValidationError as e:
    logger.error(f"Invalid: {e}")
```

**Validators**:
- `validate_channel_name()` - Twitch username + security
- `validate_player_path()` - Path traversal prevention
- `validate_player_args()` - Command injection prevention
- `validate_quality()` - Enum validation
- `validate_log_level()` - Enum validation

### Error Handling
Custom exceptions in `src/exceptions.py`:
```
TwitchAdAvoiderError (base)
├── ValidationError (input validation)
├── TwitchStreamError (stream issues)
├── PlayerError (player issues)
└── StreamlinkError (streamlink issues)
```

### File Locations
- `config/settings.json` - App settings
- `config/favorites.json` - Favorite channels
- `logs/twitch_ad_avoider.log` - Logs

---

## Package Installation

```bash
pip install -e .        # Production
pip install -e .[dev]   # Development (includes pytest, black, flake8, mypy)
```

**Core Dependencies**: streamlink, PySide6, cryptography, requests
**Dev Dependencies**: pytest, black, flake8, mypy, coverage

**For installation details**, see [INSTALLATION.md](INSTALLATION.md).

---

## Testing Strategy

**Philosophy**: Focus on tests that **prevent regressions** when making changes. Skip enterprise testing practices.

**Test Coverage** (`tests/`) - **Target: 40-50% on critical paths**:
- ✅ Unit tests for **critical components** (auth, chat, streaming, data persistence)
- ✅ **Security tests** (malicious inputs, path traversal, command injection)
- ❌ GUI tests (manual testing is sufficient for personal use)
- ❌ Integration/E2E tests (overkill for solo project)
- ❌ CI/CD, pre-commit hooks, coverage enforcement

**What to Test**:
- **AuthManager** - OAuth flow, token encryption, secure storage
- **TwitchChatClient** - IRC connection, message handling, authentication
- **FavoritesManager** - Save/load operations, data integrity
- **TwitchViewer** - Stream opening, player detection
- **Validators** - Security validation (already well-tested)
- **ConfigManager** - Settings validation (already tested)

**What to Skip**:
- GUI components (you'll catch issues by using the app)
- Error recovery edge cases
- Performance/concurrency tests
- Utilities with minimal risk

**Security Testing Pattern**:
```python
def test_security_validation(self):
    malicious = ["../../../etc/passwd", "test;whoami", "test`id`"]
    for bad in malicious:
        with self.assertRaises(ValidationError):
            validate_function(bad)
```

**Security tests are REQUIRED** when adding:
- New validation functions
- Input handling code
- Authentication/authorization code
- File operations

---

## Common Development Patterns

### Adding Configuration Option
1. Add default in `ConfigManager.DEFAULT_CONFIG`
2. Add validation in `ConfigManager._validate_config()`
3. Update Settings tab: `gui_qt/components/settings_tab.py`
4. Document in `CONFIG-REFERENCE.md`
5. Add tests in `tests/test_config_validation.py`

### Adding Validator
1. Create function in `src/validators.py`
2. Raise `ValidationError` for invalid inputs
3. Add tests (valid + malicious inputs)
4. Document in `SECURITY.md` if security-related
5. Use in appropriate components

### Adding GUI Component
1. Create in `gui_qt/components/`
2. Use Qt signals for communication
3. Validate inputs in real-time
4. Update main window
5. Test manually (no automated GUI tests for personal project)

---

## Architecture Details

### Player Detection
Priority order (`TwitchViewer._detect_player()`):
1. Manual config path
2. GUI selection
3. System PATH
4. Common install dirs
5. Environment variables
6. Streamlink auto-detect

### Chat System
- OAuth via `AuthManager`
- IRC: `irc.chat.twitch.tv`
- **USERSTATE messages** for confirmation (not PRIVMSG echoes)
- Thread-safe (background IRC, main thread UI)

### GUI Structure
- **Stream Tab**: Favorites panel, stream controls, chat panel
- **Settings Tab**: Stream, network, chat, appearance, advanced settings
- Signal-based architecture
- Real-time validation feedback

**For detailed architecture**, see [README.md](README.md#architecture).

---

## Security Checklist

When making changes:
- [ ] Validate all user inputs via `src/validators.py`
- [ ] Use subprocess argument lists (not `shell=True`)
- [ ] Validate file paths for traversal
- [ ] Test with malicious inputs
- [ ] Log security events
- [ ] Add security tests
- [ ] Update SECURITY.md if needed

---

## See Also

**User Docs**: [CONFIG-REFERENCE.md](CONFIG-REFERENCE.md)

**Dev Docs**: [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md)

**Reference**: [README.md](README.md), [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

---

**Last Updated**: 2025-11-27 | **Target**: AI assistants, developers
