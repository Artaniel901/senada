"""Feeds WAV files through the live pipeline (no window, no sound card) and prints each line.

    python -X utf8 tools/try_live.py <target-lang> <file.wav> [more.wav ...]

Records go to a throwaway folder (CICADA_OFFLINE_HOME, or a temp dir); models come from the app."""
from __future__ import annotations

import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("CICADA_OFFLINE_HOME", tempfile.mkdtemp(prefix="cicada-offline-try-"))

from cicada_offline import catalog, paths  # noqa: E402

catalog.use_gpu_libraries()

from cicada_offline.asr import Recognizer  # noqa: E402
from cicada_offline.core import Paths, SessionStore  # noqa: E402
from cicada_offline.live import LiveSession  # noqa: E402
from cicada_offline.translate import Translator  # noqa: E402


def main(argv: list[str]) -> int:
    tgt, files = argv[0], argv[1:]
    Paths.home_override = paths.data()
    t = time.time()
    recognizer, translator = Recognizer(), Translator()
    print(f"engines {time.time() - t:.1f}s  whisper={recognizer.device} nllb={translator.device}")
    store = SessionStore()
    failures = 0
    for f in files:
        events: list[dict] = []
        session = LiveSession(recognizer, translator, store, "file", "auto", tgt, events.append, wav_path=f, wav_speed=0)
        t = time.time()
        session.start()
        session._source._thread.join()
        session.stop()
        print(f"== {os.path.basename(f)}  {time.time() - t:.1f}s")
        for e in events:
            if e["type"] == "line":
                print(f"  [{e['srcLang']}] {e['src']}\n     => {e['dst']}")
            elif e["type"] == "error":
                failures += 1
                print("  ERROR", e["message"])
    print("records:", sorted(os.listdir(Paths.sessions())))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
