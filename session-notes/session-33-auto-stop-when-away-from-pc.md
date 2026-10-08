# Session 33: Auto-Stop Streams When Away From the PC

Date: 2026-09-21

## What Happened

User wanted streams to auto-stop after being away from the PC for ~5 minutes, to
avoid wasted bandwidth/CPU from a forgotten stream. This went through two design
iterations in one session - the first shipped, then a real usage bug forced a
rework of the underlying trigger.

### 1. Design exploration (plan mode)

- Two parallel Explore agents mapped the stream-stop path (`WebStreamService`
  only ever holds one active session - `stop()` already **is** "stop
  everything"), the JS↔Python bridge/push pattern (`TwitchViewerAPI._push` →
  `window.evaluate_js`), settings/config conventions, and confirmed **no**
  existing OS-level idle-input code or `pywin32`/`ctypes` usage anywhere in the
  repo.
- Original idea (true OS-wide idle-input detection via `GetLastInputInfo`)
  raised a real problem: it can't tell "away from keyboard" apart from
  "listening while cleaning, not touching anything." Solving that would need
  reliable per-stream mute-state tracking, which the app doesn't have (the
  video's `muted` flag is only ever toggled internally for the clip editor).
- User proposed stopping on **window focus loss** instead - walking away
  without switching windows leaves the app focused, so it naturally avoids the
  cleaning-while-listening case. Confirmed pywebview exposes **no**
  focus/blur window events on any platform, but plain JS `window.blur`/`focus`
  DOM events fire reliably for a WebView2-hosted page and needed zero new
  dependencies.
- User explicitly accepted the resulting gap (window stays focused + genuinely
  AFK for hours ⇒ never auto-stops) as worth the simplicity.

### 2. First implementation - focus-loss only

- New settings: `auto_stop_on_unfocus_enabled` (default `True`),
  `auto_stop_on_unfocus_seconds` (default `300`) in `src/constants.py` +
  validators in `src/config_manager.py`.
- `gui_web/components/stream_manager.jsx`: a `window.blur`/`focus`-driven
  `setTimeout` that called the existing local `stopStream()` (same path as the
  manual Stop button) and showed a toast, gated on `isWatching` and the new
  setting, using a ref pattern (mirroring the existing `onUiStateRef`) so
  re-renders didn't drop an in-flight timer.
- Settings UI fields added under "Interface" next to the existing
  `auto_collapse_panels_enabled` 10s-idle toggle; `demoApi()` in
  `gui_web/helpers.jsx` got matching defaults.
- Tests: `test_config_validation.py` (bool + range validation),
  `test_web_ui_contract.py` (source-assertion test for the wiring, matching
  this repo's no-JS-test-runner convention).
- Verified live in the browser demo harness (`gui-web-demo`, `?demo`):
  confirmed sustained blur → stop + toast; blur-then-refocus-before-timeout →
  untouched; settings fields render/save correctly. All via tightly-batched
  `browser_batch` calls to stay inside the demo's ~60s synthetic clip window -
  an earlier, more loosely-paced manual pass gave a false read because the
  demo clip ended naturally mid-test, unrelated to the feature.
- Saved a new memory ([[feedback_rebuild_daily_exe_after_changes]]) and ran
  `scripts/update-daily-exe.ps1` per the user's explicit go-ahead.

### 3. Real-world bug: focus-loss alone was too aggressive

User reported: streams still auto-stopped while they were **actively clicking
around with the mouse in another (unfocused) window** - i.e. genuinely at the
PC, just not focused on this app. Focus-loss alone can't distinguish "busy
elsewhere" from "actually gone," which defeats the point.

**Fix - combine both signals.** Moved the decision from frontend-only to a
frontend-poll / backend-decides split:

- New `src/system_idle.py`: `get_system_idle_seconds()` via
  `ctypes.windll.user32.GetLastInputInfo` + `GetTickCount` (both 32-bit,
  wraparound-safe via a pure `_idle_millis()` helper tested independently of
  ctypes). Returns `0.0` on non-Windows so nothing ever auto-stops there.
- `src/webapi.py`: new `check_auto_stop_on_unfocus()` bridge method - only
  stops (and pushes the `__onToast` message, reusing `WebStreamService.stop()`
  which already pushes `__onStreamEvent` internally) once
  `get_system_idle_seconds() >= auto_stop_on_unfocus_seconds`, gated on the
  existing enabled setting and an active session. Channel name is captured
  **before** calling `stop()` since the fake/real stream service both clear it
  on stop.
- `gui_web/components/stream_manager.jsx`: the old timer/ref machinery was
  torn out entirely. The frontend now just starts a 5s `setInterval` calling
  `api.check_auto_stop_on_unfocus()` on blur, clears it on focus - it no
  longer makes the stop decision itself.
- Settings labels updated for the new semantics: "Auto-stop when away from
  PC" / "Away timeout (seconds)" (same setting keys, no migration needed).
- Why this fixes it without reopening the cleaning-while-listening problem:
  any input anywhere on the system resets `GetLastInputInfo`'s clock
  regardless of which window is focused, so being busy in another app keeps
  idle time near zero and the poll never trips. True AFK (no input anywhere)
  still only triggers while unfocused, so the original "window stays focused
  while just watching" protection is untouched.

### 4. Tests / verification (second pass)

- `tests/test_system_idle.py` (new): tick-count wraparound math, non-Windows
  returns `0.0`.
- `tests/test_webapi.py`: four new cases on `check_auto_stop_on_unfocus` -
  busy-elsewhere-never-stops, truly-idle-stops-and-toasts (asserts the
  channel name appears in the pushed toast), disabled-setting-is-a-noop,
  nothing-playing-is-a-noop. All mock `get_system_idle_seconds` directly
  rather than touching real ctypes, keeping the suite deterministic on any
  machine.
- `tests/test_web_ui_contract.py` rewritten for the new poll-only wiring
  (`api.check_auto_stop_on_unfocus()`, `startPolling`/`stopPolling` on
  blur/focus) instead of the old timer/stop-ref assertions.
- Full suite: **232/232 passing**. Black/flake8/mypy clean on every touched
  file (one line-length fix needed in `src/constants.py`).
- Structural-only re-check in the browser demo harness (demo mode has no real
  backend, so its `check_auto_stop_on_unfocus` stub always returns
  `stopped: false` - confirmed the poll fires repeatedly on blur without
  errors and stays inert, which is the correct/expected demo behavior since it
  can't exercise real system idle time).
- Rebuilt the daily desktop exe again after the fix (per the new standing
  memory preference), stopping the previously-running instance cleanly.

## What Was NOT Done

- **Not committed.** Everything above (both the v1 focus-only version and the
  v2 focus+idle rework) is still uncommitted in the working tree - `git
  status` shows 9 modified files plus two new files (`src/system_idle.py`,
  `tests/test_system_idle.py`). Nothing has been pushed either.
- **No real-world, real-clock validation of the actual fix.** The
  busy-in-another-window scenario that prompted the rework was only verified
  via unit tests with mocked idle time (`get_system_idle_seconds` patched) and
  by re-checking the frontend's structural wiring in demo mode - neither
  exercises real `GetLastInputInfo` over real wall-clock minutes. Worth a
  genuine day-to-day check: alt-tab away and stay busy elsewhere for 5+
  minutes (should stay playing), then actually walk away for 5+ minutes
  (should stop).
- **No release/MSI.** Only the local daily desktop exe was rebuilt and
  redeployed, twice (once per design iteration) - no version bump, no GitHub
  release.
- **Single shared threshold.** `auto_stop_on_unfocus_seconds` now means "how
  long the window must be both unfocused *and* system-idle." There's no
  separate control for "how long unfocused" vs. "how long idle" - fine for
  now, but a future ask could want them split.
- **The originally-accepted gap is still there by design**: window stays
  focused the whole time (e.g. asleep at the desk with the app in front) ⇒
  never auto-stops, regardless of real idle time. User explicitly signed off
  on this trade-off before v1 and it wasn't revisited during the v2 fix, since
  the fix only changed *what counts while unfocused*, not the focused case.
