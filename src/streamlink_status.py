"""
Streamlink-based status checker for Twitch streams
Simple live/offline detection using streamlink without API dependencies
"""

import time
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple, Callable, Any

import streamlink

try:
    import requests
except ImportError:
    requests = None

from .logging_config import get_logger
from .constants import ERROR_MESSAGES, NETWORK_TEST_ENDPOINTS

logger = get_logger(__name__)


class StreamlinkStatusChecker:
    """Simple status checker using streamlink for live/offline detection"""

    def __init__(
        self,
        config_manager: Optional[Any] = None,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> None:
        """
        Initialize the streamlink status checker

        Args:
            config_manager: Configuration manager instance
            progress_callback: Optional callback for progress updates (message, current, total)
        """
        self.config = config_manager
        self.progress_callback = progress_callback
        self.session = streamlink.Streamlink()

        # Configure session timeouts if config is available
        if self.config:
            timeout = self.config.get("network_timeout", 30)
            # Configure streamlink session options
            self.session.set_option("http-timeout", timeout)
            logger.debug(f"Streamlink configured with {timeout}s timeout (adaptive)")

        logger.info("StreamlinkStatusChecker initialized")

    def set_progress_callback(self, callback: Optional[Callable[[str, int, int], None]]) -> None:
        """Set or update the progress callback"""
        self.progress_callback = callback

    def get_error_statistics(self) -> Dict:
        """Get current error statistics and network condition"""
        # Simplified - no complex error tracking
        return {"total": 0, "by_type": {}, "consecutive": 0, "condition": "good"}

    def check_stream_status(self, channel_name: str) -> bool:
        """
        Check if a single stream is live using streamlink with retry logic

        Args:
            channel_name: Twitch channel name

        Returns:
            True if stream is live, False if offline or error
        """
        channel_name = channel_name.lower().strip()
        url = f"twitch.tv/{channel_name}"

        # Get retry configuration
        max_attempts = self.config.get("connection_retry_attempts", 3) if self.config else 3
        retry_delay = self.config.get("retry_delay", 5) if self.config else 5

        logger.debug(f"Checking stream status for {channel_name} (max {max_attempts} attempts)")

        for attempt in range(max_attempts):
            try:
                # Use streamlink to check if streams are available
                streams = self.session.streams(url)
                is_live = len(streams) > 0

                # Success - no error tracking needed

                logger.debug(f"Stream {channel_name}: {'LIVE' if is_live else 'OFFLINE'}")
                return is_live

            except streamlink.StreamlinkError as e:
                error_msg = str(e)

                # Simple error logging - no complex recovery tracking

                # Check if this is a timeout/network error that should be retried
                is_network_error = any(
                    keyword in error_msg.lower()
                    for keyword in ["timeout", "connection", "network", "unable to open"]
                )

                if is_network_error and attempt < max_attempts - 1:
                    logger.warning(
                        f"Network error checking {channel_name} "
                        f"(attempt {attempt + 1}/{max_attempts}): {error_msg}"
                    )
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    continue
                else:
                    # Final attempt or non-network error
                    if is_network_error:
                        logger.error(ERROR_MESSAGES["retry_exhausted"].format(url, max_attempts))
                    else:
                        logger.warning(f"Streamlink error checking {channel_name}: {error_msg}")
                    return False

            except Exception as e:
                # Simple error logging - no complex recovery tracking

                if attempt < max_attempts - 1:
                    logger.warning(
                        f"Unexpected error checking {channel_name} "
                        f"(attempt {attempt + 1}/{max_attempts}): {e}"
                    )
                    time.sleep(retry_delay)
                    continue
                else:
                    logger.error(
                        f"Unexpected error checking {channel_name} "
                        f"after {max_attempts} attempts: {e}"
                    )
                    return False

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

        total_channels = len(channel_names)
        logger.debug(f"Checking status for {total_channels} channels")
        results = {}

        for index, channel_name in enumerate(channel_names, 1):
            # Send progress update
            if self.progress_callback:
                self.progress_callback(f"Checking {channel_name}...", index, total_channels)

            results[channel_name] = self.check_stream_status(channel_name)

            # Small delay between requests to avoid overwhelming Twitch APIs
            time.sleep(0.5)

        live_count = sum(1 for is_live in results.values() if is_live)
        logger.info(f"Status check completed: {live_count}/{total_channels} channels live")

        # Send completion update
        if self.progress_callback:
            self.progress_callback(
                f"Completed: {live_count}/{total_channels} channels live",
                total_channels,
                total_channels,
            )

        return results

    def check_multiple_streams_cancellable(
        self, channel_names: List[str], cancel_event: threading.Event
    ) -> Dict[str, bool]:
        """
        Check status for multiple streams with cancellation support

        Args:
            channel_names: List of Twitch channel names
            cancel_event: Event to signal cancellation

        Returns:
            Dictionary mapping channel names to live status (True/False)
            May be incomplete if cancelled
        """
        if not channel_names:
            return {}

        total_channels = len(channel_names)
        logger.debug(f"Checking status for {total_channels} channels (cancellable)")
        results = {}

        for index, channel_name in enumerate(channel_names, 1):
            # Check for cancellation before each channel
            if cancel_event.is_set():
                logger.info(f"Status check cancelled after {index - 1}/{total_channels} channels")
                break

            # Send progress update
            if self.progress_callback:
                self.progress_callback(f"Checking {channel_name}...", index, total_channels)

            results[channel_name] = self.check_stream_status(channel_name)

            # Small delay between requests, but check for cancellation
            if not cancel_event.wait(timeout=0.5):
                # Continue if not cancelled during delay
                pass

        live_count = sum(1 for is_live in results.values() if is_live)
        completed_count = len(results)

        if cancel_event.is_set():
            logger.info(
                f"Status check cancelled: {completed_count}/{total_channels} channels checked"
            )
            if self.progress_callback:
                self.progress_callback(
                    f"Cancelled: {completed_count}/{total_channels} channels checked",
                    completed_count,
                    total_channels,
                )
        else:
            logger.info(f"Status check completed: {live_count}/{total_channels} channels live")
            if self.progress_callback:
                self.progress_callback(
                    f"Completed: {live_count}/{total_channels} channels live",
                    total_channels,
                    total_channels,
                )

        return results

    def check_multiple_streams_concurrent(
        self,
        channel_names: List[str],
        cancel_event: Optional[threading.Event] = None,
        max_workers: int = 3,
    ) -> Dict[str, bool]:
        """
        Check status for multiple streams concurrently with cancellation support

        Args:
            channel_names: List of Twitch channel names
            cancel_event: Optional event to signal cancellation
            max_workers: Maximum number of concurrent threads (default: 3)

        Returns:
            Dictionary mapping channel names to live status (True/False)
            May be incomplete if cancelled
        """
        if not channel_names:
            return {}

        total_channels = len(channel_names)
        logger.debug(
            f"Checking status for {total_channels} channels concurrently "
            f"(max_workers={max_workers})"
        )
        results = {}
        completed_count = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_channel = {
                executor.submit(self.check_stream_status, channel): channel
                for channel in channel_names
            }

            try:
                for future in as_completed(future_to_channel):
                    # Check for cancellation
                    if cancel_event and cancel_event.is_set():
                        logger.info(
                            f"Concurrent status check cancelled after "
                            f"{completed_count}/{total_channels} channels"
                        )
                        # Cancel remaining futures
                        for remaining_future in future_to_channel:
                            if not remaining_future.done():
                                remaining_future.cancel()
                        break

                    channel = future_to_channel[future]
                    completed_count += 1

                    try:
                        is_live = future.result()
                        results[channel] = is_live

                        # Send progress update
                        if self.progress_callback:
                            self.progress_callback(
                                f"Checked {channel}", completed_count, total_channels
                            )

                    except Exception as e:
                        logger.error(f"Error checking {channel}: {e}")
                        results[channel] = False

            except Exception as e:
                logger.error(f"Error in concurrent status checking: {e}")

        live_count = sum(1 for is_live in results.values() if is_live)
        completed_count = len(results)

        if cancel_event and cancel_event.is_set():
            logger.info(
                f"Concurrent status check cancelled: "
                f"{completed_count}/{total_channels} channels checked"
            )
            if self.progress_callback:
                self.progress_callback(
                    f"Cancelled: {completed_count}/{total_channels} channels checked",
                    completed_count,
                    total_channels,
                )
        else:
            logger.info(
                f"Concurrent status check completed: "
                f"{live_count}/{total_channels} channels live"
            )
            if self.progress_callback:
                self.progress_callback(
                    f"Completed: {live_count}/{total_channels} channels live",
                    total_channels,
                    total_channels,
                )

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
            self.session.streams(test_channel)
            # If we get here without exception, streamlink is working
            logger.debug("Streamlink availability check passed")
            return True
        except Exception as e:
            logger.error(f"Streamlink availability check failed: {e}")
            return False

    def run_network_diagnostics(self) -> Dict[str, Tuple[bool, str]]:
        """
        Run network connectivity diagnostics for Twitch endpoints

        Returns:
            Dictionary mapping endpoint URLs to (success, message) tuples
        """
        if not self.config or not self.config.get("enable_network_diagnostics", True):
            logger.info("Network diagnostics disabled in configuration")
            return {}

        if not requests:
            logger.warning("requests library not available for network diagnostics")
            return {}

        logger.info("Running network connectivity diagnostics...")
        results = {}
        timeout = self.config.get("network_timeout", 30) if self.config else 30

        for endpoint in NETWORK_TEST_ENDPOINTS:
            try:
                logger.debug(f"Testing connectivity to {endpoint}")
                start_time = time.time()

                response = requests.get(endpoint, timeout=timeout)
                elapsed = time.time() - start_time

                if response.status_code == 200:
                    results[endpoint] = (True, f"OK ({elapsed:.2f}s)")
                    logger.debug(f"✓ {endpoint}: {response.status_code} ({elapsed:.2f}s)")
                else:
                    results[endpoint] = (False, f"HTTP {response.status_code}")
                    logger.warning(f"✗ {endpoint}: HTTP {response.status_code}")

            except requests.exceptions.Timeout:
                results[endpoint] = (False, f"Timeout ({timeout}s)")
                logger.warning(f"✗ {endpoint}: Timeout after {timeout}s")

            except requests.exceptions.ConnectionError as e:
                results[endpoint] = (False, f"Connection failed: {str(e)[:50]}...")
                logger.warning(f"✗ {endpoint}: Connection failed - {e}")

            except Exception as e:
                results[endpoint] = (False, f"Error: {str(e)[:50]}...")
                logger.error(f"✗ {endpoint}: Unexpected error - {e}")

        # Summary
        successful = sum(1 for success, _ in results.values() if success)
        total = len(results)

        if successful == total:
            logger.info(f"Network diagnostics: All {total} endpoints reachable")
        else:
            logger.warning(f"Network diagnostics: {successful}/{total} endpoints reachable")

        return results
