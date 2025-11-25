from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient


def make_client(tmp_path: Path) -> TestClient:
    os.environ["YENU_RECIPES_DIR"] = str(tmp_path / "recipes")
    os.environ["YENU_UPLOADS_DIR"] = str(tmp_path / "uploads")
    from yenu.main import app

    return TestClient(app)


def test_pages_flow(tmp_path: Path):
    c = make_client(tmp_path)
    # Index page
    r = c.get("/")
    assert r.status_code == 200
    assert "Yenu" in r.text

    # Create via form
    form = {
        "title": "Noodles",
        "tags": "lunch",
        "step_list": "Boil water\nCook noodles",
        "ing_name": ["Noodles"],
        "ing_weight": ["100"],
        "ing_unit": ["g"],
    }
    r = c.post("/recipes/new", data=form, follow_redirects=False)
    assert r.status_code == 303
    loc = r.headers["Location"]

    # Detail page
    r = c.get(loc)
    assert r.status_code == 200
    assert "Noodles" in r.text
