#!/usr/bin/env python3
"""
Test script to verify the chat message sending fix.

This script can be used to test that messages only appear in local chat
after being confirmed by Twitch IRC servers.
"""

import sys
import time
import logging
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.twitch_chat_client import TwitchChatClient
from src.logging_config import get_logger

# Configure logging to see all debug messages
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('test_chat.log')
    ]
)

logger = get_logger(__name__)

def test_message_flow():
    """Test the message sending flow"""
    print("=" * 60)
    print("Chat Message Sending Fix Test")
    print("=" * 60)
    
    # Create chat client
    client = TwitchChatClient()
    
    # Test callbacks
    messages_received = []
    send_success_calls = []
    send_error_calls = []
    
    def on_message(msg):
        messages_received.append(f"{msg.username}: {msg.message}")
        print(f"[RECEIVED] {msg.username}: {msg.message}")
    
    def on_send_success(msg):
        send_success_calls.append(msg)
        print(f"[SUCCESS] Message confirmed: {msg}")
    
    def on_send_error(error):
        send_error_calls.append(error)
        print(f"[ERROR] Send failed: {error}")
    
    # Set callbacks
    client.on_message = on_message
    client.on_send_success = on_send_success
    client.on_send_error = on_send_error
    
    print(f"Authentication status: {client.get_authentication_status()}")
    print("\n1. Testing without authentication (should fail)...")
    
    # Test without authentication
    result = client.send_message("Test message without auth")
    print(f"Send without auth result: {result}")
    
    print("\n2. Testing connection to a channel...")
    
    # Connect to a test channel
    test_channel = "shroud"  # Use a popular channel for testing
    if client.connect(test_channel):
        print(f"Connected to #{test_channel}")
        
        # Listen for a few messages
        print("Listening for messages for 10 seconds...")
        time.sleep(10)
        
        print(f"Received {len(messages_received)} messages")
        
        # If you have OAuth credentials, you can test sending here
        print("\nTo test message sending, you need to:")
        print("1. Set up OAuth authentication")
        print("2. Call client.set_authentication(username, oauth_token)")
        print("3. Send a message and verify it only appears after IRC confirmation")
        
    else:
        print(f"Failed to connect to #{test_channel}")
    
    # Disconnect
    client.disconnect()
    print("\nDisconnected from chat")
    
    print(f"\nTest Summary:")
    print(f"- Messages received: {len(messages_received)}")
    print(f"- Success callbacks: {len(send_success_calls)}")
    print(f"- Error callbacks: {len(send_error_calls)}")
    
    print("\nKey changes implemented:")
    print("1. send_message() no longer calls on_send_success immediately")
    print("2. Success callback only triggered when Twitch echoes back the message")
    print("3. Enhanced logging tracks message sending vs confirmation")
    print("4. Timeout detection alerts if messages aren't confirmed")

if __name__ == "__main__":
    test_message_flow()