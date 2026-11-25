"""Text translation on this computer with NLLB-200 through CTranslate2. Text is cut into lines and
sentences, translated as one batch, and put back with the same line breaks. Results are cached, so
the live subtitles and a retyped sentence don't translate the same words twice."""
from __future__ import annotations

import os
import re
import threading
from collections import OrderedDict

from . import catalog, languages

_SENTENCE = re.compile(r"(?<=[.!?…。！？])\s+|(?<=[。！？])")
_CJK = {"ja", "zh", "zh-Hant", "yue", "th", "lo", "km", "my"}


def split_sentences(paragraph: str) -> list[str]:
    parts = [p.strip() for p in _SENTENCE.split(paragraph)]
    return [p for p in parts if p]


def threads() -> int:
    return max(2, min(8, (os.cpu_count() or 4) // 2))


class Translator:
    def __init__(self, model_id: str | None = None, device: str = "auto"):
        import ctranslate2
        import sentencepiece

        self.model_id = model_id or catalog.DEFAULT["mt"]
        if not catalog.installed(self.model_id):
            raise FileNotFoundError(f"model {self.model_id} is not downloaded")
        folder = catalog.folder(self.model_id)
        self.sp = sentencepiece.SentencePieceProcessor(model_file=os.path.join(folder, catalog.SPM[1]))
        self.device = "cpu"
        self.model = None
        if device in ("auto", "cuda") and ctranslate2.get_cuda_device_count() > 0:
            try:
                model = ctranslate2.Translator(folder, device="cuda", compute_type="int8_float16")
                model.translate_batch([["eng_Latn", "▁hi", "</s>"]], target_prefix=[["ind_Latn"]], max_decoding_length=4)
                self.model, self.device = model, "cuda"
            except Exception:  # no cuBLAS on this computer: the CPU it is
                self.model = None
        if self.model is None:
            self.model = ctranslate2.Translator(folder, device="cpu", compute_type="int8", intra_threads=threads())
        self._cache: OrderedDict = OrderedDict()
        self._gate = threading.Lock()

    def translate(self, text: str, src: str, tgt: str, beam: int = 4) -> str:
        """`src` and `tgt` are language ids (languages.py). Same language: the text back unchanged."""
        if src == tgt or not text.strip():
            return text
        s, t = languages.get(src).nllb, languages.get(tgt).nllb
        lines = text.split("\n")
        todo = []
        shape = []
        for line in lines:
            sentences = split_sentences(line)
            shape.append(len(sentences))
            todo.extend(sentences)
        done = self._batch(todo, s, t, beam)
        joiner = "" if tgt in _CJK else " "
        out, i = [], 0
        for count in shape:
            out.append(joiner.join(done[i:i + count]))
            i += count
        return "\n".join(out)

    def _batch(self, sentences: list[str], s: str, t: str, beam: int) -> list[str]:
        results: list[str | None] = []
        missing = []
        for sentence in sentences:
            hit = self._cache.get((s, t, sentence))
            results.append(hit)
            if hit is None:
                missing.append(sentence)
        if missing:
            unique = list(dict.fromkeys(missing))
            source = [[s] + self.sp.encode(x, out_type=str)[:400] + ["</s>"] for x in unique]
            with self._gate:  # one translation at a time keeps the CPU threads for it
                hyps = self.model.translate_batch(source, target_prefix=[[t]] * len(unique), beam_size=beam,
                                                  max_decoding_length=512, repetition_penalty=1.1)
            for sentence, h in zip(unique, hyps):
                tokens = h.hypotheses[0]
                if tokens and tokens[0] == t:
                    tokens = tokens[1:]
                self._remember((s, t, sentence), self.sp.decode(tokens))
            results = [r if r is not None else self._cache[(s, t, x)] for r, x in zip(results, sentences)]
        return results  # type: ignore[return-value]

    def _remember(self, key, value: str) -> None:
        self._cache[key] = value
        self._cache.move_to_end(key)
        while len(self._cache) > 4000:
            self._cache.popitem(last=False)
