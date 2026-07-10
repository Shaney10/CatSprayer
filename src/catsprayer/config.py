"""
CatSprayer Configuration Loader

Loads project settings from pyproject.toml.
"""

from __future__ import annotations

import tomllib
from pathlib import Path


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
