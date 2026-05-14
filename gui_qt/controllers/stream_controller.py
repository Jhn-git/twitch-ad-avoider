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
from typing import Any, Optional

from src.twitch_viewer import TwitchViewer
from src.config_manager import ConfigManager
from src.logging_config import get_logger

logger = get_logger(__name__)


class ClipWorker(QObject):
    """Runs create_clip() in a background thread."""

    finished = Signal(str)  # output path
    failed = Signal(str)  # error message

    def __init__(self, twitch_viewer: "TwitchViewer"):
        super().__init__()
        self.twitch_viewer = twitch_viewer

    def run(self) -> None:
        result = self.twitch_viewer.create_clip()
        if result:
            self.finished.emit(result)
        else:
            self.failed.emit(
                "Failed to create clip — check FFmpeg is installed and stream is active"
            )


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
        self.process: Optional[Any] = None
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
    stream_started = Signal(str)  # channel
    stream_finished = Signal(str)  # channel
    stream_error = Signal(str, str)  # channel, error_message
    clip_created = Signal(str)  # output file path
    clip_failed = Signal(str)  # error message

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
        self.current_process: Optional[Any] = None
        self.current_quality: Optional[str] = None
        self._clip_thread: Optional[QThread] = None
        self._clip_worker: Optional[ClipWorker] = None
        self._stream_generation = 0
        self._cleaned_stream_threads: set[int] = set()

    def start_stream(self, channel: str, quality: str) -> None:
        """
        Start watching a stream in background thread.

        Args:
            channel: Channel name to watch
            quality: Quality to request
        """
        logger.info(f"[DEBUG] start_stream called: channel={channel}, quality={quality}")

        # Update config with current quality before launch; TwitchViewer reads this key.
        if not self.config.set("preferred_quality", quality):
            logger.warning(f"Rejected invalid stream quality: {quality}")
            self.stream_error.emit(channel, f"Invalid stream quality: {quality}")
            return
        logger.info(f"[DEBUG] Config updated with preferred_quality: {quality}")

        # Stop any existing stream first
        if self.is_streaming():
            logger.warning("Stream already running, stopping it first")
            if not self.stop_stream():
                self.stream_error.emit(
                    self.current_channel or channel,
                    "Could not stop the current stream before starting a new one",
                )
                return

        # Create worker and thread
        worker = StreamWorker(self.twitch_viewer, channel, quality)
        thread = QThread()
        self._stream_generation += 1
        generation = self._stream_generation

        self.current_worker = worker
        self.current_thread = thread
        self.current_channel = channel
        self.current_quality = quality
        logger.info("[DEBUG] Created worker and thread")

        # Move worker to thread
        worker.moveToThread(thread)
        logger.info("[DEBUG] Worker moved to thread")

        # Connect signals
        thread.started.connect(worker.run)
        worker.started.connect(
            lambda ch=channel, stream_worker=worker, gen=generation: self._on_stream_started(
                ch, stream_worker, gen
            )
        )
        worker.finished.connect(
            lambda ch=channel, gen=generation: self._on_stream_finished(ch, gen)
        )
        worker.error.connect(
            lambda error, ch=channel, gen=generation: self._on_stream_error(ch, error, gen)
        )
        logger.info("[DEBUG] Signals connected")

        # Cleanup when finished
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(
            lambda stream_thread=thread, stream_worker=worker, gen=generation: (
                self._cleanup_thread(stream_thread, stream_worker, gen)
            )
        )

        # Start the thread
        logger.info(f"[DEBUG] Starting thread for channel: {channel}")
        thread.start()
        logger.info("[DEBUG] Thread started successfully")

        logger.info(f"Stream thread started for channel: {channel}")

    def stop_stream(self) -> bool:
        """Stop the current stream.

        Returns:
            True if no stream is active or the active stream stopped, False otherwise.
        """
        if not self.is_streaming():
            logger.warning("No stream to stop")
            return True

        logger.info(f"Stopping stream: {self.current_channel}")

        thread = self.current_thread
        worker = self.current_worker
        generation = self._stream_generation

        if worker:
            worker.stop()

        if thread:
            thread.quit()
            if not thread.wait(3000):
                logger.error("Stream thread did not stop within timeout")
                return False

        self._cleanup_thread(thread, worker, generation)
        return True

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

    def _on_stream_started(self, channel: str, worker: StreamWorker, generation: int) -> None:
        """Handle stream started signal from worker."""
        if generation != self._stream_generation or worker is not self.current_worker:
            logger.debug(f"Ignoring stale stream started signal for {channel}")
            return

        self.current_process = worker.process

        logger.info(f"Stream started: {channel}")
        self.stream_started.emit(channel)

    def _on_stream_finished(self, channel: str, generation: int) -> None:
        """Handle stream finished signal from worker."""
        if generation != self._stream_generation:
            logger.debug(f"Ignoring stale stream finished signal for {channel}")
            return

        logger.info(f"Stream finished: {channel}")
        self.stream_finished.emit(channel)

    def _on_stream_error(self, channel: str, error_message: str, generation: int) -> None:
        """
        Handle stream error signal from worker.

        Args:
            channel: Channel associated with the worker that failed
            error_message: Error message from worker
            generation: Stream lifecycle generation for stale signal filtering
        """
        if generation != self._stream_generation:
            logger.debug(f"Ignoring stale stream error signal for {channel}: {error_message}")
            return

        logger.error(f"Stream error for {channel}: {error_message}")
        self.stream_error.emit(channel, error_message)

    def _cleanup_thread(
        self,
        thread: Optional[QThread] = None,
        worker: Optional[StreamWorker] = None,
        generation: Optional[int] = None,
    ) -> None:
        """Clean up a completed stream thread and worker."""
        thread = thread or self.current_thread
        worker = worker or self.current_worker

        if thread is None and worker is None:
            return

        if thread is not None:
            thread_id = id(thread)
            if thread_id in self._cleaned_stream_threads:
                return
            self._cleaned_stream_threads.add(thread_id)
            thread.deleteLater()

        if worker is not None:
            worker.deleteLater()

        if generation is None or generation == self._stream_generation:
            self.current_thread = None
            self.current_worker = None
            self.current_channel = None
            self.current_process = None
            self.current_quality = None

        logger.debug("Stream thread cleaned up")

    def get_current_process(self) -> Optional[Any]:
        """
        Get the current stream process for cleanup.

        Returns:
            Current subprocess.Popen or None
        """
        return self.current_process
