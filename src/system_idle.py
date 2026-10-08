"""Windows system-wide input idle time, via the Win32 GetLastInputInfo API.

Used to tell "the user is away from the PC entirely" (no keyboard/mouse input
anywhere, regardless of which window is focused) apart from "the app window
merely isn't focused" - the latter is also true while the user is actively
working in another application.
"""

from __future__ import annotations

import ctypes
import os

_TICK_COUNT_WRAP = 2**32


def _idle_millis(tick_count: int, last_input_tick: int) -> int:
    """Milliseconds between two 32-bit tick counts, handling wraparound.

    Both GetTickCount() and LASTINPUTINFO.dwTime are 32-bit millisecond
    counters that wrap to 0 every ~49.7 days of uptime; a naive subtraction
    goes negative right after a wrap.
    """
    diff = tick_count - last_input_tick
    if diff < 0:
        diff += _TICK_COUNT_WRAP
    return diff


def get_system_idle_seconds() -> float:
    """Seconds since the last system-wide keyboard/mouse input.

    Returns 0.0 on non-Windows platforms and if the Win32 call fails, so
    callers on those platforms/conditions never treat the user as idle.
    """
    if os.name != "nt":
        return 0.0

    class _LastInputInfo(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

    info = _LastInputInfo()
    info.cbSize = ctypes.sizeof(_LastInputInfo)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):  # type: ignore[attr-defined]
        return 0.0

    tick_count = ctypes.windll.kernel32.GetTickCount()  # type: ignore[attr-defined]
    return _idle_millis(tick_count, info.dwTime) / 1000.0
