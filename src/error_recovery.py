"""
Error recovery and handling system for network operations.

This module provides intelligent error recovery strategies for network-related
operations, including adaptive timeout management and automatic retry strategies.
"""

from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, timezone, timedelta
from enum import Enum

from .logging_config import get_logger
from .exceptions import StreamlinkError

logger = get_logger(__name__)


class ErrorType(Enum):
    """Classification of different error types"""

    NETWORK_TIMEOUT = "network_timeout"
    CONNECTION_REFUSED = "connection_refused"
    DNS_RESOLUTION = "dns_resolution"
    SSL_ERROR = "ssl_error"
    HTTP_ERROR = "http_error"
    STREAMLINK_ERROR = "streamlink_error"
    UNKNOWN = "unknown"


class NetworkCondition(Enum):
    """Network condition assessment"""

    GOOD = "good"
    DEGRADED = "degraded"
    POOR = "poor"
    OFFLINE = "offline"


class ErrorRecoveryManager:
    """Manages error recovery strategies and network condition monitoring"""

    def __init__(self, config_manager: Optional[Any] = None) -> None:
        """
        Initialize the error recovery manager

        Args:
            config_manager: Configuration manager instance
        """
        self.config = config_manager
        self._error_history: List[Dict] = []
        self._network_condition = NetworkCondition.GOOD
        self._last_assessment = datetime.now(timezone.utc)
        self._adaptive_timeout = None
        self._consecutive_errors = 0

        # Recovery strategies
        self._recovery_callbacks: Dict[ErrorType, List[Callable]] = {}

    def record_error(
        self, error: Exception, operation: str, channel: Optional[str] = None
    ) -> ErrorType:
        """
        Record and classify an error for recovery analysis

        Args:
            error: The error that occurred
            operation: Description of the operation that failed
            channel: Optional channel name involved

        Returns:
            Classified error type
        """
        error_type = self._classify_error(error)
        error_record = {
            "timestamp": datetime.now(timezone.utc),
            "error_type": error_type,
            "operation": operation,
            "channel": channel,
            "error_message": str(error),
            "error_class": error.__class__.__name__,
        }

        self._error_history.append(error_record)
        self._consecutive_errors += 1

        # Keep only recent errors (last hour)
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=1)
        self._error_history = [
            record for record in self._error_history if record["timestamp"] > cutoff_time
        ]

        logger.warning(f"Error recorded: {error_type.value} in {operation} - {str(error)}")

        # Assess network condition
        self._assess_network_condition()

        # Trigger recovery if threshold exceeded
        if self._should_trigger_recovery():
            self._trigger_recovery_strategy(error_type)

        return error_type

    def record_success(self, operation: str, channel: Optional[str] = None) -> None:
        """
        Record a successful operation to reset error counters

        Args:
            operation: Description of the successful operation
            channel: Optional channel name involved
        """
        if self._consecutive_errors > 0:
            logger.info(f"Recovery successful after {self._consecutive_errors} errors")
            self._consecutive_errors = 0

        # Gradually improve network condition assessment on success
        if self._network_condition != NetworkCondition.GOOD:
            self._assess_network_condition()

    def get_adaptive_timeout(self, base_timeout: int = 30) -> int:
        """
        Get adaptive timeout based on network conditions

        Args:
            base_timeout: Base timeout value

        Returns:
            Adjusted timeout value
        """
        if not self.config or not self.config.get("enable_adaptive_timeouts", True):
            return base_timeout

        if self._adaptive_timeout is not None:
            return self._adaptive_timeout

        # Adjust timeout based on network condition
        multipliers = {
            NetworkCondition.GOOD: 1.0,
            NetworkCondition.DEGRADED: 1.5,
            NetworkCondition.POOR: 2.0,
            NetworkCondition.OFFLINE: 3.0,
        }

        adjusted_timeout = int(base_timeout * multipliers[self._network_condition])
        return max(10, min(adjusted_timeout, 120))  # Keep within reasonable bounds

    def get_network_condition(self) -> NetworkCondition:
        """Get current network condition assessment"""
        return self._network_condition

    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics for the last hour"""
        total_errors = len(self._error_history)
        if total_errors == 0:
            return {
                "total": 0,
                "by_type": {},
                "consecutive": 0,
                "condition": self._network_condition.value,
            }

        error_counts: Dict[str, int] = {}
        for record in self._error_history:
            error_type = record["error_type"].value
            error_counts[error_type] = error_counts.get(error_type, 0) + 1

        return {
            "total": total_errors,
            "by_type": error_counts,
            "consecutive": self._consecutive_errors,
            "condition": self._network_condition.value,
        }

    def register_recovery_callback(self, error_type: ErrorType, callback: Callable) -> None:
        """Register a callback for specific error type recovery"""
        if error_type not in self._recovery_callbacks:
            self._recovery_callbacks[error_type] = []
        self._recovery_callbacks[error_type].append(callback)

    def _classify_error(self, error: Exception) -> ErrorType:
        """Classify an error into a specific error type"""
        error_message = str(error).lower()
        error_class = error.__class__.__name__.lower()

        # Timeout errors
        if "timeout" in error_message or "timed out" in error_message:
            return ErrorType.NETWORK_TIMEOUT

        # Connection errors
        if any(
            keyword in error_message
            for keyword in ["connection refused", "connection reset", "connection failed"]
        ):
            return ErrorType.CONNECTION_REFUSED

        # DNS errors
        if any(
            keyword in error_message for keyword in ["name resolution", "dns", "host not found"]
        ):
            return ErrorType.DNS_RESOLUTION

        # SSL errors
        if any(keyword in error_message for keyword in ["ssl", "certificate", "handshake"]):
            return ErrorType.SSL_ERROR

        # HTTP errors
        if any(keyword in error_message for keyword in ["http", "404", "500", "502", "503"]):
            return ErrorType.HTTP_ERROR

        # Streamlink specific errors
        if isinstance(error, StreamlinkError) or "streamlink" in error_class:
            return ErrorType.STREAMLINK_ERROR

        return ErrorType.UNKNOWN

    def _assess_network_condition(self) -> None:
        """Assess current network condition based on error history"""
        now = datetime.now(timezone.utc)

        # Don't assess too frequently
        if (now - self._last_assessment).total_seconds() < 30:
            return

        self._last_assessment = now

        # Look at errors in the last 5 minutes
        recent_cutoff = now - timedelta(minutes=5)
        recent_errors = [
            record for record in self._error_history if record["timestamp"] > recent_cutoff
        ]

        recent_count = len(recent_errors)

        # Classify network condition
        if recent_count == 0:
            if self._consecutive_errors == 0:
                self._network_condition = NetworkCondition.GOOD
        elif recent_count <= 2:
            self._network_condition = NetworkCondition.DEGRADED
        elif recent_count <= 5:
            self._network_condition = NetworkCondition.POOR
        else:
            self._network_condition = NetworkCondition.OFFLINE

        logger.debug(f"Network condition assessed as: {self._network_condition.value}")

    def _should_trigger_recovery(self) -> bool:
        """Determine if recovery strategies should be triggered"""
        if not self.config or not self.config.get("enable_error_recovery", True):
            return False

        threshold = self.config.get("network_error_threshold", 3)
        return self._consecutive_errors >= threshold

    def _trigger_recovery_strategy(self, error_type: ErrorType) -> None:
        """Trigger appropriate recovery strategy for error type"""
        logger.info(f"Triggering recovery strategy for {error_type.value}")

        # Execute registered callbacks
        if error_type in self._recovery_callbacks:
            for callback in self._recovery_callbacks[error_type]:
                try:
                    callback()
                except Exception as e:
                    logger.error(f"Recovery callback failed: {e}")

        # Built-in recovery strategies
        if error_type == ErrorType.NETWORK_TIMEOUT:
            self._adaptive_timeout = min(self.get_adaptive_timeout() + 15, 120)
            logger.info(f"Increased adaptive timeout to {self._adaptive_timeout}s")

        elif error_type == ErrorType.CONNECTION_REFUSED:
            # Suggest checking firewall/network
            logger.warning("Connection refused - check firewall and network connectivity")

        elif error_type == ErrorType.DNS_RESOLUTION:
            # Suggest checking DNS settings
            logger.warning("DNS resolution failed - check DNS settings")
