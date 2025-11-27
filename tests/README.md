# TwitchAdAvoider Tests

Quick reference for running tests in this personal project.

## Running Tests

### All Tests
```bash
pytest tests/
```

### Specific Test File
```bash
pytest tests/test_auth_manager.py
pytest tests/test_twitch_chat_client.py
pytest tests/test_favorites_manager.py
pytest tests/test_validators.py
```

### Specific Test Class or Method
```bash
pytest tests/test_auth_manager.py::TestAuthManager::test_encryption_decryption_roundtrip
pytest tests/test_validators.py::TestChannelNameValidation
```

### With Verbose Output
```bash
pytest tests/ -v
```

### With Coverage
```bash
# Run tests with coverage
pytest tests/ --cov=src --cov-report=term-missing

# Generate HTML coverage report
pytest tests/ --cov=src --cov-report=html
# Open htmlcov/index.html in browser
```

## Test Organization

### Critical Component Tests (Security & Core)
- **test_auth_manager.py** - OAuth authentication, token encryption, secure storage
- **test_twitch_chat_client.py** - IRC connection, message handling, USERSTATE confirmation
- **test_favorites_manager.py** - Favorites CRUD, JSON persistence, data integrity
- **test_validators.py** - Input validation, security attack prevention (path traversal, command injection)

### Configuration Tests
- **test_config_validation.py** - Settings validation, config management
- **test_network_config.py** - Network settings, timeout configuration

### Application Logic Tests
- **test_twitch_viewer.py** - Stream viewer, player detection (partial coverage)

### Shared Fixtures
- **conftest.py** - Reusable test fixtures, mock objects, test data

## What's Tested (Personal Project Scope)

✅ **Critical paths that prevent regressions:**
- Authentication & token security
- Chat messaging & IRC protocol
- Data persistence (favorites)
- Input validation & security

❌ **Intentionally skipped (overkill for solo use):**
- GUI components (manual testing is fine)
- Error recovery edge cases
- Performance/concurrency stress tests
- Integration/E2E tests

## Common Test Patterns

### Using Fixtures
```python
def test_with_temp_config(temp_config_path):
    """Uses temp_config_path fixture from conftest.py"""
    config = ConfigManager(temp_config_path)
    # ... test code
```

### Security Testing
```python
def test_path_traversal_prevention():
    """Test that malicious paths are rejected"""
    malicious_paths = ['../../../etc/passwd', '..\\..\\windows\\system32']
    for path in malicious_paths:
        with self.assertRaises(ValidationError):
            validate_file_path(path)
```

### Mocking External Services
```python
@patch('socket.socket')
def test_irc_connection(mock_socket):
    """Mock socket for IRC testing"""
    mock_instance = MagicMock()
    mock_socket.return_value = mock_instance
    # ... test IRC code without real connection
```

## Tips

### Watch Mode (Run Tests on File Changes)
```bash
pytest-watch tests/
```

### Only Run Failed Tests
```bash
pytest tests/ --lf
```

### Stop on First Failure
```bash
pytest tests/ -x
```

### Show Print Statements
```bash
pytest tests/ -s
```

### Run Tests by Marker
```bash
# Mark tests with @pytest.mark.security
pytest tests/ -m security
```

## Target Coverage

**Goal:** ~40-50% coverage on critical paths

- ✅ AuthManager: ~90% (security-critical)
- ✅ TwitchChatClient: ~85% (security-critical)
- ✅ FavoritesManager: ~90% (data integrity)
- ✅ Validators: ~95% (security-critical)
- ✅ ConfigManager: ~70% (configuration)
- ⚠️ TwitchViewer: ~40% (partial)
- ❌ GUI: 0% (manual testing only)

**Philosophy:** Focus on tests that catch bugs when making changes, not on hitting arbitrary coverage percentages.
