# Session 14: WebView Cutover And Embedded Playback

Date: 2026-07-07

## What Happened

Jhn asked to implement the full cleanup plan for the Twitch Viewer app:

- Replace the messy Qt redesign and partial web scaffold with a pywebview + no-build React app.
- Open directly to the Stream Manager view, matching `goal.png` more closely.
- Remove the old top tab chrome.
- Move playback into the center app preview/video area instead of launching VLC or another external player.
- Keep the unrelated related project fully outside this repository.

The session completed the main cutover:

- `python main.py` now launches the pywebview Stream Manager by default.
- `--web-gui` was removed.
- `--channel/-c`, `--quality`, and `--debug` remain, with channel/quality feeding the web UI path.
- The old Qt runtime folder was removed.
- The old external-player stream module and player-argument helper were removed.
- The new frontend lives in `gui_web/` with local React, ReactDOM, Babel, and hls.js vendor files.
- A new JS bridge in `webapi.py` exposes favorites, settings, playback, clipping, activity, and open-channel/chat/folder actions.
- A new `src/web_stream_service.py` handles Streamlink playback resolution, local HLS proxying, recording, stop/shutdown, and FFmpeg clipping.

## Key Decisions

- Final desktop shell is pywebview, not Qt.
- Runtime views are plain JSX files under `gui_web/`, loaded without a frontend build step.
- Playback is Streamlink-backed embedded playback, not Twitch iframe playback.
- The local WebView player uses hls.js against a loopback playlist URL.
- If WebView2 needs CORS/header help, the local proxy rewrites playlists and segment URLs.
- Old user-facing settings for `player`, `player_path`, `player_args`, and external-player cache duration are retired.
- Existing old config files still load: retired keys are dropped during migration instead of breaking `config/settings.json`.
- The unrelated related project remains its own app and is not coupled into this repo.

## Important Files And Artifacts

- `main.py`: now launches the web app path by default.
- `webapi.py`: single JS-callable API bridge.
- `src/web_stream_service.py`: Streamlink HLS resolution, local proxy, recording, clips, cleanup.
- `gui_web/index.html`: full Stream Manager shell and styling.
- `gui_web/app.jsx`: app bootstrap and pywebview bridge setup.
- `gui_web/components/`: favorites rail, video stage, options rail, activity drawer, settings view, toast, icons.
- `gui_web/vendor/`: local React/Babel/hls.js files so the app does not depend on CDNs.
- `pyproject.toml`: removed PySide6, added Python `<3.14`, fixed mypy target, added PyInstaller to dev deps.
- `scripts/twitchadavoider.spec`: now bundles `gui_web`, vendor JS, assets, config, pywebview, requests, and Streamlink.
- `README.md` and `CHANGELOG.md`: rewritten to describe the WebView embedded-playback app.
- `dist/TwitchAdAvoider.exe`: PyInstaller build succeeded after the cutover.

## Verification Completed

Commands run successfully:

```powershell
python -m pip install -e .[dev]
python -m pytest tests/
make check
python scripts/build_executable.py --skip-deps
rg -n "PySide6|gui_qt" .
```

Results (plus a separate related-project-name boundary check, which returned no matches):

- `python -m pytest tests/` passed: 89 tests.
- `make check` passed: Black, Flake8, and MyPy clean.
- PyInstaller build succeeded and produced `dist/TwitchAdAvoider.exe`.
- `rg -n "PySide6|gui_qt" .` returned no matches.

## Tests Added Or Reworked

- Config migration tests now confirm retired player keys are dropped on load and rejected at runtime.
- Web stream service tests cover:
  - Streamlink session options.
  - Loopback playback URL creation.
  - Quality fallback.
  - Stop state cleanup.
  - Playlist/resource URL rewriting.
  - FFmpeg clip command behavior.
- API tests cover:
  - Initial state.
  - Favorites add/remove/pin.
  - Start/stop/clip delegation.
  - Settings validation.
  - JS push payloads.
- Project boundary test checks that the related app name remains absent without spelling it directly in the test source.

## Things We Have Not Tried Yet

- Manual launch of `python main.py` and click-through of the real WebView app.
- Manual launch of `dist/TwitchAdAvoider.exe`.
- Live Twitch embedded playback with a currently live channel.
- Real clip creation from an active live stream.
- App restart persistence check for selected quality, clip duration, and drawer state.
- Long-running playback/reconnect behavior against a real stream ending or dropping.
- Visual screenshot comparison against `goal.png` after the actual app renders.

## Remaining Risks

- The local HLS proxy and hls.js path is covered by unit tests but still needs a real Twitch playback test.
- Recording currently reads a separate Streamlink stream while playback uses the proxied HLS URL; this preserves clipping but should be watched for doubled bandwidth on slow connections.
- The UI has a demo fallback only when opened with `?demo=1`; pywebview startup should use the real bridge, but this still needs a real launch check.
- The build succeeds, but the built EXE still needs a human smoke test on the desktop.

## Next Steps

1. Run `python main.py` and confirm it opens directly to the new Stream Manager.
2. Select a live favorite or launch with `python main.py --channel CHANNEL_NAME`.
3. Start embedded playback and verify the center video player actually plays.
4. Create a short clip and verify the saved file opens.
5. Restart the app and confirm settings/UI state persist.
6. Run the built `dist/TwitchAdAvoider.exe` and repeat a quick playback smoke test.
7. If playback fails, inspect logs and focus first on HLS proxy headers, playlist rewriting, and WebView2 media support.
