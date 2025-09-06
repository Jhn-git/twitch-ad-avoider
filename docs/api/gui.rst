gui package
===========

The ``gui`` package provides a comprehensive tkinter-based graphical interface for
TwitchAdAvoider with real-time validation, status monitoring, and theme support.

.. automodule:: gui
   :members:
   :undoc-members:
   :show-inheritance:

GUI Architecture
---------------

The GUI is built using a modular architecture with clear separation of concerns:

1. **Main Interface**: :class:`~gui.stream_gui.StreamGUI` - Primary application window
2. **Favorites Management**: :class:`~gui.favorites_manager.FavoritesManager` - Channel persistence
3. **Status System**: :class:`~gui.status_manager.StatusManager` - Status display and feedback
4. **Theme Support**: :mod:`gui.themes` - Light/dark theme management

Key Features
-----------

- **Real-time Validation**: Input validation with immediate visual feedback
- **Asynchronous Operations**: Non-blocking UI with threaded operations  
- **Cross-platform Support**: Works on Windows, macOS, and Linux
- **Status Monitoring**: Live channel status tracking for favorites
- **Theme Customization**: Light and dark theme support

Usage Patterns
--------------

Common GUI integration patterns:

.. code-block:: python

   # Basic GUI initialization
   from gui.stream_gui import StreamGUI
   from src.config_manager import ConfigManager
   
   config = ConfigManager()
   app = StreamGUI(config)
   app.run()
   
   # Favorites management
   from gui.favorites_manager import FavoritesManager
   
   favorites = FavoritesManager()
   favorites.add_favorite("ninja")
   channel_info = favorites.get_favorite_info("ninja")

Integration with Core
-------------------

The GUI integrates seamlessly with core functionality:

- Uses :class:`~src.twitch_viewer.TwitchViewer` for streaming operations
- Leverages :mod:`src.validators` for input validation
- Integrates with :class:`~src.config_manager.ConfigManager` for settings
- Handles :mod:`src.exceptions` for user-friendly error display

Submodules
----------

gui.favorites\_manager module
-----------------------------

.. automodule:: gui.favorites_manager
   :members:
   :undoc-members:
   :show-inheritance:

gui.status\_manager module
--------------------------

.. automodule:: gui.status_manager
   :members:
   :undoc-members:
   :show-inheritance:

gui.stream\_gui module
----------------------

.. automodule:: gui.stream_gui
   :members:
   :undoc-members:
   :show-inheritance:

gui.themes module
-----------------

.. automodule:: gui.themes
   :members:
   :undoc-members:
   :show-inheritance: