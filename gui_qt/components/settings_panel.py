"""
Settings panel component for TwitchAdAvoider Qt GUI.

This module provides the settings controls interface with improved
layout and spacing using PySide6.

The SettingsPanel handles:
    - Player selection dropdown
    - Dark mode toggle
    - Clean horizontal layout with proper spacing

Key Features:
    - Compact horizontal layout
    - Signal-based communication
    - Modern Qt styling
"""

from PySide6.QtWidgets import QGroupBox, QLabel, QComboBox, QCheckBox, QHBoxLayout
from PySide6.QtCore import Signal
from typing import List

from src.logging_config import get_logger

logger = get_logger(__name__)


class SettingsPanel(QGroupBox):
    """
    Manages application settings controls.

    This component provides a clean interface for application settings
    with a horizontal layout for compact presentation.

    Signals:
        player_changed(str): Emitted when player selection changes
        dark_mode_changed(bool): Emitted when dark mode checkbox changes
    """

    # Signals
    player_changed = Signal(str)  # player name
    dark_mode_changed = Signal(bool)  # dark mode enabled

    def __init__(self, parent=None):
        """
        Initialize the SettingsPanel.

        Args:
            parent: Parent widget
        """
        super().__init__("Settings", parent)

        # Available players
        self.player_options = ["vlc", "mpv", "mpc-hc", "auto"]

        # Create UI components
        self._create_ui()

        # Connect signals
        self._connect_signals()

    def _create_ui(self) -> None:
        """Create the UI components with horizontal layout."""
        # Horizontal layout for settings
        layout = QHBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(15, 20, 15, 15)

        # Player selection
        player_label = QLabel("Player:")
        self.player_combo = QComboBox()
        self.player_combo.addItems(self.player_options)
        self.player_combo.setMinimumWidth(120)

        layout.addWidget(player_label)
        layout.addWidget(self.player_combo)

        # Spacer
        layout.addSpacing(30)

        # Dark mode checkbox
        self.dark_mode_checkbox = QCheckBox("Dark Mode")

        layout.addWidget(self.dark_mode_checkbox)

        # Stretch to push everything to the left
        layout.addStretch()

        self.setLayout(layout)

    def _connect_signals(self) -> None:
        """Connect internal signals."""
        # Player selection changed
        self.player_combo.currentTextChanged.connect(self._on_player_changed)

        # Dark mode checkbox changed
        self.dark_mode_checkbox.stateChanged.connect(self._on_dark_mode_changed)

    def _on_player_changed(self, player: str) -> None:
        """
        Handle player selection change.

        Args:
            player: Selected player name
        """
        logger.info(f"Player changed to: {player}")
        self.player_changed.emit(player)

    def _on_dark_mode_changed(self, state: int) -> None:
        """
        Handle dark mode checkbox change.

        Args:
            state: Checkbox state (Qt.Checked or Qt.Unchecked)
        """
        from PySide6.QtCore import Qt

        is_checked = state == Qt.CheckState.Checked
        logger.info(f"Dark mode changed to: {is_checked}")
        self.dark_mode_changed.emit(is_checked)

    def get_player(self) -> str:
        """
        Get the selected player.

        Returns:
            Selected player name
        """
        return self.player_combo.currentText()

    def set_player(self, player: str) -> None:
        """
        Set the player selection.

        Args:
            player: Player name to select
        """
        if player in self.player_options:
            self.player_combo.setCurrentText(player)
        else:
            logger.warning(f"Invalid player value: {player}, defaulting to 'vlc'")
            self.player_combo.setCurrentText("vlc")

    def get_dark_mode(self) -> bool:
        """
        Get the dark mode checkbox state.

        Returns:
            True if dark mode is enabled, False otherwise
        """
        from PySide6.QtCore import Qt

        return self.dark_mode_checkbox.checkState() == Qt.CheckState.Checked

    def set_dark_mode(self, enabled: bool) -> None:
        """
        Set the dark mode checkbox state.

        Args:
            enabled: True to enable dark mode, False to disable
        """
        from PySide6.QtCore import Qt

        self.dark_mode_checkbox.setCheckState(
            Qt.CheckState.Checked if enabled else Qt.CheckState.Unchecked
        )

    def add_player_option(self, player: str) -> None:
        """
        Add a new player option to the dropdown.

        Args:
            player: Player name to add
        """
        if player not in self.player_options:
            self.player_options.append(player)
            self.player_combo.addItem(player)
            logger.info(f"Added player option: {player}")

    def set_player_options(self, players: List[str]) -> None:
        """
        Set the available player options.

        Args:
            players: List of player names
        """
        self.player_options = players
        current_player = self.player_combo.currentText()

        self.player_combo.clear()
        self.player_combo.addItems(players)

        # Restore selection if still available
        if current_player in players:
            self.player_combo.setCurrentText(current_player)
        else:
            self.player_combo.setCurrentIndex(0)

        logger.info(f"Updated player options: {players}")
