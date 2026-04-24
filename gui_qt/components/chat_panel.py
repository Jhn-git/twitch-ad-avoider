"""Chat panel component for TwitchAdAvoider Qt GUI."""

from PySide6.QtWidgets import QGroupBox, QPushButton, QVBoxLayout, QLabel
from PySide6.QtCore import Signal, Qt

from src.logging_config import get_logger

logger = get_logger(__name__)


class ChatPanel(QGroupBox):
    """Opens Twitch chat in the default browser for the current channel.

    Signals:
        open_chat_requested(): Emitted when the open button is clicked.
    """

    open_chat_requested = Signal()

    def __init__(self, parent=None):
        super().__init__("Chat", parent)
        self._channel: str = ""

        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 15, 10, 10)
        layout.setAlignment(Qt.AlignCenter)

        self._channel_label = QLabel("No channel active")
        self._channel_label.setAlignment(Qt.AlignCenter)
        self._channel_label.setObjectName("statusLabel")

        self._open_button = QPushButton("Open Chat in Browser")
        self._open_button.setEnabled(False)
        self._open_button.setMinimumWidth(160)
        self._open_button.clicked.connect(self.open_chat_requested)

        self._hint_label = QLabel("Opens official Twitch chat in your browser")
        self._hint_label.setAlignment(Qt.AlignCenter)
        self._hint_label.setObjectName("hintLabel")

        layout.addStretch()
        layout.addWidget(self._channel_label)
        layout.addWidget(self._open_button, 0, Qt.AlignCenter)
        layout.addWidget(self._hint_label)
        layout.addStretch()

        self.setLayout(layout)

    def set_channel(self, channel: str) -> None:
        """Update the active channel and enable the button.

        Args:
            channel: Twitch channel name; pass empty string to reset.
        """
        self._channel = channel
        if channel:
            self._channel_label.setText(f"Chat: #{channel}")
            self._open_button.setEnabled(True)
        else:
            self._channel_label.setText("No channel active")
            self._open_button.setEnabled(False)

    @property
    def channel(self) -> str:
        """Currently tracked channel name."""
        return self._channel
