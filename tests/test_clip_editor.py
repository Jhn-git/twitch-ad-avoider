"""Focused coverage for recent-clip editing, naming, and media preview serving."""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from conftest import ConfigManagerTestCase
from src.clip_editor import (
    ClipEditSession,
    clip_filename,
    collision_safe_path,
    kebab_slug,
)
from src.web_stream_service import WebStreamService


class TestClipNaming(ConfigManagerTestCase):
    def test_title_becomes_kebab_suffix_after_channel_and_capture_time(self):
        captured_at = datetime(2026, 7, 18, 21, 14, 58)

        filename = clip_filename("jg_darhk", captured_at, "Batman Cape look")

        self.assertEqual(
            filename,
            "jg-darhk-20260718-211458-batman-cape-look.mp4",
        )
        self.assertEqual(kebab_slug("../../Résumé: Cape Look"), "resume-cape-look")

    def test_collision_safe_path_never_overwrites_an_existing_clip(self):
        directory = Path(self.temp_dir)
        filename = "jg-darhk-20260718-211458-batman-cape-look.mp4"
        (directory / filename).write_bytes(b"one")
        (directory / filename.replace(".mp4", "-2.mp4")).write_bytes(b"two")

        candidate = collision_safe_path(directory, filename)

        self.assertEqual(candidate.name, "jg-darhk-20260718-211458-batman-cape-look-3.mp4")


class TestRecentClipEditor(ConfigManagerTestCase):
    def setUp(self):
        super().setUp()
        self.events = []
        self.activity = []
        self.service = WebStreamService(
            self.config,
            self.events.append,
            lambda level, message, category=None: self.activity.append((level, message, category)),
        )
        self.addCleanup(self.service.shutdown)

    def make_edit(self) -> ClipEditSession:
        source = Path(self.temp_dir) / "recording.ts"
        source.write_bytes(b"s" * 4096)
        source_start = datetime.now() - timedelta(seconds=100)
        os.utime(source, (datetime.now().timestamp(), datetime.now().timestamp()))
        output = Path(self.temp_dir) / "clips" / "testuser-20260724-120000.mp4"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"safety" * 512)
        return ClipEditSession(
            id="clip-1",
            channel="testuser",
            captured_at=datetime(2026, 7, 24, 12, 0, 0),
            source_path=source,
            source_start_time=source_start,
            output_path=output,
            duration_seconds=30.0,
            anchor_seconds=100.0,
            rendered_start_seconds=70.0,
            rendered_end_seconds=100.0,
            selected_start_seconds=70.0,
            selected_end_seconds=100.0,
            preview_start_seconds=70.0,
            preview_end_seconds=100.0,
            preview_token="media-token",
            preview_path=output,
        )

    def test_automatic_postroll_renders_from_immutable_anchor(self):
        edit = self.make_edit()
        self.service._set_recent_clip(edit)
        source_session = Mock(status="live")

        with (
            patch.object(
                self.service,
                "_wait_for_clip_source",
                return_value=(105.0, True, False, None),
            ),
            patch.object(
                self.service,
                "_render_final_clip",
                return_value=(True, None),
            ) as render,
            patch.object(
                self.service,
                "_prepare_editor_preview",
                return_value=(True, None),
            ),
        ):
            self.service._automatic_postroll_worker(edit, source_session)

        render.assert_called_once_with(edit, 70.0, 105.0, edit.output_path)
        self.assertEqual(edit.rendered_end_seconds, 105.0)
        self.assertEqual(edit.tail_seconds, 5.0)
        self.assertEqual(edit.status, "ready")

    def test_failed_postroll_keeps_the_safety_clip(self):
        edit = self.make_edit()
        safety_bytes = edit.output_path.read_bytes()
        self.service._set_recent_clip(edit)

        with (
            patch.object(
                self.service,
                "_wait_for_clip_source",
                return_value=(105.0, True, False, None),
            ),
            patch.object(
                self.service,
                "_render_final_clip",
                return_value=(False, "NVENC and CPU render failed"),
            ),
        ):
            self.service._automatic_postroll_worker(edit, Mock(status="live"))

        self.assertEqual(edit.output_path.read_bytes(), safety_bytes)
        self.assertEqual(edit.status, "error")
        self.assertIn("render failed", edit.error)

    def test_stalled_recorder_reports_failure_without_inventing_an_endpoint(self):
        edit = self.make_edit()
        source_session = Mock(status="live")

        with (
            patch.object(self.service, "_source_available_seconds", return_value=90.0),
            patch("src.web_stream_service.time.monotonic", side_effect=[0.0, 31.0]),
        ):
            available, complete, ended, error = self.service._wait_for_clip_source(
                edit,
                105.0,
                source_session,
            )

        self.assertEqual(available, 90.0)
        self.assertFalse(complete)
        self.assertFalse(ended)
        self.assertIn("did not catch up", error)

    def test_stream_end_applies_the_verified_partial_postroll(self):
        edit = self.make_edit()
        self.service._set_recent_clip(edit)

        with (
            patch.object(
                self.service,
                "_wait_for_clip_source",
                return_value=(103.25, False, True, None),
            ),
            patch.object(
                self.service,
                "_render_final_clip",
                return_value=(True, None),
            ) as render,
            patch.object(
                self.service,
                "_prepare_editor_preview",
                return_value=(True, None),
            ),
        ):
            self.service._automatic_postroll_worker(edit, Mock(status="ended"))

        render.assert_called_once_with(edit, 70.0, 103.25, edit.output_path)
        self.assertEqual(edit.tail_seconds, 3.25)
        self.assertIn("3.2s", edit.message)

    def test_manual_extension_refreshes_preview_without_rerendering_saved_clip(self):
        edit = self.make_edit()
        edit.status = "ready"
        edit.rendered_end_seconds = 105.0
        edit.selected_end_seconds = 105.0
        edit.tail_seconds = 10.0
        self.service._set_recent_clip(edit)
        edit.operation_lock.acquire()

        with (
            patch.object(
                self.service,
                "_wait_for_clip_source",
                return_value=(110.0, True, False, None),
            ) as wait_for_source,
            patch.object(
                self.service,
                "_prepare_editor_preview",
                return_value=(True, None),
            ) as preview,
            patch.object(self.service, "_render_final_clip") as final_render,
        ):
            self.service._manual_tail_worker(edit)

        wait_for_source.assert_called_once()
        self.assertEqual(wait_for_source.call_args.args[1], 110.0)
        preview.assert_called_once_with(edit, edit.selected_start_seconds, 110.0)
        final_render.assert_not_called()
        self.assertEqual(edit.selected_end_seconds, 110.0)
        self.assertEqual(edit.status, "ready")

    def test_editor_payload_exposes_named_available_and_selected_bounds(self):
        edit = self.make_edit()
        edit.preview_start_seconds = 55.0
        edit.preview_end_seconds = 105.0
        self.service._set_recent_clip(edit)

        payload = self.service.get_recent_clip()["clip"]

        self.assertEqual(payload["available_start_seconds"], 0.0)
        self.assertEqual(payload["available_end_seconds"], 50.0)
        self.assertEqual(payload["selected_start_seconds"], 15.0)
        self.assertEqual(payload["selected_end_seconds"], 45.0)
        self.assertEqual(payload["click_timestamp"], edit.captured_at.isoformat())
        self.assertEqual(payload["saved_path"], str(edit.output_path))
        self.assertEqual(payload["computed_filename"], edit.output_path.name)
        first_preview_url = payload["preview_url"]
        edit.preview_revision += 1
        revised_payload = self.service.get_recent_clip()["clip"]
        self.assertNotEqual(revised_payload["preview_url"], first_preview_url)
        self.assertIn("?v=2", revised_payload["preview_url"])

    def test_save_uses_preview_relative_boundaries_and_requested_title(self):
        edit = self.make_edit()
        edit.status = "ready"
        edit.preview_start_seconds = 55.0
        edit.preview_end_seconds = 105.0
        edit.selected_start_seconds = 70.0
        edit.selected_end_seconds = 105.0
        self.service._set_recent_clip(edit)

        def render_success(_edit, _start, _end, destination):
            destination.write_bytes(b"edited" * 512)
            return True, None

        with patch.object(
            self.service,
            "_render_final_clip",
            side_effect=render_success,
        ) as render:
            result = self.service.save_clip_edit(
                edit.id,
                10.0,
                45.0,
                "Batman Cape look",
            )

        self.assertTrue(result["ok"])
        self.assertEqual(
            Path(result["path"]).name,
            "testuser-20260724-120000-batman-cape-look.mp4",
        )
        render.assert_called_once()
        self.assertEqual(render.call_args.args[1:3], (65.0, 100.0))

    def test_save_rejects_boundaries_outside_server_preview(self):
        edit = self.make_edit()
        edit.status = "ready"
        self.service._set_recent_clip(edit)

        result = self.service.save_clip_edit(edit.id, -1, 20, "")

        self.assertFalse(result["ok"])
        self.assertIn("outside", result["error"])

    def test_title_only_save_moves_an_output_backed_preview_without_overwriting(self):
        edit = self.make_edit()
        edit.status = "ready"
        collision = edit.output_path.with_name("testuser-20260724-120000-batman-cape-look.mp4")
        collision.write_bytes(b"existing")
        self.service._set_recent_clip(edit)

        result = self.service.save_clip_edit(
            edit.id,
            0.0,
            30.0,
            "Batman Cape look",
        )

        self.assertTrue(result["ok"])
        self.assertEqual(
            Path(result["path"]).name, "testuser-20260724-120000-batman-cape-look-2.mp4"
        )
        self.assertEqual(collision.read_bytes(), b"existing")
        self.assertEqual(edit.preview_path, Path(result["path"]))
        self.assertTrue(edit.preview_path.exists())

    def test_nvenc_failure_retries_with_libx264(self):
        edit = self.make_edit()
        destination = Path(self.temp_dir) / "preview.mp4"

        with (
            patch("src.web_stream_service.shutil.which", return_value="ffmpeg"),
            patch.object(
                self.service,
                "_run_clip_render_command",
                side_effect=[(False, "NVENC unavailable"), (True, None)],
            ) as run,
        ):
            result = self.service._render_transcoded_clip(
                edit,
                60.0,
                90.0,
                destination,
                preview=False,
            )

        self.assertEqual(result, (True, None))
        self.assertIn("h264_nvenc", run.call_args_list[0].args[0])
        self.assertIn("libx264", run.call_args_list[1].args[0])

    def test_failed_render_removes_partial_output(self):
        edit = self.make_edit()
        destination = Path(self.temp_dir) / "partial.mp4"

        def fail_with_partial(_cmd, output, *_args):
            output.write_bytes(b"partial")
            return False, "render failed"

        with (
            patch("src.web_stream_service.shutil.which", return_value="ffmpeg"),
            patch.object(
                self.service,
                "_run_clip_render_command",
                side_effect=fail_with_partial,
            ),
        ):
            result = self.service._render_transcoded_clip(
                edit,
                60.0,
                90.0,
                destination,
                preview=False,
            )

        self.assertEqual(result, (False, "render failed"))
        self.assertFalse(destination.exists())

    def test_final_render_replaces_safety_only_after_part_file_succeeds(self):
        edit = self.make_edit()
        safety_bytes = edit.output_path.read_bytes()
        replacement_bytes = b"replacement" * 512

        def render_part(_edit, _start, _end, destination, preview):
            self.assertTrue(destination.name.endswith(".part.mp4"))
            self.assertFalse(preview)
            self.assertEqual(edit.output_path.read_bytes(), safety_bytes)
            destination.write_bytes(replacement_bytes)
            return True, None

        with patch.object(
            self.service,
            "_render_transcoded_clip",
            side_effect=render_part,
        ):
            result = self.service._render_final_clip(
                edit,
                70.0,
                105.0,
                edit.output_path,
            )

        self.assertEqual(result, (True, None))
        self.assertEqual(edit.output_path.read_bytes(), replacement_bytes)

    def test_output_validation_enforces_frame_accurate_duration(self):
        destination = Path(self.temp_dir) / "validated.mp4"
        destination.write_bytes(b"clip" * 512)

        def probe_payload(duration):
            return Mock(
                returncode=0,
                stdout=(
                    '{"streams":[{"codec_type":"video","duration":"'
                    f'{duration}","avg_frame_rate":"60/1"}}],'
                    f'"format":{{"duration":"{duration}"}}}}'
                ).encode(),
                stderr=b"",
            )

        with (
            patch.object(self.service, "_get_ffprobe_executable", return_value="ffprobe"),
            patch(
                "src.web_stream_service.subprocess.run",
                return_value=probe_payload("20.430"),
            ),
        ):
            valid = self.service._validate_clip_output(destination, 20.43)

        with (
            patch.object(self.service, "_get_ffprobe_executable", return_value="ffprobe"),
            patch(
                "src.web_stream_service.subprocess.run",
                return_value=probe_payload("19.500"),
            ),
        ):
            short = self.service._validate_clip_output(destination, 20.43)

        self.assertEqual(valid, (True, None))
        self.assertFalse(short[0])
        self.assertIn("did not match", short[1])

    def test_media_preview_supports_http_range_requests(self):
        edit = self.make_edit()
        media_bytes = bytes(range(64))
        edit.preview_path.write_bytes(media_bytes)
        self.service._set_recent_clip(edit)
        url = self.service._media_url(edit.preview_token, edit.preview_revision)

        response = requests.get(url, headers={"Range": "bytes=10-19"}, timeout=5)

        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.content, media_bytes[10:20])
        self.assertEqual(response.headers["Content-Range"], "bytes 10-19/64")
