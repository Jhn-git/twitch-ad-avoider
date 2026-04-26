"""
Stream control panel component for TwitchAdAvoider Qt GUI.

This module provides the stream input controls interface with improved
layout, spacing, and visual polish using PySide6.

The StreamControlPanel handles:
    - Channel name input with real-time validation
    - Quality selection dropdown
    - Watch button with state management
    - Clean visual feedback
    - Keyboard shortcuts (Enter to watch)

Key Features:
    - Real-time input validation with visual feedback
    - Proper spacing and padding
    - Modern Qt styling
    - Signal-based communication
"""

from PySide6.QtWidgets import (
    QGroupBox,
    QLabel,
    QLineEdit,
    QComboBox,
    QPushButton,
    QFormLayout,
    QHBoxLayout,
    QVBoxLayout,
)
from PySide6.QtCore import Signal

from src.logging_config import get_logger

logger = get_logger(__name__)


class StreamControlPanel(QGroupBox):
    """
    Manages the stream input controls and validation.

    This component provides a clean interface for channel selection
    and stream initiation with improved spacing and organization.

    Signals:
        watch_stream_requested(str, str): Emitted when user wants to watch a stream
            Args: (channel_name, quality)
        channel_changed(str): Emitted when channel input changes
    """

    # Signals
    watch_stream_requested = Signal(str, str)  # channel, quality
    channel_changed = Signal(str)  # channel

    def __init__(self, parent=None):
        """
        Initialize the StreamControlPanel.

        Args:
            parent: Parent widget
        """
        super().__init__("Watch Stream", parent)

        # Quality options
        self.quality_options = ["best", "worst", "720p", "480p", "360p"]

        # Create UI components
        self._create_ui()

        # Connect signals
        self._connect_signals()

        # Initial state
        self._dark_mode = False
        self.set_watch_button_enabled(False)

    def _create_ui(self) -> None:
        """Create the UI components with improved layout and spacing."""
        # Main layout for the group box
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 20, 15, 15)

        # Form layout for inputs
        form_layout = QFormLayout()
        form_layout.setSpacing(12)
        form_layout.setHorizontalSpacing(15)
        form_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        # Channel input
        self.channel_input = QLineEdit()
        self.channel_input.setPlaceholderText("Enter channel name...")
        self.channel_input.setMinimumWidth(250)

        # Validation label
        self.validation_label = QLabel("")
        self.validation_label.setObjectName("validationLabel")
        self.validation_label.setMinimumHeight(20)

        # Create channel input row with validation label
        channel_layout = QHBoxLayout()
        channel_layout.setSpacing(10)
        channel_layout.addWidget(self.channel_input, 1)
        channel_layout.addWidget(self.validation_label, 0)

        form_layout.addRow("Channel:", channel_layout)

        # Quality selection
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(self.quality_options)
        self.quality_combo.setCurrentText("best")
        self.quality_combo.setMinimumWidth(150)

        form_layout.addRow("Quality:", self.quality_combo)

        main_layout.addLayout(form_layout)

        # Watch button
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 10, 0, 0)

        self.watch_button = QPushButton("Watch Stream")
        self.watch_button.setObjectName("watchButton")
        self.watch_button.setMinimumHeight(35)
        self.watch_button.setMinimumWidth(130)

        button_layout.addStretch()
        button_layout.addWidget(self.watch_button)
        button_layout.addStretch()

        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

    def _connect_signals(self) -> None:
        """Connect internal signals."""
        # Watch button clicked
        self.watch_button.clicked.connect(self._on_watch_clicked)

        # Channel input changed
        self.channel_input.textChanged.connect(self._on_channel_changed)

        # Enter key in channel input
        self.channel_input.returnPressed.connect(self._on_enter_pressed)

    def _on_channel_changed(self, text: str) -> None:
        """
        Handle channel input change.

        Args:
            text: Current channel input text
        """
        self.channel_changed.emit(text)

    def _on_watch_clicked(self) -> None:
        """Handle watch button click."""
        channel = self.channel_input.text().strip()
        quality = self.quality_combo.currentText()

        if channel:
            logger.info(f"Watch stream requested: {channel} @ {quality}")
            self.watch_stream_requested.emit(channel, quality)
        else:
            logger.warning("Watch button clicked but channel is empty")

    def _on_enter_pressed(self) -> None:
        """Handle Enter key press in channel input."""
        if self.watch_button.isEnabled():
            self._on_watch_clicked()

    def get_channel(self) -> str:
        """
        Get the current channel name.

        Returns:
            Channel name from input field
        """
        return self.channel_input.text().strip()

    def get_quality(self) -> str:
        """
        Get the selected quality.

        Returns:
            Selected quality value
        """
        return self.quality_combo.currentText()

    def set_channel(self, channel: str) -> None:
        """
        Set the channel name.

        Args:
            channel: Channel name to set
        """
        self.channel_input.setText(channel)

    def set_quality(self, quality: str) -> None:
        """
        Set the quality selection.

        Args:
            quality: Quality to select
        """
        if quality in self.quality_options:
            self.quality_combo.setCurrentText(quality)
        else:
            logger.warning(f"Invalid quality value: {quality}")

    def set_watch_button_enabled(self, enabled: bool) -> None:
        """
        Enable or disable the watch button.

        Args:
            enabled: True to enable, False to disable
        """
        self.watch_button.setEnabled(enabled)

    def set_validation_message(self, message: str, is_valid: bool) -> None:
        """
        Set the validation message and styling.

        Args:
            message: Validation message to display
            is_valid: True if valid, False if invalid
        """
        self.validation_label.setText(message)

        if not message:
            self.validation_label.setStyleSheet("")
        elif is_valid:
            color = "#3CB371" if self._dark_mode else "#006400"
            self.validation_label.setStyleSheet(f"color: {color};")
        else:
            self.validation_label.setStyleSheet("color: #FF0000;")

    def clear_validation_message(self) -> None:
        """Clear the validation message."""
        self.validation_label.setText("")
        self.validation_label.setStyleSheet("")

    def set_dark_mode(self, enabled: bool) -> None:
        self._dark_mode = enabled

    def focus_channel_input(self) -> None:
        """Set focus to the channel input field."""
        self.channel_input.setFocus()
