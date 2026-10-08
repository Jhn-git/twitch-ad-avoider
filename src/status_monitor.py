"""
Lightweight status monitoring for favorite Twitch channels.

Checks live status via Twitch's GraphQL API using a single batched request
for all channels — much faster and more reliable than the previous per-channel
streamlink approach, which broke when Twitch started requiring OAuth for
stream-url lookups.
"""

import time
import requests
from typing import Dict, List, Optional
from src.constants import TWITCH_GQL_URL, TWITCH_GQL_CLIENT_ID
from src.exceptions import ValidationError
from src.logging_config import get_logger
from src.validators import validate_channel_name

logger = get_logger(__name__)

# Transient failures (DNS drop after sleep/wake, Twitch 5xx blips) are common
# enough that a single failed request shouldn't fail a whole refresh interval.
MAX_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = (0.5, 1.5)

ERROR_OFFLINE = "offline"
ERROR_TIMEOUT = "timeout"
ERROR_SERVER = "server"
ERROR_OTHER = "other"


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, (requests.ConnectionError, requests.Timeout)):
        return True
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        status = exc.response.status_code
        return status >= 500 or status == 429
    return False


def _classify_error(exc: Exception) -> str:
    # Timeout is checked first: ConnectTimeout subclasses both Timeout and ConnectionError.
    if isinstance(exc, requests.Timeout):
        return ERROR_TIMEOUT
    if isinstance(exc, requests.ConnectionError):
        return ERROR_OFFLINE
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        if exc.response.status_code >= 500 or exc.response.status_code == 429:
            return ERROR_SERVER
    return ERROR_OTHER


class StatusMonitor:
    """Check Twitch channel live status via the Twitch GQL API."""

    def __init__(self, check_timeout: int = 10):
        self.check_timeout = check_timeout
        # Why the most recent check failed (one of the ERROR_* kinds), or None
        # if it succeeded. Lets callers show an accurate message.
        self.last_error_kind: Optional[str] = None
        logger.debug(f"StatusMonitor initialized (timeout={check_timeout}s)")

    def check_channels(self, channels: List[str]) -> Dict[str, bool]:
        """
        Check live status for all channels in a single batched GQL request.

        Args:
            channels: List of channel names to check

        Returns:
            Dictionary mapping channel names to live status (True/False).
            Empty dict means the check itself failed (e.g. network error) —
            callers should treat this as "unknown", not "all offline", and
            leave any previously known status untouched. ``last_error_kind``
            says why.
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
            results = self._batch_check_with_retry(valid_channels)
        except Exception as e:
            self.last_error_kind = _classify_error(e)
            logger.error(f"Status check failed ({self.last_error_kind}): {e}")
            return {}

        self.last_error_kind = None
        live_count = sum(results.values())
        logger.info(f"Status check complete: {live_count}/{len(valid_channels)} live")
        return results

    def _batch_check_with_retry(self, channels: List[str]) -> Dict[str, bool]:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                return self._batch_check(channels)
            except Exception as e:
                if attempt == MAX_ATTEMPTS or not _is_retryable(e):
                    raise
                delay = RETRY_BACKOFF_SECONDS[min(attempt - 1, len(RETRY_BACKOFF_SECONDS) - 1)]
                logger.warning(
                    f"Status check attempt {attempt}/{MAX_ATTEMPTS} failed "
                    f"({_classify_error(e)}), retrying in {delay}s"
                )
                time.sleep(delay)
        raise RuntimeError("unreachable")  # pragma: no cover

    def _batch_check(self, channels: List[str]) -> Dict[str, bool]:
        """Single GQL request that checks all channels at once."""
        # Build a multi-alias query: ch0: user(login:"x"){stream{id}} ...
        aliases = [
            f'ch{i}: user(login: "{ch.lower()}") {{ stream {{ id }} }}'
            for i, ch in enumerate(channels)
        ]
        query = "{ " + " ".join(aliases) + " }"

        response = requests.post(
            TWITCH_GQL_URL,
            json={"query": query},
            headers={"Client-ID": TWITCH_GQL_CLIENT_ID},
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
