from __future__ import annotations

import io
import json
import shutil
import zipfile
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

import yaml

from yenu.models import Recipe
from yenu.settings import RECIPES_DIR
from yenu.utils import atomic_write, paginate, slugify_title


def _recipe_path_for_slug(slug: str) -> Path:
    return RECIPES_DIR / f"{slug}.yaml"


def slug_for_title(title: str) -> str:
    return slugify_title(title)


def list_recipe_files() -> List[Path]:
    return sorted(RECIPES_DIR.glob("*.yaml"))


def load_recipe_by_path(path: Path) -> Recipe:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return Recipe(**data)


def get_all_recipes() -> List[Tuple[str, Recipe]]:
    items: List[Tuple[str, Recipe]] = []
    for file in list_recipe_files():
        try:
            recipe = load_recipe_by_path(file)
            slug = file.stem
            items.append((slug, recipe))
        except Exception:
            # Skip invalid files silently; could log in real app
            continue
    return items


def search_recipes(
    q: Optional[str] = None,
    tag: Optional[str] = None,
    ingredient: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    items = get_all_recipes()

    def matches(slug: str, r: Recipe) -> bool:
        if q:
            ql = q.lower()
            if ql not in r.title.lower() and not any(
                ql in t.lower() for t in (r.tags or [])
            ):
                return False
        if tag:
            tl = tag.lower()
            if not any(tl == t.lower() for t in (r.tags or [])):
                return False
        if ingredient:
            il = ingredient.lower()
            if not any(il in ing.name.lower() for ing in r.ingredients):
                return False
        return True

    filtered = [(s, r) for s, r in items if matches(s, r)]
    total = len(filtered)
    paginated = paginate(filtered, page, page_size)
    data = [
        {
            "slug": s,
            "title": r.title,
            "tags": r.tags or [],
            "dish_image_path": r.dish_image_path,
        }
        for s, r in paginated
    ]
    return {"total": total, "items": data}


def read_recipe(slug: str) -> Optional[Recipe]:
    path = _recipe_path_for_slug(slug)
    if not path.exists():
        return None
    return load_recipe_by_path(path)


def write_recipe(slug: str, recipe: Recipe) -> str:
    # Returns slug (may change if title changes)
    desired_slug = slug_for_title(recipe.title)
    if desired_slug != slug:
        # rename file after write (caller should manage assets rename)
        slug = desired_slug
    path = _recipe_path_for_slug(slug)
    data = yaml.safe_dump(recipe.dict_for_yaml(), allow_unicode=True, sort_keys=False)
    atomic_write(path, data.encode("utf-8"))
    return slug


def create_recipe(recipe: Recipe) -> str:
    slug = slug_for_title(recipe.title)
    path = _recipe_path_for_slug(slug)
    if path.exists():
        # Overwrite to keep idempotency during import; could raise otherwise
        pass
    data = yaml.safe_dump(recipe.dict_for_yaml(), allow_unicode=True, sort_keys=False)
    atomic_write(path, data.encode("utf-8"))
    return slug


def delete_recipe(slug: str) -> bool:
    path = _recipe_path_for_slug(slug)
    if not path.exists():
        return False
    path.unlink()
    return True


def export_all_json() -> str:
    items = get_all_recipes()
    payload = [
        {"slug": slug, **recipe.dict_for_yaml()} for slug, recipe in items
    ]
    return json.dumps(payload, ensure_ascii=False, indent=2)


def import_from_json(payload: str) -> dict:
    data = json.loads(payload)
    created = 0
    updated = 0
    slugs_seen = set()
    for item in data:
        # Deduplicate by title
        r = Recipe(
            title=item["title"],
            tags=item.get("tags"),
            ingredients=item["ingredients"],
            steps=item["steps"],
            dish_image_path=item.get("dish_image_path"),
        )
        slug = slug_for_title(r.title)
        slugs_seen.add(slug)
        path = _recipe_path_for_slug(slug)
        existed = path.exists()
        write_recipe(slug, r)
        if existed:
            updated += 1
        else:
            created += 1
    return {"created": created, "updated": updated}


def backup_recipes_zip() -> bytes:
    # Create an in-memory zip archive of the recipes directory
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in list_recipe_files():
            arcname = path.relative_to(RECIPES_DIR.parent)
            zf.write(path, arcname=str(arcname))
    buf.seek(0)
    return buf.read()
