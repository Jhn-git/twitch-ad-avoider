# Changelog

## v2.0.0 — Initial Release

### Features
- **GUI + CLI dual mode** — PySide6 desktop app with full `--channel`/`--quality` CLI support
- **Ad-free streaming** — Streamlink-based stream piping to bypass Twitch ads
- **Multi-player support** — Auto-detects VLC, MPV, and MPC-HC (with 5 fallback detection methods)
- **Stream clipping** — FFmpeg-powered clipping with accurate HLS seek via `ffprobe`
- **Favorites panel** — Save and manage favorite channels with status monitoring
- **Settings persistence** — JSON config with validation and atomic saves
- **Security-first input validation** — Blocks path traversal, command injection, and control characters
- **Dark/light theme** — Switchable UI theme
- **Twitch chat** — Opens chat in browser via a dedicated panel

### Tech
- Python 3.8+ / PySide6 / streamlink / FFmpeg
- MIT License
