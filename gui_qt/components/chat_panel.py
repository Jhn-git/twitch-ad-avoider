"""
Chat panel component for TwitchAdAvoider Qt GUI.

This module provides the Twitch chat interface with improved
layout, spacing, and rich text formatting.

The ChatPanel handles:
    - Real-time chat message display
    - Authentication controls
    - Message sending interface
    - Connection status display

Key Features:
    - HTML-formatted messages with timestamps
    - Auto-scrolling to latest messages
    - Message trimming to prevent memory bloat
    - Clean authentication UI
    - Signal-based communication
"""

from PySide6.QtWidgets import (
    QGroupBox, QTextEdit, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QLabel
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QTextCursor, QFont
from datetime import datetime
from typing import Optional

from src.logging_config import get_logger

logger = get_logger(__name__)


class ChatPanel(QGroupBox):
    """
    Manages Twitch chat display and interaction.

    This component provides a clean interface for viewing and
    participating in Twitch chat with rich text formatting.

    Signals:
        login_requested(): Emitted when login button is clicked
        logout_requested(): Emitted when logout button is clicked
        send_message_requested(str): Emitted when message is sent
        clear_requested(): Emitted when clear button is clicked
    """

    # Signals
    login_requested = Signal()
    logout_requested = Signal()
    send_message_requested = Signal(str)  # message
    clear_requested = Signal()

    def __init__(self, parent=None, max_messages: int = 500):
        """
        Initialize the ChatPanel.

        Args:
            parent: Parent widget
            max_messages: Maximum number of messages to keep in display
        """
        super().__init__("Chat", parent)

        self.max_messages = max_messages
        self.message_count = 0
        self.is_logged_in = False
        self.is_connected = False

        # Create UI components
        self._create_ui()

        # Connect signals
        self._connect_signals()

        # Initial state
        self._update_ui_state()

    def _create_ui(self) -> None:
        """Create the UI components."""
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 15, 10, 10)

        # Chat display (read-only)
        self.chat_display = QTextEdit()
        self.chat_display.setObjectName("chatDisplay")
        self.chat_display.setReadOnly(True)
        self.chat_display.setMinimumHeight(200)

        # Set font
        font = QFont("Segoe UI", 10)
        self.chat_display.setFont(font)

        layout.addWidget(self.chat_display)

        # Authentication status and button
        auth_layout = QHBoxLayout()
        auth_layout.setSpacing(10)

        self.auth_status_label = QLabel("Not logged in")
        self.auth_status_label.setObjectName("statusLabel")

        self.auth_button = QPushButton("Login")
        self.auth_button.setObjectName("loginButton")
        self.auth_button.setMinimumWidth(100)

        auth_layout.addWidget(self.auth_status_label)
        auth_layout.addStretch()
        auth_layout.addWidget(self.auth_button)

        layout.addLayout(auth_layout)

        # Message input and send button
        message_layout = QHBoxLayout()
        message_layout.setSpacing(10)

        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Type a message...")
        self.message_input.setEnabled(False)

        self.send_button = QPushButton("Send")
        self.send_button.setMinimumWidth(80)
        self.send_button.setEnabled(False)

        message_layout.addWidget(self.message_input, 1)
        message_layout.addWidget(self.send_button)

        layout.addLayout(message_layout)

        # Connection status and clear button
        status_layout = QHBoxLayout()
        status_layout.setSpacing(10)

        self.connection_status_label = QLabel("Chat disconnected")
        self.connection_status_label.setObjectName("statusLabel")

        self.clear_button = QPushButton("Clear")
        self.clear_button.setMinimumWidth(80)

        status_layout.addWidget(self.connection_status_label)
        status_layout.addStretch()
        status_layout.addWidget(self.clear_button)

        layout.addLayout(status_layout)

        self.setLayout(layout)

    def _connect_signals(self) -> None:
        """Connect internal signals."""
        # Auth button
        self.auth_button.clicked.connect(self._on_auth_button_clicked)

        # Send button
        self.send_button.clicked.connect(self._on_send_clicked)

        # Message input Enter key
        self.message_input.returnPressed.connect(self._on_send_clicked)

        # Clear button
        self.clear_button.clicked.connect(self._on_clear_clicked)

    def _on_auth_button_clicked(self) -> None:
        """Handle auth button click (login/logout)."""
        if self.is_logged_in:
            logger.info("Logout requested")
            self.logout_requested.emit()
        else:
            logger.info("Login requested")
            self.login_requested.emit()

    def _on_send_clicked(self) -> None:
        """Handle send button click or Enter key."""
        message = self.message_input.text().strip()
        if message:
            logger.debug(f"Sending message: {message}")
            self.send_message_requested.emit(message)
            self.message_input.clear()

    def _on_clear_clicked(self) -> None:
        """Handle clear button click."""
        logger.info("Clear chat requested")
        self.clear_requested.emit()
        self.clear_chat()

    def _update_ui_state(self) -> None:
        """Update UI elements based on login and connection state."""
        # Auth button
        if self.is_logged_in:
            self.auth_button.setText("Logout")
            self.auth_status_label.setText("Logged in")
        else:
            self.auth_button.setText("Login")
            self.auth_status_label.setText("Not logged in")

        # Message input and send button
        can_send = self.is_logged_in and self.is_connected
        self.message_input.setEnabled(can_send)
        self.send_button.setEnabled(can_send)

        # Connection status
        if self.is_connected:
            self.connection_status_label.setText("Chat connected")
        else:
            self.connection_status_label.setText("Chat disconnected")

    def add_message(
        self,
        username: str,
        message: str,
        timestamp: Optional[datetime] = None
    ) -> None:
        """
        Add a chat message to the display.

        Args:
            username: Username of the sender
            message: Message text
            timestamp: Message timestamp (defaults to now)
        """
        if timestamp is None:
            timestamp = datetime.now()

        # Convert float timestamp to datetime if needed
        if isinstance(timestamp, float):
            timestamp = datetime.fromtimestamp(timestamp)

        # Format timestamp
        time_str = timestamp.strftime("%H:%M:%S")

        # Build HTML formatted message
        html_message = (
            f'<span style="color: gray;">[{time_str}]</span> '
            f'<span style="color: #9147FF; font-weight: bold;">{username}</span>: '
            f'<span>{message}</span>'
        )

        # Append message
        self.chat_display.append(html_message)

        # Increment message count
        self.message_count += 1

        # Trim old messages if exceeding max
        if self.message_count > self.max_messages:
            self._trim_messages()

        # Auto-scroll to bottom
        self._scroll_to_bottom()

    def add_system_message(self, message: str) -> None:
        """
        Add a system message to the display.

        Args:
            message: System message text
        """
        timestamp = datetime.now().strftime("%H:%M:%S")

        html_message = (
            f'<span style="color: gray;">[{timestamp}]</span> '
            f'<span style="color: #0078D4; font-style: italic;">{message}</span>'
        )

        self.chat_display.append(html_message)
        self._scroll_to_bottom()

    def _trim_messages(self) -> None:
        """Remove old messages to prevent memory bloat."""
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.Start)

        # Remove approximately 20% of messages from the top
        lines_to_remove = self.max_messages // 5

        for _ in range(lines_to_remove):
            cursor.select(QTextCursor.LineUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()  # Remove the newline

        self.message_count -= lines_to_remove

        logger.debug(f"Trimmed {lines_to_remove} old chat messages")

    def _scroll_to_bottom(self) -> None:
        """Scroll the chat display to show the latest message."""
        scrollbar = self.chat_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear_chat(self) -> None:
        """Clear all messages from the chat display."""
        self.chat_display.clear()
        self.message_count = 0
        logger.debug("Chat display cleared")

    def set_logged_in(self, logged_in: bool) -> None:
        """
        Set the login state.

        Args:
            logged_in: True if logged in, False otherwise
        """
        self.is_logged_in = logged_in
        self._update_ui_state()
        logger.debug(f"Login state changed: {logged_in}")

    def set_connected(self, connected: bool) -> None:
        """
        Set the connection state.

        Args:
            connected: True if connected to chat, False otherwise
        """
        self.is_connected = connected
        self._update_ui_state()
        logger.debug(f"Connection state changed: {connected}")

    def get_is_logged_in(self) -> bool:
        """
        Get the current login state.

        Returns:
            True if logged in, False otherwise
        """
        return self.is_logged_in

    def get_is_connected(self) -> bool:
        """
        Get the current connection state.

        Returns:
            True if connected, False otherwise
        """
        return self.is_connected
