# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# Windows için
a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('assets', 'assets'),
        ('models', 'models'),
        ('js', 'js'),
        ('styles', 'styles'),
        ('templates', 'templates'),
        ('music', 'music'),
        ('yolov8n.pt', '.'),
    ],
    hiddenimports=[
        'edge_tts',
        'yt_dlp',
        'PIL',
        'psutil',
        'google.genai',
        'ultralytics',
        'rembg',
        'mediapipe',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt5', 'PySide6'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Visionary Navigator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
