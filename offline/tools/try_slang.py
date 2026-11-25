"""Runs the slang sentences in tests/slang_cases.tsv through Penalar (as a live line and as typed text)
and NLLB, and writes what each gave next to what the sentence means, for a person to judge.

    python -X utf8 tools/try_slang.py [--no-slang] [--only penalar|nllb] <out.tsv>

--no-slang runs without the slang dictionary (senada/slang/), to compare with it."""
from __future__ import annotations

import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SENADA_HOME", tempfile.mkdtemp(prefix="senada-try-"))

from senada import catalog  # noqa: E402

catalog.use_gpu_libraries()

from senada.reason import Reasoner  # noqa: E402
from senada.translate import Translator  # noqa: E402

CASES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests", "slang_cases.tsv")


def cases():
    with open(CASES, encoding="utf-8") as f:
        for row in f:
            if row.strip() and not row.startswith("#"):
                src, tgt, text, meaning = row.rstrip("\n").split("\t")
                yield src, tgt, text, meaning


def main(argv: list[str]) -> int:
    only = None
    while argv and argv[0].startswith("--"):
        flag = argv.pop(0)
        if flag == "--no-slang":
            from senada import slang
            slang.ENABLED = False
        elif flag == "--only":
            only = argv.pop(0)
    out_path = argv[0]
    reasoner = None if only == "nllb" else Reasoner(catalog.DEFAULT["llm"])
    translator = None if only == "penalar" else Translator(device="cpu" if reasoner else "auto")
    with open(out_path, "w", encoding="utf-8") as out:
        out.write("src\ttgt\ttext\tmeaning\tline\ttext_mode\tnllb\tseconds\n")
        for src, tgt, text, meaning in cases():
            t = time.time()
            line = typed = nllb = ""
            if reasoner:
                got = reasoner.translate_line(text, src, tgt)
                line = (got.translation + (f"  [{got.note}]" if got.note else "")) if got else "(none)"
                got = reasoner.translate_text(text, src, tgt)
                typed = (got[0] + (f"  [{got[1]}]" if got[1] else "")) if got else "(none)"
            if translator:
                nllb = translator.translate(text, src, tgt)
            row = [src, tgt, text, meaning, line, typed, nllb, f"{time.time() - t:.1f}"]
            out.write("\t".join(x.replace("\t", " ").replace("\n", " / ") for x in row) + "\n")
            out.flush()
            print(f"{src}>{tgt} {text}\n   line : {line}\n   text : {typed}\n   nllb : {nllb}")
    if reasoner:
        reasoner.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
