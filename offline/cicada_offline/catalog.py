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
    kind: str  # "mt" or "asr"
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
]
BY_ID = {m.id: m for m in MODELS}
DEFAULT = {"mt": "nllb-1.3b", "asr": "whisper-small"}

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
    elif model_id in BY_ID:
        d = folder(model_id)
    else:
        return
    if os.path.isdir(d):
        shutil.rmtree(d)
