src package
===========

The ``src`` package contains the core functionality of TwitchAdAvoider, providing
streaming capabilities, configuration management, input validation, and security features.

.. automodule:: src
   :members:
   :undoc-members:
   :show-inheritance:

Architecture Overview
--------------------

The core modules work together to provide secure, reliable streaming:

1. **Input Layer**: :mod:`src.validators` ensures all user inputs are safe
2. **Configuration Layer**: :class:`~src.config_manager.ConfigManager` manages settings
3. **Streaming Layer**: :class:`~src.twitch_viewer.TwitchViewer` handles stream operations
4. **Monitoring Layer**: :mod:`src.status_monitor` tracks channel status

Security Features
----------------

The src package implements comprehensive security measures:

- **Input Validation**: All inputs pass through :mod:`src.validators`
- **Path Traversal Protection**: File path validation prevents directory traversal
- **Command Injection Prevention**: Player arguments are sanitized
- **Error Handling**: Custom exceptions in :mod:`src.exceptions`

Cross-Module Integration
----------------------

Key integration patterns used throughout the codebase:

.. code-block:: python

   # Standard initialization pattern
   from src.config_manager import ConfigManager
   from src.twitch_viewer import TwitchViewer
   
   config = ConfigManager()
   viewer = TwitchViewer(config)
   
   # Validation integration
   from src.validators import validate_channel_name
   channel = validate_channel_name(user_input)
   viewer.watch_stream(channel, "720p")

Submodules
----------

src.config\_manager module
--------------------------

.. automodule:: src.config_manager
   :members:
   :undoc-members:
   :show-inheritance:

src.constants module
--------------------

.. automodule:: src.constants
   :members:
   :undoc-members:
   :show-inheritance:

src.exceptions module
---------------------

.. automodule:: src.exceptions
   :members:
   :undoc-members:
   :show-inheritance:

src.logging\_config module
--------------------------

.. automodule:: src.logging_config
   :members:
   :undoc-members:
   :show-inheritance:

src.status\_monitor module
--------------------------

.. automodule:: src.status_monitor
   :members:
   :undoc-members:
   :show-inheritance:

src.streamlink\_status module
-----------------------------

.. automodule:: src.streamlink_status
   :members:
   :undoc-members:
   :show-inheritance:

src.twitch\_viewer module
-------------------------

.. automodule:: src.twitch_viewer
   :members:
   :undoc-members:
   :show-inheritance:

src.validators module
---------------------

.. automodule:: src.validators
   :members:
   :undoc-members:
   :show-inheritance: