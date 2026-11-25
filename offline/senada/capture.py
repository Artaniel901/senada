"""Where the sound comes from: what this computer plays (WASAPI loopback of the default output), a
microphone, or a WAV file (tests and "translate a recording"). Each source calls `on_audio(pcm16)`
with 16 kHz mono int16 `array("h")` blocks of about 100 ms, from its own thread, until stopped."""
from __future__ import annotations

import threading
import time
from array import array

RATE = 16000
CAPTURE_RATE = 48000
BLOCK = CAPTURE_RATE // 10


def to_pcm16(frames) -> array:
    """float32 (n, channels) at 48 kHz -> 16 kHz mono int16: average the channels, then each 3 samples."""
    import numpy as np

    mono = frames.mean(axis=1) if frames.ndim == 2 else frames
    n = len(mono) // 3 * 3
    mono = mono[:n].reshape(-1, 3).mean(axis=1)
    pcm = np.clip(mono * 32767.0, -32768, 32767).astype(np.int16)
    out = array("h")
    out.frombytes(pcm.tobytes())
    return out


class Source:
    def __init__(self, on_audio):
        self.on_audio = on_audio
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.error: str | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._guard, name=type(self).__name__, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=3)

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def _guard(self) -> None:
        try:
            self._run()
        except Exception as e:  # shown in the live panel; listening stops
            self.error = str(e) or type(e).__name__

    def _run(self) -> None:
        raise NotImplementedError


class _SoundcardSource(Source):
    """Follows Windows' default device: bound once at start, a session went on hearing the laptop speakers
    after the sound had moved to a headset, and ended with no lines. The default is looked up every
    `check_every` seconds (about 1 ms) and the recorder reopened on the new one; a device that vanishes
    (headset unplugged) gets `retries` tries at the default Windows picks next."""
    check_every = 1.0
    retries = 3
    retry_wait = 1.0  # Windows takes a moment to name the next default

    def __init__(self, on_audio):
        super().__init__(on_audio)
        self.on_device = lambda name, switched: None  # the device now heard, and whether it changed

    def _default_id(self) -> str:
        raise NotImplementedError

    def _device(self):
        raise NotImplementedError

    def _run(self) -> None:
        import ctypes
        import sys
        import soundcard  # noqa: F401 -- first: its import joins COM itself and fails if already joined (S_FALSE)
        # soundcard joins COM only in the thread that imports it: once that thread had ended, the next
        # session's thread failed with 0x800401f0 (system audio, stop, then the mic). Each thread joins itself.
        com = sys.platform == "win32" and ctypes.windll.ole32.CoInitializeEx(None, 0) in (0, 1)  # MTA, as soundcard
        try:
            self._listen()
        finally:
            if com:
                ctypes.windll.ole32.CoUninitialize()

    def _listen(self) -> None:
        import warnings
        import soundcard

        warnings.filterwarnings("ignore", category=soundcard.SoundcardRuntimeWarning)
        heard, failures = None, 0
        while not self._stop.is_set():
            try:
                mic = self._device()
                with mic.recorder(samplerate=CAPTURE_RATE, blocksize=BLOCK) as rec:
                    self.on_device(mic.name, heard is not None and heard != mic.id)
                    heard, failures = mic.id, 0
                    checked = time.monotonic()
                    while not self._stop.is_set():
                        self.on_audio(to_pcm16(rec.record(numframes=BLOCK)))
                        if time.monotonic() - checked >= self.check_every:
                            checked = time.monotonic()
                            if self._default_id() != heard:
                                break  # the user switched outputs: reopen on the new default
            except Exception:
                failures += 1
                if failures >= self.retries:
                    raise
                self._stop.wait(self.retry_wait)


class SystemAudio(_SoundcardSource):
    """What the speakers or headphones play, any app."""
    def _default_id(self) -> str:
        import soundcard
        return soundcard.default_speaker().id

    def _device(self):
        import soundcard
        return soundcard.get_microphone(id=self._default_id(), include_loopback=True)


class Microphone(_SoundcardSource):
    def _default_id(self) -> str:
        import soundcard
        return soundcard.default_microphone().id

    def _device(self):
        import soundcard
        return soundcard.default_microphone()


class WavFile(Source):
    """A WAV file, fed at `speed` times real time (0: as fast as it reads)."""
    def __init__(self, on_audio, path: str, speed: float = 1.0):
        super().__init__(on_audio)
        self.path, self.speed = path, speed
        self.finished = threading.Event()

    def _run(self) -> None:
        from .core import Wav
        pcm = Wav.read_file(self.path)
        step = RATE // 10
        for i in range(0, len(pcm), step):
            if self._stop.is_set():
                return
            self.on_audio(pcm[i:i + step])
            if self.speed:
                time.sleep(0.1 / self.speed)
        self.finished.set()


def devices() -> dict:
    import soundcard
    try:
        return {"speaker": soundcard.default_speaker().name, "microphone": soundcard.default_microphone().name}
    except Exception as e:
        return {"error": str(e)}
