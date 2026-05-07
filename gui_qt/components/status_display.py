"""
Activity display component for TwitchAdAvoider Qt GUI.

This module provides a collapsible activity drawer with color-coded
messages and timestamps.

The StatusDisplay handles:
    - Compact latest activity summary
    - Collapsible multi-line activity history
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

from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
)
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
    Displays activity messages with timestamps and color coding.

    This component keeps the main stream view compact while still making
    recent activity available when the user expands the drawer.
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
        super().__init__("Activity", parent)

        self.max_messages = max_messages
        self.message_count = 0
        self.dark_mode = False
        self.expanded = False
        self.unread_count = 0

        # Create UI components
        self._create_ui()

        # Add initial message
        self.add_message("Ready", MessageLevel.SYSTEM)
        self.unread_count = 0
        self.toggle_button.setText(self._collapsed_button_text())

    def _create_ui(self) -> None:
        """Create the UI components."""
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 15, 10, 10)
        layout.setSpacing(8)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        self.summary_label = QLabel("Ready")
        self.summary_label.setObjectName("activitySummary")
        self.summary_label.setMinimumWidth(0)
        self.summary_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        header_layout.addWidget(self.summary_label, 1)

        self.clear_button = QPushButton("Clear")
        self.clear_button.setMaximumWidth(80)
        self.clear_button.clicked.connect(self.clear)
        header_layout.addWidget(self.clear_button)

        self.toggle_button = QPushButton("Show Log")
        self.toggle_button.setCheckable(True)
        self.toggle_button.setMaximumWidth(110)
        self.toggle_button.clicked.connect(self._on_toggle_clicked)
        header_layout.addWidget(self.toggle_button)

        layout.addLayout(header_layout)

        # Text display (read-only)
        self.text_display = QTextEdit()
        self.text_display.setObjectName("statusDisplay")
        self.text_display.setReadOnly(True)
        self.text_display.setMinimumHeight(110)
        self.text_display.setMaximumHeight(180)

        # Set monospace font
        font = QFont("Consolas", 9)
        if not font.exactMatch():
            font = QFont("Courier New", 9)
        self.text_display.setFont(font)

        # Disable word wrap for clean line-by-line display
        self.text_display.setLineWrapMode(QTextEdit.NoWrap)

        layout.addWidget(self.text_display)
        self.setLayout(layout)
        self._set_expanded(False)

    def _on_toggle_clicked(self, checked: bool) -> None:
        """Handle the log drawer toggle button."""
        self._set_expanded(checked)

    def _set_expanded(self, expanded: bool) -> None:
        """Expand or collapse the activity history."""
        self.expanded = expanded
        self.text_display.setVisible(expanded)

        if expanded:
            self.unread_count = 0
            self.toggle_button.setText("Hide Log")
        else:
            self.toggle_button.setText(self._collapsed_button_text())

    def _collapsed_button_text(self) -> str:
        """Return the collapsed drawer button text."""
        if self.unread_count:
            return f"Show Log ({self.unread_count})"
        return "Show Log"

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
        # Send to file logger FIRST (before GUI formatting)
        # This ensures all GUI status messages are written to the log file
        log_message = f"[{category}] {message}" if category else message

        if level == MessageLevel.ERROR:
            logger.error(log_message)
        elif level == MessageLevel.WARNING:
            logger.warning(log_message)
        elif level == MessageLevel.SYSTEM:
            logger.info(log_message)  # SYSTEM → INFO
        else:  # INFO, STATUS, or unknown
            logger.info(log_message)

        # Get current timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")
        summary_text = (
            f"[{timestamp}] {message}" if not category else f"[{timestamp}] {category}: {message}"
        )

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
        self.summary_label.setText(summary_text)

        if not self.expanded:
            self.unread_count += 1
            self.toggle_button.setText(self._collapsed_button_text())

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
        self.unread_count = 0
        self.summary_label.setText("Activity cleared")
        self.toggle_button.setText(self._collapsed_button_text())
        logger.debug("Status display cleared")

    def set_streaming(self, active: bool) -> None:
        """Keep API compatibility for stream state updates."""
        return None

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
