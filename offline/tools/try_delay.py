"""How long live listening takes and how much it gets wrong, the way a person meets it: FLEURS clips
(tools/get_fleurs.py) joined into one stream with short pauses, played in real time through the live
pipeline. For every line: how many seconds after the sentence ended its words showed up, and how many
after that the finished line (translated or fixed). Then the word error rate over the whole stream.

    python -X utf8 tools/try_delay.py [--penalar] [--laptop] [--clips N] [--src id|auto] <fleurs-lang-folder> <target>

--laptop: the speech made quiet (about -38 dBFS) over room hiss (-50 dBFS), as a laptop's own microphone
hears someone at the desk; measured on this PC's Intel array: the room sits at -50 dBFS."""
from __future__ import annotations

import os
import re
import sys
import tempfile
import time
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SENADA_HOME", tempfile.mkdtemp(prefix="senada-delay-"))

from senada import catalog, paths  # noqa: E402

catalog.use_gpu_libraries()

import numpy as np  # noqa: E402
from faster_whisper.audio import decode_audio  # noqa: E402

from senada.asr import Recognizer  # noqa: E402
from senada.core import Paths, SessionStore  # noqa: E402
from senada.live import LiveSession  # noqa: E402
from senada.translate import Translator  # noqa: E402

RATE = 16000


def stream(folder: str, n: int, laptop: bool, out: str) -> list[str]:
    """Writes the joined clips to `out`; returns their reference texts."""
    rows = [line.rstrip("\n").split("\t") for line in open(os.path.join(folder, "clips.tsv"), encoding="utf-8")][:n]
    rng = np.random.default_rng(7)
    parts = []
    for name, _text, *_ in rows:
        x = decode_audio(os.path.join(folder, name), sampling_rate=RATE)
        if laptop:
            x = x / max(1e-6, float(np.sqrt((x ** 2).mean()))) * 10 ** (-38 / 20)
        parts += [x, np.zeros(int(RATE * rng.uniform(0.8, 1.6)), dtype=np.float32)]
    audio = np.concatenate([np.zeros(RATE // 2, dtype=np.float32)] + parts)
    if laptop:
        audio = audio + rng.normal(0, 10 ** (-50 / 20), len(audio)).astype(np.float32)
    pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
    with wave.open(out, "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(RATE), w.writeframes(pcm.tobytes())
    return [r[1] for r in rows]


def words(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def wer(ref: list[str], hyp: list[str]) -> float:
    d = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        prev, d[0] = d[0], i
        for j, h in enumerate(hyp, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (r != h))
    return d[-1] / max(1, len(ref))


def main(argv: list[str]) -> int:
    penalar, laptop, n, src, fast, prompt = False, False, 8, "id", False, True
    while argv and argv[0].startswith("--"):
        flag = argv.pop(0)
        if flag == "--penalar":
            penalar = True
        elif flag == "--laptop":
            laptop = True
        elif flag == "--clips":
            n = int(argv.pop(0))
        elif flag == "--src":
            src = argv.pop(0)
        elif flag == "--fast":  # as fast as it reads: for the error rate only, the delays mean nothing then
            fast = True
        elif flag == "--no-prompt":  # Whisper without the sentence before
            prompt = False
    folder, tgt = argv
    wav = os.path.join(os.environ["SENADA_HOME"], "stream.wav")
    refs = stream(folder, n, laptop, wav)
    Paths.home_override = paths.data()
    reasoner = None
    if penalar:
        from senada.reason import Reasoner
        reasoner = Reasoner(catalog.DEFAULT["llm"])
    recognizer = Recognizer("whisper-turbo")
    translator = Translator(device="cpu" if reasoner else "auto")
    seen: dict[str, list] = {}
    t0 = [0.0]

    looks: dict[str, float] = {}  # line id -> when its words first showed grey, while still being spoken

    def on_event(e):
        if e["type"] == "line":
            seen.setdefault(e["id"], []).append((time.monotonic() - t0[0], e))
        elif e["type"] == "partial":
            looks.setdefault(e["id"], time.monotonic() - t0[0])

    session = LiveSession(recognizer, translator, SessionStore(), "file", src, tgt, on_event, wav_path=wav,
                          wav_speed=0 if fast else 1.0, reasoner=reasoner, candidates=["id", "ko", "en"])
    if not prompt:
        session._prompt = lambda lang: ""
    ends = {}
    cut = session._segmenter.on_segment

    def mark(stretch):
        ends[f"h1-{stretch.index}"] = stretch.start + len(stretch.samples) / 2 / RATE
        cut(stretch)
    session._segmenter.on_segment = mark
    # The file is fed a little slower than real time (a sleep per 100 ms block plus the work done on it),
    # so a delay is counted from when the sentence's last sound went in, as a microphone would deliver it.
    fed: list[tuple[float, float]] = []  # (seconds of audio fed so far, when)
    feed = session._audio

    def audio(pcm):
        feed(pcm)
        fed.append(((fed[-1][0] if fed else 0.0) + len(pcm) / RATE, time.monotonic() - t0[0]))
    session._audio = audio

    def arrived(at: float) -> float:
        return next((w for s, w in fed if s >= at - 1e-6), fed[-1][1] if fed else at)
    t0[0] = time.monotonic()
    session.start()
    session._source._thread.join()
    session.stop(wait=120)
    if fed:
        print(f"audio {fed[-1][0]:.0f}s fed in {fed[-1][1]:.0f}s")
    ends = {k: arrived(v) for k, v in ends.items()}
    first, final, heard, lead = [], [], [], []
    for lid, evs in seen.items():
        end = ends.get(lid, 0)
        first.append(evs[0][0] - end)
        final.append(evs[-1][0] - end)
        heard.append(evs[-1][1]["src"])
        if lid in looks:
            lead.append(end - looks[lid])  # how long before the sentence ended its first words were up
        print(f"{lid:6} +{evs[0][0] - end:5.1f}s words  +{evs[-1][0] - end:5.1f}s done  {evs[-1][1]['src']}")
    if reasoner:
        reasoner.close()
    med = lambda v: sorted(v)[len(v) // 2] if v else 0
    print(f"lines {len(seen)}  words shown: median {med(first):.1f}s max {max(first or [0]):.1f}s  "
          f"done: median {med(final):.1f}s max {max(final or [0]):.1f}s  "
          f"WER {wer(words(' '.join(refs)), words(' '.join(heard))) * 100:.1f}%")
    if lead:
        print(f"grey words while speaking: {len(lead)}/{len(seen)} lines, shown median {med(lead):.1f}s before the sentence ended")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
