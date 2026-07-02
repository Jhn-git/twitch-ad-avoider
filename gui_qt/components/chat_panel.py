"""Stream actions panel for TwitchAdAvoider Qt GUI."""

from pathlib import Path

from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFrame,
    QGroupBox,
    QLabel,
    QMenu,
    QPushButton,
    QToolButton,
    QVBoxLayout,
)

from gui_qt.popup_utils import configure_menu_popup_surface
from src.constants import CLIPS_DIR
from src.logging_config import get_logger

logger = get_logger(__name__)


class ChatPanel(QGroupBox):
    """Channel and stream controls: open channel/chat in browser, clip.

    Signals:
        open_chat_requested(): Emitted when Open Chat is clicked.
        open_channel_requested(): Emitted when Open Channel is clicked.
        clip_requested(): Emitted when Clip is clicked.
    """

    open_chat_requested = Signal()
    open_channel_requested = Signal()
    clip_requested = Signal(int)

    def __init__(self, parent=None):
        super().__init__("Stream", parent)
        self._channel: str = ""

        layout = QVBoxLayout()
        layout.setSpacing(6)
        layout.setContentsMargins(10, 15, 10, 10)
        layout.setAlignment(Qt.AlignTop)

        self._channel_label = QLabel("No channel active")
        self._channel_label.setAlignment(Qt.AlignCenter)
        self._channel_label.setObjectName("statusLabel")
        layout.addWidget(self._channel_label)

        layout.addSpacing(4)

        self._open_channel_button = QPushButton("Open Channel")
        self._open_channel_button.setEnabled(False)
        self._open_channel_button.setMinimumWidth(160)
        self._open_channel_button.clicked.connect(self.open_channel_requested)
        layout.addWidget(self._open_channel_button)

        self._open_chat_button = QPushButton("Open Chat")
        self._open_chat_button.setEnabled(False)
        self._open_chat_button.setMinimumWidth(160)
        self._open_chat_button.setToolTip(
            "Open Twitch chat in your default browser. If that browser is already logged into "
            "Twitch, you will chat as that account."
        )
        self._open_chat_button.clicked.connect(self.open_chat_requested)
        layout.addWidget(self._open_chat_button)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addSpacing(6)
        layout.addWidget(separator)
        layout.addSpacing(6)

        _clip_durations = [
            ("Last 30s", 30),
            ("Last 1 min", 60),
            ("Last 2 min", 120),
            ("Last 5 min", 300),
        ]

        self._clip_button = QToolButton()
        self._clip_button.setObjectName("clipSplitButton")
        self._clip_button.setText("Clip (30s)")
        self._clip_button.setToolTip("Click to clip last 30s, or use the arrow for more durations")
        self._clip_button.setEnabled(False)
        self._clip_button.setMinimumWidth(160)
        self._clip_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)

        clip_menu = QMenu(self._clip_button)
        clip_menu.setObjectName("clipDurationMenu")
        configure_menu_popup_surface(clip_menu)
        for label, seconds in _clip_durations:
            action = clip_menu.addAction(label)
            action.triggered.connect(lambda checked=False, s=seconds: self.clip_requested.emit(s))

        self._clip_menu = clip_menu
        self._clip_button.setMenu(clip_menu)
        self._clip_button.clicked.connect(lambda: self.clip_requested.emit(30))
        layout.addWidget(self._clip_button)

        self._open_clips_button = QPushButton("Open Clips Folder")
        self._open_clips_button.setToolTip(f"Open the clips folder ({CLIPS_DIR})")
        self._open_clips_button.setMinimumWidth(160)
        self._open_clips_button.clicked.connect(self._open_clips_folder)
        layout.addWidget(self._open_clips_button)

        layout.addStretch()
        self.setLayout(layout)

    def _open_clips_folder(self) -> None:
        clips_path = Path(CLIPS_DIR).resolve()
        clips_path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(clips_path)))

    def set_channel(self, channel: str) -> None:
        """Update the active channel and enable channel-dependent buttons.

        Args:
            channel: Twitch channel name; pass empty string to reset.
        """
        self._channel = channel
        if channel:
            self._channel_label.setText(f"Channel: #{channel}")
            self._open_channel_button.setEnabled(True)
            self._open_chat_button.setEnabled(True)
        else:
            self._channel_label.setText("No channel active")
            self._open_channel_button.setEnabled(False)
            self._open_chat_button.setEnabled(False)

    def set_streaming(self, active: bool) -> None:
        """Enable or disable the clip button based on stream state.

        Args:
            active: Whether a stream is currently running.
        """
        self._clip_button.setEnabled(active)

    @property
    def channel(self) -> str:
        """Currently tracked channel name."""
        return self._channel
