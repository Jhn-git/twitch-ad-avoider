Welcome to TwitchAdAvoider's documentation!
==========================================

TwitchAdAvoider is a security-focused Python application for watching Twitch streams while avoiding ads. 
It features both GUI and command-line interfaces, with comprehensive input validation and cross-platform video player support.

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
* **Cross-Platform**: Supports Windows, macOS, and Linux  
* **Multiple Players**: VLC, MPV, MPC-HC with auto-detection
* **GUI and CLI**: Both graphical and command-line interfaces
* **Favorites Management**: Save and monitor favorite channels
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