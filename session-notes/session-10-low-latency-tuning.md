# Session 10: Low-Latency Tuning

Date: 2026-07-05

## What Happened

- User asked how to get the lowest possible viewing latency and whether it's achievable in the current architecture (streamlink Python API → tee thread → external VLC over stdin).
- Explored the existing pipeline: `TwitchViewer.__init__` (`src/twitch_viewer.py`) configured `http-timeout`, `stream-segment-*`, `hls-playlist-reload-attempts`, and Twitch ad-blocking, but had **no** LL-HLS mode and **no** `hls-live-edge` tuning. The one deliberate latency knob, VLC's `cache_duration`, defaulted to 30 seconds — by far the largest added delay in the whole pipeline.
- Designed and implemented a plan (approved via plan mode) to add two new tunable settings and lower the existing default:
  - `twitch_low_latency` (bool) → wired to `session.set_plugin_option("twitch", "low-latency", ...)`. Enables Twitch's LL-HLS delivery.
  - `hls_live_edge` (int, 1–10) → wired to `session.set_option("hls-live-edge", ...)`. Controls how many segments streamlink buffers behind live.
  - Lowered `cache_duration` default (VLC-only cache flags) from 30s.
- Added GUI controls (checkbox + spin box) in Settings → Stream Settings, config validators, README docs, and tests.
- Updated the live `config/settings.json` directly (user opted for this) so the change took effect immediately instead of waiting for a manual Settings-tab edit.
- First pass used aggressive values (`cache_duration=3`, `hls_live_edge=2`). User tested and saw occasional blocky/pixelated frame corruption (decode artifact from a live segment arriving before the buffer had enough slack to absorb minor network jitter) — not classic diagonal screen tearing.
- Diagnosed as the predicted latency/stability trade-off, not a bug. Bumped both values up one notch (`cache_duration=6`, `hls_live_edge=3`) in both the live config and the shipped defaults, added a README troubleshooting note distinguishing "blocky/pixelated frames" (buffer too tight) from generic stutter.
- User re-tested with the bumped values: **stream is working great, no distortion.**
- Follow-up: user then asked to create a TODO list of missing Twitch features for later (see `TODO.md` at repo root — 4 priority items: multi-stream viewing, VOD playback, stream-uptime-in-clip-filenames, channel points).
- Follow-up: after using the app more, user reported still feeling ~15s behind Twitch's own player despite the tuning above. Discussed two ways to investigate: (a) manual stopwatch A/B against a browser tab (ground truth, but manual/one-off), (b) automated internal logging of the fetch-side live-edge lag (objective, ongoing, but only measures our fetch layer, not full end-to-end including player buffering). User chose (b).
- User also asked whether the buffer/latency settings could auto-tune themselves instead of manual nudging. Recommendation given: hold off — auto-tuning means also having to tune the auto-tuner's own thresholds/cooldowns, which is more complexity than it's worth for a single solo setup with a fairly consistent network; better to gather real lag data first (via the new logging) and only build auto-tune if the data shows genuine night-to-night variance that a static value can't handle.
- Implemented the live-edge lag logger: `TwitchViewer._monitor_live_edge_lag()` in `src/twitch_viewer.py` runs as a daemon thread per stream session. It independently polls the resolved HLS media-playlist URL (`streams[quality].url`, captured in `watch_stream()`) every `LIVE_EDGE_LAG_CHECK_INTERVAL_SECONDS` (15s), parses the newest `#EXT-X-PROGRAM-DATE-TIME` tag via `_parse_program_date_time()`, and logs `[live-edge] <channel>: newest fetched segment is ~X.Xs behind broadcast` at INFO level (so it shows up in `logs/twitch_ad_avoider.log` by default, no debug flag needed). It stops polling once `_StreamSession.end_reason` is set. Request failures are caught and logged at DEBUG so a transient network blip doesn't crash the thread or spam the log.
- Important caveat documented for later: this number only measures the **fetch side** (how stale the segment we grabbed is) — it does not include the extra delay added by VLC's own `cache_duration` buffering downstream, or OS pipe/decode time. So it's a lower bound on what the user perceives, not the full end-to-end latency. If this number comes back small (e.g. 2-5s) while the user still perceives ~15s, that would point at the player-side buffering (VLC) as the real culprit rather than streamlink's fetch settings.
- Follow-up: user asked whether clips require "sitting behind" the stream. Clarified they don't — the clip recording writes continuously to a temp `.ts` file throughout the whole viewing session (not just triggered on clip request), so hitting Clip just trims the trailing ~30s off data that's already on disk; it's exactly as fresh as the fetch-side lag, no extra delay added on purpose.
- While explaining that, found a real architectural risk in `src/twitch_viewer.py`'s tee thread (`watch_stream()`): the same thread that reads from the stream and feeds `player_proc.stdin` was **also** doing the synchronous `recording_file.write(chunk)` call right after. A slow disk (antivirus scan, network drive, etc.) would stall that one thread, which would delay the *next* chunk reaching the player too — i.e., disk I/O could have been silently adding to perceived live latency, not just clip accuracy. User agreed to fix this.
- Implemented the fix: recording writes are now decoupled onto their own daemon thread via a `queue.Queue`. The tee thread just does `recording_queue.put(chunk)` (non-blocking) instead of writing to disk itself; a separate `_write_recording()` thread drains the queue and does the actual file I/O, closing the file once it receives a `None` sentinel that the tee thread pushes on shutdown. This ensures a slow disk can no longer stall the player feed.
- Not unit-tested: `watch_stream()`'s internals (tee thread, recording, player launch) have no existing unit test coverage anywhere in the project — existing stream-controller tests use a fully mocked `TwitchViewer` stand-in instead, since this path involves real subprocess/streamlink/player spawning that the project has historically verified live rather than mocked (matches the reconnect work in session 03). Kept that convention rather than bolting on a heavy new mocking harness. Verified via `py_compile` + full test suite (still 182 passing) only — **needs a live watch+clip test to confirm end-to-end**.
- Follow-up: user asked about adding a subtle on-screen indicator (red square, upper-right) for "ad currently being blocked" and "how far behind live." Discussed feasibility and gave a recommendation (not yet implemented, no decision made to build it yet):
  - VLC renders in its own separate OS window (we only pipe bytes into it), so a true "corner of the video" overlay would need either embedding VLC's video output into the Qt window (real architecture change) or driving VLC's own on-screen overlay via its remote-control interface (VLC-specific, wouldn't carry over to mpv). The much simpler version is a status indicator living in the app's own window instead of literally burned into the video corner.
  - Recommended swapping the "how far behind" live number out for something more actionable: an ad-blocked indicator (genuinely useful — Twitch marks ad segments in the same playlist fetch the live-edge logger already polls, so this is a natural extension) plus a simple stream-health light (green/amber/red based on recent stalls or corruption events) rather than a raw seconds-behind counter nobody can act on moment-to-moment.
  - No implementation decision made yet — parked for a future turn once the user decides which direction (and whether it lives in the app's own window vs. a bigger VLC-embedding project).
- Follow-up: user said go ahead with the ad-blocked indicator (dim/desaturated normally, subtle slow red pulse while an ad plays), and refined the health-indicator idea themselves: instead of a green/amber/red light, they want a known "normal" number (e.g. "it should be about 3") with alerts in the log when it strays higher or lower, so they can grep the log and bring findings to discuss rather than guessing what a light means. Agreed this was a better, more actionable design than the original traffic-light idea and implemented both:
  - **Ad detection**: added `_parse_daterange_attrs()` / `_is_ad_daterange()` / `_is_ad_currently_active()` in `src/twitch_viewer.py`, reusing the exact same signal streamlink's own Twitch plugin uses — `#EXT-X-DATERANGE` tags with `CLASS="twitch-stitched-ad"` (or `ID` starting with `stitched-ad-`) in the playlist. Checks whether the newest fetched segment's timestamp falls inside an ad daterange's start/duration window (treating a daterange with no duration yet as still active) — more accurate than a naive "does the playlist mention an ad anywhere" substring check, which could stay stuck "on" after an ad already scrolled out of the sliding playlist window. This reuses the same 15s playlist fetch `_monitor_live_edge_lag()` already does — no extra network calls.
  - **Expected-lag alerting**: added `expected_live_edge_lag_seconds` (default 3) and `live_edge_lag_alert_margin_seconds` (default 2) config settings. `_monitor_live_edge_lag()` now logs a `WARNING` (instead of the normal `INFO`) whenever `abs(lag - expected) > margin`, so deviations are easy to grep for instead of eyeballing every line.
  - **`_StreamSession`** (`src/twitch_viewer.py`) now stores the latest `live_edge_lag_seconds` and `ad_active` behind a lock, updated by the monitor thread and readable from the GUI thread.
  - **GUI**: new `gui_qt/components/ad_indicator.py` (`AdBlockIndicator`) — a small painted dot, dim gray at rest, bright red with a slow 2s opacity pulse (via `QPropertyAnimation` on a `QGraphicsOpacityEffect`) while an ad is active. Wired into `StreamActions` (`gui_qt/components/stream_actions.py`) next to the existing stream-state label, and polled every 2s from `gui_qt/stream_gui.py` (`_setup_ad_status_timer`/`_on_check_ad_status`) reading `_StreamSession.ad_active` off the active stream session. Timer starts on stream start, stops on stream finish/error; `StreamActions.set_streaming(False, ...)` also resets the indicator so it can't show stale "ad active" after the stream ends.
  - Config + validators + GUI spin boxes for the two new settings added following the exact same pattern as `hls_live_edge`/`twitch_low_latency` earlier this session. README settings table and a new "Diagnosing latency issues" troubleshooting section updated.

## Key Decisions

- Twitch's own broadcast/CDN encode delay is the hard floor — this app can't beat it, only strip out its own extra buffering. Realistic ceiling with everything tuned: low single digits of seconds behind broadcast when LL-HLS is healthy, degrading toward Twitch's normal ~8–15s floor if it isn't.
- `twitch_low_latency` defaults to `True` (safe, no real downside for a solo stdin-piped setup).
- Settled on `cache_duration=6`, `hls_live_edge=3` as the working baseline after one round of live feedback — a middle ground between the very aggressive first attempt (3/2, caused corruption) and the old default (30/unset, way more latency than needed).
- Did not extend `MANAGED_CACHE_FLAGS` (`src/player_args.py`) to cover mpv — user's live config uses VLC, and mpv's cache model doesn't map cleanly onto VLC's duration-based flags. Documented as a manual `player_args` workaround for mpv/mpc-hc users instead.
- Chose target+margin (`expected_live_edge_lag_seconds` +/- `live_edge_lag_alert_margin_seconds`) over a single hard ceiling for the lag alert, since the user specifically wants to catch "higher or lower than normal," not just "too high."
- Chose not to unit-test the `AdBlockIndicator` widget itself (presentation-only: a paint call + an animation toggle) — matches the project's explicit "skip GUI tests unless there's a strong specific reason" convention (see `tests/test_chat_panel.py`'s header comment). The actual logic with real bug risk (ad-daterange parsing, the threshold math) is fully unit-tested instead.

## Files Changed

- `src/constants.py`
- `src/config_manager.py`
- `src/twitch_viewer.py`
- `gui_qt/components/settings_tab.py`
- `gui_qt/components/ad_indicator.py` (new)
- `gui_qt/components/stream_actions.py`
- `gui_qt/stream_gui.py`
- `config/settings.json`
- `README.md`
- `TODO.md` (new)
- `tests/test_config_validation.py`
- `tests/test_network_config.py`
- `tests/test_twitch_viewer.py`

## Verification

- `./.venv/Scripts/python.exe -m pytest tests/` — full suite passed: 176 (initial tuning) → 182 (live-edge lag monitor) → 182 (tee/recording-writer split, no new tests) → **196** (ad detection + expected-lag alerting + settings).
- `./.venv/Scripts/python.exe -m py_compile` on all changed Python files — no syntax errors.
- Live test in the real app by the user: first pass (3/2) showed intermittent pixelation/corruption; second pass (6/3) confirmed working great with no distortion.
- Live-edge lag monitor: unit-tested with mocked `requests.get`/`time.sleep` (playlist parsing, stop-on-session-end, error swallowing, INFO-vs-WARNING threshold behavior, ad-daterange detection). **Not yet verified against a real live stream** — that's the next real-world step, see below.
- Tee/recording-writer split: **not unit-tested (by design, matches project convention — see What Happened) and not yet live-tested.** Needs a real watch+clip session to confirm the decoupling actually works and doesn't break clip recording.
- Ad indicator + lag alerting: unit-tested at the logic layer (`_parse_daterange_attrs`, `_is_ad_daterange`, `_is_ad_currently_active`, WARNING/INFO threshold logging, `_StreamSession` metrics). **The GUI dot itself and the real-world accuracy of ad detection have not been seen live yet** — needs a real stream with an actual ad break to confirm the dot lights up correctly and stops when the ad ends.

## Current Progress

- Buffer/latency tuning is implemented, tested, and confirmed working in the live app (no distortion) as of this session. Current live values: `cache_duration=6`, `twitch_low_latency=true`, `hls_live_edge=3`.
- User still perceives ~15s of lag vs. Twitch's own player even with the above tuning — root cause not yet identified. The new live-edge lag logger exists specifically to narrow this down (fetch-side lag vs. player-side buffering) but hasn't been observed with real data yet.
- The live-edge lag monitor code is merged and unit-tested but **has not yet been run against a real Twitch stream** — next session should start by watching a stream for a while and then reading `logs/twitch_ad_avoider.log` for `[live-edge]` lines.
- The tee/recording-writer thread split is merged but **not yet live-tested** — next real viewing session should also confirm (a) clips still work correctly and (b) playback still feels smooth, since this changed how recording bytes flow without changing what's written.
- The ad-blocked indicator and expected-lag WARNING alerting are both implemented and unit-tested, with defaults `expected_live_edge_lag_seconds=3` / `live_edge_lag_alert_margin_seconds=2` already applied to the live config — **not yet confirmed against a real stream with an actual ad break**.

## Things We Haven't Tried Yet

- Reading real `[live-edge]` log output from an actual viewing session (the main next step — nothing has consumed this data yet).
- Depending on what that data shows: if fetch-side lag is small (~2-5s) but perceived lag is ~15s, the next investigation target becomes VLC's own buffering/decode path (e.g. is `cache_duration` actually being honored over a stdin pipe the way we assume, or is VLC quietly buffering more than the configured cache flags suggest) rather than more streamlink tuning.
- Confirming the tee/recording-writer split actually reduces or removes any disk-I/O-caused delay — we don't have before/after evidence yet, just the architectural reasoning for why it should help.
- Auto-tuning the buffer settings based on observed conditions — deliberately deferred until the lag-logging data shows whether it's actually needed (see Key Decisions).
- Longer-session soak testing (multiple hours, different times of day / network conditions) to see if `6`/`3` holds up under worse jitter than the initial short test, or whether it could be pushed back down slightly (e.g. `hls_live_edge=2`) once the network's real jitter profile is better known.
- No side-by-side latency measurement was done (e.g. stopwatch against a browser tab) to quantify how many seconds behind broadcast the app now sits — only subjective "seems low and stream looks clean" verification, plus the not-yet-analyzed lag logs.
- Haven't tried mpv as the player to see if it would give lower latency than VLC out of the box (mpv's stdin-pipe handling is generally considered better for this use case, but `cache_duration` is currently a no-op for mpv — would need manual `player_args` cache flags per the README note, or a future `MANAGED_CACHE_FLAGS` extension for mpv).
- Haven't tested behavior on a degraded/throttled network to confirm the corruption-vs-stutter trade-off documented in the README actually manifests as predicted at the extremes (e.g. `hls_live_edge=1`, `cache_duration=0`).
- Haven't confirmed the ad-blocked indicator against a real ad break (does it light up at the right time, does it turn off promptly when the ad ends, any false positives/negatives from the 15s poll granularity).
- Haven't confirmed whether `expected_live_edge_lag_seconds=3` / `margin=2` are actually the right numbers once real `[live-edge]` data comes in — these were picked to match what the user already observed, but haven't been validated against a full session's worth of data yet.

## Next Steps

- **Watch a stream for a while with the current build, then check `logs/twitch_ad_avoider.log` for `[live-edge]` lines** — this is the concrete next action and will tell us whether the remaining ~15s gap is on the fetch side or the player side, and whether any `WARNING` lines show up.
- During that same session: watch for an actual ad break and confirm the indicator dot pulses red at the right time and clears when the ad ends.
- Same session should also confirm the tee/recording-writer split didn't break clips and that a manual clip still trims correctly.
- If fetch-side lag is already low, shift investigation to VLC's cache/decode behavior over the stdin pipe rather than further streamlink tuning.
- If pixelation/corruption ever reappears (e.g. on a worse network night), bump `hls_live_edge` by 1 before touching `cache_duration` further, per the README guidance.
- Revisit the auto-tune idea only once real lag data is in hand — don't build it speculatively.
- If the `WARNING` threshold fires too often or too rarely once real data comes in, adjust `expected_live_edge_lag_seconds`/`live_edge_lag_alert_margin_seconds` in Settings based on what's actually observed.
