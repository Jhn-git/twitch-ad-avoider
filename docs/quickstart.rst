Quick Start Guide
=================

This guide will help you get started with TwitchAdAvoider quickly.

Basic Usage
-----------

**GUI Mode** (Default)::

    python main.py

**Command Line Mode**::

    python main.py --channel <channel_name> [options]

Common Commands
---------------

Watch a stream in best quality::

    python main.py --channel ninja

Watch with specific quality::

    python main.py --channel shroud --quality 720p

Enable debug output::

    python main.py --channel pokimane --debug

GUI Interface
-------------

The GUI provides an easy-to-use interface with the following sections:

**Stream Input**
    * Enter channel name
    * Select video quality
    * Real-time input validation

**Favorites**
    * Save frequently watched channels
    * Live status indicators
    * Quick access to favorite streams

**Settings**
    * Player selection (VLC, MPV, MPC-HC, Auto)
    * Debug mode toggle
    * Dark/Light theme toggle

**Status Bar**
    * Real-time status updates
    * Error messages and debugging info
    * Message history

Configuration
-------------

Settings are automatically saved to ``config/settings.json``. Key settings include:

* **player**: Video player choice (vlc, mpv, mpc-hc, auto)
* **preferred_quality**: Default stream quality (best, 720p, 480p, etc.)
* **debug**: Enable debug logging
* **network_timeout**: Network timeout in seconds
* **current_theme**: UI theme (light, dark)

See :doc:`CONFIG-REFERENCE` for complete configuration options.

Troubleshooting
---------------

**Stream won't start**
    1. Check that streamlink is installed: ``streamlink --version``
    2. Verify the channel name is correct
    3. Try different video quality options
    4. Enable debug mode for detailed error information

**Player not found**
    1. Install a supported video player (VLC recommended)
    2. Check player is in system PATH
    3. Set manual player path in settings
    4. Use "auto" player detection

**Network issues**
    1. Check internet connection
    2. Increase network timeout in settings
    3. Enable network diagnostics
    4. Try different Twitch servers

For more help, see the troubleshooting section in the README or open an issue on GitHub.