# Repository Guidelines

## Project Structure & Module Organization

This is a Python desktop app for Twitch playback through Streamlink, pywebview, and a no-build React UI. `main.py` is the app entrypoint. Core Python modules live in `src/`, including `webapi.py` for the JavaScript bridge, `web_stream_service.py` for Streamlink/HLS proxy behavior, and managers for config, favorites, logging, and validation. Frontend files live in `gui_web/`; React JSX components are under `gui_web/components/`, with vendored browser libraries in `gui_web/vendor/`. Tests live in `tests/`. Packaging, release, and executable helpers live in `scripts/`. Static icons and sounds live in `assets/`.

## Build, Test, and Development Commands

Use Python 3.10-3.13; Python 3.12 or 3.13 is preferred on Windows.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
python main.py
```

Common commands:

- `make run`: start the GUI app.
- `make test`: run `pytest` against `tests/`.
- `make check`: run Black format check, flake8, and mypy.
- `make all`: run checks plus tests before a PR.
- `make build`: build the Windows executable via `scripts/build_executable.py`.
- `make release BUMP=patch`: bump, build, and publish a GitHub release.

## Coding Style & Naming Conventions

Python code uses Black with a 100-character line length and flake8 with Black-compatible ignores (`W503`, `E203`). Prefer clear snake_case for functions, variables, modules, and test files. Use PascalCase for classes. Keep frontend components in descriptive snake_case filenames, matching the existing `gui_web/components/*.jsx` style. Avoid introducing a build step for the frontend unless the project direction changes.

## Testing Guidelines

Tests use pytest and follow `test_*.py`, `Test*`, and `test_*` naming configured in `pyproject.toml`. Add focused tests in `tests/` for backend service, config, validator, API bridge, and persistence behavior. Run `make test` for normal verification and `make all` before larger changes. Use `make test-coverage` when touching shared logic or behavior with higher regression risk.

## Commit & Pull Request Guidelines

Recent history uses short imperative commits such as `Refactor Twitch viewer stream and UI handling` and release bumps like `bump: v2.0.13`. Keep commits scoped and descriptive. Pull requests should explain the behavior change, mention tests run, link related issues when available, and include screenshots or short recordings for visible `gui_web/` UI changes.

## Security & Configuration Tips

Do not commit local settings, logs, clips, build output, virtualenvs, or generated executables. Runtime settings belong in `config/settings.json`; keep defaults and migrations in `src/config_manager.py`. Be careful with network, proxy, and FFmpeg changes because they affect local playback and clipping paths.
