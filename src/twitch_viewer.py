"""
Main module for TwitchViewer functionality.

This module provides the core streaming functionality for TwitchAdAvoider, including:
    - Stream detection and quality selection
    - Video player auto-detection and management
    - Process control and monitoring
    - Integration with streamlink for ad avoidance

The :class:`TwitchViewer` class serves as the primary interface for stream operations,
coordinating between configuration management, input validation, and external processes.

See Also:
    :mod:`src.config_manager`: Configuration and settings management
    :mod:`src.validators`: Input validation and security functions
    :mod:`gui_qt.stream_gui`: Qt graphical user interface integration
"""

import os
import shlex
import subprocess
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Dict, List, cast
import streamlink
import shutil

from .exceptions import TwitchStreamError, ValidationError
from .config_manager import ConfigManager
from .logging_config import get_logger
from .validators import validate_channel_name
from .constants import (
    SUPPORTED_PLAYERS,
    COMMON_PLAYER_PATHS,
    ENV_PLAYER_PATH,
    ENV_PLAYER_NAME,
    CLIPS_DIR,
    TEMP_DIR,
)

logger = get_logger(__name__)


class _StreamSession:
    """Wraps a player subprocess and its open stream fd for coordinated shutdown."""

    def __init__(self, player: subprocess.Popen, stream_fd: Any) -> None:
        self._player = player
        self._fd = stream_fd
        self.pid: int = player.pid

    def poll(self) -> Optional[int]:
        return self._player.poll()

    def wait(self, timeout: Optional[float] = None) -> int:
        return self._player.wait(timeout=timeout)

    def terminate(self) -> None:
        try:
            self._player.terminate()
        except Exception:
            pass
        try:
            self._fd.close()
        except Exception:
            pass

    def kill(self) -> None:
        try:
            self._player.kill()
        except Exception:
            pass
        try:
            self._fd.close()
        except Exception:
            pass


class TwitchViewer:
    """
    Main class for watching Twitch streams with ad avoidance.

    This class provides the core functionality for stream detection, player management,
    and process control. It integrates with streamlink for ad-free streaming and
    supports multiple video players with automatic detection.

    The class handles the complete streaming workflow:
        1. Input validation via :mod:`src.validators`
        2. Stream detection and quality selection
        3. Player detection and configuration
        4. Process launching and monitoring

    Attributes:
        config (:class:`~src.config_manager.ConfigManager`): Configuration manager instance
        player_path (Optional[str]): Path to detected video player executable
        selected_player (Optional[str]): Name of currently selected player
        session (streamlink.Streamlink): Streamlink session for stream operations

    Example:
        >>> from src.config_manager import ConfigManager
        >>> config = ConfigManager()
        >>> viewer = TwitchViewer(config)
        >>> viewer.watch_stream("ninja", "720p")

    See Also:
        :class:`~src.config_manager.ConfigManager`: Configuration management
        :func:`~src.validators.validate_channel_name`: Channel name validation
        :class:`~gui_qt.stream_gui.StreamGUI`: Qt GUI integration
    """

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """
        Initialize the TwitchViewer with configuration and streamlink session.

        Args:
            config_manager (Optional[ConfigManager]): Configuration manager instance.
                If None, a new ConfigManager will be created with default settings.

        Note:
            The streamlink session is configured with timeout settings from the
            configuration manager's network_timeout setting.
        """
        self.config = config_manager or ConfigManager()
        self.player_path: Optional[str] = None
        self.selected_player: Optional[str] = None
        self.session = streamlink.Streamlink()
        self._recording_path: Optional[str] = None
        self._recording_start_time: Optional[datetime] = None
        self._current_channel: Optional[str] = None

        # Configure session options
        timeout = self.config.get("network_timeout", 30)
        self.session.set_option("http-timeout", timeout)
        self.session.set_option("stream-segment-attempts", 5)
        self.session.set_option("stream-segment-timeout", 15.0)
        self.session.set_option("hls-playlist-reload-attempts", 5)
        try:
            self.session.set_plugin_option("twitch", "disable-ads", True)
        except Exception:
            pass
        logger.debug(f"TwitchViewer session configured with {timeout}s timeout")

        # Check streamlink availability on startup
        if not self._check_streamlink_availability():
            logger.warning("Streamlink availability check failed")

        logger.info("TwitchViewer initialized")

    def set_player_choice(self, player_name: str) -> None:
        """
        Set the player choice from GUI selection.

        Args:
            player_name: Name of the player selected in GUI ('vlc', 'mpv', 'mpc-hc', 'auto')
        """
        self.selected_player = player_name
        # Reset player path when player choice changes to force re-detection
        self.player_path = None
        logger.debug(f"Player choice set to: {player_name}")

    def _check_streamlink_availability(self) -> bool:
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

    def is_streamlink_available(self) -> bool:
        """
        Public method to check streamlink availability

        Returns:
            True if streamlink is available, False otherwise
        """
        return self._check_streamlink_availability()

    def _validate_channel(self, channel_name: str) -> str:
        """
        Validate the Twitch channel name using enhanced security controls.
        Args:
            channel_name (str): Name of the channel to validate
        Returns:
            str: Validated channel name
        Raises:
            ValidationError: If channel name is invalid
        """
        return validate_channel_name(channel_name)

    def _get_supported_players(self) -> Dict[str, List[str]]:
        """
        Get supported player configurations.

        Returns:
            Dict[str, List[str]]: Dictionary mapping player names to their executable names
        """
        return SUPPORTED_PLAYERS

    def _get_common_player_paths(self) -> Dict[str, List[str]]:
        """
        Get common installation paths for players.

        Returns:
            Dict[str, List[str]]: Dictionary mapping player names to their common installation paths
        """
        return COMMON_PLAYER_PATHS

    def _check_environment_player(self, debug: bool = False) -> Optional[str]:
        """
        Check for player from environment variables (PowerShell integration).

        Args:
            debug: Enable debug logging

        Returns:
            Optional[str]: Player name if found via environment variables, None otherwise
        """
        exported_player_path = os.environ.get(ENV_PLAYER_PATH)
        exported_player_name = os.environ.get(ENV_PLAYER_NAME)

        if exported_player_path and os.path.exists(exported_player_path):
            if debug:
                logger.debug(
                    f"Found exported player: {exported_player_name} at {exported_player_path}"
                )
            self.player_path = exported_player_path
            return exported_player_name.lower() if exported_player_name else "unknown"
        return None

    def _check_manual_player(self, debug: bool = False) -> Optional[str]:
        """
        Check for manually configured player path.

        Args:
            debug: Enable debug logging

        Returns:
            Optional[str]: Player name if manually configured path exists, None otherwise
        """
        manual_player_path = self.config.get("player_path")
        if manual_player_path and os.path.exists(manual_player_path):
            if debug:
                logger.debug(f"Using manual player path: {manual_player_path}")
            self.player_path = manual_player_path
            return cast(str, self.config.get("player", "manual"))
        return None

    def _check_player_in_path(
        self, player_name: str, executables: List[str], debug: bool = False
    ) -> Optional[str]:
        """
        Check if player is available in system PATH.

        Args:
            player_name: Name of the player to check
            executables: List of executable names to search for
            debug: Enable debug logging

        Returns:
            Optional[str]: Player name if found in PATH, None otherwise
        """
        for exe in executables:
            player_path = shutil.which(exe)
            if player_path:
                if debug:
                    logger.debug(f"Found {player_name} in PATH: {player_path}")
                self.player_path = player_path
                return player_name
        return None

    def _check_player_common_paths(
        self, player_name: str, paths: List[str], debug: bool = False
    ) -> Optional[str]:
        """
        Check player in common installation paths.

        Args:
            player_name: Name of the player to check
            paths: List of paths to check
            debug: Enable debug logging

        Returns:
            Optional[str]: Player name if found in common paths, None otherwise
        """
        for path in paths:
            if os.path.exists(path):
                if debug:
                    logger.debug(f"Found {player_name} at: {path}")
                self.player_path = path
                return player_name
        return None

    def _detect_player(self) -> str:
        """
        Detect available video player based on GUI selection and configuration.

        Uses a priority-based detection system:
        1. Manual player path from configuration
        2. Auto detection if selected
        3. Selected player search in PATH and common locations
        4. Environment variables (PowerShell integration)
        5. Fallback to streamlink auto-detection

        Returns:
            str: Name of the detected player or 'auto' for streamlink auto-detection
        """
        debug = self.config.get("debug", False)
        if debug:
            logger.debug("Starting player detection...")

        # Get player choice (GUI selection takes precedence)
        player_choice = self._get_player_choice(debug)

        # Try different detection methods in priority order
        if self._try_manual_player_detection(debug, player_choice):
            return player_choice

        if self._try_auto_detection(debug, player_choice):
            return "auto"

        if self._try_specific_player_detection(debug, player_choice):
            return player_choice

        if self._try_environment_player_detection(debug):
            env_player = self._check_environment_player(debug)
            return env_player if env_player else "auto"

        # Final fallback
        return self._fallback_to_streamlink_detection(debug, player_choice)

    def _get_player_choice(self, debug: bool) -> str:
        """Get the preferred player choice from GUI or configuration."""
        player_choice = self.selected_player or self.config.get("player", "vlc")
        if debug:
            logger.debug(f"Player choice: {player_choice}")
        return player_choice

    def _try_manual_player_detection(self, debug: bool, player_choice: str) -> bool:
        """Try to use manually configured player path."""
        manual_result = self._check_manual_player(debug)
        return manual_result is not None

    def _try_auto_detection(self, debug: bool, player_choice: str) -> bool:
        """Try auto detection if selected."""
        if player_choice == "auto":
            if debug:
                logger.debug("Using streamlink auto-detection")
            self.player_path = None
            return True
        return False

    def _try_specific_player_detection(self, debug: bool, player_choice: str) -> bool:
        """Try to detect a specific player using multiple methods."""
        players = self._get_supported_players()
        common_paths = self._get_common_player_paths()

        if player_choice not in players:
            return False

        # Search system PATH first
        if self._check_player_in_path(player_choice, players[player_choice], debug):
            return True

        # Search common installation directories
        if player_choice in common_paths:
            return (
                self._check_player_common_paths(player_choice, common_paths[player_choice], debug)
                is not None
            )

        return False

    def _try_environment_player_detection(self, debug: bool) -> bool:
        """Try to detect player from environment variables."""
        return self._check_environment_player(debug) is not None

    def _fallback_to_streamlink_detection(self, debug: bool, player_choice: str) -> str:
        """Fallback when no specific player is detected."""
        if debug:
            logger.debug(f"Could not find {player_choice}, will scan all known players")
        self.player_path = None
        return "auto"

    def _find_any_player(self) -> None:
        """Last-resort scan: try every known player in PATH and common dirs."""
        for player_name, exes in SUPPORTED_PLAYERS.items():
            if self._check_player_in_path(player_name, exes):
                return
        for player_name, paths in COMMON_PLAYER_PATHS.items():
            if self._check_player_common_paths(player_name, paths):
                return

    def watch_stream(self, channel_name: str) -> Optional["_StreamSession"]:
        """
        Watch a Twitch stream for the specified channel.

        Uses the streamlink Python API to open the stream and pipes raw TS bytes
        to the player's stdin, simultaneously writing to a recording file for
        clip support. No external streamlink executable is required.

        Args:
            channel_name: Name of the Twitch channel to watch

        Returns:
            _StreamSession wrapping the player process, or None on error

        Raises:
            ValidationError: If channel name is invalid
            TwitchStreamError: If stream cannot be accessed or player not found
        """
        try:
            channel_name = self._validate_channel(channel_name)

            # Ensure we have a concrete player path
            if self.player_path is None:
                self._detect_player()
            if self.player_path is None:
                self._find_any_player()
            if self.player_path is None:
                raise TwitchStreamError(
                    "No video player found. Install VLC or MPV, or configure a "
                    "custom player path in Settings."
                )

            quality = self.config.get("preferred_quality", "best")
            logger.info(
                f"Starting stream: {channel_name} @ {quality} "
                f"| player={self.config.get('player')}"
            )

            # Resolve stream via streamlink Python API
            streams = self.session.streams(f"twitch.tv/{channel_name}")
            if not streams:
                raise TwitchStreamError(f"No streams available for: {channel_name}")
            if quality not in streams:
                quality = "best"
            if quality not in streams:
                quality = next(iter(streams))

            stream_fd = streams[quality].open()

            # Setup recording file (tee target for clip support)
            self._current_channel = channel_name
            self._recording_path = None
            self._recording_start_time = None
            recording_file = None
            if self.config.get("clip_enabled", True):
                TEMP_DIR.mkdir(parents=True, exist_ok=True)
                rec_path = TEMP_DIR / f"recording_{channel_name}.ts"
                self._recording_path = str(rec_path)
                self._recording_start_time = datetime.now()
                if rec_path.exists():
                    try:
                        rec_path.unlink()
                        logger.debug(f"Removed stale recording: {rec_path}")
                    except Exception as e:
                        logger.warning(f"Could not remove stale recording: {e}")
                try:
                    recording_file = open(self._recording_path, "wb")
                    logger.debug(f"Recording to: {self._recording_path}")
                except Exception as e:
                    logger.warning(f"Could not open recording file: {e}")

            # Launch player with stdin as its input source ("-" = stdin MRL)
            player_cmd = [self.player_path, "-"]
            player_args_str = self.config.get("player_args")
            if player_args_str:
                player_cmd.extend(shlex.split(player_args_str))

            logger.info(f"Launching player: {' '.join(str(a) for a in player_cmd)}")
            try:
                player_proc = subprocess.Popen(player_cmd, stdin=subprocess.PIPE, bufsize=0)
            except FileNotFoundError:
                stream_fd.close()
                if recording_file:
                    recording_file.close()
                raise TwitchStreamError(
                    f"Player not found at: {self.player_path}. "
                    "Check the player path in Settings."
                )

            # Background tee: stream fd → player stdin + recording file
            def _tee() -> None:
                try:
                    while True:
                        chunk = stream_fd.read(65536)
                        if not chunk:
                            break
                        if player_proc.stdin:
                            try:
                                player_proc.stdin.write(chunk)
                            except (BrokenPipeError, OSError):
                                break
                        if recording_file:
                            recording_file.write(chunk)
                except Exception as e:
                    logger.error(f"Tee thread error: {e}")
                finally:
                    try:
                        stream_fd.close()
                    except Exception:
                        pass
                    try:
                        if player_proc.stdin:
                            player_proc.stdin.close()
                    except Exception:
                        pass
                    if recording_file:
                        try:
                            recording_file.close()
                        except Exception:
                            pass
                    logger.debug("Tee thread finished")

            tee = threading.Thread(target=_tee, daemon=True, name=f"tee-{channel_name}")
            tee.start()

            logger.info(f"Stream live: {channel_name} @ {quality} (player PID {player_proc.pid})")
            return _StreamSession(player_proc, stream_fd)

        except ValidationError:
            raise
        except TwitchStreamError:
            raise
        except streamlink.StreamlinkError as e:
            raise TwitchStreamError(f"Stream error: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error starting stream: {e}")
            raise TwitchStreamError(f"Unexpected error: {e}") from e

    def _get_ffmpeg_executable(self) -> Optional[str]:
        """Locate FFmpeg, checking configured path then system PATH."""
        configured = self.config.get("ffmpeg_path", "")
        if configured and Path(configured).exists():
            return configured
        return shutil.which("ffmpeg")

    def _probe_clip_start(self, _ffmpeg_exe: str, duration_seconds: int) -> Optional[float]:
        """Return start offset (seconds) for a clip of duration_seconds from end of recording.

        Uses wall-clock elapsed time since recording started. ffprobe's format.duration
        is unreliable for live TS files: it reflects the HLS PTS value (stream time since
        the Twitch stream started, potentially hours ago) rather than the amount of content
        actually recorded to disk.
        """
        if self._recording_start_time is None:
            logger.warning("[PROBE] No recording start time — cannot calculate clip offset")
            return None

        elapsed = (datetime.now() - self._recording_start_time).total_seconds()
        start_offset = max(0.0, elapsed - duration_seconds)
        logger.info(
            f"[PROBE] Elapsed recording time: {elapsed:.1f}s, "
            f"clip start offset: {start_offset:.1f}s (last {duration_seconds}s)"
        )
        return start_offset

    def create_clip(self, duration_seconds: int = 30) -> Optional[str]:
        """
        Save the last N seconds of the current recording as a clip.

        Args:
            duration_seconds: How many seconds to clip from the end

        Returns:
            Path to the saved clip file, or None on failure
        """
        if not self._recording_path or not Path(self._recording_path).exists():
            logger.warning("No recording available — start a stream with clip_enabled=True first")
            return None

        ffmpeg_exe = self._get_ffmpeg_executable()
        if not ffmpeg_exe:
            logger.error("FFmpeg not found. Install FFmpeg and ensure it is in PATH.")
            return None

        clip_dir = Path(self.config.get("clip_directory", str(CLIPS_DIR)))
        clip_dir.mkdir(parents=True, exist_ok=True)

        channel = self._current_channel or "unknown"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = clip_dir / f"{channel}_{timestamp}.ts"

        # Probe the recording duration so we can seek accurately.
        # -sseof is unreliable for live-written TS files (FFmpeg can't find
        # the true EOF), so we calculate the start offset explicitly.
        logger.debug(
            f"[CLIP] Recording file size: {Path(self._recording_path).stat().st_size} bytes"
        )
        start_time = self._probe_clip_start(ffmpeg_exe, duration_seconds)

        if start_time is not None:
            seek_args = [
                "-ss",
                str(start_time),
                "-i",
                self._recording_path,
                "-t",
                str(duration_seconds),
            ]
            logger.info(
                f"[CLIP] Using seek: -ss {start_time} -i <file> -t {duration_seconds}"
            )
        else:
            seek_args = ["-sseof", f"-{duration_seconds}", "-i", self._recording_path]
            logger.warning(
                f"[CLIP] No start time, falling back to: -sseof -{duration_seconds} -i <file>"
            )

        cmd = [
            ffmpeg_exe,
            # Tolerate partial/corrupt packets at the tail of a live recording.
            # The tee thread is still writing; the last chunk may be incomplete,
            # causing "Invalid NAL unit size" errors with -c copy.
            # discardcorrupt drops those packets and trims to the last clean frame.
            "-fflags", "+discardcorrupt",
            *seek_args,
            "-c", "copy",
            # NOTE: -bsf:v h264_mp4toannexb is intentionally absent. That filter
            # converts MP4 length-prefixed NALUs to Annex-B start codes. TS streams
            # are already Annex-B, so applying it produces "Invalid NAL unit size".
            "-avoid_negative_ts", "make_zero",
            "-y",
            str(output_path),
        ]

        logger.debug(f"[CLIP] Full FFmpeg command: {' '.join(cmd)}")

        try:
            result = subprocess.run(cmd, capture_output=True, timeout=60)
            stderr_text = result.stderr.decode(errors="replace") if result.stderr else ""
            logger.debug(f"[CLIP] FFmpeg return code: {result.returncode}")
            if stderr_text:
                logger.debug(f"[CLIP] FFmpeg stderr: {stderr_text[:500]}...")

            output_size = output_path.stat().st_size if output_path.exists() else 0
            if output_size > 1024:
                # Accept the clip even on non-zero exit — with -fflags +discardcorrupt,
                # FFmpeg may skip corrupt tail packets and still exit non-zero while
                # having written a perfectly usable clip.
                if result.returncode != 0:
                    logger.debug(
                        f"[CLIP] FFmpeg exited {result.returncode} but clip was created "
                        f"({output_size} bytes); treating as success"
                    )
                logger.info(f"[CLIP] Clip saved: {output_path} ({output_size} bytes)")
                return str(output_path)
            else:
                logger.error(f"[CLIP] FFmpeg failed (code {result.returncode}): {stderr_text}")
                return None
        except subprocess.TimeoutExpired:
            logger.error("[CLIP] FFmpeg timed out creating clip after 60 seconds")
            return None
        except Exception as e:
            logger.error(f"[CLIP] Unexpected error creating clip: {e}")
            return None

    def cleanup_recording(self) -> None:
        """Delete the temp recording file from the current session."""
        if self._recording_path and Path(self._recording_path).exists():
            try:
                Path(self._recording_path).unlink()
                logger.debug(f"Deleted temp recording: {self._recording_path}")
            except Exception as e:
                logger.warning(f"Failed to delete temp recording: {e}")
        self._recording_path = None
        self._recording_start_time = None
