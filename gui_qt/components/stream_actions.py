"""Current stream action strip for the TwitchAdAvoider Qt GUI."""

from pathlib import Path

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QGroupBox, QHBoxLayout, QLabel, QPushButton, QSizePolicy

from src.constants import CLIPS_DIR


class StreamActions(QGroupBox):
    """Shows the active stream state and exposes stream-related actions."""

    clip_requested = Signal()

    def __init__(self, parent=None):
        """Initialize the stream action strip.

        Args:
            parent: Parent widget.
        """
        super().__init__("Current Stream", parent)
        self._channel = ""
        self._quality = "best"
        self._create_ui()
        self.set_streaming(False)

    def _create_ui(self) -> None:
        """Create the stream action controls."""
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

        self.clip_button = QPushButton("Clip (30s)")
        self.clip_button.setToolTip("Save the last 30 seconds to a local file")
        self.clip_button.clicked.connect(self.clip_requested)
        layout.addWidget(self.clip_button)

        self.open_clips_button = QPushButton("Open Clips Folder")
        self.open_clips_button.setToolTip(f"Open the clips folder ({CLIPS_DIR})")
        self.open_clips_button.clicked.connect(self._open_clips_folder)
        layout.addWidget(self.open_clips_button)

        self.setLayout(layout)

    def _open_clips_folder(self) -> None:
        """Open the clips folder in the system file explorer."""
        clips_path = Path(CLIPS_DIR).resolve()
        clips_path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(clips_path)))

    def set_streaming(self, active: bool, channel: str = "", quality: str = "best") -> None:
        """Update the visible stream state.

        Args:
            active: Whether a stream is currently running.
            channel: Active Twitch channel name.
            quality: Requested stream quality.
        """
        self._channel = channel
        self._quality = quality
        self.clip_button.setEnabled(active)

        if active:
            self.state_label.setText("Live")
            self.detail_label.setText(f"{channel} @ {quality}")
        elif channel:
            self.state_label.setText("Starting")
            self.detail_label.setText(f"{channel} @ {quality}")
        else:
            self.state_label.setText("Idle")
            self.detail_label.setText("No stream active")
