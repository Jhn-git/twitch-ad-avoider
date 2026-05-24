"""Small in-app toast for favorite live notifications."""

from typing import List

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFrame, QLabel, QHBoxLayout, QWidget


class LiveNotificationToast(QFrame):
    """Temporary in-app notification shown when favorite streamers go live."""

    def __init__(self, parent: QWidget, timeout_ms: int = 4500):
        super().__init__(parent)

        self.timeout_ms = timeout_ms
        self.setObjectName("liveNotificationToast")
        self.setStyleSheet(
            """
            QFrame#liveNotificationToast {
                background-color: rgba(26, 31, 39, 238);
                border: 1px solid #2ecc71;
                border-radius: 6px;
            }
            QLabel {
                color: #f8f9fa;
                font-weight: 600;
                padding: 8px 12px;
            }
            """
        )

        self.message_label = QLabel()
        self.message_label.setMinimumWidth(220)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.message_label)
        self.setLayout(layout)

        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide)

        self.hide()

    def show_live_channels(self, channels: List[str]) -> None:
        """Show a live notification for one or more channels."""
        if not channels:
            return

        if len(channels) == 1:
            message = f"{channels[0]} is live now"
        else:
            preview = ", ".join(channels[:3])
            if len(channels) > 3:
                preview += f", +{len(channels) - 3} more"
            message = f"{len(channels)} favorites are live now: {preview}"

        self.message_label.setText(message)
        self.adjustSize()
        self._move_to_corner()
        self.raise_()
        self.show()
        self.hide_timer.start(self.timeout_ms)

    def _move_to_corner(self) -> None:
        """Position the toast near the top-right of the parent window."""
        parent = self.parentWidget()
        if not parent:
            return

        margin = 18
        x = max(margin, parent.width() - self.width() - margin)
        y = margin
        self.move(x, y)
