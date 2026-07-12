# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

block_cipher = None

# Base directory tracking
BASE_DIR = os.path.abspath(os.getcwd())

a = Analysis(
    [os.path.join(BASE_DIR, 'src', 'catsprayer', 'main.py')],
    pathex=[os.path.join(BASE_DIR, 'src')],
    binaries=[],
    datas=[
        # (Source path on disk, Destination location inside bundle)
        (os.path.join(BASE_DIR, 'config', 'config.json'), 'config'),
        (os.path.join(BASE_DIR, 'src', 'catsprayer', 'models'), 'catsprayer/models'),
        (os.path.join(BASE_DIR, 'data'), 'data'),
        (os.path.join(BASE_DIR, 'pyproject.toml'), '.'),  # Single, clean root location
    ],
    hiddenimports=[
        'catsprayer.detector',
        'catsprayer.sprayer',
        'catsprayer.event_recorder',
        'catsprayer.config',
        'catsprayer.gui',
        'catsprayer.camera',
        'catsprayer.imx500',
        'PIL._tkinter_finder'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CatSprayerApp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='CatSprayerApp',
)
