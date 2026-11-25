"""Feeds WAV files through the live pipeline (no window, no sound card) and prints each line.

    python -X utf8 tools/try_live.py [--penalar [model]] [--asr whisper-turbo] [--hear id,ko,en] [--topic T]
        [--words W] <target-lang> <file.wav> [more.wav ...]

Records go to a throwaway folder (SENADA_HOME, or a temp dir); models come from the app."""
from __future__ import annotations

import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SENADA_HOME", tempfile.mkdtemp(prefix="senada-try-"))

from senada import catalog, paths  # noqa: E402

catalog.use_gpu_libraries()

from senada.asr import Recognizer  # noqa: E402
from senada.core import Paths, SessionStore  # noqa: E402
from senada.live import LiveSession  # noqa: E402
from senada.translate import Translator  # noqa: E402


def main(argv: list[str]) -> int:
    reasoner, topic, words, asr_model, hear = None, "", "", None, None
    t = time.time()
    while argv and argv[0].startswith("--"):
        flag = argv.pop(0)
        if flag == "--penalar":
            model = argv.pop(0) if argv and argv[0] in catalog.BY_ID else catalog.DEFAULT["llm"]
            from senada.reason import Reasoner
            reasoner = Reasoner(model)
        elif flag == "--topic":
            topic = argv.pop(0)
        elif flag == "--words":
            words = argv.pop(0)
        elif flag == "--asr":
            asr_model = argv.pop(0)
        elif flag == "--hear":  # the languages "auto" chooses from, comma-separated (the app's liveLangs)
            hear = argv.pop(0).split(",")
    tgt, files = argv[0], argv[1:]
    Paths.home_override = paths.data()
    recognizer, translator = Recognizer(asr_model), Translator(device="cpu" if reasoner else "auto")
    print(f"engines {time.time() - t:.1f}s  whisper={recognizer.device} nllb={translator.device}"
          f" penalar={reasoner.device if reasoner else 'off'}")
    store = SessionStore()
    failures = 0
    for f in files:
        events: list[dict] = []
        session = LiveSession(recognizer, translator, store, "file", "auto", tgt, events.append, wav_path=f, wav_speed=0,
                              reasoner=reasoner, hints=lambda: (topic, words), candidates=hear)
        t = time.time()
        session.start()
        session._source._thread.join()
        session.stop()
        print(f"== {os.path.basename(f)}  {time.time() - t:.1f}s")
        for e in events:
            if e["type"] == "line" and not e.get("translating"):
                print(f"  [{e['srcLang']}] {e['src']}\n     => {e['dst']}  ({e.get('translateMs')} ms)")
                if e.get("fixes"):
                    print(f"     fixed: {e['fixes']}")
                if e.get("note"):
                    print(f"     note: {e['note']}")
            elif e["type"] == "error":
                failures += 1
                print("  ERROR", e["message"])
    print("records:", sorted(os.listdir(Paths.sessions())))
    if reasoner:
        reasoner.close()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
