"""Settings and the text-translation history, as small JSON files in data/ (written through a temp
file and a rename, so a crash never leaves half a file)."""
from __future__ import annotations

import json
import os
import threading
import time

from . import catalog, paths

DEFAULTS = {
    "mtModel": catalog.DEFAULT["mt"],
    "asrModel": catalog.DEFAULT["asr"],
    "device": "auto",  # auto | cpu
    "textSrc": "auto",
    "textTgt": "ko",
    "liveSource": "system",  # system | mic
    "liveSrc": "auto",
    "liveTgt": "id",
    "overlay": False,
    "overlaySize": 28,
    "translateAsYouType": True,
    "keepHistory": True,
}
HISTORY_MAX = 200


def _read(path: str, fallback):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return fallback


def _write(path: str, value) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


class Settings:
    def __init__(self):
        self.path = os.path.join(paths.data(), "settings.json")
        self._gate = threading.Lock()
        saved = _read(self.path, {})
        self.values = {**DEFAULTS, **{k: v for k, v in saved.items() if k in DEFAULTS}}

    def get(self, key: str):
        return self.values[key]

    def update(self, patch: dict) -> dict:
        with self._gate:
            for k, v in patch.items():
                if k in DEFAULTS and isinstance(v, type(DEFAULTS[k])):
                    self.values[k] = v
            _write(self.path, self.values)
            return dict(self.values)


class History:
    def __init__(self):
        self.path = os.path.join(paths.data(), "history.json")
        self._gate = threading.Lock()
        self.items: list = _read(self.path, [])

    def add(self, src: str, tgt: str, text: str, out: str) -> dict:
        item = {"at": time.time(), "src": src, "tgt": tgt, "text": text, "out": out}
        with self._gate:
            # Typing as you go would leave every prefix; keep only the latest of a growing text.
            if self.items and (text.startswith(self.items[0]["text"]) or self.items[0]["text"].startswith(text)) \
                    and self.items[0]["tgt"] == tgt and time.time() - self.items[0]["at"] < 120:
                self.items[0] = item
            else:
                self.items.insert(0, item)
            del self.items[HISTORY_MAX:]
            _write(self.path, self.items)
        return item

    def clear(self) -> None:
        with self._gate:
            self.items = []
            _write(self.path, self.items)
