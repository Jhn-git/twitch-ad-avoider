# Session 18: Settings-Stream Overlay Fix, Close-Hang Deadlock Fix, And Auto-Collapse Panels

Date: 2026-07-10

## What Happened

Picked up right where session 17 left off ("we're back, let's knock out the issues") and worked through the deferred Settings/stream bug, then a new close-hang bug the user found, then a new feature request.

### 1. Settings page stopping/restarting the stream (deferred bug from session 17) — fixed

- Root cause confirmed by reading `gui_web/app.jsx`, `stream_manager.jsx`, `settings_view.jsx`, `video_stage.jsx`, `webapi.py`, `web_stream_service.py`: `App` in `app.jsx` rendered **either** `<SettingsView>` **or** `<StreamManager>` via a ternary — a true mount/unmount swap, not a CSS show/hide. `VideoStage` (child of `StreamManager`) owns the `<video>` element and the hls.js instance; opening Settings unmounted `StreamManager` → unmounted `VideoStage` → hls.js got destroyed → playback visibly stopped. Closing Settings remounted everything from scratch, which looked like a restart/rebuffer.
- Confirmed via code reading that the backend (Streamlink session in `WebStreamService`) never actually stopped — this was a pure front-end unmount/remount artifact, not a backend lifecycle bug.
- Fix (approved by the user via a plan-mode question — they picked "full-screen Settings, stream hidden" over a side-panel/PiP redesign): `App` now always renders `StreamManager`; `SettingsView` renders as a conditional overlay sibling instead of replacing it, styled with a new `.settings-overlay` CSS rule (`position: fixed; inset: 0; z-index: 50; background: var(--bg);`) so it still visually covers the whole screen like before.
- Verified in the browser (demo mode, static server + Playwright-style eval): tagged the stream `<div class="app-shell">` DOM node with a marker before opening Settings, confirmed the marker survived opening AND closing Settings (proving no remount), and confirmed the stream stayed "active" (`Stop Stream` button state) the whole time.
- This was already committed by the time we got to the close-hang bug (commit `1621721`), along with all of session 17's onedir/build-script/README changes.

### 2. App sometimes not responding when closing the window while watching a stream — fixed (two parts)

**Part A — the actual freeze/deadlock:**
- User reported the app hangs (Windows "Not Responding") sometimes when closing the window while a stream is active.
- Root cause: `window.events.closing` (registered in `main.py`) fires **synchronously on the UI thread**. It calls `api.shutdown()` → `WebStreamService.stop()`, which fires activity/stream-stopped events that call back into `evaluate_js()` to notify the JS side. On the WebView2 backend (`.venv/Lib/site-packages/webview/platforms/edgechromium.py`), `evaluate_js()` blocks on a semaphore waiting for an async JS continuation — but that continuation can only be delivered by the **same UI thread that is currently blocked waiting for it**. Self-deadlock. Only happens "sometimes" because it only triggers when a stream session is actually active at the moment of closing (idle-close skips this code path entirely).
- Fix: added a `self._shutting_down` flag to `TwitchViewerAPI` (`src/webapi.py`), set at the very start of `shutdown()`, and `_push()` (the single choke point all JS-push paths go through — `_add_activity`, `_on_stream_event`, favorites/settings pushes, everything) now no-ops once that flag is set. Confirmed via grep that every JS-push call site in `webapi.py` routes through `_push()`, so this closes off the whole deadlock class in one place, not just one call site.
- Added a regression test (`tests/test_webapi.py::test_shutdown_suppresses_js_push_to_avoid_ui_thread_deadlock`) asserting no `evaluate_js` calls happen once `shutdown()` has started, even if activity/stream events fire afterward.

**Part B — residual ~2 second stall after Part A:**
- After deploying Part A, user reported it now closes but still takes about 2 seconds — "slightly faster than before... still kinda slow imo."
- Cause: `WebStreamService.shutdown()` called `self.stop(join_timeout=2.0)`, which waits up to 2 seconds for the recording thread to notice `stop_event` and exit before returning — still blocking the UI thread for that stretch.
- Fix: `shutdown()` now calls `self.stop(join_timeout=0)`. The recording thread is a daemon thread and the process is exiting anyway, so there's nothing to gain from waiting on it during shutdown specifically (unlike a normal user-triggered "Stop Stream" click, where `stop()`'s default `join_timeout=1.0` is unchanged).
- User confirmed after redeploy: "thats working better."

**Important debugging note for future sessions:** the first time the user reported this hang, the deployed desktop exe (`C:\Users\<user>\Desktop\Jhn Apps\jhn-twitch-viewer\twitchadavoider.exe`) was still the *old* build from session 17 (00:02 timestamp) — the fix existed only in source and had never been rebuilt/redeployed. Always check the actual exe's file timestamp against when a fix was made before concluding a fix "didn't work" — rebuild + redeploy via `scripts/update-daily-exe.ps1` before re-testing.

### 3. New feature: auto-collapse panels after 10s idle while watching — implemented

User asked for the favorites rail, options rail, and activity drawer to auto-collapse after 10 seconds of inactivity while a stream is being watched, with a toggle setting defaulting to on.

- New persisted setting `auto_collapse_panels_enabled` (default `True`) added to `src/constants.py` (`DEFAULT_SETTINGS`) and `src/config_manager.py` (`_setting_validators()`), following the exact pattern of the existing `stream_manager_*` boolean settings. Added to `tests/test_config_validation.py`'s `test_boolean_validation` list and `gui_web/helpers.jsx`'s `demoApi()` settings object.
- New Settings UI field: **Settings → Interface → "Auto-collapse panels (10s idle)"** (`gui_web/components/settings_view.jsx`).
- Behavior implemented in `gui_web/components/stream_manager.jsx`: a `useEffect` that, only when `auto_collapse_panels_enabled` is true AND `state.stream?.active` is true, attaches `mousemove`/`mousedown`/`keydown`/`wheel`/`touchstart` listeners on `window` and arms a 10-second `setTimeout`. Any of those events resets the timer. When the timer fires uninterrupted, it collapses the left rail, right rail, and activity drawer via the existing `onUiState(...)` plumbing (same mechanism as the manual collapse buttons). Used a ref (`onUiStateRef`) to avoid tearing down/rebuilding the listeners on every unrelated parent re-render.
- Verified thoroughly in the browser (demo mode): (1) rails collapse after 10s idle while watching, with the setting on; (2) rails stay open indefinitely with the setting off; (3) a self-contained in-page async timing test proved activity genuinely resets the 10-second window — dispatched a `mousemove` at the 6s mark, confirmed panels were still open at the 12s mark (only 6s since the reset), then confirmed they collapsed at the ~17s mark (11s after the reset). This ruled out both "fires on a fixed schedule regardless of activity" and "never resets" as possible bugs.

## Important Files Changed (this session, on top of session 17's already-committed work)

- `gui_web/app.jsx`, `gui_web/components/settings_view.jsx`, `gui_web/index.html` — Settings-as-overlay fix (already committed in `1621721`).
- `src/webapi.py` — `_shutting_down` flag; `_push()` no-ops during shutdown.
- `src/web_stream_service.py` — `shutdown()` uses `join_timeout=0` instead of `2.0`.
- `src/constants.py`, `src/config_manager.py` — new `auto_collapse_panels_enabled` setting + validator.
- `gui_web/components/stream_manager.jsx` — auto-collapse inactivity timer implementation.
- `gui_web/components/settings_view.jsx` — new Settings field for the toggle.
- `gui_web/helpers.jsx` — demo-mode settings object updated with the new key.
- `tests/test_webapi.py` — new shutdown/deadlock regression test.
- `tests/test_config_validation.py` — new setting added to the boolean-validation test list.

## Current Git State

- Commit `1621721` (already on `main` before this session's later work) contains: the Settings-overlay fix, and all of session 17's onedir/build-script/README changes.
- **Not yet committed:** the close-hang fix (`src/webapi.py`, `src/web_stream_service.py`, `tests/test_webapi.py`) and the auto-collapse feature (`src/constants.py`, `src/config_manager.py`, `gui_web/components/stream_manager.jsx`, `gui_web/components/settings_view.jsx`, `gui_web/helpers.jsx`, `tests/test_config_validation.py`). All of it is built, deployed to the desktop app, and confirmed working by the user — just needs a commit.
- Full test suite (`python -m pytest tests/`) passes: 101/101.
- The desktop app (`C:\Users\<user>\Desktop\Jhn Apps\jhn-twitch-viewer\`) has been rebuilt and redeployed three times this session via a real (non-dry-run) `scripts\update-daily-exe.ps1` — each run correctly replaced only `twitchadavoider.exe`/`_internal/`/`launch.bat`, backed up the previous versions as `*.previous`, and left `config/`, `clips/`, `logs/`, `temp/` untouched. This is good real-world confirmation that last session's rewrite of that script is solid.

## Things We Haven't Tried Yet / Still Pending

1. **Commit the uncommitted work** described above — it's tested and deployed but not yet committed to git.
2. **The old ~27GB `C:\Users\<user>\Desktop\Jhn Apps\jhn-twitch-viewer.previous\` folder from session 17 is still sitting on disk**, unchanged (confirmed still present, still ~27GB). The user already said back in session 17 they don't care if it's deleted — it's just never actually been deleted. Safe to delete whenever convenient.
3. Each real run of `update-daily-exe.ps1` this session left small `*.previous` files/folders (`twitchadavoider.exe.previous`, `_internal.previous`, `launch.bat.previous`) inside the live `jhn-twitch-viewer\` folder itself — these are tiny (part of a normal build, not user data) and get overwritten on each subsequent update, so no action needed, just noting they exist if they look unfamiliar.
4. **A real (non-dry-run) `scripts\release.ps1` GitHub release has still never been done** — only `-DryRun` has ever been tested. If a public release is wanted, that's the next thing to actually run for real.
5. The `streamlink` auto-upgrade step inside `update-daily-exe.ps1` failed with a warning each of the three times it ran tonight ("streamlink upgrade failed: System.Management.Automation.RemoteException - continuing with installed version") but didn't block the build. Not investigated — streamlink still works fine with the installed version, but worth a look if streamlink-related stream-start issues ever come up.
6. **New known issue, not yet investigated:** scrubbing/seeking backward in the video player while watching a stream is "very buggy and not useable" (user's words). Reported at the very end of the session, no investigation done yet. Likely relevant starting points for next time: `gui_web/components/video_stage.jsx` (owns the `<video>` element, hls.js instance, and its config — `lowLatencyMode: true`, `liveSyncDurationCount: 3`), and `src/web_stream_service.py`'s local HLS proxy (`_proxy_playlist`/`_proxy_resource`, the `/playlist/...` and `/resource/...` endpoints that rewrite Twitch's HLS playlists for WebView2). Since this is a low-latency live HLS setup, seeking backward may be fighting against a deliberately small live buffer window and/or the proxy's playlist rewriting — needs actual investigation, nothing ruled in or out yet.
