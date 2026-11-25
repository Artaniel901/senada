"""The window: pywebview (Edge WebView2) showing ui/index.html, with `Api` as window.pywebview.api.
Engines load in the background after the window opens; everything they report reaches the page as
window.cicadaEvent({...}). A second, frameless window shows the floating subtitles."""
from __future__ import annotations

import json
import os
import threading
import time
import traceback

from . import __version__, catalog, detect, export, languages, paths
from .store import History, Settings

catalog.use_gpu_libraries()

from .core import Paths, SessionStore  # noqa: E402

LOG = os.path.join(paths.data(), "cicada-offline.log")


def log(message: str) -> None:
    try:
        os.makedirs(paths.data(), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + message + "\n")
    except OSError:
        pass


def _drive_script() -> str | None:
    path = os.environ.get("CICADA_OFFLINE_DRIVE")
    if not path:
        return None
    with open(path, encoding="utf-8") as f:
        return f.read()


class Engines:
    """Whisper and NLLB, loaded once and swapped when Settings picks another model."""

    def __init__(self, settings: Settings, emit):
        self._settings, self.emit = settings, emit
        self.translator = None
        self.recognizer = None
        self._gate = threading.Lock()

    def state(self) -> dict:
        return {
            "mt": {"model": self.translator.model_id, "device": self.translator.device} if self.translator else None,
            "asr": {"model": self.recognizer.model_id, "device": self.recognizer.device} if self.recognizer else None,
        }

    def load(self, which=("mt", "asr")) -> None:
        with self._gate:
            device = self._settings.get("device")
            if "mt" in which:
                self.translator = None
                self._load("mt", self._settings.get("mtModel"), device)
            if "asr" in which:
                self.recognizer = None
                self._load("asr", self._settings.get("asrModel"), device)

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
            else:
                from .asr import Recognizer
                self.recognizer = Recognizer(model_id, device)
                got = self.recognizer
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
            if name == "overlay" and event.get("type") not in ("line", "overlay-style", "stopped", "started"):
                continue
            try:
                w.evaluate_js(f"window.cicadaEvent && window.cicadaEvent({payload})")
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
        values = self._settings.update(patch or {})
        reload = []
        if values["mtModel"] != before["mtModel"]:
            reload.append("mt")
        if values["asrModel"] != before["asrModel"]:
            reload.append("asr")
        if values["device"] != before["device"]:
            reload = ["mt", "asr"]
        if reload and not self._live:
            threading.Thread(target=self._engines.load, args=(tuple(reload),), daemon=True).start()
        if "overlaySize" in (patch or {}):
            self._emit({"type": "overlay-style", "size": values["overlaySize"]})
        return values

    def detect(self, text: str):
        return detect.detect(text)

    def translate(self, text: str, src: str, tgt: str, remember: bool = True) -> dict:
        tr = self._engines.translator
        if tr is None:
            return {"error": "Penerjemah belum siap. Unduh atau pilih modelnya di tab Model."}
        guessed = None
        if src == "auto":
            guessed = detect.detect(text)
            src = guessed or ("en" if tgt != "en" else "id")
        t = time.time()
        try:
            out = tr.translate(text, src, tgt)
        except Exception as e:
            log("translate failed: " + traceback.format_exc())
            return {"error": f"Terjemahan gagal: {e}"}
        ms = round((time.time() - t) * 1000)
        if remember and self._settings.get("keepHistory") and text.strip() and src != tgt:
            self._history.add(src, tgt, text, out)
        return {"text": out, "src": src, "guessed": guessed, "ms": ms, "device": tr.device}

    def clear_history(self) -> bool:
        self._history.clear()
        return True

    def history_items(self) -> list:
        return self._history.items

    # Live ------------------------------------------------------------------------------------

    def start_live(self, source: str, src: str, tgt: str, path: str | None = None) -> dict:
        if self._live:
            return {"error": "Sudah sedang mendengarkan."}
        if not self._engines.recognizer or not self._engines.translator:
            return {"error": "Pendengar atau penerjemah belum siap. Cek tab Model."}
        from .live import LiveSession
        self._live = LiveSession(self._engines.recognizer, self._engines.translator, self._records, source, src, tgt,
                                self._live_event, wav_path=path, wav_speed=1.0)
        try:
            sid = self._live.start()
        except Exception as e:
            self._live = None
            return {"error": str(e)}
        log(f"live started {source} {src}->{tgt} {sid}")
        return {"sid": sid}

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
        if not self._engines.recognizer or not self._engines.translator:
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
        rec = self._engines.recognizer
        tr = self._engines.translator
        session = self._records.begin()
        sid = session.id
        self._records.rename(sid, os.path.splitext(os.path.basename(path))[0])
        self._emit({"type": "started", "sid": sid, "source": "file", "name": os.path.basename(path)})
        count = 0
        try:
            code = languages.get(src).whisper if src != "auto" else None
            with rec._gate:
                segments, info = rec.model.transcribe(path, language=code, beam_size=5, vad_filter=True,
                                                      condition_on_previous_text=False)
                found = languages.from_whisper(info.language)
                lang = src if src != "auto" else (found.id if found else "en")
                total = float(info.duration or 0) or 1.0
                for s in segments:
                    text = s.text.strip()
                    if not text:
                        continue
                    dst = tr.translate(text, lang, tgt, beam=4) if lang != tgt else None
                    count += 1
                    line = TranscriptLine(id=f"h1-{count}", t=round(s.start, 2), speaker="them", src=text, dst=dst,
                                          srcLang=lang, dstLang=tgt)
                    self._records.append(sid, line)
                    self._emit({"type": "line", "sid": sid, "id": line.id, "t": line.t, "src": text, "dst": dst,
                                "srcLang": lang, "dstLang": tgt})
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
                "lines": [{"t": l.t, "src": l.src, "dst": l.dst, "srcLang": l.srcLang, "dstLang": l.dstLang}
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
                elif self._settings.get("mtModel" if kind == "mt" else "asrModel") == model_id:
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
                "Subtitle Cicada", url=os.path.join(paths.UI, "overlay.html"), js_api=self, width=width, height=height,
                frameless=True, easy_drag=True, on_top=True, focus=False, background_color="#1D1A4A")
            bar.events.shown += lambda: _place_at_bottom(bar)
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
    """One Cicada Offline at a time: a second copy loads the models onto the GPU again, and two of them
    overflowing 6 GB of video memory made each sentence take 35 s instead of 0.3 s in testing."""
    import ctypes
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    _first_instance.handle = kernel32.CreateMutexW(None, False, "Local\\CicadaOfflineSingleInstance")
    return kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS


def main() -> None:
    import ctypes
    import webview

    if not _first_instance():
        ctypes.windll.user32.MessageBoxW(None, "Cicada Offline sudah terbuka. Cari jendelanya di taskbar.", "Cicada Offline", 0x40)
        return
    api = Api()
    log(f"start {__version__}")
    main_window = webview.create_window(
        "Cicada Offline", url=os.path.join(paths.UI, "index.html"), js_api=api,
        width=1180, height=800, min_size=(820, 620), background_color="#F6F5FB", text_select=True)
    api._windows = {"main": main_window}

    def started():
        api._start_engines()
        if api._settings.get("overlay"):
            api.overlay(True)

    def closing():
        api.stop_live()
        bar = api._windows.pop("overlay", None)
        if bar:
            bar.destroy()

    main_window.events.closing += closing
    webview.start(started, gui="edgechromium", private_mode=False,
                  storage_path=os.path.join(paths.data(), "webview"), debug=os.environ.get("CICADA_OFFLINE_DEBUG") == "1")
