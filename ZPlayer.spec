# -*- mode: python ; coding: utf-8 -*-
"""
ZPlayer PyInstaller 打包配置。

生成 macOS .app bundle。
用法: pyinstaller ZPlayer.spec
"""

from pathlib import Path

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'PyQt6.QtSvg',
        'qtawesome',
        'qtawesome.iconic_font',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        'torch',
        'torchvision',
        'torchaudio',
        'whisper',
        'IPython',
        'jupyter',
        'matplotlib',
        'scipy',
        'pandas',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# qtawesome 字体资源由 PyInstaller 内置 hook-qtawesome.py 自动收集

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# macOS .icns 图标路径（构建前由 generate_icon.py 生成）
_icon_path = 'ZPlayer.icns' if Path('ZPlayer.icns').exists() else None

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ZPlayer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=_icon_path,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='ZPlayer',
)

app = BUNDLE(
    coll,
    name='ZPlayer.app',
    icon=_icon_path,
    bundle_identifier='com.zplayer.app',
    info_plist={
        'CFBundleDisplayName': 'ZPlayer',
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleVersion': '1.0.0',
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '10.14',
        'NSMicrophoneUsageDescription': 'ZPlayer 需要访问麦克风以进行语音识别（可选功能）。',
    },
)
