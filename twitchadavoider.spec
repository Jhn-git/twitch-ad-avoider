# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for TwitchAdAvoider Windows EXE
Configured for minimal Windows executable size.
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import os

# Application metadata
APP_NAME = 'TwitchAdAvoider'
VERSION = '2.0.0'

# Only collect essential streamlink components for Twitch
streamlink_hiddenimports = [
    'streamlink.plugins.twitch',
    'streamlink.stream.hls',
    'streamlink.stream.http',
    'streamlink.stream.file',
]

# Minimal data files - only what's absolutely necessary
minimal_datas = [
    ('config/settings.json', 'config'),
    ('config/favorites.json', 'config'),
    ('gui_qt/styles/dark.qss', 'gui_qt/styles'),
    ('gui_qt/styles/light.qss', 'gui_qt/styles'),
]

# Check for pre-generated pycparser tables to fix cryptography/cffi runtime issues
import glob
pycparser_tables_dir = 'build_cache/pycparser_tables'
if os.path.exists(pycparser_tables_dir):
    # Add pycparser table files to prevent runtime generation issues
    table_files = glob.glob(os.path.join(pycparser_tables_dir, '*.py'))
    for table_file in table_files:
        filename = os.path.basename(table_file)
        minimal_datas.append((table_file, 'pycparser'))
    print(f"[OK] Found {len(table_files)} pycparser table files to bundle")

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=minimal_datas,
    hiddenimports=[
        # Core application imports
        'src.twitch_viewer',
        'src.config_manager', 
        'src.validators',
        'src.exceptions',
        'src.logging_config',
        'src.status_monitor',
        'src.error_recovery',
        'src.streamlink_status',
        'src.constants',
        
        # Qt GUI imports - all components needed
        'gui_qt.stream_gui',
        'gui_qt.main_window',
        'gui_qt.components.chat_panel',
        'gui_qt.components.favorites_panel',
        'gui_qt.components.settings_panel',
        'gui_qt.components.status_display',
        'gui_qt.components.stream_control_panel',
        'gui_qt.controllers.chat_controller',
        'gui_qt.controllers.stream_controller',
        'gui_qt.controllers.validation_controller',
        'gui_qt.styles',

        # PySide6 Qt imports
        'PySide6',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        
        # Streamlink essentials
        *streamlink_hiddenimports,
        
        # Standard library essentials
        'json',
        'subprocess',
        'pathlib',
        'threading',
        'logging',
        'logging.handlers',
        'uuid',
        'shutil',
        
        # URL and network modules (fix for ipaddress issue)
        'ipaddress',
        'urllib',
        'urllib.parse',
        'urllib.request',
        'urllib.error',
        
        # Import system modules
        'importlib',
        'importlib.util',
        'importlib.machinery',
        
        # External dependencies
        'requests',
        'typing_extensions',
        
        # Platform-specific imports
        'platform',
        'os',
        'sys',
        're',
        'time',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude large unnecessary modules
        'matplotlib', 'numpy', 'pandas', 'scipy', 'IPython', 'jupyter',
        'pytest', 'coverage', 'sphinx', 'mypy', 'black', 'flake8',
        'PIL', 'Pillow',
        'pygame',
        
        # Exclude unused streamlink plugins to reduce size
        'streamlink.plugins.youtube', 'streamlink.plugins.dailymotion',
        'streamlink.plugins.kick', 'streamlink.plugins.bilibili',
        
        # Exclude GUI frameworks we don't use
        'PyQt5', 'PyQt6', 'PySide2', 'wxPython', 'tkinter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# Create Python archive
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=APP_NAME,
    debug=True,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)