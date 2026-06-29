"""
Shared JSON file I/O with explicit UTF-8 handling.

Why this exists: Path.read_text()/write_text() use the platform default encoding
(cp1252 on Windows, UTF-8 on Linux). Files written on a Windows dev machine and
then read by the Linux GitHub Actions runner would crash on bytes like 0x96 (an
en-dash) or 0xe9 (e-acute). These helpers always write UTF-8 and read tolerantly
so a stray non-UTF-8 byte never aborts the pipeline.
"""

import json
from pathlib import Path


def read_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    raw = p.read_bytes()
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return json.loads(raw.decode(enc))
        except (UnicodeDecodeError, ValueError):
            continue
    # Last resort: never crash the run over one bad file
    return json.loads(raw.decode("utf-8", errors="replace"))


def write_json(path, obj) -> None:
    Path(path).write_text(
        json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8"
    )
