"""Stream actions panel for TwitchAdAvoider Qt GUI."""

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSize, QUrl, Qt, Signal
from PySide6.QtGui import QColor, QDesktopServices, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QGroupBox,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
)

from gui_qt.popup_utils import configure_menu_popup_surface
from src.constants import CLIPS_DIR
from src.logging_config import get_logger

logger = get_logger(__name__)


class _LandscapePreviewLabel(QLabel):
    """A QLabel that always fills its layout's width at a fixed 16:9 ratio.

    Stream thumbnails are inherently landscape, so height is derived from
    whatever width the surrounding layout assigns rather than a fixed pixel
    size - the preview scales naturally with the window instead of leaving
    dead space on wide layouts or clipping on narrow ones.
    """

    _ASPECT_RATIO = 16 / 9  # width / height
    _DIMMED_OPACITY = 0.55
    _DIMMED_TITLE_STYLE = "background-color: rgba(0, 0, 0, 90); color: rgba(255, 255, 255, 140);"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._source_pixmap: Optional[QPixmap] = None
        self._max_height: Optional[int] = None
        self._dimmed = False

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(160)
        self.setAlignment(Qt.AlignCenter)

        # Caption overlay lives directly on the image (rather than its own
        # row below it) so the title doesn't eat into the image's own,
        # already-limited vertical budget - it's positioned/sized manually
        # since it isn't managed by a layout.
        self.title_label = QLabel(self)
        self.title_label.setObjectName("streamPreviewTitle")
        self.title_label.setWordWrap(True)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setVisible(False)
        title_shadow = QGraphicsDropShadowEffect(self.title_label)
        title_shadow.setBlurRadius(4)
        title_shadow.setOffset(1, 1)
        title_shadow.setColor(QColor(0, 0, 0, 200))
        self.title_label.setGraphicsEffect(title_shadow)

        self._sync_height()

    def set_source_pixmap(self, pixmap: Optional[QPixmap]) -> None:
        """Set the full-resolution source image to scale on every resize."""
        self._source_pixmap = pixmap
        self._apply_scaled_pixmap()

    def set_title(self, title: str) -> None:
        """Show (or hide, if empty) the caption overlaid on the image."""
        text = title or ""
        self.title_label.setText(text)
        self.title_label.setVisible(bool(text))
        self._position_title_overlay()

    def set_dimmed(self, dimmed: bool) -> None:
        """Desaturate and fade the preview, or restore it to normal.

        Used while a stream is actively being watched: the preview stays
        visible (so context isn't lost) but recedes visually instead of
        competing with the video for attention.

        Both the image and the title's dimming are baked into pixel data /
        an inline stylesheet rather than a QGraphicsEffect on this widget -
        a QGraphicsEffect here was found to suppress title_label's own
        stylesheet-painted background entirely (a Qt quirk where a parent
        widget's effect breaks rendering of a child that has its own
        separate QGraphicsEffect, i.e. title_label's drop shadow).
        """
        if dimmed == self._dimmed:
            return
        self._dimmed = dimmed
        self.title_label.setStyleSheet(self._DIMMED_TITLE_STYLE if dimmed else "")
        self._apply_scaled_pixmap()

    def set_max_height(self, max_height: int) -> None:
        """Cap the width-driven height to whatever vertical room is available.

        Without this, height (derived purely from width at a fixed 16:9
        ratio) can demand more vertical space than the panel actually has on
        wide-but-not-proportionally-tall windows, which overflows the parent
        layout instead of just shrinking the preview.
        """
        self._max_height = max(max_height, 1)
        self._sync_height()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._sync_height()
        self._apply_scaled_pixmap()
        self._position_title_overlay()

    def _position_title_overlay(self) -> None:
        if self.width() <= 0 or not self.title_label.text():
            return
        width = self.width()
        self.title_label.setFixedWidth(width)
        height = self.title_label.heightForWidth(width)
        if height <= 0:
            height = self.title_label.sizeHint().height()
        self.title_label.setGeometry(0, self.height() - height, width, height)

    def sizeHint(self) -> QSize:
        # Derived from the fixed minimum width, never from the held pixmap -
        # QLabel's default sizeHint/minimumSizeHint tracks the current pixmap
        # size, which would feed back into the parent QGridLayout's column
        # width negotiation on every resize and cause runaway growth during
        # an interactive drag.
        width = max(self.minimumWidth(), 1)
        return QSize(width, round(width / self._ASPECT_RATIO))

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def _sync_height(self) -> None:
        # Pin height directly via min/max rather than relying on Qt's
        # heightForWidth machinery, which QVBoxLayout only honors reliably
        # when every sibling widget also opts in - fixing the height here
        # keeps this widget's aspect ratio correct regardless of its siblings.
        target_height = round(self.width() / self._ASPECT_RATIO)
        if self._max_height is not None:
            target_height = min(target_height, self._max_height)
        target_height = max(target_height, 1)
        if self.height() != target_height:
            self.setFixedHeight(target_height)

    def _apply_scaled_pixmap(self) -> None:
        if self._source_pixmap is None or self._source_pixmap.isNull():
            self.setPixmap(QPixmap())
            return
        if self.width() <= 0 or self.height() <= 0:
            # No real geometry yet (widget not laid out/shown); the next
            # resizeEvent once it is will trigger a proper scale.
            return
        scaled = self._source_pixmap.scaled(
            self.width(),
            self.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        if self._dimmed:
            scaled = self._dim_pixmap(scaled)
        self.setPixmap(scaled)

    @classmethod
    def _dim_pixmap(cls, pixmap: QPixmap) -> QPixmap:
        """Desaturate a pixmap and fade it, baked directly into its pixels."""
        grayscale = pixmap.toImage().convertToFormat(QImage.Format.Format_Grayscale8)
        grayscale = grayscale.convertToFormat(QImage.Format.Format_ARGB32)
        result = QPixmap(pixmap.size())
        result.fill(Qt.GlobalColor.transparent)
        painter = QPainter(result)
        painter.setOpacity(cls._DIMMED_OPACITY)
        painter.drawImage(0, 0, grayscale)
        painter.end()
        return result


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

        preview_separator = QFrame()
        preview_separator.setFrameShape(QFrame.Shape.HLine)
        preview_separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addSpacing(6)
        layout.addWidget(preview_separator)
        layout.addSpacing(6)

        self._preview_image_label = _LandscapePreviewLabel()
        self._preview_image_label.setObjectName("streamPreviewImage")
        layout.addWidget(self._preview_image_label)

        layout.addStretch()
        self.setLayout(layout)
        self._update_preview_max_height()

    def _open_clips_folder(self) -> None:
        clips_path = Path(CLIPS_DIR).resolve()
        clips_path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(clips_path)))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_preview_max_height()

    def _update_preview_max_height(self) -> None:
        """Cap the preview image's height to whatever vertical room is left.

        _LandscapePreviewLabel derives its height purely from its own width
        (16:9), which has no awareness of how tall this panel actually is.
        On a wide-but-not-proportionally-tall window that can demand more
        height than the panel has, overflowing this group box instead of
        just shrinking the preview. Cap it to the space left over after
        every other row in this layout, computed fresh each resize rather
        than a fixed pixel value.
        """
        layout = self.layout()
        if layout is None:
            return
        other_height = 0
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item.widget() is self._preview_image_label:
                continue
            other_height += item.sizeHint().height()
        if layout.count() > 1:
            other_height += layout.spacing() * (layout.count() - 1)
        available = self.contentsRect().height() - other_height
        self._preview_image_label.set_max_height(available)

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
            self.clear_preview()

    def show_preview_loading(self) -> None:
        """Show a loading placeholder while a preview fetch is in flight."""
        self._preview_image_label.set_source_pixmap(None)
        self._preview_image_label.setText("Loading preview...")
        self._preview_image_label.set_title("")

    def set_preview_image(self, image_bytes: bytes) -> None:
        """Display a fetched thumbnail, scaled to fill the preview area's width."""
        pixmap = QPixmap()
        if pixmap.loadFromData(image_bytes):
            self._preview_image_label.setText("")
            self._preview_image_label.set_source_pixmap(pixmap)
        else:
            self.set_preview_image_unavailable()

    def set_preview_title(self, title: str) -> None:
        """Display the live stream's title."""
        self._preview_image_label.set_title(title or "")

    def set_preview_offline(self) -> None:
        """Show an offline placeholder and clear the title."""
        self._preview_image_label.set_source_pixmap(None)
        self._preview_image_label.setText("Offline")
        self._preview_image_label.set_title("")

    def set_preview_image_unavailable(self) -> None:
        """Show a fallback when the channel is live but its thumbnail failed to load."""
        self._preview_image_label.set_source_pixmap(None)
        self._preview_image_label.setText("Preview unavailable")

    def clear_preview(self) -> None:
        """Reset the preview area to its empty state."""
        self._preview_image_label.set_source_pixmap(None)
        self._preview_image_label.setText("")
        self._preview_image_label.set_title("")

    def set_preview_dimmed(self, dimmed: bool) -> None:
        """Fade and desaturate the preview, e.g. while its stream is playing."""
        self._preview_image_label.set_dimmed(dimmed)

    def set_streaming(self, active: bool) -> None:
        """Enable/disable the clip button and dim the preview based on stream state.

        Args:
            active: Whether a stream is currently running.
        """
        self._clip_button.setEnabled(active)
        self.set_preview_dimmed(active)

    @property
    def channel(self) -> str:
        """Currently tracked channel name."""
        return self._channel
