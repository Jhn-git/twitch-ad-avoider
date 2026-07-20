"""Serve gui_web/ for browser-only UI demo/smoke testing (?demo=1).

Generates a small local HLS test clip on first run (via ffmpeg) so the demo
harness has a real playback_url to exercise actual video buffering/seeking,
instead of the video player area silently staying empty. The generated clip
lives in gui_web/demo-assets/, which is gitignored and skipped by the
PyInstaller build - it's local test fixture data, not shipped or committed.
"""

import http.server
import os
import shutil
import socketserver
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GUI_WEB = os.path.join(ROOT, "gui_web")
DEMO_ASSETS = os.path.join(GUI_WEB, "demo-assets")
PLAYLIST = os.path.join(DEMO_ASSETS, "stream.m3u8")
PORT = 8743

# Silent test pattern with a burned-in elapsed-time readout, so a specific
# scrub position is easy to sanity-check by eye during manual QA.
FFMPEG_ARGS = [
    "ffmpeg",
    "-y",
    "-f",
    "lavfi",
    "-i",
    "testsrc2=size=640x360:rate=30:duration=60",
    "-vf",
    "drawtext=text='%{pts\\:hms}':fontsize=48:fontcolor=white:"
    "x=(w-text_w)/2:y=(h-text_h)/2:box=1:boxcolor=black@0.6:boxborderw=10",
    "-c:v",
    "libx264",
    "-profile:v",
    "baseline",
    "-pix_fmt",
    "yuv420p",
    "-g",
    "30",
    "-keyint_min",
    "30",
    "-an",
    "-f",
    "hls",
    "-hls_time",
    "4",
    "-hls_playlist_type",
    "vod",
    "-hls_segment_filename",
    os.path.join(DEMO_ASSETS, "stream_%03d.ts"),
    PLAYLIST,
]


def ensure_demo_stream():
    if os.path.isfile(PLAYLIST):
        return
    if not shutil.which("ffmpeg"):
        print(
            "ffmpeg not found on PATH - skipping demo stream generation; "
            "the player area will stay empty in demo mode.",
            file=sys.stderr,
        )
        return
    os.makedirs(DEMO_ASSETS, exist_ok=True)
    print("Generating demo HLS test clip (first run only)...")
    subprocess.run(FFMPEG_ARGS, cwd=ROOT, check=True)


def main():
    ensure_demo_stream()
    os.chdir(GUI_WEB)
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("127.0.0.1", PORT), handler) as httpd:
        print(f"Serving gui_web/ at http://127.0.0.1:{PORT}")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
