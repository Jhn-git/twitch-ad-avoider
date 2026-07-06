# twitch-ad-avoider

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Watch Twitch streams ad-free through an external video player, with a modern Qt GUI and command-line interface.

---

## Download

**Windows**: grab the latest `TwitchAdAvoider.exe` from the [Releases](https://github.com/Jhn-git/TwitchAdAvoider-lite/releases) page — no Python or streamlink installation required. You only need a video player (VLC recommended).

---

## Features

### Stream Viewing
- **Ad Avoidance**: Streams are routed through streamlink (bundled) to bypass Twitch ads
- **Quality Selection**: best, 720p, 480p, 360p, 160p, or worst
- **Player Auto-Detection**: Automatically finds VLC, MPV, or MPC-HC on your system
- **Clipping**: Save the last 30 seconds of an active stream as a local video file (requires FFmpeg)

### Interface
- **Qt GUI**: Tabbed PySide6 interface — Stream, Favorites, Chat, and Settings tabs
- **CLI**: Full command-line support for scripting or headless use
- **Favorites**: Save channels with live status auto-refresh
- **Chat**: Opens Twitch chat in your browser alongside the stream. It uses your normal browser session, so if you're already logged into Twitch there, you'll join/chat as that account; the app itself does not log you into Twitch.
- **Theming**: Light and dark mode with QSS stylesheets

### Configuration & Security
- **JSON Config**: All settings in `config/settings.json`, validated on load and save
- **Input Validation**: Protection against path traversal, command injection, and control character injection
- **Network Settings**: Configurable timeouts, retry attempts, and retry delay

---

## Quick Start

### Windows EXE (Easiest)

1. Download `TwitchAdAvoider.exe` from [Releases](https://github.com/Jhn-git/TwitchAdAvoider-lite/releases)
2. Install [VLC](https://www.videolan.org/vlc/) if you don't have a video player
3. Run `TwitchAdAvoider.exe`

### From Source

**Prerequisites**: Python 3.8+, a video player (VLC recommended)

```bash
git clone https://github.com/Jhn-git/TwitchAdAvoider-lite.git
cd TwitchAdAvoider-lite

python -m venv .venv

# Windows:
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

pip install -e .
python main.py
```

### CLI Usage

```bash
# Watch a channel
python main.py --channel ninja

# Watch with specific quality
python main.py --channel shroud --quality 720p

# Enable debug logging
python main.py --channel pokimane --debug
```

---

## Configuration

Settings are stored in `config/settings.json` and created with defaults on first run. All settings can be changed via the GUI Settings tab.

### Key Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `preferred_quality` | `"best"` | Stream quality: best, 720p, 480p, 360p, 160p, worst |
| `player` | `"vlc"` | Player: vlc, mpv, mpc-hc, auto |
| `player_path` | `null` | Absolute path to player executable (overrides auto-detect) |
| `player_args` | `""` | Extra arguments passed to the player |
| `cache_duration` | `6` | Stream buffer in seconds (0–3600) — VLC only today |
| `twitch_low_latency` | `true` | Use Twitch's low-latency HLS mode (shorter segments, faster reload) |
| `hls_live_edge` | `3` | HLS segments buffered behind live (1–10). Lower = less latency, more stutter/corruption risk on jitter |
| `network_timeout` | `30` | HTTP timeout in seconds (10–120) |
| `connection_retry_attempts` | `3` | Retry count on stream failure (1–10) |
| `retry_delay` | `5` | Seconds between retries (1–30) |
| `debug` | `false` | Enable verbose debug logging |
| `log_to_file` | `false` | Write logs to `logs/twitch_ad_avoider.log` |
| `log_level` | `"INFO"` | Minimum log level |
| `dark_mode` | `true` | Dark theme |
| `window_width` | `940` | Main window width in pixels |
| `window_height` | `680` | Main window height in pixels |

### Example Configs

**Minimal**:
```json
{
    "preferred_quality": "best",
    "player": "auto"
}
```

**Fixed player path + fullscreen**:
```json
{
    "preferred_quality": "best",
    "player": "vlc",
    "player_path": "C:\\Program Files\\VideoLAN\\VLC\\vlc.exe",
    "player_args": "--fullscreen"
}
```

---

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Qt GUI Layer    │    │   CLI Interface  │    │  Configuration  │
│ • Stream Tab    │    │ • Arg Parsing    │    │ • Validation    │
│ • Favorites Tab │    │ • Direct Launch  │    │ • Persistence   │
│ • Settings Tab  │    └────────┬─────────┘    └────────┬────────┘
└────────┬────────┘             │                       │
         └─────────────────────┼───────────────────────┘
                               │
                  ┌────────────▼────────────┐
                  │     Core Engine         │
                  │ • Stream Management     │
                  │ • Player Detection      │
                  │ • Clip Recording        │
                  └────────────┬────────────┘
                               │
                  ┌────────────▼────────────┐
                  │   Security Layer        │
                  │ • Input Validation      │
                  │ • Attack Prevention     │
                  │ • Sanitization          │
                  └─────────────────────────┘
```

| Component | Responsibility | File |
|-----------|---------------|------|
| **TwitchViewer** | Stream management, player detection, clipping | `src/twitch_viewer.py` |
| **StreamGUI** | Qt interface orchestration | `gui_qt/stream_gui.py` |
| **ConfigManager** | Settings validation & persistence | `src/config_manager.py` |
| **Validators** | Security input validation | `src/validators.py` |
| **FavoritesManager** | Channel persistence & status checks | `src/favorites_manager.py` |

For developer details see **[CLAUDE.md](CLAUDE.md)**.

---

## Clipping

While a stream is active, use the **Clip** button in the GUI to save the last ~30 seconds as a local `.mp4` file. Clips are saved to `clips/` by default.

**Requires FFmpeg**: Download from [ffmpeg.org](https://ffmpeg.org/download.html) and ensure `ffmpeg` is on your PATH (or set `ffmpeg_path` in settings).

---

## Troubleshooting

### "No video player found"
- Install [VLC](https://www.videolan.org/vlc/) — the app will prompt you with a download link if no player is detected
- Or set a custom path: Settings → Stream Settings → Custom Player Path

### Stream won't start / timeouts
- Increase timeout: Settings → Network Settings → Network Timeout: 60
- Lower quality: try 720p or 480p instead of best

### Stream stutters / buffers constantly
- Increase cache: Settings → Stream Settings → Cache Duration: 60
- Check bandwidth: 480p needs ~3 Mbps, 720p ~5 Mbps, 1080p ~10 Mbps
- If you've tuned `cache_duration` / `hls_live_edge` down for lower latency (see below), that trades away stutter resilience — raise `cache_duration` back up a few seconds and/or raise `hls_live_edge` before touching network timeout/quality

### Reduce latency (catch up to live)
- Enable Twitch low-latency mode: Settings → Stream Settings → Use Twitch Low-Latency Mode (LL-HLS) — default on
- Lower live-edge buffer: Settings → Stream Settings → HLS Live Edge: 2–4 (lower = less latency, more stutter/corruption risk)
- Lower cache duration: Settings → Stream Settings → Cache Duration: 4–8 seconds
- This app cannot beat Twitch's own broadcast/CDN encode delay. Even fully tuned, expect low single digits of seconds behind broadcast at best (typically more like several seconds), not zero latency
- **Blocky/pixelated frames (not diagonal tearing)**: this means a frame was decoded from incomplete data — the live-edge buffer or cache is too tight for your network's jitter. Raise `hls_live_edge` by 1 and/or `cache_duration` by a couple seconds until it clears; this trades a little latency back for stability
- mpv/mpc-hc users: `cache_duration` only manages VLC's cache flags today — pass your own cache flags manually via Player Arguments (e.g. mpv: `--cache=yes --cache-secs=2`)

### GUI won't launch (from source)
```bash
pip install --upgrade --force-reinstall PySide6
```

### WSL2 Qt error (`undefined symbol: wl_proxy_marshal_flags`)
```bash
export QT_QPA_PLATFORM=xcb
python main.py
```

### Enable debug logging
```bash
python main.py --debug
```
Or via GUI: Settings → Advanced → Enable Debug Mode + Log to File → Apply Settings → check `logs/twitch_ad_avoider.log`.

---

## Development

```bash
pip install -e .[dev]

make test      # Run tests
make check     # black + flake8 + mypy
make run       # Launch app
make build     # Build Windows EXE
```

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Acknowledgments

- **[Streamlink](https://streamlink.github.io/)** — Core streaming library
- **[PySide6](https://doc.qt.io/qtforpython/)** — Qt GUI framework
- **[VLC](https://www.videolan.org/vlc/)** — Recommended video player
