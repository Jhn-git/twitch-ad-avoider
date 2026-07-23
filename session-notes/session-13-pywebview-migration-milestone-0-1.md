# Session 13: PySide6/Qt → pywebview+React Migration — Milestones 0 & 1

## Context

Session 12 ended with the user deciding to migrate the GUI off PySide6/Qt entirely (see the "Decision: Migrating Off PySide6/Qt" section at the end of `session-12-stream-manager-redesign-implementation.md`), after a clean bug investigation still left the app looking "pretty bad." Target architecture: `pywebview` + a no-build-step React frontend, modeled on an existing pywebview+React app the user had already built (referred to below as "the reference project").

This session executed the plan approved in plan mode: research the current `gui_qt/` surface and the reference project's architecture in depth, design a full migration plan (API method inventory, screen-by-screen port order, threading migration, packaging changes), and begin implementation.

## Decisions made with the user

- **Dev workflow**: build directly on `main`, gated behind a `--web-gui` CLI flag until cutover. Old Qt GUI (`gui_qt.stream_gui.StreamGUI`) stays the default launch path throughout the migration.
- **Qt test fate**: at cutover, port the meaningful logic (generation-guards, debounce/cache, stream lifecycle state machine) from Qt-thread tests into plain-Python tests against the new API class; delete pure Qt-widget-wiring tests (`test_chat_panel*.py`, `test_favorites_panel.py`, `test_activity_drawer.py`, `test_options_rail.py`, `test_stream_manager_screen_collapse.py`, `test_stream_gui_preview_logic.py`).

The full migration plan (API method names, screen-by-screen milestones, threading-migration table, packaging changes) is preserved in the plan-mode transcript; this file tracks execution progress against it.

## Environment blocker found and fixed: Python 3.14 incompatible with pywebview's Windows backend

The repo's existing `.venv` was on Python 3.14. `pywebview`'s Windows backend depends on `pythonnet`, which does not yet support Python 3.14 — the same constraint the reference project already guards against via its own `runtime_check.py` (ported here verbatim as `runtime_check.verify_compatible()`).

Fix: created a **new**, separate `.venv312` (Python 3.12) alongside the existing `.venv` — non-destructive, nothing was deleted. Installed the project (`pip install -e ".[dev]"`) into it; `pywebview>=4.4` was added to `pyproject.toml`'s dependencies and pulled in cleanly, along with `pythonnet`/`clr_loader`/`bottle` as transitive deps.

**Follow-up needed**: decide whether `.venv312` becomes the project's new primary dev venv (and the old 3.14 `.venv` gets removed) as part of a later milestone, or whether both are kept side-by-side until cutover. Not decided yet — flagging for a future session.

## What was built this session

### Milestone 0 — pywebview skeleton (done)

- `runtime_check.py` (new, repo root) — Python-version/pythonnet compatibility guard, ported from the reference project.
- `webapi.py` (new, repo root) — `TwitchViewerAPI` class, the flat JS-callable surface. This session implemented the bootstrap + settings + UI-state slice only:
  - `set_window`, `_push` (shared `evaluate_js` helper, guarded against a torn-down window)
  - `get_initial_state()` — aggregate settings + dark_mode + UI-state for the frontend's initial load
  - `get_settings()`, `validate_setting(key, value)`, `save_settings(patch)` (calls `reconfigure_logging_from_config`, same as the Qt `settings_tab.py` did), `reset_settings_to_defaults()`
  - `set_ui_state(key, value)` — generic setter for the `stream_manager_*` persisted UI-state keys
  - Favorites/stream/clip/preview API methods are **not yet implemented** — those land with their respective milestones (E, F).
- `gui_web/` (new folder) — frontend shell:
  - `index.html` — CDN React 18 + ReactDOM + `@babel/standalone`, no build step. Theme CSS ported by hand from `gui_qt/styles/dark.qss`/`light.qss` into CSS custom properties (oklch-based, Twitch-purple accent instead of the reference project's amber), toggled via `data-theme` attribute.
  - `app.jsx` — root component: pywebview-readiness detection (`window.pywebview` check + `pywebviewready` event listener + timeout fallback, same pattern as the reference project's `app.jsx`), tab routing between "Stream Manager" (placeholder for now) and "Settings".
  - `helpers.jsx` — `window.AppHelpers.applyTheme(darkMode)`.
- `main.py` — added a `--web-gui` flag; when set, builds `TwitchViewerAPI`, creates the pywebview window (1280×800, min 1000×650), and starts the event loop, entirely separate from the existing Qt branch (which remains the default/no-flag path).
- `pyproject.toml` — added `pywebview>=4.4` to dependencies (PySide6 stays until cutover).

**Verified working**: launched `python main.py --web-gui` under the new 3.12 venv — clean log output ("Application ready - entering event loop"), no exceptions, process stayed alive in the event loop until killed. Full-screen screenshot capture didn't clearly show the new window (same window-stacking/focus limitation as session 12's investigation — the window very likely opened behind other on-screen content), so this was confirmed via clean process/log behavior rather than a visual screenshot. **A real, human-driven visual check of the skeleton window is still outstanding** — flagging as a next step rather than claiming full visual confirmation.

Full existing test suite (193 tests, unchanged) still passes under the new Python 3.12 venv: `pytest tests/` → `193 passed`.

### Milestone 1 — Settings tab (built, not yet manually verified)

- `gui_web/components/settings_tab.jsx` — ported all of `settings_tab.py`'s fields into fieldsets (Stream, Clips, Network, Favorites, Appearance, Advanced), each field calling `validate_setting` on change and showing an inline error, plus Save/Reset buttons wired to `save_settings`/`reset_settings_to_defaults` with a toast for success/failure.
- Wired into `app.jsx`'s Settings tab.

**Not yet done**: an actual human click-through of the Settings tab (save a value, confirm it persists to `config/settings.json`, confirm validation errors show correctly for bad input). This is the natural next step before moving on to Milestone 2 (app shell/theming polish) or Milestone 3 (Options rail).

## Next steps

1. Do a real, visual, human-driven check of the skeleton + Settings tab (the automation session's screenshot tooling couldn't confirm this reliably — see the window-stacking limitation noted above and in session 12).
2. Decide the `.venv`/`.venv312` question (see "Follow-up needed" above).
3. Continue with Milestone 2 (app shell/theming polish — dark/light toggle round-trip) and Milestone 3 (Options rail), per the approved migration plan.
