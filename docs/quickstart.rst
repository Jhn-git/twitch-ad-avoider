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

Qt GUI Interface
----------------

The modern Qt GUI provides a tabbed interface with two main tabs:

**Stream Tab** (Main Interface)
    * **Stream Control Panel**: Enter channel name with real-time validation, select quality, watch button
    * **Favorites Panel** (left): Save frequently watched channels, live status monitoring, quick-watch by double-clicking
    * **Chat Panel** (right): Real-time Twitch IRC chat, OAuth authentication, send messages, message history
    * **Status Display** (bottom): Application logs and event messages

**Settings Tab** (Comprehensive Configuration)
    * **Stream Settings**: Player selection (VLC, MPV, MPC-HC, Auto), preferred quality, cache duration, custom player path/arguments
    * **Network Settings**: Timeout configuration, retry attempts, retry delay
    * **Chat Settings**: Auto-connect toggle, maximum messages, timestamp display
    * **Appearance**: Light/Dark theme toggle with immediate preview
    * **Advanced**: Debug mode, log to file, log level, Twitch client ID
    * **Apply Settings** button to save changes
    * **Reset to Defaults** button to restore original settings

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