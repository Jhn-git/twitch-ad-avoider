# TwitchAdAvoider-lite

A Python implementation for watching Twitch streams while avoiding ads.

## Requirements

- Python 3.6+
- MPV player
- streamlink

## Installation

1. Clone this repository
2. Create a virtual environment and activate it
3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

```bash
python watch_stream.py CHANNEL_NAME
```

Replace `CHANNEL_NAME` with the name of the Twitch channel you want to watch.

## Configuration

Settings can be modified in `config/settings.json`:

- `preferred_quality`: Stream quality (default: "best")
- `player`: Video player to use (default: "mpv")
- `cache_duration`: Cache duration in seconds (default: 30)
