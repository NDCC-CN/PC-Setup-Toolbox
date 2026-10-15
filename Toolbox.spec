# -*- mode: python ; coding: utf-8 -*-

import glob
import os

# 收集 UCRT DLL（Win7 默认没有 Universal C Runtime，不带上会报 api-ms-win-crt-runtime-l1-1-0.dll 缺失）
_ucrt_dir = r"E:\VM\ucrt"
ucrt_binaries = [(f, ".") for f in glob.glob(os.path.join(_ucrt_dir, "*.dll"))]


a = Analysis(
    ['src/main.py'],
    pathex=[],
    binaries=ucrt_binaries,
    datas=[('rdpwrap/rdpwrap.dll', 'rdpwrap'), ('rdpwrap/rdpwrap.ini', 'rdpwrap'),
           ('packages/Windows6.1-KB2533623-x64.msu', 'packages')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Toolbox',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    uac_admin=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
)
