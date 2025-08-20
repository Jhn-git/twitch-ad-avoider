"""
Twitch API client for Helix API integration
Handles stream status checking and authentication
"""
import os
import time
from typing import Dict, List, Optional, NamedTuple
from datetime import datetime, timezone
import requests

from .exceptions import TwitchAPIError
from .logging_config import get_logger

logger = get_logger(__name__)


class StreamInfo(NamedTuple):
    """Stream information data structure"""
    channel_name: str
    is_live: bool
    title: Optional[str] = None
    game_name: Optional[str] = None
    viewer_count: Optional[int] = None
    started_at: Optional[datetime] = None
    thumbnail_url: Optional[str] = None


class TwitchAPIClient:
    """Twitch Helix API client for stream status checking"""
    
    BASE_URL = "https://api.twitch.tv/helix"
    
    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None):
        """
        Initialize Twitch API client
        
        Args:
            client_id: Twitch application client ID
            client_secret: Twitch application client secret
        """
        # Try environment variables if not provided
        self.client_id = client_id or os.getenv('TWITCH_CLIENT_ID')
        self.client_secret = client_secret or os.getenv('TWITCH_CLIENT_SECRET')
        self.access_token: Optional[str] = None
        self.token_expires_at: Optional[float] = None
        self.session = requests.Session()
        self.rate_limit_remaining = 800
        self.rate_limit_reset = time.time()
        
        # Set default headers
        if self.client_id:
            self.session.headers.update({
                'Client-ID': self.client_id,
                'Content-Type': 'application/json'
            })
    
    def _get_app_access_token(self) -> str:
        """
        Get application access token for API requests
        
        Returns:
            Access token string
            
        Raises:
            TwitchAPIError: If token acquisition fails
        """
        if not self.client_id or not self.client_secret:
            raise TwitchAPIError("Client ID and Client Secret are required for API access")
        
        # Check if current token is still valid
        if (self.access_token and self.token_expires_at and 
            time.time() < self.token_expires_at - 300):  # 5 minute buffer
            return self.access_token
        
        logger.info("Requesting new Twitch API access token")
        
        url = "https://id.twitch.tv/oauth2/token"
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'client_credentials'
        }
        
        try:
            response = requests.post(url, data=data, timeout=10)
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data['access_token']
            expires_in = token_data.get('expires_in', 3600)
            self.token_expires_at = time.time() + expires_in
            
            # Update session headers
            self.session.headers.update({
                'Authorization': f'Bearer {self.access_token}'
            })
            
            logger.info("Successfully obtained Twitch API access token")
            return self.access_token
            
        except requests.RequestException as e:
            logger.error(f"Failed to get Twitch API access token: {e}")
            raise TwitchAPIError(f"Failed to authenticate with Twitch API: {e}")
    
    def _handle_rate_limit(self, response: requests.Response) -> None:
        """Handle rate limiting from API responses"""
        if 'Ratelimit-Remaining' in response.headers:
            self.rate_limit_remaining = int(response.headers['Ratelimit-Remaining'])
        if 'Ratelimit-Reset' in response.headers:
            self.rate_limit_reset = int(response.headers['Ratelimit-Reset'])
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """
        Make authenticated request to Twitch API
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
            
        Returns:
            JSON response data
            
        Raises:
            TwitchAPIError: If request fails
        """
        # Ensure we have a valid token
        self._get_app_access_token()
        
        # Check rate limits
        if self.rate_limit_remaining <= 1 and time.time() < self.rate_limit_reset:
            wait_time = self.rate_limit_reset - time.time()
            logger.warning(f"Rate limit reached, waiting {wait_time:.1f} seconds")
            time.sleep(wait_time + 1)
        
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        
        try:
            logger.debug(f"Making Twitch API request to {endpoint}")
            response = self.session.get(url, params=params, timeout=10)
            
            # Handle rate limiting
            self._handle_rate_limit(response)
            
            if response.status_code == 401:
                # Token might be expired, try to refresh
                logger.warning("API token expired, requesting new token")
                self.access_token = None
                self._get_app_access_token()
                response = self.session.get(url, params=params, timeout=10)
            
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            logger.error(f"Twitch API request failed: {e}")
            raise TwitchAPIError(f"API request failed: {e}")
    
    def get_user_id(self, username: str) -> Optional[str]:
        """
        Get user ID from username
        
        Args:
            username: Twitch username
            
        Returns:
            User ID or None if not found
        """
        try:
            response = self._make_request("users", {"login": username.lower()})
            users = response.get("data", [])
            if users:
                return users[0]["id"]
            return None
            
        except TwitchAPIError as e:
            logger.error(f"Failed to get user ID for {username}: {e}")
            return None
    
    def get_stream_info(self, channel_name: str) -> StreamInfo:
        """
        Get stream information for a single channel
        
        Args:
            channel_name: Twitch channel name
            
        Returns:
            StreamInfo object with stream data
        """
        try:
            # Get user ID first
            user_id = self.get_user_id(channel_name)
            if not user_id:
                logger.warning(f"User not found: {channel_name}")
                return StreamInfo(channel_name=channel_name, is_live=False)
            
            # Get stream data
            response = self._make_request("streams", {"user_id": user_id})
            streams = response.get("data", [])
            
            if not streams:
                # Stream is offline
                return StreamInfo(channel_name=channel_name, is_live=False)
            
            stream = streams[0]
            started_at = None
            if stream.get("started_at"):
                started_at = datetime.fromisoformat(
                    stream["started_at"].replace("Z", "+00:00")
                )
            
            return StreamInfo(
                channel_name=channel_name,
                is_live=True,
                title=stream.get("title"),
                game_name=stream.get("game_name"),
                viewer_count=stream.get("viewer_count"),
                started_at=started_at,
                thumbnail_url=stream.get("thumbnail_url")
            )
            
        except TwitchAPIError as e:
            logger.error(f"Failed to get stream info for {channel_name}: {e}")
            return StreamInfo(channel_name=channel_name, is_live=False)
    
    def get_multiple_stream_info(self, channel_names: List[str]) -> Dict[str, StreamInfo]:
        """
        Get stream information for multiple channels in a single request
        
        Args:
            channel_names: List of Twitch channel names
            
        Returns:
            Dictionary mapping channel names to StreamInfo objects
        """
        if not channel_names:
            return {}
        
        # Twitch API limit is 100 user logins per request
        chunk_size = 100
        all_results = {}
        
        for i in range(0, len(channel_names), chunk_size):
            chunk = channel_names[i:i + chunk_size]
            chunk_results = self._get_chunk_stream_info(chunk)
            all_results.update(chunk_results)
        
        return all_results
    
    def _get_chunk_stream_info(self, channel_names: List[str]) -> Dict[str, StreamInfo]:
        """Get stream info for a chunk of channels (max 100)"""
        try:
            # Convert channel names to lowercase for API
            login_params = [name.lower() for name in channel_names]
            
            # Get streams data
            response = self._make_request("streams", {"user_login": login_params})
            streams = response.get("data", [])
            
            # Create mapping of user_login to stream data
            live_streams = {stream["user_login"]: stream for stream in streams}
            
            # Build results for all requested channels
            results = {}
            for channel_name in channel_names:
                channel_lower = channel_name.lower()
                
                if channel_lower in live_streams:
                    stream = live_streams[channel_lower]
                    started_at = None
                    if stream.get("started_at"):
                        started_at = datetime.fromisoformat(
                            stream["started_at"].replace("Z", "+00:00")
                        )
                    
                    results[channel_name] = StreamInfo(
                        channel_name=channel_name,
                        is_live=True,
                        title=stream.get("title"),
                        game_name=stream.get("game_name"),
                        viewer_count=stream.get("viewer_count"),
                        started_at=started_at,
                        thumbnail_url=stream.get("thumbnail_url")
                    )
                else:
                    # Channel is offline
                    results[channel_name] = StreamInfo(
                        channel_name=channel_name,
                        is_live=False
                    )
            
            return results
            
        except TwitchAPIError as e:
            logger.error(f"Failed to get stream info for channels: {e}")
            # Return offline status for all channels on error
            return {
                name: StreamInfo(channel_name=name, is_live=False)
                for name in channel_names
            }
    
    def is_configured(self) -> bool:
        """Check if the API client is properly configured"""
        return bool(self.client_id and self.client_secret)