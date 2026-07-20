# TODO / Feature Backlog

Ordered by priority. Not started unless noted.

## Priority

1. **Remember player volume and avoid starting at full volume**
   - User-observed 2026-07-18: the app appears to start playback at full volume, which is too loud.
   - Preferred behavior: remember the last volume the user had set when the app was previously open.
   - Fallback behavior: if no previous volume exists yet, start the player around 20% volume instead of 100%.
   - Likely touch points are `gui_web/components/video_stage.jsx` for reading/applying `video.volume`, and settings/UI-state persistence through `gui_web/app.jsx`, `gui_web/components/stream_manager.jsx`, `src/config_manager.py`, and `src/webapi.py`.

2. **Give pinned live streamers a distinct highlight color**
   - Pinned favorites are more important than normal favorites because they sit above the regular list, so their live glow/highlight should read as a higher-priority state instead of using the same green treatment as every other live favorite.
   - Explore a gold/amber-style treatment that fits the existing dark + green UI without becoming harsh or noisy. Likely touch points are the favorite-row/avatar live styles in `gui_web/index.html` and the pinned/live class wiring from `gui_web/components/favorites_rail.jsx`.
   - Acceptance: pinned live streamers are visually distinct at a glance, normal live favorites still keep the current green treatment, and offline pinned favorites do not look live.

3. **Finish day-scoped recording history (Stages 4-5)**
   - Stages 1-3 shipped 2026-07-18 (see `session-notes/session-22-clip-offset-scrub-bar-and-go-live-fixes.md` and the plan at `.claude/plans/hey-ive-been-using-fluttering-zebra.md`): the stale-recording-file bug is fixed, 3-day retention is in place, true Twitch stream start time is fetched, and a gap-aware "today's recording history" timeline strip renders under the player.
   - What's left is the harder part: actually making those past/gap segments playable (Stage 4 - new local video serving, real ffmpeg conversion) and the confirm-before-loading prompt for scrubbing deep into the still-live session (Stage 5). Both involve new subprocess/network-serving code, which is the riskiest part of this whole feature.

4. **Auto-refresh favorites' live status on app boot and when adding a new favorite**
   - Boot-time auto-refresh already exists (`refreshFavoritesOnStartup` in `gui_web/app.jsx`, gated by the `favorites_auto_refresh` setting) - confirm it's actually working as expected for the user. What's likely still missing: `addFavorite` (`gui_web/components/stream_manager.jsx`) doesn't check the new channel's live status immediately - it just adds it (defaulting to offline) and waits for the next scheduled `favorites_refresh_interval` tick.

5. **Auto-swap to next pinned live streamer when the current pinned streamer goes offline**
   - When live-status refresh/network checks detect that the currently selected pinned streamer has gone offline, automatically select the next live pinned streamer in the pinned section.
   - If there are no other live pinned streamers, do not auto-swap to a normal/non-pinned favorite. Leave the current selection or show the offline state instead.
   - This should likely build on the favorites live-status refresh path (`refreshFavorites`, `__onFavoritesUpdated`, and `gui_web/components/stream_manager.jsx`) rather than a separate polling system.

6. **Refresh selected streamer thumbnails while idle and select the top streamer on startup**
   - If the user is idle with a streamer selected, periodically refresh that streamer's preview/thumbnail so the highlighted streamer's preview does not go stale.
   - On app startup, select the top-most streamer in the visible favorites list so its thumbnail/preview loads immediately and the user is not met with a blank empty video player.
   - This should respect the existing pinned-first/live-first ordering: startup should select the same streamer the user sees at the top of the list.
   - Avoid interrupting active watching or user-driven selection changes; this is for idle preview freshness and first-load polish.

7. **Multi-stream / side-by-side viewing**
   - Needs multiple concurrent `WebStreamService` sessions, multiple HLS proxy/playback URLs, and UI layout controls for more than one video stage.

8. **VOD playback**
   - Streamlink can resolve Twitch VOD URLs. Main work: URL entry or lightweight lookup, VOD-aware playback state, seeking, and clip offsets that work without a live edge.

9. **Stream uptime in clip filenames**
   - The broadcast-start-time fetch this references now exists (`stream_created_at` via `src/stream_preview.py`, built for the day-scoped recording history work above) - remaining work is just naming clips with their true VOD timestamp instead of only the local recording timestamp.

10. **Channel points auto-claim / total per streamer**
   - Requires real Twitch login/OAuth. This is intentionally larger than the current login-free app model.

## Backlog

- Polish the merged scrub bar's visuals (`gui_web/components/video_stage.jsx` / `.scrub-*` CSS in `gui_web/index.html`). User feedback 2026-07-19 after the seek-bar/day-timeline merge: "it appears to be working but it looks a little bad." Functionally correct (see `session-notes/session-27-merged-scrub-bar-and-demo-harness.md`) - this is purely a visual-treatment pass, no specifics requested yet.
- Viewer count and game/category in the preview metadata.
- Browse/search live channels or categories.
- Real Twitch following import instead of hand-typed favorites.
- In-app chat sending rather than browser popout chat.
- Predictions, polls, subscriptions/bits, whispers, raids, and extension surfaces, all of which likely need login.
- In-app volume/mute and screenshot shortcuts on the HTML video player.
- Went-live notifications outside the favorites list, likely after following import exists.

## Recently Completed

- 2026-07-19: Merged the live seek bar and the day-timeline recording-history strip into one bar (user felt the two stacked green bars were redundant). The merged `.scrub-track` shows the whole session's segments (past/current/gaps) with a highlighted `.scrub-live-window` overlay marking the actually-scrubbable buffered range, floored to a minimum width so it stays draggable on long sessions. Also fixed the browser-only demo harness (`?demo` mode) so it can actually exercise this: `scripts/run_demo_server.py` now generates a small local HLS test clip via ffmpeg on first run, and `demoApi()` points `playback_url`/`get_recording_segments` at it, giving demo mode a real playable stream instead of an always-empty player. User feedback after seeing it working: "it appears to be working but it looks a little bad" - functionally correct, visual polish is a separate backlog item (see Backlog above). See `session-notes/session-27-merged-scrub-bar-and-demo-harness.md`.
- 2026-07-19: Fixed stream start landing too far behind live. Root cause was two-fold: nothing re-synced to live on startup (fixed with a client-side auto-catch-up mechanism, capped at a barely-perceptible 1.1x speed instead of a jarring hard seek), and the playback path was never actually using Twitch's low-latency stream data in the first place (fixed by recognizing and rewriting Twitch's prefetch segments in the manifest proxy). User confirmed live: "that is working much better." See `session-notes/session-25-stream-latency-autocatchup-and-prefetch-segments.md`.
- 2026-07-18: Clip split-button styling, clip-duration dropdown flip-up behavior, and duplicate "Clip saved" toast were fixed. See `session-notes/session-24-clip-split-button-and-toast-fixes.md`.
