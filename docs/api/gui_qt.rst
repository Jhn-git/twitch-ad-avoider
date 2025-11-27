gui_qt package
==============

The ``gui_qt`` package provides a modern PySide6 Qt-based graphical interface for
TwitchAdAvoider with real-time validation, status monitoring, chat integration, and theme support.

.. automodule:: gui_qt
   :members:
   :undoc-members:
   :show-inheritance:

Qt GUI Architecture
-------------------

The Qt GUI is built using a modular signal-based architecture with clear separation of concerns:

1. **Main Interface**: :class:`~gui_qt.stream_gui.StreamGUI` - Primary application window
2. **Main Window**: :class:`~gui_qt.main_window.MainWindow` - Tabbed interface container
3. **Components**: Dedicated panels for streaming, favorites, chat, and settings
4. **Controllers**: Business logic controllers for stream, chat, and validation
5. **Styles**: QSS stylesheets for light and dark themes

Key Features
-----------

- **Modern Qt Interface**: Professional PySide6-based GUI with native look and feel
- **Tabbed Navigation**: Organized interface with Stream, Favorites, Chat, and Settings panels
- **Real-time Validation**: Input validation with immediate visual feedback
- **Signal-Based Architecture**: Responsive UI using Qt signals and slots
- **Asynchronous Operations**: Non-blocking UI with threaded operations
- **Cross-platform Support**: Works on Windows, macOS, and Linux
- **Status Monitoring**: Live channel status tracking for favorites
- **Chat Integration**: Real-time Twitch IRC chat with OAuth authentication
- **Theme Customization**: Light and dark themes with QSS stylesheets

Usage Patterns
--------------

Common Qt GUI integration patterns:

.. code-block:: python

   # Basic Qt GUI initialization
   from PySide6.QtWidgets import QApplication
   from gui_qt.stream_gui import StreamGUI
   from src.config_manager import ConfigManager
   import sys

   app = QApplication(sys.argv)
   config = ConfigManager()
   gui = StreamGUI(config)
   gui.show()
   sys.exit(app.exec())

   # Using controllers
   from gui_qt.controllers.stream_controller import StreamController

   stream_controller = StreamController(config)
   stream_controller.watch_stream("ninja", "best")

Integration with Core
-------------------

The Qt GUI integrates seamlessly with core functionality:

- Uses :class:`~src.twitch_viewer.TwitchViewer` for streaming operations
- Leverages :mod:`src.validators` for input validation
- Integrates with :class:`~src.config_manager.ConfigManager` for settings
- Integrates with :class:`~src.auth_manager.AuthManager` for OAuth authentication
- Uses :class:`~src.twitch_chat_client.TwitchChatClient` for IRC chat
- Handles :mod:`src.exceptions` for user-friendly error display

Components
----------

gui_qt.components.chat\_panel module
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. automodule:: gui_qt.components.chat_panel
   :members:
   :undoc-members:
   :show-inheritance:

gui_qt.components.favorites\_panel module
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. automodule:: gui_qt.components.favorites_panel
   :members:
   :undoc-members:
   :show-inheritance:

gui_qt.components.settings\_panel module
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. automodule:: gui_qt.components.settings_panel
   :members:
   :undoc-members:
   :show-inheritance:

gui_qt.components.status\_display module
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. automodule:: gui_qt.components.status_display
   :members:
   :undoc-members:
   :show-inheritance:

gui_qt.components.stream\_control\_panel module
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. automodule:: gui_qt.components.stream_control_panel
   :members:
   :undoc-members:
   :show-inheritance:

Controllers
-----------

gui_qt.controllers.chat\_controller module
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. automodule:: gui_qt.controllers.chat_controller
   :members:
   :undoc-members:
   :show-inheritance:

gui_qt.controllers.stream\_controller module
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. automodule:: gui_qt.controllers.stream_controller
   :members:
   :undoc-members:
   :show-inheritance:

gui_qt.controllers.validation\_controller module
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. automodule:: gui_qt.controllers.validation_controller
   :members:
   :undoc-members:
   :show-inheritance:

Main Modules
------------

gui_qt.main\_window module
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. automodule:: gui_qt.main_window
   :members:
   :undoc-members:
   :show-inheritance:

gui_qt.stream\_gui module
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. automodule:: gui_qt.stream_gui
   :members:
   :undoc-members:
   :show-inheritance:

gui_qt.styles module
^^^^^^^^^^^^^^^^^^^^

.. automodule:: gui_qt.styles
   :members:
   :undoc-members:
   :show-inheritance: