"""
Streamlink-based status checker for Twitch streams
Simple live/offline detection using streamlink without API dependencies
"""
import time
import uuid
from typing import Dict, List, Optional
from datetime import datetime, timezone

import streamlink

from .exceptions import StreamlinkError
from .logging_config import get_logger

logger = get_logger(__name__)


class StreamlinkStatusChecker:
    """Simple status checker using streamlink for live/offline detection"""
    
    def __init__(self):
        """Initialize the streamlink status checker"""
        self.session = streamlink.Streamlink()
        logger.info("StreamlinkStatusChecker initialized")
    
    def check_stream_status(self, channel_name: str) -> bool:
        """
        Check if a single stream is live using streamlink
        
        Args:
            channel_name: Twitch channel name
            
        Returns:
            True if stream is live, False if offline or error
        """
        try:
            channel_name = channel_name.lower().strip()
            url = f"twitch.tv/{channel_name}"
            
            logger.debug(f"Checking stream status for {channel_name}")
            
            # Use streamlink to check if streams are available
            streams = self.session.streams(url)
            is_live = len(streams) > 0
            
            logger.debug(f"Stream {channel_name}: {'LIVE' if is_live else 'OFFLINE'}")
            return is_live
            
        except streamlink.StreamlinkError as e:
            logger.warning(f"Streamlink error checking {channel_name}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error checking {channel_name}: {e}")
            return False
    
    def check_multiple_streams(self, channel_names: List[str]) -> Dict[str, bool]:
        """
        Check status for multiple streams
        
        Args:
            channel_names: List of Twitch channel names
            
        Returns:
            Dictionary mapping channel names to live status (True/False)
        """
        if not channel_names:
            return {}
        
        logger.debug(f"Checking status for {len(channel_names)} channels")
        results = {}
        
        for channel_name in channel_names:
            results[channel_name] = self.check_stream_status(channel_name)
            
            # Small delay to avoid overwhelming streamlink
            time.sleep(0.1)
        
        live_count = sum(1 for is_live in results.values() if is_live)
        logger.info(f"Status check completed: {live_count}/{len(channel_names)} channels live")
        
        return results
    
    def is_available(self) -> bool:
        """
        Check if streamlink is available and working
        
        Returns:
            True if streamlink is functional, False otherwise
        """
        try:
            # Try to create a session and check a non-existent stream
            test_channel = f"twitch.tv/test_{uuid.uuid4().hex[:12]}"
            test_streams = self.session.streams(test_channel)
            # If we get here without exception, streamlink is working
            logger.debug("Streamlink availability check passed")
            return True
        except Exception as e:
            logger.error(f"Streamlink availability check failed: {e}")
            return False