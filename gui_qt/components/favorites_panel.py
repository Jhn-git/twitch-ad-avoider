"""
Favorites panel component for TwitchAdAvoider Qt GUI.

The FavoritesPanel handles:
    - Display of favorite channels with live-status circles and pinned section headers
    - Add/remove favorites with right-click context menu
    - Manual refresh button and quality selector
    - Double-click to stream, Ctrl+double-click to open in browser
    - Pin/unpin channels to prioritize them within live/offline groups
"""

import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QGroupBox,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QComboBox,
    QLabel,
    QMenu,
)
from PySide6.QtCore import Signal, Qt, QSize, QPoint, QRect, QTimer
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QIcon, QPixmap
from PySide6.QtSvg import QSvgRenderer
from typing import Dict, List, Optional, Set, Tuple

from src.logging_config import get_logger

logger = get_logger(__name__)

QUALITY_OPTIONS = ["best", "720p", "480p", "360p", "worst"]
RECENT_LIVE_DURATION_MS = 120_000
PIN_ICON_SIZE = QSize(14, 14)

# Qt item data roles
_LIVE_ROLE = Qt.UserRole
_PIN_ROLE = Qt.UserRole + 1
_RECENT_LIVE_ROLE = Qt.UserRole + 2
_ITEM_KIND_ROLE = Qt.UserRole + 3

_ITEM_KIND_FAVORITE = "favorite"
_ITEM_KIND_HEADER = "header"


def _assets_dir() -> Path:
    """Return the assets directory for source and frozen app runs."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "assets"
    return Path(__file__).resolve().parents[2] / "assets"


class FavoriteItemDelegate(QStyledItemDelegate):
    """Custom delegate that draws a live-status circle and recent-live highlight."""

    LIVE_FILL = QColor("#E74C3C")
    LIVE_OUTLINE = QColor("#C0392B")
    OFFLINE_FILL = QColor("#95A5A6")
    OFFLINE_OUTLINE = QColor("#7F8C8D")
    LIVE_FILL_DARK = QColor("#FF4C4C")
    LIVE_OUTLINE_DARK = QColor("#FF6B6B")
    OFFLINE_FILL_DARK = QColor("#A0A0A0")
    OFFLINE_OUTLINE_DARK = QColor("#BEBEBE")
    RECENT_LIVE_TINT = QColor(46, 204, 113, 24)
    RECENT_LIVE_TINT_DARK = QColor(46, 204, 113, 32)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.dark_mode = False

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        if index.data(_ITEM_KIND_ROLE) == _ITEM_KIND_HEADER:
            painter.save()

            font = QFont(option.font)
            font.setBold(True)
            font.setPixelSize(11)
            painter.setFont(font)
            painter.setPen(QPen(QColor("#AFAFAF")))

            content_left = option.rect.left() + 2
            icon = index.data(Qt.DecorationRole)
            if isinstance(icon, QIcon) and not icon.isNull():
                icon_rect = QRect(
                    content_left,
                    option.rect.center().y() - (PIN_ICON_SIZE.height() // 2),
                    PIN_ICON_SIZE.width(),
                    PIN_ICON_SIZE.height(),
                )
                icon.paint(painter, icon_rect, Qt.AlignCenter)
                content_left = icon_rect.right() + 6

            text_rect = option.rect.adjusted(content_left - option.rect.left(), 0, -4, 0)
            painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, index.data(Qt.DisplayRole))
            painter.restore()
            return

        is_live = index.data(_LIVE_ROLE) or False
        is_recent_live = bool(index.data(_RECENT_LIVE_ROLE)) and is_live

        if is_recent_live:
            painter.save()
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(Qt.NoPen)
            painter.setBrush(self.RECENT_LIVE_TINT_DARK if self.dark_mode else self.RECENT_LIVE_TINT)
            highlight_rect = option.rect.adjusted(2, 2, -2, -2)
            painter.drawRoundedRect(highlight_rect, 5, 5)
            painter.restore()

        super().paint(painter, option, index)

        if is_live:
            fill = self.LIVE_FILL_DARK if self.dark_mode else self.LIVE_FILL
            outline = self.LIVE_OUTLINE_DARK if self.dark_mode else self.LIVE_OUTLINE
        else:
            fill = self.OFFLINE_FILL_DARK if self.dark_mode else self.OFFLINE_FILL
            outline = self.OFFLINE_OUTLINE_DARK if self.dark_mode else self.OFFLINE_OUTLINE

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        # Status circle (left margin)
        r = 5
        cx = option.rect.left() + 10
        cy = option.rect.center().y()
        painter.setBrush(QBrush(fill))
        painter.setPen(QPen(outline, 1))
        painter.drawEllipse(cx - r, cy - r, r * 2, r * 2)

        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        size = super().sizeHint(option, index)
        if index.data(_ITEM_KIND_ROLE) == _ITEM_KIND_HEADER:
            size.setHeight(max(size.height(), 24))
            return size
        size.setHeight(max(size.height(), 28))
        return size

    def set_dark_mode(self, enabled: bool) -> None:
        self.dark_mode = enabled


class FavoritesListWidget(QListWidget):
    """QListWidget that separates Ctrl+double-click from plain double-click."""

    ctrl_double_clicked = Signal(str)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.modifiers() & Qt.ControlModifier:
            item = self.itemAt(event.pos())
            if item and item.data(_ITEM_KIND_ROLE) == _ITEM_KIND_FAVORITE:
                self.ctrl_double_clicked.emit(item.text())
            return
        super().mouseDoubleClickEvent(event)


class FavoritesPanel(QGroupBox):
    """
    Manages favorite channels with status display.

    Signals:
        favorite_selected(str): Single-click on a channel
        favorite_double_clicked(str): Double-click — start streaming
        open_channel_in_browser(str): Ctrl+double-click — open Twitch page
        add_new_requested(): "Add" button clicked
        remove_requested(str): "Remove" via button or context menu
        refresh_requested(): "Refresh" button clicked
        pin_toggle_requested(str): Pin/Unpin chosen from context menu
        quality_changed(str): Quality dropdown changed
    """

    favorite_selected = Signal(str)
    favorite_double_clicked = Signal(str)
    open_channel_in_browser = Signal(str)
    add_new_requested = Signal()
    remove_requested = Signal(str)
    refresh_requested = Signal()
    pin_toggle_requested = Signal(str)
    quality_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__("Favorites", parent)

        # channel -> {is_live, is_pinned}
        self.favorites_data: Dict[str, Dict] = {}
        self._recent_live_channels: Set[str] = set()
        self._recent_live_timers: Dict[str, QTimer] = {}
        self._pin_header_icon = self._load_pin_header_icon()

        self.delegate = FavoriteItemDelegate()
        self._create_ui()
        self._connect_signals()

    def _create_ui(self) -> None:
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 15, 10, 10)

        self.list_widget = FavoritesListWidget()
        self.list_widget.setItemDelegate(self.delegate)
        self.list_widget.setIconSize(PIN_ICON_SIZE)
        self.list_widget.setMinimumHeight(150)
        self.list_widget.setSpacing(2)
        self.list_widget.setStyleSheet("""
            QListWidget::item {
                padding-left: 25px;
                padding-right: 22px;
            }
        """)
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        layout.addWidget(self.list_widget)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)

        self.add_new_btn = QPushButton("Add")
        self.remove_btn = QPushButton("Remove")
        self.refresh_btn = QPushButton("Refresh")
        self.remove_btn.setEnabled(False)

        button_layout.addWidget(self.add_new_btn)
        button_layout.addWidget(self.remove_btn)
        button_layout.addWidget(self.refresh_btn)
        button_layout.addStretch()

        quality_label = QLabel("Quality:")
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(QUALITY_OPTIONS)
        self.quality_combo.setCurrentText("best")
        self.quality_combo.setMinimumWidth(80)

        button_layout.addWidget(quality_label)
        button_layout.addWidget(self.quality_combo)

        layout.addLayout(button_layout)
        self.setLayout(layout)

    def _connect_signals(self) -> None:
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.list_widget.ctrl_double_clicked.connect(self.open_channel_in_browser)
        self.list_widget.customContextMenuRequested.connect(self._on_context_menu)

        self.add_new_btn.clicked.connect(self.add_new_requested)
        self.remove_btn.clicked.connect(self._on_remove_clicked)
        self.refresh_btn.clicked.connect(self.refresh_requested)
        self.quality_combo.currentTextChanged.connect(self.quality_changed)

    def _on_selection_changed(self) -> None:
        selected = self.list_widget.selectedItems()
        is_favorite_selected = bool(selected) and (
            selected[0].data(_ITEM_KIND_ROLE) == _ITEM_KIND_FAVORITE
        )
        self.remove_btn.setEnabled(is_favorite_selected)
        if is_favorite_selected:
            self.favorite_selected.emit(selected[0].text())

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        if item.data(_ITEM_KIND_ROLE) != _ITEM_KIND_FAVORITE:
            return
        logger.debug(f"Favorite clicked: {item.text()}")

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        if item.data(_ITEM_KIND_ROLE) != _ITEM_KIND_FAVORITE:
            return
        logger.info(f"Favorite double-clicked: {item.text()}")
        self.favorite_double_clicked.emit(item.text())

    def _on_remove_clicked(self) -> None:
        selected = self.list_widget.selectedItems()
        if selected and selected[0].data(_ITEM_KIND_ROLE) == _ITEM_KIND_FAVORITE:
            self.remove_requested.emit(selected[0].text())

    def _on_context_menu(self, pos: QPoint) -> None:
        item = self.list_widget.itemAt(pos)
        if not item or item.data(_ITEM_KIND_ROLE) != _ITEM_KIND_FAVORITE:
            return
        channel = item.text()
        is_pinned = self.favorites_data.get(channel, {}).get("is_pinned", False)

        menu = QMenu(self.list_widget)
        pin_action = menu.addAction("Unpin" if is_pinned else "Pin to top")
        menu.addSeparator()
        remove_action = menu.addAction("Remove")

        action = menu.exec(self.list_widget.viewport().mapToGlobal(pos))
        if action == pin_action:
            self.pin_toggle_requested.emit(channel)
        elif action == remove_action:
            self.remove_requested.emit(channel)

    def _load_pin_header_icon(self) -> QIcon:
        """Load the pinned-section icon from the repo assets."""
        pin_path = _assets_dir() / "pin.svg"
        if not pin_path.exists():
            logger.warning(f"Pinned-section icon not found: {pin_path}")
            return QIcon()

        renderer = QSvgRenderer(str(pin_path))
        if not renderer.isValid():
            logger.warning(f"Pinned-section icon could not be rendered: {pin_path}")
            return QIcon()

        pixmap = QPixmap(PIN_ICON_SIZE)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        return QIcon(pixmap)

    def _create_header_item(self, label: str, icon: Optional[QIcon] = None) -> QListWidgetItem:
        """Create a non-interactive section header row."""
        item = QListWidgetItem(label)
        item.setData(_ITEM_KIND_ROLE, _ITEM_KIND_HEADER)
        item.setData(_LIVE_ROLE, False)
        item.setData(_PIN_ROLE, False)
        item.setData(_RECENT_LIVE_ROLE, False)
        item.setFlags(Qt.ItemIsEnabled)
        if icon and not icon.isNull():
            item.setIcon(icon)

        font = QFont()
        font.setBold(True)
        font.setPixelSize(11)
        item.setFont(font)
        item.setForeground(QColor("#AFAFAF"))
        item.setSizeHint(QSize(0, 24))
        return item

    def _create_favorite_item(
        self,
        channel: str,
        is_live: bool,
        is_pinned: bool,
        is_recent_live: bool,
    ) -> QListWidgetItem:
        """Create a normal favorite row item."""
        item = QListWidgetItem(channel)
        item.setData(_ITEM_KIND_ROLE, _ITEM_KIND_FAVORITE)
        item.setData(_LIVE_ROLE, is_live)
        item.setData(_PIN_ROLE, is_pinned)
        item.setData(_RECENT_LIVE_ROLE, is_recent_live and is_live)
        return item

    def _get_sorted_favorites(self) -> Tuple[List[Tuple[str, bool, bool]], List[Tuple[str, bool, bool]]]:
        """Return pinned and unpinned favorites in their display order."""
        favorites = [
            (channel, info.get("is_live", False), info.get("is_pinned", False))
            for channel, info in self.favorites_data.items()
        ]
        sort_key = lambda row: (not row[1], row[0].lower())
        pinned = sorted((row for row in favorites if row[2]), key=sort_key)
        unpinned = sorted((row for row in favorites if not row[2]), key=sort_key)
        return pinned, unpinned

    def _sort_favorites(self) -> None:
        """Rebuild list grouped by pinned status, with live channels first within each group."""
        selected_channel = self.get_selected_favorite()
        pinned, unpinned = self._get_sorted_favorites()

        self.list_widget.blockSignals(True)
        try:
            self.list_widget.clear()

            if pinned:
                self.list_widget.addItem(self._create_header_item("Pinned", self._pin_header_icon))
                for channel, is_live, is_pinned in pinned:
                    self.list_widget.addItem(
                        self._create_favorite_item(
                            channel,
                            is_live,
                            is_pinned,
                            channel in self._recent_live_channels,
                        )
                    )

            if pinned and unpinned:
                self.list_widget.addItem(self._create_header_item("Others"))

            if unpinned:
                for channel, is_live, is_pinned in unpinned:
                    self.list_widget.addItem(
                        self._create_favorite_item(
                            channel,
                            is_live,
                            is_pinned,
                            channel in self._recent_live_channels,
                        )
                    )
        finally:
            self.list_widget.blockSignals(False)

        if selected_channel:
            items = self.list_widget.findItems(selected_channel, Qt.MatchExactly)
            if items:
                self.list_widget.setCurrentItem(items[0])

        self._on_selection_changed()
        self.list_widget.viewport().update()

    def add_favorite(self, channel: str, is_live: bool = False, is_pinned: bool = False) -> None:
        if not is_live and channel in self._recent_live_channels:
            self._clear_recent_live_state(channel)
        if channel not in self.favorites_data:
            logger.info(f"Added favorite: {channel}")
        self.favorites_data[channel] = {"is_live": is_live, "is_pinned": is_pinned}
        self._sort_favorites()

    def remove_favorite(self, channel: str) -> None:
        if channel not in self.favorites_data:
            return

        self._clear_recent_live_state(channel)
        self.favorites_data.pop(channel, None)
        self._sort_favorites()
        logger.info(f"Removed favorite: {channel}")

    def update_favorite_status(self, channel: str, is_live: bool) -> None:
        if channel not in self.favorites_data:
            return

        self.favorites_data[channel]["is_live"] = is_live
        if not is_live:
            self._clear_recent_live_state(channel)
        self._sort_favorites()
        logger.debug(f"Updated {channel} status: live={is_live}")

    def update_pin_status(self, channel: str, is_pinned: bool) -> None:
        if channel not in self.favorites_data:
            return

        self.favorites_data[channel]["is_pinned"] = is_pinned
        self._sort_favorites()
        logger.debug(f"Updated {channel} pin: {is_pinned}")

    def mark_recently_live(self, channels: List[str]) -> None:
        """Temporarily highlight channels that just came online."""
        if not channels:
            return

        changed = False
        for channel in channels:
            items = self.list_widget.findItems(channel, Qt.MatchExactly)
            if not items or not items[0].data(_LIVE_ROLE):
                continue

            item = items[0]
            item.setData(_RECENT_LIVE_ROLE, True)
            self._recent_live_channels.add(channel)

            timer = self._recent_live_timers.get(channel)
            if timer is None:
                timer = QTimer(self)
                timer.setSingleShot(True)
                timer.timeout.connect(lambda ch=channel: self._expire_recent_live(ch))
                self._recent_live_timers[channel] = timer
            else:
                timer.stop()

            timer.start(RECENT_LIVE_DURATION_MS)
            changed = True

        if changed:
            self.list_widget.viewport().update()

    def _expire_recent_live(self, channel: str) -> None:
        self._clear_recent_live_state(channel)
        self.list_widget.viewport().update()

    def _clear_recent_live_state(self, channel: str) -> None:
        self._recent_live_channels.discard(channel)

        timer = self._recent_live_timers.pop(channel, None)
        if timer:
            timer.stop()
            timer.deleteLater()

        for item in self.list_widget.findItems(channel, Qt.MatchExactly):
            item.setData(_RECENT_LIVE_ROLE, False)

    def get_favorites(self) -> List[str]:
        favorites = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.data(_ITEM_KIND_ROLE) == _ITEM_KIND_FAVORITE:
                favorites.append(item.text())
        return favorites

    def get_selected_favorite(self) -> Optional[str]:
        selected = self.list_widget.selectedItems()
        if not selected or selected[0].data(_ITEM_KIND_ROLE) != _ITEM_KIND_FAVORITE:
            return None
        return selected[0].text()

    def get_quality(self) -> str:
        return self.quality_combo.currentText()

    def set_quality(self, quality: str) -> None:
        if quality in QUALITY_OPTIONS:
            self.quality_combo.setCurrentText(quality)

    def clear_favorites(self) -> None:
        for channel in list(self._recent_live_channels):
            self._clear_recent_live_state(channel)
        self.list_widget.clear()
        self.favorites_data.clear()

    def set_dark_mode(self, enabled: bool) -> None:
        self.delegate.set_dark_mode(enabled)
        self.list_widget.viewport().update()
