"""
Twitch IRC chat client for TwitchAdAvoider.

This module provides a simple IRC client implementation for connecting to Twitch chat
channels and receiving real-time messages. It integrates with the main application's
logging system and follows the project's validation and security practices.

The :class:`TwitchChatClient` provides:
    - Anonymous IRC connection to Twitch servers
    - Real-time message parsing and handling
    - Thread-safe message processing
    - Integration with application logging system
    - Callback-based event handling for UI updates

Key Features:
    - Anonymous connection using justinfan usernames
    - Automatic PING/PONG handling for connection stability
    - Regex-based message parsing for usernames and content
    - Thread-safe callback system for UI integration
"""

import socket
import threading
import time
import re
from typing import Callable, Optional, Dict, Any

from .logging_config import get_logger

logger = get_logger(__name__)


class ChatMessage:
    """Represents a chat message with parsed components."""

    def __init__(self, raw_message: str):
        self.raw = raw_message
        self.username = ""
        self.message = ""
        self.timestamp = time.time()
        self.tags = {}

        self._parse_message()

    def _parse_message(self):
        """Parse IRC message format."""
        # Basic IRC message parsing for Twitch
        # Format: @tags :username!username@username.tmi.twitch.tv PRIVMSG #channel :message

        if self.raw.startswith("@"):
            # Parse tags
            tag_end = self.raw.find(" ")
            tag_part = self.raw[1:tag_end]
            for tag in tag_part.split(";"):
                if "=" in tag:
                    key, value = tag.split("=", 1)
                    self.tags[key] = value
            message_part = self.raw[tag_end + 1 :]
        else:
            message_part = self.raw

        # Parse username and message
        if "PRIVMSG" in message_part:
            # Updated regex to handle channel names with underscores/numbers and any username characters
            match = re.search(r":([a-zA-Z0-9_]+)!.*PRIVMSG #([a-zA-Z0-9_]+) :(.+)", message_part)
            if match:
                self.username = match.group(1)
                self.message = match.group(3).strip()


class TwitchChatClient:
    """
    Twitch IRC chat client for real-time messaging and receiving.

    This client supports both anonymous and authenticated connections to Twitch IRC,
    providing callback-based event handling for integration with GUI components.
    When authenticated, it can send messages to chat.
    """

    def __init__(self):
        self.socket = None
        self.connected = False
        self.running = False
        self.current_channel = None

        # Authentication state
        self.is_authenticated = False
        self.username = None
        self.oauth_token = None
        
        # Message tracking for USERSTATE confirmation
        self.pending_messages = []  # List of recently sent messages awaiting confirmation

        # Callbacks
        self.on_message: Optional[Callable[[ChatMessage], None]] = None
        self.on_connect: Optional[Callable[[], None]] = None
        self.on_disconnect: Optional[Callable[[], None]] = None
        self.on_raw_message: Optional[Callable[[str], None]] = None
        self.on_send_success: Optional[Callable[[str], None]] = None
        self.on_send_error: Optional[Callable[[str], None]] = None

        # IRC settings
        self.server = "irc.chat.twitch.tv"
        self.port = 6667
        self.nickname = f"justinfan{int(time.time() % 100000)}"  # Default anonymous user

    def set_authentication(self, username: str, oauth_token: str) -> None:
        """
        Set authentication credentials for the chat client.
        
        Args:
            username: Twitch username
            oauth_token: OAuth access token
        """
        self.username = username.lower()
        self.oauth_token = oauth_token
        self.nickname = self.username
        self.is_authenticated = True
        logger.info(f"Authentication set for user: {self.username}")

    def clear_authentication(self) -> None:
        """Clear authentication credentials and return to anonymous mode"""
        self.username = None
        self.oauth_token = None
        self.nickname = f"justinfan{int(time.time() % 100000)}"
        self.is_authenticated = False
        logger.info("Cleared authentication, using anonymous mode")

    def can_send_messages(self) -> bool:
        """Check if the client can send messages (requires authentication)"""
        return self.is_authenticated and self.connected

    def connect(self, channel: str) -> bool:
        """
        Connect to Twitch IRC and join a channel.

        Args:
            channel: Twitch channel name to join (with or without # prefix)

        Returns:
            True if connection successful, False otherwise
        """
        # Close any existing connection
        if self.socket:
            self.disconnect()
        
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10.0)

            logger.info(f"Connecting to {self.server}:{self.port}")
            self.socket.connect((self.server, self.port))

            # Send IRC handshake (use OAuth token if authenticated)
            if self.is_authenticated and self.oauth_token:
                self.socket.send(f"PASS oauth:{self.oauth_token}\r\n".encode("utf-8"))
                logger.info(f"Using authenticated connection for user: {self.username}")
                logger.debug(f"OAuth token provided: {self.oauth_token[:20]}...")
            else:
                self.socket.send(f"PASS SCHMOOPIIE\r\n".encode("utf-8"))
                logger.info("Using anonymous connection (read-only mode)")
            
            self.socket.send(f"NICK {self.nickname}\r\n".encode("utf-8"))

            # Request capabilities for better message parsing and USERSTATE messages
            self.socket.send(b"CAP REQ :twitch.tv/tags twitch.tv/commands\r\n")
            logger.info("Requested IRC capabilities: twitch.tv/tags twitch.tv/commands")

            # Join the channel
            channel = channel.lower()
            if not channel.startswith("#"):
                channel = f"#{channel}"

            self.socket.send(f"JOIN {channel}\r\n".encode("utf-8"))
            self.current_channel = channel

            self.connected = True
            self.running = True

            if self.on_connect:
                self.on_connect()

            # Start listening thread
            self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
            self.listen_thread.start()

            logger.info(f"Connected to channel {channel}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to Twitch IRC: {e}")
            self.connected = False
            return False

    def disconnect(self):
        """Disconnect from Twitch IRC."""
        self.running = False
        self.connected = False
        
        if self.socket:
            try:
                # Try to close the socket gracefully
                self.socket.shutdown(socket.SHUT_RDWR)
            except Exception as e:
                logger.debug(f"Error shutting down socket: {e}")
            
            try:
                self.socket.close()
            except Exception as e:
                logger.debug(f"Error closing socket: {e}")
            
            self.socket = None

        if self.on_disconnect:
            self.on_disconnect()

        logger.info("Disconnected from Twitch IRC")

    def _listen_loop(self):
        """Main listening loop for incoming messages."""
        buffer = ""

        while self.running and self.connected:
            try:
                if not self.socket:
                    break
                    
                data = self.socket.recv(4096).decode("utf-8", errors="ignore")
                if not data:
                    logger.debug("Received empty data, connection closed by server")
                    break

                buffer += data

                # Process complete lines
                while "\r\n" in buffer:
                    line, buffer = buffer.split("\r\n", 1)
                    if line:
                        self._handle_message(line)

            except socket.timeout:
                # Timeout is expected, continue listening
                continue
            except OSError as e:
                # Handle socket errors specifically
                if e.errno == 10038:  # WSAENOTSOCK on Windows
                    logger.debug("Socket operation attempted on non-socket object")
                else:
                    logger.error(f"Socket error in chat listen loop: {e}")
                break
            except Exception as e:
                logger.error(f"Error in chat listen loop: {e}")
                break

        # Clean up connection state
        self.connected = False
        if self.on_disconnect:
            try:
                self.on_disconnect()
            except Exception as e:
                logger.debug(f"Error in disconnect callback: {e}")

    def _handle_message(self, raw_message: str):
        """Handle incoming IRC messages."""
        # Enhanced debug logging for all IRC messages
        logger.debug(f"RAW IRC: {raw_message}")
        
        # Call raw message callback for debugging
        if self.on_raw_message:
            self.on_raw_message(raw_message)

        # Handle PING/PONG to stay connected
        if raw_message.startswith("PING"):
            pong_response = raw_message.replace("PING", "PONG")
            self.socket.send(f"{pong_response}\r\n".encode("utf-8"))
            return
        
        # Handle USERSTATE messages (confirm our own messages were sent)
        if "USERSTATE" in raw_message and self.is_authenticated:
            logger.debug(f"🔄 USERSTATE received (pending: {len(self.pending_messages)})")
            # USERSTATE is sent by Twitch to confirm our message was processed
            # This is the proper way to confirm message delivery on Twitch IRC
            # We'll use this instead of waiting for PRIVMSG echoes
            self._handle_userstate_message(raw_message)
            return

        # Handle PRIVMSG (chat messages from other users)
        if "PRIVMSG" in raw_message:
            message = ChatMessage(raw_message)
            if message.username and message.message:
                # Only process messages from other users (not our own)
                # Our own messages are confirmed via USERSTATE, not PRIVMSG echoes
                if not (self.is_authenticated and message.username.lower() == self.username):
                    logger.debug(f"Received chat message from {message.username}: {message.message}")
                    
                    if self.on_message:
                        self.on_message(message)
                else:
                    logger.debug(f"Ignoring our own PRIVMSG echo (using USERSTATE for confirmation): {message.username}")
            else:
                # Debug failed parsing
                logger.debug(f"Failed to parse chat message: {raw_message}")

        # Log other messages for debugging
        logger.debug(f"IRC: {raw_message}")

    def _handle_userstate_message(self, raw_message: str):
        """Handle USERSTATE messages that confirm our messages were sent"""
        try:
            logger.debug("🔍 Processing USERSTATE message for confirmation")
            
            # USERSTATE is sent by Twitch for various reasons:
            # 1. After sending a message (what we want to confirm)
            # 2. When joining a channel 
            # 3. When capabilities change
            # We only care about message confirmations
            
            # Find the most recent unconfirmed message
            confirmed_any = False
            for pending in self.pending_messages:
                if not pending['confirmed']:
                    message = pending['message']
                    pending['confirmed'] = True
                    confirmed_any = True
                    
                    logger.info(f"✅ CONFIRMED via USERSTATE: Message successfully sent to Twitch: '{message}'")
                    
                    # Call success callback
                    if self.on_send_success:
                        self.on_send_success(message)
                    
                    break
            
            # Only warn if we're actively sending messages but can't confirm any
            if not confirmed_any and len(self.pending_messages) == 0:
                # This is normal - USERSTATE can be sent for non-message events
                logger.debug("Received USERSTATE (likely for channel join or capability change, not message confirmation)")
            elif not confirmed_any:
                # This might indicate a timing issue
                logger.debug(f"Received USERSTATE but all {len(self.pending_messages)} pending messages already confirmed")
                
        except Exception as e:
            logger.error(f"Error handling USERSTATE message: {e}")

    def is_connected(self) -> bool:
        """Check if currently connected."""
        return self.connected

    def get_current_channel(self) -> Optional[str]:
        """Get the currently connected channel."""
        return self.current_channel

    def send_message(self, message: str) -> bool:
        """
        Send a message to the current channel.
        
        Args:
            message: Message text to send
            
        Returns:
            True if message was sent successfully, False otherwise
        """
        if not self.can_send_messages():
            error_msg = "Cannot send message: not authenticated or not connected"
            logger.warning(error_msg)
            if self.on_send_error:
                self.on_send_error(error_msg)
            return False
        
        if not self.current_channel:
            error_msg = "Cannot send message: no channel joined"
            logger.warning(error_msg)
            if self.on_send_error:
                self.on_send_error(error_msg)
            return False
        
        # Validate message
        if not message or not message.strip():
            error_msg = "Cannot send empty message"
            logger.warning(error_msg)
            if self.on_send_error:
                self.on_send_error(error_msg)
            return False
        
        message = message.strip()
        
        # Check message length (Twitch limit is 500 characters)
        if len(message) > 500:
            error_msg = "Message too long (max 500 characters)"
            logger.warning(error_msg)
            if self.on_send_error:
                self.on_send_error(error_msg)
            return False
        
        try:
            # Send PRIVMSG command
            privmsg = f"PRIVMSG {self.current_channel} :{message}\r\n"
            bytes_sent = self.socket.send(privmsg.encode("utf-8"))
            
            logger.info(f"Message sent to {self.current_channel}: {message}")
            logger.debug(f"Sent {bytes_sent} bytes to Twitch IRC")
            logger.debug(f"Raw IRC command sent: {privmsg.strip()}")
            
            # Add message to pending list for USERSTATE confirmation
            import time
            self.pending_messages.append({
                'message': message,
                'timestamp': time.time(),
                'confirmed': False
            })
            logger.debug(f"Added message to pending confirmation list")
            
            # Keep only last 10 pending messages to prevent memory issues
            if len(self.pending_messages) > 10:
                self.pending_messages.pop(0)
            
            return True
            
        except Exception as e:
            error_msg = f"Failed to send message: {str(e)}"
            logger.error(error_msg)
            if self.on_send_error:
                self.on_send_error(error_msg)
            return False

    def get_authentication_status(self) -> Dict[str, Any]:
        """
        Get current authentication status information.
        
        Returns:
            Dictionary with authentication details
        """
        return {
            "authenticated": self.is_authenticated,
            "username": self.username,
            "can_send_messages": self.can_send_messages(),
            "connected": self.connected,
            "current_channel": self.current_channel
        }
