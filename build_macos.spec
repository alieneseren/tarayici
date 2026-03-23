# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# macOS için
a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('assets', 'assets'),
        ('models', 'models'),
        ('js', 'js'),
        ('styles', 'styles'),
        ('icons', 'icons'),
    ],
    hiddenimports=[
        'edge_tts',
        'yt_dlp',
        'pillow',
        'psutil',
        'google.genai',
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
    [],
    exclude_binaries=True,
    name='Visionary Navigator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Visionary Navigator',
)

app = BUNDLE(
    coll,
    name='Visionary Navigator.app',
    icon=None,
    bundle_identifier='com.visionary.navigator',
    version='1.0.0',
    info_plist={
        'NSPrincipalClass': 'NSApplication',
        'NSHighResolutionCapable': 'True',
        'NSCameraUsageDescription': 'Jest kontrolü ve AR özellikleri için kamera erişimi gereklidir.',
        'NSMicrophoneUsageDescription': 'Sesli asistan için mikrofon erişimi gereklidir.',
    },
)
