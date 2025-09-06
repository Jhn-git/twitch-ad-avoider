"""
Input validation controller for TwitchAdAvoider GUI.

This module provides centralized input validation handling, extracted from the
monolithic StreamGUI class to improve maintainability and separation of concerns.

The :class:`ValidationController` handles:
    - Real-time channel name validation
    - Visual feedback management for validation states
    - Integration with core validation functions
    - UI state management based on validation results

Key Features:
    - Real-time validation with visual feedback
    - Centralized validation logic
    - Theme-aware validation messaging
    - UI control state management
"""

from typing import Callable, Optional, Dict, Any
import tkinter as tk
from tkinter import ttk

from src.validators import validate_channel_name
from src.exceptions import ValidationError
from src.logging_config import get_logger

logger = get_logger(__name__)


class ValidationState:
    """Represents the result of a validation operation"""
    
    def __init__(self, is_valid: bool, message: str = "", error_type: Optional[str] = None):
        self.is_valid = is_valid
        self.message = message
        self.error_type = error_type


class ValidationController:
    """
    Manages input validation and visual feedback for the GUI application.
    
    This controller extracts validation logic from the main GUI class,
    providing a clean separation between UI presentation and validation handling.
    """

    def __init__(self, current_theme: Dict[str, Any]):
        """
        Initialize the ValidationController.

        Args:
            current_theme: Current theme dictionary with validation colors
        """
        self.current_theme = current_theme
        
        # UI widget references (set by GUI components)
        self.validation_label: Optional[ttk.Label] = None
        self.watch_button: Optional[ttk.Button] = None
        
        # Callbacks for validation events
        self.on_validation_changed: Optional[Callable[[ValidationState], None]] = None

    def set_ui_components(self, 
                         validation_label: ttk.Label,
                         watch_button: ttk.Button) -> None:
        """
        Set references to UI components for validation feedback.
        
        Args:
            validation_label: Label widget for displaying validation messages
            watch_button: Button widget to enable/disable based on validation
        """
        self.validation_label = validation_label
        self.watch_button = watch_button

    def set_theme(self, theme: Dict[str, Any]) -> None:
        """
        Update the current theme for validation colors.
        
        Args:
            theme: Theme dictionary with validation color definitions
        """
        self.current_theme = theme

    def set_validation_callback(self, callback: Callable[[ValidationState], None]) -> None:
        """
        Set callback function for validation state changes.
        
        Args:
            callback: Function to call when validation state changes
        """
        self.on_validation_changed = callback

    def validate_channel_input(self, channel_text: str) -> ValidationState:
        """
        Validate channel input and provide visual feedback.

        Args:
            channel_text: Channel name to validate

        Returns:
            ValidationState object with validation result
        """
        channel = channel_text.strip()

        # Empty input state
        if not channel:
            validation_state = ValidationState(is_valid=False, message="", error_type="empty")
            self._update_validation_ui(validation_state)
            return validation_state

        # Perform channel name validation
        try:
            validate_channel_name(channel)
            validation_state = ValidationState(is_valid=True, message="✓ Valid")
            self._update_validation_ui(validation_state)
            return validation_state
            
        except ValidationError as e:
            validation_state = ValidationState(
                is_valid=False, 
                message=f"✗ {str(e)}", 
                error_type="validation_error"
            )
            self._update_validation_ui(validation_state)
            return validation_state
            
        except Exception as e:
            logger.warning(f"Unexpected validation error for '{channel}': {e}")
            validation_state = ValidationState(
                is_valid=False, 
                message="✗ Invalid format", 
                error_type="unknown_error"
            )
            self._update_validation_ui(validation_state)
            return validation_state

    def validate_channel_for_favorites(self, channel_text: str) -> str:
        """
        Validate and normalize channel name for adding to favorites.
        
        Args:
            channel_text: Channel name to validate
            
        Returns:
            Validated and normalized channel name
            
        Raises:
            ValidationError: If channel name is invalid
        """
        channel = channel_text.strip()
        if not channel:
            raise ValidationError("Channel name cannot be empty")
            
        return validate_channel_name(channel)

    def create_tkinter_trace_callback(self, channel_var: tk.StringVar) -> Callable:
        """
        Create a Tkinter trace callback for real-time validation.
        
        Args:
            channel_var: StringVar to monitor for changes
            
        Returns:
            Callback function suitable for Tkinter trace_add
        """
        def trace_callback(*args) -> None:
            """Tkinter trace callback for real-time validation"""
            channel_text = channel_var.get()
            validation_state = self.validate_channel_input(channel_text)
            
            # Notify external callbacks
            if self.on_validation_changed:
                self.on_validation_changed(validation_state)
                
        return trace_callback

    def _update_validation_ui(self, validation_state: ValidationState) -> None:
        """
        Update UI components based on validation state.
        
        Args:
            validation_state: Current validation state
        """
        if not self.validation_label or not self.watch_button:
            return
            
        if validation_state.error_type == "empty":
            # Empty input - neutral state
            self.validation_label.config(
                text=validation_state.message,
                foreground=self.current_theme.get("validation_neutral", "gray")
            )
            self.watch_button.config(state="disabled")
            
        elif validation_state.is_valid:
            # Valid input - success state
            self.validation_label.config(
                text=validation_state.message,
                foreground=self.current_theme.get("validation_valid", "green")
            )
            self.watch_button.config(state="normal")
            
        else:
            # Invalid input - error state
            self.validation_label.config(
                text=validation_state.message,
                foreground=self.current_theme.get("validation_invalid", "red")
            )
            self.watch_button.config(state="disabled")

    def clear_validation(self) -> None:
        """Clear validation state and reset UI to neutral"""
        if self.validation_label:
            self.validation_label.config(text="")
        if self.watch_button:
            self.watch_button.config(state="disabled")

    def set_manual_validation_message(self, message: str, is_valid: bool) -> None:
        """
        Manually set validation message and state.
        
        Args:
            message: Message to display
            is_valid: Whether the current state is valid
        """
        validation_state = ValidationState(is_valid=is_valid, message=message)
        self._update_validation_ui(validation_state)
        
        if self.on_validation_changed:
            self.on_validation_changed(validation_state)