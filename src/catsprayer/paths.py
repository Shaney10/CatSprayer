"""
Common filesystem paths for the CatSprayer project.
"""

import sys
from pathlib import Path

# Identify where the actual python files or binary structures live
PACKAGE_DIR = Path(__file__).resolve().parent

# Check if running inside a compiled PyInstaller bundle
if getattr(sys, 'frozen', False):
    # PyInstaller splits files into an '_internal' directory in multi-file mode.
    # We explicitly anchor all dynamic data storage directly to your permanent user home directory.
    PROJECT_ROOT = Path("/home/haney/CatSprayer")
else:
    # Standard local development fallback
    PROJECT_ROOT = PACKAGE_DIR.parent.parent

CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"

VIDEOS_DIR = DATA_DIR / "videos"
LOGS_DIR = DATA_DIR / "logs"
SNAPSHOTS_DIR = DATA_DIR / "snapshots"
FAVORITES_DIR = DATA_DIR / "favorites"

CONFIG_FILE = CONFIG_DIR / "config.json"
