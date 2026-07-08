# Changelog

## v2.1.0 — WebView Cutover

### Changed
- Replaced the desktop interface with a pywebview Stream Manager backed by a no-build React UI.
- Embedded Streamlink playback in the main video stage through a loopback HLS proxy and hls.js.
- Converted stream lifecycle, clipping, favorites, settings, and activity logging to plain Python services exposed through `TwitchViewerAPI`.
- Removed external-player settings and load-migrated old `player`, `player_path`, `player_args`, and cache keys out of `config/settings.json`.
- Updated packaging to bundle `gui_web`, local vendor scripts, Streamlink, pywebview, assets, and config defaults.

### Removed
- Removed the legacy desktop widget runtime, style files, controllers, and tests.
- Removed the old external-player stream module.

## v2.0.0 — Initial Release

### Features
- Streamlink-based Twitch viewing.
- FFmpeg-powered clipping.
- Favorites with live status monitoring.
- JSON config with validation and atomic saves.
- Security-first input validation.
