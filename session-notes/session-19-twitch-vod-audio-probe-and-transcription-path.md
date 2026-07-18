# Session 19: Twitch VOD Audio Probe And Transcription Path

Date: 2026-07-12

## What Happened

We intentionally kept this separate from the app UI and built a proof-path first.

The original question was whether Twitch's newer VOD caption experience might give us a clean transcription path we could later surface in the app. Instead of wiring anything into Settings right away, this session focused on the safer long-term experiment: pull audio from a Twitch VOD first, then optionally hand that local audio file to the existing `transcribe-yt` workflow.

### 1. Built a standalone Twitch VOD audio probe script

- Added `scripts/probe_twitch_vod_audio.py`.
- The script accepts either a Twitch VOD URL or a numeric VOD ID.
- It resolves the VOD directly through Streamlink, prefers `audio_only`, and falls back to `audio` only if needed.
- Default behavior is a short probe sample (`--sample-seconds`, default `300`) so we can test quickly without downloading an entire VOD.
- `--full` skips sampling and extracts the whole VOD audio instead.
- Output goes to `temp/vod-audio-probe/` by default unless `--output-dir` is passed.

### 2. Added ffmpeg / ffprobe verification so the probe fails clearly

- The probe requires machine-available `ffmpeg` and `ffprobe`.
- Audio extraction uses `ffmpeg` to create a local `.m4a` file.
- Post-extraction validation uses `ffprobe` to confirm:
  - the file exists,
  - it contains audio,
  - it does not contain video,
  - duration is non-zero,
  - file size is non-zero.
- Failure messages are written to be explicit for bad VOD input, missing tools, unavailable streams, and restricted/deleted VODs.

### 3. Wired an optional handoff into the existing `transcribe-yt` repo

- `--transcribe` is opt-in.
- The default external workflow root for this probe is `C:\Users\redacted\Desktop\transcribe-yt`, overrideable with `--transcribe-yt-root`.
- The probe expects `transcribe-youtube.py` plus that repo's `.venv\Scripts\python.exe`.
- When transcription is requested, the probe calls the existing `transcribe-yt` environment rather than re-implementing Whisper in this repo.
- The script prints transcript output paths when it can detect them.

### 4. Added focused tests for the probe logic

- Added `tests/test_probe_twitch_vod_audio.py`.
- Coverage includes:
  - VOD ID / URL parsing,
  - stream selection preference for `audio_only`,
  - clear failure when no audio stream is exposed,
  - `ffprobe` validation behavior,
  - transcript path parsing,
  - missing `transcribe-yt` venv failure,
  - end-to-end flow orchestration through `run_probe(...)`,
  - CLI bad-input behavior.

## Important Files Changed

- `scripts/probe_twitch_vod_audio.py`
- `tests/test_probe_twitch_vod_audio.py`

## Current Git State

- Uncommitted files currently in the worktree:
  - `scripts/probe_twitch_vod_audio.py`
  - `tests/test_probe_twitch_vod_audio.py`
- No `twitch-viewer` UI, pywebview bridge, config schema, or app-facing API changes were made in this step.

## Things We Haven't Tried Yet / Still Pending

1. Run the probe against a real public Twitch VOD and confirm the actual Streamlink + ffmpeg path behaves the way the unit-tested code expects.
2. Run the `--transcribe` path end-to-end against a real extracted VOD audio sample and confirm the existing `transcribe-yt` environment produces usable transcript outputs.
3. Try `--full` against a real VOD to see whether full-length extraction is practical enough for the intended workflow.
4. Confirm how the probe behaves against restricted, subscriber-only, deleted, or otherwise unavailable VODs in real-world conditions.
5. Decide later whether app integration should:
   - call this probe logic directly,
   - inline the audio-extraction logic inside `twitch-viewer`,
   - or keep transcription delegated to the external `transcribe-yt` environment.
6. If the probe works well in practice, then we can revisit where this should live in the app UI and whether Settings is still the right temporary home.
