# Session 30: Clip Editor Boundary And File-Lock Investigation

Date: 2026-07-24

## What Happened

- The recent-clip editor and anchored five-second post-roll workflow were implemented in
  `514e552`.
- The trim bar was then corrected in `5ff3d88` so both handles use one fixed timeline,
  cannot cross, and show the selected duration in the center.
- A real saved clip,
  `jg-darhk-20260724-202635-9-fuckin-hours.mp4`, appeared to lose the desired beginning
  even though the boundary looked correct in the editor.
- The installed app repeatedly reported:
  `Could not replace the open clip file: [WinError 5] Access is denied`.
- A second live attempt at `20:48:23` reproduced the replacement error before completing
  the full post-roll/editor flow. Its drawer showed a playable preview and a selected
  `Start 0:01.5`, `End 0:06.1` range.

## Confirmed Evidence

- The affected output is `6.871s` long at 1080p60.
- Audio matching placed its first content at approximately `14.58s` in the retained raw
  recording, with correlation `0.963`.
- A timestamped transcript placed the final word `hours` at approximately
  `13.92-14.44s`, so the output genuinely begins just after the titled moment.
- Repeated FFmpeg seek tests from `8.0s` through `14.5s` landed within `0.01s` of their
  requested source positions. The frame-accurate final renderer itself does not appear
  to be drifting.
- The app Activity panel recorded this sequence:

  - `20:26:36`: safety clip saved.
  - `20:26:48`: automatic replacement failed because the clip was open.
  - `20:28:08`: the titled edit was saved.

- Similar replacement failures occurred again around `20:39` and `20:48`, so the file
  lock is repeatable rather than isolated.
- The raw recording was still present under
  `temp/jg_darhk/2026-07-24/` during the investigation.

## Important Correction

The earlier conclusion that the editor simply lacked the beginning is incomplete. Jhn
confirmed that the desired beginning was visible and playable in the preview before
saving. If it was visible there, the editor did have those frames.

The leading explanation is now a preview-coordinate mismatch:

1. The immediate safety clip uses fast input seeking plus stream copy (`-ss` and
   `-c copy`).
2. A stream-copy output can begin at the preceding video keyframe and visibly contain a
   few seconds before the requested logical start.
3. The backend nevertheless records `preview_start_seconds` as the requested
   `safety_start`, not the safety file's actual first displayed frame.
4. The automatic frame-accurate post-roll replacement should remove this ambiguity, but
   it fails because the browser is currently playing the same output file Windows is
   asked to replace.
5. Save then translates the handle position using the assumed logical preview start and
   performs an accurate transcode from a later source position. This would explain why
   the preview showed the full moment but the output began roughly a keyframe interval
   later.

This explanation fits the current evidence but has not yet been directly reproduced.

## Relevant Code

- `src/web_stream_service.py:379` calculates the safety `start_offset`.
- `src/web_stream_service.py:382-410` creates the safety clip with fast seeking and
  stream copy.
- `src/web_stream_service.py:449-452` assigns the requested safety bounds and points
  `preview_path` at the replaceable output file.
- `src/web_stream_service.py:534-535` converts editor-relative bounds back into source
  bounds.
- `src/web_stream_service.py:884-963` runs the automatic post-roll job.
- `src/web_stream_service.py:1102-1138` creates the expanded editor preview.
- `src/web_stream_service.py:1144-1169` renders and atomically replaces the final clip.

## Things We Haven't Tried Yet

1. Recreate the immediate safety stream-copy command against the retained recording and
   measure its actual first decoded frame/audio sample versus `safety_start`.
2. Log the exact clip descriptor sent to the drawer and the exact
   `save_clip_edit(start_seconds, end_seconds)` arguments from a real attempt.
3. Compare the preview's visible frame at handle time zero with the raw source position
   the backend believes is time zero.
4. Serve a separate temporary preview copy from the moment the drawer opens, then verify
   that Windows can replace the untouched safety output while the preview is playing.
5. Test whether explicitly detaching/closing the preview before replacement releases the
   lock, although a separate immutable preview is likely the cleaner design.
6. Make post-roll failure still build a usable raw-context preview, or disable Save and
   offer Retry rather than allowing an unverified coordinate mapping.
7. Add automated coverage for an open Windows media handle and for keyframe pre-roll in a
   stream-copy safety clip.
8. Repeat real 30/60/120/300-second live clip acceptance after the lock and coordinate
   issues are fixed.

## Recommended Resume Plan

1. Prove or disprove the keyframe-offset hypothesis with the exact safety command.
2. Change the drawer to play a distinct temporary preview, never the MP4 that background
   work will atomically replace.
3. Ensure the backend derives selection coordinates from the preview's actual media
   origin, or make every editor preview frame-accurate before it becomes editable.
4. Preserve the safety output on every failure, but prevent saving from an unverified
   preview mapping.
5. Add diagnostic logs and regression tests before another live acceptance run.

## Verification And Workspace State

- Before this note, the repository was clean at `5ff3d88`.
- The earlier full suite passed: `192 passed, 65 subtests passed`.
- MyPy passed for all 14 source files.
- The investigation made no code changes. Only this session note was added.
- Temporary audio/transcription probes were removed after collecting the measurements.

## Non-Technical TLDR

The editor really did show the missing beginning, so Jhn did not simply place the handle
wrong. The most likely problem is that the quick preview and the final save disagree
about where time zero is, while a separate Windows file-lock error prevents the app from
correcting that preview automatically. Next time, first prove that timing mismatch, then
make the preview use its own temporary file so the full process can finish reliably.
