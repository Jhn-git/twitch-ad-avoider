"""
GUI Components package for TwitchAdAvoider.

This package contains UI component classes that handle specific sections
of the user interface, promoting separation of concerns and modularity.

Components:
    MainWindow: Primary window management and layout coordination
    FavoritesPanel: Favorites list display and interactions (planned)
    StreamControlPanel: Stream controls and input handling (planned)
"""

from .main_window import MainWindow
from .favorites_panel import FavoritesPanel
from .stream_control_panel import StreamControlPanel

__all__ = ['MainWindow', 'FavoritesPanel', 'StreamControlPanel']