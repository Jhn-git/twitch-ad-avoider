"""
GUI Components package for TwitchAdAvoider.

This package contains UI component classes that handle specific sections
of the user interface, promoting separation of concerns and modularity.

Components:
    MainWindow: Primary window management and layout coordination
    FavoritesPanel: Favorites list display and interactions
    StreamControlPanel: Stream controls and input handling
    ChatPanel: Real-time chat display and management
"""

from .main_window import MainWindow
from .favorites_panel import FavoritesPanel
from .stream_control_panel import StreamControlPanel
from .chat_panel import ChatPanel

__all__ = ['MainWindow', 'FavoritesPanel', 'StreamControlPanel', 'ChatPanel']