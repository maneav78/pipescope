from __future__ import annotations

from pathlib import Path
from typing import Iterator


def iter_files(root: Path) -> Iterator[Path]:
    for p in root.rglob("*"): # recursive pattern search, walk through everything under root
        if p.is_file():
            yield p

def safe_relpath(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except Exception:
        return str(path)

