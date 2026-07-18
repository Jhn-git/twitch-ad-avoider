# Session 17: Onedir Build Fix, Config Data-Loss Fix, And Settings-Page Stream Bug

Date: 2026-07-09

## What Happened

Started from "are we even able to build anymore for releases" after the Qt -> pywebview swap, and ended up finding and fixing two real bugs plus a near-miss data-loss incident:

1. **Build script false positives (not a real bug, just noise):**
   - The first build failure the user hit was a manual `KeyboardInterrupt` (Ctrl+C on an impatient/silent build).
   - The second was `No module named PyInstaller` because the project's `.venv` never had `pip install -e .[dev]` run in it. Fixed by installing dev deps into the venv.
   - Found and fixed a real latent bug while we were in there: `check_dependencies()` in `scripts/build_executable.py` checked for PyInstaller via `shutil.which()` (a PATH lookup), which can find an unrelated global Python's PyInstaller and falsely report `[OK]` even when the active venv can't actually run it. Now checks by importing from the current interpreter, same as the other deps.

2. **Real bug: the built EXE launched but showed no window and crashed silently.**
   - Root cause: pywebview's Windows backend requires `pythonnet` to bootstrap a .NET runtime (winforms backend), and `console=False` (windowed) builds have `sys.stdout`/`sys.stderr` as `None` in a frozen PyInstaller app, so any crash's `print()`-based error handling in `main.py` was itself throwing (raising a second exception on top of the first), producing zero visible output.
   - Once we forced a temporary `console=True` build to see the real error, we found pythonnet's CLR loader (`Failed to resolve Python.Runtime.Loader.Initialize`) fundamentally breaks under PyInstaller's **onefile** mode, because onefile re-extracts everything to a fresh random temp folder on every launch. Confirmed both `.NET Framework` and `CoreCLR` hosting fail under onefile; **onedir** (a folder instead of a single exe) works cleanly.
   - Migrated `scripts/twitchadavoider.spec` from onefile to onedir (`EXE` + `COLLECT`), disabled UPX entirely (`upx=False`) since UPX is known to corrupt mixed-mode native/.NET DLLs like `Python.Runtime.dll` and this class of bug isn't worth revisiting.
   - Updated the ripple-through: `scripts/build_executable.py` (launcher path/messaging), `scripts/release.ps1` (now zips `dist/twitchadavoider/` and uploads the zip to `gh release` instead of a bare exe), `scripts/update-daily-exe.ps1` (see below), and `README.md` download instructions.
   - Later renamed the build artifact from `TwitchAdAvoider.exe`/`TwitchAdAvoider/` to lowercase `twitchadavoider.exe`/`twitchadavoider/` per user preference (app display name / window title were intentionally left alone, e.g. `main.py`'s window title is still "TwitchAdAvoider - Stream Manager").

3. **Near-miss data-loss incident caused by the onedir migration, now fixed:**
   - My first version of `update-daily-exe.ps1` moved the *entire* existing desktop app folder (`C:\Users\redacted\Desktop\Jhn Apps\jhn-twitch-viewer`) to a `.previous` sibling folder and copied a totally fresh build over it. Since PyInstaller's build output never includes `config/`, this reset the live app's `config/settings.json` and `favorites.json` to blank/default, and left `clips/` (~750MB, 23 files) and `temp/` (~26GB of in-progress/orphaned `.ts` recordings) sitting only in the backup, one `Remove-Item` away from being permanently deleted on the *next* update run.
   - We caught this because the user noticed settings looked reset. We recovered by manually copying `config/` and `clips/` back from `jhn-twitch-viewer.previous/` into the live folder. We deliberately did **not** touch `temp/` during recovery because the app was actively running with an in-progress recording (`temp/recording_jg_darhk.ts`) and the backup had a file with the exact same name — copying it back risked corrupting the live recording.
   - Rewrote `scripts/update-daily-exe.ps1` so this class of bug can't happen again: it now only ever replaces the specific build-output items that exist in the fresh build (`twitchadavoider.exe`, `_internal/`, `launch.bat`), each backed up as `<name>.previous` for rollback, and never touches `config/`, `clips/`, `logs/`, or `temp/` at all. Verified with a simulated dummy folder that user-data files are byte-for-byte untouched while build output is replaced and backed up.

## Important Files Changed

- `scripts/build_executable.py`: fixed false-positive dependency check (import-based, not PATH-based); `APP_NAME = "twitchadavoider"` constant; launcher script now written inside the app folder; updated result messaging for onedir.
- `scripts/twitchadavoider.spec`: converted onefile `EXE()` to onedir `EXE(exclude_binaries=True)` + `COLLECT()`; `upx=False`; `console=False` (confirmed working after the onedir fix); `APP_NAME = "twitchadavoider"`.
- `scripts/release.ps1`: builds, then zips `dist\twitchadavoider\*` into `dist\twitchadavoider-vX.Y.Z.zip`, uploads that zip to `gh release create` instead of a bare exe.
- `scripts/update-daily-exe.ps1`: rewritten to do a surgical per-item replace-and-backup of only the build output, never touching user-data folders. See incident description above.
- `README.md`: download instructions updated to describe downloading+extracting the zip and running `twitchadavoider.exe` from inside the extracted folder.

## Verification Already Run

- `pip install -e .[dev]` succeeded in `.venv`; confirmed `python -c "import PyInstaller"` works.
- Full production build via `python scripts/build_executable.py` succeeds and produces `dist/twitchadavoider/twitchadavoider.exe`.
- Ran the built exe directly (both temporarily with `console=True` for debugging, and with the real `console=False` production spec) and confirmed it starts, logs "Application ready - entering event loop", and stays running (process visible in `tasklist`) instead of crashing.
- Confirmed the dependency-check fix correctly reports `pyinstaller` as missing when temporarily uninstalled from the venv, then reinstalled it.
- `python -m pytest tests/` passed all 100 tests after all changes.
- `scripts/release.ps1 -DryRun` printed the correct lowercase zip name and `gh release create` command.
- Simulated the new `update-daily-exe.ps1` replace logic against dummy folders: confirmed `config/settings.json` and `clips/clip1.mp4` were left byte-for-byte untouched, while `twitchadavoider.exe`/`_internal/`/`launch.bat` were replaced and the previous versions backed up as `*.previous`.
- Manually restored the user's real `config/settings.json`, `config/favorites.json`, and `clips/` (23 files) from `jhn-twitch-viewer.previous/` back into the live `jhn-twitch-viewer/` folder on the Desktop.

## Current Git State

- Work is implemented but not committed. Modified files: `README.md`, `scripts/build_executable.py`, `scripts/release.ps1`, `scripts/twitchadavoider.spec`, `scripts/update-daily-exe.ps1`.
- All `dist/`/`build/` test artifacts created during verification were cleaned up afterward (gitignored anyway).

## Things We Haven't Tried Yet (build/release side)

- Running `scripts/update-daily-exe.ps1` for real end-to-end since the rewrite (only simulated the core replace logic against dummy folders so far).
- Running a real `scripts/release.ps1` release (only `-DryRun` was tested).
- The user still has `C:\Users\redacted\Desktop\Jhn Apps\jhn-twitch-viewer.previous\` sitting on their Desktop with ~26GB of orphaned `.ts` recordings in its `temp/` folder (leftovers from the old script force-killing the app mid-recording during past updates). The new script will never touch this folder again, but it hasn't been cleaned up or reviewed for anything worth keeping.
- The user needs to restart the live desktop app (once its current recording finishes) so it reloads the restored `settings.json`/`favorites.json` from disk — it was still running with blank in-memory defaults as of end of session, and could overwrite the restored files if it autosaves before a restart.

## Next Bug To Investigate: Stream Stops When Opening Settings

Not started yet this session — just captured before compaction/stopping for the night.

**Symptom:** Opening the Settings page in the app stops the active stream. Closing the Settings page starts the stream again. Desired behavior: the stream should keep playing/streaming in the background while the user is in Settings; it should NOT be stopped and restarted just from navigating to/from Settings.

**Likely relevant files (found via a quick grep, not yet investigated):**
- `gui_web/components/settings_view.jsx` (the Settings page component)
- `gui_web/components/stream_manager.jsx` (has an `onOpenSettings` prop and stream/quality state; likely where navigation to Settings is wired up)
- `gui_web/components/options_rail.jsx` (also references settings)
- Backend-side: `src/webapi.py` (JS bridge) and `src/web_stream_service.py` (Streamlink/HLS proxy) may have stream stop/start calls that need tracing to see what actually triggers on Settings open/close.

**Things not tried yet (nothing has been tried yet — fresh start next session):**
- Haven't traced what UI/JS event actually fires on opening/closing Settings.
- Haven't confirmed whether the stop/restart happens in the frontend (React unmounting the video/player component) or backend (webapi.py telling web_stream_service to stop/start Streamlink).
- Haven't checked if this is intentional-but-undesired behavior (e.g. the video player component unmounts when Settings is shown, killing the underlying stream), or an actual bug (e.g. some effect/cleanup hook fires incorrectly on route change).
- Haven't looked at whether the fix should be "don't unmount the stream when Settings opens" (e.g. keep the video element mounted but hidden, or move Settings into an overlay/modal rather than a route swap) vs. "the stream stop call is happening somewhere it shouldn't."

## User Decision: `temp/` Does Not Need To Be Preserved

Confirmed with the user after this session's write-up: `temp/` (the in-progress/orphaned `.ts` recordings) is fine to lose — no need to back it up or carry it forward on updates. `config/`, `clips/`, and everything else are the things that must survive an update, and the rewritten `update-daily-exe.ps1` already leaves those untouched/carried-over correctly (confirmed working as intended). So the ~26GB orphaned `jhn-twitch-viewer.previous/temp/` folder mentioned below can just be deleted whenever convenient — it does not need review first.

## Next Steps

1. Restart the live desktop app once the current recording finishes, to make sure the restored settings/favorites actually load.
2. Delete the ~26GB orphaned `jhn-twitch-viewer.previous/temp/` folder whenever convenient — confirmed not needed (see decision above).
3. Do a real (non-dry-run) test of `update-daily-exe.ps1` and `release.ps1` before relying on them for an actual release.
4. Start investigating the Settings-page stream-stop bug: trace the Settings open/close flow starting from `stream_manager.jsx`'s `onOpenSettings` and `settings_view.jsx`, and check whether Settings is unmounting the player/stream component or whether there's an explicit stop-stream call tied to navigation.
