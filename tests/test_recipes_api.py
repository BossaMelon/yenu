from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def make_client(tmp_path: Path) -> TestClient:
    os.environ["YENU_RECIPES_DIR"] = str(tmp_path / "recipes")
    os.environ["YENU_UPLOADS_DIR"] = str(tmp_path / "uploads")
    # Import after env is set
    from yenu.main import app

    return TestClient(app)


def test_api_crud_and_search(tmp_path: Path):
    c = make_client(tmp_path)
    from yenu.settings import RECIPES_DIR

    # Create
    payload = {
        "title": "Pancakes",
        "tags": "breakfast, sweet",
        "ingredients": json.dumps(
            [
                {"name": "Flour", "weight": 200, "unit": "g"},
                {"name": "Milk", "weight": 250, "unit": "ml"},
            ]
        ),
        "steps": json.dumps(["Mix", "Cook"]),
    }
    r = c.post("/api/recipes", data=payload)
    assert r.status_code == 200, r.text
    slug = r.json()["slug"]

    # Get
    r = c.get(f"/api/recipes/{slug}")
    assert r.status_code == 200
    assert r.json()["title"] == "Pancakes"

    # Search by q
    r = c.get("/api/recipes", params={"q": "breakfast"})
    assert r.status_code == 200
    assert r.json()["total"] == 1

    # Update (change title)
    upd = {
        "title": "Banana Pancakes",
        "tags": "breakfast",
        "ingredients": json.dumps(
            [
                {"name": "Flour", "weight": 200, "unit": "g"},
                {"name": "Banana", "weight": 1, "unit": "pc"},
            ]
        ),
        "steps": json.dumps(["Mix", "Cook"]),
    }
    r = c.put(f"/api/recipes/{slug}", data=upd)
    assert r.status_code == 200
    new_slug = r.json()["slug"]
    assert new_slug != slug
    old_path = RECIPES_DIR / f"{slug}.yaml"
    new_path = RECIPES_DIR / f"{new_slug}.yaml"
    assert new_path.exists()
    assert not old_path.exists()

    # Ingredient search
    r = c.get("/api/recipes", params={"ingredient": "banana"})
    assert r.status_code == 200
    assert r.json()["total"] == 1

    # Allow non-numeric ingredient weight
    text_payload = {
        "title": "Salt Pinch",
        "tags": "",
        "ingredients": json.dumps([{"name": "Salt", "weight": "少许", "unit": ""}]),
        "steps": json.dumps(["Sprinkle"]),
    }
    r = c.post("/api/recipes", data=text_payload)
    assert r.status_code == 200, r.text
    text_slug = r.json()["slug"]
    r = c.get(f"/api/recipes/{text_slug}")
    assert r.status_code == 200
    assert r.json()["ingredients"][0]["weight"] == "少许"

    # Export
    r = c.get("/api/export")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

    # Delete
    r = c.delete(f"/api/recipes/{new_slug}")
    assert r.status_code == 200
    r = c.get(f"/api/recipes/{new_slug}")
    assert r.status_code == 404
