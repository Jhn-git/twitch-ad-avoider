# Session 06: Favorites Selection Stream Preview — Feature Added, Resize Bug Open

Date: 2026-07-03

## What Happened

- User asked for a live preview (thumbnail + title) to appear in the "Stream" panel's empty lower area when a favorite is highlighted in the Favorites list.
- Explored the codebase (PySide6/Qt6 app) and confirmed: no existing image-fetching code, only live/offline batch checks via Twitch's public GQL API (`src/status_monitor.py`), and an existing `QObject` + `QThread` worker pattern (`gui_qt/controllers/stream_controller.py`) to reuse for async work.
- Planned and implemented the feature (see "Files Changed"), then iterated on a follow-up request to make the thumbnail size responsive instead of a fixed 280×158 pixel box, since the user explicitly dislikes hardcoded sizes and wants it to always stay landscape (16:9).
- Two real bugs were found and fixed along the way (see "Key Decisions"/"Bugs Fixed").
- **A third bug is currently open and unresolved**: in the real running app, resizing the window larger causes the preview thumbnail to visibly overflow/distort — image runs off the right edge of the panel and looks stretched. This did NOT reproduce in an offscreen synthetic test harness (see "Open Bug" below for full detail). User interrupted mid-investigation to have this session-notes file written before compacting the conversation.

## Key Decisions

- Kept the preview fetch fully async (new `StreamPreviewController` in `gui_qt/controllers/preview_controller.py`, mirroring `ClipWorker`/`StreamController`'s QThread pattern) rather than following the existing synchronous `StatusMonitor.check_channels()` precedent, since this fires on every single list-selection change (not a periodic timer) and includes an image download.
- Used a generation counter + 250ms debounce timer in `StreamPreviewController` to avoid stale-selection races (e.g. arrow-keying rapidly through the favorites list) and request spam.
- Added a "Show stream preview" settings toggle (default on) since this adds a network round-trip per click.
- Decided against caching fetched previews — small favorites list, manual-trigger-only, and a "live" preview should always be fresh.
- For the responsive-size follow-up: chose to make the thumbnail fill 100% of the panel's available width and derive height from a fixed 16:9 ratio, rather than picking a bigger fixed pixel size. Bumped the requested Twitch thumbnail resolution from 320×180 to 640×360 so scaling up on wide panels doesn't look blurry.
- Attempted `QSizePolicy` + `heightForWidth()` (the "proper" Qt way to do width-driven height) first, but abandoned it — mixing `heightForWidth` into a plain `QVBoxLayout` alongside non-HFW-aware sibling widgets (buttons) produced a broken layout (label locked to a stray 640px width regardless of actual panel width). Switched to manually pinning height in `resizeEvent` via `setFixedHeight()` instead, which is more predictable but has its own new bug (see below).

## Bugs Fixed

1. **Config validation regression (self-inflicted, caught before shipping)**: Adding `"show_stream_preview": True` to `DEFAULT_SETTINGS` in `src/constants.py` without also adding a matching `elif key == "show_stream_preview":` branch in `ConfigManager._validate_setting()` (`src/config_manager.py`) caused **the entire settings.json to silently fail validation and reset to defaults on every app launch** — any key in `DEFAULT_SETTINGS` without a validator branch falls through the `if/elif` chain, implicitly returns `None`, and `_validate_settings()` treats that as `False` for the whole file. Fixed by adding the missing branch. Added a regression test (`tests/test_config_validation.py::test_every_default_setting_has_a_validator_branch`) that asserts every `DEFAULT_SETTINGS` key validates successfully — this test was verified to actually catch the bug (confirmed via `git stash` on just `config_manager.py` and re-running).
2. **Blanket `taskkill /F /IM python.exe`**: while testing, killed *all* running Python processes system-wide instead of the one test instance, which also terminated an unrelated PID (31304) the user had running for something else. Already flagged to the user in-conversation. Lesson: always target the exact PID (`ps aux | grep python` first) rather than `/IM` blanket kills, even when "it's probably just my test process."

## Files Changed

- New: `src/stream_preview.py` — `fetch_stream_preview_info()` (GQL query for title + `previewImageURL`, now requested at 640×360) and `fetch_image_bytes()`, both defensive (never raise, degrade to offline/None on any error).
- New: `gui_qt/controllers/preview_controller.py` — `PreviewWorker` (QObject, runs on a QThread) + `StreamPreviewController` (debounce + generation-counter race guard, public signals `preview_ready`/`image_ready`/`image_failed`).
- New: `tests/test_stream_preview.py` — 6 tests for the GQL/image fetch functions (monkeypatched `requests`).
- Edit: `gui_qt/components/chat_panel.py` — added `_LandscapePreviewLabel` (custom `QLabel` subclass, see "Open Bug") and new `ChatPanel` methods: `show_preview_loading()`, `set_preview_image(bytes)`, `set_preview_title(str)`, `set_preview_offline()`, `set_preview_image_unavailable()`, `clear_preview()`. `set_channel("")` now also clears the preview.
- Edit: `gui_qt/stream_gui.py` — constructs `StreamPreviewController` in `_create_controllers()`; wires its signals in `_connect_signals()`; `_on_favorite_selected()` now calls `_request_preview_for_selection()`; preview is cleared while actively streaming (`_on_stream_started`) and re-requested after a stream ends/errors (`_on_stream_finished`/`_on_stream_error`); `_cleanup()` calls `preview_controller.clear()`.
- Edit: `src/constants.py` — added `"show_stream_preview": True` to `DEFAULT_SETTINGS`.
- Edit: `src/config_manager.py` — added the missing `show_stream_preview` validator branch (bug fix #1 above).
- Edit: `gui_qt/components/settings_tab.py` — new `show_stream_preview_check` `QCheckBox` in the Favorites Settings group, wired to load/save.
- Edit: `gui_qt/styles/dark.qss` / `gui_qt/styles/light.qss` — added `QLabel#streamPreviewImage` / `QLabel#streamPreviewTitle` styling.
- Edit: `tests/test_config_validation.py` — added the regression test from bug fix #1.

## Verification So Far

- `pytest tests/` (excluding two pre-existing, unrelated `test_katch_*` failures caused by a missing `katch` module — confirmed pre-existing, not touched this session): **162 passed**.
- Offscreen Qt harness (`QT_QPA_PLATFORM=offscreen`, script lived only in the session scratchpad temp dir, **not committed, will not exist in a future session** — recreate if needed) drove the real `ChatPanel` + `StreamPreviewController` against the **live** Twitch GQL API:
  - Live channel (`jg_darhk`): real title + real thumbnail fetched and rendered correctly.
  - Offline/invalid channel: correctly showed the "Offline" placeholder, no crash.
  - Resize test at panel widths 300/500/900px (**after** explicitly calling `panel.show()` first — see gotcha below): label width tracked panel width proportionally, height stayed locked to 16:9, pixmap matched label size exactly in all three cases. This appeared to fully validate the responsive-resize fix.
- **However**, live-testing in the actual running app (`python main.py`, real window, user resizing/maximizing by hand) surfaced a real bug the offscreen harness missed — see below.

## Open Bug: Thumbnail Overflows/Distorts on Real-Window Resize

**Symptom (from user's screenshots, real app)**: at most window sizes the thumbnail looks correct and fills the panel width nicely. But in at least one state (window maximized very wide), the image visibly **runs off the right edge of the "Stream" panel** — extending past where the panel/groupbox border should be — and looks stretched/distorted rather than cleanly filling a landscape box. The other buttons above it (Open Channel/Open Chat/Open Clips Folder) also appear stretched unusually wide in that same screenshot, suggesting the whole `ChatPanel` column may have grown wider than the grid's intended 40/60 favorites/chat split, not just the image label in isolation.

**Why the offscreen test didn't catch it**: that harness created `ChatPanel` as a **standalone top-level widget** (`ChatPanel()` with no parent, then `.show()` directly), not nested inside the real app's `QGridLayout` (`gui_qt/main_window.py`, column stretch 2:3) → `QVBoxLayout` (central widget) → `QTabWidget`. The bug likely only manifests under that deeper nesting, or specifically during a live interactive resize/maximize (many rapid `resizeEvent`s in quick succession) rather than a single discrete `panel.resize()` call in a script.

**Current implementation** (`gui_qt/components/chat_panel.py`, `_LandscapePreviewLabel`):
```python
def __init__(self, parent=None):
    ...
    self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    self.setMinimumWidth(160)
    ...
    self._sync_height()

def resizeEvent(self, event) -> None:
    super().resizeEvent(event)
    self._sync_height()
    self._apply_scaled_pixmap()

def _sync_height(self) -> None:
    target_height = round(self.width() / self._ASPECT_RATIO)
    if self.height() != target_height:
        self.setFixedHeight(target_height)   # <-- calls resize() reentrantly from inside resizeEvent

def _apply_scaled_pixmap(self) -> None:
    ...
    scaled = self._source_pixmap.scaled(self.width(), self.height(), Qt.AspectRatioMode.KeepAspectRatio, ...)
    self.setPixmap(scaled)
```

**Leading hypotheses (untested against the real app yet)**:

1. **Reentrant `setFixedHeight()` inside `resizeEvent` racing with layout settlement.** Calling `setFixedHeight()` from within the label's own `resizeEvent` changes `minimumHeight`/`maximumHeight` and triggers another geometry/layout pass. Nested inside a `QGridLayout` → `QVBoxLayout` → `QTabWidget`, this reentrant trigger may not settle synchronously the way it appeared to in the flat, standalone offscreen test — `self.width()` read at the top of `_apply_scaled_pixmap()` could be a transient/stale value mid-layout-pass, producing a pixmap scaled to a size that doesn't match where the label actually ends up once layout fully settles. `KeepAspectRatio` itself can't produce distortion (it always preserves source AR within the target box), so visible "stretching" more likely means the **label's own rectangle** grew disproportionately (see hypothesis 2), with the correctly-proportioned pixmap just being displayed inside an incorrectly-sized/positioned label.
2. **`QSizePolicy.Expanding` horizontally, combined with default `QLabel.sizeHint()` returning the currently-held pixmap's size**, could be feeding an ever-growing size hint back into the parent `QGridLayout` across successive resize events during an interactive drag/maximize (each pass's sizeHint reflects the previous pass's scaled pixmap, one frame behind the real target size) — worth checking whether overriding `sizeHint()`/`minimumSizeHint()` on `_LandscapePreviewLabel` (to return something width-independent of the held pixmap, as was tried earlier and reverted when abandoning `heightForWidth`) is still needed even without `heightForWidth`, purely to stop `QLabel`'s default pixmap-driven `sizeHint()` from feeding back into the grid layout's column-width negotiation.
3. Possible that the **grid layout's column-stretch (40/60 favorites/chat split in `main_window.py`)** doesn't actually cap `ChatPanel`'s width the way assumed, and an `Expanding`-policy child inside it can legitimately push the whole column wider than its stretch-factor share once its own preferred size grows past some threshold — i.e. this might not be a resize *event ordering* bug at all, but a **`QSizePolicy`/stretch-factor interaction** bug (Expanding widgets can request more than their stretch share; `QGridLayout` stretch factors only govern how *extra* space is distributed, not a hard cap).

**Things we haven't tried yet**:

- Reproducing the distortion in the offscreen harness by nesting `ChatPanel` inside an actual replica of the real layout (`QGridLayout` with 2:3 stretch inside a `QVBoxLayout` inside a `QTabWidget`, matching `main_window.py` exactly) rather than as a standalone top-level widget — needed to get a reliable, scriptable repro before trying more fixes blind.
- Simulating an *interactive drag-resize* (many rapid resize events in succession, as happens when a user drags a window edge or hits maximize) rather than a single discrete `.resize()` call — the bug may specifically be about event-ordering during rapid successive resizes, not steady-state at any single size.
- Overriding `sizeHint()`/`minimumSizeHint()` on `_LandscapePreviewLabel` again (this time *without* also re-adding `heightForWidth`/`hasHeightForWidth`) to decouple the label's reported preferred size from the currently-held pixmap's resolution — this was removed when the `heightForWidth` approach was abandoned, but may independently be needed to stop feedback into the grid layout.
- Deferring the pixmap rescale to the *next* event-loop tick (`QTimer.singleShot(0, self._apply_scaled_pixmap)`) instead of doing it synchronously inside `resizeEvent`, so it always reads the label's fully-settled post-layout size rather than a possibly-transient mid-resize value.
- Alternative architecture: move the aspect-ratio logic up to `ChatPanel.resizeEvent()` itself (which already knows the group box's real content width via `self.contentsRect()`), and have it explicitly command the label's height in one atomic step, rather than having the label try to self-manage via its own `resizeEvent`/`setFixedHeight` reentrancy.
- Have NOT yet reproduced this via computer-use / driving the real running app window directly — attempted `request_access` for the dev script's window several times (tried `"TwitchAdAvoider - Stream Manager"`, `"TwitchAdAvoider"`, `"Stream Manager"`, `"Python"`) and it only matches installed/Start-Menu-registered applications, not an ad-hoc `python main.py` window. No workaround found yet for driving the real app via computer-use; relied on the user's manual screenshots instead. Worth asking the user directly for the exact process/window name computer-use should target, if this comes up again.

## Next Steps

1. Build a more faithful offscreen repro (real nested layout, simulated rapid interactive resize) to reliably reproduce the overflow/distortion before attempting another fix.
2. Try the "defer rescale to next tick" and/or "move aspect logic to `ChatPanel.resizeEvent`" approaches from the list above; re-verify with the user's help live in the running app since the offscreen harness has already been shown to miss at least one real-layout-only bug.
3. Once genuinely fixed, re-run the full test suite and get explicit user confirmation via live screenshots at multiple window sizes (small, default, maximized) before considering this closed.

## Follow-Up Investigation (Same Day, After Compaction) — Fix Applied, Root Cause Still Unconfirmed

Resumed via plan mode. An Explore agent mapped the exact real nesting (`gui_qt/main_window.py`'s `QGridLayout` with `setColumnStretch(0, 2)` / `setColumnStretch(1, 3)`, `ChatPanel` at row 1 col 1, no `QSplitter` anywhere, no other `heightForWidth` usage in the app). A Plan agent then proposed a theory: `_LandscapePreviewLabel` never overrides `sizeHint()`/`minimumSizeHint()`, so `QLabel`'s default (which tracks the *currently held pixmap's size*) feeds back into `QGridLayout`'s two-phase sizing (minimums satisfied before the 2:3 stretch is applied), causing the column's effective minimum to ratchet upward across a continuous drag's many resize events.

**Applied the fix** (`gui_qt/components/chat_panel.py`, `_LandscapePreviewLabel`): added
```python
def sizeHint(self) -> QSize:
    width = max(self.minimumWidth(), 1)
    return QSize(width, round(width / self._ASPECT_RATIO))

def minimumSizeHint(self) -> QSize:
    return self.sizeHint()
```
so the label's reported size is always derived from its constant `minimumWidth()` (160), never from the held pixmap. Added `QSize` to the `PySide6.QtCore` import.

**Could not confirm this is the actual root cause.** Before committing to the theory, built increasingly faithful offscreen repros to test it:
1. Real `MainWindow` + real `ChatPanel` + a bare `QWidget()` stub for the favorites column, 40 incremental resize steps from 900→1900px with `app.processEvents()` after each — ratio held at exactly 0.600 throughout, **even with the fix disabled**.
2. Same, but with a single huge jump (900→3840px, simulating a maximize click) — same result, ratio exactly 0.600, fix disabled.
3. Same, but batching multiple `resize()` calls with NO `processEvents()` between them (to simulate events queuing up faster than layout can settle) — same result.
4. Swapped the bare stub for the **real** `FavoritesPanel` (which has genuine minimum-width buttons/list, unlike an empty stub) — at small window widths the ratio is correctly *below* 60% (favorites' real minimum forces it wider than its stretch share, squeezing chat panel — normal, expected Qt behavior, not a bug), and converges to exactly 0.600 once both columns' minimums are satisfied. Never exceeds 0.600.
5. Added the real `StreamActions` (row 0) and `StatusDisplay` (row 2) widgets and used a real `window.showMaximized()` call instead of `resize()` — still exactly 0.600, no overflow, fix disabled.

In every one of these — using the actual production `MainWindow`/`FavoritesPanel`/`StreamActions`/`StatusDisplay`/`ChatPanel` classes, multiple resize patterns, and a real maximize call — the grid's 2:3 stretch ratio held perfectly, **with or without the sizeHint fix**. Also directly verified (separate probe script) that `setFixedHeight()` updates `self.height()` synchronously within the same `resizeEvent` call for this widget — so the "stale self.height() read in `_apply_scaled_pixmap` after `setFixedHeight`" theory considered along the way is also not it.

**Conclusion**: the sizeHint/minimumSizeHint fix is being kept — it removes a genuine anti-pattern (a `QLabel`'s reported preferred size silently tracking whatever pixmap it currently displays is fragile regardless of whether it's this specific bug), is fully covered by a passing regression test (`tests/test_chat_panel_preview_resize.py::test_preview_label_size_hint_is_independent_of_held_pixmap`), and cannot make anything worse. But it is **not confirmed to be the fix for the originally-reported overflow/distortion** — five different offscreen repro attempts, including ones using the complete real widget hierarchy, failed to reproduce the bug at all, with or without the fix in place.

**Leading remaining hypothesis**: the bug may be specific to *native* Windows interactive window-border dragging, which runs through a nested win32 message pump separate from Qt's normal event loop — this is a documented class of Qt/Windows quirk where posted events (like the `LayoutRequest` that `setFixedHeight()`/`updateGeometry()` schedules) can lag or get starved for the duration of the drag in a way that a scripted `.resize()` + `.processEvents()` cannot replicate, since scripted resizes always fully flush the event queue between steps. If true, this may present as a **transient rendering artifact** during the drag itself (an OS-cached backing-store bitmap being stretched while Qt's own relayout/repaint hasn't caught up) rather than a persistent logical layout bug — which would also explain why it's hard to catch outside of a live screenshot at exactly the wrong moment.

**Also added `tests/test_chat_panel_preview_resize.py`** (new file): a fast, meaningful unit test for the sizeHint invariant (passes/fails correctly with/without the fix — verified both ways), plus a slower sanity test that drives the real `MainWindow`→`FavoritesPanel`+`ChatPanel` nesting through a 40-step resize sweep and asserts the column stays within its 60% share — this is *not* a reproduction of the reported bug (see above), just regression coverage so a future change can't silently break the stretch ratio. Full suite: 164 passed (162 prior + 2 new; same 2 pre-existing unrelated `test_katch_*` failures as noted earlier, caused by a missing `katch` module).

**Still open / next steps if the user reports the bug persists after this fix**:
1. Ask the user to reproduce it live and note precisely: does it happen mid-drag (releasing the mouse fixes it) or does it persist after releasing/settling? This distinguishes "transient rendering artifact" from "persistent layout state bug" and determines which class of fix is even relevant.
2. If it's a transient live-drag artifact: consider debouncing the expensive `QPixmap.scaled(..., SmoothTransformation)` call — do a cheap/fast rescale (or skip rescaling and just resize the label) on every `resizeEvent`, and only do the full smooth rescale once a short `QTimer` (~100-150ms) fires after resize activity settles. This is a standard mitigation for exactly this class of "image looks stretched during a live resize" symptom, independent of the exact underlying Qt/Windows mechanism.
3. If it persists after settling: get a screenshot of window dimensions immediately before/after, and if possible the OS DPI scaling setting, since none of the offscreen repros (which run at 100% scale, no native DPI awareness quirks) reproduced it.
4. Computer-use still cannot target this ad-hoc dev window (same limitation as before) — real-app verification continues to depend on the user's manual testing/screenshots.

## Follow-Up #2: sizeHint Fix Confirmed NOT Sufficient — Added Temporary Debug Logging

User re-tested with the sizeHint fix in place: **no visible change**. Maximizing still shows the preview image going "beyond the square" with part of it "cut off" — importantly, this is a more specific description than the original ("overflow past the panel edge, sibling buttons look wide"). "Cut off inside the box" points away from the grid-column-growth theory (already unconfirmed via 5 offscreen repro attempts, see above) and toward a **stale-scaled-pixmap-size mismatch**: `_apply_scaled_pixmap()` computes a `QPixmap.scaled(self.width(), self.height(), KeepAspectRatio, ...)` and caches the result via `setPixmap()`; if the label's actual final size (at paint time) ends up smaller than the `width()`/`height()` that were used at scale-time, the oversized cached pixmap gets clipped by the label's real (smaller) rect — since `KeepAspectRatio` can never overflow the box it was scaled *to*, but it also never *shrinks itself* automatically if the box shrinks *after* scaling. `showMaximized()` on Windows is a plausible trigger: Qt/Windows is known to sometimes deliver an oversized intermediate maximize geometry (covering the full monitor before the taskbar-aware work-area is applied) before settling to the final, smaller maximized size.

Rather than guess further, added **temporary debug logging** (clearly marked `# TEMP DEBUG (session-06 resize bug) - remove once diagnosed.` — must be stripped out once root-caused) to `gui_qt/components/chat_panel.py`:
- `_LandscapePreviewLabel.resizeEvent`: logs old/new `QResizeEvent` size, `self.width()/height()`, parent size, window size.
- `_LandscapePreviewLabel._sync_height`: logs width, height before/after `setFixedHeight()`, and the computed target.
- `_LandscapePreviewLabel._apply_scaled_pixmap`: logs the target size used for scaling, the resulting scaled pixmap size, and the source pixmap size.
- `_LandscapePreviewLabel.paintEvent` (new override): logs the label's actual rect size and its *currently held* pixmap size at the exact moment of painting — this is the critical one, since a mismatch here (`rect` smaller than `pixmap`) would directly confirm the clipping theory.
- `ChatPanel.resizeEvent` (new override): logs ChatPanel's own size, `contentsRect()`, the label's size, the top-level window's size, and `window().isMaximized()` — to correlate everything against the moment maximize actually happens.

All lines are prefixed `[PREVIEW-DEBUG]` and logged at `logger.info(...)` level (not `.debug()`) specifically so they show up with the app's **default** settings (`log_level: "INFO"`, `log_to_file: True` are both defaults per `src/constants.py` — no need for the user to enable debug mode). Verified via a quick offscreen sanity script that all five log points fire correctly with real geometry numbers and no exceptions; full test suite still 164/164 passing with this instrumentation in place.

**Next step**: user will run the real app, reproduce the maximize bug, and share the relevant `[PREVIEW-DEBUG]` lines from `logs/twitch_ad_avoider.log` (or console output) covering the maximize event. Once we have that, diagnose from real data instead of more speculative offscreen probing, then implement the fix (leading candidate: rewrite `_LandscapePreviewLabel` to draw via a `paintEvent` override that scales fresh from `self.rect()` on every paint, instead of caching a pre-scaled `QPixmap` from `resizeEvent` — this structurally can't go stale, since paint always uses the actual current, settled geometry). **Remember to strip the temporary debug logging back out once the real fix lands.**

## RESOLVED — Actual Root Cause Found via Real Log + Screenshots

The raw `[PREVIEW-DEBUG]` log data (966 lines) showed **no anomaly whatsoever** — every recorded `paintEvent` had the held pixmap matching the label's own rect almost exactly (≤1px rounding), and `ChatPanel` never exceeded its 60% grid column share at any point in the log. This ruled out both the sizeHint-feedback-loop theory and a stale-pixmap-scaling theory. User confirmed the bug **persists** in the settled maximized state (not a transient drag-animation artifact), which meant the defect had to be something my geometry logging wasn't checking at all.

**Screenshots broke it open**: comparing the non-maximized window (where the "Activity" section/`StatusDisplay` was fully visible below Favorites) against the maximized window (where "Activity" was entirely absent from the visible window) revealed the real mechanism: **a vertical overflow, not horizontal.**

`_LandscapePreviewLabel._sync_height()` computed height purely as `round(self.width() / (16/9))`, with zero awareness of how much vertical room `ChatPanel` (the "Stream" group box) actually had. On a wide-but-not-proportionally-tall maximized window (1920×1009 per the log), this formula demanded ~620px of height for the image alone. `ChatPanel`'s own allotted height in the grid (761px in this exact scenario) wasn't enough to fit that image *plus* all the buttons/labels/separators above and below it in its `QVBoxLayout` — so the image's bottom edge extended ~140px past `ChatPanel`'s own bottom edge and got **clipped there** (Qt widgets clip child rendering to their own contentsRect). This is exactly "goes beyond the square [ChatPanel's own bordered box] and part of the preview image is being cut off."

**Fix** (`gui_qt/components/chat_panel.py`):
- Added `_LandscapePreviewLabel.set_max_height(max_height)`: caps the width-driven height to an externally-supplied ceiling.
- `_sync_height()` now does `target_height = min(width_driven_height, self._max_height)` before applying it (still `max(..., 1)` floored).
- Added `ChatPanel._update_preview_max_height()`: iterates every *other* item in `ChatPanel`'s own `QVBoxLayout` (skipping the image label), sums their `sizeHint().height()` plus inter-item `layout.spacing()`, and subtracts that from `self.contentsRect().height()` to get the real available room for the image — computed fresh every resize, not a hardcoded pixel value (per the user's explicit preference against hardcoding). Called from `ChatPanel.__init__` (once, after `setLayout`) and `ChatPanel.resizeEvent()` (every resize).
- Removed all temporary `[PREVIEW-DEBUG]` logging that was added for diagnosis — none of it remains in the shipped code.

**Verification — this time a real, confirmed-effective regression test**:
- Built the *exact* real widget hierarchy (`MainWindow` + `StreamActions` row 0 + `FavoritesPanel`/`ChatPanel` row 1 + `StatusDisplay` row 2, matching `gui_qt/stream_gui.py::_setup_layout()` exactly) with a real 640×360 Twitch-resolution thumbnail, and drove it to the *exact* dimensions from the real log (902×823 → 1920×1009).
- **Confirmed the bug reproduces**: with the cap temporarily disabled, the label's bottom edge landed at y=901 while `ChatPanel` was only 761px tall — a 140px overflow, clipped exactly as described.
- **Confirmed the fix resolves it**: with the cap restored, the label's bottom edge (713) stays within `ChatPanel`'s bottom edge (761).
- Added `tests/test_chat_panel_preview_resize.py::test_preview_image_does_not_overflow_chat_panel_on_wide_maximized_window` — asserts this exact invariant (label bottom ≤ ChatPanel height, and StatusDisplay bottom ≤ window height) at both the 902×823 and 1920×1009 dimensions from the log. Verified via temporarily disabling the fix that this test **fails** without it (`901 <= 761` assertion error) and **passes** with it restored — this is a real, proven-effective regression test, unlike the earlier sizeHint-feedback-loop test which never actually distinguished fixed/unfixed code in a realistic scenario.
- Full suite: **165 passed** (164 prior + 1 new; same 2 pre-existing unrelated `test_katch_*` failures, excluded via `--ignore`).

**Status**: fix implemented and verified via a reproduction that matches the real bug exactly (confirmed fails without the fix, passes with it, at the real app's own logged dimensions). Awaiting final user confirmation by re-testing the actual running app (maximize + resize at various sizes) before considering this fully closed.

**Lesson learned for future sessions**: two earlier theories (sizeHint/minimumSizeHint feedback loop; stale-pixmap-scaling) were plausible-sounding and even had partial supporting reasoning, but neither was verified against *real* data before being implemented — the sizeHint fix was shipped once already and turned out not to fix the reported symptom. The eventual fix only emerged once actual log data and screenshots from the real running app were used to falsify the wrong theories and reveal what was actually happening (a vertical, not horizontal, overflow). When a GUI layout bug resists offscreen reproduction, get real data (logs + screenshots) before implementing a fix, not after.
