"""Speech to text on this computer with Whisper (faster-whisper). Each call gets one stretch of speech
the segmenter cut (16 kHz mono int16) and returns the language heard and the words."""
from __future__ import annotations

import math
import threading
from dataclasses import dataclass

from . import catalog, languages, speech
from .translate import threads


@dataclass
class Heard:
    text: str
    lang: str | None  # language id (languages.py), None when Whisper named one we don't list
    probability: float  # how sure the language is (its share among the candidates, when given)
    confidence: float = 1.0  # how sure the words are: mean token probability, 0..1


class Recognizer:
    def __init__(self, model_id: str | None = None, device: str = "auto"):
        from faster_whisper import WhisperModel

        self.model_id = model_id or catalog.DEFAULT["asr"]
        if not catalog.installed(self.model_id):
            raise FileNotFoundError(f"model {self.model_id} is not downloaded")
        folder = catalog.folder(self.model_id)
        self.device = "cpu"
        self.model = None
        if device in ("auto", "cuda"):
            try:
                import ctranslate2
                if ctranslate2.get_cuda_device_count() > 0:
                    model = WhisperModel(folder, device="cuda", compute_type="int8_float16")
                    # transcribe() is lazy: read its segments so cuBLAS/cuDNN load now, not mid-meeting.
                    list(model.transcribe(_silence(), language="en")[0])
                    self.model, self.device = model, "cuda"
            except Exception:
                self.model = None
        if self.model is None:
            self.model = WhisperModel(folder, device="cpu", compute_type="int8", cpu_threads=threads())
        self._gate = threading.Lock()

    def hear(self, pcm16, language: str | None = None, beam: int = 1, candidates=None, prompt: str = "",
             fallback: bool = True) -> Heard:
        """`language` is a language id to listen for, or None to let Whisper tell. With `candidates`
        (language ids), Whisper only chooses among them: asked to pick from all 99, Whisper small called
        Indonesian Javanese and Vietnamese, and wrote one line in Khmer. `prompt`: what was said just before
        and the user's own terms, so names and topic words come out spelled as meant. `fallback`: retry
        at higher temperatures when the first pass looks wrong (off for the quick look at a sentence
        still being spoken)."""
        import numpy as np

        audio = np.frombuffer(bytes(pcm16), dtype=np.int16).astype(np.float32) / 32768.0
        probability = 1.0
        with self._gate:
            if not language and candidates:
                language, probability = self._choose(audio, candidates)
            code = languages.get(language).whisper if language else None
            segments, info = self.model.transcribe(
                audio, language=code, beam_size=beam, vad_filter=False, condition_on_previous_text=False,
                without_timestamps=True, no_speech_threshold=0.6, log_prob_threshold=-1.0,
                compression_ratio_threshold=2.4, temperature=(0.0, 0.2, 0.4) if fallback else 0.0,
                initial_prompt=prompt[-400:] or None)
            kept = [s for s in segments if _speech(s)]
        text = " ".join(s.text.strip() for s in kept).strip()
        if language:
            lang = languages.get(language)
        else:
            lang, probability = languages.from_whisper(info.language), float(info.language_probability or 0)
        lang_id = lang.id if lang else None
        text = _clean(text)
        if not speech.plausible(text, lang_id):
            text = ""
        # How sure Whisper was of the words: the mean token probability, weighted by length.
        sure = sum(s.avg_logprob * len(s.text) for s in kept) / max(1, sum(len(s.text) for s in kept))
        return Heard(text=text, lang=lang_id, probability=probability, confidence=math.exp(sure) if kept else 0.0)

    def _choose(self, audio, candidates) -> tuple[str | None, float]:
        """The candidate Whisper finds likeliest, and its share among the candidates."""
        by_code = {}
        for lid in candidates:
            try:
                code = languages.get(lid).whisper
            except ValueError:
                continue
            if code and code not in by_code:
                by_code[code] = lid
        if not by_code:
            return None, 0.0
        if len(by_code) == 1:
            return next(iter(by_code.values())), 1.0
        _, _, probs = self.model.detect_language(audio=audio)
        scores = {code: p for code, p in probs if code in by_code}
        total = sum(scores.values())
        if not total:
            return None, 0.0
        best = max(scores, key=scores.get)
        return by_code[best], scores[best] / total


# Whisper's well-known inventions on silence or music (YouTube outros it was trained on).
_HALLUCINATIONS = {
    "terima kasih.", "terima kasih telah menonton!", "thank you.", "thanks for watching!", "thank you for watching.",
    "시청해주셔서 감사합니다.", "구독과 좋아요 부탁드립니다.", "ご視聴ありがとうございました", "you", "."}


def _speech(segment) -> bool:
    """Whisper's own signs that a piece was noise it made words of: it thinks nothing was said and is
    unsure of the words, or it is very unsure of them whatever it thinks."""
    if segment.no_speech_prob >= 0.7:
        return False
    if segment.no_speech_prob >= 0.4 and segment.avg_logprob < -0.9:
        return False
    return segment.avg_logprob >= -1.4


def _clean(text: str) -> str:
    return "" if text.lower() in _HALLUCINATIONS else text


def _silence():
    import numpy as np
    return np.zeros(16000, dtype=np.float32)
