"""
Lightweight status monitoring for favorite Twitch channels.

Checks live status via Twitch's GraphQL API using a single batched request
for all channels — much faster and more reliable than the previous per-channel
streamlink approach, which broke when Twitch started requiring OAuth for
stream-url lookups.
"""

import requests
from typing import Dict, List
from src.exceptions import ValidationError
from src.logging_config import get_logger
from src.validators import validate_channel_name

logger = get_logger(__name__)

_GQL_URL = "https://gql.twitch.tv/gql"
# Public client ID embedded in the Twitch website — used by streamlink and
# other open-source Twitch clients for anonymous GQL queries.
_CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"


class StatusMonitor:
    """Check Twitch channel live status via the Twitch GQL API."""

    def __init__(self, check_timeout: int = 10, max_workers: int = 3):
        self.check_timeout = check_timeout
        self.max_workers = max_workers
        logger.debug(f"StatusMonitor initialized (timeout={check_timeout}s)")

    def check_channels(self, channels: List[str]) -> Dict[str, bool]:
        """
        Check live status for all channels in a single batched GQL request.

        Args:
            channels: List of channel names to check

        Returns:
            Dictionary mapping channel names to live status (True/False)
        """
        if not channels:
            return {}

        valid_channels = []
        for channel in channels:
            try:
                valid_channels.append(validate_channel_name(channel))
            except ValidationError as e:
                logger.warning(f"Skipping invalid channel during status check: {channel!r}: {e}")

        if not valid_channels:
            return {ch: False for ch in channels}

        logger.info(f"Checking status for {len(valid_channels)} channels")

        try:
            results = self._batch_check(valid_channels)
            live_count = sum(results.values())
            logger.info(f"Status check complete: {live_count}/{len(valid_channels)} live")
            return results
        except Exception as e:
            logger.error(f"Status check failed: {e}")
            return {ch: False for ch in valid_channels}

    def _batch_check(self, channels: List[str]) -> Dict[str, bool]:
        """Single GQL request that checks all channels at once."""
        # Build a multi-alias query: ch0: user(login:"x"){stream{id}} ...
        aliases = [
            f'ch{i}: user(login: "{ch.lower()}") {{ stream {{ id }} }}'
            for i, ch in enumerate(channels)
        ]
        query = "{ " + " ".join(aliases) + " }"

        response = requests.post(
            _GQL_URL,
            json={"query": query},
            headers={"Client-ID": _CLIENT_ID},
            timeout=self.check_timeout,
        )
        response.raise_for_status()

        data = response.json().get("data") or {}
        results: Dict[str, bool] = {}
        for i, channel in enumerate(channels):
            user_node = data.get(f"ch{i}") or {}
            is_live = user_node.get("stream") is not None
            results[channel] = is_live
            logger.debug(f"{channel} -> {'LIVE' if is_live else 'offline'}")

        return results

    def update_timeout(self, timeout: int) -> None:
        self.check_timeout = timeout
        logger.debug(f"Updated check timeout to {timeout}s")

    def update_max_workers(self, workers: int) -> None:
        self.max_workers = workers
