# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the pywebview TwitchAdAvoider app."""

import os

from PyInstaller.utils.hooks import collect_submodules

APP_NAME = "twitchadavoider"
ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
ICON_PATH = os.path.join(ROOT, "assets", "twitch-cartoon-logo.ico")


def collect_tree(source, destination, skip_dirs=()):
    entries = []
    if not os.path.isdir(source):
        return entries
    for root, dirs, files in os.walk(source):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for file_name in files:
            file_path = os.path.join(root, file_name)
            rel_dir = os.path.relpath(root, source)
            target_dir = destination if rel_dir == "." else os.path.join(destination, rel_dir)
            entries.append((file_path, target_dir))
    return entries


datas = []
datas.extend(collect_tree(os.path.join(ROOT, "gui_web"), "gui_web", skip_dirs=("demo-assets",)))
datas.extend(collect_tree(os.path.join(ROOT, "assets"), "assets"))

hiddenimports = [
    "main",
    "src.config_manager",
    "src.constants",
    "src.exceptions",
    "src.favorites_manager",
    "src.logging_config",
    "src.runtime_check",
    "src.status_monitor",
    "src.stream_preview",
    "src.validators",
    "src.webapi",
    "src.web_stream_service",
    "requests",
    "webview",
    "webview.platforms.winforms",
    "webview.platforms.edgechromium",
    *collect_submodules("streamlink"),
]

a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib",
        "numpy",
        "pandas",
        "scipy",
        "IPython",
        "jupyter",
        "pytest",
        "coverage",
        "sphinx",
        "mypy",
        "black",
        "flake8",
        "PIL",
        "Pillow",
        "pygame",
        "tkinter",
        "wxPython",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON_PATH,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name=APP_NAME,
)
