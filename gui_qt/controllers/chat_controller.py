"""
Chat management controller for TwitchAdAvoider Qt GUI.

This module provides centralized chat functionality using Qt signals
for thread-safe communication.

The ChatController handles:
    - Chat client connection management
    - Thread-safe UI updates via signals
    - Chat lifecycle (connect, disconnect, cleanup)
    - Authentication integration

Key Features:
    - Signal-based thread-safe communication
    - Integration with Twitch IRC client
    - OAuth authentication support
    - Message confirmation tracking
"""

from PySide6.QtCore import QObject, Signal
from typing import Optional
from datetime import datetime

from src.twitch_chat_client import TwitchChatClient, ChatMessage
from src.config_manager import ConfigManager
from src.auth_manager import AuthManager
from src.validators import validate_channel_name
from src.logging_config import get_logger

logger = get_logger(__name__)


class ChatController(QObject):
    """
    Manages chat operations with signal-based communication.

    This controller handles Twitch chat integration using Qt signals
    for thread-safe UI updates from IRC callbacks.

    Signals:
        chat_connected(str): Emitted when connected to chat
            Args: (channel)
        chat_disconnected(): Emitted when disconnected from chat
        message_received(str, str, datetime): Emitted when message received
            Args: (username, message, timestamp)
        system_message(str): Emitted for system messages
            Args: (message)
        auth_success(str): Emitted when authentication succeeds
            Args: (username)
        auth_failure(str): Emitted when authentication fails
            Args: (error_message)
        send_success(str): Emitted when message send confirmed
            Args: (message)
        send_error(str): Emitted when message send fails
            Args: (error_message)
    """

    # Signals
    chat_connected = Signal(str)  # channel
    chat_disconnected = Signal()
    message_received = Signal(str, str, object)  # username, message, timestamp
    system_message = Signal(str)  # message
    auth_success = Signal(str)  # username
    auth_failure = Signal(str)  # error_message
    send_success = Signal(str)  # message
    send_error = Signal(str)  # error_message

    def __init__(self, config: ConfigManager):
        """
        Initialize the ChatController.

        Args:
            config: Configuration manager for settings
        """
        super().__init__()

        self.config = config

        # Chat client and authentication
        self.chat_client = TwitchChatClient()
        self.auth_manager: Optional[AuthManager] = None
        self.current_channel: Optional[str] = None
        self.is_connecting = False

        # Configuration
        self.auto_connect = self.config.get("chat_auto_connect", True)

        # Initialize authentication if credentials available
        client_id = self.config.get("twitch_client_id", "")
        client_secret = self.config.get("twitch_client_secret", "")

        if client_id and client_secret:
            self.auth_manager = AuthManager(client_id, client_secret)
            self._setup_auth_callbacks()

            # Check if already authenticated
            if self.auth_manager.is_authenticated():
                username = self.auth_manager.get_username()
                access_token = self.auth_manager.get_access_token()
                self.chat_client.set_authentication(username, access_token)
                logger.info(f"Chat authenticated as {username}")

        # Setup chat callbacks
        self._setup_chat_callbacks()

        logger.debug("ChatController initialized")

    def _setup_chat_callbacks(self) -> None:
        """Setup callbacks for the chat client."""
        self.chat_client.on_connect = self._on_chat_connected
        self.chat_client.on_disconnect = self._on_chat_disconnected
        self.chat_client.on_message = self._on_chat_message
        self.chat_client.on_send_success = self._on_message_sent
        self.chat_client.on_send_error = self._on_message_send_error

    def _setup_auth_callbacks(self) -> None:
        """Setup callbacks for the authentication manager."""
        if self.auth_manager:
            self.auth_manager.set_callbacks(
                on_success=self._on_auth_success,
                on_failure=self._on_auth_failure
            )

    def _on_chat_connected(self) -> None:
        """Handle chat connection success (called from IRC thread)."""
        self.is_connecting = False
        channel = self.current_channel
        logger.info(f"Chat connected to #{channel}")
        self.chat_connected.emit(channel)

    def _on_chat_disconnected(self) -> None:
        """Handle chat disconnection (called from IRC thread)."""
        self.is_connecting = False
        logger.info("Chat disconnected")
        self.chat_disconnected.emit()

    def _on_chat_message(self, message: ChatMessage) -> None:
        """
        Handle incoming chat message (called from IRC thread).

        Args:
            message: Chat message object
        """
        logger.debug(f"Received chat message from {message.username}")
        self.message_received.emit(
            message.username,
            message.message,
            message.timestamp
        )

    def _on_message_sent(self, message: str) -> None:
        """
        Handle message send confirmation (called from IRC thread).

        Args:
            message: Sent message text
        """
        logger.debug(f"Message send confirmed: {message}")
        self.send_success.emit(message)

    def _on_message_send_error(self, message: str) -> None:
        """
        Handle message send error (called from IRC thread).

        Args:
            message: Error message
        """
        logger.warning(f"Message send error: {message}")
        self.send_error.emit(message)

    def _on_auth_success(self, username: str) -> None:
        """
        Handle authentication success.

        Args:
            username: Authenticated username
        """
        logger.info(f"Authentication successful for {username}")
        if self.auth_manager:
            access_token = self.auth_manager.get_access_token()
            self.chat_client.set_authentication(username, access_token)
        self.auth_success.emit(username)

    def _on_auth_failure(self, error: str) -> None:
        """
        Handle authentication failure.

        Args:
            error: Error message
        """
        logger.error(f"Authentication failed: {error}")
        self.auth_failure.emit(error)

    def connect_to_channel(self, channel: str) -> bool:
        """
        Connect to a Twitch channel's chat.

        Args:
            channel: Channel name to connect to

        Returns:
            True if connection initiated, False if failed
        """
        try:
            # Validate channel name
            validate_channel_name(channel)

            # Disconnect from current channel if connected
            if self.is_connected():
                logger.info(f"Disconnecting from current channel before connecting to {channel}")
                self.disconnect()

            self.current_channel = channel
            self.is_connecting = True

            # Start connection in background
            success = self.chat_client.connect(channel)

            if not success:
                self.is_connecting = False
                logger.error(f"Failed to initiate connection to #{channel}")
                return False

            logger.info(f"Connecting to #{channel}")
            return True

        except Exception as e:
            self.is_connecting = False
            logger.error(f"Error connecting to chat: {e}")
            self.system_message.emit(f"Chat connection error: {str(e)}")
            return False

    def disconnect(self) -> None:
        """Disconnect from current chat channel."""
        if self.chat_client.is_connected() or self.is_connecting:
            logger.info("Disconnecting from chat")
            self.chat_client.disconnect()
            self.current_channel = None
            self.is_connecting = False

    def send_message(self, message: str) -> bool:
        """
        Send a message to the current chat channel.

        Args:
            message: Message text to send

        Returns:
            True if message was sent, False otherwise
        """
        if not self.is_connected():
            logger.warning("Cannot send message - not connected to chat")
            self.send_error.emit("Not connected to chat")
            return False

        if not message.strip():
            logger.warning("Cannot send empty message")
            return False

        try:
            success = self.chat_client.send_message(message)
            if success:
                logger.debug(f"Message sent: {message}")
            else:
                logger.warning("Failed to send message")
                self.send_error.emit("Failed to send message")
            return success

        except Exception as e:
            logger.error(f"Error sending message: {e}")
            self.send_error.emit(str(e))
            return False

    def is_connected(self) -> bool:
        """
        Check if connected to chat.

        Returns:
            True if connected, False otherwise
        """
        return self.chat_client.is_connected()

    def is_authenticated(self) -> bool:
        """
        Check if authenticated with Twitch.

        Returns:
            True if authenticated, False otherwise
        """
        return self.auth_manager and self.auth_manager.is_authenticated()

    def start_authentication(self) -> None:
        """Start the OAuth authentication flow."""
        if not self.auth_manager:
            logger.error("AuthManager not initialized - missing client credentials")
            self.auth_failure.emit("Chat authentication not configured")
            return

        try:
            logger.info("Starting OAuth authentication flow")
            self.auth_manager.start_oauth_flow()
        except Exception as e:
            logger.error(f"Error starting authentication: {e}")
            self.auth_failure.emit(str(e))

    def logout(self) -> None:
        """Logout and clear authentication."""
        if self.auth_manager:
            logger.info("Logging out")
            self.auth_manager.logout()
            self.chat_client.set_authentication(None, None)

        # Disconnect from chat
        self.disconnect()

    def cleanup(self) -> None:
        """Cleanup chat resources."""
        logger.info("Cleaning up chat controller")
        self.disconnect()

    def get_current_channel(self) -> Optional[str]:
        """
        Get the current connected channel.

        Returns:
            Channel name or None
        """
        return self.current_channel if self.is_connected() else None

    def get_username(self) -> Optional[str]:
        """
        Get the authenticated username.

        Returns:
            Username or None
        """
        if self.auth_manager and self.auth_manager.is_authenticated():
            return self.auth_manager.get_username()
        return None
