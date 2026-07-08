"""
Startup runtime validation.

pywebview's Windows backend uses pythonnet. At the moment pythonnet does not
support Python 3.14, so fail before pywebview tries to initialize .NET.
"""

import platform
import sys

MAX_WINDOWS_PYTHON = (3, 13)


def is_windows_python_supported(version_info=None, system=None):
    version_info = version_info or sys.version_info
    system = system or platform.system()
    return system != "Windows" or version_info[:2] <= MAX_WINDOWS_PYTHON


def unsupported_runtime_message(version_info=None):
    version_info = version_info or sys.version_info
    major, minor, micro = version_info[:3]
    max_major, max_minor = MAX_WINDOWS_PYTHON
    return (
        f"Python {major}.{minor}.{micro} is not supported for this app on Windows. "
        "pywebview uses pythonnet for its Windows backend, and this project's "
        f"supported range currently tops out at Python {max_major}.{max_minor}. "
        "Recreate the virtual environment with Python 3.13 or 3.12, then run "
        "`pip install -e .` again."
    )


def verify_compatible(version_info=None, system=None):
    if not is_windows_python_supported(version_info, system):
        raise SystemExit(unsupported_runtime_message(version_info))
