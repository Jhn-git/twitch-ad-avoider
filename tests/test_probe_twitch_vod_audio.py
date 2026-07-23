"""Tests for the standalone Twitch VOD audio probe script."""

from __future__ import annotations

import argparse
import importlib.util
import json
import io
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


def load_probe_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "probe_twitch_vod_audio.py"
    spec = importlib.util.spec_from_file_location("probe_twitch_vod_audio", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


probe = load_probe_module()


class FakePlugin:
    def __init__(self, streams, title="Probe Title"):
        self._streams = streams
        self._title = title

    def streams(self):
        return self._streams

    def get_title(self):
        return self._title


class FakePluginClass:
    def __init__(self, session, url, options=None):
        self.session = session
        self.url = url
        self.options = options

    def streams(self):
        return {"audio": object()}

    def get_title(self):
        return "Probe Title"


class TestProbeTwitchVodAudio(unittest.TestCase):
    def test_parse_vod_reference_accepts_numeric_id(self):
        reference = probe.parse_vod_reference("123456789")

        self.assertEqual(reference.video_id, "123456789")
        self.assertEqual(reference.canonical_url, "https://www.twitch.tv/videos/123456789")

    def test_parse_vod_reference_accepts_standard_twitch_url(self):
        reference = probe.parse_vod_reference("https://www.twitch.tv/videos/987654321?t=1h2m3s")

        self.assertEqual(reference.video_id, "987654321")

    def test_parse_vod_reference_accepts_player_embed_url(self):
        reference = probe.parse_vod_reference(
            "https://player.twitch.tv/?video=v24680&parent=example.com"
        )

        self.assertEqual(reference.video_id, "24680")

    def test_parse_vod_reference_rejects_non_vod_twitch_url(self):
        with self.assertRaises(ValueError):
            probe.parse_vod_reference("https://www.twitch.tv/theonlymonto")

    def test_choose_audio_stream_prefers_audio_only(self):
        audio_only = object()
        audio = object()

        stream_name, stream = probe.choose_audio_stream(
            {"best": object(), "audio": audio, "audio_only": audio_only}
        )

        self.assertEqual(stream_name, "audio_only")
        self.assertIs(stream, audio_only)

    def test_choose_audio_stream_accepts_audio_fallback(self):
        audio = object()

        stream_name, stream = probe.choose_audio_stream({"best": object(), "audio": audio})

        self.assertEqual(stream_name, "audio")
        self.assertIs(stream, audio)

    def test_choose_audio_stream_fails_clearly_when_missing(self):
        with self.assertRaises(RuntimeError) as ctx:
            probe.choose_audio_stream({"best": object(), "720p": object()})

        self.assertIn("audio-only stream", str(ctx.exception))
        self.assertIn("best", str(ctx.exception))

    def test_instantiate_streamlink_plugin_accepts_streamlink_tuple(self):
        session = object()

        plugin = probe.instantiate_streamlink_plugin(
            session,
            ("twitch", FakePluginClass, "https://www.twitch.tv/videos/123456789"),
        )

        self.assertIsInstance(plugin, FakePluginClass)
        self.assertIs(plugin.session, session)
        self.assertEqual(plugin.url, "https://www.twitch.tv/videos/123456789")

    def test_extract_audio_with_ffmpeg_uses_stream_url_when_available(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "probe.m4a"
            stream = SimpleNamespace(url="https://example.com/audio.m3u8")

            with patch.object(probe, "run_ffmpeg_with_progress") as progress_mock:
                returned_path = probe.extract_audio_with_ffmpeg(
                    stream,
                    "ffmpeg",
                    output_path,
                    5,
                    start_seconds=900,
                    expected_duration_seconds=300.0,
                )

        self.assertEqual(returned_path, output_path)
        command = progress_mock.call_args.args[0]
        self.assertIn("https://example.com/audio.m3u8", command)
        self.assertNotIn("pipe:0", command)
        self.assertIn("-ss", command)
        self.assertIn("-progress", command)

    def test_build_audio_output_path_includes_start_offset(self):
        output_path = probe.build_audio_output_path(
            Path(r"C:\temp\vod-audio-probe"),
            "123456789",
            300,
            start_seconds=900,
        )

        self.assertEqual(output_path.name, "vod-123456789-sample-300s-start-900s.m4a")

    def test_build_transcribe_command_uses_unbuffered_wrapper(self):
        command = probe.build_transcribe_command(
            Path(r"C:\transcribe-yt\.venv\Scripts\python.exe"),
            Path(r"C:\transcribe-yt\transcribe-youtube.py"),
            Path(r"C:\temp\audio.m4a"),
            Path(r"C:\temp\transcripts"),
        )

        self.assertEqual(command[1:4], ["-u", "-c", probe.TRANSCRIBE_WRAPPER_CODE])
        self.assertEqual(command[-3:], [
            r"C:\transcribe-yt\transcribe-youtube.py",
            r"C:\temp\audio.m4a",
            r"C:\temp\transcripts",
        ])

    def test_expected_output_duration_seconds_uses_remaining_source_time(self):
        duration = probe.expected_output_duration_seconds(
            sample_seconds=None,
            start_seconds=900,
            source_duration_seconds=21030.0,
        )

        self.assertEqual(duration, 20130.0)

    def test_stream_transcribe_output_parses_progress_and_result_markers(self):
        stdout_lines = iter(
            [
                probe.TRANSCRIBE_PROGRESS_PREFIX
                + '{"type":"status","message":"Loading model..."}\n',
                probe.TRANSCRIBE_PROGRESS_PREFIX
                + '{"type":"progress","percent":25,"current_time":75.0,"duration":300.0,"last_text":"hello world"}\n',
                probe.TRANSCRIBE_RESULT_PREFIX
                + '{"txt_path":"C:\\\\temp\\\\probe.txt","srt_path":"C:\\\\temp\\\\probe.srt"}\n',
            ]
        )
        process = SimpleNamespace(stdout=stdout_lines)

        with patch("builtins.print"):
            lines, result_payload = probe.stream_transcribe_output(process)

        self.assertEqual(len(lines), 3)
        assert result_payload is not None
        self.assertEqual(result_payload["txt_path"], r"C:\temp\probe.txt")

    def test_probe_audio_output_rejects_video_streams(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = Path(temp_dir) / "probe.m4a"
            audio_path.write_bytes(b"audio")
            payload = {
                "streams": [
                    {"codec_type": "audio", "duration": "5.0"},
                    {"codec_type": "video", "duration": "5.0"},
                ],
                "format": {"duration": "5.0", "format_name": "mov,mp4,m4a"},
            }
            completed = SimpleNamespace(
                returncode=0,
                stdout=json.dumps(payload),
                stderr="",
            )

            with patch.object(probe.subprocess, "run", return_value=completed):
                with self.assertRaises(RuntimeError) as ctx:
                    probe.probe_audio_output(audio_path, "ffprobe")

        self.assertIn("video stream", str(ctx.exception))

    def test_probe_audio_output_returns_duration_and_format(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = Path(temp_dir) / "probe.m4a"
            audio_path.write_bytes(b"audio-bytes")
            payload = {
                "streams": [{"codec_type": "audio", "duration": "12.5"}],
                "format": {"duration": "12.5", "format_name": "mov,mp4,m4a"},
            }
            completed = SimpleNamespace(
                returncode=0,
                stdout=json.dumps(payload),
                stderr="",
            )

            with patch.object(probe.subprocess, "run", return_value=completed):
                info = probe.probe_audio_output(audio_path, "ffprobe")

        self.assertEqual(info.duration_seconds, 12.5)
        self.assertEqual(info.audio_stream_count, 1)
        self.assertEqual(info.format_name, "mov,mp4,m4a")

    def test_parse_transcribe_output_extracts_paths(self):
        output = """
Transcribed 5m 0s in 12.3s.
Text transcript: C:\\temp\\probe.txt
SRT transcript:  C:\\temp\\probe.srt
"""

        paths = probe.parse_transcribe_output(output)

        self.assertEqual(paths, [Path(r"C:\temp\probe.txt"), Path(r"C:\temp\probe.srt")])

    def test_transcribe_audio_probe_fails_on_missing_venv(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "transcribe-youtube.py").write_text("print('stub')", encoding="utf-8")

            with self.assertRaises(RuntimeError) as ctx:
                probe.transcribe_audio_probe(
                    audio_path=root / "audio.m4a",
                    transcribe_root=root,
                    output_dir=root / "transcripts",
                )

        self.assertIn("venv Python", str(ctx.exception))

    def test_run_probe_uses_streamlink_and_transcription_flow(self):
        args = argparse.Namespace(
            vod_url_or_id="123456789",
            sample_seconds=300,
            start_seconds=900,
            full=False,
            output_dir="C:\\temp\\vod-audio-probe",
            reuse_existing_audio=False,
            transcribe=True,
            transcribe_yt_root="C:\\fake\\transcribe-yt",
        )
        fake_stream = object()
        fake_plugin = FakePlugin({"audio_only": fake_stream})
        fake_probe_info = probe.AudioProbeInfo(
            path=Path(r"C:\temp\vod-audio-probe\vod-123456789-sample-300s.m4a"),
            duration_seconds=300.0,
            audio_stream_count=1,
            format_name="mov,mp4,m4a",
            size_bytes=4096,
        )

        with (
            patch.object(probe, "find_required_executable", side_effect=["ffmpeg", "ffprobe"]),
            patch.object(probe, "resolve_vod_audio_stream", return_value=(fake_plugin, "audio_only", fake_stream)),
            patch.object(probe, "extract_audio_with_ffmpeg") as extract_mock,
            patch.object(probe, "probe_audio_output", return_value=fake_probe_info),
            patch.object(
                probe,
                "transcribe_audio_probe",
                return_value=[Path(r"C:\temp\vod-audio-probe\transcripts\probe.txt")],
            ) as transcribe_mock,
        ):
            exit_code = probe.run_probe(args)

        self.assertEqual(exit_code, 0)
        extract_mock.assert_called_once()
        transcribe_mock.assert_called_once()

    def test_run_probe_reuses_existing_audio_when_requested(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            existing_audio = output_dir / "vod-123456789-sample-300s-start-900s.m4a"
            existing_audio.write_bytes(b"audio")
            args = argparse.Namespace(
                vod_url_or_id="123456789",
                sample_seconds=300,
                start_seconds=900,
                full=False,
                output_dir=str(output_dir),
                reuse_existing_audio=True,
                transcribe=False,
                transcribe_yt_root="C:\\fake\\transcribe-yt",
            )
            fake_stream = object()
            fake_plugin = FakePlugin({"audio_only": fake_stream})
            fake_probe_info = probe.AudioProbeInfo(
                path=existing_audio,
                duration_seconds=300.0,
                audio_stream_count=1,
                format_name="mov,mp4,m4a",
                size_bytes=4096,
            )

            with (
                patch.object(probe, "find_required_executable", side_effect=["ffmpeg", "ffprobe"]),
                patch.object(
                    probe,
                    "resolve_vod_audio_stream",
                    return_value=(fake_plugin, "audio_only", fake_stream),
                ),
                patch.object(probe, "stream_input_url", return_value="https://example.com/audio.m3u8"),
                patch.object(probe, "probe_input_duration_seconds", return_value=21030.0),
                patch.object(probe, "probe_audio_output", return_value=fake_probe_info),
                patch.object(probe, "extract_audio_with_ffmpeg") as extract_mock,
                patch("sys.stdout", new_callable=io.StringIO) as stdout_mock,
            ):
                exit_code = probe.run_probe(args)

        self.assertEqual(exit_code, 0)
        extract_mock.assert_not_called()
        self.assertIn("Reusing existing extracted audio file.", stdout_mock.getvalue())

    def test_main_returns_one_for_bad_input(self):
        exit_code = probe.main(["not-a-vod"])

        self.assertEqual(exit_code, 1)


if __name__ == "__main__":
    unittest.main()
