"""
Stream control panel component for TwitchAdAvoider GUI.

This module provides the stream input controls interface,
extracted from the monolithic StreamGUI class to improve maintainability.

The :class:`StreamControlPanel` handles:
    - Channel name input with real-time validation
    - Quality selection dropdown
    - Watch button with state management
    - Integration with validation controller
    - Theme-aware visual styling

Key Features:
    - Real-time input validation with visual feedback
    - Keyboard shortcuts (Enter to watch)
    - Quality preset selection
    - Button state management based on validation
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional, Callable, Dict, Any

from ..controllers.validation_controller import ValidationController, ValidationState
from src.logging_config import get_logger

logger = get_logger(__name__)


class StreamControlPanel:
    """
    Manages the stream input controls and validation.
    
    This component handles the stream input section of the GUI, providing
    a clean interface for channel selection and stream initiation.
    """

    def __init__(self, 
                 parent: ttk.Frame,
                 validation_controller: ValidationController,
                 current_theme: Dict[str, Any]):
        """
        Initialize the StreamControlPanel.

        Args:
            parent: Parent frame to contain the stream controls
            validation_controller: Controller for input validation
            current_theme: Current theme configuration
        """
        self.parent = parent
        self.validation_controller = validation_controller
        self.current_theme = current_theme
        
        # Tkinter variables
        self.channel_var = tk.StringVar()
        self.quality_var = tk.StringVar(value="best")
        
        # UI widget references
        self.channel_entry: Optional[ttk.Entry] = None
        self.validation_label: Optional[ttk.Label] = None
        self.quality_combo: Optional[ttk.Combobox] = None
        self.watch_btn: Optional[ttk.Button] = None
        
        # Callbacks (set by parent components)
        self.on_watch_stream: Optional[Callable[[str, str], None]] = None
        
        # Create the stream input section
        self.main_frame = self._create_stream_input_section()
        
        # Setup validation
        self._setup_validation()

    def set_callbacks(self, on_watch_stream: Optional[Callable[[str, str], None]] = None) -> None:
        """
        Set callback functions for user interactions.
        
        Args:
            on_watch_stream: Called when user wants to watch a stream (channel, quality)
        """
        self.on_watch_stream = on_watch_stream

    def set_theme(self, theme: Dict[str, Any]) -> None:
        """
        Update the current theme.
        
        Args:
            theme: New theme configuration
        """
        self.current_theme = theme
        self.validation_controller.set_theme(theme)

    def _create_stream_input_section(self) -> ttk.LabelFrame:
        """Create the complete stream input section"""
        input_frame = ttk.LabelFrame(self.parent, text="Watch Stream", padding="10")
        input_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        # Channel input row
        self._create_channel_input(input_frame)
        
        # Quality selection row
        self._create_quality_selection(input_frame)
        
        # Watch button row
        self._create_watch_button(input_frame)
        
        # Configure grid weights for responsiveness
        input_frame.columnconfigure(1, weight=1)

        return input_frame

    def _create_channel_input(self, parent: ttk.LabelFrame) -> None:
        """Create the channel input controls"""
        # Channel label
        ttk.Label(parent, text="Channel:").grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        
        # Channel entry
        self.channel_entry = ttk.Entry(parent, textvariable=self.channel_var, width=25)
        self.channel_entry.grid(row=0, column=1, padx=(10, 0), pady=(0, 5), sticky=(tk.W, tk.E))
        self.channel_entry.bind("<Return>", self._on_enter_key)
        
        # Validation feedback label
        self.validation_label = ttk.Label(parent, text="", foreground="red", font=("Arial", 8))
        self.validation_label.grid(row=0, column=2, padx=(5, 0), pady=(0, 5), sticky=tk.W)

    def _create_quality_selection(self, parent: ttk.LabelFrame) -> None:
        """Create the quality selection controls"""
        # Quality label
        ttk.Label(parent, text="Quality:").grid(row=1, column=0, sticky=tk.W, pady=(0, 5))
        
        # Quality combobox
        self.quality_combo = ttk.Combobox(parent, textvariable=self.quality_var, width=22)
        self.quality_combo["values"] = ("best", "worst", "720p", "480p", "360p")
        self.quality_combo.grid(row=1, column=1, padx=(10, 0), pady=(0, 5), sticky=(tk.W, tk.E))
        self.quality_combo.state(["readonly"])

    def _create_watch_button(self, parent: ttk.LabelFrame) -> None:
        """Create the watch button"""
        self.watch_btn = ttk.Button(parent, text="Watch Stream", command=self._on_watch_clicked)
        self.watch_btn.grid(row=2, column=0, columnspan=2, pady=(15, 5))
        self.watch_btn.config(state="disabled")  # Start disabled until valid input

    def _setup_validation(self) -> None:
        """Setup real-time validation for channel input"""
        if not self.validation_label or not self.watch_btn:
            logger.error("Cannot setup validation - UI components not initialized")
            return
            
        # Connect validation controller to UI components
        self.validation_controller.set_ui_components(self.validation_label, self.watch_btn)
        
        # Create and bind trace callback
        trace_callback = self.validation_controller.create_tkinter_trace_callback(self.channel_var)
        self.channel_var.trace_add("write", trace_callback)
        
        # Set validation callback for additional handling
        self.validation_controller.set_validation_callback(self._on_validation_changed)

    def _on_validation_changed(self, validation_state: ValidationState) -> None:
        """Handle validation state changes"""
        # Additional validation handling can be added here if needed
        logger.debug(f"Validation state changed: valid={validation_state.is_valid}, message='{validation_state.message}'")

    def _on_enter_key(self, event) -> None:
        """Handle Enter key press in channel entry"""
        if self.watch_btn and self.watch_btn['state'] == 'normal':
            self._on_watch_clicked()

    def _on_watch_clicked(self) -> None:
        """Handle watch button click"""
        if not self.on_watch_stream:
            logger.warning("No watch stream callback configured")
            return
            
        channel = self.channel_var.get().strip()
        quality = self.quality_var.get()
        
        if channel:
            self.on_watch_stream(channel, quality)

    def get_channel_name(self) -> str:
        """Get the current channel name"""
        return self.channel_var.get().strip()

    def set_channel_name(self, channel: str) -> None:
        """
        Set the channel name.
        
        Args:
            channel: Channel name to set
        """
        self.channel_var.set(channel)

    def get_quality(self) -> str:
        """Get the current quality setting"""
        return self.quality_var.get()

    def set_quality(self, quality: str) -> None:
        """
        Set the quality setting.
        
        Args:
            quality: Quality setting to set
        """
        if quality in self.quality_combo["values"]:
            self.quality_var.set(quality)

    def enable_watch_button(self) -> None:
        """Enable the watch button"""
        if self.watch_btn:
            self.watch_btn.config(state="normal")

    def disable_watch_button(self) -> None:
        """Disable the watch button"""
        if self.watch_btn:
            self.watch_btn.config(state="disabled")

    def set_watch_button_text(self, text: str) -> None:
        """
        Set the text of the watch button.
        
        Args:
            text: Button text to set
        """
        if self.watch_btn:
            self.watch_btn.config(text=text)

    def focus_channel_entry(self) -> None:
        """Focus the channel entry widget"""
        if self.channel_entry:
            self.channel_entry.focus_set()

    def clear_channel_input(self) -> None:
        """Clear the channel input"""
        self.channel_var.set("")

    def clear_validation_message(self) -> None:
        """Clear the validation message"""
        self.validation_controller.clear_validation()

    def set_loading_state(self, loading: bool, message: str = "Starting stream...") -> None:
        """
        Set the loading state of the panel.
        
        Args:
            loading: Whether loading state is active
            message: Loading message to display
        """
        if loading:
            self.disable_watch_button()
            self.set_watch_button_text(message)
            if self.channel_entry:
                self.channel_entry.config(state="disabled")
            if self.quality_combo:
                self.quality_combo.config(state="disabled")
        else:
            self.set_watch_button_text("Watch Stream")
            if self.channel_entry:
                self.channel_entry.config(state="normal")
            if self.quality_combo:
                self.quality_combo.state(["readonly"])
            # Let validation controller handle button enabling

    def get_main_frame(self) -> ttk.LabelFrame:
        """Get the main stream control frame"""
        return self.main_frame

    def cleanup(self) -> None:
        """Cleanup resources"""
        # Clear validation
        self.validation_controller.clear_validation()
        
        # Clear variables
        self.channel_var.set("")
        self.quality_var.set("best")