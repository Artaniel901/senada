"""Slang dictionary. Gemma and NLLB learned mostly written, formal text, so new slang ("gabut", "킹받네",
"no cap") comes out literal or garbled. The words found in a line are looked up here and handed over:

- Penalar gets each word's meaning next to the line ("gabut = bored, nothing to do") and decides,
  with the context, whether the slang sense applies.
- NLLB can't take notes, so a word whose plain form is safe to swap in is replaced before translation
  ("gak" -> "tidak"). Words that also have an ordinary sense have no plain form and are left alone.

Bundled lists: senada/slang/<lang>.tsv, one word per row: `forms<TAB>plain form<TAB>meaning`, forms
split by `|`. The user's own words come from the app's settings, one per line: `word = meaning`."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

ENABLED = True  # tools/try_slang.py --no-slang turns it off to compare
_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "slang")
_HANGUL = re.compile(r"[가-힣ㄱ-ㆎ]")


@dataclass(frozen=True)
class Word:
    form: str      # as written in the line, lowercase
    plain: str     # the same thing in plain words of that language, "" when it isn't safe to swap
    meaning: str   # for Penalar, usually English


_lists: dict[str, list[Word]] = {}
_user: list[Word] = []


def _load(lang: str) -> list[Word]:
    if lang not in _lists:
        words = []
        path = os.path.join(_DIR, lang + ".tsv")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for row in f:
                    if not row.strip() or row.startswith("#"):
                        continue
                    forms, plain, meaning = (row.rstrip("\n").split("\t") + ["", ""])[:3]
                    for form in forms.split("|"):
                        if form.strip():
                            words.append(Word(form.strip().lower(), plain.strip(), meaning.strip()))
        words.sort(key=lambda w: -len(w.form))  # "wkwkwk" before "wkwk", "anjir lah" before "anjir"
        _lists[lang] = words
    return _lists[lang]


def set_user(text: str) -> None:
    """The user's own slang from the settings: `word = meaning` per line, any language."""
    global _user
    out = []
    for row in (text or "").splitlines()[:200]:
        word, sep, meaning = row.partition("=")
        if sep and word.strip() and meaning.strip():
            out.append(Word(word.strip().lower()[:60], "", meaning.strip()[:200]))
    _user = sorted(out, key=lambda w: -len(w.form))


def _pattern(form: str) -> re.Pattern:
    # Korean endings and particles stick to the word (킹받네, 존맛탱이다, TMI였어), so a Hangul word only
    # needs a word start and any word may be followed by Hangul; otherwise it must be a whole word.
    tail = "" if _HANGUL.search(form) else r"(?![^\W가-힣ㄱ-ㆎ])"
    return re.compile(r"(?<!\w)" + re.escape(form) + tail, re.IGNORECASE)


_patterns: dict[str, re.Pattern] = {}


def _spans(text: str, words: list[Word]):
    taken: list[tuple[int, int]] = []
    for w in words:
        p = _patterns.get(w.form) or _patterns.setdefault(w.form, _pattern(w.form))
        for m in p.finditer(text):
            if not any(a < m.end() and m.start() < b for a, b in taken):
                taken.append((m.start(), m.end()))
                yield m, w


def find(text: str, lang: str) -> list[Word]:
    """Slang in `text`, the user's own first, each word once, in the order it appears."""
    if not ENABLED or not text:
        return []
    hits = sorted(_spans(text, _user + _load(lang)), key=lambda h: h[0].start())
    seen, out = set(), []
    for _, w in hits:
        if w.meaning and w.form not in seen:  # no meaning: an everyday word only NLLB needs swapped
            seen.add(w.form)
            out.append(w)
    return out[:12]


def notes(text: str, lang: str) -> str:
    """The prompt line for Penalar, or ""."""
    return "; ".join(f"{w.form} = {w.meaning}" for w in find(text, lang))


def plain(text: str, lang: str) -> str:
    """`text` with the slang that has a safe plain form swapped for it, for NLLB."""
    if not ENABLED or not text:
        return text
    parts, last = [], 0
    for m, w in sorted(_spans(text, _load(lang)), key=lambda h: h[0].start()):
        if not w.plain or (_HANGUL.search(w.form) and m.end() < len(text) and _HANGUL.match(text[m.end()])):
            continue  # a Korean stem with an ending on it can't take a plain word in its place
        parts += [text[last:m.start()], w.plain]
        last = m.end()
    return "".join(parts) + text[last:] if parts else text
