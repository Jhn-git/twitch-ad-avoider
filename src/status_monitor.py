"""
Lightweight status monitoring for favorite Twitch channels.

This module provides efficient, non-blocking status checks for favorite channels
using streamlink with strict performance constraints.

The StatusMonitor class:
    - Uses streamlink --stream-url for quick checks (no download)
    - Runs concurrent checks with limited workers (max 3)
    - Enforces per-channel timeouts (default 5s)
    - Handles errors gracefully without crashing
    - Returns results as dict: {channel: is_live}

Performance guarantees:
    - Non-blocking: Runs in background thread pool
    - Timeout enforcement: Each channel check limited to configurable timeout
    - Limited concurrency: Max 3 workers to avoid system overload
    - Graceful degradation: Failed checks return False, don't crash
"""

import subprocess
import concurrent.futures
from typing import Dict, List
from src.logging_config import get_logger

logger = get_logger(__name__)


class StatusMonitor:
    """
    Lightweight monitor for checking Twitch channel live status.

    Uses streamlink to quickly test if channels are live without downloading
    stream data. Designed for minimal system impact with strict timeouts and
    limited concurrency.
    """

    def __init__(self, check_timeout: int = 5, max_workers: int = 3):
        """
        Initialize the status monitor.

        Args:
            check_timeout: Timeout in seconds for each channel check (default: 5)
            max_workers: Maximum concurrent workers (default: 3)
        """
        self.check_timeout = check_timeout
        self.max_workers = max_workers
        logger.debug(f"StatusMonitor initialized (timeout={check_timeout}s, workers={max_workers})")

    def check_channels(self, channels: List[str]) -> Dict[str, bool]:
        """
        Check live status for multiple channels concurrently.

        This method runs streamlink checks in parallel with controlled
        concurrency to avoid overwhelming the system or network.

        Args:
            channels: List of channel names to check

        Returns:
            Dictionary mapping channel names to live status (True/False)
        """
        if not channels:
            logger.debug("No channels to check")
            return {}

        logger.info(f"Checking status for {len(channels)} channels")
        results = {}

        # Use ThreadPoolExecutor for concurrent checks
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all checks
            future_to_channel = {
                executor.submit(self._check_single_channel, channel): channel
                for channel in channels
            }

            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_channel):
                channel = future_to_channel[future]
                try:
                    is_live = future.result()
                    results[channel] = is_live
                    logger.debug(f"Status check complete: {channel} -> {is_live}")
                except Exception as e:
                    # Failed check defaults to offline
                    logger.warning(f"Failed to check {channel}: {e}")
                    results[channel] = False

        logger.info(f"Status check complete: {sum(results.values())}/{len(results)} live")
        return results

    def _check_single_channel(self, channel: str) -> bool:
        """
        Check if a single channel is live using streamlink.

        Uses `streamlink --stream-url` to quickly test if a stream is available
        without downloading any data. Enforces timeout to prevent hanging.

        Args:
            channel: Channel name to check

        Returns:
            True if channel is live, False otherwise
        """
        try:
            # Build streamlink command for quick URL test
            # --stream-url returns stream URL without downloading
            # This is much faster than actually opening the stream
            url = f"https://twitch.tv/{channel}"
            command = [
                "streamlink",
                "--stream-url",
                url,
                "best",
            ]

            logger.debug(f"Running streamlink check for {channel}")

            # Run with timeout
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.check_timeout,
                check=False,  # Don't raise on non-zero exit
            )

            # streamlink returns exit code 0 and outputs URL if stream is available
            # Returns non-zero exit code if stream is offline or unavailable
            if result.returncode == 0 and result.stdout.strip():
                logger.debug(f"Channel {channel} is LIVE")
                return True
            else:
                logger.debug(f"Channel {channel} is OFFLINE")
                return False

        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout checking {channel} (>{self.check_timeout}s)")
            return False
        except FileNotFoundError:
            logger.error("streamlink not found in PATH")
            return False
        except Exception as e:
            logger.warning(f"Error checking {channel}: {e}")
            return False

    def update_timeout(self, timeout: int) -> None:
        """
        Update the per-channel check timeout.

        Args:
            timeout: New timeout in seconds
        """
        self.check_timeout = timeout
        logger.debug(f"Updated check timeout to {timeout}s")

    def update_max_workers(self, workers: int) -> None:
        """
        Update the maximum number of concurrent workers.

        Args:
            workers: New maximum number of workers
        """
        self.max_workers = workers
        logger.debug(f"Updated max workers to {workers}")
