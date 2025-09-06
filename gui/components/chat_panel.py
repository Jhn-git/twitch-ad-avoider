"""
Chat panel component for TwitchAdAvoider GUI.

This module provides the chat display interface for real-time Twitch chat viewing,
extracted as a component to improve maintainability and follow the application's
modular architecture.

The :class:`ChatPanel` handles:
    - Real-time chat message display with timestamps
    - Scrollable message history with auto-scroll
    - Connection status indicators
    - Theme-aware visual styling
    - Message formatting and display limits

Key Features:
    - Auto-scrolling chat display
    - Timestamp formatting for messages
    - Connection status feedback
    - Memory management with message limits
    - Theme integration for consistent styling
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
from typing import Optional, Dict, Any, Callable
import time

from ..status_manager import StatusManager, StatusCategory
from src.logging_config import get_logger

logger = get_logger(__name__)


class ChatPanel:
    """
    Manages the chat display and interactions.

    This component handles the chat section of the GUI, providing
    a real-time chat viewing interface for Twitch streams.
    """

    def __init__(
        self,
        parent: ttk.Frame,
        status_manager: Optional[StatusManager],
        current_theme: Dict[str, Any],
    ):
        """
        Initialize the ChatPanel.

        Args:
            parent: Parent frame to place the chat panel in
            status_manager: Status manager for user feedback
            current_theme: Current UI theme configuration
        """
        self.parent = parent
        self.status_manager = status_manager
        self.current_theme = current_theme

        # Chat state
        self.connected_channel = None
        self.message_count = 0
        self.max_messages = 500  # Default, will be configurable
        
        # Authentication state
        self.is_authenticated = False
        self.username = None

        # Callbacks (set by parent)
        self.on_clear_chat: Optional[Callable[[], None]] = None
        self.on_auth_login: Optional[Callable[[], None]] = None
        self.on_auth_logout: Optional[Callable[[], None]] = None
        self.on_send_message: Optional[Callable[[str], None]] = None

        # Create the main frame and UI
        self._create_chat_frame()

        logger.debug("ChatPanel initialized")

    def _create_chat_frame(self) -> None:
        """Create the main chat panel frame and widgets"""
        # Main chat frame
        self.chat_frame = ttk.LabelFrame(self.parent, text="Chat", padding="10")
        self.chat_frame.grid(
            row=1, column=2, rowspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(10, 0), pady=(0, 10)
        )

        # Configure grid weights for resizing
        self.chat_frame.columnconfigure(0, weight=1)
        self.chat_frame.rowconfigure(0, weight=1)

        # Chat display (scrolled text widget)
        self.chat_display = scrolledtext.ScrolledText(
            self.chat_frame,
            width=40,
            height=15,
            state=tk.DISABLED,
            wrap=tk.WORD,
            relief=tk.SUNKEN,
            borderwidth=1,
        )
        self.chat_display.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 5))

        # Authentication controls frame
        auth_frame = ttk.Frame(self.chat_frame)
        auth_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(5, 0))
        auth_frame.columnconfigure(1, weight=1)

        # Login status label
        self.auth_status_label = ttk.Label(
            auth_frame, text="Not logged in", font=("TkDefaultFont", 8)
        )
        self.auth_status_label.grid(row=0, column=0, sticky=tk.W)

        # Login/Logout button
        self.auth_button = ttk.Button(
            auth_frame, text="Login", command=self._on_auth_button_clicked, width=10
        )
        self.auth_button.grid(row=0, column=2, sticky=tk.E, padx=(5, 0))

        # Message input frame
        input_frame = ttk.Frame(self.chat_frame)
        input_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(5, 0))
        input_frame.columnconfigure(0, weight=1)

        # Message input field
        self.message_entry = ttk.Entry(input_frame, state="disabled")
        self.message_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        self.message_entry.bind("<Return>", self._on_message_entry_return)

        # Send button
        self.send_button = ttk.Button(
            input_frame, text="Send", command=self._on_send_button_clicked, width=8, state="disabled"
        )
        self.send_button.grid(row=0, column=1, sticky=tk.E)

        # Chat controls frame
        controls_frame = ttk.Frame(self.chat_frame)
        controls_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(5, 0))
        controls_frame.columnconfigure(0, weight=1)

        # Connection status label
        self.status_label = ttk.Label(
            controls_frame, text="Chat disconnected", font=("TkDefaultFont", 8)
        )
        self.status_label.grid(row=0, column=0, sticky=tk.W)

        # Clear button
        self.clear_button = ttk.Button(
            controls_frame, text="Clear", command=self._on_clear_chat_clicked, width=8
        )
        self.clear_button.grid(row=0, column=1, sticky=tk.E, padx=(5, 0))

        # Apply theme
        self._apply_theme()

    def _apply_theme(self) -> None:
        """Apply the current theme to chat components"""
        if not self.current_theme:
            return

        try:
            # Apply theme to chat display
            bg_color = self.current_theme.get("bg", "white")
            fg_color = self.current_theme.get("fg", "black")

            self.chat_display.configure(bg=bg_color, fg=fg_color, insertbackground=fg_color)

            # Configure text tags for styling
            self._configure_text_tags()

        except Exception as e:
            logger.error(f"Error applying theme to chat panel: {e}")

    def _configure_text_tags(self) -> None:
        """Configure text tags for message formatting"""
        try:
            # Timestamp tag
            self.chat_display.tag_configure(
                "timestamp",
                foreground=self.current_theme.get("muted_fg", "gray"),
                font=("TkDefaultFont", 8),
            )

            # Username tag
            self.chat_display.tag_configure(
                "username",
                foreground=self.current_theme.get("accent_color", "blue"),
                font=("TkDefaultFont", 9, "bold"),
            )

            # Message tag
            self.chat_display.tag_configure(
                "message",
                foreground=self.current_theme.get("fg", "black"),
                font=("TkDefaultFont", 9),
            )

        except Exception as e:
            logger.error(f"Error configuring chat text tags: {e}")

    def add_message(self, username: str, message: str, timestamp: float) -> None:
        """
        Add a new chat message to the display.

        Args:
            username: Username of the message sender
            message: Message content
            timestamp: Message timestamp
        """
        try:
            # Format timestamp
            time_str = time.strftime("%H:%M:%S", time.localtime(timestamp))

            # Enable editing temporarily
            self.chat_display.config(state=tk.NORMAL)

            # Insert timestamp
            self.chat_display.insert(tk.END, f"[{time_str}] ", "timestamp")

            # Insert username
            self.chat_display.insert(tk.END, f"{username}: ", "username")

            # Insert message
            self.chat_display.insert(tk.END, f"{message}\n", "message")

            # Disable editing
            self.chat_display.config(state=tk.DISABLED)

            # Auto-scroll to bottom
            self.chat_display.see(tk.END)

            # Increment message count
            self.message_count += 1

            # Check if we need to trim old messages
            self._trim_messages_if_needed()

        except Exception as e:
            logger.error(f"Error adding chat message: {e}")

    def _trim_messages_if_needed(self) -> None:
        """Trim old messages if we exceed the maximum"""
        if self.message_count > self.max_messages:
            try:
                # Calculate how many lines to remove (remove oldest 100 messages)
                lines_to_remove = min(100, self.message_count - self.max_messages)

                self.chat_display.config(state=tk.NORMAL)

                # Remove lines from the beginning
                for _ in range(lines_to_remove):
                    self.chat_display.delete("1.0", "2.0")

                self.chat_display.config(state=tk.DISABLED)

                # Update count
                self.message_count -= lines_to_remove

                logger.debug(f"Trimmed {lines_to_remove} old chat messages")

            except Exception as e:
                logger.error(f"Error trimming chat messages: {e}")

    def clear_chat(self) -> None:
        """Clear all chat messages"""
        try:
            self.chat_display.config(state=tk.NORMAL)
            self.chat_display.delete("1.0", tk.END)
            self.chat_display.config(state=tk.DISABLED)
            self.message_count = 0

            logger.debug("Chat messages cleared")

        except Exception as e:
            logger.error(f"Error clearing chat: {e}")

    def set_connection_status(self, connected: bool, channel: Optional[str] = None) -> None:
        """
        Update the connection status display.

        Args:
            connected: Whether chat is connected
            channel: Channel name if connected
        """
        try:
            if connected and channel:
                self.status_label.config(text=f"Connected to #{channel}")
                self.connected_channel = channel

                if self.status_manager:
                    self.status_manager.add_status_message(f"Chat connected to #{channel}")
            else:
                self.status_label.config(text="Chat disconnected")
                self.connected_channel = None

                if self.status_manager:
                    self.status_manager.add_status_message("Chat disconnected")

        except Exception as e:
            logger.error(f"Error updating chat connection status: {e}")

    def set_max_messages(self, max_messages: int) -> None:
        """
        Set the maximum number of messages to keep in memory.

        Args:
            max_messages: Maximum message count
        """
        self.max_messages = max(100, min(2000, max_messages))  # Clamp between 100-2000
        logger.debug(f"Chat max messages set to {self.max_messages}")

    def set_theme(self, theme: Dict[str, Any]) -> None:
        """
        Update the theme for the chat panel.

        Args:
            theme: New theme configuration
        """
        self.current_theme = theme
        self._apply_theme()

    def _on_clear_chat_clicked(self) -> None:
        """Handle clear chat button click"""
        self.clear_chat()
        if self.on_clear_chat:
            self.on_clear_chat()

    def set_callbacks(self, on_clear_chat: Optional[Callable[[], None]] = None) -> None:
        """
        Set callbacks for chat events.

        Args:
            on_clear_chat: Callback when chat is cleared
        """
        self.on_clear_chat = on_clear_chat

    def get_main_frame(self) -> ttk.Frame:
        """
        Get the main frame of the chat panel.

        Returns:
            Main chat panel frame
        """
        return self.chat_frame

    def set_authentication_status(self, authenticated: bool, username: str = None) -> None:
        """
        Update authentication status and UI state.
        
        Args:
            authenticated: Whether user is authenticated
            username: Username if authenticated
        """
        self.is_authenticated = authenticated
        self.username = username
        
        # Update UI based on authentication status
        if authenticated and username:
            self.auth_status_label.config(text=f"Logged in as: {username}")
            self.auth_button.config(text="Logout")
            self.message_entry.config(state="normal")
            self.send_button.config(state="normal")
        else:
            self.auth_status_label.config(text="Not logged in")
            self.auth_button.config(text="Login")
            self.message_entry.config(state="disabled")
            self.send_button.config(state="disabled")
            self.message_entry.delete(0, tk.END)

    def _on_auth_button_clicked(self) -> None:
        """Handle authentication button click"""
        if self.is_authenticated:
            # Logout
            if self.on_auth_logout:
                self.on_auth_logout()
        else:
            # Login
            if self.on_auth_login:
                self.on_auth_login()

    def _on_send_button_clicked(self) -> None:
        """Handle send button click"""
        self._send_current_message()

    def _on_message_entry_return(self, event) -> None:
        """Handle Enter key in message entry"""
        self._send_current_message()
        return "break"  # Prevent default behavior

    def _send_current_message(self) -> None:
        """Send the current message from the entry field"""
        if not self.is_authenticated:
            return
            
        message = self.message_entry.get().strip()
        if not message:
            return
            
        # Clear the entry field
        self.message_entry.delete(0, tk.END)
        
        # Send message via callback
        if self.on_send_message:
            self.on_send_message(message)

    def set_callbacks(self, 
                     on_clear_chat: Optional[Callable[[], None]] = None,
                     on_auth_login: Optional[Callable[[], None]] = None,
                     on_auth_logout: Optional[Callable[[], None]] = None,
                     on_send_message: Optional[Callable[[str], None]] = None) -> None:
        """
        Set callback functions for chat panel interactions.
        
        Args:
            on_clear_chat: Called when user wants to clear chat
            on_auth_login: Called when user wants to login
            on_auth_logout: Called when user wants to logout  
            on_send_message: Called when user sends a message
        """
        self.on_clear_chat = on_clear_chat
        self.on_auth_login = on_auth_login
        self.on_auth_logout = on_auth_logout
        self.on_send_message = on_send_message

    def cleanup(self) -> None:
        """Clean up chat panel resources"""
        try:
            # Clear any remaining messages
            self.clear_chat()

            # Reset state
            self.connected_channel = None
            self.message_count = 0

            logger.debug("ChatPanel cleanup completed")

        except Exception as e:
            logger.error(f"Error during chat panel cleanup: {e}")
