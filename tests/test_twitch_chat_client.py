"""
Tests for TwitchChatClient IRC functionality.

Critical tests for:
- IRC connection (anonymous and authenticated)
- Message sending and receiving
- Message parsing and validation
- PING/PONG handling
- USERSTATE confirmation
"""

import unittest
import socket
import time
from unittest.mock import Mock, MagicMock, patch

from src.twitch_chat_client import TwitchChatClient, ChatMessage


class TestChatMessage(unittest.TestCase):
    """Test ChatMessage parsing"""

    def test_parse_simple_privmsg(self):
        """Test parsing basic PRIVMSG"""
        raw = ":testuser!testuser@testuser.tmi.twitch.tv PRIVMSG #testchannel :Hello World"
        msg = ChatMessage(raw)

        self.assertEqual(msg.username, "testuser")
        self.assertEqual(msg.message, "Hello World")
        self.assertIsInstance(msg.timestamp, float)

    def test_parse_privmsg_with_tags(self):
        """Test parsing PRIVMSG with IRC tags"""
        raw = (
            "@badge-info=;badges=;color=#FF0000;display-name=TestUser;id=abc-123 "
            ":testuser!testuser@testuser.tmi.twitch.tv PRIVMSG #testchannel :Test message"
        )
        msg = ChatMessage(raw)

        self.assertEqual(msg.username, "testuser")
        self.assertEqual(msg.message, "Test message")
        self.assertIn("color", msg.tags)
        self.assertEqual(msg.tags["color"], "#FF0000")
        self.assertEqual(msg.tags["display-name"], "TestUser")

    def test_parse_privmsg_underscores_numbers(self):
        """Test parsing usernames and channels with underscores/numbers"""
        raw = (
            ":test_user_123!test_user_123@test_user_123.tmi.twitch.tv "
            "PRIVMSG #channel_name_456 :Hello"
        )
        msg = ChatMessage(raw)

        self.assertEqual(msg.username, "test_user_123")
        self.assertEqual(msg.message, "Hello")

    def test_parse_empty_message(self):
        """Test parsing message with empty content"""
        raw = ":tmi.twitch.tv 001 testuser :Welcome"
        msg = ChatMessage(raw)

        self.assertEqual(msg.username, "")
        self.assertEqual(msg.message, "")

    def test_parse_message_with_colon(self):
        """Test parsing message containing colons"""
        raw = ":testuser!testuser@testuser.tmi.twitch.tv PRIVMSG #channel :Message with: colons"
        msg = ChatMessage(raw)

        self.assertEqual(msg.username, "testuser")
        self.assertEqual(msg.message, "Message with: colons")


class TestTwitchChatClient(unittest.TestCase):
    """Test TwitchChatClient functionality"""

    def setUp(self):
        """Set up test client"""
        self.client = TwitchChatClient()

    def tearDown(self):
        """Clean up connections"""
        if self.client.connected:
            self.client.disconnect()

    def test_initialization(self):
        """Test client initializes correctly"""
        self.assertFalse(self.client.connected)
        self.assertFalse(self.client.running)
        self.assertIsNone(self.client.current_channel)
        self.assertFalse(self.client.is_authenticated)
        self.assertIsNone(self.client.username)
        self.assertEqual(self.client.pending_messages, [])

    def test_set_authentication(self):
        """Test setting authentication credentials"""
        self.client.set_authentication("test_user", "oauth_token_123")

        self.assertTrue(self.client.is_authenticated)
        self.assertEqual(self.client.username, "test_user")
        self.assertEqual(self.client.oauth_token, "oauth_token_123")

    def test_can_send_messages_not_authenticated(self):
        """Test can_send_messages returns False when not authenticated"""
        self.assertFalse(self.client.can_send_messages())

    def test_can_send_messages_authenticated_not_connected(self):
        """Test can_send_messages returns False when authenticated but not connected"""
        self.client.set_authentication("test_user", "oauth_token")
        self.assertFalse(self.client.can_send_messages())

    def test_can_send_messages_authenticated_and_connected(self):
        """Test can_send_messages returns True when authenticated and connected"""
        self.client.set_authentication("test_user", "oauth_token")
        self.client.connected = True
        self.assertTrue(self.client.can_send_messages())

    @patch("socket.socket")
    def test_connect_anonymous(self, mock_socket_class):
        """Test anonymous connection to IRC"""
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        # Mock callbacks
        on_connect = Mock()
        self.client.on_connect = on_connect

        result = self.client.connect("testchannel")

        self.assertTrue(result)
        self.assertTrue(self.client.connected)
        self.assertEqual(self.client.current_channel, "#testchannel")

        # Verify IRC handshake
        calls = mock_socket.send.call_args_list
        self.assertGreaterEqual(len(calls), 3)

        # Check for anonymous PASS
        pass_call = calls[0][0][0].decode("utf-8")
        self.assertIn("PASS SCHMOOPIIE", pass_call)

        # Check for NICK
        nick_call = calls[1][0][0].decode("utf-8")
        self.assertIn("NICK", nick_call)

        # Check for JOIN
        join_found = False
        for call_args in calls:
            decoded = call_args[0][0].decode("utf-8")
            if "JOIN #testchannel" in decoded:
                join_found = True
                break
        self.assertTrue(join_found)

        # Verify callback was called
        on_connect.assert_called_once()

    @patch("socket.socket")
    def test_connect_authenticated(self, mock_socket_class):
        """Test authenticated connection to IRC"""
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        # Set authentication
        self.client.set_authentication("test_user", "oauth_token_123")

        result = self.client.connect("testchannel")

        self.assertTrue(result)
        self.assertTrue(self.client.connected)

        # Verify OAuth PASS was sent
        calls = mock_socket.send.call_args_list
        pass_call = calls[0][0][0].decode("utf-8")
        self.assertIn("PASS oauth:oauth_token_123", pass_call)

    @patch("socket.socket")
    def test_connect_with_hash_prefix(self, mock_socket_class):
        """Test connecting with # prefix on channel name"""
        mock_socket = MagicMock()
        mock_socket_class.return_value = mock_socket

        result = self.client.connect("#testchannel")

        self.assertTrue(result)
        self.assertEqual(self.client.current_channel, "#testchannel")

    @patch("socket.socket")
    def test_connect_failure(self, mock_socket_class):
        """Test connection failure handling"""
        mock_socket = MagicMock()
        mock_socket.connect.side_effect = socket.error("Connection refused")
        mock_socket_class.return_value = mock_socket

        result = self.client.connect("testchannel")

        self.assertFalse(result)
        self.assertFalse(self.client.connected)

    def test_disconnect(self):
        """Test disconnection"""
        # Setup connected state
        mock_socket = MagicMock()
        self.client.socket = mock_socket
        self.client.connected = True
        self.client.running = True

        # Mock callback
        on_disconnect = Mock()
        self.client.on_disconnect = on_disconnect

        self.client.disconnect()

        self.assertFalse(self.client.connected)
        self.assertFalse(self.client.running)
        self.assertIsNone(self.client.socket)

        # Verify socket was closed
        mock_socket.shutdown.assert_called_once()
        mock_socket.close.assert_called_once()

        # Verify callback
        on_disconnect.assert_called_once()

    def test_is_connected(self):
        """Test is_connected method"""
        self.assertFalse(self.client.is_connected())

        self.client.connected = True
        self.assertTrue(self.client.is_connected())

    def test_get_current_channel(self):
        """Test get_current_channel method"""
        self.assertIsNone(self.client.get_current_channel())

        self.client.current_channel = "#testchannel"
        self.assertEqual(self.client.get_current_channel(), "#testchannel")

    def test_handle_ping_pong(self):
        """Test PING/PONG handling"""
        mock_socket = MagicMock()
        self.client.socket = mock_socket

        self.client._handle_message("PING :tmi.twitch.tv")

        # Verify PONG was sent
        mock_socket.send.assert_called_once()
        pong_msg = mock_socket.send.call_args[0][0].decode("utf-8")
        self.assertIn("PONG :tmi.twitch.tv", pong_msg)

    def test_handle_privmsg(self):
        """Test PRIVMSG handling"""
        on_message = Mock()
        self.client.on_message = on_message

        raw_msg = ":testuser!testuser@testuser.tmi.twitch.tv PRIVMSG #channel :Hello World"
        self.client._handle_message(raw_msg)

        # Verify callback was called
        on_message.assert_called_once()
        chat_msg = on_message.call_args[0][0]
        self.assertIsInstance(chat_msg, ChatMessage)
        self.assertEqual(chat_msg.username, "testuser")
        self.assertEqual(chat_msg.message, "Hello World")

    def test_handle_own_privmsg_authenticated(self):
        """Test that own PRIVMSG is ignored when authenticated"""
        self.client.set_authentication("test_user", "oauth_token")
        self.client.username = "test_user"

        on_message = Mock()
        self.client.on_message = on_message

        # Our own message
        raw_msg = ":test_user!test_user@test_user.tmi.twitch.tv PRIVMSG #channel :My message"
        self.client._handle_message(raw_msg)

        # Callback should NOT be called for our own messages
        on_message.assert_not_called()

    def test_handle_userstate_confirmation(self):
        """Test USERSTATE message confirmation"""
        self.client.set_authentication("test_user", "oauth_token")
        self.client.pending_messages.append(
            {"message": "Test message", "timestamp": time.time(), "confirmed": False}
        )

        on_send_success = Mock()
        self.client.on_send_success = on_send_success

        # Simulate USERSTATE message
        userstate_msg = "@badge-info=;badges=;color=#FF0000 :tmi.twitch.tv USERSTATE #channel"
        self.client._handle_message(userstate_msg)

        # Verify message was confirmed
        self.assertTrue(self.client.pending_messages[0]["confirmed"])
        on_send_success.assert_called_once_with("Test message")

    def test_send_message_not_authenticated(self):
        """Test send_message fails when not authenticated"""
        on_send_error = Mock()
        self.client.on_send_error = on_send_error

        result = self.client.send_message("Hello")

        self.assertFalse(result)
        on_send_error.assert_called_once()
        self.assertIn("not authenticated", on_send_error.call_args[0][0])

    def test_send_message_no_channel(self):
        """Test send_message fails when no channel joined"""
        self.client.set_authentication("test_user", "oauth_token")
        self.client.connected = True

        on_send_error = Mock()
        self.client.on_send_error = on_send_error

        result = self.client.send_message("Hello")

        self.assertFalse(result)
        on_send_error.assert_called_once()
        self.assertIn("no channel", on_send_error.call_args[0][0])

    def test_send_message_empty(self):
        """Test send_message fails with empty message"""
        self.client.set_authentication("test_user", "oauth_token")
        self.client.connected = True
        self.client.current_channel = "#testchannel"

        on_send_error = Mock()
        self.client.on_send_error = on_send_error

        result = self.client.send_message("")

        self.assertFalse(result)
        on_send_error.assert_called_once()
        self.assertIn("empty", on_send_error.call_args[0][0].lower())

    def test_send_message_too_long(self):
        """Test send_message fails with too long message (>500 chars)"""
        self.client.set_authentication("test_user", "oauth_token")
        self.client.connected = True
        self.client.current_channel = "#testchannel"

        on_send_error = Mock()
        self.client.on_send_error = on_send_error

        # 501 character message
        long_message = "a" * 501

        result = self.client.send_message(long_message)

        self.assertFalse(result)
        on_send_error.assert_called_once()
        self.assertIn("too long", on_send_error.call_args[0][0].lower())

    def test_send_message_success(self):
        """Test successful message sending"""
        mock_socket = MagicMock()
        self.client.socket = mock_socket
        self.client.set_authentication("test_user", "oauth_token")
        self.client.connected = True
        self.client.current_channel = "#testchannel"

        result = self.client.send_message("Hello World")

        self.assertTrue(result)

        # Verify PRIVMSG was sent
        mock_socket.send.assert_called_once()
        privmsg = mock_socket.send.call_args[0][0].decode("utf-8")
        self.assertIn("PRIVMSG #testchannel :Hello World", privmsg)

        # Verify message added to pending list
        self.assertEqual(len(self.client.pending_messages), 1)
        self.assertEqual(self.client.pending_messages[0]["message"], "Hello World")
        self.assertFalse(self.client.pending_messages[0]["confirmed"])

    def test_send_message_pending_list_limit(self):
        """Test pending messages list is limited to 10"""
        mock_socket = MagicMock()
        self.client.socket = mock_socket
        self.client.set_authentication("test_user", "oauth_token")
        self.client.connected = True
        self.client.current_channel = "#testchannel"

        # Send 15 messages
        for i in range(15):
            self.client.send_message(f"Message {i}")

        # Should only keep last 10
        self.assertEqual(len(self.client.pending_messages), 10)
        self.assertEqual(self.client.pending_messages[0]["message"], "Message 5")
        self.assertEqual(self.client.pending_messages[-1]["message"], "Message 14")

    def test_get_authentication_status(self):
        """Test get_authentication_status method"""
        status = self.client.get_authentication_status()

        self.assertFalse(status["authenticated"])
        self.assertIsNone(status["username"])
        self.assertFalse(status["can_send_messages"])
        self.assertFalse(status["connected"])
        self.assertIsNone(status["current_channel"])

        # Set authenticated and connected
        self.client.set_authentication("test_user", "oauth_token")
        self.client.connected = True
        self.client.current_channel = "#testchannel"

        status = self.client.get_authentication_status()

        self.assertTrue(status["authenticated"])
        self.assertEqual(status["username"], "test_user")
        self.assertTrue(status["can_send_messages"])
        self.assertTrue(status["connected"])
        self.assertEqual(status["current_channel"], "#testchannel")

    def test_raw_message_callback(self):
        """Test raw message callback is called"""
        on_raw_message = Mock()
        self.client.on_raw_message = on_raw_message

        raw_msg = ":tmi.twitch.tv 001 testuser :Welcome"
        self.client._handle_message(raw_msg)

        on_raw_message.assert_called_once_with(raw_msg)


if __name__ == "__main__":
    unittest.main()
