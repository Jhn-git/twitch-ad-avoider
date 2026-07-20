# Session 27: Merged Scrub Bar And Demo Harness Fix

Date: 2026-07-19

## What Happened

User was looking at a screenshot of the Stream Manager and said the second green bar under the player (the day-timeline recording-history strip added in session-23) "feels redundant" next to the live seek bar above it, and asked what to do about it. Worked through it in plan mode: explored the actual two bars' code and data sources, asked the user to choose between finishing the unbuilt Stage 4/5 playback, restyling it, or hiding it - user instead asked for a fourth option not on the list: merge the two bars into one. Investigated the real constraint (the two bars operate on very different time scales - a ~15 min live buffer window vs. an hours-long recording session) and designed a single-bar solution around that, then implemented, verified, and fixed the demo test harness so this kind of thing is actually testable in the future.

### 1. The merge design

Replaced the stacked `.seek-row`/`.seek-track` (live DVR seek bar) and `.day-timeline` (session-history strip) with one `.scrub-track`:
- Background layer: the same session-scaled segment bands as before (dim = past, muted green `--accent-soft` = currently recording), now called `.scrub-segment`.
- Foreground layer: a new `.scrub-live-window` - a solid-green (`--accent`) highlighted sub-region showing exactly which part of the session is actually buffered and scrubbable right now. This is what you drag; it visually pops out of the muted current-segment band behind it.
- Since a 15-minute buffer can be a sliver of an hours-long session, the highlight has a **10%-minimum-width floor** anchored to the live edge (`MIN_LIVE_WINDOW_PCT` in `video_stage.jsx`), so it never shrinks to an unusable pixel. Tradeoff, stated to the user up front: past a certain session length this is no longer strictly proportional - its job is to stay draggable, not to be a precise ruler.
- Clicking outside the highlight (past segments/gaps) still shows the existing "coming soon" toasts - Stage 4/5 real playback of old segments was explicitly kept out of scope.

### 2. A math bug caught during implementation

The approved plan's floor formula was `liveLeftPct = Math.max(rawLeft, 100 - MIN_LIVE_WINDOW_PCT)`. Working through it by hand while implementing showed this was backwards - `Math.max` would let a long session's raw left position (which is *already close to 100%*, e.g. 93.75%) win over the floor, giving a highlight *narrower* than the intended minimum instead of wider. Fixed to `Math.min(rawLeft, 100 - MIN_LIVE_WINDOW_PCT)`, which correctly caps how close to the right edge the highlight's left boundary can get. Confirmed against the real shipped code afterward (see Verification) with a synthetic 4-hour-session/15-minute-buffer scenario: floors to exactly 90%/10% as intended.

### 3. Demo harness fix (this session's second ask)

The user said the merged bar "appears to be working but it looks a little bad" and asked to fix the demo test harness before wrapping up, so future sessions can actually see and interact with the video/scrub-bar area during testing. Root problem: `demoApi()` in `gui_web/helpers.jsx` never set a `playback_url` on `start_stream`, and `get_recording_segments` always returned an empty segment list - so in `?demo=1` mode the `<video>`/scrub-bar area never rendered at all, regardless of any frontend code changes. Today's own verification work had to route around this with temporary JS-injected stubs (see Verification) rather than testing the real code path.

Fix, scoped to stay dev-only and never bloat the shipped app:
- `scripts/run_demo_server.py` (new) replaces the old raw `python -m http.server 8743 --directory gui_web` launch command. On first run it generates a small (~60s, silent, ~7.7MB) local HLS test clip via `ffmpeg` - a `testsrc2` color-bar pattern with a burned-in elapsed-time readout (`drawtext`, `%{pts\:hms}`) so a specific scrub position is easy to eyeball - into `gui_web/demo-assets/`, then serves `gui_web/` exactly as before.
- `gui_web/demo-assets/` is **gitignored** (added to `.gitignore`) and **excluded from the PyInstaller build** (`scripts/twitchadavoider.spec`'s `collect_tree` now takes a `skip_dirs` param, used to skip `demo-assets`) - it's generated test fixture data, never committed or shipped, regenerated fresh on whichever machine runs the demo.
- `.claude/launch.json`'s `gui-web-demo` config now runs the new script instead of the raw `http.server` command.
- `demoApi()` in `helpers.jsx`: `start_stream` now sets `playback_url: "demo-assets/stream.m3u8"`; `get_recording_segments` now returns a synthetic-but-realistic session (a closed segment from 4h-2.5h ago, a gap, then a still-recording current segment starting 2h ago) computed off `Date.now()` so it's always fresh.

## Key Decisions

- Chose a single VOD-style local test clip (`-hls_playlist_type vod`) over trying to simulate a genuinely live/growing stream. Reasoned that the app's own scrub-bar code drives everything off `video.buffered`/`currentTime` directly rather than relying on hls.js's live-vs-VOD internals, so a short VOD clip exercises the same code paths - confirmed true in Verification (the existing `maybeAutoCatchUp`/`syncToLiveEdge` live-edge-sync logic from session-25 actually fired and worked correctly against it, unprompted).
- Generated the demo asset on-demand at first run rather than committing a binary video file to the repo, and defended that in two places (`.gitignore` + PyInstaller spec `skip_dirs`) rather than one, since the spec's `collect_tree` sweeps `gui_web/` recursively with no filtering and would otherwise silently bundle any local demo-assets/ a developer happened to have on disk into a real build.
- Kept the demo server's existing root (`--directory gui_web`, `index.html` at `http://localhost:8743/`) unchanged rather than restructuring to serve the repo root - lower disruption to the existing `gui-web-demo` launch config and any muscle memory/skill docs already built around that URL shape.
- Did not touch the visual styling beyond what the merge itself required (segment/highlight colors were chosen from existing `--accent`/`--accent-soft`/`--ink-4` theme variables, not new ones) - user explicitly deferred "looks a little bad" to a separate TODO item rather than asking for a design pass now.

## Files Changed

- `gui_web/components/video_stage.jsx` - merged seek/day-timeline render block into one `.scrub-track`; new `MIN_LIVE_WINDOW_PCT` constant; `liveWindowRef`/`scrubTrackRef`/`scrubFillRef`/`scrubThumbRef` refs (renamed/added, `dayTimelineRef`/`seekTrackRef`/`seekFillRef`/`seekThumbRef` removed); shared `timelineBounds` memo (was duplicated inline in two places); `updateSeekVisuals` rewritten to also compute and write the live-window's position via wall-clock conversion + floor; `segmentsIndexRef`/`timelineBoundsRef` added so that computation doesn't destabilize `updateSeekVisuals`'s identity (segments refetch every 30s while watching - including them as a real dependency would have torn down and reattached hls.js on every poll); `seekFromEvent` rect source moved from the track to the live-window sub-region; `handleDayTimelineClick` retargeted to the merged track ref (logic unchanged).
- `gui_web/index.html` - CSS: `.seek-row`/`.seek-track`/`.day-timeline`/etc. replaced with `.scrub-row`/`.scrub-track`/`.scrub-segment`/`.scrub-live-window`/`.scrub-fill`/`.scrub-thumb`.
- `scripts/run_demo_server.py` (new) - demo HLS clip generator + static file server.
- `gui_web/helpers.jsx` - `demoApi()`'s `start_stream` and `get_recording_segments` now return real/realistic data instead of empty placeholders.
- `scripts/twitchadavoider.spec` - `collect_tree` gained a `skip_dirs` parameter, applied to skip `demo-assets` when bundling `gui_web/`.
- `.gitignore` - added `gui_web/demo-assets/`.
- `.claude/launch.json` - `gui-web-demo` now runs `scripts/run_demo_server.py` (gitignored itself, not tracked in git, so this change only exists locally).
- `TODO.md` - added a Backlog item for the visual-polish follow-up, and a Recently Completed entry for today.

## Verification

**Scrub-bar merge** - browser-only demo mode, driven through actual shipped code, not reimplemented logic:
- Confirmed exactly one `.scrub-track` renders (`document.querySelectorAll('.scrub-track').length === 1`), with zero leftover legacy `.seek-track`/`.day-timeline` elements.
- Faked a 4-hour session with a 15-minute buffered window (via `Object.defineProperty` stubs on `video.buffered`/`currentTime`, since demo mode had no real playback yet at that point) and dispatched a real `timeupdate` event: `updateSeekVisuals` correctly computed the live-window at `left: 90%, width: 10%` - matching the floor calculation by hand.
- Clicking a past segment (outside the highlight) correctly fired the existing "coming soon" toast, with a 50ms-delayed DOM read needed since `get_page_text`'s default extraction missed the toast (renders outside `<main>`).
- Clicking/dragging inside the live-window correctly updated `video.currentTime`/fill/thumb *and* did not also fire the outer track's toast handler - confirms the `stopPropagation()` on the live-window's own `onClick` is doing its job (a `click` event bubbles after `pointerup` as a separate event from `pointerdown`, so this needed its own explicit stop, not just one on `pointerdown`).
- "Go Live" correctly re-snapped the highlight/thumb back to the live edge.
- Screenshots timed out repeatedly during this first pass (an apparent environment/tooling issue, unrelated to the app - confirmed via `read_console_messages` showing no page errors) - worked around by decompiling verification into pure DOM/computed-style/event-dispatch checks instead of visual screenshots.

**Demo harness fix** - re-verified everything above a second time, this time against the real generated stream with no stubbing:
- `document.querySelector('video').currentSrc` was a real `blob:` URL (hls.js actually parsed and loaded the local `.m3u8`/`.ts` files), `readyState: 4` (fully loaded), `video.buffered` genuinely populated (`bufferedEnd: 59.999999` for the 60s clip).
- The session-25 auto-catch-up logic (`maybeAutoCatchUp`/`syncToLiveEdge`) fired on its own and correctly snapped playback from 0 to the live edge, then rode it out to the natural end of the clip - the first time that logic has been exercised against genuine `video.buffered`/`timeupdate` events in this repo (session-25's own notes flagged this as unverified: "This did not exercise real hls.js buffered-timing behavior").
- Real pointer-drag on the live-window genuinely seeked the real `<video>` element (`currentTime` moved to 11.999999s for a click at the 20% mark of a 0-60s buffered range) - not a stub.
- Screenshot tooling worked on the second attempt (fresh browser tab) and visually confirmed: one merged bar, the color-bar test pattern with a legible burned-in timestamp overlay (`drawtext` worked despite an ffmpeg fontconfig warning at generation time), thumb positioned correctly.
- Zoomed into the bar itself: this is where the "looks a little bad" feedback likely comes from - the three-way color distinction (dim past / muted-green current-but-not-buffered / solid-green live-window) is hard to read at the bar's current ~12px height and low-opacity muted tone, especially at a glance. Concrete starting point for the deferred visual-polish TODO item.

## Current Progress

- The scrub-bar merge is fully implemented and verified. **It's already committed** - `git log` shows it's part of the current HEAD commit (`0ce906d`, "refactor: Update TODO list and enhance video stage component for improved live buffer handling"). This assistant did not run `git commit` at any point this session (per standing instructions, only commits when explicitly asked) - the working tree simply already matched HEAD for `gui_web/components/video_stage.jsx` and `gui_web/index.html` by the time this was checked, meaning some automatic checkpoint mechanism in this environment committed it along the way. Worth the user's awareness since the commit message doesn't mention the scrub-bar merge specifically (it's a generic message pre-dating today's actual work, probably auto-generated/reused by that mechanism) - may be worth a manual `git commit --amend` or a follow-up commit with a more accurate message if the user wants the history to read cleanly, but not done here since amending/rewriting history wasn't asked for.
- The demo-harness fix is **not yet committed**: `git status` shows `.gitignore`, `TODO.md`, `gui_web/helpers.jsx`, and `scripts/twitchadavoider.spec` modified, plus `scripts/run_demo_server.py` untracked. `.claude/launch.json` is also changed but is itself gitignored, so it won't show up in `git status` at all - that's expected, not an oversight.
- `gui_web/demo-assets/stream.m3u8` + 15 `.ts` segments already exist on disk locally (generated during testing) - harmless, gitignored, will just get reused (not regenerated) next time the demo server starts.

## Things We Haven't Tried Yet / Still Pending

1. **Visual polish of the merged bar** - user's explicit ask, deferred to `TODO.md`. No specific direction given yet beyond "looks a little bad" - worth asking for specifics (bar height? color contrast? the muted-green current-segment tone being too subtle against the dark theme? something else entirely) before making changes, rather than guessing.
2. **Real-Twitch-stream verification** - everything today was verified against the local demo clip (60s, fully buffers almost instantly) or hand-constructed stubs. The live-window's behavior against a genuinely growing live buffer (segments arriving continuously, `bufferedEnd` advancing in real time rather than being static) has not been watched firsthand by the assistant. Worth a quick real-app glance next time the user is actually watching a stream, similar to how session-25's timing fix was ultimately confirmed by the user's own live testing.
3. **Commit history cleanliness** - see Current Progress above. The scrub-bar merge landed under a pre-existing/generic commit message via an apparent auto-checkpoint mechanism, not a deliberate commit. Not fixed since it wasn't asked for; flagging in case the user wants the history to be more descriptive later.
4. **Whether the auto-checkpoint mechanism is expected/desired** - not investigated further (no `.claude/settings.json` found in this repo to explain it; may be a global/user-level setting or a feature of this specific coding environment). Not something to chase down uninvited, but worth the user knowing it exists if they weren't already aware, since it committed working-tree changes without an explicit `git commit` request from either the user or this assistant.
5. **Screenshot-tool timeouts** seen early in this session (unrelated to any app code, resolved on their own by the second browser tab/pass) - no action taken, just noting in case it recurs and looks alarming next time.

## Skills

No new skill created this session, but two are worth flagging for next time:

- **`run` / `pywebview-gui-test`** (existing) were used for demo-mode testing, but neither currently documents the pattern used repeatedly today - stubbing `video.buffered`/`currentTime` via `Object.defineProperty` and dispatching synthetic `timeupdate`/`pointerdown`/`pointerup`/`click` events to exercise the *real* player component logic without a real stream. Now that the demo harness has a real local clip (this session's fix), that specific stubbing trick is less necessary going forward, but the general technique (verify via DOM/computed-style reads and dispatched events when screenshots aren't available or the interaction is hard to drive visually) is likely to come up again for other interactive-but-hard-to-screenshot UI. Not worth a dedicated skill on its own yet - just a technique worth remembering.
- Consider documenting the new `scripts/run_demo_server.py` / `gui_web/demo-assets/` pattern in `AGENTS.md` or the `pywebview-gui-test` skill itself, so future sessions know the demo harness now serves a real stream and don't accidentally reintroduce the old empty-player gap (e.g., if `demoApi()` is refactored later and someone forgets to keep `playback_url` wired up).
