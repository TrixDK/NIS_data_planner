from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from version_info import APP_NAME


SOURCE_DIR = Path(__file__).resolve().parent
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", SOURCE_DIR))
EXECUTABLE_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else SOURCE_DIR

_local_app_data = os.environ.get("LOCALAPPDATA")
if _local_app_data:
    DATA_DIR = Path(_local_app_data) / APP_NAME
else:
    DATA_DIR = Path.home() / ".nis-data-center-planner"

DB_PATH = DATA_DIR / "nis_planner_v1.db"
CATALOG_PATH = DATA_DIR / "hardware_catalog.json"
SETTINGS_PATH = DATA_DIR / "settings.json"
EXPORT_DIR = Path.home() / "Documents"


def initialize_user_data() -> None:
    """Create persistent per-user storage and migrate portable data when available."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    legacy_db = EXECUTABLE_DIR / "nis_planner_v1.db"
    if not DB_PATH.exists() and legacy_db.exists() and legacy_db.resolve() != DB_PATH.resolve():
        shutil.copy2(legacy_db, DB_PATH)

    bundled_catalog = RESOURCE_DIR / "hardware_catalog.json"
    legacy_catalog = EXECUTABLE_DIR / "hardware_catalog.json"
    source_catalog = legacy_catalog if legacy_catalog.exists() else bundled_catalog
    if not CATALOG_PATH.exists() and source_catalog.exists() and source_catalog.resolve() != CATALOG_PATH.resolve():
        shutil.copy2(source_catalog, CATALOG_PATH)
