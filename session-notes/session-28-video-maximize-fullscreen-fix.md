# Session 28: Video Maximize / Fullscreen Fix

Date: 2026-07-20

## What Happened

User shared a screenshot of the Stream Manager showing the video paused mid-stream with the channel name/title bar still visible above the player and the scrub bar/clip buttons still visible below it, and said the "maximize button" wasn't fully maximizing the video. Investigated in plan mode first.

### 1. Root cause

There was no custom maximize/fullscreen feature in the app at all. The video element used the browser's native HTML5 `controls` bar (`<video ref={videoRef} controls playsInline />` in `video_stage.jsx`), which includes a built-in fullscreen icon. Clicking it calls the standard `video.requestFullscreen()` Fullscreen Web API - but pywebview's WebView2 host on Windows doesn't act on that call, so nothing visually changes. The video stays at its normal in-flow size, and the app's own `.channel-meta` (top) and `.scrub-row`/`.stage-actions` (bottom) - ordinary flow siblings of the player, not descendants of it - just stay exactly where they were.

### 2. First fix: in-app "theater mode" (frontend only)

Asked the user to choose between (a) an in-app theater mode that stays within the existing OS window (title bar still visible), or (b) true OS-level fullscreen requiring pywebview/Python changes too. User picked (a) first, so implemented:

- New `maximize`/`minimize` icons in `gui_web/components/icons.jsx`.
- `video_stage.jsx`: `theaterMode` state, a custom toggle button overlaid top-right on `.player-shell`, an Escape-key handler, and conditional rendering that unmounts `.channel-meta`, `.scrub-row`, and `.stage-actions` while active.
- `gui_web/index.html`: `.stage.theater-mode` becomes `position: fixed; inset: 0` (verified no ancestor sets `transform`/`filter`/`contain` that would confine it to a grid cell), `.player-shell` grows to fill it, and `object-fit: contain` was added to `.player-shell video` so the video letterboxes instead of stretching once the container is no longer a strict 16:9 box.

Verified via the browser-only demo harness (`gui-web-demo` + `?demo` mode, see session-27): button renders, clicking it applies the fixed-overlay class and unmounts the chrome, Escape and re-clicking both restore the layout, no console errors.

### 3. Second fix: real OS-level fullscreen

User tested the in-app version live and reported it was "redundant" with the native player's own fullscreen icon, and that the Windows taskbar and the app's own title bar were still visible - i.e. option (b) was actually needed after all, not just (a). Added the OS-level half on top of the existing theater-mode work rather than replacing it:

- `src/webapi.py`: new `toggle_fullscreen()` method on `TwitchViewerAPI`, exposed to JS as `pywebview.api.toggle_fullscreen()`, calling `self._window.toggle_fullscreen()`. Confirmed by reading the installed `webview` package source (`platforms/winforms.py`) that this does a real borderless-fullscreen on Windows: removes `FormBorderStyle`, resizes to the monitor's full `Screen.Bounds` (covering the taskbar), and there's no built-in Escape-key binding in that backend to conflict with our own Escape handler.
- `video_stage.jsx`: both the maximize button and the Escape handler now go through one `setTheaterState(next)` helper that flips `theaterMode` and calls `window.pywebview?.api?.toggle_fullscreen?.()?.catch?.(() => {})` in the same step, so the CSS state and the real OS fullscreen state can never drift out of sync (each is a plain toggle, so it matters that it's called exactly once per transition, from exactly one place).

User confirmed this works in the real running app.

## Key Decisions

- Asked the user up front (via `AskUserQuestion`) which scope they wanted rather than guessing, since in-app-only vs. OS-level fullscreen is a real fork with different blast radius (frontend-only vs. touching `main.py`/`webapi.py`). Turned out the user's first answer wasn't actually sufficient once they saw it running - worth remembering that "theater mode within the window" and "real fullscreen" can look similar in description but feel very different in practice, so a quick real-app look before considering this kind of thing "done" is worth it even after an explicit up-front choice.
- Did not touch or remove the native `<video controls>` fullscreen icon - flagged as a follow-up (see below) rather than done reactively, since removing/suppressing native controls has its own UX tradeoffs (loses the native play/pause/volume/time bar too, since there's no custom control bar to replace it with) worth a deliberate look rather than a quick patch.
- Kept `toggle_fullscreen()` as a bare toggle (matching pywebview's own API) rather than adding explicit enter/exit methods, since the JS side already has a single source of truth (`theaterMode`) driving both the CSS class and the one-call-per-transition OS toggle - an explicit set-state method would have been redundant complexity for no behavior difference given today's usage.

## Files Changed

- `gui_web/components/icons.jsx` - added `maximize`/`minimize` icon paths.
- `gui_web/components/video_stage.jsx` - `theaterMode` state; `setTheaterState`/`toggleTheaterMode`; Escape-key handler; custom `.theater-toggle` button; conditional rendering of `.channel-meta`/`.scrub-row`/`.stage-actions`; `pywebview.api.toggle_fullscreen()` call wired into both the button and Escape paths.
- `gui_web/index.html` - `.theater-toggle` button styling; `.stage.theater-mode`/`.stage.theater-mode .player-shell` fixed-overlay CSS; `object-fit: contain` added to `.player-shell video`.
- `src/webapi.py` - new `toggle_fullscreen()` bridge method calling `self._window.toggle_fullscreen()`.

## Current Progress

Both the in-app theater mode and the OS-level fullscreen call are implemented, verified (theater mode via the demo harness; OS-level fullscreen via the user's own real-app test), and already committed - `git log` shows commit `4753f88` ("feat: Implement theater mode toggle and enhance demo server for realistic playback testing") already contains all of this session's `gui_web/`/`src/webapi.py` changes, via the same automatic checkpoint mechanism noted in session-27's notes. `git status` is clean as of the end of this session except for this session-notes file and the `TODO.md` edits made just now, which have not been committed (per standing instructions, only commit when explicitly asked).

## Things We Haven't Tried Yet / Still Pending

1. **Redundant native fullscreen icon** - the user's own follow-up ask, now in `TODO.md`'s Backlog. The browser's native `<video controls>` bar still shows its own fullscreen icon, which does nothing useful (same root cause as this session's original bug) and sits right next to our working maximize button - confusing to have two, one broken. Not yet investigated: whether pywebview/WebView2 exposes a way to suppress just that one native control (there's precedent for suppressing individual native controls - see the existing `.player-shell video::-webkit-media-controls-timeline { display: none; }` rule - so a similar `::-webkit-media-controls-fullscreen-button` rule is a promising first thing to try), versus dropping the `controls` attribute entirely and building a full custom control bar (bigger job, loses native play/pause/volume/time for free). User explicitly called this "more cosmetic, like some of the other todos" - not urgent.

Both items below were flagged as open questions at the end of this session and the user confirmed the same day, from real firsthand use, that neither is actually a problem - recorded here so a future session doesn't re-flag or re-test either unprompted:

- **Real-stream behavior**: user confirmed the feature "works as expected just fine, no complaints" on a real live stream, not just the local demo clip.
- **Multi-monitor behavior**: user confirmed it "works fine" - tested firsthand on their own multi-monitor setup.

## Skills

No new skill created. The existing `pywebview-gui-test` skill's Tier 2 (browser-only demo mode) and the `127.0.0.1` vs `localhost` cache-partition trick (used today to dodge a stale cached `icons.jsx` mid-session - confirmed via a `cache: 'no-store'` fetch that the file on disk was already correct, so the stale copy was purely a browser HTTP-cache artifact, not a real bug) both worked well and are worth remembering for next time a demo-mode edit doesn't seem to take effect after a source edit. Not significant enough on its own to warrant a dedicated new skill, but could be worth a one-line addition to `pywebview-gui-test`'s "gotchas" section if this recurs.
