# Session 35: Taste Skill Install And GUI Polish

Date: 2026-10-08

## What Happened

Installed the "Taste" design skills and used them for a polish pass on the web GUI. Look and layout
were kept; this was a refinement, not a redesign.

### 1. Skills installed (global, not in this repo)

- `design-taste-frontend` and `redesign-existing-projects` from the open-source taste-skill repo,
  installed with `npx skills add ... -g -a claude-code --copy`. They live in the user-level
  `~/.claude/skills/`, so nothing was added to this public repo.

### 2. GUI polish (`gui_web/index.html`, CSS only)

- Visible keyboard focus ring on every control (there was none); darker ring variant for the light
  theme after the Luna review flagged low contrast (about 2:1) there.
- Hover and press feedback (transitions, `scale`/`translateY` on press), `not-allowed` cursor on
  disabled controls.
- Dropdown menus and toasts animate in; the activity drawer slides with an ease-out curve and is
  `visibility: hidden` when closed. `prefers-reduced-motion` turns animation off.
- The activity drawer was hard-coded dark and looked wrong in the light theme; it now uses theme
  variables.
- Typography: tighter channel title, tidier all-caps field label, tabular numerals in the activity
  log. Tinted shadows, thin themed scrollbars, selection color, settings section dividers.
- Accent colors pulled into variables (`--accent-hover`, `--accent-ink`) instead of repeated hex.

### 3. Font

- Bundled Geist (variable, SIL OFL) in `gui_web/vendor/fonts/` (latin + latin-ext woff2 plus the
  license text). `font-family` is `"Geist", "Segoe UI", system-ui, ...`. Source: the
  `@fontsource-variable/geist` npm package, 5.3.0. No build step added.

### 4. Process

- Luna review ran once (budget is one per session): one real finding (light-theme focus ring),
  fixed. Luna also noted there is no automated coverage for the visual changes.
- `AGENTS.md` (local only) gained two things: Claude now pushes to `origin` after committing
  (releases and destructive git still need confirmation), and a "Daily EXE Update" section.
- Project memory (outside the repo) got notes for the git/push rule and the daily-exe step.

## Verified

- `make test`: 248 passed, 73 subtests. Browser demo (`?demo=1`) checked: no console errors; drawer,
  dropdown, settings view and light theme render; Geist loads.
- `make check` fails on Black formatting in `scripts/probe_twitch_vod_audio.py` and
  `tests/test_probe_twitch_vod_audio.py`. Both were already failing before this session and were
  not touched.

## Not Done / Still Open

- The packaged exe was not built by Claude; Jhn ran the daily-exe updater himself. Confirm Geist
  actually shows in the built app (the build bundles `gui_web` wholesale, so it should).
- No automated test covers the new CSS (focus ring, drawer visibility, reduced motion). The UI
  contract tests only grep source strings.
- Fix the two Black-formatting failures so `make check` is green again.
- Not yet looked at after the pass: clip editor, collapsed rails and narrow-window layouts were
  only covered by the CSS edits, not re-screenshotted.
- Releases are still manual and need Jhn's go-ahead.
