from __future__ import annotations

import json
from typing import Any

from catsprayer.paths import CONFIG_FILE


class Config:
    def __init__(self) -> None:
        if not CONFIG_FILE.exists():
            raise FileNotFoundError(
                f"Configuration file not found:\n{CONFIG_FILE}"
            )

        self.reload()

    def reload(self) -> None:
        with CONFIG_FILE.open("r", encoding="utf-8") as file:
            self._data = json.load(file)

    def get(self, *keys: str, default: Any = None) -> Any:
        value: Any = self._data

        for key in keys:
            if not isinstance(value, dict):
                return default

            value = value.get(key)

            if value is None:
                return default

        return value
