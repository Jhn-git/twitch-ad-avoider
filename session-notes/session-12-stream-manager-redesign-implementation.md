# Session 12: Stream Manager Redesign Implementation

Date: 2026-07-06

## What Happened

- User asked to pull a UI mockup called "Stream Manager.dc.html" from a Claude Design project (via the `claude_design` MCP / `/design-login`) and implement it in the real app.
- The mockup redesigns the main streaming screen into a collapsible three-pane layout — Favorites rail (left), video/clip stage (center), Options rail (right) — plus a slide-up Activity log drawer at the bottom, using a new darker color palette (near-black background, dark panels, green accent) instead of the app's current blue-accented dark theme.
- Explored the existing `gui_qt/` code first and found almost everything needed already existed in some form: favorites list + live status (`FavoritesPanel`), stream start/stop + clip capture at 30/60/120/300s + quality selection + open channel/chat (`ChatPanel`, `StreamController`), and an activity log (`StatusDisplay`). This was a UI restructuring/restyling job, not new backend work.
- Went through a full plan-mode pass (exploration agents, then a planning agent, then clarifying questions) before writing any code. The plan is saved at `C:\Users\<user>\.claude\plans\use-the-claude-design-mcp-twinkly-stroustrup.md` if the detailed reasoning is needed again.
- Implemented the full plan (see Files Changed below), then ran the test suite and lint/type checks, then launched the real app (`python main.py`) and got a screenshot from the user confirming it renders correctly: three-pane dark/green layout, avatar rail with live-status dots and Pinned/Others sections, Clip button + dropdown, Options rail with Quality dropdown, Activity drawer pull-tab at the bottom.
- Note: the app was launched in the background for that check and **may still be running** (a `python main.py` process) — worth closing manually if not needed anymore, since my own attempt to screenshot/control that window via PowerShell failed (window handle came back null/inaccessible from the automation session), so I couldn't cleanly verify or close it programmatically.
- Session ended on the user asking whether it'd be easier to migrate parts of the app to TypeScript because the redesigned UI "looked rough" in the screenshot. I recommended against it (that's a full platform/runtime change — Electron/Node + packaging + IPC — for what's really just QSS/layout polish, not a technology ceiling) and asked if they wanted a polish pass instead.
- **Update (later same day, 2026-07-06): the user agreed to do the polish pass.** See "Layout Polish Pass" section below for what was actually done. Partway through that pass, while debugging a newly-discovered blank-label QSS bug, the user asked a second time whether to swap frameworks entirely (this time phrased as "swap this over to a different file type instead of trying to fit Qt into a non native system"). I again recommended staying with Qt/PySide6 — the friction so far (box-layout stretch/alignment quirks, one blank-label bug) reads as normal Qt debugging, not a sign the framework is the wrong fit, and a rewrite would mean re-implementing everything that already works just to get back to parity. **The user agreed to keep going with Qt, with an explicit condition: if Qt/QSS friction keeps piling up in ways that feel structural rather than incidental, revisiting a framework swap becomes fair game.** This is saved as a standing memory for future sessions.

## Layout Polish Pass (2026-07-06, same day)

- User compared a screenshot of the running app (`current-layout-screenshot.png`) against the original design mockup's own screenshot (`new-layout-goal.png`) and asked to tighten up the gaps.
- Ran three background investigation agents in parallel (read-only, root-cause only) covering: (1) the Activity drawer pull-tab rendering in the wrong place, (2) the video preview box rendering far smaller than the mockup, (3) three smaller styling gaps (Options header order, favorites selection fill, Clip button icon/divider). All three reported back concrete file:line root causes before any code was touched.
- Wrote a fresh plan file (`stream-manager-layout-polish.md`) — note: due to a stale plan-file path carried over from before this conversation was compacted, `ExitPlanMode` actually re-approved the *old* session-12 plan file's contents rather than this new one. The intent was unambiguous from context, so implementation proceeded directly from the new plan without re-litigating it.
- Implemented and verified 5 fixes (see Files Changed / Verification below). Confirmed via a real screenshot of the running app that the Activity drawer is now centered and the video preview now fills most of the center column, both matching the mockup.
- **Found a new bug while confirming the fixes, not yet resolved**: the "Favorites" and "Options" header labels render completely blank (only the collapse chevron is visible) even though both rails are expanded and every other row (avatars, buttons) renders fine. Confirmed via cropped close-up screenshots that the text truly isn't there, not just low-contrast. Was mid-investigation (had just located the relevant QSS block, `QLabel#favoritesHeaderLabel, QLabel#optionsHeaderLabel` in `dark.qss` lines 476-481, and confirmed the objectName in `favorites_rail.py` matches) when the conversation was paused for a session-notes update. **This is unrelated to the 5 fixes made today — it was not visible in the original post-redesign screenshot, so something about today's changes likely triggered it, but the cause is not yet confirmed.**

## Key Decisions

- **Replace, don't add.** The new layout replaces the existing "Stream" tab entirely rather than living alongside it.
- **Adopt the mockup's exact palette**, but scope it in QSS under a `#streamManagerRoot` object name so it can't leak into the Settings tab (which keeps the old blue theme).
- **New screen ignores the app's light/dark toggle** — it's always the new dark palette; no `light.qss` changes were made for it.
- **Persist UI state**: sidebar collapsed/expanded state and Activity-drawer open/closed state now save to `config/settings.json` (four new keys, see below) instead of resetting every launch.
- **Quality selector moved** from the Favorites panel to the new Options rail.
- **UX change (flagged, not yet explicitly confirmed by user):** the old standalone "Refresh" button on Favorites was dropped from the UI — the existing auto-refresh timer already covers it, but this is a visible behavior change worth double-checking with the user.
- **UX change (mockup-faithful):** picking a duration from the Clip dropdown no longer immediately fires a clip like it used to — it now only changes which duration the main Clip button will use next time it's clicked.
- The old separate "Idle / Starting / Live" status strip (`StreamActions`) was folded into the new center-stage panel instead of kept as its own component.
- **Stay on PySide6/Qt, don't migrate frameworks** — decided twice today (see "Layout Polish Pass" above) when the user asked about swapping stacks over UI friction. Standing condition: revisit if friction becomes structural rather than incidental.

## Files Changed

**New:**
- `gui_qt/components/favorites_list_core.py` (shared list/delegate pieces extracted from the old favorites panel)
- `gui_qt/components/preview_label.py` (video preview label extracted from the old chat panel)
- `gui_qt/components/favorites_rail.py` (new collapsible left sidebar)
- `gui_qt/components/options_rail.py` (new collapsible right sidebar)
- `gui_qt/components/stream_stage_panel.py` (new center video/clip stage)
- `gui_qt/components/activity_drawer.py` (new slide-up bottom log drawer)
- `gui_qt/components/stream_manager_screen.py` (top-level composite tying the four above together)
- `tests/test_options_rail.py`, `tests/test_activity_drawer.py`, `tests/test_stream_manager_screen_collapse.py`

**Deleted:**
- `gui_qt/components/favorites_panel.py`, `gui_qt/components/chat_panel.py`, `gui_qt/components/stream_actions.py`

**Modified:**
- `gui_qt/components/status_display.py` — stripped down to just the message feed (chrome/collapse-toggle now lives in `activity_drawer.py`)
- `gui_qt/main_window.py` — replaced the old grid-based Stream tab with `set_stream_manager_screen()`
- `gui_qt/stream_gui.py` — fully rewired signal/handler wiring for the new components, plus new handlers that persist sidebar/drawer/clip-duration state
- `gui_qt/styles/dark.qss` — added a new `#streamManagerRoot`-scoped section for the new palette; removed a couple of now-dead rules (`streamStateLabel`, `activitySummary`) that only the deleted components used
- `src/constants.py` — added 4 new default settings (`stream_manager_left_sidebar_open`, `stream_manager_right_sidebar_open`, `stream_manager_activity_drawer_open`, `stream_manager_clip_duration_seconds`)
- `src/config_manager.py` — added validators for the above, plus a new reusable `_validate_int_choice_setting` helper (didn't exist before — for "must be one of a fixed set of values" settings)
- `tests/test_favorites_panel.py`, `tests/test_chat_panel.py`, `tests/test_chat_panel_preview_dimming.py`, `tests/test_chat_panel_preview_resize.py`, `tests/test_stream_gui_preview_logic.py`, `tests/test_config_validation.py` — retargeted to the new components / new settings

**Modified (Layout Polish Pass, same day):**
- `gui_qt/components/activity_drawer.py` — centered the pull-tab (`layout.setAlignment(self._pull_tab, Qt.AlignHCenter)`) instead of leaving it left-aligned/`Fixed`-size-policy.
- `gui_qt/components/stream_manager_screen.py` — added a `showEvent` override that also calls `activity_drawer.reposition()`, so first-paint geometry isn't computed against a stale/placeholder parent size (previously only `resizeEvent` did this, which isn't guaranteed to fire with the real size before first paint).
- `gui_qt/components/stream_stage_panel.py` — changed the main layout's `setAlignment(Qt.AlignTop | Qt.AlignHCenter)` to just `Qt.AlignTop` (the `AlignHCenter` was collapsing the whole vbox down to its widest child's sizeHint — the actions row — capping every row including the preview at ~265px regardless of available width); gave the preview label an explicit stretch factor (`addWidget(self._preview_label, 1)`) so it now claims surplus width up to its existing 920px cap instead of splitting space evenly with its two flanking spacers. Also updated `_clip_button_text()` to prepend a scissors glyph (`"✂  Clip (30s)"`).
- `gui_qt/components/options_rail.py` — reordered the header row so `header_label` ("Options") is added before `toggle_button` (chevron), matching the mockup's "Options ›" reading (previously "› Options").
- `gui_qt/components/favorites_rail.py` — `FavoriteAvatarDelegate.paint()`'s selected-state brush changed from `QBrush(self.SELECTED_TINT)` (filled green wash) to `Qt.NoBrush`, so the selected favorite now shows as an outline (just the `SELECTED_BORDER` stroke) instead of a solid fill, matching the mockup.
- `gui_qt/styles/dark.qss` — bumped the scoped `#clipSplitButton::menu-button` divider's alpha for more contrast, and added a scoped `::menu-arrow` rule (reusing the existing `caret-dark.svg` asset) since the new palette-scoped block previously had no menu-arrow rule at all and was falling back to inconsistent default styling.
- `tests/test_chat_panel.py` — updated the clip-button-text assertion to match the new `"✂  Clip (2 min)"` format.

## Verification

- `python -m pytest tests/` — **193 passed**.
- `python -m flake8 gui_qt/` — clean (fixed one lambda-assignment warning and one unused import that I introduced).
- `python -m black --line-length 100` — applied; also reformatted a few pre-existing files it touched incidentally (`live_notification_toast.py`, `settings_tab.py`, `popup_utils.py`) — formatting only, no logic changes.
- `python -m mypy` — remaining errors are pre-existing PySide6/mypy stub noise that already exists throughout the untouched parts of the codebase (e.g. `ad_indicator.py`, which I never touched, shows the same class of "attr-defined" errors on `Qt.UserRole`-style enums). Fixed the one real issue that was mine: a `Dict[int, object]` typed too loosely, now `Dict[int, QAction]`.
- Manually launched the real app and got a screenshot back from the user confirming the new layout renders correctly.

**Verification (Layout Polish Pass, same day):**
- `python -m pytest tests/` — 193 passed (updated the one clip-button-text assertion that needed to change; nothing else broke).
- `python -m flake8 gui_qt/` — clean.
- `python -m black --check` on the specific files touched today — clean (two unrelated pre-existing files, `test_popup_utils.py`/`test_stream_preview.py`, still show drift from before this session — left untouched, not mine).
- `python -m mypy` on the touched files — only the same pre-existing PySide6/mypy stub noise class as always (`attr-defined` on Qt enums); no new categories of error introduced.
- **Found a working screenshot method this session** (see below) — took a real screenshot of the running app and confirmed: the Activity drawer pull-tab is now centered at the bottom (no longer overlapping the Favorites rail), and the video preview now fills most of the center column width instead of the small ~265px box from before. Did **not** get to visually confirm the other 3 fixes (Options header order, favorites outline, clip icon) before discovering the blank-header-label bug and pausing for this note.

## Blank Header-Label Bug: Investigated, Does Not Reproduce (2026-07-07)

- Picked this up as the next session's first priority. Two rounds of investigation (a subagent that
  loaded the live `dark.qss`/`favorites_rail.py`/`options_rail.py` in a real PySide6 process, then my
  own direct in-process test) found **no code defect**: QSS specificity resolves correctly (`#f2f2f3`),
  `isVisible()`/`isHidden()` are correct on every `set_collapsed` code path including the real startup
  sequence, label geometry is non-zero, and the font resolves with `exactMatch() == True` (Segoe UI,
  10.5pt, weight 600).
- Confirmed empirically via `QWidget.grab()` (renders through the real Windows/Qt paint pipeline, not
  the offscreen QPA platform the first investigation pass used) that **both header labels render their
  text correctly** ("Favorites ‹" and "Options ›") with the exact current working-tree code, in both
  expanded and collapsed→re-expanded states.
- **Conclusion: treating this as a one-off rendering glitch, not a persistent bug.** Most likely
  explanation is a race condition from reading `dark.qss` while it was still being saved/edited during
  the previous session, or a stale already-running process from earlier in that session picking up a
  partial stylesheet. No code changes were made — the existing implementation is correct as written.
  If this recurs, capture the exact sequence of actions immediately beforehand (this is the detail that
  was missing last time).
- Used the same live `grab()`-based approach (driving the real `StreamGUI` programmatically, screenshot
  via Qt's own paint rather than OS-level window capture — this machine's automation session can't see
  other processes' windows for focus/enumeration, only raw screen capture works) to close out the 3
  previously-unconfirmed polish-pass fixes, all now visually confirmed correct:
  - Options rail header reads "Options ›" (label before chevron), matching the mockup.
  - A selected favorite renders as a green outline, not a filled box.
  - The Clip button shows the scissors icon, "Clip (30s)" text, a visible divider, and a distinct
    darker-green dropdown-arrow zone.
- Also did a programmatic click-through pass: selecting a favorite, collapsing both rails, re-expanding
  them (header text confirmed still present after a real collapse/expand cycle), and opening the
  Activity drawer — all behaved correctly.
- Full test suite re-run clean: `python -m pytest tests/` — 193 passed, no changes needed.
- **Cleanup done**: moved the loose reference/diagnostic screenshots out of the repo root (both mine
  and the investigation subagent's) into a scratch folder outside the repo; killed the throwaway
  diagnostic-script processes. Left two long-idle `python` processes (PIDs 16416/22424, no visible
  window, running since earlier today) untouched pending the user's confirmation they're not needed.
  Also reset `stream_manager_activity_drawer_open` back to `false` in `config/settings.json` after
  testing (left both sidebars persisted as expanded — seems like the better default resting state).

## Open Questions: Resolved (2026-07-07)

- **Dropped Favorites "Refresh" button**: user confirmed keeping it dropped — auto-refresh timer already covers it.
- **`Stream Manager Redesign.dc.html`** (the second, unimplemented Claude Design file): user confirmed it's an unrelated/old draft, not something to build or compare against.
- **Stale python processes (16416/22424)**: user confirmed closing them; done.

## Things We Haven't Tried Yet

- A real (human-driven, not programmatic) click-through pass in the running app, plus a genuine app restart to confirm persisted sidebar/drawer/clip-duration settings survive it — today's click-through was programmatic (driving the widgets directly in-process), which is good evidence but not identical to a user's actual mouse-driven session.
  - Superseded by the framework decision below — no longer worth doing against the Qt build specifically.

## Decision: Migrating Off PySide6/Qt (2026-07-07)

After the header-bug investigation above came back clean (no code defect, bug didn't even reproduce)
and all 3 outstanding polish-pass fixes were visually confirmed correct, the user looked at the actual
running app again and judged it still "pretty bad as it was before" — the visual quality itself, not
just isolated bugs, is the problem. This invokes the standing condition from earlier today (see
`## Key Decisions` above / `feedback_qt_framework_commitment` memory): Qt/QSS friction has become
structural rather than incidental, so **the plan is now to migrate the GUI off PySide6/Qt entirely**,
rather than continue polishing it.

**Target architecture**: `pywebview` + a no-build-step React frontend, modeled directly on an existing
pywebview+React app the user had already built (referred to below as "the reference project"). Shape to follow:
- Python (`main.py`) creates a `pywebview` window loading a local `index.html`, passing a single
  backend API class as `js_api=` so it's exposed to JS as `window.pywebview.api.*`.
- That one API class is the entire JS-callable surface (stream control, favorites, config, clip
  capture, etc.) — mirrors `ConverterAPI` in the reference project's `api.py`.
- Python-to-JS push (e.g. live status updates, activity log messages) goes through
  `window.evaluate_js(...)` invoking global callback functions the frontend defines at startup.
- Frontend is plain HTML + inline React loaded as ES modules directly by the browser engine — no
  webpack/vite/bundler, no Node toolchain. CSS lives in the HTML shell (the reference project uses
  oklch custom properties for dark/light theming).
- Packaging stays PyInstaller-based (`build.ps1`), same as today — this part of the toolchain carries
  over unchanged.
- This sidesteps QSS entirely: real browser text/layout rendering (flexbox/grid, no `font-weight`/QSS
  cascade quirks), which is the actual thing being escaped.

This is a full GUI rewrite, not a patch — all of `gui_qt/` gets replaced. The existing backend logic
(`src/` — stream detection, config manager, favorites manager, clip capture, ad-block detection, etc.)
is Qt-independent and should carry over largely as-is, wired to the new API class instead of Qt
signals/slots.

## Next Steps

1. Plan the migration: inventory current `gui_qt/` components/screens against what needs an
   HTML/React equivalent (Stream Manager screen's 3 panes + Activity drawer, Settings tab, live
   notification toast, ad-block indicator, popups/menus).
2. Stand up the `pywebview` + API-class skeleton first (empty window, one round-trip call), confirming
   the pattern works in this repo before porting real screens.
3. Port screen-by-screen, starting with the Stream Manager screen since it's the freshest in mind.
4. Decide packaging/build script changes needed in `build.ps1`/`run.ps1` for the new dependency
   (`pywebview`) and confirm PyInstaller hidden-imports needs.
