#!/usr/bin/env python3
"""Probe Twitch VOD audio extraction before app integration."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import streamlink


DEFAULT_OUTPUT_DIR = Path("temp") / "vod-audio-probe"
DEFAULT_TRANSCRIBE_YT_ROOT = Path(r"C:\Users\redacted\Desktop\transcribe-yt")
STREAMLINK_CHUNK_SIZE = 64 * 1024
TRANSCRIBE_PROGRESS_PREFIX = "__probe_progress__="
TRANSCRIBE_RESULT_PREFIX = "__probe_result__="
TRANSCRIBE_WRAPPER_CODE = """
import importlib.util
import json
import pathlib
import sys

script_path = pathlib.Path(sys.argv[1])
source_path = sys.argv[2]
output_dir = sys.argv[3]

spec = importlib.util.spec_from_file_location("probe_transcribe_yt", script_path)
module = importlib.util.module_from_spec(spec)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Could not load transcribe-youtube.py from {script_path}")
sys.modules[spec.name] = module
spec.loader.exec_module(module)

def emit(event):
    print("__probe_progress__=" + json.dumps(event, ensure_ascii=True), flush=True)

result = module.run_transcription(
    source_path,
    model="auto",
    device="cuda",
    compute_type="auto",
    output_dir=output_dir,
    progress_callback=emit,
)

print("__probe_result__=" + json.dumps(result, ensure_ascii=True), flush=True)
"""


@dataclass(frozen=True)
class VodReference:
    video_id: str
    canonical_url: str


@dataclass(frozen=True)
class AudioProbeInfo:
    path: Path
    duration_seconds: float
    audio_stream_count: int
    format_name: str
    size_bytes: int


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive integer") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def non_negative_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a non-negative integer") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be a non-negative integer")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Resolve a Twitch VOD to audio_only and save a local probe file.",
    )
    parser.add_argument("vod_url_or_id", help="Twitch VOD URL or numeric VOD ID.")
    parser.add_argument(
        "--sample-seconds",
        type=positive_int,
        default=300,
        help="Length of the default sample probe. Ignored when --full is used.",
    )
    parser.add_argument(
        "--start-seconds",
        type=non_negative_int,
        default=0,
        help="Seek this many seconds into the VOD before extracting audio. Default: 0",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Extract the full VOD audio instead of only a sample.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"Where probe output is written. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--reuse-existing-audio",
        action="store_true",
        help="Reuse a matching existing extracted audio file when it is already present.",
    )
    parser.add_argument(
        "--transcribe",
        action="store_true",
        help="Hand the extracted audio file to the existing transcribe-yt environment.",
    )
    parser.add_argument(
        "--transcribe-yt-root",
        default=str(DEFAULT_TRANSCRIBE_YT_ROOT),
        help=f"Path to the existing transcribe-yt repo. Default: {DEFAULT_TRANSCRIBE_YT_ROOT}",
    )
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def canonical_vod_url(video_id: str) -> str:
    return f"https://www.twitch.tv/videos/{video_id}"


def parse_vod_reference(raw_value: str) -> VodReference:
    value = raw_value.strip().strip('"')
    if not value:
        raise ValueError("No VOD URL or ID provided.")

    if value.isdigit():
        return VodReference(video_id=value, canonical_url=canonical_vod_url(value))

    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(
            "Expected a Twitch VOD URL like https://www.twitch.tv/videos/123456789 "
            "or a numeric VOD ID."
        )

    host = parsed.netloc.lower().split(":", 1)[0]
    path_parts = [part for part in parsed.path.split("/") if part]

    video_token: str | None = None
    if host == "player.twitch.tv":
        video_token = parse_qs(parsed.query).get("video", [None])[0]
    elif host.endswith("twitch.tv"):
        for index, part in enumerate(path_parts[:-1]):
            if part in {"videos", "video", "v"}:
                video_token = path_parts[index + 1]
                break

    if video_token:
        normalized = video_token[1:] if video_token.lower().startswith("v") else video_token
        if normalized.isdigit():
            return VodReference(video_id=normalized, canonical_url=canonical_vod_url(normalized))

    raise ValueError(
        "Could not find a numeric VOD ID in that Twitch URL. "
        "Use a VOD URL like https://www.twitch.tv/videos/123456789 or just the numeric ID."
    )


def slugify(value: str) -> str:
    cleaned: list[str] = []
    last_was_dash = False
    for char in value.lower():
        if char.isalnum():
            cleaned.append(char)
            last_was_dash = False
        elif not last_was_dash:
            cleaned.append("-")
            last_was_dash = True
    return "".join(cleaned).strip("-") or "vod-audio"


def format_clock(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return "unknown"
    total_seconds = int(round(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{secs:02}" if hours else f"{minutes:02}:{secs:02}"


def format_bytes(size_bytes: int) -> str:
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f}{unit}" if unit != "B" else f"{int(size)}B"
        size /= 1024
    return f"{int(size_bytes)}B"


def format_percent(value: float | None) -> str:
    if value is None:
        return "?"
    return f"{value:.1f}%"


def build_progress_line(
    label: str,
    current_seconds: float | None,
    total_seconds: float | None,
    size_bytes: int | None = None,
    speed: str | None = None,
    extra: str | None = None,
) -> str:
    parts = [label]
    percent = None
    if (
        current_seconds is not None
        and total_seconds is not None
        and total_seconds > 0
    ):
        percent = min(max(current_seconds / total_seconds * 100.0, 0.0), 100.0)
    if percent is not None:
        parts.append(format_percent(percent))
    if current_seconds is not None:
        if total_seconds is not None and total_seconds > 0:
            parts.append(f"{format_clock(current_seconds)} / {format_clock(total_seconds)}")
        else:
            parts.append(format_clock(current_seconds))
    if size_bytes is not None:
        parts.append(format_bytes(size_bytes))
    if speed:
        parts.append(speed)
    if extra:
        parts.append(extra)
    return " | ".join(parts)


def create_streamlink_session() -> Any:
    session = streamlink.Streamlink()
    set_plugin_option = getattr(session, "set_plugin_option", None)
    session.set_option("http-timeout", 30)
    if callable(set_plugin_option):
        set_plugin_option("twitch", "disable-ads", True)
    return session


def choose_audio_stream(streams: dict[str, Any]) -> tuple[str, Any]:
    for candidate in ("audio_only", "audio"):
        stream = streams.get(candidate)
        if stream is not None:
            return candidate, stream

    available = ", ".join(sorted(streams)) or "none"
    raise RuntimeError(
        "Twitch VOD resolved successfully, but it did not expose an audio-only stream. "
        f"Available streams: {available}"
    )


def resolve_vod_audio_stream(
    reference: VodReference,
    session: Any | None = None,
) -> tuple[Any, str, Any]:
    active_session = session or create_streamlink_session()
    try:
        resolved = active_session.resolve_url(reference.canonical_url)
    except Exception as exc:
        raise RuntimeError(f"Could not resolve Twitch VOD URL: {exc}") from exc

    plugin = instantiate_streamlink_plugin(active_session, resolved)

    try:
        streams = plugin.streams()
    except Exception as exc:
        raise RuntimeError(
            "Could not fetch VOD streams. The VOD may be deleted, restricted, "
            f"or require a subscription. Details: {exc}"
        ) from exc

    if not streams:
        raise RuntimeError(
            "No playable streams were returned for this VOD. "
            "It may be deleted, restricted, or subscriber-only."
        )

    stream_name, stream = choose_audio_stream(streams)
    return plugin, stream_name, stream


def instantiate_streamlink_plugin(session: Any, resolved: Any) -> Any:
    if hasattr(resolved, "streams"):
        return resolved

    if isinstance(resolved, tuple) and len(resolved) >= 3:
        _plugin_name, plugin_class, resolved_url = resolved[:3]
        if callable(plugin_class):
            return plugin_class(session, resolved_url)

    raise RuntimeError(
        "Streamlink returned an unexpected resolve_url() result. "
        f"Expected a plugin object or (name, class, url) tuple, got: {type(resolved).__name__}"
    )


def find_required_executable(name: str) -> str:
    executable = shutil.which(name)
    if executable:
        return executable
    raise RuntimeError(f"{name} was not found on PATH.")


def probe_input_duration_seconds(input_source: str, ffprobe_exe: str) -> float | None:
    command = [
        ffprobe_exe,
        "-v",
        "error",
        "-show_format",
        "-of",
        "json",
        input_source,
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        return None

    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return None

    format_node = payload.get("format")
    if not isinstance(format_node, dict):
        return None
    duration = _safe_float(format_node.get("duration"))
    return duration if duration > 0 else None


def expected_output_duration_seconds(
    sample_seconds: int | None,
    start_seconds: int,
    source_duration_seconds: float | None,
) -> float | None:
    remaining_seconds = None
    if source_duration_seconds is not None:
        remaining_seconds = max(source_duration_seconds - start_seconds, 0.0)

    if sample_seconds is None:
        return remaining_seconds

    if remaining_seconds is None:
        return float(sample_seconds)
    return min(float(sample_seconds), remaining_seconds)


def build_audio_output_path(
    output_dir: Path,
    video_id: str,
    sample_seconds: int | None,
    start_seconds: int = 0,
) -> Path:
    mode = "full" if sample_seconds is None else f"sample-{sample_seconds}s"
    offset = f"-start-{start_seconds}s" if start_seconds > 0 else ""
    return output_dir / f"{slugify(f'vod-{video_id}-{mode}{offset}')}.m4a"


def build_ffmpeg_command(
    ffmpeg_exe: str,
    input_source: str,
    output_path: Path,
    sample_seconds: int | None,
    start_seconds: int = 0,
    input_seekable: bool = True,
    emit_progress: bool = False,
) -> list[str]:
    command = [
        ffmpeg_exe,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
    ]
    if emit_progress:
        command.extend(["-nostats", "-progress", "pipe:1"])
    if start_seconds > 0 and input_seekable:
        command.extend(["-ss", str(start_seconds)])
    command.extend(["-i", input_source])
    if start_seconds > 0 and not input_seekable:
        command.extend(["-ss", str(start_seconds)])
    command.extend(["-vn", "-sn", "-dn", "-map", "0:a:0"])
    if sample_seconds is not None:
        command.extend(["-t", str(sample_seconds)])
    command.extend(
        [
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
    )
    return command


def run_ffmpeg_with_progress(
    command: list[str],
    *,
    expected_duration_seconds: float | None,
) -> None:
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    progress_state: dict[str, str] = {}
    last_reported_percent = -1.0
    last_reported_seconds = -999999.0

    try:
        assert process.stdout is not None
        for raw_line in process.stdout:
            line = raw_line.strip()
            if not line or "=" not in line:
                continue
            key, value = line.split("=", 1)
            progress_state[key] = value
            if key != "progress":
                continue

            out_time_seconds = _ffmpeg_progress_seconds(progress_state)
            total_size = _safe_int(progress_state.get("total_size"))
            speed = progress_state.get("speed") or None
            should_report = value == "end"

            percent = None
            if expected_duration_seconds and expected_duration_seconds > 0 and out_time_seconds is not None:
                percent = min(max(out_time_seconds / expected_duration_seconds * 100.0, 0.0), 100.0)
                if percent >= last_reported_percent + 2.0:
                    should_report = True
            if out_time_seconds is not None and out_time_seconds >= last_reported_seconds + 60.0:
                should_report = True
            if last_reported_seconds < 0:
                should_report = True

            if should_report:
                print(
                    build_progress_line(
                        "Download progress",
                        out_time_seconds,
                        expected_duration_seconds,
                        total_size,
                        speed,
                    ),
                    flush=True,
                )
                if percent is not None:
                    last_reported_percent = percent
                if out_time_seconds is not None:
                    last_reported_seconds = out_time_seconds
    finally:
        if process.stdout is not None:
            process.stdout.close()

    stderr_text = ""
    if process.stderr is not None:
        stderr_text = process.stderr.read()
        process.stderr.close()
    return_code = process.wait()
    if return_code != 0:
        raise RuntimeError(
            "ffmpeg failed while extracting audio: "
            f"{stderr_text.strip() or 'unknown error'}"
        )


def _ffmpeg_progress_seconds(progress_state: dict[str, str]) -> float | None:
    microseconds = _safe_float(progress_state.get("out_time_ms"))
    if microseconds > 0:
        return microseconds / 1_000_000.0
    out_time = progress_state.get("out_time")
    if not out_time:
        return None
    try:
        hours, minutes, seconds = out_time.split(":")
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    except ValueError:
        return None


def extract_audio_with_ffmpeg(
    stream: Any,
    ffmpeg_exe: str,
    output_path: Path,
    sample_seconds: int | None,
    start_seconds: int = 0,
    expected_duration_seconds: float | None = None,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    stream_url = stream_input_url(stream)
    if stream_url:
        command = build_ffmpeg_command(
            ffmpeg_exe,
            stream_url,
            output_path,
            sample_seconds,
            start_seconds=start_seconds,
            input_seekable=True,
            emit_progress=True,
        )
        run_ffmpeg_with_progress(command, expected_duration_seconds=expected_duration_seconds)
        return output_path

    command = build_ffmpeg_command(
        ffmpeg_exe,
        "pipe:0",
        output_path,
        sample_seconds,
        start_seconds=start_seconds,
        input_seekable=False,
    )
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    stream_fd = None
    try:
        stream_fd = stream.open()
        while True:
            chunk = stream_fd.read(STREAMLINK_CHUNK_SIZE)
            if not chunk:
                break
            if not process.stdin:
                break
            try:
                process.stdin.write(chunk)
            except (BrokenPipeError, OSError):
                break
    finally:
        if process.stdin:
            try:
                process.stdin.close()
            except OSError:
                pass
        if stream_fd is not None:
            try:
                stream_fd.close()
            except Exception:
                pass

    stderr = b""
    if process.stderr is not None:
        stderr = process.stderr.read()
        process.stderr.close()
    return_code = process.wait()
    if return_code != 0:
        error_text = stderr.decode(errors="replace").strip()
        raise RuntimeError(f"ffmpeg failed while extracting audio: {error_text or 'unknown error'}")
    return output_path


def stream_input_url(stream: Any) -> str | None:
    url = getattr(stream, "url", None)
    if isinstance(url, str) and url.strip():
        return url

    to_url = getattr(stream, "to_url", None)
    if callable(to_url):
        translated = to_url()
        if isinstance(translated, str) and translated.strip():
            return translated

    return None


def probe_audio_output(audio_path: Path, ffprobe_exe: str) -> AudioProbeInfo:
    if not audio_path.exists():
        raise RuntimeError(f"ffmpeg reported success but the output file is missing: {audio_path}")

    command = [
        ffprobe_exe,
        "-v",
        "error",
        "-show_streams",
        "-show_format",
        "-of",
        "json",
        str(audio_path),
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr.strip() or result.stdout.strip()}")

    payload = json.loads(result.stdout or "{}")
    streams = payload.get("streams") or []
    audio_streams = [stream for stream in streams if stream.get("codec_type") == "audio"]
    video_streams = [stream for stream in streams if stream.get("codec_type") == "video"]
    if not audio_streams:
        raise RuntimeError("ffprobe found no audio stream in the extracted file.")
    if video_streams:
        raise RuntimeError("ffprobe found a video stream in the extracted audio file.")

    duration = _probe_duration_seconds(payload, audio_streams)
    if duration <= 0:
        raise RuntimeError("ffprobe reported a zero-length audio file.")
    size_bytes = audio_path.stat().st_size
    if size_bytes <= 0:
        raise RuntimeError("The extracted audio file is empty.")

    format_name = ""
    if isinstance(payload.get("format"), dict):
        format_name = str(payload["format"].get("format_name") or "")

    return AudioProbeInfo(
        path=audio_path,
        duration_seconds=duration,
        audio_stream_count=len(audio_streams),
        format_name=format_name,
        size_bytes=size_bytes,
    )


def _probe_duration_seconds(payload: dict[str, Any], audio_streams: list[dict[str, Any]]) -> float:
    format_node = payload.get("format")
    if isinstance(format_node, dict):
        format_duration = _safe_float(format_node.get("duration"))
        if format_duration > 0:
            return format_duration
    for stream in audio_streams:
        stream_duration = _safe_float(stream.get("duration"))
        if stream_duration > 0:
            return stream_duration
    return 0.0


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def ensure_transcribe_yt_environment(root: Path) -> tuple[Path, Path]:
    script_path = root / "transcribe-youtube.py"
    python_exe = root / ".venv" / "Scripts" / "python.exe"

    if not root.exists():
        raise RuntimeError(f"transcribe-yt root does not exist: {root}")
    if not script_path.exists():
        raise RuntimeError(f"transcribe-youtube.py was not found under: {root}")
    if not python_exe.exists():
        raise RuntimeError(f"transcribe-yt venv Python was not found: {python_exe}")
    return python_exe, script_path


def build_transcribe_command(
    python_exe: Path,
    script_path: Path,
    audio_path: Path,
    output_dir: Path,
) -> list[str]:
    return [
        str(python_exe),
        "-u",
        "-c",
        TRANSCRIBE_WRAPPER_CODE,
        str(script_path),
        str(audio_path),
        str(output_dir),
    ]


def parse_transcribe_output(output: str) -> list[Path]:
    transcript_paths: list[Path] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        for prefix in ("Text transcript:", "SRT transcript:"):
            if line.startswith(prefix):
                candidate = line[len(prefix) :].strip()
                if candidate:
                    transcript_paths.append(Path(candidate))
    return transcript_paths


def stream_transcribe_output(process: subprocess.Popen[str]) -> tuple[list[str], dict[str, Any] | None]:
    stdout_lines: list[str] = []
    result_payload: dict[str, Any] | None = None
    last_percent = -1
    last_seconds = -999999.0

    assert process.stdout is not None
    for raw_line in process.stdout:
        line = raw_line.rstrip()
        stdout_lines.append(line)
        stripped = line.strip()
        if not stripped:
            continue

        if stripped.startswith(TRANSCRIBE_PROGRESS_PREFIX):
            payload = _parse_json_marker(stripped, TRANSCRIBE_PROGRESS_PREFIX)
            if not isinstance(payload, dict):
                continue

            event_type = str(payload.get("type") or "")
            if event_type == "status":
                message = str(payload.get("message") or "").strip()
                if message:
                    print(f"Transcription status: {message}", flush=True)
                continue

            if event_type == "progress":
                percent = _safe_int(payload.get("percent"))
                current_seconds = _safe_float(payload.get("current_time"))
                total_seconds = _safe_float(payload.get("duration"))
                last_text = normalize_progress_text(str(payload.get("last_text") or ""))

                should_report = False
                if percent is not None and percent >= last_percent + 5:
                    should_report = True
                if current_seconds > 0 and current_seconds >= last_seconds + 120.0:
                    should_report = True
                if last_seconds < 0:
                    should_report = True

                if should_report:
                    extra = f'"{last_text}"' if last_text else None
                    print(
                        build_progress_line(
                            "Transcription progress",
                            current_seconds if current_seconds > 0 else None,
                            total_seconds if total_seconds > 0 else None,
                            extra=extra,
                        ),
                        flush=True,
                    )
                    if percent is not None:
                        last_percent = percent
                    if current_seconds > 0:
                        last_seconds = current_seconds
                continue

            if event_type == "done":
                result_payload = payload
                duration = _safe_float(payload.get("duration"))
                elapsed = _safe_float(payload.get("elapsed"))
                extra = None
                if elapsed > 0:
                    extra = f"elapsed {elapsed:.1f}s"
                print(
                    build_progress_line(
                        "Transcription progress",
                        duration if duration > 0 else None,
                        duration if duration > 0 else None,
                        extra=extra,
                    ),
                    flush=True,
                )
                continue

        if stripped.startswith(TRANSCRIBE_RESULT_PREFIX):
            payload = _parse_json_marker(stripped, TRANSCRIBE_RESULT_PREFIX)
            if isinstance(payload, dict):
                result_payload = payload
            continue

        print(f"Transcribe output: {stripped}", flush=True)

    return stdout_lines, result_payload


def _parse_json_marker(line: str, prefix: str) -> Any:
    try:
        return json.loads(line[len(prefix) :])
    except json.JSONDecodeError:
        return None


def normalize_progress_text(text: str, max_length: int = 80) -> str:
    compact = " ".join(text.split())
    if len(compact) <= max_length:
        return compact
    return compact[: max_length - 3].rstrip() + "..."


def transcribe_audio_probe(
    audio_path: Path,
    transcribe_root: Path,
    output_dir: Path,
) -> list[Path]:
    python_exe, script_path = ensure_transcribe_yt_environment(transcribe_root)
    output_dir.mkdir(parents=True, exist_ok=True)
    command = build_transcribe_command(python_exe, script_path, audio_path, output_dir)
    process = subprocess.Popen(
        command,
        cwd=str(transcribe_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    stdout_lines, result_payload = stream_transcribe_output(process)
    stderr_text = ""
    if process.stderr is not None:
        stderr_text = process.stderr.read()
        process.stderr.close()
    return_code = process.wait()
    if return_code != 0:
        combined = "\n".join(
            part.strip()
            for part in ("\n".join(stdout_lines), stderr_text)
            if part.strip()
        )
        raise RuntimeError(f"transcribe-yt failed:\n{combined or 'no output returned'}")

    transcript_paths: list[Path] = []
    if isinstance(result_payload, dict):
        txt_path = result_payload.get("txt_path")
        srt_path = result_payload.get("srt_path")
        if isinstance(txt_path, str) and txt_path.strip():
            transcript_paths.append(Path(txt_path))
        if isinstance(srt_path, str) and srt_path.strip():
            transcript_paths.append(Path(srt_path))
    if not transcript_paths:
        transcript_paths = parse_transcribe_output("\n".join(stdout_lines))
    if not transcript_paths:
        transcript_paths = sorted(output_dir.glob("*.txt")) + sorted(output_dir.glob("*.srt"))
    return transcript_paths


def run_probe(args: argparse.Namespace) -> int:
    reference = parse_vod_reference(args.vod_url_or_id)
    output_dir = Path(args.output_dir).expanduser().resolve()
    transcribe_root = Path(args.transcribe_yt_root).expanduser().resolve()
    sample_seconds = None if args.full else args.sample_seconds
    start_seconds = args.start_seconds

    ffmpeg_exe = find_required_executable("ffmpeg")
    ffprobe_exe = find_required_executable("ffprobe")

    print(f"Resolved VOD ID: {reference.video_id}")
    print(f"Canonical URL: {reference.canonical_url}")
    print(f"Probe mode: {'full VOD' if sample_seconds is None else f'{sample_seconds}s sample'}")
    print(f"Probe start: {start_seconds}s")

    plugin, stream_name, stream = resolve_vod_audio_stream(reference)
    plugin_title = _safe_plugin_title(plugin)
    print(f"Selected stream: {stream_name}")
    if plugin_title:
        print(f"VOD title: {plugin_title}")

    stream_url = stream_input_url(stream)
    source_duration_seconds = None
    if stream_url:
        source_duration_seconds = probe_input_duration_seconds(stream_url, ffprobe_exe)
    if source_duration_seconds is not None:
        print(f"Source duration: {format_clock(source_duration_seconds)}")

    planned_duration_seconds = expected_output_duration_seconds(
        sample_seconds,
        start_seconds,
        source_duration_seconds,
    )
    if source_duration_seconds is not None and planned_duration_seconds is not None:
        if planned_duration_seconds <= 0:
            raise RuntimeError(
                "The requested start offset is beyond the available VOD duration. "
                f"Start: {format_clock(float(start_seconds))}, VOD: {format_clock(source_duration_seconds)}"
            )
        print(f"Planned output duration: {format_clock(planned_duration_seconds)}")

    audio_path = build_audio_output_path(
        output_dir,
        reference.video_id,
        sample_seconds,
        start_seconds=start_seconds,
    )
    print(f"Audio output path: {audio_path}")
    probe_info: AudioProbeInfo
    if args.reuse_existing_audio and audio_path.exists():
        print("Reusing existing extracted audio file.", flush=True)
        probe_info = probe_audio_output(audio_path, ffprobe_exe)
    else:
        if args.reuse_existing_audio:
            print("No reusable audio file found. Extracting audio now.", flush=True)
        print("Starting audio extraction...", flush=True)
        extract_audio_with_ffmpeg(
            stream,
            ffmpeg_exe,
            audio_path,
            sample_seconds,
            start_seconds=start_seconds,
            expected_duration_seconds=planned_duration_seconds,
        )
        print("Audio extraction finished.", flush=True)
        probe_info = probe_audio_output(audio_path, ffprobe_exe)

    print(f"Audio file: {probe_info.path}")
    print(f"Audio duration: {probe_info.duration_seconds:.1f}s")
    print(f"Audio streams: {probe_info.audio_stream_count}")
    print(f"Container: {probe_info.format_name or 'unknown'}")
    print(f"Size: {probe_info.size_bytes} bytes")

    transcript_paths: list[Path] = []
    if args.transcribe:
        transcript_dir = output_dir / "transcripts"
        print(f"Transcript output dir: {transcript_dir}")
        print("Starting transcription...", flush=True)
        transcript_paths = transcribe_audio_probe(probe_info.path, transcribe_root, transcript_dir)
        if transcript_paths:
            print("Transcript outputs:")
            for transcript_path in transcript_paths:
                print(f"  {transcript_path}")
        else:
            print("Transcript run finished, but no output paths were detected.")

    return 0


def _safe_plugin_title(plugin: Any) -> str | None:
    get_title = getattr(plugin, "get_title", None)
    if not callable(get_title):
        return None
    try:
        title = get_title()
    except Exception:
        return None
    return title if isinstance(title, str) and title.strip() else None


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return run_probe(args)
    except KeyboardInterrupt:
        print("\nStopped.")
        return 130
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
