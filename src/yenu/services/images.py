from __future__ import annotations

import imghdr
import os
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image

from yenu.settings import THUMB_MAX_PX, UPLOADS_DIR, MAX_IMAGE_MB
from yenu.utils import atomic_write, safe_join, slugify_title


ALLOWED_FORMATS = {"jpeg", "png"}


def _detect_format(data: bytes) -> Optional[str]:
    kind = imghdr.what(None, h=data)
    if kind == "jpg":
        kind = "jpeg"
    return kind


def validate_image(data: bytes) -> Tuple[bool, str]:
    max_bytes = int(MAX_IMAGE_MB * 1024 * 1024)
    if len(data) > max_bytes:
        return False, f"Image too large (>{MAX_IMAGE_MB} MB)"
    kind = _detect_format(data)
    if kind not in ALLOWED_FORMATS:
        return False, "Unsupported image type"
    return True, kind or ""


def _resize_if_needed(img: Image.Image) -> Image.Image:
    w, h = img.size
    max_dim = max(w, h)
    if max_dim <= THUMB_MAX_PX:
        return img
    scale = THUMB_MAX_PX / float(max_dim)
    new_size = (int(w * scale), int(h * scale))
    return img.resize(new_size, Image.LANCZOS)


def save_image(slug: str, file_name: str, data: bytes) -> str:
    ok, kind = validate_image(data)
    if not ok:
        raise ValueError(kind)
    base = UPLOADS_DIR / slug
    base.mkdir(parents=True, exist_ok=True)
    # Sanitize file name
    stem = slugify_title(Path(file_name).stem) or slug
    ext = ".jpg" if kind == "jpeg" else ".png"
    out_name = stem + ext
    target = safe_join(base, out_name)

    import io as _io  # local import to avoid global dependency on import

    with Image.open(_io.BytesIO(data)) as img:
        img = _resize_if_needed(img.convert("RGB" if kind == "jpeg" else "RGBA"))
        out = _io.BytesIO()
        if kind == "jpeg":
            img.save(out, format="JPEG", quality=85, optimize=True)
        else:
            img.save(out, format="PNG", optimize=True)
        out.seek(0)
        atomic_write(target, out.read())

    # Return web-relative path
    rel = Path("assets/uploads") / slug / target.name
    return rel.as_posix()
