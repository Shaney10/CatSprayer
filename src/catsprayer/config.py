"""
CatSprayer Configuration Loader

Loads project settings from pyproject.toml.
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path


# Dynamic root calculation to support both standard execution and PyInstaller bundles
if getattr(sys, 'frozen', False):
    # When bundled, PyInstaller places assets directly in the extraction root
    PROJECT_ROOT = Path(sys._MEIPASS)
else:
    # Local development mode uses the standard 2-level-up parent hierarchy
    PROJECT_ROOT = Path(__file__).parents[2]

CONFIG_FILE = PROJECT_ROOT / "pyproject.toml"


def load_config():
    with open(
        CONFIG_FILE,
        "rb"
    ) as file:
        config = tomllib.load(file)

    return config["tool"]["catsprayer"]


CONFIG = load_config()
