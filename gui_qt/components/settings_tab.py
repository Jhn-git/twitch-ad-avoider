"""
Settings tab component for TwitchAdAvoider Qt GUI.

This module provides a comprehensive settings interface with all
configuration options in a scrollable list layout.

The SettingsTab handles:
    - All configuration options from ConfigManager
    - Input validation and real-time feedback
    - Settings persistence via ConfigManager
    - Scrollable layout for extensive settings

Key Features:
    - Simple scrollable list layout
    - Signal-based communication
    - Comprehensive configuration coverage
    - Save/Apply button for persistence
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QComboBox, QCheckBox, QSpinBox,
    QLineEdit, QPushButton, QScrollArea, QGroupBox,
    QFileDialog
)
from PySide6.QtCore import Signal, Qt
from typing import Optional
from pathlib import Path

from src.config_manager import ConfigManager
from src.constants import QUALITY_OPTIONS, SUPPORTED_PLAYERS
from src.logging_config import get_logger

logger = get_logger(__name__)


class SettingsTab(QWidget):
    """
    Comprehensive settings tab for all application configuration.

    This component provides access to all ConfigManager settings
    in a simple, scrollable list layout.

    Signals:
        settings_changed(): Emitted when any setting changes and is saved
        dark_mode_changed(bool): Emitted when dark mode changes
    """

    # Signals
    settings_changed = Signal()
    dark_mode_changed = Signal(bool)

    def __init__(self, config: ConfigManager, parent=None):
        """
        Initialize the SettingsTab.

        Args:
            config: Configuration manager instance
            parent: Parent widget
        """
        super().__init__(parent)

        self.config = config

        # Create UI components
        self._create_ui()

        # Load current settings
        self._load_current_settings()

    def _create_ui(self) -> None:
        """Create the scrollable settings UI."""
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Create scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Create scroll content widget
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(15)
        scroll_layout.setContentsMargins(20, 20, 20, 20)

        # === Stream Settings ===
        stream_group = self._create_stream_settings()
        scroll_layout.addWidget(stream_group)

        # === Network Settings ===
        network_group = self._create_network_settings()
        scroll_layout.addWidget(network_group)

        # === Chat Settings ===
        chat_group = self._create_chat_settings()
        scroll_layout.addWidget(chat_group)

        # === Favorites Settings ===
        favorites_group = self._create_favorites_settings()
        scroll_layout.addWidget(favorites_group)

        # === Appearance Settings ===
        appearance_group = self._create_appearance_settings()
        scroll_layout.addWidget(appearance_group)

        # === Advanced Settings ===
        advanced_group = self._create_advanced_settings()
        scroll_layout.addWidget(advanced_group)

        # Add stretch to push everything to the top
        scroll_layout.addStretch()

        # Set scroll content
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)

        # === Bottom Buttons ===
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(20, 10, 20, 15)

        # Reset to defaults button
        self.reset_button = QPushButton("Reset to Defaults")
        self.reset_button.clicked.connect(self._on_reset_to_defaults)
        button_layout.addWidget(self.reset_button)

        button_layout.addStretch()

        # Apply button
        self.apply_button = QPushButton("Apply Settings")
        self.apply_button.setMinimumWidth(120)
        self.apply_button.clicked.connect(self._on_apply_settings)
        button_layout.addWidget(self.apply_button)

        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

    def _create_stream_settings(self) -> QGroupBox:
        """Create stream settings group."""
        group = QGroupBox("Stream Settings")
        layout = QFormLayout()
        layout.setSpacing(10)

        # Player selection
        self.player_combo = QComboBox()
        self.player_combo.addItems(["vlc", "mpv", "mpc-hc", "auto"])
        layout.addRow("Video Player:", self.player_combo)

        # Quality preference
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(QUALITY_OPTIONS)
        layout.addRow("Preferred Quality:", self.quality_combo)

        # Cache duration
        self.cache_spin = QSpinBox()
        self.cache_spin.setRange(0, 3600)
        self.cache_spin.setSuffix(" seconds")
        layout.addRow("Cache Duration:", self.cache_spin)

        # Player path
        player_path_layout = QHBoxLayout()
        self.player_path_edit = QLineEdit()
        self.player_path_edit.setPlaceholderText("Leave empty for auto-detection")
        player_path_layout.addWidget(self.player_path_edit)

        self.player_path_button = QPushButton("Browse...")
        self.player_path_button.clicked.connect(self._on_browse_player_path)
        player_path_layout.addWidget(self.player_path_button)

        layout.addRow("Custom Player Path:", player_path_layout)

        # Player arguments
        self.player_args_edit = QLineEdit()
        self.player_args_edit.setPlaceholderText("Optional custom player arguments")
        layout.addRow("Player Arguments:", self.player_args_edit)

        group.setLayout(layout)
        return group

    def _create_network_settings(self) -> QGroupBox:
        """Create network settings group."""
        group = QGroupBox("Network Settings")
        layout = QFormLayout()
        layout.setSpacing(10)

        # Network timeout
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(5, 120)
        self.timeout_spin.setSuffix(" seconds")
        layout.addRow("Network Timeout:", self.timeout_spin)

        # Retry attempts
        self.retry_attempts_spin = QSpinBox()
        self.retry_attempts_spin.setRange(1, 10)
        layout.addRow("Connection Retry Attempts:", self.retry_attempts_spin)

        # Retry delay
        self.retry_delay_spin = QSpinBox()
        self.retry_delay_spin.setRange(1, 60)
        self.retry_delay_spin.setSuffix(" seconds")
        layout.addRow("Retry Delay:", self.retry_delay_spin)

        group.setLayout(layout)
        return group

    def _create_chat_settings(self) -> QGroupBox:
        """Create chat settings group."""
        group = QGroupBox("Chat Settings")
        layout = QFormLayout()
        layout.setSpacing(10)

        # Auto-connect to chat
        self.chat_auto_connect_check = QCheckBox("Automatically connect to chat when watching stream")
        layout.addRow(self.chat_auto_connect_check)

        # Max messages
        self.chat_max_messages_spin = QSpinBox()
        self.chat_max_messages_spin.setRange(100, 2000)
        layout.addRow("Max Messages in Memory:", self.chat_max_messages_spin)

        # Show timestamps
        self.chat_timestamps_check = QCheckBox("Show timestamps on chat messages")
        layout.addRow(self.chat_timestamps_check)

        group.setLayout(layout)
        return group

    def _create_favorites_settings(self) -> QGroupBox:
        """Create favorites settings group."""
        group = QGroupBox("Favorites Settings")
        layout = QFormLayout()
        layout.setSpacing(10)

        # Auto-refresh checkbox
        self.favorites_auto_refresh_check = QCheckBox("Automatically refresh favorite channels status")
        layout.addRow(self.favorites_auto_refresh_check)

        # Refresh interval
        self.favorites_refresh_interval_spin = QSpinBox()
        self.favorites_refresh_interval_spin.setRange(30, 3600)
        self.favorites_refresh_interval_spin.setSuffix(" seconds")

        # Create a horizontal layout for the spinbox and minute display
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(self.favorites_refresh_interval_spin)
        self.favorites_interval_label = QLabel()
        interval_layout.addWidget(self.favorites_interval_label)
        interval_layout.addStretch()

        # Connect signal to update minute display
        self.favorites_refresh_interval_spin.valueChanged.connect(self._update_interval_label)

        layout.addRow("Refresh Interval:", interval_layout)

        # Check timeout
        self.favorites_check_timeout_spin = QSpinBox()
        self.favorites_check_timeout_spin.setRange(3, 10)
        self.favorites_check_timeout_spin.setSuffix(" seconds")
        layout.addRow("Status Check Timeout:", self.favorites_check_timeout_spin)

        group.setLayout(layout)
        return group

    def _create_appearance_settings(self) -> QGroupBox:
        """Create appearance settings group."""
        group = QGroupBox("Appearance")
        layout = QFormLayout()
        layout.setSpacing(10)

        # Dark mode checkbox
        self.dark_mode_check = QCheckBox("Enable Dark Mode")
        self.dark_mode_check.stateChanged.connect(self._on_dark_mode_changed)
        layout.addRow(self.dark_mode_check)

        group.setLayout(layout)
        return group

    def _create_advanced_settings(self) -> QGroupBox:
        """Create advanced settings group."""
        group = QGroupBox("Advanced Settings")
        layout = QFormLayout()
        layout.setSpacing(10)

        # Debug mode
        self.debug_check = QCheckBox("Enable Debug Mode")
        layout.addRow(self.debug_check)

        # Log to file
        self.log_to_file_check = QCheckBox("Enable logging to file")
        layout.addRow(self.log_to_file_check)

        # Log level
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        layout.addRow("Log Level:", self.log_level_combo)

        # Twitch Client ID
        self.client_id_edit = QLineEdit()
        self.client_id_edit.setPlaceholderText("Optional: Twitch application client ID")
        layout.addRow("Twitch Client ID:", self.client_id_edit)

        group.setLayout(layout)
        return group

    def _load_current_settings(self) -> None:
        """Load current settings from ConfigManager into UI."""
        # Stream settings
        self.player_combo.setCurrentText(self.config.get("player", "vlc"))
        self.quality_combo.setCurrentText(self.config.get("preferred_quality", "best"))
        self.cache_spin.setValue(self.config.get("cache_duration", 30))

        player_path = self.config.get("player_path")
        if player_path:
            self.player_path_edit.setText(str(player_path))

        player_args = self.config.get("player_args")
        if player_args:
            self.player_args_edit.setText(str(player_args))

        # Network settings
        self.timeout_spin.setValue(self.config.get("network_timeout", 30))
        self.retry_attempts_spin.setValue(self.config.get("connection_retry_attempts", 3))
        self.retry_delay_spin.setValue(self.config.get("retry_delay", 5))

        # Chat settings
        self.chat_auto_connect_check.setChecked(self.config.get("chat_auto_connect", True))
        self.chat_max_messages_spin.setValue(self.config.get("chat_max_messages", 500))
        self.chat_timestamps_check.setChecked(self.config.get("chat_show_timestamps", True))

        # Favorites settings
        self.favorites_auto_refresh_check.setChecked(self.config.get("favorites_auto_refresh", True))
        interval_value = self.config.get("favorites_refresh_interval", 300)
        self.favorites_refresh_interval_spin.setValue(interval_value)
        self._update_interval_label(interval_value)  # Update the minute display
        self.favorites_check_timeout_spin.setValue(self.config.get("favorites_check_timeout", 5))

        # Appearance
        dark_mode = self.config.get("dark_mode", False)
        self.dark_mode_check.setChecked(dark_mode)

        # Advanced settings
        self.debug_check.setChecked(self.config.get("debug", False))
        self.log_to_file_check.setChecked(self.config.get("log_to_file", False))
        self.log_level_combo.setCurrentText(self.config.get("log_level", "INFO"))

        client_id = self.config.get("twitch_client_id", "")
        if client_id:
            self.client_id_edit.setText(client_id)

        logger.debug("Settings loaded into UI")

    def _on_browse_player_path(self) -> None:
        """Handle player path browse button click."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Video Player Executable",
            "",
            "Executables (*.exe);;All Files (*.*)"
        )

        if file_path:
            self.player_path_edit.setText(file_path)
            logger.info(f"Player path selected: {file_path}")

    def _update_interval_label(self, value: int) -> None:
        """
        Update the minute display label for refresh interval.

        Args:
            value: Refresh interval in seconds
        """
        minutes = value / 60
        if value % 60 == 0:
            # Exact minutes
            self.favorites_interval_label.setText(f"({int(minutes)} min)")
        else:
            # Minutes with decimal
            self.favorites_interval_label.setText(f"({minutes:.1f} min)")

    def _on_dark_mode_changed(self, state: int) -> None:
        """
        Handle dark mode checkbox change.

        Args:
            state: Checkbox state
        """
        is_checked = state == Qt.CheckState.Checked
        logger.info(f"Dark mode changed to: {is_checked}")
        # Don't save yet, just emit signal for immediate UI update
        self.dark_mode_changed.emit(is_checked)

    def _on_apply_settings(self) -> None:
        """Apply and save all settings."""
        try:
            # Stream settings
            self.config.set("player", self.player_combo.currentText())
            self.config.set("preferred_quality", self.quality_combo.currentText())
            self.config.set("cache_duration", self.cache_spin.value())

            player_path = self.player_path_edit.text().strip()
            self.config.set("player_path", player_path if player_path else None)

            player_args = self.player_args_edit.text().strip()
            self.config.set("player_args", player_args if player_args else None)

            # Network settings
            self.config.set("network_timeout", self.timeout_spin.value())
            self.config.set("connection_retry_attempts", self.retry_attempts_spin.value())
            self.config.set("retry_delay", self.retry_delay_spin.value())

            # Chat settings
            self.config.set("chat_auto_connect", self.chat_auto_connect_check.isChecked())
            self.config.set("chat_max_messages", self.chat_max_messages_spin.value())
            self.config.set("chat_show_timestamps", self.chat_timestamps_check.isChecked())

            # Favorites settings
            self.config.set("favorites_auto_refresh", self.favorites_auto_refresh_check.isChecked())
            self.config.set("favorites_refresh_interval", self.favorites_refresh_interval_spin.value())
            self.config.set("favorites_check_timeout", self.favorites_check_timeout_spin.value())

            # Appearance
            self.config.set("dark_mode", self.dark_mode_check.isChecked())

            # Advanced settings
            self.config.set("debug", self.debug_check.isChecked())
            self.config.set("log_to_file", self.log_to_file_check.isChecked())
            self.config.set("log_level", self.log_level_combo.currentText())

            client_id = self.client_id_edit.text().strip()
            self.config.set("twitch_client_id", client_id)

            # Save to file
            if self.config.save_settings():
                logger.info("Settings applied and saved successfully")
                self.settings_changed.emit()
            else:
                logger.error("Failed to save settings")

        except Exception as e:
            logger.error(f"Error applying settings: {e}")

    def _on_reset_to_defaults(self) -> None:
        """Reset all settings to default values."""
        reply = self._confirm_reset()

        if reply:
            self.config.reset_to_defaults()
            self.config.save_settings()
            self._load_current_settings()
            self.settings_changed.emit()
            logger.info("Settings reset to defaults")

    def _confirm_reset(self) -> bool:
        """
        Show confirmation dialog for reset action.

        Returns:
            True if user confirms, False otherwise
        """
        from PySide6.QtWidgets import QMessageBox

        reply = QMessageBox.question(
            self,
            "Reset Settings",
            "Are you sure you want to reset all settings to their default values?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        return reply == QMessageBox.StandardButton.Yes
