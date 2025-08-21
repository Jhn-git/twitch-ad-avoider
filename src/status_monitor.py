"""
Background status monitoring system for favorite channels
Uses streamlink to check stream status periodically
"""

import time
import threading
from typing import Dict, List, Callable, Optional
from datetime import datetime, timezone

from .streamlink_status import StreamlinkStatusChecker
from .exceptions import StreamlinkError
from .logging_config import get_logger

logger = get_logger(__name__)


class StatusMonitor:
    """Background monitor for checking stream status of favorite channels"""

    def __init__(
        self,
        status_checker: StreamlinkStatusChecker,
        favorites_manager,
        config_manager,
        status_callback: Optional[Callable] = None,
    ):
        """
        Initialize status monitor

        Args:
            status_checker: StreamlinkStatusChecker instance
            favorites_manager: FavoritesManager instance
            config_manager: ConfigManager instance
            status_callback: Optional callback function called when status updates
        """
        self.status_checker = status_checker
        self.favorites_manager = favorites_manager
        self.config = config_manager
        self.status_callback = status_callback

        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_check_time: Optional[datetime] = None
        self._is_running = False

        # Status cache to avoid unnecessary updates
        self._status_cache: Dict[str, bool] = {}
        self._cache_timestamp: Optional[datetime] = None

    def start_monitoring(self) -> None:
        """Start the background monitoring thread"""
        if self._is_running:
            logger.warning("Status monitoring is already running")
            return

        if not self.config.get("enable_status_monitoring", True):
            logger.info("Status monitoring is disabled in configuration")
            return

        if not self.status_checker.is_available():
            logger.warning("Streamlink is not available, status monitoring disabled")
            return

        logger.info("Starting stream status monitoring")
        self._stop_event.clear()
        self._is_running = True

        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, name="StatusMonitor", daemon=True
        )
        self._monitor_thread.start()

    def stop_monitoring(self) -> None:
        """Stop the background monitoring thread"""
        if not self._is_running:
            return

        logger.info("Stopping stream status monitoring")
        self._stop_event.set()
        self._is_running = False

        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5)

    def force_refresh(self) -> None:
        """Force an immediate status refresh"""
        if not self.status_checker.is_available():
            logger.warning("Streamlink not available, cannot refresh status")
            return

        logger.info("Forcing immediate status refresh")
        try:
            self._check_all_favorites()
        except Exception as e:
            logger.error(f"Error during forced refresh: {e}")

    def _monitor_loop(self) -> None:
        """Main monitoring loop running in background thread"""
        logger.info("Status monitoring loop started")

        while not self._stop_event.is_set():
            try:
                # Check if it's time for an update
                interval = self.config.get("status_check_interval", 300)  # 5 minutes default

                if (
                    self._last_check_time is None
                    or (datetime.now(timezone.utc) - self._last_check_time).total_seconds()
                    >= interval
                ):

                    self._check_all_favorites()
                    self._last_check_time = datetime.now(timezone.utc)

                # Sleep for a short interval to avoid busy waiting
                # Check every 30 seconds if it's time for an update
                self._stop_event.wait(timeout=30)

            except Exception as e:
                logger.error(f"Error in status monitoring loop: {e}")
                # Sleep a bit longer on error to avoid spam
                self._stop_event.wait(timeout=60)

        logger.info("Status monitoring loop stopped")

    def _check_all_favorites(self) -> None:
        """Check status for all favorite channels"""
        favorites = self.favorites_manager.get_favorites()
        if not favorites:
            logger.debug("No favorite channels to check")
            return

        logger.debug(f"Checking status for {len(favorites)} favorite channels")

        try:
            # Get status for all channels using streamlink
            status_results = self.status_checker.check_multiple_streams(favorites)

            # Update status for each channel
            updated_channels = []
            for channel_name, is_live in status_results.items():
                # Check if status actually changed before updating
                cached_status = self._status_cache.get(channel_name.lower())

                if cached_status is None or cached_status != is_live:
                    # Update favorites manager with new status (simplified)
                    self.favorites_manager.update_channel_status(
                        channel_name=channel_name, is_live=is_live
                    )

                    # Update cache
                    self._status_cache[channel_name.lower()] = is_live
                    updated_channels.append(channel_name)

                    logger.debug(
                        f"Status updated for {channel_name}: " f"{'LIVE' if is_live else 'OFFLINE'}"
                    )

            # Update cache timestamp
            self._cache_timestamp = datetime.now(timezone.utc)

            # Notify callback if any channels were updated
            if updated_channels and self.status_callback:
                try:
                    self.status_callback(updated_channels)
                except Exception as e:
                    logger.error(f"Error in status callback: {e}")

            logger.debug(f"Status check completed, {len(updated_channels)} channels updated")

        except StreamlinkError as e:
            logger.error(f"Streamlink error during status check: {e}")
            # Run network diagnostics if enabled and multiple failures occur
            if self.config.get("enable_network_diagnostics", True):
                logger.info("Running network diagnostics due to status check failures...")
                try:
                    diagnostics = self.status_checker.run_network_diagnostics()
                    failed_endpoints = [
                        url for url, (success, _) in diagnostics.items() if not success
                    ]
                    if failed_endpoints:
                        logger.warning(
                            f"Network issues detected with endpoints: {failed_endpoints}"
                        )
                except Exception as diag_e:
                    logger.error(f"Failed to run network diagnostics: {diag_e}")
        except Exception as e:
            logger.error(f"Unexpected error during status check: {e}")

    def get_cached_status(self, channel_name: str) -> Optional[bool]:
        """Get cached status for a channel"""
        cached_status = self._status_cache.get(channel_name.lower())

        # Check if cache is still valid
        cache_duration = self.config.get("status_cache_duration", 60)  # 1 minute default

        if (
            cached_status is not None
            and self._cache_timestamp
            and (datetime.now(timezone.utc) - self._cache_timestamp).total_seconds()
            < cache_duration
        ):
            return cached_status

        return None

    def is_monitoring(self) -> bool:
        """Check if monitoring is currently active"""
        return self._is_running

    def get_last_check_time(self) -> Optional[datetime]:
        """Get timestamp of last status check"""
        return self._last_check_time

    def add_channel_to_monitoring(self, channel_name: str) -> None:
        """Add a new channel to monitoring (when added to favorites)"""
        if not self._is_running:
            return

        logger.debug(f"Adding channel to monitoring: {channel_name}")

        # Get immediate status for the new channel
        try:
            is_live = self.status_checker.check_stream_status(channel_name)

            # Update favorites manager (simplified)
            self.favorites_manager.update_channel_status(channel_name=channel_name, is_live=is_live)

            # Update cache
            self._status_cache[channel_name.lower()] = is_live

            # Notify callback
            if self.status_callback:
                try:
                    self.status_callback([channel_name])
                except Exception as e:
                    logger.error(f"Error in status callback: {e}")

            logger.debug(
                f"Status fetched for new channel {channel_name}: "
                f"{'LIVE' if is_live else 'OFFLINE'}"
            )

        except StreamlinkError as e:
            logger.error(f"Failed to get status for new channel {channel_name}: {e}")

    def remove_channel_from_monitoring(self, channel_name: str) -> None:
        """Remove a channel from monitoring (when removed from favorites)"""
        channel_lower = channel_name.lower()
        if channel_lower in self._status_cache:
            del self._status_cache[channel_lower]
            logger.debug(f"Removed channel from monitoring: {channel_name}")
