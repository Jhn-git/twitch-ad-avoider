.PHONY: help clean test format lint typecheck check run build install dev-install all

# Detect OS for cross-platform compatibility
ifeq ($(OS),Windows_NT)
    PYTHON := python
    RUN_CMD := $(PYTHON) main.py
else
    PYTHON := python3
    RUN_CMD := QT_QPA_PLATFORM=xcb $(PYTHON) main.py
endif

# Default target - show available commands
help:
	@echo "TwitchAdAvoider - Available Commands"
	@echo "===================================="
	@echo ""
	@echo "Development:"
	@echo "  make run          - Run the application (GUI mode)"
	@echo "  make test         - Run all tests"
	@echo "  make format       - Format code with black"
	@echo "  make lint         - Lint code with flake8"
	@echo "  make typecheck    - Type check with mypy"
	@echo "  make check        - Run format, lint, and typecheck"
	@echo "  make all          - Run check + test (pre-commit workflow)"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean        - Remove build artifacts and caches"
	@echo "  make install      - Install package (production)"
	@echo "  make dev-install  - Install package with dev dependencies"
	@echo ""
	@echo "Building:"
	@echo "  make build        - Build Windows executable (clean + check + test + build)"
	@echo ""

# Run the application
run:
	$(RUN_CMD)

# Run tests
test:
	$(PYTHON) -m pytest tests/

# Run tests with coverage
test-coverage:
	$(PYTHON) -m coverage run -m pytest tests/
	$(PYTHON) -m coverage report

# Format code with black
format:
	$(PYTHON) -m black .

# Lint with flake8
lint:
	$(PYTHON) -m flake8 .

# Type check with mypy
typecheck:
	$(PYTHON) -m mypy src/

# Run all code quality checks
check: format lint typecheck
	@echo "✓ All checks passed"

# Pre-commit workflow (checks + tests)
all: check test
	@echo "✓ All checks and tests passed"

# Clean build artifacts and caches
clean:
	@echo "Cleaning build artifacts..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf build/ dist/ *.egg-info .coverage build_cache/ .pytest_cache/ 2>/dev/null || true
	@echo "✓ Cleanup complete"

# Install package (production)
install:
	pip install -e .

# Install package with dev dependencies
dev-install:
	pip install -e .[dev]

# Build Windows executable (skip tests for faster builds)
build: clean
	@echo "Building executable..."
	$(PYTHON) scripts/build_executable.py
	@echo "✓ Build complete"

# Build with full quality checks and tests
build-full: clean format lint test
	@echo "Building executable..."
	$(PYTHON) scripts/build_executable.py
	@echo "✓ Build complete"
