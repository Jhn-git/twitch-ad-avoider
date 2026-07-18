# Session 11: Startup Favorites Refresh Fix

Date: 2026-07-05

## What Happened

- User reported the Favorites list usually shows stale live/offline data until either the periodic auto-refresh interval ticks or they manually hit Refresh — annoying when they want to glance at the app and immediately see who's live.
- Found that `gui_qt/stream_gui.py` already had a one-shot "initial refresh on startup" mechanism (`_initial_refresh_timer`, a singleShot `QTimer` started with `.start(0)` in `_setup_refresh_timer()`), but it was gated behind the same `favorites_auto_refresh` config flag that controls the *periodic* recurring refresh.
- Checked the live `config/settings.json` and confirmed `"favorites_auto_refresh": false` — meaning the user has periodic auto-refresh turned off, which was also silently suppressing the one-time startup refresh they actually wanted. That's the root cause.

## Key Decisions

- Decoupled the concepts: "refresh once on startup so the list is current" is logically separate from "keep refreshing every N seconds forever." Made the initial refresh unconditional — it now always fires once on app startup regardless of the `favorites_auto_refresh` setting. The periodic recurring timer's behavior is untouched and still respects `favorites_auto_refresh` as before.

## Files Changed

- `gui_qt/stream_gui.py` — removed the `if self.config.get("favorites_auto_refresh", True):` guard around `self._initial_refresh_timer.start(0)` in `_setup_refresh_timer()`.

## Verification

- `./.venv/Scripts/python.exe -m py_compile gui_qt/stream_gui.py` — no syntax errors.
- `./.venv/Scripts/python.exe -m pytest tests/` — full suite still passes, 182 passed. Checked `tests/test_stream_gui_preview_logic.py` specifically since it explicitly sets `favorites_auto_refresh=False` in its test setup — confirmed this is safe because the dummy favorites manager returns an empty favorites list at GUI construction time, so the now-unconditional initial refresh just hits the harmless "no favorites saved" skip branch during those tests.
- **Not yet live-tested** — next app launch should confirm the Favorites list shows current live/offline status immediately on open, without needing to click Refresh.

## Things We Haven't Tried Yet

- Live-launching the app to visually confirm favorites populate with fresh status right away.

## Next Steps

- Launch the app once and check that favorites show correct live status immediately, without a manual refresh click.
