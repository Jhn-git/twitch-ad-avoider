# Session 23: Day-Scoped Recording History (Stages 1-3 of 5)

Date: 2026-07-18

## What Happened

Picked up directly from session 22's deferred item: live-verifying the post-stream-end clip fix. That verification succeeded (see section 1), but surfaced a second, more serious bug along the way - the real recording file on disk turned out to be silently corrupted across multiple days. Reporting that bug led the user to describe a bigger feature they actually wanted: the ability to scrub back through everything recorded **today** for a channel, even across app restarts, with gaps shown where nothing was recorded. That became a full 5-stage plan (Plan Mode, approved), and stages 1-3 were built, tested, and verified live in a browser before wrapping up for the night.

### 1. Live-verified the post-stream-end clip fix (closing out session 22)

Rather than waiting for a real stream to end, found `temp/recording_jg_darhk.ts` sitting idle from a prior test session (confirmed via `scripts/gui_test_support.find_running_app_pids()` that nothing was actively writing it). Extracted a clean 300s real segment from it, ran the *real* `create_clip()` (real ffmpeg, not mocked) against it twice - once simulating a mid-buffer scrub, once at the live edge - and visually compared extracted stills from both real output clips against independently-computed reference frames from the source. Both matched exactly (down to matching webcam overlay text). **Confirmed working with real footage**, not just unit tests.

### 2. Found a second bug: recording files were silently corrupted across sessions

While picking a clean extraction offset, found `temp/recording_jg_darhk.ts` had a Windows creation time of Jul 9 but was last written Jul 17 - an 8-day span - while `ffprobe` showed only ~5.55 hours of actual playable content, plus real `Non-monotonic DTS` / `duplicated MOOV Atom` errors from `ffmpeg` partway through the file.

**Root cause**: `_prepare_recording()` (`src/web_stream_service.py`) tried to `unlink()` the previous rolling `recording_<channel>.ts` on every `start()`, but only logged a warning if that failed - then silently opened the *same stale file* in append mode while still assigning a fresh `recording_start_time`. Any session that inherited a stale file this way would measure all its clip offsets from the wrong zero point.

### 3. Planned a bigger feature: day-scoped recording history

The user's actual ask: keep only *today's* recording per channel (auto-expire after 3 days - explicitly confirmed), let them scrub back through everything cached today even after closing/reopening the app, show gaps for stretches that weren't recorded (app closed), snap to the nearest recorded edge if they drag into a gap (explicitly confirmed), and know the *true* total stream length (Twitch's real broadcast start, not just whenever the app happened to start recording).

Went through full Plan Mode: an Explore pass confirmed no Range-header or segment/gap scaffolding existed anywhere to reuse, and a live empirical call to Twitch's public GQL endpoint (same anonymous endpoint `stream_preview.py` already used) confirmed `stream.createdAt` is a real, populated field. A Plan-agent review validated the architecture and flagged real risks (see Key Decisions). One more clarifying question to the user produced a "middle ground" design for scrubbing within the still-live session: prompt-and-confirm rather than fully automatic or fully blocked.

Final 5-stage plan written to `.claude/plans/hey-ive-been-using-fluttering-zebra.md`:
- **Stage 1** (done): day-scoped storage + retention + the bug fix itself.
- **Stage 2** (done): true stream start time via GQL.
- **Stage 3** (done): gap-aware seek bar UI, static index only.
- **Stage 4** (not started): actually playing back past/closed segments (new local video serving, real ffmpeg HLS conversion).
- **Stage 5** (not started): user-confirmed scrub-back within the still-recording session.

### 4. Built Stage 1: day-scoped storage, retention, and the bug fix

New `src/recording_index.py`: pure, no-mocking-needed module (`RecordingSegment`/`DayIndex` dataclasses, `load_index`/`save_index` with atomic temp-file+`os.replace` writes, `start_segment`/`close_segment`/`close_dangling_segments` (auto-closes a segment left open by a crash, using the raw file's own mtime - the same trick behind the session-22 clip fix), `resolve_timestamp` (maps an absolute timestamp to a segment+offset, snapping to the nearest edge if it lands in a gap), `purge_old_days`). Every function takes `now`/times explicitly - no internal `datetime.now()` calls, so none of it needs time-mocking.

`web_stream_service.py`'s `_prepare_recording()` was rewritten to build `temp/<channel>/<date>/`, purge old days for that channel, load/create `index.json`, auto-close any dangling segment, and start a brand-new uniquely-named `raw_<id>.ts` file every single call - never reusing or appending to a previous file. This eliminates the corruption bug **by construction**, not by hardening the old retry/delete logic. Segment-closing is hooked into `stop()` and the two genuinely-terminal branches of `_recording_loop` (retries exhausted / unrecoverable error) - a reconnect within the same live session does *not* close the segment, since it's still the same continuous recording.

**Caught and fixed a real regression during this stage**: an initial version ran a "purge every channel's old recordings" sweep directly in `WebStreamService.__init__()`. Since nearly every test in `test_web_stream_service.py` constructs a real `WebStreamService` in `setUp()`, this meant simply *running the test suite* would touch the real on-disk `temp/` folder on every run - exactly the kind of collision `scripts/gui_test_support.py` was built to prevent, this time self-inflicted. Fixed by moving the sweep out of the constructor into an explicit `purge_expired_recordings()` method, called once from real app startup (`TwitchViewerAPI.__init__`) instead - constructors shouldn't have filesystem side effects, and now instantiating the service for a test can never touch real files just by existing.

### 5. Built Stage 2: true stream start time

Extended `stream_preview.py`'s existing anonymous Twitch GQL query (used for preview thumbnails/titles) to also request `stream { createdAt }` - verified live against the real endpoint before trusting it (see section 3). `web_stream_service.py` fetches and stores this into `index.json.stream_created_at` on every `start()`, but only overwrites the stored value when a fresh fetch actually succeeds (an offline channel or network hiccup on a later restart shouldn't erase an already-known good value). If it's never available at all, `get_recording_segments` (Stage 3) falls back to the earliest recorded segment's own start time at read time, rather than baking a fabricated fallback into storage.

### 6. Built Stage 3: gap-aware seek bar UI (visual + data plumbing, not yet interactive playback)

New backend: `WebStreamService.get_recording_segments(channel)` / `TwitchViewerAPI.get_recording_segments()` return today's segment index (with the open segment's end synthesized as "now").

New frontend: a slim **day-timeline strip** renders under the existing seek bar (`gui_web/components/video_stage.jsx`), showing today's recorded segments as colored bands (bright accent for the currently-recording one, dimmer for past/closed ones) against the full day's span, with visible gaps for stretches the app wasn't running. Pure timeline math (`computeTimelineBounds`, `timestampToRatio`, `ratioToTimestamp`, `findSegmentAt`, `currentSegment`) lives in `gui_web/helpers.jsx` alongside the app's other shared helpers.

Clicking the strip is real, not just decorative, within what's actually possible today: clicking inside the *current* segment's band, if the target is still within hls.js's live buffer, seeks there directly (reusing the exact "seconds behind live" math `handleClip` already uses). Clicking a *past* segment or an actual gap shows an honest toast ("coming soon" / "nothing was recorded then") rather than silently failing or pretending to work - Stage 4 is what will make past segments truly playable.

## Key Decisions

- **Retention**: no cap on today's total size; a channel's whole day-folder is deleted once it's more than 3 days old (user's explicit call).
- **Gaps**: dragging into a gap snaps to the nearest recorded edge, never lets the thumb rest inside a gap (user's explicit call).
- **Live-session scrub-back is deliberately split from past-session scroll-back.** Past (closed) sessions become fully scrubbable via Stage 4 with no extra prompt. The *still-recording* session keeps today's ~15-minute hls.js buffer behavior by default - going further back within it will (Stage 5, not yet built) show a confirm prompt rather than converting automatically in the background. This was a user-proposed middle ground after being asked to choose between "always capped at 15 min" and "always unlimited even while still recording" - they preferred neither extreme.
- **Lazy, on-demand ffmpeg HLS re-segmenting (`-c copy -f hls`) for past segments, not raw-`.ts` byte-range serving.** A Plan-agent review confirmed there's no existing Range-header scaffolding to build on, and that hand-rolled byte-range slicing would need its own keyframe/PTS indexing to avoid corrupt decode starts - letting ffmpeg's HLS muxer do real segmenting is barely more work and guarantees clean, independently-decodable chunks.
- **Lazy VOD conversion only ever targets already-*closed* segments** (Stage 4 scope), never the file the recording thread is actively appending to - sidesteps a real race condition (reading a file mid-write) entirely by construction, rather than trying to detect/handle it.
- **The existing `behind_live_seconds` clip API stays untouched.** Stage 4 will add a new, additive `target_timestamp` parameter for clipping from a resolved past segment, rather than repurposing or changing the contract that was just shipped and tested in session 22.

## Files Changed

- `src/recording_index.py` (new) - day-scoped segment bookkeeping, pure functions.
- `src/web_stream_service.py` - day-scoped `_prepare_recording()`, segment-closing hooks, `purge_expired_recordings()`, `get_recording_segments()`, true-stream-start resolution.
- `src/stream_preview.py` - `stream_created_at` field, GQL query extended.
- `src/webapi.py` - `get_recording_segments()` wrapper, `purge_expired_recordings()` called once at real startup.
- `gui_web/components/video_stage.jsx` - day-timeline strip, click-to-seek within what's currently reachable.
- `gui_web/components/stream_manager.jsx` - fetches/polls `get_recording_segments`, passes it down.
- `gui_web/helpers.jsx` - new timeline-math pure functions, `demoApi()` stub.
- `gui_web/index.html` - `.day-timeline` / `.day-timeline-segment` styles.
- `tests/test_recording_index.py` (new), plus new tests in `tests/test_web_stream_service.py`, `tests/test_webapi.py`, `tests/test_stream_preview.py`.
- `TODO.md` - added the clip-button UI bug and the remaining Stage 4-5 work as new top priorities, plus a favorites-auto-refresh-on-add item (all from this session's closing conversation - see section 7).

Also: everything sitting uncommitted from prior sessions (the session-21 sound-restoration work, the session-19/20 VOD-transcription-probe work) plus all of tonight's work was committed by the user directly, outside this conversation, for backup purposes (private repo) - not something I did or was asked to do.

## Verification

- Full backend suite: **159 passed**. `black`/`flake8`/`mypy` clean on every file touched this session (the two pre-existing lint items in `tests/test_webapi.py` and `tests/test_probe_twitch_vod_audio.py` predate this session, confirmed unrelated to anything touched here).
- Confirmed via direct testing that instantiating `WebStreamService` in a test, and running the new day-scoped-recording tests, never touches the real `temp/` folder - checked before and after full test runs while the user's real app was actively recording a different channel in the background the whole time.
- Stage 3's frontend was verified live in a browser (not just read for syntax): loaded the app's existing demo-mode dev server, confirmed zero console errors, then directly exercised the new pure timeline-math functions (`computeTimelineBounds`, `ratioToTimestamp`, `findSegmentAt`, etc.) against a synthetic day's worth of segments/gaps to confirm the math is correct, and visually confirmed the `.day-timeline` CSS renders as intended (distinct current/past/gap bands) by injecting sample markup matching the real component's output.
- Stage 4/5 are **not built yet** - nothing to verify there.

## Current Progress

- Session 22's deferred item (live-verify the clip fix) is fully closed out.
- A second, previously-unknown bug (multi-session file corruption) was found, root-caused, and fixed as part of Stage 1 - by construction, not a patch.
- Stages 1-3 of the new day-scoped recording history feature are built, tested, and verified (backend fully unit-tested; frontend logic and visuals directly verified in a browser).
- Stages 4-5 (making past segments actually playable, and the confirm-before-loading path for the live session) are designed but not started - now the #2 TODO priority.
- Two additional items were captured in `TODO.md` at the user's request but not implemented: the Clip button's disconnected-looking split-button UI + dropdown-overflow-off-screen bug (now #1 priority), and refreshing a favorite's live status immediately after adding it rather than waiting for the next scheduled refresh (#3 priority, boot-time auto-refresh already existed).

## Things We Haven't Tried Yet / Still Pending

1. **Stage 4** - lazy ffmpeg HLS conversion of closed segments, new local-file-serving proxy routes, wiring the day-timeline's click handler to actually swap playback sources into a past segment, and the additive `target_timestamp` clip parameter.
2. **Stage 5** - the confirm-before-loading snapshot conversion for scrubbing deep into the still-live session.
3. **The Clip button UI fix** (TODO #1) - didn't get far enough to fully root-cause the "disconnected pill" look before being asked to just capture it as a TODO item instead; worth a fresh look at `.clip-split`/`.clip-menu-button` alignment in `gui_web/index.html` next time, plus adding viewport-aware flip-upward positioning to `gui_web/components/dropdown.jsx`.
4. **Favorites auto-refresh on add** (TODO #3) - `addFavorite` in `stream_manager.jsx` doesn't check the new channel's live status immediately.
5. Live-verifying Stage 4/5 against a real channel once built, the same way Stage 3 was visually verified tonight.

## Skills

No new skills built this session. The `pywebview-gui-test` skill's guidance on test isolation (via `scripts/gui_test_support.py`, built last session) directly caught the self-inflicted `WebStreamService.__init__` regression described in section 4 above - a good example of that skill's file-collision lesson paying off immediately, not just for live-testing but for the ordinary automated test suite too.
