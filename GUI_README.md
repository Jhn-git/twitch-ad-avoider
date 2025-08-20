# TwitchAdAvoider GUI

## Overview
A simple tkinter-based GUI for managing Twitch streams and favorite channels.

## Features
- **Stream Management**: Enter channel names and start streams with quality selection
- **Favorites System**: Add, remove, and manage favorite channels with persistent storage
- **Settings Panel**: Configure video player (VLC, MPV, MPC-HC) and debug mode
- **Lightweight**: Uses built-in tkinter (no additional dependencies)

## Files Created
```
gui/
├── __init__.py
├── favorites_manager.py    # Handles favorite channel storage/management
└── stream_gui.py          # Main GUI application

config/
└── favorites.json         # Stores favorite channels

run_gui.py                 # GUI launcher script
```

## Usage

### Launch GUI
```bash
python run_gui.py
```

### GUI Layout
```
┌─── TwitchAdAvoider - Stream Manager ───┐
│ ╔═══ Watch Stream ═══════════════════╗ │
│ ║ Channel: [___________] Quality: [▼] ║ │
│ ║           [Watch Stream]            ║ │
│ ╚═════════════════════════════════════╝ │
│                                         │
│ ╔═══ Favorites ══════════════════════╗ │
│ ║ ☐ shroud                           ║ │
│ ║ ☐ ninja                            ║ │
│ ║ ☐ pokimane                         ║ │
│ ║ [Add Current][Add New][Remove][▶]  ║ │
│ ╚═════════════════════════════════════╝ │
│                                         │
│ ╔═══ Settings ═══════════════════════╗ │
│ ║ Player: [VLC ▼]    ☐ Debug Mode    ║ │
│ ╚═════════════════════════════════════╝ │
│ Status: Ready                           │
└─────────────────────────────────────────┘
```

## GUI Controls

### Stream Section
- **Channel Input**: Enter Twitch channel name
- **Quality Dropdown**: Select stream quality (best, worst, 720p, 480p, 360p)  
- **Watch Stream Button**: Start streaming the entered channel
- **Enter Key**: Press Enter in channel field to start stream

### Favorites Section  
- **Favorites List**: Shows saved favorite channels
- **Double-click**: Double-click any favorite to start watching
- **Add Current**: Add the currently entered channel to favorites
- **Add New**: Open dialog to add a new favorite channel
- **Remove**: Remove selected favorite from the list
- **▶ Watch**: Start streaming the selected favorite

### Settings Section
- **Player Dropdown**: Choose video player (vlc, mpv, mpc-hc, auto)
- **Debug Mode**: Toggle debug output for troubleshooting

## Integration
- Uses existing `TwitchViewer` class for streaming functionality
- Reuses all existing player detection and streamlink integration
- Favorites stored in JSON format in `config/favorites.json`

## Requirements
- Python 3.6+ with tkinter (built-in on most systems)
- All existing TwitchAdAvoider dependencies (streamlink, etc.)

## Troubleshooting

### "No module named 'tkinter'"
On some Linux systems, tkinter needs to be installed separately:
```bash
# Ubuntu/Debian
sudo apt-get install python3-tk

# CentOS/RHEL
sudo yum install tkinter

# Arch Linux  
sudo pacman -S tk
```

### Windows
Tkinter should be included with Python on Windows by default.

## Testing
The favorites manager can be tested without GUI:
```python
from gui.favorites_manager import FavoritesManager
fm = FavoritesManager()
fm.add_favorite('test_channel')
print(fm.get_favorites())
```