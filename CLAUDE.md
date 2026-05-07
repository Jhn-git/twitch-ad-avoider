# CLAUDE.md

<!-- Last Updated: 2025-11-27 | Target: AI Assistants, Developers -->

## Project Context

**Personal project for solo use** - not for distribution.

- ✅ Focus on practical value, test critical components only (auth, chat, streaming, persistence)
- ✅ Target 40-50% coverage on critical paths
- ❌ Skip: GUI tests, CI/CD, pre-commit hooks, enterprise bloat, over-engineering

---

## Overview

**TwitchAdAvoider**: Security-focused Python app for ad-free Twitch viewing. GUI (PySide6) + CLI.

**Data Flow**: `User Input → Validators → ConfigManager → TwitchViewer → Player`

| Component     | File                                | Purpose                     |
| ------------- | ----------------------------------- | --------------------------- |
| TwitchViewer  | `src/twitch_viewer.py`              | Streaming, player detection |
| ConfigManager | `src/config_manager.py`             | JSON config + validation    |
| Validators    | `src/validators.py`                 | Security input validation   |
| StreamGUI     | `gui_qt/stream_gui.py`              | Qt GUI orchestrator         |
| SettingsTab   | `gui_qt/components/settings_tab.py` | Settings interface          |

---

## Security (CRITICAL)

**Principles**:

- ✅ Always use `src/validators.py` for user input
- ✅ Use subprocess with argument lists (never `shell=True` with user input)
- ✅ Validate file paths for traversal
- ✅ Test with malicious inputs

**Validators** (`src/validators.py`):

- `validate_channel_name()` - 4-25 chars, alphanumeric + underscore only
- `validate_player_path()` - Path traversal prevention
- `validate_player_args()` - Command injection prevention
- `validate_quality()` / `validate_log_level()` - Enum validation

**Blocked Patterns**:

- Path traversal: `../`, `..\\`
- Command injection: `;`, `|`, `&`, `$()`, backticks
- Control chars: null bytes, dangerous chars
- Windows reserved names: con, prn, aux, etc.

**Security Test Pattern** (required for new validators/input handling):

```python
def test_security_validation(self):
    malicious = ["../../../etc/passwd", "test;whoami", "test`id`", "test\x00name"]
    for bad in malicious:
        with self.assertRaises(ValidationError):
            validate_function(bad)
```

---

## Commands

**Use Makefile** (recommended):

```bash
make run      # Run app
make test     # Run tests
make check    # Format, lint, type check
make all      # Checks + tests (before commit)
make build    # Full build workflow
```

**Direct**:

```bash
python main.py                                 # GUI
python main.py --channel ninja --quality 720p  # CLI
python -m pytest tests/                        # Tests
black . && flake8 . && python -m mypy src/     # Quality
```

---

## Key Details

**Config**: `ConfigManager` uses JSON (`config/settings.json`), validates all settings, atomic saves.

**Exceptions** (`src/exceptions.py`):

```
TwitchAdAvoiderError (base)
├── ValidationError    # Input validation
├── TwitchStreamError  # Stream issues
├── PlayerError        # Player issues
└── StreamlinkError    # Streamlink issues
```

**File Locations**:

- `config/settings.json` - Settings
- `config/favorites.json` - Favorites
- `logs/twitch_ad_avoider.log` - Logs

**Player Detection Priority**: Manual config → GUI selection → PATH → Common dirs → Env vars → Streamlink auto

**Chat**: Browser-based via `webbrowser.open()` (Twitch popout chat URL). No IRC or OAuth.

---

## Code Style

**Format**: PEP 8, 100 char lines, 4-space indent, double quotes
**Naming**: `PascalCase` (classes), `snake_case` (functions/vars), `UPPER_SNAKE` (constants), `_private` (prefix)
**Required**: Type hints on all functions, Google-style docstrings

```python
def validate_channel_name(channel_name: str) -> str:
    """Validate Twitch channel name with security controls.

    Args:
        channel_name: Raw channel name input
    Returns:
        Validated and normalized channel name
    Raises:
        ValidationError: If invalid or malicious
    """
```

**Error Handling**: Use specific exceptions, log with context:

```python
try:
    channel = validate_channel_name(input)
except ValidationError as e:
    logger.warning(f"Validation failed: {e}")
```

---

## Development Patterns

**Adding Config Option**:

1. Add default in `ConfigManager.DEFAULT_CONFIG`
2. Add validation in `ConfigManager._validate_config()`
3. Update `gui_qt/components/settings_tab.py`
4. Add tests

**Adding Validator**:

1. Create in `src/validators.py`, raise `ValidationError`
2. Add tests (valid + malicious inputs)
3. Use in components

**Adding GUI Component**:

1. Create in `gui_qt/components/`
2. Use Qt signals, validate inputs real-time
3. Test manually

---

## Security Checklist

- [ ] Validate inputs via `src/validators.py`
- [ ] Subprocess argument lists (no `shell=True`)
- [ ] File paths checked for traversal
- [ ] Tested with malicious inputs
- [ ] Security tests added

---

## Git Guidelines

- **Commit Messages**: DO NOT include "Co-authored-by" trailers. Commits should only represent the user.

---

## Installation

```bash
pip install -e .       # Production
pip install -e .[dev]  # Dev (pytest, black, flake8, mypy)
```

**Deps**: streamlink, PySide6, cryptography, requests