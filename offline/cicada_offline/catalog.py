"""The engines Cicada Offline can download, and the downloader. The only time the app goes online is
here, once per model, from Hugging Face; after that everything runs on this computer.

Files are fetched straight from huggingface.co (not through huggingface_hub, whose cache lives on C:),
into models/<id>/ via a .part file, and each LFS file is checked against the SHA-256 the Hub lists."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import urllib.request
from dataclasses import dataclass

from . import paths

HF = "https://huggingface.co"
# NLLB's SentencePiece model is the same for every size; the 1.3B CT2 build ships without it.
SPM = ("JustFrederik/nllb-200-distilled-600M-ct2-int8", "sentencepiece.bpe.model")


@dataclass(frozen=True)
class Model:
    id: str
    kind: str  # "mt", "asr" or "llm"
    title: str
    blurb: str
    repo: str
    files: tuple
    size_mb: int
    license: str


MODELS = [
    Model("nllb-1.3b", "mt", "Penerjemah · Kualitas", "NLLB-200 1.3B, 200 bahasa", "OpenNMT/nllb-200-distilled-1.3B-ct2-int8",
          ("config.json", "model.bin", "shared_vocabulary.json"), 1390, "CC-BY-NC-4.0"),
    Model("nllb-600m", "mt", "Penerjemah · Cepat", "NLLB-200 600M, 200 bahasa", "JustFrederik/nllb-200-distilled-600M-ct2-int8",
          ("config.json", "model.bin", "shared_vocabulary.txt"), 630, "CC-BY-NC-4.0"),
    Model("whisper-small", "asr", "Pendengar · Seimbang", "Whisper small, 99 bahasa", "Systran/faster-whisper-small",
          ("config.json", "model.bin", "tokenizer.json", "vocabulary.txt"), 490, "MIT"),
    Model("whisper-base", "asr", "Pendengar · Ringan", "Whisper base, paling cepat", "Systran/faster-whisper-base",
          ("config.json", "model.bin", "tokenizer.json", "vocabulary.txt"), 150, "MIT"),
    Model("whisper-turbo", "asr", "Pendengar · Akurat", "Whisper large-v3 turbo", "deepdml/faster-whisper-large-v3-turbo-ct2",
          ("config.json", "model.bin", "preprocessor_config.json", "tokenizer.json", "vocabulary.json"), 1620, "MIT"),
    # Penalar: Gemma 4 (Google, Apache-2.0) in unsloth's 4-bit GGUF, for llama.cpp.
    Model("gemma4-e4b", "llm", "Penalar · Kualitas", "Gemma 4 E4B, paham konteks, idiom dan maksud", "unsloth/gemma-4-E4B-it-GGUF",
          ("gemma-4-E4B-it-Q4_K_M.gguf",), 4746, "Apache-2.0"),
    Model("gemma4-e2b", "llm", "Penalar · Ringan", "Gemma 4 E2B, lebih kecil dan cepat", "unsloth/gemma-4-E2B-it-GGUF",
          ("gemma-4-E2B-it-Q4_K_M.gguf",), 2962, "Apache-2.0"),
]
BY_ID = {m.id: m for m in MODELS}
DEFAULT = {"mt": "nllb-1.3b", "asr": "whisper-small", "llm": "gemma4-e4b"}

# llama.cpp's llama-server for Penalar: the Vulkan build runs on NVIDIA, AMD and Intel GPUs without a CUDA
# download, and on the CPU otherwise. Pinned to one build; the zip is checked against its SHA-256.
LLAMA = {
    "id": "llama-vulkan",
    "tag": "b12721",
    "asset": "llama-b12721-bin-win-vulkan-x64.zip",
    "sha256": "2e15aaf92807ef03b64c38ac52ad403770d4a67079ddfd00808bd86c51e20f4e",
    "size": 39_100_000,
    "license": "MIT",
}

# NVIDIA GPU speed-up: CTranslate2 already carries cuDNN; cuBLAS is the missing piece. Only its two
# DLLs are kept from NVIDIA's PyPI wheel (pinned by SHA-256).
GPU = {
    "id": "gpu-cuda",
    "title": "Percepatan GPU NVIDIA",
    "blurb": "cuBLAS 12.9 untuk kartu NVIDIA",
    "package": "nvidia-cublas-cu12",
    "version": "12.9.2.10",
    "file": "nvidia_cublas_cu12-12.9.2.10-py3-none-win_amd64.whl",
    "sha256":"623f43027d40d44ceadf0043f002bd25cf353e8f13ce90b9a87057019f560661",
    "size": 553_000_000,
    "members": ("nvidia/cublas/bin/cublas64_12.dll", "nvidia/cublas/bin/cublasLt64_12.dll"),
    "license": "NVIDIA",
}


def gpu_folder() -> str:
    return os.path.join(paths.models(), GPU["id"])


def gpu_installed() -> bool:
    return all(os.path.isfile(os.path.join(gpu_folder(), os.path.basename(m))) for m in GPU["members"])


def use_gpu_libraries() -> None:
    """Lets CTranslate2 find cuBLAS when the GPU pack is downloaded (call before loading models)."""
    if gpu_installed():
        folder = gpu_folder()
        os.add_dll_directory(folder)
        if folder not in os.environ.get("PATH", ""):
            os.environ["PATH"] = folder + os.pathsep + os.environ.get("PATH", "")


def has_nvidia() -> bool:
    try:
        import ctranslate2
        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False


def download_gpu(progress=None, cancelled=lambda: False) -> None:
    import zipfile

    d = gpu_folder()
    os.makedirs(d, exist_ok=True)
    wheel = os.path.join(d, "cublas.whl.part")
    digest = hashlib.sha256()
    done = 0
    with urllib.request.urlopen(f"https://pypi.org/pypi/{GPU['package']}/{GPU['version']}/json", timeout=30) as r:
        url = next(f["url"] for f in json.load(r)["urls"] if f["filename"] == GPU["file"])
    req = urllib.request.Request(url, headers={"User-Agent": "cicada-offline"})
    with urllib.request.urlopen(req, timeout=60) as r, open(wheel, "wb") as out:
        total = int(r.headers.get("Content-Length") or GPU["size"])
        while chunk := r.read(1 << 20):
            if cancelled():
                out.close()
                os.remove(wheel)
                raise InterruptedError("download cancelled")
            out.write(chunk)
            digest.update(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)
    try:
        if digest.hexdigest() != GPU["sha256"]:
            raise RuntimeError("cuBLAS wheel: SHA-256 does not match PyPI's")
        with zipfile.ZipFile(wheel) as z:
            for member in GPU["members"]:
                with z.open(member) as src, open(os.path.join(d, os.path.basename(member)) + ".part", "wb") as dst:
                    shutil.copyfileobj(src, dst)
                os.replace(os.path.join(d, os.path.basename(member)) + ".part", os.path.join(d, os.path.basename(member)))
    finally:
        os.remove(wheel)  # the wheel is only a carrier; the two DLLs stay


def llama_folder() -> str:
    return os.path.join(paths.models(), LLAMA["id"])


def llama_installed() -> bool:
    return os.path.isfile(os.path.join(llama_folder(), ".complete")) and         os.path.isfile(os.path.join(llama_folder(), "llama-server.exe"))


def download_llama(progress=None, cancelled=lambda: False) -> None:
    """The server's zip from llama.cpp's GitHub release (the URL comes from the release, the hash is pinned)."""
    import zipfile

    d = llama_folder()
    os.makedirs(d, exist_ok=True)
    marker = os.path.join(d, ".complete")
    if os.path.exists(marker):
        os.remove(marker)
    req = urllib.request.Request(f"https://api.github.com/repos/ggml-org/llama.cpp/releases/tags/{LLAMA['tag']}",
                                 headers={"User-Agent": "cicada-offline", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        url = next(a["browser_download_url"] for a in json.load(r)["assets"] if a["name"] == LLAMA["asset"])
    part = os.path.join(d, "llama.zip.part")
    digest = hashlib.sha256()
    done = 0
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "cicada-offline"}), timeout=60) as r,             open(part, "wb") as out:
        total = int(r.headers.get("Content-Length") or LLAMA["size"])
        while chunk := r.read(1 << 20):
            if cancelled():
                out.close()
                os.remove(part)
                raise InterruptedError("download cancelled")
            out.write(chunk)
            digest.update(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)
    try:
        if digest.hexdigest() != LLAMA["sha256"]:
            raise RuntimeError("llama.cpp: SHA-256 does not match the pinned build")
        with zipfile.ZipFile(part) as z:
            for name in z.namelist():
                target = os.path.realpath(os.path.join(d, name))
                if not target.startswith(os.path.realpath(d) + os.sep):
                    raise RuntimeError(f"llama.cpp zip: unsafe path {name}")
            z.extractall(d)
    finally:
        os.remove(part)
    with open(marker, "w") as f:
        f.write(LLAMA["tag"])


def gguf_path(model_id: str) -> str:
    return os.path.join(folder(model_id), BY_ID[model_id].files[0])


def folder(model_id: str) -> str:
    return os.path.join(paths.models(), model_id)


def _wanted(m: Model) -> list[tuple[str, str]]:
    """(repo, file) pairs that make the model whole."""
    out = [(m.repo, f) for f in m.files]
    if m.kind == "mt":
        out.append(SPM)
    return out


def installed(model_id: str) -> bool:
    m = BY_ID[model_id]
    d = folder(model_id)
    if m.kind == "llm" and not llama_installed():
        return False
    return os.path.isfile(os.path.join(d, ".complete")) and all(
        os.path.isfile(os.path.join(d, f)) for _, f in _wanted(m))


def status() -> list[dict]:
    return [{"id": m.id, "kind": m.kind, "title": m.title, "blurb": m.blurb, "sizeMb": m.size_mb,
             "license": m.license, "installed": installed(m.id)} for m in MODELS]


def _listing(repo: str) -> dict[str, dict]:
    with urllib.request.urlopen(f"{HF}/api/models/{repo}/tree/main", timeout=30) as r:
        return {f["path"]: f for f in json.load(r)}


def download(model_id: str, progress=None, cancelled=lambda: False) -> None:
    """Fetches every file of the model; `progress(done_bytes, total_bytes)` as it goes. Already
    complete files are kept, so a broken download picks up where it stopped (per file)."""
    m = BY_ID[model_id]
    if m.kind == "llm" and not llama_installed():
        download_llama(None, cancelled)  # 38 MB, before the model so the model's progress bar is the real one
    d = folder(model_id)
    os.makedirs(d, exist_ok=True)
    marker = os.path.join(d, ".complete")
    if os.path.exists(marker):
        os.remove(marker)
    listings: dict[str, dict] = {}
    plan = []
    for repo, name in _wanted(m):
        if repo not in listings:
            listings[repo] = _listing(repo)
        info = listings[repo].get(name)
        if info is None:
            raise RuntimeError(f"{repo} has no {name}")
        plan.append((repo, name, int(info.get("size") or 0), (info.get("lfs") or {}).get("oid")))
    total = sum(p[2] for p in plan)
    done = 0
    for repo, name, size, sha in plan:
        target = os.path.join(d, name)
        if os.path.isfile(target) and os.path.getsize(target) == size:
            done += size
            if progress:
                progress(done, total)
            continue
        part = target + ".part"
        digest = hashlib.sha256()
        req = urllib.request.Request(f"{HF}/{repo}/resolve/main/{name}", headers={"User-Agent": "cicada-offline"})
        with urllib.request.urlopen(req, timeout=60) as r, open(part, "wb") as out:
            while chunk := r.read(1 << 20):
                if cancelled():
                    raise InterruptedError("download cancelled")
                out.write(chunk)
                digest.update(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
        if os.path.getsize(part) != size:
            raise RuntimeError(f"{name}: got {os.path.getsize(part)} bytes, expected {size}")
        if sha and digest.hexdigest() != sha:
            raise RuntimeError(f"{name}: SHA-256 does not match the Hub's")
        os.replace(part, target)
    with open(marker, "w") as f:
        f.write(m.repo)


def remove(model_id: str) -> None:
    """Deletes one downloaded model folder (the user asked for it in Settings)."""
    if model_id == GPU["id"]:
        d = gpu_folder()
    elif model_id == LLAMA["id"]:
        d = llama_folder()
    elif model_id in BY_ID:
        d = folder(model_id)
    else:
        return
    if os.path.isdir(d):
        shutil.rmtree(d)
