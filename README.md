# TwitchAdAvoider

A Python implementation for watching Twitch streams while avoiding ads with a modern GUI interface.

## Features

- 🎯 **Ad Avoidance**: Watch Twitch streams without ads
- 🖥️ **GUI Interface**: User-friendly tkinter-based interface
- ⭐ **Favorites Management**: Save and manage your favorite channels
- 🔴 **Live Stream Status**: Real-time monitoring of favorite channels (live/offline indicators)
- 👥 **Stream Information**: View viewer count, game being played, and stream titles
- 🔄 **Auto-Refresh**: Background polling of stream status with manual refresh option
- 🎮 **Multiple Players**: Support for VLC, MPV, and MPC-HC players
- ⚙️ **Configurable**: Extensive configuration options
- 🔧 **CLI Support**: Command-line interface for power users
- 📝 **Comprehensive Logging**: Detailed logging with configurable levels

## Requirements

- Python 3.6+
- One of the supported players: VLC, MPV, or MPC-HC
- streamlink
- Twitch API credentials (for stream status monitoring - optional)

## Installation

1. Clone this repository:
```bash
git clone https://github.com/your-repo/TwitchAdAvoider-lite-2.git
cd TwitchAdAvoider-lite-2
```

2. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### GUI Mode (Default)

Launch the graphical interface:
```bash
python main.py
```

### Command Line Mode

Watch a specific channel directly:
```bash
python main.py --channel CHANNEL_NAME
python main.py --channel CHANNEL_NAME --quality 720p
```

Enable debug mode:
```bash
python main.py --debug
```

### As Python Module

```bash
python -m twitch_ad_avoider
```

## Configuration

Settings are automatically saved in `config/settings.json`. You can configure:

- **preferred_quality**: Stream quality (best, 720p, 480p, 360p, worst)
- **player**: Video player to use (vlc, mpv, mpc-hc, auto)
- **debug**: Enable debug mode for troubleshooting
- **log_level**: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- **log_to_file**: Whether to save logs to file
- **player_path**: Custom path to video player executable
- **player_args**: Additional arguments to pass to the player
- **enable_status_monitoring**: Enable/disable stream status monitoring (default: true)
- **status_check_interval**: How often to check stream status in seconds (default: 300)
- **twitch_client_id**: Twitch API client ID for status monitoring
- **twitch_client_secret**: Twitch API client secret for status monitoring
- **show_viewer_count**: Show viewer count in favorites list (default: true)
- **show_stream_title**: Show stream title in favorites list (default: true)
- **show_game_name**: Show current game in favorites list (default: true)

## GUI Features

- **Stream Watching**: Enter channel name and quality, click "Watch Stream"
- **Favorites**: Add, remove, and watch favorite channels with live status indicators
- **Status Monitoring**: Real-time display of stream status (🔴 live, ⚫ offline)
- **Stream Information**: View viewer count, current game, and stream details
- **Manual Refresh**: Force update stream status with the refresh button
- **Settings**: Configure player and debug mode
- **Status Updates**: Real-time status information

## Troubleshooting

### Player Not Found
If no video player is detected:
1. Install VLC, MPV, or MPC-HC
2. Ensure the player is in your system PATH
3. Or set a custom player path in settings

### Streamlink Issues
If streamlink is not found:
```bash
pip install --upgrade streamlink
```

### Debug Mode
Enable debug mode for detailed logging:
- In GUI: Check "Debug Mode"
- In CLI: Use `--debug` flag

### Stream Status Monitoring Setup

For stream status monitoring to work, you need Twitch API credentials:

1. Go to [Twitch Developers Console](https://dev.twitch.tv/console)
2. Create a new application
3. Note your Client ID and Client Secret
4. Add them to your configuration:
   - Either edit `config/settings.json` directly:
     ```json
     {
       "twitch_client_id": "your_client_id_here",
       "twitch_client_secret": "your_client_secret_here"
     }
     ```
   - Or set them via environment variables:
     ```bash
     export TWITCH_CLIENT_ID="your_client_id_here"
     export TWITCH_CLIENT_SECRET="your_client_secret_here"
     ```

**Note**: Stream status monitoring will be disabled if credentials are not provided, but all other features will work normally.

## Project Structure

```
TwitchAdAvoider-lite-2/
├── main.py                 # Main entry point
├── src/                    # Core application modules
│   ├── twitch_viewer.py   # Main viewer class
│   ├── config_manager.py  # Configuration management
│   ├── logging_config.py  # Logging setup
│   ├── constants.py       # Application constants
│   └── exceptions.py      # Custom exceptions
├── gui/                   # GUI components
│   ├── stream_gui.py     # Main GUI interface
│   └── favorites_manager.py # Favorites management
├── config/               # Configuration files
│   ├── settings.json    # Application settings
│   └── favorites.json   # Saved favorites
└── logs/                # Log files (created when needed)
```

## License

This project is provided as-is for educational purposes.
