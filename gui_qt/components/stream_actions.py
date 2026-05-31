"""Current stream status strip for the TwitchAdAvoider Qt GUI."""

from PySide6.QtWidgets import QGroupBox, QHBoxLayout, QLabel, QSizePolicy


class StreamActions(QGroupBox):
    """Shows the active stream state (Idle / Starting / Live)."""

    def __init__(self, parent=None):
        super().__init__("Current Stream", parent)
        self._create_ui()
        self.set_streaming(False)

    def _create_ui(self) -> None:
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 15, 10, 10)
        layout.setSpacing(10)

        self.state_label = QLabel("Idle")
        self.state_label.setObjectName("streamStateLabel")
        layout.addWidget(self.state_label)

        self.detail_label = QLabel("No stream active")
        self.detail_label.setObjectName("hintLabel")
        self.detail_label.setMinimumWidth(0)
        self.detail_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        layout.addWidget(self.detail_label, 1)

        self.setLayout(layout)

    def set_streaming(self, active: bool, channel: str = "", quality: str = "best") -> None:
        """Update the visible stream state.

        Args:
            active: Whether a stream is currently running.
            channel: Active Twitch channel name.
            quality: Requested stream quality.
        """
        if active:
            self.state_label.setText("Live")
            self.detail_label.setText(f"{channel} @ {quality}")
        elif channel:
            self.state_label.setText("Starting")
            self.detail_label.setText(f"{channel} @ {quality}")
        else:
            self.state_label.setText("Idle")
            self.detail_label.setText("No stream active")
