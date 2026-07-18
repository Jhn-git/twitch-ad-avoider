# Session 20: Twitch VOD Probe Debug, Silence Offset, And Progress Reporting

Date: 2026-07-12

## What Happened

We picked up from the new standalone VOD probe and debugged it against a real Twitch VOD instead of moving on to app integration too early.

The main test VOD today was:

- `https://www.twitch.tv/videos/123456789`

### 1. Fixed the first real Streamlink compatibility bug

- The probe originally failed on a real VOD with:
  - `Error: Could not fetch VOD streams. The VOD may be deleted, restricted, or require a subscription. Details: 'tuple' object has no attribute 'streams'`
- Root cause: this checkout is using `streamlink 8.4.0`, where `Streamlink.resolve_url()` returns a tuple like `(plugin_name, plugin_class, resolved_url)`, not a ready-to-use plugin instance.
- Fix: updated `scripts/probe_twitch_vod_audio.py` to instantiate the plugin when Streamlink returns the tuple-shaped result, while still tolerating a plugin-like object if that is ever returned in another environment.
- Added regression coverage for that exact tuple-return case in `tests/test_probe_twitch_vod_audio.py`.

### 2. Fixed the ffmpeg extraction path for Twitch's VOD audio stream

- After the Streamlink fix, the next failure was during extraction:
  - `OSError: [Errno 22] Invalid argument`
- Root cause: the Twitch VOD audio stream here is HLS/fMP4, and the probe's stdin pipe approach to ffmpeg was the fragile part.
- Confirmed that ffmpeg can read the Streamlink-selected HLS URL directly without that pipe issue.
- Fix: the probe now prefers using the stream object's resolved URL (`url` / `to_url()`) as ffmpeg input, and keeps the old pipe path only as a fallback when no direct URL exists.
- Verified this against the real VOD, including the original 300-second sample path.

### 3. Confirmed the "empty transcript" problem was caused by silent early VOD audio, not a broken probe

- After the extraction fix, the saved sample and transcript outputs still looked wrong at first because the audio sounded empty and the transcript files had nothing useful in them.
- Verified with `ffprobe` + `ffmpeg` `volumedetect` that the saved first 300 seconds were effectively silent (`-91.0 dB`).
- Sampled later offsets from the same VOD and found:
  - `0s`, `300s`, `600s` were effectively silent
  - `900s` and later had normal audio levels
- This means the probe was working, but the beginning of this specific VOD was not a good transcription test target.

### 4. Added `--start-seconds` so we can skip silent intros / muted sections

- Added a new CLI option:
  - `--start-seconds <n>`
- The probe can now start later in the VOD instead of always sampling from second zero.
- Output filenames now include the start offset so later test files do not overwrite the original zero-offset ones.
- Real successful test:
  - `.\.venv\Scripts\python.exe scripts\probe_twitch_vod_audio.py https://www.twitch.tv/videos/123456789 --sample-seconds 30 --start-seconds 900 --transcribe`
- That later-start sample produced real speech audio and a populated transcript instead of silence.

### 5. Added much better progress output for long runs

- The probe now prints:
  - source duration when it can detect it,
  - planned output duration,
  - audio output path,
  - transcript output directory,
  - live download progress during ffmpeg extraction,
  - live transcription status/progress during the `transcribe-yt` handoff.
- ffmpeg progress now shows useful fields like current extracted time, approximate percent, output size, and speed.
- `transcribe-yt` already had internal progress/status callbacks available through `run_transcription(...)`, but our original subprocess call hid all of that until completion.
- Fix: the probe now launches a small wrapper inside the `transcribe-yt` venv, hooks its progress callback, and streams those events back to the terminal in real time.
- Also had to fix a small dynamic-import quirk by registering the loaded `transcribe-youtube.py` module in `sys.modules` before executing it.

### 6. Verified the improved end-to-end behavior

- Focused probe tests now pass:
  - `.\.venv\Scripts\python.exe -m pytest tests\test_probe_twitch_vod_audio.py`
  - Result: `20 passed`
- Real VOD run with progress reporting and later-start transcription succeeded:
  - `.\.venv\Scripts\python.exe scripts\probe_twitch_vod_audio.py https://www.twitch.tv/videos/123456789 --sample-seconds 30 --start-seconds 900 --transcribe`
- Current best full-VOD test command for this VOD:
  - `.\.venv\Scripts\python.exe scripts\probe_twitch_vod_audio.py https://www.twitch.tv/videos/123456789 --full --start-seconds 900 --transcribe`

### 7. Fixed the later wrapper crash and added a way to reuse an already-downloaded full audio file

- After the progress-reporting work landed, a later full-VOD run still failed during the `transcribe-yt` handoff with the `dataclass` / `sys.modules.get(cls.__module__)` traceback from the dynamic import wrapper.
- Confirmed the current wrapper fix in `scripts/probe_twitch_vod_audio.py` registers the loaded `transcribe-youtube.py` module in `sys.modules` before `exec_module(...)`, and the current sample transcription path now gets past that old crash.
- Added `--reuse-existing-audio` so an already-downloaded extracted audio file can be reused for transcription instead of forcing another long ffmpeg extraction first.
- Useful resume command for the already-existing zero-offset full file:
  - `.\.venv\Scripts\python.exe scripts\probe_twitch_vod_audio.py https://www.twitch.tv/videos/123456789 --full --transcribe --reuse-existing-audio`
- Note: the tool timeout during Codex verification is now about total transcription runtime on a long file, not the old wrapper import crash.

## Important Files Changed

- `scripts/probe_twitch_vod_audio.py`
- `tests/test_probe_twitch_vod_audio.py`

## Current Git State

- Uncommitted work currently in the worktree:
  - `scripts/probe_twitch_vod_audio.py`
  - `tests/test_probe_twitch_vod_audio.py`
- No `twitch-viewer` app UI, pywebview bridge, config schema, or app-facing API changes were made in this session.

## Things We Haven't Tried Yet / Still Pending

1. Run the full real workflow on this VOD long enough outside Codex timeout pressure to confirm the multi-hour transcription finishes cleanly, especially for:
   - `--full --transcribe --reuse-existing-audio`
   - and, if we want to skip the silent intro, `--full --start-seconds 900 --transcribe`
2. Test how the probe behaves on other real VODs that do **not** have a long silent intro, so we can tell whether `--start-seconds` should stay a manual troubleshooting tool or become something smarter later.
3. Test more real-world failure cases such as subscriber-only, deleted, restricted, or geoblocked VODs and make sure the resulting error messages are still clear.
4. Decide later whether the app should expose a manual start offset, auto-detect long silence, or leave this as probe-only/dev-only behavior.
5. Decide later whether `twitch-viewer` should eventually:
   - call this probe logic directly,
   - inline the audio extraction/transcription orchestration,
   - or keep using the external `transcribe-yt` environment as the runtime boundary.
6. Commit the current probe/test changes once we are happy with this checkpoint.
