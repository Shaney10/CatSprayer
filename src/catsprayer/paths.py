"""
Common filesystem paths for the CatSprayer project.
"""

from pathlib import Path

# src/catsprayer/
PACKAGE_DIR = Path(__file__).resolve().parent

# CatSprayer/
PROJECT_ROOT = PACKAGE_DIR.parent.parent

CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"

VIDEOS_DIR = DATA_DIR / "videos"
LOGS_DIR = DATA_DIR / "logs"
SNAPSHOTS_DIR = DATA_DIR / "snapshots"
FAVORITES_DIR = DATA_DIR / "favorites"

CONFIG_FILE = CONFIG_DIR / "config.json"
