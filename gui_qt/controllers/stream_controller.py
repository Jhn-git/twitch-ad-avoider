"""
Stream controller for TwitchAdAvoider Qt GUI.

This module manages stream lifecycle using QThread for background
operations and signal-based communication.

The StreamController handles:
    - Stream process launching and management
    - Background thread operations
    - Signal-based status updates

Key Features:
    - QThread-based background operations
    - Signal/slot communication
    - Process lifecycle management
    - Error handling and reporting
"""

from PySide6.QtCore import QObject, Signal, QThread
import subprocess
from typing import Optional

from src.twitch_viewer import TwitchViewer
from src.config_manager import ConfigManager
from src.logging_config import get_logger

logger = get_logger(__name__)


class ClipWorker(QObject):
    """Runs create_clip() in a background thread."""

    finished = Signal(str)   # output path
    failed = Signal(str)     # error message

    def __init__(self, twitch_viewer: "TwitchViewer"):
        super().__init__()
        self.twitch_viewer = twitch_viewer

    def run(self) -> None:
        result = self.twitch_viewer.create_clip()
        if result:
            self.finished.emit(result)
        else:
            self.failed.emit("Failed to create clip — check FFmpeg is installed and stream is active")


class StreamWorker(QObject):
    """
    Worker object for running stream processes in background thread.

    Signals:
        started(): Emitted when stream starts
        finished(): Emitted when stream finishes normally
        error(str): Emitted when an error occurs
    """

    # Signals
    started = Signal()
    finished = Signal()
    error = Signal(str)  # error message

    def __init__(self, twitch_viewer: TwitchViewer, channel: str, quality: str):
        """
        Initialize the StreamWorker.

        Args:
            twitch_viewer: TwitchViewer instance
            channel: Channel name to watch
            quality: Quality to request
        """
        super().__init__()

        self.twitch_viewer = twitch_viewer
        self.channel = channel
        self.quality = quality
        self.process: Optional[subprocess.Popen] = None
        self.should_stop = False

    def run(self) -> None:
        """Run the stream process (executed in background thread)."""
        logger.info("[DEBUG] StreamWorker.run() ENTERED")
        try:
            logger.info(f"Starting stream: {self.channel} @ {self.quality}")
            logger.info(f"[DEBUG] About to call watch_stream for {self.channel}")

            # Launch stream (quality is set in config before this call)
            self.process = self.twitch_viewer.watch_stream(self.channel)
            logger.info(f"[DEBUG] watch_stream returned: {self.process}")

            if self.process:
                logger.info("[DEBUG] Process created successfully, about to emit started signal")
                self.started.emit()
                logger.info(f"Stream process started: PID {self.process.pid}")

                # Wait for process to finish
                return_code = self.process.wait()
                logger.info(f"[DEBUG] Process finished with return code: {return_code}")

                if not self.should_stop:
                    if return_code == 0:
                        logger.info("Stream finished normally")
                        self.finished.emit()
                    else:
                        error_msg = f"Stream exited with code {return_code}"
                        logger.warning(error_msg)
                        self.error.emit(error_msg)
            else:
                error_msg = "Failed to start stream process"
                logger.error(error_msg)
                logger.error("[DEBUG] watch_stream returned None - stream failed to start")
                self.error.emit(error_msg)

        except Exception as e:
            error_msg = f"Stream error: {str(e)}"
            logger.error(f"[DEBUG] Exception in StreamWorker.run(): {type(e).__name__}: {str(e)}")
            logger.error(error_msg, exc_info=True)
            self.error.emit(error_msg)

    def stop(self) -> None:
        """Stop the stream process."""
        self.should_stop = True
        if self.process and self.process.poll() is None:
            try:
                logger.info("Terminating stream process")
                self.process.terminate()
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                logger.warning("Process didn't terminate, killing it")
                self.process.kill()
            except Exception as e:
                logger.error(f"Error stopping stream: {e}")


class StreamController(QObject):
    """
    Manages stream lifecycle with background thread operations.

    This controller handles starting, stopping, and monitoring stream
    processes using Qt's threading system.

    Signals:
        stream_started(str): Emitted when stream starts
            Args: (channel)
        stream_finished(str): Emitted when stream finishes
            Args: (channel)
        stream_error(str, str): Emitted when stream error occurs
            Args: (channel, error_message)
    """

    # Signals
    stream_started = Signal(str)   # channel
    stream_finished = Signal(str)  # channel
    stream_error = Signal(str, str)  # channel, error_message
    clip_created = Signal(str)     # output file path
    clip_failed = Signal(str)      # error message

    def __init__(self, config: ConfigManager):
        """
        Initialize the StreamController.

        Args:
            config: Configuration manager instance
        """
        super().__init__()

        self.config = config
        self.twitch_viewer = TwitchViewer(config)

        self.current_thread: Optional[QThread] = None
        self.current_worker: Optional[StreamWorker] = None
        self.current_channel: Optional[str] = None
        self.current_process: Optional[subprocess.Popen] = None
        self.current_quality: Optional[str] = None
        self._clip_thread: Optional[QThread] = None
        self._clip_worker: Optional[ClipWorker] = None

    def start_stream(self, channel: str, quality: str) -> None:
        """
        Start watching a stream in background thread.

        Args:
            channel: Channel name to watch
            quality: Quality to request
        """
        logger.info(f"[DEBUG] start_stream called: channel={channel}, quality={quality}")

        # Stop any existing stream first
        if self.is_streaming():
            logger.warning("Stream already running, stopping it first")
            self.stop_stream()

        # Update config with current quality
        self.config.set("quality", quality)
        logger.info(f"[DEBUG] Config updated with quality: {quality}")

        # Create worker and thread
        self.current_worker = StreamWorker(self.twitch_viewer, channel, quality)
        self.current_thread = QThread()
        self.current_channel = channel
        self.current_quality = quality
        logger.info("[DEBUG] Created worker and thread")

        # Move worker to thread
        self.current_worker.moveToThread(self.current_thread)
        logger.info("[DEBUG] Worker moved to thread")

        # Connect signals
        self.current_thread.started.connect(self.current_worker.run)
        self.current_worker.started.connect(self._on_stream_started)
        self.current_worker.finished.connect(self._on_stream_finished)
        self.current_worker.error.connect(self._on_stream_error)
        logger.info("[DEBUG] Signals connected")

        # Cleanup when finished
        self.current_worker.finished.connect(self.current_thread.quit)
        self.current_worker.error.connect(self.current_thread.quit)
        self.current_thread.finished.connect(self._cleanup_thread)

        # Start the thread
        logger.info(f"[DEBUG] Starting thread for channel: {channel}")
        self.current_thread.start()
        logger.info("[DEBUG] Thread started successfully")

        logger.info(f"Stream thread started for channel: {channel}")

    def stop_stream(self) -> None:
        """Stop the current stream."""
        if not self.is_streaming():
            logger.warning("No stream to stop")
            return

        logger.info(f"Stopping stream: {self.current_channel}")

        if self.current_worker:
            self.current_worker.stop()

        if self.current_thread:
            self.current_thread.quit()
            self.current_thread.wait(2000)  # Wait up to 2 seconds

        self._cleanup_thread()

    def is_streaming(self) -> bool:
        """
        Check if a stream is currently running.

        Returns:
            True if stream is running, False otherwise
        """
        return self.current_thread is not None and self.current_thread.isRunning()

    def create_clip(self) -> None:
        """Save the last 30 seconds of the current stream as a local clip."""
        if not self.is_streaming():
            self.clip_failed.emit("No active stream to clip")
            return

        self._clip_worker = ClipWorker(self.twitch_viewer)
        self._clip_thread = QThread()
        self._clip_worker.moveToThread(self._clip_thread)

        self._clip_thread.started.connect(self._clip_worker.run)
        self._clip_worker.finished.connect(self.clip_created)
        self._clip_worker.failed.connect(self.clip_failed)
        self._clip_worker.finished.connect(self._clip_thread.quit)
        self._clip_worker.failed.connect(self._clip_thread.quit)
        self._clip_thread.finished.connect(self._on_clip_thread_finished)

        self._clip_thread.start()

    def _on_clip_thread_finished(self) -> None:
        """Clean up clip thread and worker after completion."""
        if self._clip_thread:
            self._clip_thread.deleteLater()
            self._clip_thread = None
        if self._clip_worker:
            self._clip_worker.deleteLater()
            self._clip_worker = None

    def get_current_channel(self) -> Optional[str]:
        """
        Get the currently streaming channel.

        Returns:
            Channel name or None
        """
        return self.current_channel if self.is_streaming() else None

    def _on_stream_started(self) -> None:
        """Handle stream started signal from worker."""
        if self.current_worker:
            self.current_process = self.current_worker.process

        logger.info(f"Stream started: {self.current_channel}")
        self.stream_started.emit(self.current_channel)

    def _on_stream_finished(self) -> None:
        """Handle stream finished signal from worker."""
        channel = self.current_channel
        logger.info(f"Stream finished: {channel}")
        self.stream_finished.emit(channel)

    def _on_stream_error(self, error_message: str) -> None:
        """
        Handle stream error signal from worker.

        Args:
            error_message: Error message from worker
        """
        channel = self.current_channel
        logger.error(f"Stream error for {channel}: {error_message}")
        self.stream_error.emit(channel, error_message)

    def _cleanup_thread(self) -> None:
        """Clean up thread and worker references."""
        if self.current_thread:
            self.current_thread.deleteLater()
            self.current_thread = None

        if self.current_worker:
            self.current_worker.deleteLater()
            self.current_worker = None

        self.current_channel = None
        self.current_process = None
        self.current_quality = None

        logger.debug("Stream thread cleaned up")

    def get_current_process(self) -> Optional[subprocess.Popen]:
        """
        Get the current stream process for cleanup.

        Returns:
            Current subprocess.Popen or None
        """
        return self.current_process
