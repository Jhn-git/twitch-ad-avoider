# TODO / Feature Backlog

Ordered by priority. Not started unless noted.

## Priority

1. **Fix Clip button split-button UI**
   - The Clip button + clip-duration dropdown chevron (`.clip-split` in `gui_web/index.html`, rendered in `gui_web/components/video_stage.jsx`) don't read as one connected control - looks like two mismatched pieces rather than a seamless pill (`.clip-split .btn` / `.clip-menu-button` in `gui_web/index.html`). Worth double-checking border/height alignment between the two (`align-items: stretch` on `.clip-split`, borders on both pieces at the seam) for what's actually causing the visual break.
   - Separately, the dropdown menu (`.clip-duration-dropdown .dropdown-menu`, opened via `gui_web/components/dropdown.jsx`) can render off the bottom of the window when it's small/short, instead of flipping to open upward. `dropdown.jsx` has no viewport-space-aware positioning logic today - needs to check available space below (e.g. via `getBoundingClientRect()`) and open upward when there isn't enough room, rather than requiring the user to resize the window.

2. **Finish day-scoped recording history (Stages 4-5)**
   - Stages 1-3 shipped 2026-07-18 (see `session-notes/session-22-clip-offset-scrub-bar-and-go-live-fixes.md` and the plan at `.claude/plans/hey-ive-been-using-fluttering-zebra.md`): the stale-recording-file bug is fixed, 3-day retention is in place, true Twitch stream start time is fetched, and a gap-aware "today's recording history" timeline strip renders under the player.
   - What's left is the harder part: actually making those past/gap segments playable (Stage 4 - new local video serving, real ffmpeg conversion) and the confirm-before-loading prompt for scrubbing deep into the still-live session (Stage 5). Both involve new subprocess/network-serving code, which is the riskiest part of this whole feature.

3. **Auto-refresh favorites' live status on app boot and when adding a new favorite**
   - Boot-time auto-refresh already exists (`refreshFavoritesOnStartup` in `gui_web/app.jsx`, gated by the `favorites_auto_refresh` setting) - confirm it's actually working as expected for the user. What's likely still missing: `addFavorite` (`gui_web/components/stream_manager.jsx`) doesn't check the new channel's live status immediately - it just adds it (defaulting to offline) and waits for the next scheduled `favorites_refresh_interval` tick.

4. **Multi-stream / side-by-side viewing**
   - Needs multiple concurrent `WebStreamService` sessions, multiple HLS proxy/playback URLs, and UI layout controls for more than one video stage.

5. **VOD playback**
   - Streamlink can resolve Twitch VOD URLs. Main work: URL entry or lightweight lookup, VOD-aware playback state, seeking, and clip offsets that work without a live edge.

6. **Stream uptime in clip filenames**
   - The broadcast-start-time fetch this references now exists (`stream_created_at` via `src/stream_preview.py`, built for the day-scoped recording history work above) - remaining work is just naming clips with their true VOD timestamp instead of only the local recording timestamp.

7. **Channel points auto-claim / total per streamer**
   - Requires real Twitch login/OAuth. This is intentionally larger than the current login-free app model.

## Backlog

- Viewer count and game/category in the preview metadata.
- Browse/search live channels or categories.
- Real Twitch following import instead of hand-typed favorites.
- In-app chat sending rather than browser popout chat.
- Predictions, polls, subscriptions/bits, whispers, raids, and extension surfaces, all of which likely need login.
- In-app volume/mute and screenshot shortcuts on the HTML video player.
- Went-live notifications outside the favorites list, likely after following import exists.
