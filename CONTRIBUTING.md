# Contributing to TwitchAdAvoider

Thank you for your interest in contributing to TwitchAdAvoider! This guide will help you get started with contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Code Style Guidelines](#code-style-guidelines)
- [Testing Requirements](#testing-requirements)
- [Security Guidelines](#security-guidelines)
- [Contribution Workflow](#contribution-workflow)
- [Documentation Standards](#documentation-standards)
- [Issue Guidelines](#issue-guidelines)
- [Pull Request Process](#pull-request-process)

## Code of Conduct

By participating in this project, you agree to abide by our code of conduct:

- **Be Respectful**: Treat all contributors with respect and kindness
- **Be Constructive**: Provide helpful feedback and constructive criticism
- **Be Inclusive**: Welcome contributors of all backgrounds and experience levels
- **Be Professional**: Maintain a professional tone in all communications
- **Be Patient**: Understand that everyone is learning and growing

## Getting Started

### Prerequisites

Before contributing, ensure you have:

- **Python 3.7+** (recommended: Python 3.8 or higher)
- **Git** for version control
- **A code editor** (VS Code, PyCharm, or similar)
- **Basic understanding** of Python and software security principles

### Project Overview

TwitchAdAvoider is a security-focused application for watching Twitch streams while avoiding ads. Key aspects to understand:

- **Security First**: All user inputs are validated and sanitized
- **Cross-Platform**: Supports Windows, macOS, and Linux
- **Modular Design**: Clean separation between GUI, core logic, and configuration
- **Comprehensive Testing**: All features must have corresponding tests

## Development Setup

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/yourusername/TwitchAdAvoider-lite-2.git
cd TwitchAdAvoider-lite-2
```

### 2. Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 3. Install Dependencies

```bash
# Install dependencies (production)
pip install -e .

# Install with development dependencies
pip install -e .[dev]
```

### 4. Verify Setup

```bash
# Run tests to ensure everything works
python -m unittest discover tests/

# Alternative: Run tests with pytest
python -m pytest tests/

# Run the application
python main.py --help

# Code quality checks (now configured in pyproject.toml)
black --check .
flake8 .
python -m coverage run -m unittest discover tests/ && python -m coverage report

# Build documentation
cd docs && make html
```

## Code Style Guidelines

### Python Style

We follow **PEP 8** with some project-specific conventions:

#### Formatting
- **Line Length**: Maximum 100 characters (not 79)
- **Indentation**: 4 spaces (no tabs)
- **String Quotes**: Use double quotes `"` for strings, single quotes `'` for string literals in code
- **Imports**: Group imports by standard library, third-party, and local modules

#### Naming Conventions
```python
# Classes: PascalCase
class StreamGUI:
    pass

# Functions and variables: snake_case
def validate_channel_name(channel_name: str) -> str:
    pass

# Constants: UPPER_SNAKE_CASE
MAX_CHANNEL_LENGTH = 25

# Private methods: leading underscore
def _validate_input(self, value):
    pass
```

#### Type Hints
Always use type hints for function parameters and return values:

```python
from typing import Optional, Dict, List, Any

def process_stream(channel: str, quality: str = "best") -> Optional[subprocess.Popen]:
    """Process stream with proper type hints."""
    pass
```

### Documentation Style

#### Docstrings
Use Google-style docstrings for all functions and classes:

```python
def validate_channel_name(channel_name: str) -> str:
    """
    Validate and sanitize Twitch channel name with security controls.
    
    Args:
        channel_name: Raw channel name input
        
    Returns:
        Validated and normalized channel name
        
    Raises:
        ValidationError: If channel name is invalid or potentially malicious
        
    Example:
        >>> validate_channel_name("  TestChannel  ")
        'testchannel'
    """
    pass
```

#### Comments
- Use comments to explain **why**, not **what**
- Document complex algorithms and security considerations
- Include comments for non-obvious business logic

```python
# Multi-level path traversal protection
# Defense in depth: check both Path object analysis and string patterns
if '..' in path.parts:
    raise ValidationError("Path traversal sequences (..) are not allowed")
```

## Testing Requirements

### Test Coverage

All new features must include comprehensive tests:

- **Unit Tests**: Test individual functions and methods
- **Integration Tests**: Test component interactions
- **Security Tests**: Test validation and security measures
- **GUI Tests**: Test user interface functionality (where applicable)

### Test Structure

```python
import unittest
from unittest.mock import patch, MagicMock

from src.validators import validate_channel_name
from src.exceptions import ValidationError


class TestChannelValidation(unittest.TestCase):
    """Test channel name validation with security controls."""
    
    def test_valid_channel_names(self):
        """Test valid Twitch channel names."""
        valid_channels = ['ninja', 'shroud', 'test_channel']
        for channel in valid_channels:
            result = validate_channel_name(channel)
            self.assertEqual(result, channel.lower())
    
    def test_security_patterns(self):
        """Test rejection of security attack patterns."""
        malicious_patterns = [
            '../../../etc/passwd',  # Path traversal
            'test;whoami',  # Command injection
        ]
        for pattern in malicious_patterns:
            with self.assertRaises(ValidationError):
                validate_channel_name(pattern)
```

### Running Tests

```bash
# Run all tests
python -m pytest tests/

# Run with coverage
python -m pytest tests/ --cov=src --cov-report=html

# Run specific test file
python -m pytest tests/test_validators.py -v

# Run security-focused tests
python -m pytest tests/test_validators.py::TestChannelValidation::test_security_patterns -v
```

## Security Guidelines

Security is a top priority for TwitchAdAvoider. All contributions must follow these guidelines:

### Input Validation

**Always validate user inputs**:

```python
# ✓ Good: Use existing validation functions
from src.validators import validate_channel_name

def process_channel(channel: str) -> str:
    return validate_channel_name(channel)

# ✗ Bad: Direct use without validation
def process_channel(channel: str) -> str:
    return channel.lower()  # No validation!
```

### Command Injection Prevention

**Never concatenate user input into shell commands**:

```python
# ✓ Good: Use subprocess with argument list
subprocess.run(['streamlink', f'twitch.tv/{channel}', quality])

# ✗ Bad: String concatenation
os.system(f"streamlink twitch.tv/{channel} {quality}")
```

### Path Traversal Prevention

**Always validate file paths**:

```python
# ✓ Good: Use validation function
from src.validators import validate_file_path

def load_config(config_path: str) -> dict:
    validated_path = validate_file_path(config_path)
    with open(validated_path, 'r') as f:
        return json.load(f)

# ✗ Bad: Direct file access
def load_config(config_path: str) -> dict:
    with open(config_path, 'r') as f:  # Path traversal risk!
        return json.load(f)
```

### Security Testing

Include security test cases for all new validation:

```python
def test_command_injection_prevention(self):
    """Test prevention of command injection attacks."""
    malicious_args = [
        '--volume=50; rm -rf /',
        '--fullscreen && whoami',
        '--cache=yes | id',
    ]
    for args in malicious_args:
        with self.assertRaises(ValidationError):
            sanitize_player_args(args)
```

## Contribution Workflow

### 1. Create Feature Branch

```bash
# Create and switch to feature branch
git checkout -b feature/your-feature-name

# Or for bug fixes
git checkout -b fix/bug-description
```

### 2. Make Changes

- Follow code style guidelines
- Include comprehensive tests
- Update documentation as needed
- Ensure security best practices

### 3. Test Changes

```bash
# Run all tests
python -m pytest tests/

# Check code style
flake8 src/ gui/ tests/

# Type checking (if using mypy)
mypy src/ gui/

# Build and check documentation
cd docs && make html
```

### 4. Commit Changes

Use clear, descriptive commit messages:

```bash
# Good commit messages
git commit -m "Add channel name validation with security controls"
git commit -m "Fix path traversal vulnerability in config loader"
git commit -m "Update player detection algorithm for better reliability"

# Bad commit messages
git commit -m "fix stuff"
git commit -m "working on it"
git commit -m "changes"
```

### 5. Push and Create Pull Request

```bash
# Push feature branch
git push origin feature/your-feature-name

# Create pull request on GitHub
```

## Documentation Standards

### Code Documentation

- **All public functions** must have docstrings
- **Complex algorithms** must have inline comments
- **Security considerations** must be documented
- **Configuration options** must be explained

### User Documentation

When adding new features, update relevant documentation:

- **README.md**: Basic usage instructions
- **CONFIG-REFERENCE.md**: Configuration options
- **PLAYER-CONFIG.md**: Player-specific settings
- **SECURITY.md**: Security implications

### Documentation Format

Use Markdown for all documentation:

```markdown
## Feature Name

Brief description of the feature.

### Usage

```python
# Code example
function_call(parameter="value")
```

### Security Considerations

- Important security note 1
- Important security note 2
```

## Issue Guidelines

### Reporting Bugs

Use the bug report template and include:

- **Python version** and operating system
- **Steps to reproduce** the issue
- **Expected behavior** vs actual behavior
- **Error messages** or logs (if any)
- **Configuration** (sanitized, no sensitive data)

### Feature Requests

For new features, include:

- **Use case**: Why is this feature needed?
- **Proposed solution**: How should it work?
- **Security implications**: Any security considerations?
- **Breaking changes**: Will this break existing functionality?

### Security Issues

**Do not report security issues publicly**. Instead:

1. Email security concerns privately
2. Include detailed reproduction steps
3. Provide impact assessment
4. Allow time for coordinated disclosure

## Pull Request Process

### Before Submitting

Ensure your pull request:

- [ ] **Passes all tests** (`python -m pytest tests/`)
- [ ] **Follows code style** (flake8, black formatting)
- [ ] **Includes comprehensive tests** for new functionality
- [ ] **Updates documentation** as needed
- [ ] **Follows security guidelines**
- [ ] **Has clear commit messages**

### Pull Request Template

Use this template for pull requests:

```markdown
## Description

Brief description of changes made.

## Type of Change

- [ ] Bug fix (non-breaking change fixing an issue)
- [ ] New feature (non-breaking change adding functionality)  
- [ ] Breaking change (fix or feature causing existing functionality to change)
- [ ] Documentation update

## Security Considerations

- List any security implications
- Describe validation added
- Note any security tests included

## Testing

- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Security tests included
- [ ] Manual testing completed

## Documentation

- [ ] Code documentation updated
- [ ] User documentation updated
- [ ] Configuration documentation updated
```

### Review Process

1. **Automated checks** must pass (tests, linting)
2. **Security review** for all code changes
3. **Code review** by maintainers
4. **Documentation review** for user-facing changes
5. **Final approval** and merge

### After Merge

- Delete feature branch
- Update local repository
- Consider contributing to related documentation

## Development Best Practices

### Code Organization

```
src/                    # Core application logic
├── validators.py       # Input validation and security
├── config_manager.py   # Configuration management
├── twitch_viewer.py    # Main stream functionality
└── exceptions.py       # Custom exception classes

gui/                    # User interface components
├── stream_gui.py       # Main GUI application
└── favorites_manager.py # Favorites management

tests/                  # Test suite
├── test_validators.py  # Validation tests
├── test_config_validation.py # Configuration tests
└── test_twitch_viewer.py # Main functionality tests
```

### Error Handling

Use specific exception types and provide helpful error messages:

```python
# ✓ Good: Specific exceptions with helpful messages
try:
    validated_channel = validate_channel_name(channel)
except ValidationError as e:
    logger.warning(f"Channel validation failed: {e}")
    return None

# ✗ Bad: Generic exception handling
try:
    validated_channel = validate_channel_name(channel)
except Exception:
    return None  # No information about what went wrong
```

### Logging

Use appropriate log levels and structured logging:

```python
import logging
from src.logging_config import get_logger

logger = get_logger(__name__)

# Use appropriate log levels
logger.debug("Detailed debugging information")
logger.info("General information about program execution")
logger.warning("Something unexpected happened")
logger.error("A serious error occurred")
logger.critical("The program cannot continue")
```

### Performance Considerations

- **Minimize network requests** (use caching where appropriate)
- **Avoid blocking the GUI thread** (use threading for long operations)
- **Validate inputs early** (fail fast on invalid data)
- **Use efficient algorithms** (consider time and space complexity)

## Questions and Support

### Getting Help

- **Documentation**: Check existing documentation first
- **Issues**: Search existing issues for similar problems
- **Discussions**: Use GitHub Discussions for questions
- **Discord/IRC**: Check if project has a community chat

### Mentorship

New contributors are welcome! If you're new to:

- **Python**: We can help you learn best practices
- **Security**: We'll guide you through security considerations
- **Open Source**: We'll help you navigate the contribution process
- **Testing**: We'll help you write effective tests

## Recognition

Contributors are recognized through:

- **Contributors file**: All contributors are listed
- **Release notes**: Significant contributions are highlighted
- **GitHub insights**: Contribution statistics are visible
- **Community recognition**: Outstanding contributions are celebrated

---

Thank you for contributing to TwitchAdAvoider! Your efforts help make the project better for everyone.