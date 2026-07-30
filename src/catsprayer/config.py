"""
CatSprayer Configuration Loader

Loads project settings from pyproject.toml.
"""

from __future__ import annotations

import sys
import tomllib
import tomlkit
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


def save_detector_settings(new_values: dict) -> None:
    """
    Write updated [tool.catsprayer.detector] values back to pyproject.toml,
    preserving all existing comments/formatting via tomlkit. Only keys
    present in new_values are changed; everything else in the file
    (including other [tool.catsprayer.*] tables) is left untouched.

    Note: this writes to CONFIG_FILE, which only points at a real,
    persistent pyproject.toml in normal (non-frozen) execution. Changes
    take effect on next app restart, not live.
    """

    if getattr(sys, 'frozen', False):
        raise RuntimeError(
            "Cannot save settings from a bundled/frozen build: "
            "pyproject.toml is not available at runtime in that mode."
        )

    with open(CONFIG_FILE, "r", encoding="utf-8") as file:
        doc = tomlkit.parse(file.read())

    detector_table = doc["tool"]["catsprayer"]["detector"]

    for key, value in new_values.items():
        detector_table[key] = value

    with open(CONFIG_FILE, "w", encoding="utf-8") as file:
        file.write(tomlkit.dumps(doc))


CONFIG = load_config()
