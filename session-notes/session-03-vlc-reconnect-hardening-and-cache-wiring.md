# Session 03: VLC Reconnect Hardening And Cache Wiring

Date: 2026-07-01

## What Happened

- Investigated the occasional VLC stopouts during streamer-side or network issues using the desktop app log and the current repo code.
- Confirmed the failure starts upstream of VLC: the app log showed `No new segments for more than 18.00s. Stopping...`, then a clean player exit, reconnect messaging, and later a manual double-click that started a fresh launch.
- Decided to keep external VLC instead of moving playback into the app for now.
- Patched reconnect handling so once a stream has already been running, a reconnect-time `No streams available` error now uses the remaining retry budget instead of ending the whole reconnect flow immediately.
- Wired `cache_duration` into the actual VLC launch args so buffering is controlled by a real setting instead of relying on hardcoded cache flags living inside `player_args`.
- Added config migration logic to strip managed VLC cache flags out of saved `player_args` on load, plus focused tests around the reconnect and cache-arg behavior.

## Key Decisions

- Keep the external VLC architecture and harden the stream/reconnect layer before considering an embedded-player rewrite.
- Treat `cache_duration` as the source of truth for VLC buffering.
- Treat `player_args` as freeform non-cache player flags going forward.
- Keep initial launch `No streams available` as a normal immediate stream error; only reconnect-time startup failures should consume retry budget.

## Files Changed

- `gui_qt/controllers/stream_controller.py`
- `src/twitch_viewer.py`
- `src/player_args.py`
- `src/config_manager.py`
- `src/constants.py`
- `gui_qt/components/settings_tab.py`
- `tests/test_stream_controller.py`
- `tests/test_twitch_viewer.py`
- `tests/test_config_validation.py`

## Verification

- Ran `.\.venv\Scripts\python.exe -m pytest tests/test_stream_controller.py tests/test_twitch_viewer.py tests/test_config_validation.py`.
- Focused suite passed: `55 passed, 9 subtests passed`.
- Ran `.\.venv\Scripts\python.exe -m py_compile src/player_args.py src/twitch_viewer.py src/config_manager.py gui_qt/controllers/stream_controller.py gui_qt/components/settings_tab.py`.
- Ran `git diff --check`.
- Attempted a broader `.\.venv\Scripts\python.exe -m pytest tests\`, but collection stopped on unrelated import errors in two stray test files belonging to an unrelated related project.

## Current Progress

- Reconnects now keep retrying after a reconnect-launch `No streams available` failure instead of bailing after the first failed relaunch.
- VLC runtime cache args now follow `cache_duration`, and old managed cache flags in `player_args` are stripped during config load.
- The Settings UI now hints that cache is managed separately from freeform player args.
- The main unresolved UX edge case is still manual double-clicking during an active reconnect window; the current UI can interrupt the reconnect cycle and start a fresh launch.
- There is still an unrelated repo-wide test-collection issue around those stray tests, but it did not block the focused stream/reconnect verification.

## Things We Haven't Tried Yet

- Live-testing the new reconnect behavior during a real streamer outage or an induced segment stall.
- Verifying how the app behaves if the channel comes back after one or two reconnect-launch `No streams available` failures in the real GUI.
- Deciding whether manual double-click/start requests should be ignored, debounced, or queued while reconnect is already in progress.
- Trying different `cache_duration` values in the live app to see whether the added buffer is worth the startup delay.
- Deciding whether the non-VLC players should keep ignoring `cache_duration` or whether they need a similar managed-buffer path later.
- Running the full repo test suite after the unrelated stray-module import issue is fixed.

## Next Steps

- Do one live reconnect test in the desktop app during a real or simulated interruption.
- If the manual restart UX still feels messy, patch reconnect-in-progress click handling next.
- If buffering still feels weak after live use, tune defaults based on evidence from real stalls rather than guessing.
