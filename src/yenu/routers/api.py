from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

from yenu.models import Ingredient, Recipe
from yenu.services.images import save_image
from yenu.services.recipes_yaml import (
    backup_recipes_zip,
    create_recipe,
    delete_recipe,
    export_all_json,
    import_from_json,
    read_recipe,
    search_recipes,
    slug_for_title,
    write_recipe,
)
from yenu.settings import UPLOADS_DIR
from yenu.utils import move_tree


router = APIRouter()


@router.get("/recipes")
def api_list_recipes(
    q: Optional[str] = None,
    tag: Optional[str] = None,
    ingredient: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
):
    return search_recipes(q=q, tag=tag, ingredient=ingredient, page=page, page_size=page_size)


@router.get("/recipes/{slug}")
def api_get_recipe(slug: str):
    r = read_recipe(slug)
    if not r:
        raise HTTPException(status_code=404, detail="Not found")
    return {"slug": slug, **r.dict_for_yaml()}


@router.post("/recipes")
async def api_create_recipe(
    title: str = Form(...),
    tags: Optional[str] = Form(None),
    ingredients: Optional[str] = Form(None),  # JSON string list of {name,weight,unit}
    steps: Optional[str] = Form(None),  # JSON string list
    dish_image: UploadFile | None = File(None),
):
    # Accept either JSON body or form fields
    if ingredients is None or steps is None:
        raise HTTPException(status_code=400, detail="ingredients and steps are required")
    try:
        ing_list = json.loads(ingredients)
        step_list = json.loads(steps)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON for ingredients/steps")

    recipe = Recipe(
        title=title.strip(),
        tags=[t.strip() for t in (tags or "").split(",") if t.strip()] or None,
        ingredients=[Ingredient(**ing) for ing in ing_list],
        steps=[str(s) for s in step_list],
    )

    slug = create_recipe(recipe)
    if dish_image and dish_image.filename:
        data = await dish_image.read()
        path = save_image(slug, dish_image.filename, data)
        recipe.dish_image_path = path
    write_recipe(slug, recipe)
    return {"slug": slug}


@router.put("/recipes/{slug}")
async def api_update_recipe(
    slug: str,
    title: str = Form(...),
    tags: Optional[str] = Form(None),
    ingredients: Optional[str] = Form(None),
    steps: Optional[str] = Form(None),
    dish_image: UploadFile | None = File(None),
):
    existing = read_recipe(slug)
    if not existing:
        raise HTTPException(status_code=404, detail="Not found")
    if ingredients is None or steps is None:
        raise HTTPException(status_code=400, detail="ingredients and steps are required")
    try:
        ing_list = json.loads(ingredients)
        step_list = json.loads(steps)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON for ingredients/steps")

    updated = Recipe(
        title=title.strip(),
        tags=[t.strip() for t in (tags or "").split(",") if t.strip()] or None,
        ingredients=[Ingredient(**ing) for ing in ing_list],
        steps=[str(s) for s in step_list],
        dish_image_path=existing.dish_image_path,
    )

    new_slug = slug_for_title(updated.title)
    if new_slug != slug:
        move_tree(UPLOADS_DIR / slug, UPLOADS_DIR / new_slug)
        # Update stored image path lists
        if updated.dish_image_path:
            updated.dish_image_path = updated.dish_image_path.replace(
                f"assets/uploads/{slug}/", f"assets/uploads/{new_slug}/"
            )
        # no ingredient images managed anymore
    if dish_image and dish_image.filename:
        data = await dish_image.read()
        path = save_image(new_slug, dish_image.filename, data)
        updated.dish_image_path = path
    final_slug = write_recipe(slug, updated)
    return {"slug": final_slug}


@router.delete("/recipes/{slug}")
def api_delete_recipe(slug: str):
    ok = delete_recipe(slug)
    from yenu.utils import rmtree_silent
    from yenu.settings import UPLOADS_DIR

    rmtree_silent(UPLOADS_DIR / slug)
    if not ok:
        raise HTTPException(status_code=404, detail="Not found")
    return {"status": "deleted"}


@router.get("/export")
def api_export():
    data = export_all_json()
    return JSONResponse(content=json.loads(data))


@router.post("/import")
async def api_import(payload: str = Form(...)):
    try:
        res = import_from_json(payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return res


@router.get("/backup.zip")
def api_backup_zip():
    data = backup_recipes_zip()
    return StreamingResponse(
        iter([data]),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=recipes_backup.zip"},
    )
