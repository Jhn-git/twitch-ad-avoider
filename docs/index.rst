Welcome to TwitchAdAvoider's documentation!
==========================================

TwitchAdAvoider is a security-focused Python application for watching Twitch streams while avoiding ads.
It features a modern Qt GUI and command-line interface, with comprehensive input validation, Twitch chat integration, and cross-platform video player support.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   installation
   quickstart
   api/modules
   security
   contributing

Features
--------

* **Security First**: All user inputs are validated and sanitized
* **Modern Qt GUI**: Professional PySide6-based interface with tabbed panels
* **Cross-Platform**: Supports Windows, macOS, and Linux
* **Multiple Players**: VLC, MPV, MPC-HC with auto-detection
* **Twitch Chat Integration**: Real-time IRC chat with OAuth authentication
* **GUI and CLI**: Both graphical and command-line interfaces
* **Favorites Management**: Save and monitor favorite channels with live status
* **Theme Support**: Light and dark themes with QSS stylesheets
* **Network Reliability**: Configurable timeouts and retry logic

Quick Start
-----------

Install the application::

    pip install -e .

Run with GUI::

    python main.py

Run from command line::

    python main.py --channel ninja --quality 720p

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`