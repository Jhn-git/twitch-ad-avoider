# Feature idea: keyword/date clip search + download for twitch-viewer

Status: idea only, not started. Written after prototyping the workflow as a
standalone script during a one-off "find TOFINA clips" request.

## What this would add

Right now `twitch-viewer` (`C:\Users\thewa\Documents\GitHub\streaming\twitch-viewer`)
only knows about clips it records itself while you're watching a live stream
(`clip_editor.py`, `WebStreamService`, local FFmpeg). It has no way to reach
into a channel's existing Twitch clip history. The idea: add a "Clip Search"
panel that can

1. **Search a broadcaster's clips by keyword** in the title (client-side
   substring filter — Twitch's Helix API has no server-side title search, so
   this pages through clips and filters locally).
2. **Expand a match to "same day"** — pull every clip posted on the same UTC
   calendar day as a match, useful for finding the surrounding context of a
   moment when you only remember one clip from it.
3. **List all clips in an arbitrary time window** (e.g. "everything from this
   streamer on this date, this hour range") independent of any keyword.
4. **Download selected clips** into the app's existing `clip_directory`
   setting, alongside the locally-recorded clips it already produces.

## What's already proven to work

A throwaway prototype lives at
`streamer-editing-search/scripts/search_clips.py` (Desktop). It does #1-#3
today via the Helix API, and downloading (#4) was done manually with `yt-dlp`
against the URLs it returned. Both were run for real against `ohtofu` this
session:

- Keyword search for "TOFINA" → 1 match ("Dancing Tofina").
- Same-day expansion → 19 clips from 2025-09-15.
- All 19 downloaded via `yt-dlp <clip-url>` at ~1080p, 336 MB total, into
  this folder.

So the API calls, pagination, timezone handling, and download path are all
validated — what's left is wiring it into the real app's UI/service layers
instead of a CLI script.

## How it'd likely fit the existing architecture

- **Auth**: needs a `twitch_client_id` / `twitch_client_secret` pair in
  `config/settings.json`, same pattern as
  `twitch-streamer-outreach/config/settings.json` already uses (app access
  token via Client Credentials grant — no user login). Would need its own
  `ConfigManager` keys and a first-run prompt if unset.
- **Service layer**: a new `TwitchClipSearchService` (mirrors
  `WebStreamService`'s shape) wrapping the Helix `clips`/`users` endpoints —
  token fetch/cache, `get_broadcaster_id`, `iter_clips` with
  `started_at`/`ended_at` support, same as the prototype's functions.
- **Bridge**: expose it on `TwitchViewerAPI` (`src/webapi.py`) as
  JS-callable methods, e.g. `search_clips(broadcaster, keyword)`,
  `list_clips_in_window(broadcaster, start, hours)`,
  `download_clips(urls)` — same call shape as the existing
  `FavoritesManager`/`StatusMonitor` methods it already bridges.
- **Download**: needs `yt-dlp` as an actual dependency (not just ambient on
  PATH like in the prototype) since it's what actually pulls clip video from
  Twitch's CDN — `ffmpeg` is already a dependency for local clipping, so this
  follows the same "external binary, configurable path" pattern as
  `ffmpeg_path` in settings.
- **UI**: a panel in the Stream Manager (`gui_web/`) — broadcaster + keyword
  inputs, a results list (title, thumbnail, view count, date), a "same day"
  expand action per result, and a multi-select "download selected" button
  that writes into `clip_directory`.

## Open questions for later

- Bundle `yt-dlp` with the installer (like `ffmpeg`) or require it on PATH?
- Where do Twitch API credentials come from for a general user — self-service
  dev.twitch.tv app registration walkthrough in Settings, or ship a shared
  one? (The outreach tool assumes Jhn's own personal dev app.)
- Dedup UX between locally-recorded ad-avoider clips and downloaded official
  Twitch clips in the same `clips/` folder — separate subfolder is probably
  simplest.
- Rate limits / UX for channels with thousands of clips (prototype defaults
  to scanning the most recent 1000; fine for a script, needs a real loading
  state in a GUI).
