"""
Favorites panel component for TwitchAdAvoider Qt GUI.

The FavoritesPanel handles:
    - Display of favorite channels with live-status circles and pin stars
    - Add/remove favorites with right-click context menu
    - Manual refresh button and quality selector
    - Double-click to stream, Ctrl+double-click to open in browser
    - Pin/unpin channels to prioritize them within live/offline groups
"""

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
from PySide6.QtCore import Signal, Qt, QSize, QPoint
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont
from typing import List, Optional, Dict

from src.logging_config import get_logger

logger = get_logger(__name__)

QUALITY_OPTIONS = ["best", "720p", "480p", "360p", "worst"]

# Qt item data roles
_LIVE_ROLE = Qt.UserRole
_PIN_ROLE = Qt.UserRole + 1


class FavoriteItemDelegate(QStyledItemDelegate):
    """Custom delegate that draws a live-status circle and optional pin star."""

    LIVE_FILL = QColor("#E74C3C")
    LIVE_OUTLINE = QColor("#C0392B")
    OFFLINE_FILL = QColor("#95A5A6")
    OFFLINE_OUTLINE = QColor("#7F8C8D")
    LIVE_FILL_DARK = QColor("#FF4C4C")
    LIVE_OUTLINE_DARK = QColor("#FF6B6B")
    OFFLINE_FILL_DARK = QColor("#A0A0A0")
    OFFLINE_OUTLINE_DARK = QColor("#BEBEBE")
    STAR_COLOR = QColor("#FFD700")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.dark_mode = False

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        super().paint(painter, option, index)

        is_live = index.data(_LIVE_ROLE) or False
        is_pinned = index.data(_PIN_ROLE) or False

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

        # Pin star (right margin) — drawn as text for sharpness
        if is_pinned:
            font = QFont()
            font.setPixelSize(13)
            painter.setFont(font)
            painter.setPen(QPen(self.STAR_COLOR))
            star_rect = option.rect.adjusted(0, 0, -6, 0)
            painter.drawText(star_rect, Qt.AlignRight | Qt.AlignVCenter, "★")

        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        size = super().sizeHint(option, index)
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
            if item:
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

        self.delegate = FavoriteItemDelegate()
        self._create_ui()
        self._connect_signals()

    def _create_ui(self) -> None:
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 15, 10, 10)

        self.list_widget = FavoritesListWidget()
        self.list_widget.setItemDelegate(self.delegate)
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
        self.remove_btn.setEnabled(bool(selected))
        if selected:
            self.favorite_selected.emit(selected[0].text())

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        logger.debug(f"Favorite clicked: {item.text()}")

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        logger.info(f"Favorite double-clicked: {item.text()}")
        self.favorite_double_clicked.emit(item.text())

    def _on_remove_clicked(self) -> None:
        selected = self.list_widget.selectedItems()
        if selected:
            self.remove_requested.emit(selected[0].text())

    def _on_context_menu(self, pos: QPoint) -> None:
        item = self.list_widget.itemAt(pos)
        if not item:
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

    def _sort_favorites(self) -> None:
        """Re-order list: live channels first, pinned within each group, then alpha."""
        items_data = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            items_data.append((
                item.text(),
                item.data(_LIVE_ROLE) or False,
                item.data(_PIN_ROLE) or False,
            ))

        items_data.sort(key=lambda x: (not x[1], not x[2], x[0].lower()))

        self.list_widget.clear()
        for channel, is_live, is_pinned in items_data:
            new_item = QListWidgetItem(channel)
            new_item.setData(_LIVE_ROLE, is_live)
            new_item.setData(_PIN_ROLE, is_pinned)
            self.list_widget.addItem(new_item)

    def add_favorite(self, channel: str, is_live: bool = False, is_pinned: bool = False) -> None:
        existing = self.list_widget.findItems(channel, Qt.MatchExactly)
        if existing:
            existing[0].setData(_LIVE_ROLE, is_live)
            existing[0].setData(_PIN_ROLE, is_pinned)
            self.list_widget.viewport().update()
        else:
            item = QListWidgetItem(channel)
            item.setData(_LIVE_ROLE, is_live)
            item.setData(_PIN_ROLE, is_pinned)
            self.list_widget.addItem(item)
            logger.info(f"Added favorite: {channel}")

        self.favorites_data[channel] = {"is_live": is_live, "is_pinned": is_pinned}
        self._sort_favorites()

    def remove_favorite(self, channel: str) -> None:
        for item in self.list_widget.findItems(channel, Qt.MatchExactly):
            self.list_widget.takeItem(self.list_widget.row(item))
            logger.info(f"Removed favorite: {channel}")
        self.favorites_data.pop(channel, None)

    def update_favorite_status(self, channel: str, is_live: bool) -> None:
        items = self.list_widget.findItems(channel, Qt.MatchExactly)
        if items:
            items[0].setData(_LIVE_ROLE, is_live)
            if channel in self.favorites_data:
                self.favorites_data[channel]["is_live"] = is_live
            self._sort_favorites()
            self.list_widget.viewport().update()
            logger.debug(f"Updated {channel} status: live={is_live}")

    def update_pin_status(self, channel: str, is_pinned: bool) -> None:
        items = self.list_widget.findItems(channel, Qt.MatchExactly)
        if items:
            items[0].setData(_PIN_ROLE, is_pinned)
            if channel in self.favorites_data:
                self.favorites_data[channel]["is_pinned"] = is_pinned
            self._sort_favorites()
            self.list_widget.viewport().update()
            logger.debug(f"Updated {channel} pin: {is_pinned}")

    def get_favorites(self) -> List[str]:
        return [self.list_widget.item(i).text() for i in range(self.list_widget.count())]

    def get_selected_favorite(self) -> Optional[str]:
        selected = self.list_widget.selectedItems()
        return selected[0].text() if selected else None

    def get_quality(self) -> str:
        return self.quality_combo.currentText()

    def set_quality(self, quality: str) -> None:
        if quality in QUALITY_OPTIONS:
            self.quality_combo.setCurrentText(quality)

    def clear_favorites(self) -> None:
        self.list_widget.clear()
        self.favorites_data.clear()

    def set_dark_mode(self, enabled: bool) -> None:
        self.delegate.set_dark_mode(enabled)
        self.list_widget.viewport().update()
