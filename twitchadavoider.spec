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
        'src.twitch_chat_client',
        'src.auth_manager',
        'src.constants',
        
        # GUI imports - all components needed
        'gui.stream_gui',
        'gui.status_manager',
        'gui.favorites_manager',
        'gui.themes',
        'gui.components.main_window',
        'gui.components.favorites_panel',
        'gui.components.stream_control_panel',
        'gui.components.chat_panel',
        'gui.controllers.stream_controller',
        'gui.controllers.config_controller',
        'gui.controllers.validation_controller',
        'gui.controllers.theme_controller',
        'gui.controllers.chat_controller',
        'gui.utils.datetime_utility',
        'gui.utils.spinner_manager',
        
        # Streamlink essentials
        *streamlink_hiddenimports,
        
        # Standard library essentials
        'tkinter',
        'tkinter.ttk',
        'tkinter.messagebox',
        'tkinter.filedialog',
        'json',
        'subprocess',
        'pathlib',
        'threading',
        'logging',
        'logging.handlers',
        'uuid',
        'shutil',
        
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
        'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'wxPython',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
    optimize=0,
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
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)