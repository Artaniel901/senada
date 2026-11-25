"""Speech to text on this computer with Whisper (faster-whisper). Each call gets one stretch of speech
the segmenter cut (16 kHz mono int16) and returns the language heard and the words."""
from __future__ import annotations

import threading
from dataclasses import dataclass

from . import catalog, languages
from .translate import threads


@dataclass
class Heard:
    text: str
    lang: str | None  # language id (languages.py), None when Whisper named one we don't list
    probability: float


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

    def hear(self, pcm16, language: str | None = None, beam: int = 1) -> Heard:
        """`language` is a language id to listen for, or None to let Whisper tell."""
        import numpy as np

        audio = np.frombuffer(bytes(pcm16), dtype=np.int16).astype(np.float32) / 32768.0
        code = languages.get(language).whisper if language else None
        with self._gate:
            segments, info = self.model.transcribe(
                audio, language=code, beam_size=beam, vad_filter=False, condition_on_previous_text=False,
                without_timestamps=True, no_speech_threshold=0.6, log_prob_threshold=-1.0,
                compression_ratio_threshold=2.4, temperature=(0.0, 0.2, 0.4))
            text = " ".join(s.text.strip() for s in segments if s.no_speech_prob < 0.7).strip()
        lang = languages.get(language) if language else languages.from_whisper(info.language)
        return Heard(text=_clean(text), lang=lang.id if lang else None, probability=float(info.language_probability or 0))


# Whisper's well-known inventions on silence or music (YouTube outros it was trained on).
_HALLUCINATIONS = {
    "terima kasih.", "terima kasih telah menonton!", "thank you.", "thanks for watching!", "thank you for watching.",
    "시청해주셔서 감사합니다.", "구독과 좋아요 부탁드립니다.", "ご視聴ありがとうございました", "you", "."}


def _clean(text: str) -> str:
    return "" if text.lower() in _HALLUCINATIONS else text


def _silence():
    import numpy as np
    return np.zeros(16000, dtype=np.float32)
