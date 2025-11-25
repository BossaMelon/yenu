from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Iterable

from pypinyin import lazy_pinyin


_cjk_re = re.compile(r"[\u4e00-\u9fff]")


def _is_cjk(ch: str) -> bool:
    return bool(_cjk_re.match(ch))


def slugify_title(title: str) -> str:
    """Slugify a title using pinyin for Chinese characters.

    - Chinese chars -> pinyin (lowercase)
    - ASCII letters/digits -> lowercase kept
    - Others -> treated as separators (hyphens)
    - Multiple separators collapsed; trimmed from ends
    """
    parts: list[str] = []
    for ch in title:
        if _is_cjk(ch):
            p = lazy_pinyin(ch)
            if p:
                parts.append(p[0].lower())
            else:
                parts.append("")
        elif ch.isalnum():
            parts.append(ch.lower())
        else:
            parts.append("-")
    slug = "".join(parts)
    # Collapse multiple hyphens, strip
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "recipe"


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(delete=False, dir=str(path.parent)) as tmp:
        tmp.write(data)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_name = tmp.name
    os.replace(tmp_name, path)


def safe_join(base: Path, *paths: str) -> Path:
    candidate = (base / Path(*paths)).resolve()
    base_resolved = base.resolve()
    if not str(candidate).startswith(str(base_resolved)):
        raise ValueError("Path traversal detected")
    return candidate


def move_tree(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.move(str(src), str(dst))


def rmtree_silent(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)


def paginate(items: list, page: int, page_size: int) -> list:
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 10
    start = (page - 1) * page_size
    end = start + page_size
    return items[start:end]
