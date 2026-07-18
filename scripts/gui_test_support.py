#!/usr/bin/env python3
"""Safety helpers for driving the real app/backend from a test script.

``TEMP_DIR``/``CLIPS_DIR`` (``src/constants.py``) are hardcoded relative
paths, not per-session-isolated - any process launched from the repo root
(a real ``main.py`` session *and* a test script) writes the rolling
recording to the exact same ``temp/recording_<channel>.ts`` file if both
happen to be watching the same channel. Session 22 hit this for real: a
live-testing script collided with the user's own running app, and the two
processes briefly appended to the same file concurrently.

Use ``warn_if_app_running()`` before starting a live test, and
``patch_temp_dir()`` / ``make_scratch_config()`` to keep the test's
recording and clip output in a scratch directory so it can never collide
with a real session again - even if one happens to be running at the same
time on the same channel.

Typical use in a driver script::

    from scripts.gui_test_support import (
        warn_if_app_running, patch_temp_dir, make_scratch_config,
    )

    warn_if_app_running()
    scratch_dir = Path(tempfile.mkdtemp(prefix="twitch_viewer_gui_test_"))
    config = make_scratch_config(scratch_dir)
    with patch_temp_dir(scratch_dir):
        api = TwitchViewerAPI(config, launch_channel="somechannel")
        window = webview.create_window(..., js_api=api, ...)
        api.set_window(window)
        ...
"""

from __future__ import annotations

import contextlib
import subprocess
import sys
from pathlib import Path
from typing import Iterator

REPO_ROOT = Path(__file__).resolve().parent.parent


def find_running_app_pids() -> list[int]:
    """Return PIDs of other ``main.py`` processes already running from this repo.

    Windows-only (matches this project's dev environment - see AGENTS.md).
    Best-effort: returns an empty list if the check itself fails for any
    reason (missing PowerShell, permissions, etc.) rather than raising, since
    this is a safety nice-to-have, not something a test run should die on.
    """
    if sys.platform != "win32":
        return []
    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_Process -Filter \"Name='python.exe' or Name='pythonw.exe'\" "
                "| Where-Object { $_.CommandLine -like '*main.py*' } "
                "| Select-Object -ExpandProperty ProcessId",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return [int(line) for line in result.stdout.split() if line.strip().isdigit()]
    except Exception:
        return []


def warn_if_app_running() -> list[int]:
    """Print a loud warning (does not raise/abort) if a real app instance is
    running. Returns the PIDs found, in case the caller wants to decide for
    itself whether to proceed, prompt, or bail out."""
    pids = find_running_app_pids()
    if pids:
        print(
            f"[WARNING] {len(pids)} real `main.py` process(es) already running "
            f"(PID {', '.join(str(p) for p in pids)}). Make sure this test run "
            "uses patch_temp_dir()/make_scratch_config() below, and avoid "
            "picking the same channel the real session is watching if you can "
            "help it - the two will otherwise compete for the same network "
            "bandwidth even with recording paths isolated.",
            file=sys.stderr,
        )
    return pids


@contextlib.contextmanager
def patch_temp_dir(scratch_dir: Path) -> Iterator[Path]:
    """Redirect WebStreamService's rolling-recording path to a scratch dir.

    TEMP_DIR is a hardcoded constant (src/constants.py) imported by name into
    src.web_stream_service's module namespace - patching that module-level
    binding is what actually takes effect, since _prepare_recording() reads
    the name from its own module, not from src.constants directly. Restores
    the original binding on exit even if the test raises.
    """
    import src.web_stream_service as web_stream_service

    scratch_temp = scratch_dir / "temp"
    scratch_temp.mkdir(parents=True, exist_ok=True)
    original = web_stream_service.TEMP_DIR
    web_stream_service.TEMP_DIR = scratch_temp
    try:
        yield scratch_temp
    finally:
        web_stream_service.TEMP_DIR = original


def make_scratch_config(scratch_dir: Path):
    """A fresh ConfigManager rooted entirely in a scratch directory.

    Never touches the user's real config/settings.json, and clip_directory
    is redirected too - so a test run's clips can't land in the real clips
    folder. Does not touch config/favorites.json at all (FavoritesManager
    always uses its own default path); safe as long as the test script never
    calls favorites-mutating API methods (add/remove/toggle/refresh).
    """
    from src.config_manager import ConfigManager

    scratch_clips = scratch_dir / "clips"
    scratch_clips.mkdir(parents=True, exist_ok=True)
    config = ConfigManager(scratch_dir / "settings.json")
    config.set("clip_directory", str(scratch_clips))
    config.save_settings()
    return config
