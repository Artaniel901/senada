"""The window: pywebview (Edge WebView2) showing ui/index.html, with `Api` as window.pywebview.api.
Engines load in the background after the window opens; everything they report reaches the page as
window.senadaEvent({...}). A second, frameless window shows the floating subtitles."""
from __future__ import annotations

import json
import os
import threading
import time
import traceback

from . import __version__, catalog, detect, export, languages, paths, reason, slang, speech
from .store import History, Settings

catalog.use_gpu_libraries()

from .core import Paths, SessionStore  # noqa: E402

LOG = os.path.join(paths.data(), "senada.log")


def log(message: str) -> None:
    try:
        os.makedirs(paths.data(), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + message + "\n")
    except OSError:
        pass


def _hearable(ids) -> list:
    """The languages "auto" may choose from while listening: known ones Whisper can hear, no repeats."""
    out = []
    for lid in ids if isinstance(ids, list) else []:
        if isinstance(lid, str) and lid in languages.BY_ID and languages.BY_ID[lid].whisper and lid not in out:
            out.append(lid)
    return out[:12]


def _fresh_ui(storage: str) -> None:
    """The page is served from 127.0.0.1 and WebView2 keeps its files in an HTTP cache, so after an update
    the window kept the old app.css (the new language checkboxes showed unstyled). When anything in ui/
    changed since the last start, the browser cache (not settings, records or local storage) is emptied."""
    import hashlib
    import shutil
    stamp = hashlib.sha1()
    for root, _, files in os.walk(paths.UI):
        for name in sorted(files):
            st = os.stat(os.path.join(root, name))
            stamp.update(f"{os.path.relpath(os.path.join(root, name), paths.UI)}:{st.st_size}:{st.st_mtime_ns};".encode())
    marker = os.path.join(storage, "ui-stamp.txt")
    try:
        with open(marker, encoding="utf-8") as f:
            if f.read() == stamp.hexdigest():
                return
    except OSError:
        pass
    for cache in ("Cache", "Code Cache"):
        shutil.rmtree(os.path.join(storage, "EBWebView", "Default", cache), ignore_errors=True)
    os.makedirs(storage, exist_ok=True)
    with open(marker, "w", encoding="utf-8") as f:
        f.write(stamp.hexdigest())


def _drive_script() -> str | None:
    path = os.environ.get("SENADA_DRIVE")
    if not path:
        return None
    with open(path, encoding="utf-8") as f:
        return f.read()


class Engines:
    """Whisper, NLLB and Penalar, loaded once and swapped when Settings picks another model. With Penalar on,
    NLLB only covers the regional languages and failures, so it moves to the CPU and leaves the GPU's
    memory to Whisper and Gemma (all three on a 6 GB card did not fit)."""

    def __init__(self, settings: Settings, emit):
        self._settings, self.emit = settings, emit
        self.translator = None
        self.recognizer = None
        self.reasoner = None
        self._gate = threading.Lock()

    def state(self) -> dict:
        return {
            "mt": {"model": self.translator.model_id, "device": self.translator.device} if self.translator else None,
            "asr": {"model": self.recognizer.model_id, "device": self.recognizer.device} if self.recognizer else None,
            "llm": {"model": self.reasoner.model_id, "device": self.reasoner.device} if self.reasoner else None,
        }

    def reasoning_wanted(self) -> bool:
        return bool(self._settings.get("reasoning")) and catalog.installed(self._settings.get("llmModel"))

    def load(self, which=("asr", "llm", "mt")) -> None:
        with self._gate:
            device = self._settings.get("device")
            if "asr" in which:
                self.recognizer = None
                self._load("asr", self._settings.get("asrModel"), device)
            if "llm" in which:
                old, self.reasoner = self.reasoner, None
                if old:
                    old.close()
                if self._settings.get("reasoning"):
                    self._load("llm", self._settings.get("llmModel"), device)
                else:
                    self.emit({"type": "engine", "kind": "llm", "state": "off"})
            if "mt" in which:
                self.translator = None
                self._load("mt", self._settings.get("mtModel"), "cpu" if self.reasoning_wanted() else device)

    def close(self) -> None:
        if self.reasoner:
            self.reasoner.close()
            self.reasoner = None

    def _load(self, kind: str, model_id: str, device: str) -> None:
        if not catalog.installed(model_id):
            self.emit({"type": "engine", "kind": kind, "state": "missing", "model": model_id})
            return
        self.emit({"type": "engine", "kind": kind, "state": "loading", "model": model_id})
        t = time.time()
        try:
            if kind == "mt":
                from .translate import Translator
                self.translator = Translator(model_id, device)
                got = self.translator
            elif kind == "asr":
                from .asr import Recognizer
                self.recognizer = Recognizer(model_id, device)
                got = self.recognizer
            else:
                from .reason import Reasoner
                self.reasoner = Reasoner(model_id, device, log)
                got = self.reasoner
            log(f"{kind} {model_id} on {got.device} in {time.time() - t:.1f}s")
            self.emit({"type": "engine", "kind": kind, "state": "ready", "model": model_id, "device": got.device})
        except Exception as e:
            log(f"{kind} {model_id} failed: {traceback.format_exc()}")
            self.emit({"type": "engine", "kind": kind, "state": "error", "model": model_id, "message": str(e)})


class Api:
    def __init__(self):
        Paths.home_override = paths.data()
        os.makedirs(paths.data(), exist_ok=True)
        self._settings = Settings()
        slang.set_user(self._settings.get("slang"))
        self._history = History()
        self._records = SessionStore()
        self._engines = Engines(self._settings, self._emit)
        self._live = None
        self._windows: dict = {}
        self._download_cancel = threading.Event()
        self._downloading: str | None = None

    # Plumbing ------------------------------------------------------------------------------

    def _emit(self, event: dict) -> None:
        payload = json.dumps(event, ensure_ascii=False)
        for name, w in list(self._windows.items()):
            if name == "overlay" and event.get("type") not in ("line", "partial", "overlay-style", "stopped", "started"):
                continue
            try:
                w.evaluate_js(f"window.senadaEvent && window.senadaEvent({payload})")
            except Exception:
                pass

    def _start_engines(self) -> None:
        threading.Thread(target=self._engines.load, name="engines", daemon=True).start()

    # Called from the page ------------------------------------------------------------------

    def init(self) -> dict:
        return {
            "version": __version__,
            "languages": languages.as_json(),
            "settings": self._settings.values,
            "models": catalog.status(),
            "gpu": {"nvidia": catalog.has_nvidia(), "installed": catalog.gpu_installed(),
                    "title": catalog.GPU["title"], "blurb": catalog.GPU["blurb"], "sizeMb": catalog.GPU["size"] // 1_000_000},
            "engines": self._engines.state(),
            "history": self._history.items[:50],
            "dataFolder": paths.data(),
            # Development only: a script the page runs after it starts, to drive the real UI in checks.
            "drive": _drive_script(),
        }

    def save_settings(self, patch: dict) -> dict:
        before = dict(self._settings.values)
        patch = dict(patch or {})
        if "liveLangs" in patch:
            patch["liveLangs"] = _hearable(patch["liveLangs"]) or before["liveLangs"]
        values = self._settings.update(patch)
        if "slang" in patch:
            slang.set_user(values["slang"])
        if self._live and "liveLangs" in patch:
            self._live.candidates = list(values["liveLangs"])
        reload = []
        if values["asrModel"] != before["asrModel"]:
            reload.append("asr")
        if values["llmModel"] != before["llmModel"] or values["reasoning"] != before["reasoning"]:
            reload += ["llm", "mt"]  # NLLB's device follows whether Penalar is on
        if values["mtModel"] != before["mtModel"] and "mt" not in reload:
            reload.append("mt")
        if values["device"] != before["device"]:
            reload = ["asr", "llm", "mt"]
        if reload and not self._live:
            threading.Thread(target=self._engines.load, args=(tuple(reload),), daemon=True).start()
        if "overlaySize" in (patch or {}):
            self._emit({"type": "overlay-style", "size": values["overlaySize"]})
        return values

    def detect(self, text: str):
        return detect.detect(text)

    def translate(self, text: str, src: str, tgt: str, remember: bool = True, deep: bool = False) -> dict:
        """Penalar when it is on and knows both languages, NLLB otherwise (and when Penalar gives nothing
        usable). `deep` lets Penalar think first: the Translate button with Pikir lebih dalam, never typing."""
        guessed = None
        if src == "auto":
            guessed = detect.detect(text)
            src = guessed or ("en" if tgt != "en" else "id")
        if src == tgt:
            # Nothing to translate: no engine needed (one still loading must not turn this into an error).
            return {"text": text, "note": "", "src": src, "guessed": guessed, "ms": 0, "device": None,
                    "engine": "none", "deep": False}
        rs, tr = self._engines.reasoner, self._engines.translator
        if rs is None and tr is None:
            return {"error": "Penerjemah belum siap. Unduh atau pilih modelnya di tab Model."}
        t = time.time()
        out, note, engine, device = None, "", "nllb", None
        if rs is not None and src != tgt and reason.handles(src, tgt):
            try:
                got = rs.translate_text(text, src, tgt, self._settings.get("textContext"), self._settings.get("words"), deep)
                if got:
                    out, note = got
                    engine, device = "penalar", rs.device
            except Exception:
                log("penalar text failed: " + traceback.format_exc())
        if out is None:
            if tr is None:
                return {"error": "Penalar tidak memberi terjemahan, dan NLLB belum siap."}
            try:
                out = tr.translate(text, src, tgt)
                device = tr.device
            except Exception as e:
                log("translate failed: " + traceback.format_exc())
                return {"error": f"Terjemahan gagal: {e}"}
        ms = round((time.time() - t) * 1000)
        if remember and self._settings.get("keepHistory") and text.strip() and src != tgt:
            self._history.add(src, tgt, text, out)
        return {"text": out, "note": note, "src": src, "guessed": guessed, "ms": ms, "device": device,
                "engine": engine, "deep": bool(deep and engine == "penalar")}

    def clear_history(self) -> bool:
        self._history.clear()
        return True

    def history_items(self) -> list:
        return self._history.items

    # Live ------------------------------------------------------------------------------------

    def start_live(self, source: str, src: str, tgt: str, path: str | None = None) -> dict:
        if self._live:
            return {"error": "Sudah sedang mendengarkan."}
        if not self._engines.recognizer or not (self._engines.translator or self._engines.reasoner):
            return {"error": "Pendengar atau penerjemah belum siap. Cek tab Model."}
        from .live import LiveSession
        self._live = LiveSession(self._engines.recognizer, self._engines.translator, self._records, source, src, tgt,
                                self._live_event, wav_path=path, wav_speed=1.0, reasoner=self._engines.reasoner,
                                hints=self._hints, candidates=self._settings.get("liveLangs"))
        try:
            sid = self._live.start()
        except Exception as e:
            self._live = None
            return {"error": str(e)}
        log(f"live started {source} {src}->{tgt} {sid}")
        return {"sid": sid}

    def _hints(self) -> tuple[str, str]:
        """The meeting's topic and the word list, read per line so edits apply mid-meeting."""
        return self._settings.get("liveTopic"), self._settings.get("words")

    def _live_event(self, event: dict) -> None:
        if event.get("type") in ("error", "file-done"):
            if event.get("type") == "error":
                log("live: " + event.get("message", ""))
            threading.Thread(target=self.stop_live, daemon=True).start()
        self._emit(event)

    def stop_live(self) -> dict:
        live, self._live = self._live, None
        if live:
            live.stop()
            log(f"live stopped {live.sid} lines={live.lines}")
            return {"sid": live.sid, "lines": live.lines}
        return {}

    def set_live_target(self, tgt: str) -> bool:
        if self._live:
            self._live.set_target(tgt)
        return True

    def translate_file(self, src: str, tgt: str) -> dict:
        """Picks an audio or video file and translates it whole (Whisper reads any format through FFmpeg)."""
        import webview
        if not self._engines.recognizer or not (self._engines.translator or self._engines.reasoner):
            return {"error": "Pendengar atau penerjemah belum siap. Cek tab Model."}
        picked = self._windows["main"].create_file_dialog(
            webview.FileDialog.OPEN, file_types=("Audio dan video (*.wav;*.mp3;*.m4a;*.mp4;*.mkv;*.webm;*.ogg;*.flac;*.aac)", "Semua berkas (*.*)"))
        if not picked:
            return {"cancelled": True}
        path = picked[0]
        threading.Thread(target=self._transcribe_file, args=(path, src, tgt), daemon=True).start()
        return {"path": path, "name": os.path.basename(path)}

    def _transcribe_file(self, path: str, src: str, tgt: str) -> None:
        from .core import TranscriptLine
        from .live import interpret
        rec = self._engines.recognizer
        tr, rs = self._engines.translator, self._engines.reasoner
        recent: list = []
        session = self._records.begin()
        sid = session.id
        self._records.rename(sid, os.path.splitext(os.path.basename(path))[0])
        self._emit({"type": "started", "sid": sid, "source": "file", "name": os.path.basename(path)})
        count = 0
        try:
            from faster_whisper import decode_audio
            audio = decode_audio(path, sampling_rate=16000)
            with rec._gate:
                if src == "auto":
                    # As live: the language is chosen among the ones the user expects, from the first minute.
                    picked, _ = rec._choose(audio[:60 * 16000], self._settings.get("liveLangs"))
                    lang = picked or "en"
                else:
                    lang = src
                segments, info = rec.model.transcribe(audio, language=languages.get(lang).whisper, beam_size=5,
                                                      vad_filter=True, condition_on_previous_text=False)
                total = float(info.duration or 0) or 1.0
                for s in segments:
                    text = s.text.strip()
                    if not text or s.avg_logprob < -1.4 or not speech.plausible(text, lang):
                        continue
                    count += 1
                    line = TranscriptLine(id=f"h1-{count}", t=round(s.start, 2), speaker="them", src=text, dst=None,
                                          srcLang=lang, dstLang=tgt)
                    note = interpret(line, rs, tr, recent, self._hints(), log, beam=4)
                    self._records.append(sid, line)
                    self._emit({"type": "line", "sid": sid, "id": line.id, "t": line.t, "src": line.shown, "dst": line.dst,
                                "srcLang": lang, "dstLang": tgt, "note": note,
                                "fixes": [[f.from_, f.to] for f in line.fixes or []]})
                    self._emit({"type": "file-progress", "value": min(1.0, s.end / total)})
            self._emit({"type": "file-progress", "value": 1.0})
        except Exception as e:
            log("file failed: " + traceback.format_exc())
            self._emit({"type": "error", "message": f"Berkas tidak bisa dibaca: {e}"})
        finally:
            self._records.end(sid)
            self._emit({"type": "stopped", "sid": sid, "lines": count})

    # Records -------------------------------------------------------------------------------

    @staticmethod
    def _title(s) -> str:
        """Cicada names a record in Chinese (会议 11月25日 18:06); here it is Indonesian unless renamed."""
        if s.renamed:
            return s.title
        local = s.startedAt.astimezone()
        months = "Jan Feb Mar Apr Mei Jun Jul Agu Sep Okt Nov Des".split()
        return f"Rekaman {local.day} {months[local.month - 1]} {local:%H.%M}"

    def sessions(self) -> list:
        out = []
        for s in sorted(self._records.all(), key=lambda s: s.startedAt, reverse=True):
            first = s.lines[0] if s.lines else None
            out.append({"id": s.id, "title": self._title(s), "startedAt": s.startedAt.isoformat(),
                        "seconds": round(s.duration), "lines": len(s.lines),
                        "langs": sorted({l.srcLang for l in s.lines if l.srcLang}),
                        "preview": (first.dst or first.src) if first else ""})
        return out

    def session(self, sid: str) -> dict:
        s = self._records.get(sid)
        if not s:
            return {"error": "Rekaman tidak ditemukan."}
        return {"id": s.id, "title": self._title(s), "startedAt": s.startedAt.isoformat(),
                "lines": [{"t": l.t, "src": l.shown, "dst": l.dst, "srcLang": l.srcLang, "dstLang": l.dstLang}
                          for l in self._records.lines(sid)]}

    def delete_session(self, sid: str) -> bool:
        """Only from the record's own Delete button, after the page asked."""
        self._records.delete(sid)
        log(f"record deleted {sid}")
        return True

    def export_session(self, sid: str, fmt: str) -> dict:
        import webview
        s = self._records.get(sid)
        if not s:
            return {"error": "Rekaman tidak ditemukan."}
        lines = self._records.lines(sid)
        ext = {"txt": "txt", "srt": "srt", "md": "md"}.get(fmt, "txt")
        body = export.as_srt(lines) if ext == "srt" else export.as_markdown(self._title(s), lines) if ext == "md" else export.as_text(self._title(s), lines)
        picked = self._windows["main"].create_file_dialog(webview.FileDialog.SAVE, save_filename=f"{s.id}.{ext}")
        if not picked:
            return {"cancelled": True}
        target = picked if isinstance(picked, str) else picked[0]
        with open(target, "w", encoding="utf-8") as f:
            f.write(body)
        return {"path": target}

    # Models ----------------------------------------------------------------------------------

    def download(self, model_id: str) -> dict:
        if self._downloading:
            return {"error": "Satu unduhan sedang berjalan."}
        self._downloading = model_id
        self._download_cancel.clear()
        threading.Thread(target=self._download, args=(model_id,), daemon=True).start()
        return {"started": model_id}

    def _download(self, model_id: str) -> None:
        last = [0.0]

        def progress(done, total):
            now = time.monotonic()
            if now - last[0] > 0.25 or done >= total:
                last[0] = now
                self._emit({"type": "download", "id": model_id, "done": done, "total": total})
        try:
            if model_id == catalog.GPU["id"]:
                catalog.download_gpu(progress, self._download_cancel.is_set)
                catalog.use_gpu_libraries()
            else:
                catalog.download(model_id, progress, self._download_cancel.is_set)
            log(f"downloaded {model_id}")
            self._emit({"type": "download-done", "id": model_id})
            kind = "gpu" if model_id == catalog.GPU["id"] else catalog.BY_ID[model_id].kind
            if not self._live:
                if kind == "gpu":
                    self._engines.load()
                elif kind == "llm" and self._settings.get("llmModel") == model_id:
                    self._engines.load(("llm", "mt"))
                elif self._settings.get({"mt": "mtModel", "asr": "asrModel", "llm": "llmModel"}[kind]) == model_id:
                    self._engines.load((kind,))
        except InterruptedError:
            self._emit({"type": "download-failed", "id": model_id, "message": "Unduhan dibatalkan."})
        except Exception as e:
            log(f"download {model_id} failed: {traceback.format_exc()}")
            self._emit({"type": "download-failed", "id": model_id, "message": f"Unduhan gagal: {e}"})
        finally:
            self._downloading = None

    def cancel_download(self) -> bool:
        self._download_cancel.set()
        return True

    def remove_model(self, model_id: str) -> dict:
        in_use = model_id in (self._settings.get("mtModel"), self._settings.get("asrModel"))
        if model_id == self._settings.get("llmModel") and self._engines.reasoner:
            in_use = True
        if in_use:
            return {"error": "Model ini sedang dipakai. Pilih model lain dulu."}
        catalog.remove(model_id)
        return {"models": catalog.status(), "gpuInstalled": catalog.gpu_installed()}

    def models(self) -> dict:
        return {"models": catalog.status(), "gpuInstalled": catalog.gpu_installed(), "engines": self._engines.state()}

    def open_data_folder(self) -> bool:
        os.startfile(paths.data())  # noqa: S606 - the user's own folder in Explorer
        return True

    # Floating subtitles ----------------------------------------------------------------------

    OVERLAY_SIZE = (980, 118)

    def overlay(self, show: bool) -> bool:
        """The subtitle bar exists only while it is on: pywebview's hidden windows came back on their own
        in testing, so it is made when turned on and closed when turned off."""
        import webview
        w = self._windows.pop("overlay", None)
        if w:
            w.destroy()
        if show:
            width, height = self.OVERLAY_SIZE
            bar = webview.create_window(
                "Subtitle Senada", url=os.path.join(paths.UI, "overlay.html"), js_api=self, width=width, height=height,
                frameless=True, easy_drag=True, on_top=True, focus=False, background_color="#1D1A4A")
            bar.events.shown += lambda: (_place_at_bottom(bar), _mark_window(bar))
            self._windows["overlay"] = bar
        self._settings.update({"overlay": bool(show)})
        self._emit({"type": "overlay-state", "on": bool(show)})
        return True


def _place_at_bottom(window) -> None:
    """Puts the subtitle bar low and centred in the screen's work area, in physical pixels straight
    through Win32: pywebview's x/y and its screen sizes disagree on display scaling (at 150% the bar
    landed below the screen)."""
    import ctypes
    from ctypes import wintypes
    try:
        hwnd = window.native.Handle.ToInt64()
    except Exception:
        return
    user32 = ctypes.windll.user32
    work = wintypes.RECT()
    user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(work), 0)  # SPI_GETWORKAREA
    rect = wintypes.RECT()
    user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect))
    w, h = rect.right - rect.left, rect.bottom - rect.top
    x = work.left + (work.right - work.left - w) // 2
    y = work.bottom - h - (work.bottom - work.top) // 12
    # HWND_TOPMOST, SWP_NOSIZE | SWP_NOACTIVATE
    user32.SetWindowPos(wintypes.HWND(hwnd), wintypes.HWND(-1), x, y, 0, 0, 0x0001 | 0x0010)


def _first_instance() -> bool:
    """One Senada at a time: a second copy loads the models onto the GPU again, and two of them
    overflowing 6 GB of video memory made each sentence take 35 s instead of 0.3 s in testing."""
    import ctypes
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    _first_instance.handle = kernel32.CreateMutexW(None, False, "Local\\SenadaSingleInstance")
    return kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS


def _own_taskbar_button() -> None:
    """The app runs inside pythonw.exe, so Windows would group it with every other Python window
    under Python's icon. Its own id (the one setup's shortcut carries) gives it its own button."""
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(paths.APP_ID)


def _mark_window(window) -> None:
    """Puts Senada's app id on the window itself (System.AppUserModel.ID). Docks that name a window by
    the program running it see pythonw.exe and show Python's logo; with the id on the window they can
    find Senada's shortcut, its name and its icon instead. The process-wide id above does not reach them."""
    import ctypes
    import uuid
    from ctypes import wintypes

    class GUID(ctypes.Structure):
        _fields_ = [("bytes", ctypes.c_ubyte * 16)]

    class PROPERTYKEY(ctypes.Structure):
        _fields_ = [("fmtid", GUID), ("pid", wintypes.DWORD)]

    class PROPVARIANT(ctypes.Structure):
        _fields_ = [("vt", ctypes.c_ushort), ("pad", ctypes.c_ushort * 3), ("value", ctypes.c_void_p),
                    ("pad2", ctypes.c_void_p)]

    def guid(text: str) -> GUID:
        g = GUID()
        g.bytes[:] = uuid.UUID(text).bytes_le
        return g

    try:
        hwnd = window.native.Handle.ToInt64()
        ctypes.windll.ole32.CoInitialize(None)  # pywebview runs event handlers on their own threads
        store = ctypes.c_void_p()
        shell32 = ctypes.windll.shell32
        shell32.SHGetPropertyStoreForWindow.argtypes = [wintypes.HWND, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)]
        iid = guid("886d8eeb-8cf2-4446-8d02-cdba1dbdcf99")  # IPropertyStore
        if shell32.SHGetPropertyStoreForWindow(hwnd, ctypes.byref(iid), ctypes.byref(store)) != 0:
            return
        vtable = ctypes.cast(ctypes.cast(store, ctypes.POINTER(ctypes.c_void_p))[0], ctypes.POINTER(ctypes.c_void_p))
        set_value = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(PROPERTYKEY),
                                       ctypes.POINTER(PROPVARIANT))(vtable[6])
        commit = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p)(vtable[7])
        release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtable[2])
        key = PROPERTYKEY(guid("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3"), 5)  # PKEY_AppUserModel_ID
        text = ctypes.create_unicode_buffer(paths.APP_ID)
        value = PROPVARIANT(31, (0, 0, 0), ctypes.cast(text, ctypes.c_void_p), None)  # VT_LPWSTR
        try:
            set_value(store, ctypes.byref(key), ctypes.byref(value))
            commit(store)
        finally:
            release(store)
    except Exception as e:  # a missing id only costs the dock icon
        log(f"window id not set: {e}")


def main() -> None:
    import ctypes
    import webview

    if not _first_instance():
        ctypes.windll.user32.MessageBoxW(None, "Senada sudah terbuka. Cari jendelanya di taskbar.", "Senada", 0x40)
        return
    _own_taskbar_button()
    api = Api()
    log(f"start {__version__}")
    main_window = webview.create_window(
        "Senada", url=os.path.join(paths.UI, "index.html"), js_api=api,
        width=1180, height=800, min_size=(820, 620), background_color="#F6F5FB", text_select=True)
    api._windows = {"main": main_window}

    def started():
        api._start_engines()
        if api._settings.get("overlay"):
            api.overlay(True)

    def closing():
        api.stop_live()
        api._engines.close()
        bar = api._windows.pop("overlay", None)
        if bar:
            bar.destroy()

    main_window.events.closing += closing
    main_window.events.shown += lambda: _mark_window(main_window)
    storage = os.path.join(paths.data(), "webview")
    _fresh_ui(storage)
    webview.start(started, gui="edgechromium", private_mode=False, icon=paths.ICON,
                  storage_path=storage, debug=os.environ.get("SENADA_DEBUG") == "1")
