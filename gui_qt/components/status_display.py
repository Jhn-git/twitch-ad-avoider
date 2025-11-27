"""
Status display component for TwitchAdAvoider Qt GUI.

This module provides a read-only status message display with
color-coded messages and timestamps.

The StatusDisplay handles:
    - Multi-line status message display
    - Timestamped messages
    - Color-coded message levels (INFO, WARNING, ERROR, SYSTEM)
    - Auto-scrolling to latest messages
    - Message history limiting

Key Features:
    - HTML-formatted messages with colors
    - Monospace font for clean presentation
    - Auto-scroll to bottom
    - Message trimming to prevent memory bloat
"""

from PySide6.QtWidgets import QGroupBox, QTextEdit, QVBoxLayout
from PySide6.QtGui import QTextCursor, QFont
from datetime import datetime
from typing import Optional
from enum import Enum

from src.logging_config import get_logger

logger = get_logger(__name__)


class MessageLevel(Enum):
    """Message severity levels."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    SYSTEM = "SYSTEM"
    STATUS = "STATUS"


class StatusDisplay(QGroupBox):
    """
    Displays status messages with timestamps and color coding.

    This component provides a read-only display for system messages
    with automatic scrolling and message history management.
    """

    # Color mapping for message levels (light theme colors)
    LEVEL_COLORS = {
        MessageLevel.INFO: "#000000",  # Black
        MessageLevel.WARNING: "#FF8C00",  # Dark Orange
        MessageLevel.ERROR: "#DC143C",  # Crimson Red
        MessageLevel.SYSTEM: "#0000FF",  # Blue
        MessageLevel.STATUS: "#000000",  # Black
    }

    # Dark theme colors
    LEVEL_COLORS_DARK = {
        MessageLevel.INFO: "#FFFFFF",  # White
        MessageLevel.WARNING: "#FFA500",  # Orange
        MessageLevel.ERROR: "#FF6B6B",  # Light Red
        MessageLevel.SYSTEM: "#87CEEB",  # Sky Blue
        MessageLevel.STATUS: "#FFFFFF",  # White
    }

    def __init__(self, parent=None, max_messages: int = 100):
        """
        Initialize the StatusDisplay.

        Args:
            parent: Parent widget
            max_messages: Maximum number of messages to keep in history
        """
        super().__init__("Status", parent)

        self.max_messages = max_messages
        self.message_count = 0
        self.dark_mode = False

        # Create UI components
        self._create_ui()

        # Add initial message
        self.add_message("Ready", MessageLevel.SYSTEM)

    def _create_ui(self) -> None:
        """Create the UI components."""
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 15, 10, 10)

        # Text display (read-only)
        self.text_display = QTextEdit()
        self.text_display.setObjectName("statusDisplay")
        self.text_display.setReadOnly(True)
        self.text_display.setMinimumHeight(80)
        self.text_display.setMaximumHeight(120)

        # Set monospace font
        font = QFont("Consolas", 9)
        if not font.exactMatch():
            font = QFont("Courier New", 9)
        self.text_display.setFont(font)

        # Disable word wrap for clean line-by-line display
        self.text_display.setLineWrapMode(QTextEdit.NoWrap)

        layout.addWidget(self.text_display)
        self.setLayout(layout)

    def add_message(
        self, message: str, level: MessageLevel = MessageLevel.INFO, category: Optional[str] = None
    ) -> None:
        """
        Add a status message with timestamp and color coding.

        Args:
            message: Message text to display
            level: Message severity level
            category: Optional message category (e.g., "STREAM", "FAVORITES")
        """
        # Get current timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Select color based on theme
        colors = self.LEVEL_COLORS_DARK if self.dark_mode else self.LEVEL_COLORS
        color = colors.get(level, colors[MessageLevel.INFO])

        # Build HTML formatted message
        if category:
            html_message = (
                f'<span style="color: {color};">' f"[{timestamp}] [{category}] {message}" f"</span>"
            )
        else:
            html_message = (
                f'<span style="color: {color};">'
                f"[{timestamp}] [{level.value}] {message}"
                f"</span>"
            )

        # Append message
        self.text_display.append(html_message)

        # Increment message count
        self.message_count += 1

        # Trim old messages if exceeding max
        if self.message_count > self.max_messages:
            self._trim_messages()

        # Auto-scroll to bottom
        self._scroll_to_bottom()

    def _trim_messages(self) -> None:
        """Remove old messages to prevent memory bloat."""
        # Get all text
        cursor = self.text_display.textCursor()
        cursor.movePosition(QTextCursor.Start)

        # Remove approximately 20% of messages from the top
        lines_to_remove = self.max_messages // 5

        for _ in range(lines_to_remove):
            cursor.select(QTextCursor.LineUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()  # Remove the newline

        self.message_count -= lines_to_remove

        logger.debug(f"Trimmed {lines_to_remove} old messages")

    def _scroll_to_bottom(self) -> None:
        """Scroll the display to show the latest message."""
        scrollbar = self.text_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear(self) -> None:
        """Clear all messages from the display."""
        self.text_display.clear()
        self.message_count = 0
        logger.debug("Status display cleared")

    def set_dark_mode(self, enabled: bool) -> None:
        """
        Set dark mode for color adaptation.

        Args:
            enabled: True for dark mode, False for light mode
        """
        self.dark_mode = enabled

    def add_info(self, message: str, category: Optional[str] = None) -> None:
        """
        Add an INFO level message.

        Args:
            message: Message text
            category: Optional category
        """
        self.add_message(message, MessageLevel.INFO, category)

    def add_warning(self, message: str, category: Optional[str] = None) -> None:
        """
        Add a WARNING level message.

        Args:
            message: Message text
            category: Optional category
        """
        self.add_message(message, MessageLevel.WARNING, category)

    def add_error(self, message: str, category: Optional[str] = None) -> None:
        """
        Add an ERROR level message.

        Args:
            message: Message text
            category: Optional category
        """
        self.add_message(message, MessageLevel.ERROR, category)

    def add_system(self, message: str, category: Optional[str] = None) -> None:
        """
        Add a SYSTEM level message.

        Args:
            message: Message text
            category: Optional category
        """
        self.add_message(message, MessageLevel.SYSTEM, category)
