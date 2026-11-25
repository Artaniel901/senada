"""Live listening, Cicada's way but on this computer: a source's audio -> Cicada's segmenter ->
Whisper -> NLLB -> a line in the meeting record, and an event for the window. Lines are delivered in
segment order by one worker, so a slow sentence never jumps ahead of the next.

Language: with "auto", Whisper names it for every stretch; confident stretches agreeing make it the
meeting's language (Cicada's hint and votes), used only when Whisper is unsure of a stretch."""
from __future__ import annotations

import queue
import threading
import time

from . import capture, reason
from .core import LineFix, Segmenter, SessionStore, TranscriptLine, VoiceGate, Wav


def interpret(line, reasoner, translator, recent: list, hints: tuple, log=lambda m: None, beam: int = 2) -> str:
    """Fills in a heard line's translation: Penalar with the lines before it (fixing misheard words into
    `line.fixes`, Cicada's own field, so `line.shown` and the records carry them), NLLB when Penalar is off,
    doesn't know the pair or gives nothing usable. `recent` is the running context, updated here. Returns
    Penalar's note on what was meant, or ""."""
    src, tgt = line.srcLang, line.dstLang
    note = ""
    if src == tgt and reasoner is not None and reasoner.alive and reason.handles(src, tgt):
        # Nothing to translate, but misheard words still get fixed so the transcript reads right.
        try:
            topic, words = hints
            line.fixes = [LineFix(from_=a, to=b) for a, b in reasoner.fix_line(line.src, src, recent, topic, words)] or None
        except Exception as e:
            log(f"penalar fix failed: {type(e).__name__}: {e}")
    if src != tgt:
        if reasoner is not None and reasoner.alive and reason.handles(src, tgt):
            try:
                topic, words = hints
                got = reasoner.translate_line(line.src, src, tgt, recent, topic, words)
                if got:
                    line.dst = got.translation
                    line.fixes = [LineFix(from_=a, to=b) for a, b in got.fixes] or None
                    note = got.note
            except Exception as e:
                log(f"penalar line failed: {type(e).__name__}: {e}")
        if line.dst is None and translator is not None:
            line.dst = translator.translate(line.shown, src, tgt, beam=beam)
    recent.append((line.shown, line.dst))
    del recent[:-8]
    return note


class LiveSession:
    def __init__(self, recognizer, translator, store: SessionStore, source: str, src: str, tgt: str,
                 on_event, wav_path: str | None = None, wav_speed: float = 1.0, reasoner=None,
                 hints=lambda: ("", "")):
        self.recognizer, self.translator, self.store = recognizer, translator, store
        self.reasoner, self.hints = reasoner, hints
        self._recent: list = []
        self.kind, self.src, self.tgt = source, src, tgt
        self.on_event = on_event
        self.wav_path, self.wav_speed = wav_path, wav_speed
        self.sid: str | None = None
        self.hint: str | None = None if src == "auto" else src
        self._candidate: str | None = None
        self._votes = 0
        self._queue: queue.Queue = queue.Queue()
        self._pending = 0
        self._last_level = 0.0
        self._segmenter = Segmenter()
        self._segmenter.on_segment = self._segment
        # A room mic hears the room and a voice across the table can sit under -40 dBFS: Cicada's
        # VoiceGate learns the room's noise and lowers the segmenter's line to twice it.
        self._gate = VoiceGate(adaptive=True) if source == "mic" else None
        self._source: capture.Source | None = None
        self._worker: threading.Thread | None = None
        self.lines = 0

    # The window's side --------------------------------------------------------------------

    def start(self) -> str:
        session = self.store.begin()
        self.sid = session.id
        if self.kind == "system":
            self._source = capture.SystemAudio(self._audio)
        elif self.kind == "mic":
            self._source = capture.Microphone(self._audio)
        elif self.kind == "file":
            self._source = capture.WavFile(self._audio, self.wav_path or "", self.wav_speed)
        else:
            raise ValueError(f"unknown source {self.kind}")
        self._worker = threading.Thread(target=self._work, name="live-worker", daemon=True)
        self._worker.start()
        self._source.start()
        threading.Thread(target=self._watch, name="live-watch", daemon=True).start()
        self._emit({"type": "started", "sid": self.sid, "source": self.kind})
        return self.sid

    def stop(self, wait: float = 30.0) -> None:
        if self._source:
            self._source.stop()
            self._source = None
            self._segmenter.flush()
            self._queue.put(None)
        if self._worker:
            self._worker.join(timeout=wait)
            self._worker = None
        if self.sid:
            self.store.end(self.sid)
            self._emit({"type": "stopped", "sid": self.sid, "lines": self.lines})

    def set_target(self, tgt: str) -> None:
        self.tgt = tgt

    # Audio and the worker -------------------------------------------------------------------

    def _audio(self, pcm) -> None:
        now = time.monotonic()
        if self._gate is not None:
            self._gate.voiced(Wav.rms(pcm), len(pcm) / 16000)
            self._segmenter.threshold = self._gate.threshold
        if now - self._last_level > 0.1:
            self._last_level = now
            self._emit({"type": "level", "rms": round(Wav.rms(pcm[::4]), 4)})
        self._segmenter.feed(pcm)

    def _segment(self, segment) -> None:
        self._pending += 1
        self._emit({"type": "pending", "count": self._pending})
        self._queue.put(segment)

    def _watch(self) -> None:
        """Ends the session when its source dies (a device unplugged) or a file runs out."""
        source = self._source
        while source is not None and self._source is source:
            if not source.running:
                if source.error:
                    self._emit({"type": "error", "message": source.error})
                elif self.kind == "file":
                    self._emit({"type": "file-done"})
                return
            time.sleep(0.2)

    def _work(self) -> None:
        while True:
            segment = self._queue.get()
            if segment is None:
                return
            try:
                self._hear(segment)
            except Exception as e:
                self._emit({"type": "error", "message": f"{type(e).__name__}: {e}"})
            finally:
                self._pending = max(0, self._pending - 1)
                self._emit({"type": "pending", "count": self._pending})

    UNSURE = 0.5  # Whisper's language probability under which the meeting's language is trusted instead

    def _hear(self, segment) -> None:
        if self.src != "auto":
            # A named language skips Whisper's detection pass: half the time on a CPU.
            heard = self.recognizer.hear(segment.samples, language=self.src)
        else:
            # Every stretch is asked which language it is: people switch mid-meeting, and locking onto
            # the first language heard turned Indonesian and English into Korean in testing.
            heard = self.recognizer.hear(segment.samples, language=None)
            if heard.lang and heard.lang == self._candidate:
                self._votes += 1
            else:
                self._candidate, self._votes = heard.lang, 1
            if heard.lang and heard.probability >= 0.8 and (self._votes >= 2 or self.hint is None):
                self.hint = heard.lang
            if self.hint and (heard.lang is None or (heard.lang != self.hint and heard.probability < self.UNSURE)):
                heard = self.recognizer.hear(segment.samples, language=self.hint)
        if not heard.text:
            return
        src = heard.lang or self.hint or "en"
        tgt = self.tgt
        line = TranscriptLine(id=f"h1-{segment.index}", t=segment.start, speaker="them", src=heard.text, dst=None,
                              srcLang=src, dstLang=tgt, via="room" if self.kind == "mic" else None)
        if src != tgt and self.reasoner is not None:
            # Penalar takes a second or two: the heard words show at once, the translation fills the same line.
            self._emit({"type": "line", "sid": self.sid, "id": line.id, "t": line.t, "src": line.src, "dst": None,
                        "srcLang": src, "dstLang": tgt, "translating": True})
        t0 = time.monotonic()
        note = interpret(line, self.reasoner, self.translator, self._recent, self.hints())
        self.lines += 1
        self.store.append(self.sid, line)
        self._emit({"type": "line", "sid": self.sid, "id": line.id, "t": line.t, "src": line.shown, "dst": line.dst,
                    "srcLang": src, "dstLang": tgt, "note": note, "fixes": [[f.from_, f.to] for f in line.fixes or []],
                    "translateMs": round((time.monotonic() - t0) * 1000)})

    def _emit(self, event: dict) -> None:
        try:
            self.on_event(event)
        except Exception:
            pass
