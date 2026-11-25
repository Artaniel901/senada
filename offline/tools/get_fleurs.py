"""Streams the first N clips of FLEURS test audio per language (no full 200 MB download) plus the
transcriptions. Usage: python tools/get_fleurs.py <outdir> id_id:25 ko_kr:25 ..."""
import csv
import os
import sys
import tarfile
import urllib.request

BASE = "https://huggingface.co/datasets/google/fleurs/resolve/main/data/{lang}/"


def get(lang: str, n: int, out: str) -> None:
    folder = os.path.join(out, lang)
    os.makedirs(folder, exist_ok=True)
    with urllib.request.urlopen(BASE.format(lang=lang) + "test.tsv", timeout=60) as r:
        rows = r.read().decode("utf-8").splitlines()
    text = {}
    for row in csv.reader(rows, delimiter="\t", quoting=csv.QUOTE_NONE):
        if len(row) > 3:
            text[row[1]] = (row[2], row[6] if len(row) > 6 else "")
    got = []
    with urllib.request.urlopen(BASE.format(lang=lang) + "audio/test.tar.gz", timeout=60) as r:
        with tarfile.open(fileobj=r, mode="r|gz") as tar:
            for m in tar:
                name = os.path.basename(m.name)
                if not m.isfile() or name not in text:
                    continue
                data = tar.extractfile(m).read()
                with open(os.path.join(folder, name), "wb") as f:
                    f.write(data)
                got.append((name, *text[name]))
                if len(got) >= n:
                    break
    with open(os.path.join(folder, "clips.tsv"), "w", encoding="utf-8") as f:
        for name, raw, gender in got:
            f.write(f"{name}\t{raw}\t{gender}\n")
    print(lang, len(got))


if __name__ == "__main__":
    out = sys.argv[1]
    for spec in sys.argv[2:]:
        lang, n = spec.split(":")
        get(lang, int(n), out)
