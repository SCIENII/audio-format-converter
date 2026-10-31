# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 打包配置
"""
import sys
from pathlib import Path

block_cipher = None

# 项目根目录
app_dir = Path(SPECPATH).resolve()

a = Analysis(
    [str(app_dir / "converter_gui.py")],
    pathex=[str(app_dir)],
    binaries=[],
    datas=[
        (str(app_dir / "icon.ico"), "."),
        (str(app_dir / "icon.png"), "."),
        (str(app_dir / "core"), "core"),
    ],
    hiddenimports=[
        "Crypto",
        "Crypto.Cipher",
        "Crypto.Protocol",
        "Crypto.Util",
        "mutagen",
        "mutagen.mp3",
        "mutagen.id3",
        "mutagen.flac",
        "mutagen.ogg",
        "queue",
        "threading",
        "tkinterdnd2",
        "PIL",
        "PIL._tkinter_finder",
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="音频格式转换器",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,           # 不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(app_dir / "icon.ico"),
)

# 额外文件：复制 ffmpeg（可选）
