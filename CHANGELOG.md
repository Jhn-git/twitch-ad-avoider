# Changelog

## v2.0.1 — 2026-04-26

### Fixed
- **Dark mode not activating** — PySide6 6.4+ changed Qt enums to strict Python enums (no longer IntEnum-comparable). The checkbox `stateChanged` comparison `state == Qt.CheckState.Checked` always returned `False`, so toggling dark mode had no effect. Fixed with `bool(state)`.
- **Validation label ignores dark mode** — Channel name validation feedback (valid/invalid) used hardcoded inline `setStyleSheet` colors that bypassed QSS theming. The valid-channel green is now `#3CB371` on dark backgrounds and `#006400` on light.
- **`StreamControlPanel` not receiving theme updates** — `_apply_theme` in `stream_gui.py` now propagates `set_dark_mode` to `stream_panel` alongside other components.

---

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
