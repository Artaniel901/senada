"""Renders ui/senada.svg into senada.ico (16 to 256 px) with headless Chrome or Edge, no image library.
Each size is drawn by the browser from the vector, then the PNGs are packed into one .ico (Windows
reads PNG entries in an icon since Vista). Run after changing the logo:
    .venv\\Scripts\\python.exe tools\\make_icon.py [--preview out.png]"""
from __future__ import annotations

import argparse
import os
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SVG = os.path.join(HERE, "ui", "senada.svg")
ICO = os.path.join(HERE, "senada.ico")
SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)
BROWSERS = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
)


def browser() -> str:
    for path in BROWSERS:
        if os.path.exists(path):
            return path
    sys.exit("Chrome or Edge is needed to render the icon")


def render(exe: str, size: int, folder: str) -> bytes:
    page = os.path.join(folder, f"icon{size}.html")
    with open(SVG, encoding="utf-8") as f:
        svg = f.read()
    with open(page, "w", encoding="utf-8") as f:
        f.write("<!doctype html><style>html,body{margin:0;overflow:hidden;background:transparent}"
                f"svg{{display:block;width:{size}px;height:{size}px}}</style>{svg}")
    out = os.path.join(folder, f"icon{size}.png")
    subprocess.run([exe, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
                    f"--user-data-dir={os.path.join(folder, 'profile')}", "--default-background-color=00000000",
                    f"--window-size={size},{size}", f"--screenshot={out}", "file:///" + page.replace("\\", "/")],
                   check=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
    with open(out, "rb") as f:
        png = f.read()
    width, height = struct.unpack(">II", png[16:24])
    if (width, height) != (size, size):
        sys.exit(f"{size} px rendered as {width}x{height}")
    return png


def pack(pngs: dict[int, bytes]) -> bytes:
    head = struct.pack("<HHH", 0, 1, len(pngs))
    offset, entries, body = 6 + 16 * len(pngs), b"", b""
    for size, png in sorted(pngs.items()):
        side = 0 if size >= 256 else size  # 0 means 256 in an icon directory
        entries += struct.pack("<BBBBHHII", side, side, 0, 0, 1, 32, len(png), offset + len(body))
        body += png
    return head + entries + body


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", help="also save the 256 px PNG here")
    args = ap.parse_args()
    exe = browser()
    with tempfile.TemporaryDirectory(prefix="senada-icon-") as folder:
        pngs = {size: render(exe, size, folder) for size in SIZES}
    with open(ICO, "wb") as f:
        f.write(pack(pngs))
    if args.preview:
        with open(args.preview, "wb") as f:
            f.write(pngs[256])
    print(f"{ICO}: {len(SIZES)} sizes, {os.path.getsize(ICO):,} bytes")


if __name__ == "__main__":
    main()
