"""Where speech is, and whether what Whisper wrote can be speech at all.

`SpeechSegmenter` replaces Cicada's loudness segmenter for live listening. Cicada cuts where the sound
drops; under a film score or a song nothing drops, so its 8 s limit cut sentences in half and put an
Indonesian and a Korean sentence into one stretch, heard as one language (in testing the English line
under music vanished and a Korean one came out as "Dasi enen anggal koa?"). Here Silero VAD (bundled with
faster-whisper) finds the voice: a stretch ends at a pause in the speech, music without a voice is
dropped, and each sentence gets its own language.

`plausible()` rejects what Whisper invents on noise: a letter repeated over and over, or writing in a
script the language doesn't use (Indonesian heard as Khmer "តំំំំំំំំ")."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from . import languages

RATE = 16000


@dataclass
class Stretch:
    """One stretch of speech: the same fields live.py reads from Cicada's segments."""
    samples: bytes  # 16 kHz mono int16
    start: float  # seconds since listening started
    index: int


class SpeechSegmenter:
    pause = 0.45  # seconds without speech that end a sentence
    max_length = 14.0  # a stretch is cut here even mid-speech, so a long monologue still shows up
    step = 0.3  # how often the voice detector looks at the waiting audio
    keep = 0.6  # seconds kept before speech starts (the detector's pad reaches into it)

    def __init__(self, threshold: float = 0.35):  # 0.5 lost words under loud music, 0.25 split sentences
        import numpy as np
        from faster_whisper.vad import VadOptions

        self._np = np
        self.options = VadOptions(threshold=threshold, min_speech_duration_ms=250,
                                  min_silence_duration_ms=int(self.pause * 1000), speech_pad_ms=150)
        self.on_segment = lambda stretch: None
        self._buf = np.zeros(0, dtype=np.float32)
        self._at = 0  # stream position of _buf[0], in samples
        self._fresh = 0
        self._index = 0

    def feed(self, pcm) -> None:
        np = self._np
        x = np.frombuffer(bytes(pcm), dtype=np.int16).astype(np.float32) / 32768.0
        self._buf = np.concatenate([self._buf, x])
        self._fresh += len(x)
        if self._fresh >= self.step * RATE:
            self._fresh = 0
            self._scan(final=False)

    def flush(self) -> None:
        self._scan(final=True)

    def _scan(self, final: bool) -> None:
        from faster_whisper.vad import get_speech_timestamps

        n = len(self._buf)
        if n < RATE * 0.3:
            return
        spans = get_speech_timestamps(self._buf, self.options, sampling_rate=RATE)
        done = 0
        for span in spans:
            start, end = span["start"], span["end"]
            closed = final or n - end >= self.pause * RATE
            too_long = end - start >= self.max_length * RATE
            if not (closed or too_long):
                break
            self._out(self._buf[start:end], start)
            done = end
        if done:
            self._drop(done)
        elif not spans:
            # Nothing said yet: keep only the tail, where a sentence may be starting.
            self._drop(max(0, n - int(self.keep * RATE)))
        else:
            # Speech has started but not ended: drop the quiet before it.
            self._drop(max(0, spans[0]["start"] - int(self.keep * RATE)))

    def _out(self, audio, start: int) -> None:
        np = self._np
        self._index += 1
        pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes()
        self.on_segment(Stretch(pcm, round((self._at + start) / RATE, 2), self._index))

    def _drop(self, count: int) -> None:
        if count > 0:
            self._buf = self._buf[count:]
            self._at += count


# The Unicode script names each NLLB script code is written in (the start of a letter's Unicode name).
_SCRIPTS = {
    "Latn": ("LATIN",), "Hang": ("HANGUL", "CJK"), "Jpan": ("HIRAGANA", "KATAKANA", "CJK"), "Hans": ("CJK",),
    "Hant": ("CJK",), "Cyrl": ("CYRILLIC",), "Arab": ("ARABIC",), "Deva": ("DEVANAGARI",), "Beng": ("BENGALI",),
    "Thai": ("THAI",), "Khmr": ("KHMER",), "Laoo": ("LAO",), "Mymr": ("MYANMAR",), "Grek": ("GREEK",),
    "Hebr": ("HEBREW",), "Geor": ("GEORGIAN",), "Armn": ("ARMENIAN",), "Ethi": ("ETHIOPIC",), "Taml": ("TAMIL",),
    "Telu": ("TELUGU",), "Knda": ("KANNADA",), "Mlym": ("MALAYALAM",), "Gujr": ("GUJARATI",), "Guru": ("GURMUKHI",),
    "Orya": ("ORIYA",), "Sinh": ("SINHALA",), "Tibt": ("TIBETAN",),
}
_REPEAT = re.compile(r"(\S)\1{5,}")  # one letter six times in a row


def script_share(text: str, lang: str) -> float | None:
    """The share of letters written in `lang`'s script, or None when the script isn't one we check."""
    try:
        names = _SCRIPTS.get(languages.get(lang).nllb.split("_")[1])
    except ValueError:
        return None
    if not names:
        return None
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    ok = sum(1 for c in letters if unicodedata.name(c, "").startswith(names))
    return ok / len(letters)


def plausible(text: str, lang: str | None) -> bool:
    """Whether `text` can be speech in `lang`: not one letter repeated, and mostly in the language's own
    script (a Latin word or two inside Korean is fine; a whole line of Khmer for Indonesian is not)."""
    if not text or _REPEAT.search(text):
        return False
    if lang is None:
        return True
    share = script_share(text, lang)
    return share is None or share >= 0.5
