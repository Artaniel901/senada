"""A meeting record as a file to keep: bilingual text, SRT subtitles, or Markdown."""
from __future__ import annotations


def _clock(t: float, srt: bool = False) -> str:
    h, rest = divmod(max(0.0, t), 3600)
    m, s = divmod(rest, 60)
    if srt:
        return "%02d:%02d:%02d,%03d" % (h, m, int(s), int(round((s - int(s)) * 1000)) % 1000)
    return "%02d:%02d:%02d" % (h, m, int(s))


def _src(line) -> str:
    """The line as shown: what was heard with the misheard words Penalar fixed (Cicada's `shown`)."""
    return getattr(line, "shown", line.src)


def as_text(title: str, lines: list) -> str:
    out = [title, ""]
    for l in lines:
        out.append(f"[{_clock(l.t)}] {_src(l)}")
        if l.dst:
            out.append(f"           {l.dst}")
    return "\n".join(out) + "\n"


def as_srt(lines: list, translated: bool = True) -> str:
    out = []
    for i, l in enumerate(lines):
        end = lines[i + 1].t if i + 1 < len(lines) else l.t + 4.0
        end = min(end, l.t + 8.0)
        body = (l.dst or _src(l)) if translated else _src(l)
        out += [str(i + 1), f"{_clock(l.t, True)} --> {_clock(max(end, l.t + 0.5), True)}", body, ""]
    return "\n".join(out)


def as_markdown(title: str, lines: list) -> str:
    out = [f"# {title}", "", "| Waktu | Asli | Terjemahan |", "|---|---|---|"]
    for l in lines:
        cell = lambda s: (s or "").replace("|", "\\|").replace("\n", " ")
        out.append(f"| {_clock(l.t)} | {cell(_src(l))} | {cell(l.dst)} |")
    return "\n".join(out) + "\n"
