API Reference
=============

This section provides comprehensive API documentation for all modules in TwitchAdAvoider,
including cross-references, usage examples, and integration patterns.

The API is organized into two main categories:

**Core Modules** (:mod:`src`)
    These modules provide the core streaming functionality, configuration management,
    input validation, and security features. They form the foundation of the application
    and can be used independently of the GUI.

**Qt GUI Modules** (:mod:`gui_qt`)
    These modules provide the modern graphical user interface built with PySide6 Qt, including
    the main window, tabbed panels, chat integration, theme support, and status monitoring.

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

Qt GUI Modules
--------------

The Qt GUI modules provide a modern, professional interface with advanced features:

.. toctree::
   :maxdepth: 4

   gui_qt

Key Qt GUI components:
    - :class:`~gui_qt.stream_gui.StreamGUI`: Main Qt application window
    - :class:`~gui_qt.main_window.MainWindow`: Tabbed interface container
    - :class:`~gui_qt.components.favorites_panel.FavoritesPanel`: Channel favorites with status monitoring
    - :class:`~gui_qt.components.chat_panel.ChatPanel`: Real-time Twitch IRC chat
    - :class:`~gui_qt.controllers.stream_controller.StreamController`: Stream management controller
    - :mod:`gui_qt.styles`: QSS theme stylesheets (light and dark)