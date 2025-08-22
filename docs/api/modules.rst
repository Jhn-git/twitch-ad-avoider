API Reference
=============

This section provides comprehensive API documentation for all modules in TwitchAdAvoider,
including cross-references, usage examples, and integration patterns.

The API is organized into two main categories:

**Core Modules** (:mod:`src`)
    These modules provide the core streaming functionality, configuration management,
    input validation, and security features. They form the foundation of the application
    and can be used independently of the GUI.

**GUI Modules** (:mod:`gui`)  
    These modules provide the graphical user interface built with tkinter, including
    the main window, favorites management, theme support, and status monitoring.

Core Modules
------------

The core modules handle all streaming operations and security validation:

.. toctree::
   :maxdepth: 4

   src

Key integration points:
    - :class:`~src.twitch_viewer.TwitchViewer`: Main streaming interface
    - :class:`~src.config_manager.ConfigManager`: Configuration and settings
    - :mod:`src.validators`: Security validation functions
    - :mod:`src.exceptions`: Custom exception hierarchy

GUI Modules  
-----------

The GUI modules provide a user-friendly interface with advanced features:

.. toctree::
   :maxdepth: 4

   gui

Key GUI components:
    - :class:`~gui.stream_gui.StreamGUI`: Main application window
    - :class:`~gui.favorites_manager.FavoritesManager`: Channel favorites handling
    - :class:`~gui.status_manager.StatusManager`: Status display and management
    - :mod:`gui.themes`: Theme and styling support