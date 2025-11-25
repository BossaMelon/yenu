from __future__ import annotations

import os
from pathlib import Path


def _env_path(name: str, default: str) -> Path:
    v = os.environ.get(name, default)
    p = Path(v)
    return p


BASE_DIR = Path(os.environ.get("YENU_BASE_DIR", ".")).resolve()

# Data and uploads directories are configurable via env for tests/deployment
RECIPES_DIR = (_env_path("YENU_RECIPES_DIR", str(BASE_DIR / "data/recipes"))).resolve()
UPLOADS_DIR = (_env_path("YENU_UPLOADS_DIR", str(BASE_DIR / "assets/uploads"))).resolve()

MAX_IMAGE_MB = float(os.environ.get("YENU_MAX_IMAGE_MB", "8"))
THUMB_MAX_PX = int(os.environ.get("YENU_THUMB_MAX_PX", "800"))

# Ensure base directories exist at import time (safe on repeated calls)
RECIPES_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

