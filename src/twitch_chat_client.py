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
    Simple Twitch IRC chat client for real-time message receiving.

    This client connects anonymously to Twitch IRC servers and provides
    callback-based event handling for integration with GUI components.
    """

    def __init__(self):
        self.socket = None
        self.connected = False
        self.running = False
        self.current_channel = None

        # Callbacks
        self.on_message: Optional[Callable[[ChatMessage], None]] = None
        self.on_connect: Optional[Callable[[], None]] = None
        self.on_disconnect: Optional[Callable[[], None]] = None
        self.on_raw_message: Optional[Callable[[str], None]] = None

        # IRC settings
        self.server = "irc.chat.twitch.tv"
        self.port = 6667
        self.nickname = f"justinfan{int(time.time() % 100000)}"  # Anonymous user

    def connect(self, channel: str) -> bool:
        """
        Connect to Twitch IRC and join a channel.

        Args:
            channel: Twitch channel name to join (with or without # prefix)

        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10.0)

            logger.info(f"Connecting to {self.server}:{self.port}")
            self.socket.connect((self.server, self.port))

            # Send IRC handshake
            self.socket.send(f"PASS SCHMOOPIIE\r\n".encode("utf-8"))
            self.socket.send(f"NICK {self.nickname}\r\n".encode("utf-8"))

            # Request capabilities for better message parsing
            self.socket.send(b"CAP REQ :twitch.tv/tags\r\n")

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
        if self.socket:
            try:
                self.socket.close()
            except Exception as e:
                logger.debug(f"Error closing socket: {e}")

        self.connected = False
        if self.on_disconnect:
            self.on_disconnect()

        logger.info("Disconnected from Twitch IRC")

    def _listen_loop(self):
        """Main listening loop for incoming messages."""
        buffer = ""

        while self.running and self.connected:
            try:
                data = self.socket.recv(4096).decode("utf-8", errors="ignore")
                if not data:
                    break

                buffer += data

                # Process complete lines
                while "\r\n" in buffer:
                    line, buffer = buffer.split("\r\n", 1)
                    if line:
                        self._handle_message(line)

            except socket.timeout:
                continue
            except Exception as e:
                logger.error(f"Error in chat listen loop: {e}")
                break

        self.connected = False
        if self.on_disconnect:
            self.on_disconnect()

    def _handle_message(self, raw_message: str):
        """Handle incoming IRC messages."""
        # Call raw message callback for debugging
        if self.on_raw_message:
            self.on_raw_message(raw_message)

        # Handle PING/PONG to stay connected
        if raw_message.startswith("PING"):
            pong_response = raw_message.replace("PING", "PONG")
            self.socket.send(f"{pong_response}\r\n".encode("utf-8"))
            return

        # Handle PRIVMSG (chat messages)
        if "PRIVMSG" in raw_message:
            message = ChatMessage(raw_message)
            if message.username and message.message:
                if self.on_message:
                    self.on_message(message)
            else:
                # Debug failed parsing
                logger.debug(f"Failed to parse chat message: {raw_message}")

        # Log other messages for debugging
        logger.debug(f"IRC: {raw_message}")

    def is_connected(self) -> bool:
        """Check if currently connected."""
        return self.connected

    def get_current_channel(self) -> Optional[str]:
        """Get the currently connected channel."""
        return self.current_channel
