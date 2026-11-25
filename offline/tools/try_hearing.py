"""Scores the hearing on recorded people (for example Google FLEURS clips): which language each clip
was heard as, how many words came out right, and how long Whisper took.

    python -X utf8 tools/try_hearing.py [--asr whisper-turbo] [--hear id,ko,en] <folder> [<out.tsv>]

<folder> holds one folder per language (FLEURS names like id_id, ko_kr, en_us, or our ids), each with
audio clips and clips.tsv: `file<TAB>what was said`. Every clip is heard twice: choosing only
among --hear (what the app does) and choosing from all 99 Whisper languages."""
from __future__ import annotations

import os
import re
import sys
import time
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from senada import catalog, languages  # noqa: E402

catalog.use_gpu_libraries()

from senada.asr import Recognizer  # noqa: E402

FLEURS = {"id_id": "id", "ko_kr": "ko", "en_us": "en", "jv_id": "jv", "ms_my": "ms", "su_id": "su",
          "vi_vn": "vi", "ja_jp": "ja", "cmn_hans_cn": "zh", "tl_ph": "tl", "th_th": "th"}


def pcm16k(path: str) -> bytes:
    """Any audio file as 16 kHz mono 16-bit (FLEURS ships 32-bit float WAV)."""
    import numpy as np
    from faster_whisper.audio import decode_audio
    audio = decode_audio(path, sampling_rate=16000)
    return (np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes()


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    return re.sub(r"[^\w\s]", " ", text)


def errors(ref: str, got: str, by_char: bool) -> tuple[int, int]:
    """Edit distance and reference length, over words (or characters for Korean, which spaces loosely)."""
    a = list(_norm(ref).replace(" ", "")) if by_char else _norm(ref).split()
    b = list(_norm(got).replace(" ", "")) if by_char else _norm(got).split()
    row = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        prev, row[0] = row[0], i
        for j, y in enumerate(b, 1):
            prev, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, prev + (x != y))
    return row[-1], len(a)


def main(argv: list[str]) -> int:
    asr_model, hear = "whisper-turbo", ["id", "ko", "en"]
    while argv and argv[0].startswith("--"):
        flag = argv.pop(0)
        if flag == "--asr":
            asr_model = argv.pop(0)
        elif flag == "--hear":
            hear = argv.pop(0).split(",")
    folder, out_path = argv[0], (argv[1] if len(argv) > 1 else None)
    rec = Recognizer(asr_model)
    print(f"whisper={asr_model} on {rec.device}, choosing among {','.join(hear)}")
    rec.hear(b"\0\0" * 16000, candidates=hear)  # first call warms the GPU up
    out = open(out_path, "w", encoding="utf-8") if out_path else None
    if out:
        out.write("lang\tfile\tseconds\tasr_s\theard_as\tall99_as\terr\tlen\tsaid\theard\n")
    total = {}
    for sub in sorted(os.listdir(folder)):
        lang = FLEURS.get(sub, sub)
        clips = os.path.join(folder, sub, "clips.tsv")
        if not os.path.exists(clips):
            continue
        t = total.setdefault(lang, {"n": 0, "ok": 0, "ok99": 0, "err": 0, "len": 0, "asr": 0.0, "audio": 0.0, "as": {}})
        for row in open(clips, encoding="utf-8"):
            name, said = row.rstrip("\n").split("\t")[:2]
            pcm = pcm16k(os.path.join(folder, sub, name))
            seconds = len(pcm) / 32000
            t0 = time.perf_counter()
            heard = rec.hear(pcm, candidates=hear)
            took = time.perf_counter() - t0
            all99 = rec.hear(pcm).lang
            err, n = errors(said, heard.text, by_char=lang in ("ko", "ja", "zh", "th"))
            t["n"] += 1
            t["ok"] += heard.lang == lang
            t["ok99"] += all99 == lang
            t["err"] += err
            t["len"] += n
            t["asr"] += took
            t["audio"] += seconds
            t["as"][heard.lang] = t["as"].get(heard.lang, 0) + 1
            if out:
                out.write(f"{lang}\t{name}\t{seconds:.1f}\t{took:.2f}\t{heard.lang}\t{all99}\t{err}\t{n}\t{said}\t{heard.text}\n")
                out.flush()
    print("lang  clips  right(among)  right(all 99)  word/char errors  whisper s/clip  clip s  heard as")
    for lang, t in total.items():
        n = max(1, t["n"])
        print(f"{lang:4}  {t['n']:5}  {t['ok']:12}  {t['ok99']:13}  {100 * t['err'] / max(1, t['len']):15.1f}%"
              f"  {t['asr'] / n:14.2f}  {t['audio'] / n:6.1f}  {t['as']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
