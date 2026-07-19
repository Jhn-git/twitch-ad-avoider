# TODO / Feature Backlog

Ordered by priority. Not started unless noted.

## Priority

1. **Fix stream start landing too far behind live**
   - User-observed 2026-07-18: when starting a stream, playback loads successfully, but after the initial loading/buffering it lands far enough behind the live edge that the user has to click **Go Live** to catch up.
   - Investigate initial HLS/video startup behavior in `gui_web/components/video_stage.jsx` (`hls.loadSource`, `hls.attachMedia`, autoplay, `updateSeekVisuals`, `goLive`) and whether the player should automatically seek to the buffered end once the first playable live data is ready.
   - Be careful not to reintroduce the old scrub-back problem: automatic catch-up should only happen during normal stream startup, not after the user deliberately seeks backward.
   - Acceptance: starting a live stream should settle near the same position the **Go Live** button would choose, without requiring the user to click it immediately after startup.

2. **Remember player volume and avoid starting at full volume**
   - User-observed 2026-07-18: the app appears to start playback at full volume, which is too loud.
   - Preferred behavior: remember the last volume the user had set when the app was previously open.
   - Fallback behavior: if no previous volume exists yet, start the player around 20% volume instead of 100%.
   - Likely touch points are `gui_web/components/video_stage.jsx` for reading/applying `video.volume`, and settings/UI-state persistence through `gui_web/app.jsx`, `gui_web/components/stream_manager.jsx`, `src/config_manager.py`, and `src/webapi.py`.

3. **Give pinned live streamers a distinct highlight color**
   - Pinned favorites are more important than normal favorites because they sit above the regular list, so their live glow/highlight should read as a higher-priority state instead of using the same green treatment as every other live favorite.
   - Explore a gold/amber-style treatment that fits the existing dark + green UI without becoming harsh or noisy. Likely touch points are the favorite-row/avatar live styles in `gui_web/index.html` and the pinned/live class wiring from `gui_web/components/favorites_rail.jsx`.
   - Acceptance: pinned live streamers are visually distinct at a glance, normal live favorites still keep the current green treatment, and offline pinned favorites do not look live.

4. **Finish day-scoped recording history (Stages 4-5)**
   - Stages 1-3 shipped 2026-07-18 (see `session-notes/session-22-clip-offset-scrub-bar-and-go-live-fixes.md` and the plan at `.claude/plans/hey-ive-been-using-fluttering-zebra.md`): the stale-recording-file bug is fixed, 3-day retention is in place, true Twitch stream start time is fetched, and a gap-aware "today's recording history" timeline strip renders under the player.
   - What's left is the harder part: actually making those past/gap segments playable (Stage 4 - new local video serving, real ffmpeg conversion) and the confirm-before-loading prompt for scrubbing deep into the still-live session (Stage 5). Both involve new subprocess/network-serving code, which is the riskiest part of this whole feature.

5. **Auto-refresh favorites' live status on app boot and when adding a new favorite**
   - Boot-time auto-refresh already exists (`refreshFavoritesOnStartup` in `gui_web/app.jsx`, gated by the `favorites_auto_refresh` setting) - confirm it's actually working as expected for the user. What's likely still missing: `addFavorite` (`gui_web/components/stream_manager.jsx`) doesn't check the new channel's live status immediately - it just adds it (defaulting to offline) and waits for the next scheduled `favorites_refresh_interval` tick.

6. **Auto-swap to next pinned live streamer when the current pinned streamer goes offline**
   - When live-status refresh/network checks detect that the currently selected pinned streamer has gone offline, automatically select the next live pinned streamer in the pinned section.
   - If there are no other live pinned streamers, do not auto-swap to a normal/non-pinned favorite. Leave the current selection or show the offline state instead.
   - This should likely build on the favorites live-status refresh path (`refreshFavorites`, `__onFavoritesUpdated`, and `gui_web/components/stream_manager.jsx`) rather than a separate polling system.

7. **Refresh selected streamer thumbnails while idle and select the top streamer on startup**
   - If the user is idle with a streamer selected, periodically refresh that streamer's preview/thumbnail so the highlighted streamer's preview does not go stale.
   - On app startup, select the top-most streamer in the visible favorites list so its thumbnail/preview loads immediately and the user is not met with a blank empty video player.
   - This should respect the existing pinned-first/live-first ordering: startup should select the same streamer the user sees at the top of the list.
   - Avoid interrupting active watching or user-driven selection changes; this is for idle preview freshness and first-load polish.

8. **Multi-stream / side-by-side viewing**
   - Needs multiple concurrent `WebStreamService` sessions, multiple HLS proxy/playback URLs, and UI layout controls for more than one video stage.

9. **VOD playback**
   - Streamlink can resolve Twitch VOD URLs. Main work: URL entry or lightweight lookup, VOD-aware playback state, seeking, and clip offsets that work without a live edge.

10. **Stream uptime in clip filenames**
   - The broadcast-start-time fetch this references now exists (`stream_created_at` via `src/stream_preview.py`, built for the day-scoped recording history work above) - remaining work is just naming clips with their true VOD timestamp instead of only the local recording timestamp.

11. **Channel points auto-claim / total per streamer**
   - Requires real Twitch login/OAuth. This is intentionally larger than the current login-free app model.

## Backlog

- Viewer count and game/category in the preview metadata.
- Browse/search live channels or categories.
- Real Twitch following import instead of hand-typed favorites.
- In-app chat sending rather than browser popout chat.
- Predictions, polls, subscriptions/bits, whispers, raids, and extension surfaces, all of which likely need login.
- In-app volume/mute and screenshot shortcuts on the HTML video player.
- Went-live notifications outside the favorites list, likely after following import exists.

## Recently Completed

- 2026-07-18: Clip split-button styling, clip-duration dropdown flip-up behavior, and duplicate "Clip saved" toast were fixed. See `session-notes/session-24-clip-split-button-and-toast-fixes.md`.
