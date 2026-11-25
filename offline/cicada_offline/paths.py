"""Where Cicada Offline keeps things. Everything lives next to the app (portable, and on D: here):
models/ for the downloaded engines, data/ for records, history and settings. CICADA_OFFLINE_HOME
moves data/ only (tests point it at a temporary folder and still use the downloaded models);
CICADA_OFFLINE_MODELS moves models/."""
from __future__ import annotations

import os
import sys

PKG = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(PKG)  # offline/
UI = os.path.join(APP, "ui")


def home() -> str:
    return os.environ.get("CICADA_OFFLINE_HOME") or APP


def models() -> str:
    return os.environ.get("CICADA_OFFLINE_MODELS") or os.path.join(APP, "models")


def data() -> str:
    return os.path.join(home(), "data")


def use_cicada_core() -> None:
    """Makes `cicada.core` (the upstream Linux port's UI-free engine: segmenter, record format,
    session store) importable: bundled next to the package, or in the fork's linux/ folder."""
    for root in (os.path.join(APP, "vendor"), os.path.join(os.path.dirname(APP), "linux")):
        if os.path.isdir(os.path.join(root, "cicada", "core")):
            if root not in sys.path:
                sys.path.insert(0, root)
            return
    raise ImportError("cicada core not found (expected linux/cicada/core in the fork)")
