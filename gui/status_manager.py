"""
Status Manager for TwitchAdAvoider GUI
Handles status message history, categorization, and display management.
"""
import tkinter as tk
from datetime import datetime
from enum import Enum
from typing import List, Optional, Tuple
from collections import deque


class StatusLevel(Enum):
    """Status message severity levels"""
    INFO = "INFO"
    WARNING = "WARNING" 
    ERROR = "ERROR"
    SYSTEM = "SYSTEM"


class StatusCategory(Enum):
    """Status message categories"""
    STREAM = "STREAM"
    FAVORITES = "FAVORITES"
    SYSTEM = "SYSTEM"
    STATUS = "STATUS"
    GENERAL = "GENERAL"


class StatusMessage:
    """Represents a single status message with metadata"""
    
    def __init__(self, text: str, level: StatusLevel = StatusLevel.INFO, 
                 category: StatusCategory = StatusCategory.GENERAL):
        self.text = text
        self.level = level
        self.category = category
        self.timestamp = datetime.now()
    
    def format_for_display(self, include_timestamp: bool = True, 
                          include_category: bool = False) -> str:
        """Format message for display in the status bar"""
        parts = []
        
        if include_timestamp:
            time_str = self.timestamp.strftime("%H:%M:%S")
            parts.append(f"[{time_str}]")
            
        if include_category and self.category != StatusCategory.GENERAL:
            parts.append(f"[{self.category.value}]")
            
        if self.level != StatusLevel.INFO:
            parts.append(f"[{self.level.value}]")
            
        parts.append(self.text)
        
        return " ".join(parts)
    
    def get_color_tag(self) -> str:
        """Get color tag based on message level"""
        color_map = {
            StatusLevel.INFO: "info",
            StatusLevel.WARNING: "warning", 
            StatusLevel.ERROR: "error",
            StatusLevel.SYSTEM: "system"
        }
        return color_map.get(self.level, "info")


class StatusManager:
    """Manages status messages with history and categorization"""
    
    def __init__(self, text_widget: tk.Text, max_history: int = 100):
        """
        Initialize status manager
        
        Args:
            text_widget: Tkinter Text widget for displaying messages
            max_history: Maximum number of messages to keep in history
        """
        self.text_widget = text_widget
        self.max_history = max_history
        self.messages = deque(maxlen=max_history)
        self.visible_lines = 3  # Number of lines to show in status bar
        
        # Configure text widget
        self._configure_text_widget()
        
        # Add initial message
        self.add_message("Ready", StatusLevel.SYSTEM, StatusCategory.SYSTEM)
    
    def _configure_text_widget(self):
        """Configure the text widget appearance and behavior"""
        # Configure text widget properties
        self.text_widget.config(
            state=tk.DISABLED,  # Read-only
            wrap=tk.WORD,       # Word wrapping
            height=self.visible_lines,
            bg="#f0f0f0",       # Light gray background
            relief=tk.SUNKEN,
            borderwidth=1
        )
        
        # Configure color tags
        self.text_widget.tag_configure("info", foreground="black")
        self.text_widget.tag_configure("warning", foreground="orange")
        self.text_widget.tag_configure("error", foreground="red", font=("TkDefaultFont", 9, "bold"))
        self.text_widget.tag_configure("system", foreground="blue")
        
        # Disable text selection and editing
        self.text_widget.bind("<Button-1>", lambda e: "break")
        self.text_widget.bind("<B1-Motion>", lambda e: "break")
    
    def add_message(self, text: str, level: StatusLevel = StatusLevel.INFO,
                   category: StatusCategory = StatusCategory.GENERAL):
        """
        Add a new status message
        
        Args:
            text: Message text
            level: Message severity level
            category: Message category
        """
        message = StatusMessage(text, level, category)
        self.messages.append(message)
        self._update_display()
    
    def add_stream_message(self, text: str, level: StatusLevel = StatusLevel.INFO):
        """Add a stream-related message"""
        self.add_message(text, level, StatusCategory.STREAM)
    
    def add_favorites_message(self, text: str, level: StatusLevel = StatusLevel.INFO):
        """Add a favorites-related message"""
        self.add_message(text, level, StatusCategory.FAVORITES)
    
    def add_system_message(self, text: str, level: StatusLevel = StatusLevel.SYSTEM):
        """Add a system-related message"""
        self.add_message(text, level, StatusCategory.SYSTEM)
    
    def add_status_message(self, text: str, level: StatusLevel = StatusLevel.INFO):
        """Add a status monitoring related message"""
        self.add_message(text, level, StatusCategory.STATUS)
    
    def add_error(self, text: str, category: StatusCategory = StatusCategory.GENERAL):
        """Add an error message"""
        self.add_message(text, StatusLevel.ERROR, category)
    
    def add_warning(self, text: str, category: StatusCategory = StatusCategory.GENERAL):
        """Add a warning message"""
        self.add_message(text, StatusLevel.WARNING, category)
    
    def _update_display(self):
        """Update the text widget display with recent messages"""
        # Get the most recent messages to display
        recent_messages = list(self.messages)[-self.visible_lines:]
        
        # Enable editing temporarily
        self.text_widget.config(state=tk.NORMAL)
        
        # Clear current content
        self.text_widget.delete(1.0, tk.END)
        
        # Add recent messages
        for i, message in enumerate(recent_messages):
            if i > 0:
                self.text_widget.insert(tk.END, "\n")
            
            # Format message for display
            formatted_text = message.format_for_display(
                include_timestamp=True, 
                include_category=False
            )
            
            # Insert text with appropriate color tag
            start_pos = self.text_widget.index(tk.END + "-1c linestart")
            self.text_widget.insert(tk.END, formatted_text)
            end_pos = self.text_widget.index(tk.END + "-1c")
            
            # Apply color tag to the entire line
            self.text_widget.tag_add(message.get_color_tag(), start_pos, end_pos)
        
        # Auto-scroll to bottom
        self.text_widget.see(tk.END)
        
        # Disable editing again
        self.text_widget.config(state=tk.DISABLED)
    
    def get_message_history(self) -> List[StatusMessage]:
        """Get all messages in history"""
        return list(self.messages)
    
    def get_messages_by_level(self, level: StatusLevel) -> List[StatusMessage]:
        """Get all messages of a specific level"""
        return [msg for msg in self.messages if msg.level == level]
    
    def get_messages_by_category(self, category: StatusCategory) -> List[StatusMessage]:
        """Get all messages of a specific category"""
        return [msg for msg in self.messages if msg.category == category]
    
    def clear_history(self):
        """Clear all message history"""
        self.messages.clear()
        self.add_message("History cleared", StatusLevel.SYSTEM, StatusCategory.SYSTEM)
    
    def set_visible_lines(self, lines: int):
        """Set number of visible lines in status display"""
        self.visible_lines = max(1, min(lines, 10))  # Between 1 and 10 lines
        self.text_widget.config(height=self.visible_lines)
        self._update_display()