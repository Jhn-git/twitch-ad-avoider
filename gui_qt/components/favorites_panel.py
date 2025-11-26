"""
Favorites panel component for TwitchAdAvoider Qt GUI.

This module provides the favorites management interface with improved
layout, spacing, and custom-painted status indicators.

The FavoritesPanel handles:
    - Display of favorite channels with status indicators
    - Add/remove favorites functionality
    - Status refresh with visual feedback
    - Channel selection and interaction

Key Features:
    - Custom QStyledItemDelegate for status circles
    - Clean list-based interface
    - Signal-based communication
    - Smooth hover effects
"""

from PySide6.QtWidgets import (
    QGroupBox, QListWidget, QListWidgetItem, QPushButton,
    QVBoxLayout, QHBoxLayout, QStyledItemDelegate, QStyle,
    QStyleOptionViewItem, QWidget, QInputDialog, QMessageBox
)
from PySide6.QtCore import Signal, Qt, QRect, QSize
from PySide6.QtGui import QPainter, QColor, QPen, QBrush
from typing import List, Optional, Dict

from src.logging_config import get_logger

logger = get_logger(__name__)


class FavoriteItemDelegate(QStyledItemDelegate):
    """
    Custom delegate for drawing favorite items with status circles.

    This delegate paints a colored circle before the channel name to
    indicate live/offline status.
    """

    # Status circle colors
    LIVE_FILL = QColor("#E74C3C")      # Red fill for live
    LIVE_OUTLINE = QColor("#C0392B")   # Darker red outline
    OFFLINE_FILL = QColor("#95A5A6")   # Gray fill for offline
    OFFLINE_OUTLINE = QColor("#7F8C8D")  # Darker gray outline

    # Dark theme colors (brighter)
    LIVE_FILL_DARK = QColor("#FF4C4C")
    LIVE_OUTLINE_DARK = QColor("#FF6B6B")
    OFFLINE_FILL_DARK = QColor("#A0A0A0")
    OFFLINE_OUTLINE_DARK = QColor("#BEBEBE")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.dark_mode = False

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        """
        Paint the item with status circle.

        Args:
            painter: QPainter for drawing
            option: Style options for the item
            index: Model index of the item
        """
        # Draw background and selection
        super().paint(painter, option, index)

        # Get status from item data
        is_live = index.data(Qt.UserRole) or False

        # Select colors based on theme and status
        if is_live:
            fill_color = self.LIVE_FILL_DARK if self.dark_mode else self.LIVE_FILL
            outline_color = self.LIVE_OUTLINE_DARK if self.dark_mode else self.LIVE_OUTLINE
        else:
            fill_color = self.OFFLINE_FILL_DARK if self.dark_mode else self.OFFLINE_FILL
            outline_color = self.OFFLINE_OUTLINE_DARK if self.dark_mode else self.OFFLINE_OUTLINE

        # Calculate circle position
        circle_radius = 5
        circle_margin = 10
        circle_x = option.rect.left() + circle_margin
        circle_y = option.rect.center().y()

        # Draw circle
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        # Fill
        painter.setBrush(QBrush(fill_color))
        painter.setPen(QPen(outline_color, 1))
        painter.drawEllipse(
            circle_x - circle_radius,
            circle_y - circle_radius,
            circle_radius * 2,
            circle_radius * 2
        )

        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        """
        Return size hint for items.

        Args:
            option: Style options
            index: Model index

        Returns:
            Recommended size for item
        """
        size = super().sizeHint(option, index)
        # Add some extra height for better spacing
        size.setHeight(max(size.height(), 28))
        return size

    def set_dark_mode(self, enabled: bool) -> None:
        """
        Set dark mode for color adaptation.

        Args:
            enabled: True for dark mode, False for light mode
        """
        self.dark_mode = enabled


class FavoritesPanel(QGroupBox):
    """
    Manages favorite channels with status display.

    This component provides a clean interface for managing favorite
    channels with visual status indicators and action buttons.

    Signals:
        favorite_selected(str): Emitted when a favorite is single-clicked
        favorite_double_clicked(str): Emitted when a favorite is double-clicked
        add_current_requested(): Emitted when "Add Current" is clicked
        add_new_requested(): Emitted when "Add New" is clicked
        remove_requested(str): Emitted when "Remove" is clicked with selection
        refresh_requested(): Emitted when "Refresh" is clicked
    """

    # Signals
    favorite_selected = Signal(str)  # channel name
    favorite_double_clicked = Signal(str)  # channel name
    add_current_requested = Signal()
    add_new_requested = Signal()
    remove_requested = Signal(str)  # channel name
    refresh_requested = Signal()

    def __init__(self, parent=None):
        """
        Initialize the FavoritesPanel.

        Args:
            parent: Parent widget
        """
        super().__init__("Favorites", parent)

        # Data storage
        self.favorites_data: Dict[str, bool] = {}  # channel -> is_live

        # Custom delegate for status circles
        self.delegate = FavoriteItemDelegate()

        # Create UI components
        self._create_ui()

        # Connect signals
        self._connect_signals()

    def _create_ui(self) -> None:
        """Create the UI components."""
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 15, 10, 10)

        # List widget
        self.list_widget = QListWidget()
        self.list_widget.setItemDelegate(self.delegate)
        self.list_widget.setMinimumHeight(150)
        self.list_widget.setSpacing(2)

        # Indent text to make room for status circle
        self.list_widget.setStyleSheet("""
            QListWidget::item {
                padding-left: 25px;
            }
        """)

        layout.addWidget(self.list_widget)

        # Button layout
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)

        self.add_current_btn = QPushButton("Add Current")
        self.add_new_btn = QPushButton("Add New")
        self.remove_btn = QPushButton("Remove")
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setObjectName("refreshButton")

        # Disable remove button initially
        self.remove_btn.setEnabled(False)

        button_layout.addWidget(self.add_current_btn)
        button_layout.addWidget(self.add_new_btn)
        button_layout.addWidget(self.remove_btn)
        button_layout.addWidget(self.refresh_btn)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def _connect_signals(self) -> None:
        """Connect internal signals."""
        # List selection changed
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)

        # List item clicked
        self.list_widget.itemClicked.connect(self._on_item_clicked)

        # List item double-clicked
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)

        # Buttons
        self.add_current_btn.clicked.connect(self._on_add_current_clicked)
        self.add_new_btn.clicked.connect(self._on_add_new_clicked)
        self.remove_btn.clicked.connect(self._on_remove_clicked)
        self.refresh_btn.clicked.connect(self._on_refresh_clicked)

    def _on_selection_changed(self) -> None:
        """Handle list selection change."""
        selected_items = self.list_widget.selectedItems()
        self.remove_btn.setEnabled(len(selected_items) > 0)

        if selected_items:
            channel = selected_items[0].text()
            self.favorite_selected.emit(channel)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        """
        Handle item click.

        Args:
            item: Clicked list item
        """
        channel = item.text()
        logger.debug(f"Favorite clicked: {channel}")

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        """
        Handle item double-click.

        Args:
            item: Double-clicked list item
        """
        channel = item.text()
        logger.info(f"Favorite double-clicked: {channel}")
        self.favorite_double_clicked.emit(channel)

    def _on_add_current_clicked(self) -> None:
        """Handle Add Current button click."""
        logger.info("Add Current clicked")
        self.add_current_requested.emit()

    def _on_add_new_clicked(self) -> None:
        """Handle Add New button click."""
        logger.info("Add New clicked")
        self.add_new_requested.emit()

    def _on_remove_clicked(self) -> None:
        """Handle Remove button click."""
        selected_items = self.list_widget.selectedItems()
        if selected_items:
            channel = selected_items[0].text()
            logger.info(f"Remove clicked for: {channel}")
            self.remove_requested.emit(channel)

    def _on_refresh_clicked(self) -> None:
        """Handle Refresh button click."""
        logger.info("Refresh clicked")
        self.refresh_requested.emit()

    def add_favorite(self, channel: str, is_live: bool = False) -> None:
        """
        Add a favorite channel to the list.

        Args:
            channel: Channel name
            is_live: Whether the channel is currently live
        """
        # Check if already exists
        existing_items = self.list_widget.findItems(channel, Qt.MatchExactly)
        if existing_items:
            # Update status
            existing_items[0].setData(Qt.UserRole, is_live)
            self.list_widget.update()
            logger.debug(f"Updated favorite status: {channel} (live={is_live})")
        else:
            # Add new item
            item = QListWidgetItem(channel)
            item.setData(Qt.UserRole, is_live)
            self.list_widget.addItem(item)
            logger.info(f"Added favorite: {channel}")

        # Update data storage
        self.favorites_data[channel] = is_live

    def remove_favorite(self, channel: str) -> None:
        """
        Remove a favorite channel from the list.

        Args:
            channel: Channel name to remove
        """
        items = self.list_widget.findItems(channel, Qt.MatchExactly)
        for item in items:
            row = self.list_widget.row(item)
            self.list_widget.takeItem(row)
            logger.info(f"Removed favorite: {channel}")

        # Update data storage
        if channel in self.favorites_data:
            del self.favorites_data[channel]

    def update_favorite_status(self, channel: str, is_live: bool) -> None:
        """
        Update the live status of a favorite.

        Args:
            channel: Channel name
            is_live: Whether the channel is live
        """
        items = self.list_widget.findItems(channel, Qt.MatchExactly)
        if items:
            items[0].setData(Qt.UserRole, is_live)
            self.list_widget.update()
            self.favorites_data[channel] = is_live
            logger.debug(f"Updated {channel} status: live={is_live}")

    def get_favorites(self) -> List[str]:
        """
        Get list of all favorite channels.

        Returns:
            List of channel names
        """
        return [
            self.list_widget.item(i).text()
            for i in range(self.list_widget.count())
        ]

    def get_selected_favorite(self) -> Optional[str]:
        """
        Get the currently selected favorite.

        Returns:
            Selected channel name or None
        """
        selected_items = self.list_widget.selectedItems()
        if selected_items:
            return selected_items[0].text()
        return None

    def clear_favorites(self) -> None:
        """Clear all favorites from the list."""
        self.list_widget.clear()
        self.favorites_data.clear()
        logger.info("Cleared all favorites")

    def set_favorites(self, favorites: Dict[str, bool]) -> None:
        """
        Set the favorites list.

        Args:
            favorites: Dictionary mapping channel names to live status
        """
        self.clear_favorites()
        for channel, is_live in favorites.items():
            self.add_favorite(channel, is_live)

    def set_dark_mode(self, enabled: bool) -> None:
        """
        Set dark mode for the delegate.

        Args:
            enabled: True for dark mode, False for light mode
        """
        self.delegate.set_dark_mode(enabled)
        self.list_widget.update()

    def set_refreshing(self, is_refreshing: bool) -> None:
        """
        Set the refreshing state (enables/disables refresh button).

        Args:
            is_refreshing: True if currently refreshing
        """
        self.refresh_btn.setEnabled(not is_refreshing)
        if is_refreshing:
            self.refresh_btn.setText("Refreshing...")
        else:
            self.refresh_btn.setText("Refresh")
