"""
Chat management controller for TwitchAdAvoider GUI.

This module provides centralized chat functionality, managing the connection 
to Twitch IRC and coordinating between the chat client and UI components.

The :class:`ChatController` handles:
    - Chat client connection management
    - Thread-safe UI updates from IRC callbacks
    - Chat lifecycle (connect, disconnect, cleanup)
    - Integration with configuration system

Key Features:
    - Thread-safe chat message handling
    - Automatic connection/disconnection with streams
    - Configuration-based settings management
    - Error handling and recovery
"""

import tkinter as tk
import threading
import time
from typing import Optional, Callable

from ..status_manager import StatusManager, StatusLevel, StatusCategory
from ..components.chat_panel import ChatPanel
from src.twitch_chat_client import TwitchChatClient, ChatMessage
from src.config_manager import ConfigManager
from src.auth_manager import AuthManager
from src.validators import validate_channel_name
from src.exceptions import ValidationError
from src.logging_config import get_logger

logger = get_logger(__name__)


class ChatController:
    """
    Manages chat operations and lifecycle for the GUI application.

    This controller handles the business logic for Twitch chat integration,
    coordinating between the IRC client and the UI components.
    """

    def __init__(
        self,
        root: tk.Tk,
        chat_panel: ChatPanel,
        config: ConfigManager,
        status_manager: StatusManager,
    ):
        """
        Initialize the ChatController.

        Args:
            root: Main Tkinter root for thread-safe UI updates
            chat_panel: Chat panel component for UI updates
            config: Configuration manager for settings
            status_manager: Status manager for user feedback
        """
        self.root = root
        self.chat_panel = chat_panel
        self.config = config
        self.status_manager = status_manager

        # Chat client and authentication
        self.chat_client = TwitchChatClient()
        self.auth_manager = None  # Will be initialized when client ID is available
        self.current_channel = None
        self.is_connecting = False

        # Configuration
        self.auto_connect = self.config.get("chat_auto_connect", True)
        self.max_messages = self.config.get("chat_max_messages", 500)
        self.show_timestamps = self.config.get("chat_show_timestamps", True)

        # Initialize authentication if client ID is available
        client_id = self.config.get("twitch_client_id", "")
        if client_id:
            self.auth_manager = AuthManager(client_id)
            self._setup_auth_callbacks()
            
            # Check if already authenticated
            if self.auth_manager.is_authenticated():
                username = self.auth_manager.get_username()
                access_token = self.auth_manager.get_access_token()
                self.chat_client.set_authentication(username, access_token)
                self.chat_panel.set_authentication_status(True, username)

        # Apply configuration to chat panel
        self.chat_panel.set_max_messages(self.max_messages)

        # Setup callbacks
        self._setup_chat_callbacks()
        self._setup_chat_panel_callbacks()

        # Callbacks for external events (set by parent)
        self.on_chat_connected: Optional[Callable[[str], None]] = None
        self.on_chat_disconnected: Optional[Callable[[], None]] = None
        self.on_chat_error: Optional[Callable[[str], None]] = None

        logger.debug("ChatController initialized")

    def _setup_chat_callbacks(self) -> None:
        """Setup callbacks for the chat client"""
        self.chat_client.on_connect = self._on_chat_connected
        self.chat_client.on_disconnect = self._on_chat_disconnected
        self.chat_client.on_message = self._on_chat_message
        self.chat_client.on_send_success = self._on_message_sent
        self.chat_client.on_send_error = self._on_message_send_error
        # Note: on_raw_message callback intentionally not set for production

    def _setup_auth_callbacks(self) -> None:
        """Setup callbacks for the authentication manager"""
        if self.auth_manager:
            self.auth_manager.set_callbacks(
                on_success=self._on_auth_success,
                on_failure=self._on_auth_failure
            )

    def _setup_chat_panel_callbacks(self) -> None:
        """Setup callbacks for the chat panel"""
        self.chat_panel.set_callbacks(
            on_auth_login=self._on_auth_login_requested,
            on_auth_logout=self._on_auth_logout_requested,
            on_send_message=self._on_send_message_requested
        )

    def _on_chat_connected(self) -> None:
        """Handle chat connection success (called from IRC thread)"""
        # Schedule UI update on main thread
        self.root.after(0, self._handle_chat_connected)

    def _handle_chat_connected(self) -> None:
        """Handle chat connection on main thread"""
        try:
            self.is_connecting = False
            channel = self.current_channel

            # Update chat panel status
            self.chat_panel.set_connection_status(True, channel)

            # Notify external callbacks
            if self.on_chat_connected:
                self.on_chat_connected(channel)

            logger.info(f"Chat connected to #{channel}")

        except Exception as e:
            logger.error(f"Error handling chat connection: {e}")

    def _on_chat_disconnected(self) -> None:
        """Handle chat disconnection (called from IRC thread)"""
        # Schedule UI update on main thread
        self.root.after(0, self._handle_chat_disconnected)

    def _handle_chat_disconnected(self) -> None:
        """Handle chat disconnection on main thread"""
        try:
            self.is_connecting = False

            # Update chat panel status
            self.chat_panel.set_connection_status(False)

            # Notify external callbacks
            if self.on_chat_disconnected:
                self.on_chat_disconnected()

            logger.info("Chat disconnected")

        except Exception as e:
            logger.error(f"Error handling chat disconnection: {e}")

    def _on_chat_message(self, message: ChatMessage) -> None:
        """Handle incoming chat message (called from IRC thread)"""
        # Schedule UI update on main thread
        self.root.after(0, lambda: self._handle_chat_message(message))

    def _handle_chat_message(self, message: ChatMessage) -> None:
        """Handle chat message on main thread"""
        try:
            # Add message to chat panel
            self.chat_panel.add_message(message.username, message.message, message.timestamp)

        except Exception as e:
            logger.error(f"Error handling chat message: {e}")

    def connect_to_channel(self, channel: str) -> bool:
        """
        Connect to a Twitch channel's chat.

        Args:
            channel: Channel name to connect to

        Returns:
            True if connection initiated, False if invalid or already connecting
        """
        try:
            # Validate channel name
            if not validate_channel_name(channel):
                error_msg = f"Invalid channel name: {channel}"
                logger.warning(error_msg)
                self.status_manager.add_error(error_msg)
                return False

            # Check if already connecting or connected
            if self.is_connecting or self.chat_client.is_connected():
                logger.debug(f"Chat already connecting/connected, disconnecting first")
                self.disconnect_from_chat()

            # Start connection in background thread to avoid blocking UI
            self.is_connecting = True
            self.current_channel = channel.lower()

            # Clear existing messages
            self.chat_panel.clear_chat()

            # Update status
            self.status_manager.add_status_message(f"Connecting to #{channel} chat...")

            # Start connection in background thread
            connection_thread = threading.Thread(
                target=self._connect_in_background, args=(channel,), daemon=True
            )
            connection_thread.start()

            return True

        except ValidationError as e:
            error_msg = f"Channel validation failed: {e}"
            logger.warning(error_msg)
            self.status_manager.add_error(error_msg)
            return False
        except Exception as e:
            error_msg = f"Error connecting to chat: {e}"
            logger.error(error_msg)
            self.status_manager.add_error(error_msg)
            self.is_connecting = False
            return False

    def _connect_in_background(self, channel: str) -> None:
        """Connect to chat in background thread"""
        try:
            success = self.chat_client.connect(channel)

            if not success:
                # Schedule error handling on main thread
                self.root.after(0, lambda: self._handle_connection_error(channel))

        except Exception as e:
            logger.error(f"Error in background chat connection: {e}")
            self.root.after(0, lambda: self._handle_connection_error(channel))

    def _handle_connection_error(self, channel: str) -> None:
        """Handle connection error on main thread"""
        try:
            self.is_connecting = False
            error_msg = f"Failed to connect to #{channel} chat"

            self.status_manager.add_error(error_msg)
            self.chat_panel.set_connection_status(False)

            if self.on_chat_error:
                self.on_chat_error(error_msg)

        except Exception as e:
            logger.error(f"Error handling connection error: {e}")

    def disconnect_from_chat(self) -> None:
        """Disconnect from current chat"""
        try:
            if self.chat_client.is_connected() or self.is_connecting:
                logger.info("Disconnecting from chat")
                self.chat_client.disconnect()
                self.current_channel = None

        except Exception as e:
            logger.error(f"Error disconnecting from chat: {e}")

    def is_connected(self) -> bool:
        """Check if chat is currently connected"""
        return self.chat_client.is_connected()

    def get_current_channel(self) -> Optional[str]:
        """Get the currently connected channel"""
        return self.current_channel

    def should_auto_connect(self) -> bool:
        """Check if auto-connect is enabled"""
        return self.auto_connect

    def set_auto_connect(self, enabled: bool) -> None:
        """
        Set auto-connect preference.

        Args:
            enabled: Whether to auto-connect chat with streams
        """
        self.auto_connect = enabled
        self.config.set("chat_auto_connect", enabled)
        logger.debug(f"Chat auto-connect set to {enabled}")

    def set_max_messages(self, max_messages: int) -> None:
        """
        Set maximum number of messages to keep.

        Args:
            max_messages: Maximum message count
        """
        self.max_messages = max(100, min(2000, max_messages))
        self.chat_panel.set_max_messages(self.max_messages)
        self.config.set("chat_max_messages", self.max_messages)
        logger.debug(f"Chat max messages set to {self.max_messages}")

    def clear_chat(self) -> None:
        """Clear all chat messages"""
        self.chat_panel.clear_chat()

    def set_callbacks(
        self,
        on_connected: Optional[Callable[[str], None]] = None,
        on_disconnected: Optional[Callable[[], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ) -> None:
        """
        Set callback functions for chat events.

        Args:
            on_connected: Called when chat connects (with channel name)
            on_disconnected: Called when chat disconnects
            on_error: Called when chat encounters an error
        """
        self.on_chat_connected = on_connected
        self.on_chat_disconnected = on_disconnected
        self.on_chat_error = on_error

    def update_config(self) -> None:
        """Update configuration from current settings"""
        try:
            # Reload settings from config manager
            self.auto_connect = self.config.get("chat_auto_connect", True)
            self.max_messages = self.config.get("chat_max_messages", 500)
            self.show_timestamps = self.config.get("chat_show_timestamps", True)

            # Apply to chat panel
            self.chat_panel.set_max_messages(self.max_messages)

            logger.debug("Chat configuration updated")

        except Exception as e:
            logger.error(f"Error updating chat configuration: {e}")

    # Authentication callback handlers
    def _on_auth_login_requested(self) -> None:
        """Handle login request from chat panel"""
        if not self.auth_manager:
            client_id = self.config.get("twitch_client_id", "")
            if not client_id:
                self.status_manager.add_error("Twitch Client ID not configured. Please set it in settings.")
                return
            
            # Initialize auth manager if needed
            self.auth_manager = AuthManager(client_id)
            self._setup_auth_callbacks()
        
        # Start OAuth flow
        if not self.auth_manager.start_oauth_flow():
            self.status_manager.add_error("Failed to start authentication flow")

    def _on_auth_logout_requested(self) -> None:
        """Handle logout request from chat panel"""
        if self.auth_manager:
            self.auth_manager.logout()
        
        # Clear chat client authentication
        self.chat_client.clear_authentication()
        
        # Update UI
        self.chat_panel.set_authentication_status(False)
        
        # Disconnect from chat if connected
        if self.chat_client.is_connected():
            self.disconnect_from_chat()
        
        self.status_manager.add_status_message("Logged out successfully")

    def _on_auth_success(self, username: str) -> None:
        """Handle successful authentication"""
        if self.auth_manager:
            access_token = self.auth_manager.get_access_token()
            
            # Set authentication on chat client
            self.chat_client.set_authentication(username, access_token)
            
            # Update UI
            self.chat_panel.set_authentication_status(True, username)
            
            self.status_manager.add_status_message(f"Logged in as {username}")
            logger.info(f"Successfully authenticated as {username}")

    def _on_auth_failure(self, error_message: str) -> None:
        """Handle authentication failure"""
        self.chat_panel.set_authentication_status(False)
        self.status_manager.add_error(f"Login failed: {error_message}")
        logger.warning(f"Authentication failed: {error_message}")

    # Message sending callback handlers
    def _on_send_message_requested(self, message: str) -> None:
        """Handle send message request from chat panel"""
        if not self.chat_client.can_send_messages():
            self.status_manager.add_warning("Cannot send message: not authenticated or not connected")
            return
        
        # Send message via chat client
        success = self.chat_client.send_message(message)
        if not success:
            self.status_manager.add_error("Failed to send message")

    def _on_message_sent(self, message: str) -> None:
        """Handle successful message send"""
        # Add our own message to the chat display
        if self.chat_client.username:
            self.chat_panel.add_message(self.chat_client.username, message, time.time())

    def _on_message_send_error(self, error_message: str) -> None:
        """Handle message send error"""
        self.status_manager.add_error(f"Message send error: {error_message}")

    def cleanup(self) -> None:
        """Clean up chat resources"""
        try:
            logger.info("Cleaning up chat controller")

            # Disconnect from chat
            self.disconnect_from_chat()

            # Clear UI
            self.chat_panel.clear_chat()

            # Reset state
            self.current_channel = None
            self.is_connecting = False

        except Exception as e:
            logger.error(f"Error during chat controller cleanup: {e}")
