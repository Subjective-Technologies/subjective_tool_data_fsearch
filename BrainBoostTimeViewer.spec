# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:\\brainboost\\Subjective\\com_subjective_tools\\subjective_tool_data_fsearch\\brainboost_data_tools_time_viewer.py'],
    pathex=[],
    binaries=[],
    datas=[('C:\\brainboost\\Subjective\\com_subjective_tools\\subjective_tool_data_fsearch\\database_client.py', '.')],
    hiddenimports=['PyQt5', 'PyQt5.QtWidgets', 'PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.QtSvg', 'sqlite3'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='BrainBoostTimeViewer',
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
    name='BrainBoostTimeViewer',
)
