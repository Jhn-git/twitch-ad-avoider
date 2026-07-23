# Session 16: Project Cleanup And Root Organization

Date: 2026-07-08

## What Happened

- Cleaned up the post-webview migration project structure and removed leftover migration clutter.
- Repaired script/tooling issues found during cleanup:
  - `make check` no longer runs Black in rewrite mode.
  - PowerShell scripts were made ASCII-safe so Windows PowerShell parses them reliably.
  - `scripts/release.ps1 -DryRun` parses and reports its planned version bump without mutating files.
  - PyInstaller no longer bundles local `config/`, so personal settings/favorites are not baked into the EXE.
- Removed ignored generated/runtime folders for a fresh-checkout feel: build output, logs, temp files, config, clips, caches, and the stale PySide6 UI preview helper.
- Organized the repo root:
  - Moved `webapi.py` to `src/webapi.py`.
  - Moved `runtime_check.py` to `src/runtime_check.py`.
  - Moved `run.ps1` to `scripts/run.ps1`.
  - Moved `update-daily-exe.ps1` to `scripts/update-daily-exe.ps1`.
  - Removed ignored root helper clutter such as `AGENTS.md`, `.claude/`, and `.codex/`.
  - Restored `TODO.md` in the root because it is useful there.

## Important Files Changed

- `Makefile`: added `format-check`; changed `check` to non-mutating checks.
- `scripts/TwitchUtilities.psm1`: replaced symbol-prefixed output with ASCII `[OK]`, `[ERROR]`, `[WARN]`, and `[INFO]`; updated Python requirement text.
- `scripts/release.ps1`: removed stale spec-version update and fixed dry-run parsing/output.
- `scripts/twitchadavoider.spec`: removed local `config/` bundling and stale Qt excludes.
- `main.py`, `tests/test_webapi.py`, `README.md`, and `src/favorites_manager.py`: updated imports/docs after moving `webapi` and `runtime_check` under `src/`.
- `tests/test_project_boundary.py`: added regression guards for project-boundary cleanup, script parsing, non-mutating `make check`, and no bundled local config.

## Current Root Shape

Expected root-level files/folders after cleanup:

- Files: `.flake8`, `.gitignore`, `CHANGELOG.md`, `main.py`, `Makefile`, `pyproject.toml`, `README.md`, `TODO.md`
- Folders: `.git`, `.venv`, `assets`, `gui_web`, `scripts`, `session-notes`, `src`, `tests`

`TODO.md` and `session-notes/*` are ignored by Git on purpose, so they may not appear in normal `git status`.

## Verification Already Run

- `python -m pytest tests/` passed with 96 tests and 63 subtests.
- `python -m black --check .` passed.
- `python -m flake8 .` passed.
- `python -m mypy src/` passed.
- `make check` passed.
- `powershell -NoProfile -ExecutionPolicy Bypass -Command "Import-Module .\scripts\TwitchUtilities.psm1 -Force; Test-PythonInstallation"` passed.
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\release.ps1 -DryRun` passed.
- `python scripts\build_executable.py --skip-deps` passed and produced `dist/TwitchAdAvoider.exe`; build artifacts were removed afterward.
- `rg -n "PySide6|gui_qt" . --glob '!gui_web/vendor/**'` returned no matches, and a separate related-project-name boundary check also returned no matches.

## Current Git State

- Work is implemented but not staged or committed.
- Git will show moved files as deletes plus untracked replacements until staged:
  - old root `webapi.py` / `runtime_check.py` / `run.ps1` / `update-daily-exe.ps1`
  - new `src/webapi.py` / `src/runtime_check.py` / `scripts/run.ps1` / `scripts/update-daily-exe.ps1`

## Things We Havnt Tried Yet

- Manual `python main.py` click-through after the file moves.
- Live embedded playback after the cleanup.
- Clip creation after the cleanup.
- Running `scripts/update-daily-exe.ps1` for real.
- Running the built EXE manually after the root reorganization.
- Running a real release, tag, push, or GitHub release creation.

## Next Steps

- Do a short manual app smoke test: launch, select a favorite, start/stop a live stream, create a clip, and restart once to confirm settings are recreated cleanly.
- If the manual smoke test passes, stage the moved files so Git records them as renames/moves cleanly.
- Optional: decide whether `TODO.md` should stay ignored but local, or become a tracked backlog file.
