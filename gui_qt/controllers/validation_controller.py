"""
Validation controller for TwitchAdAvoider Qt GUI.

This module provides real-time input validation with signal-based
communication to update UI components.

The ValidationController handles:
    - Channel name validation
    - Visual feedback signals
    - Watch button state management

Key Features:
    - Signal-based architecture
    - Integration with core validators
    - Clean separation from UI
"""

from PySide6.QtCore import QObject, Signal

from src.validators import validate_channel_name
from src.logging_config import get_logger

logger = get_logger(__name__)


class ValidationController(QObject):
    """
    Manages input validation with signal-based communication.

    This controller validates user inputs and emits signals to
    update UI components accordingly.

    Signals:
        validation_changed(bool, str): Emitted when validation state changes
            Args: (is_valid, message)
        watch_button_state_changed(bool): Emitted when watch button state should change
            Args: (enabled)
    """

    # Signals
    validation_changed = Signal(bool, str)  # is_valid, message
    watch_button_state_changed = Signal(bool)  # enabled

    def __init__(self):
        """Initialize the ValidationController."""
        super().__init__()

        self.current_channel = ""
        self.is_valid = False

    def validate_channel(self, channel: str) -> None:
        """
        Validate a channel name and emit appropriate signals.

        Args:
            channel: Channel name to validate
        """
        self.current_channel = channel.strip()

        # Empty input - neutral state
        if not self.current_channel:
            self.is_valid = False
            self.validation_changed.emit(False, "")
            self.watch_button_state_changed.emit(False)
            return

        # Validate using core validator
        try:
            validate_channel_name(self.current_channel)
            # Valid channel name
            self.is_valid = True
            self.validation_changed.emit(True, "✓")
            self.watch_button_state_changed.emit(True)
            logger.debug(f"Channel '{self.current_channel}' is valid")

        except ValueError as e:
            # Invalid channel name
            self.is_valid = False
            error_message = str(e)

            # Don't show error for incomplete typing (< 4 chars)
            if len(self.current_channel) < 4:
                self.validation_changed.emit(False, "")  # Silent/neutral state
            else:
                self.validation_changed.emit(False, f"✗ {error_message}")

            self.watch_button_state_changed.emit(False)
            logger.debug(f"Channel '{self.current_channel}' is invalid: {error_message}")

    def get_current_channel(self) -> str:
        """
        Get the current channel being validated.

        Returns:
            Current channel name
        """
        return self.current_channel

    def get_is_valid(self) -> bool:
        """
        Get the current validation state.

        Returns:
            True if current input is valid, False otherwise
        """
        return self.is_valid

    def reset(self) -> None:
        """Reset the validation state."""
        self.current_channel = ""
        self.is_valid = False
        self.validation_changed.emit(False, "")
        self.watch_button_state_changed.emit(False)
