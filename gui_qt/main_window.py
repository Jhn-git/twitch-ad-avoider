"""
Main window for TwitchAdAvoider Qt GUI.

This module provides the primary window management and layout coordination
using PySide6 with improved spacing, organization, and visual polish.

The MainWindow handles:
    - Window initialization and configuration
    - Main layout structure with proper spacing
    - Component coordination and integration
    - Window lifecycle management (closing, cleanup)
    - Theme management and stylesheet loading

Key Features:
    - Modern Qt-based layout with QGridLayout
    - Persistent window state (size, position, maximized)
    - Clean component integration
    - Proper cleanup on window close
    - Theme-aware styling with QStyleSheet
"""

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QGridLayout,
    QVBoxLayout,
    QTabWidget,
)
from PySide6.QtGui import QCloseEvent
from typing import Optional, List, Callable
import subprocess
from pathlib import Path

from src.config_manager import ConfigManager
from src.logging_config import get_logger

logger = get_logger(__name__)

# GUI Configuration Constants
DEFAULT_WIDTH = 800
DEFAULT_HEIGHT = 650
MIN_WIDTH = 700
MIN_HEIGHT = 550


class MainWindow(QMainWindow):
    """
    Main application window for TwitchAdAvoider Qt GUI.

    This component handles the primary window setup, layout management,
    and coordinates integration between various GUI components with
    improved spacing and visual organization.
    """

    def __init__(self, config: ConfigManager):
        """
        Initialize the MainWindow.

        Args:
            config: Configuration manager instance
        """
        super().__init__()

        self.config = config

        # Component tracking
        self.components: List[any] = []

        # Process tracking for cleanup
        self.current_stream_process: Optional[subprocess.Popen] = None

        # Window close callbacks
        self.on_closing_callbacks: List[Callable[[], None]] = []

        # Current theme
        self.current_theme = config.get("dark_mode", False)

        # Initialize window
        self._setup_window()

        # Create central widget and main layout
        self._create_main_layout()

        # Load and apply theme
        self._apply_theme()

    def _setup_window(self) -> None:
        """Configure the main window properties."""
        self.setWindowTitle("TwitchAdAvoider - Stream Manager")

        # Load saved window state from config
        width = self.config.get("window_width", DEFAULT_WIDTH)
        height = self.config.get("window_height", DEFAULT_HEIGHT)
        is_maximized = self.config.get("window_maximized", False)

        # Set window size
        self.resize(width, height)
        self.setMinimumSize(MIN_WIDTH, MIN_HEIGHT)

        # Apply maximized state if saved
        if is_maximized:
            self.showMaximized()

    def _create_main_layout(self) -> None:
        """
        Create the main layout structure with tabbed interface.

        Layout structure:
        +--------------------------------------------------+
        | Tab 1: Stream                                    |
        |   +----------------------------------------------+|
        |   |  Current Stream controls                     ||
        |   +----------------------------------------------+|
        |   |                    |                         ||
        |   |  Favorites Panel   |   Chat Panel            ||
        |   |  (left)            |   (right)               ||
        |   |                    |                         ||
        |   +--------------------+-------------------------+|
        |   |  Activity drawer (bottom)                    ||
        |   +----------------------------------------------+|
        |                                                  |
        | Tab 2: Settings                                  |
        |   (Settings tab content)                         |
        +--------------------------------------------------+
        """
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Create main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Create tab widget
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # Create stream tab (will hold the main stream interface)
        self.stream_tab = QWidget()
        self.stream_tab_layout = QGridLayout(self.stream_tab)
        self.stream_tab_layout.setSpacing(12)
        self.stream_tab_layout.setContentsMargins(15, 15, 15, 15)

        # Grid layout weights for stream tab:
        # Row 0: Current stream controls
        # Row 1: Favorites + Chat (expandable)
        # Row 2: Activity drawer
        self.stream_tab_layout.setRowStretch(0, 0)
        self.stream_tab_layout.setRowStretch(1, 1)
        self.stream_tab_layout.setRowStretch(2, 0)

        # Column 0: Favorites (40% width)
        # Column 1: Chat (60% width)
        self.stream_tab_layout.setColumnStretch(0, 2)
        self.stream_tab_layout.setColumnStretch(1, 3)

        # Add stream tab to tab widget
        self.tab_widget.addTab(self.stream_tab, "Stream")

        # Store references
        self.central_widget = central_widget
        self.main_layout = self.stream_tab_layout  # For backward compatibility

    def add_component_to_layout(
        self, component: QWidget, row: int, column: int, row_span: int = 1, column_span: int = 1
    ) -> None:
        """
        Add a component to the stream tab grid layout.

        Args:
            component: Widget to add
            row: Grid row position
            column: Grid column position
            row_span: Number of rows to span
            column_span: Number of columns to span
        """
        self.main_layout.addWidget(component, row, column, row_span, column_span)
        self.components.append(component)

    def add_settings_tab(self, settings_widget: QWidget) -> None:
        """
        Add the settings tab to the tab widget.

        Args:
            settings_widget: Settings widget to add as a tab
        """
        self.tab_widget.addTab(settings_widget, "Settings")
        self.components.append(settings_widget)
        logger.debug("Settings tab added to tab widget")

    def _apply_theme(self) -> None:
        """Load and apply the current theme stylesheet."""
        theme_name = "dark" if self.current_theme else "light"
        stylesheet_path = Path(__file__).parent / "styles" / f"{theme_name}.qss"

        try:
            if stylesheet_path.exists():
                with open(stylesheet_path, "r", encoding="utf-8") as f:
                    stylesheet = f.read()
                    self.setStyleSheet(stylesheet)
                logger.info(f"Applied {theme_name} theme")
            else:
                logger.warning(f"Theme file not found: {stylesheet_path}")
        except Exception as e:
            logger.error(f"Failed to load theme: {e}")

    def switch_theme(self, dark_mode: bool) -> None:
        """
        Switch between light and dark themes.

        Args:
            dark_mode: True for dark theme, False for light theme
        """
        self.current_theme = dark_mode
        self.config.set("dark_mode", dark_mode)
        self._apply_theme()

        logger.info(f"Switched to {'dark' if dark_mode else 'light'} theme")

    def register_on_closing_callback(self, callback: Callable[[], None]) -> None:
        """
        Register a callback to be called when window is closing.

        Args:
            callback: Function to call on window close
        """
        self.on_closing_callbacks.append(callback)

    def save_window_state(self) -> None:
        """Save current window state to configuration."""
        # Save window size if not maximized
        if not self.isMaximized():
            self.config.set("window_width", self.width())
            self.config.set("window_height", self.height())

        # Save maximized state
        self.config.set("window_maximized", self.isMaximized())

        logger.debug(
            f"Saved window state: {self.width()}x{self.height()}, maximized={self.isMaximized()}"
        )

    def closeEvent(self, event: QCloseEvent) -> None:
        """
        Handle window close event with proper cleanup.

        Args:
            event: Close event from Qt
        """
        logger.info("Window closing - performing cleanup")

        # Save window state
        self.save_window_state()

        # Terminate stream process if running
        if self.current_stream_process and self.current_stream_process.poll() is None:
            logger.info("Terminating active stream process")
            try:
                self.current_stream_process.terminate()
                self.current_stream_process.wait(timeout=2)
            except Exception as e:
                logger.error(f"Error terminating stream process: {e}")
                try:
                    self.current_stream_process.kill()
                except Exception:
                    pass

        # Execute all registered cleanup callbacks
        for callback in self.on_closing_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Error in closing callback: {e}")

        # Save configuration
        try:
            self.config.save_settings()
            logger.info("Configuration saved successfully")
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")

        # Accept the close event
        event.accept()
        logger.info("Window closed successfully")

    def set_stream_process(self, process: Optional[subprocess.Popen]) -> None:
        """
        Set the current stream process for cleanup tracking.

        Args:
            process: Subprocess.Popen instance or None
        """
        self.current_stream_process = process
