# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_data_files


reportlab_data = collect_data_files("reportlab", includes=["fonts/*"])
reportlab_hidden = [
    "reportlab.lib.colors",
    "reportlab.lib.enums",
    "reportlab.lib.pagesizes",
    "reportlab.lib.styles",
    "reportlab.lib.units",
    "reportlab.pdfbase._fontdata",
    "reportlab.pdfgen.canvas",
    "reportlab.platypus",
]
debug_build = os.environ.get("NIS_DEBUG_BUILD") == "1"
bundle_name = "NISDataCenterPlannerDebug" if debug_build else "NISDataCenterPlanner"

a = Analysis(
    ["app_v1.py"],
    pathex=[],
    binaries=[],
    datas=[("hardware_catalog.json", ".")] + reportlab_data,
    hiddenimports=reportlab_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["numpy", "psutil", "yaml", "pyreadline3", "pygments"],
    noarchive=False,
    optimize=1,
)

# Qt for Windows uses the ICU forwarding DLL supplied by Windows itself. Build
# environments can have an unrelated ICU implementation on PATH (for example
# Poppler), which PyInstaller may otherwise copy into the bundle and load ahead
# of the Windows DLL. That produces a QtCore "procedure could not be found"
# error at startup.
a.binaries = [
    item
    for item in a.binaries
    if os.path.basename(item[0]).lower() != "icuuc.dll"
    and not os.path.basename(item[0]).lower().startswith("icudt")
]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=bundle_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=debug_build,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version="windows_version_info.txt",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=bundle_name,
)
