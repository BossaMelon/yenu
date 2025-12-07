from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from yenu.models import Ingredient, Recipe, Step
from yenu.services.images import save_image
from yenu.services.recipes_yaml import (
    create_recipe,
    delete_recipe,
    read_recipe,
    search_recipes,
    write_recipe,
    slug_for_title,
)
from yenu.settings import UPLOADS_DIR
from yenu.utils import move_tree
from pydantic import ValidationError as PydValidationError


router = APIRouter()

templates = Jinja2Templates(directory=str(Path(__file__).parents[1] / "templates"))


@router.get("/", response_class=HTMLResponse)
def index(request: Request, q: Optional[str] = None, tag: Optional[str] = None, page: int = 1):
    result = search_recipes(q=q, tag=tag, page=page, page_size=50)
    return templates.TemplateResponse(
        "recipes/index.html",
        {"request": request, "recipes": result["items"], "q": q or "", "tag": tag or ""},
    )


@router.get("/recipes/new", response_class=HTMLResponse)
def new_recipe_page(request: Request):
    return templates.TemplateResponse("recipes/form.html", {"request": request, "mode": "create"})


def _parse_ingredients(raw_names: list[str], raw_weights: list[str], raw_units: list[str]):
    items: list[Ingredient] = []
    for n, w, u in zip(raw_names, raw_weights, raw_units):
        n = n.strip()
        if not n:
            continue
        w_str = str(w).strip()
        if w_str == "":
            # If weight empty, drop unit and set weight to None (适量)
            weight = None
            unit = ""
        else:
            # Keep numeric as number, otherwise preserve free-text weight
            try:
                weight = float(w_str)
            except Exception:
                weight = w_str
            unit = (u or "").strip()
        items.append(Ingredient(name=n, weight=weight, unit=unit))
    return items


@router.post("/recipes/new")
async def create_recipe_action(
    request: Request,
    title: str = Form(...),
    tags: str = Form(""),
    step_list: str = Form(""),
    step_text: list[str] = Form([]),
    ing_name: list[str] = Form([]),
    ing_weight: list[str] = Form([]),
    ing_unit: list[str] = Form([]),
    dish_image: UploadFile | None = None,
):
    ingredients = _parse_ingredients(ing_name, ing_weight, ing_unit)
    # Build steps from either step_text list or legacy step_list textarea
    steps_text = [s.strip() for s in step_text if str(s).strip()]
    if not steps_text and step_list:
        steps_text = [s.strip() for s in step_list.splitlines() if s.strip()]
    if not steps_text:
        steps_text = ["步骤"]
    tags_list = [t.strip() for t in tags.split(",") if t.strip()] or None

    def _friendly_from_value_error(msg: str) -> str:
        if "Unsupported image type" in msg:
            return "不支持的图片格式（仅支持 JPEG/PNG）"
        if "Image too large" in msg:
            return "图片过大，请压缩后再上传"
        return msg or "输入有误，请检查后重试"

    rec_ctx = {
        "title": title.strip(),
        "tags": tags_list or [],
        "ingredients": [i.dict() for i in ingredients],
        "steps": steps_text,
        "dish_image_path": None,
    }

    try:
        recipe = Recipe(
            title=rec_ctx["title"],
            tags=tags_list,
            ingredients=ingredients,
            steps=[Step(text=t) for t in steps_text],
        )
    except PydValidationError:
        # Fallback: write minimal YAML directly to ensure UX continuity
        from yenu.services.recipes_yaml import slug_for_title
        from yenu.settings import RECIPES_DIR
        from yenu.utils import atomic_write
        import yaml
        slug_fb = slug_for_title(rec_ctx["title"]) or "recipe"
        path = RECIPES_DIR / f"{slug_fb}.yaml"
        data = {
            "title": rec_ctx["title"],
            "tags": rec_ctx["tags"] or None,
            "ingredients": rec_ctx["ingredients"],
            "steps": rec_ctx["steps"],
        }
        atomic_write(path, yaml.safe_dump(data, allow_unicode=True, sort_keys=False).encode("utf-8"))
        return RedirectResponse(url=f"/recipes/{slug_fb}", status_code=303)

    slug = create_recipe(recipe)

    # Save images if provided (multiple)
    try:
        if dish_image and dish_image.filename:
            data = await dish_image.read()
            path = save_image(slug, dish_image.filename, data)
            recipe.dish_image_path = path
        # Handle per-step images from form data
        formdata = await request.form()
        files = formdata.getlist("step_image") if hasattr(formdata, "getlist") else []
        for idx, f in enumerate(files):
            if f and getattr(f, "filename", None) and idx < len(recipe.steps):
                data = await f.read()
                path = save_image(slug, f.filename, data)
                recipe.steps[idx].image_path = path
    except ValueError as e:
        # Show friendly image error
        errors = [_friendly_from_value_error(str(e))]
        return templates.TemplateResponse(
            "recipes/form.html",
            {"request": request, "mode": "create", "errors": errors, "recipe": rec_ctx},
            status_code=400,
        )

    # Persist again if images were added
    write_recipe(slug, recipe)

    return RedirectResponse(url=f"/recipes/{slug}", status_code=303)


@router.get("/recipes/{slug}", response_class=HTMLResponse)
def recipe_detail(request: Request, slug: str):
    recipe = read_recipe(slug)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return templates.TemplateResponse(
        "recipes/detail.html", {"request": request, "slug": slug, "recipe": recipe}
    )


@router.get("/recipes/{slug}/edit", response_class=HTMLResponse)
def recipe_edit_page(request: Request, slug: str):
    recipe = read_recipe(slug)
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return templates.TemplateResponse(
        "recipes/form.html",
        {"request": request, "mode": "edit", "slug": slug, "recipe": recipe},
    )


@router.post("/recipes/{slug}/edit")
async def recipe_edit_action(
    request: Request,
    slug: str,
    title: str = Form(...),
    tags: str = Form(""),
    step_list: str = Form(""),
    step_text: list[str] = Form([]),
    ing_name: list[str] = Form([]),
    ing_weight: list[str] = Form([]),
    ing_unit: list[str] = Form([]),
    delete_dish: str | None = Form(None),
    delete_step_image: list[str] = Form([]),
    dish_image: UploadFile | None = None,
):
    existing = read_recipe(slug)
    if not existing:
        raise HTTPException(status_code=404, detail="Recipe not found")

    ingredients = _parse_ingredients(ing_name, ing_weight, ing_unit)
    steps_text = [s.strip() for s in step_text if str(s).strip()]
    if not steps_text and step_list:
        steps_text = [s.strip() for s in step_list.splitlines() if s.strip()]
    if not steps_text:
        # keep existing if available, otherwise default one
        steps_text = [s.text for s in (existing.steps or [])] or ["步骤"]
    tags_list = [t.strip() for t in tags.split(",") if t.strip()] or None

    rec_ctx = {
        "title": title.strip(),
        "tags": tags_list or [],
        "ingredients": [i.dict() for i in ingredients],
        "steps": steps_text,
        "dish_image_path": existing.dish_image_path,
    }

    try:
        # Preserve existing step images by index unless user requested deletion
        delset = set(delete_step_image or [])
        preserved_steps: list[Step] = []
        for idx, t in enumerate(steps_text):
            img = None
            if idx < len(existing.steps):
                prev = existing.steps[idx]
                if prev.image_path and prev.image_path not in delset:
                    img = prev.image_path
            preserved_steps.append(Step(text=t, image_path=img))

        updated = Recipe(
            title=rec_ctx["title"],
            tags=tags_list,
            ingredients=ingredients,
            steps=preserved_steps,
            dish_image_path=existing.dish_image_path,
        )
    except PydValidationError as exc:
        errors: list[str] = []
        fields = [e.get("loc", []) for e in exc.errors()]
        flat = [str(x) for loc in fields for x in loc]
        if "title" in flat:
            errors.append("标题不能为空")
        if "ingredients" in flat:
            errors.append("至少需要一个配料")
        if "steps" in flat:
            errors.append("至少需要一个步骤")
        if not errors:
            errors.append("填写内容有误，请检查后再试")
        return templates.TemplateResponse(
            "recipes/form.html",
            {"request": request, "mode": "edit", "slug": slug, "errors": errors, "recipe": rec_ctx},
            status_code=400,
        )

    new_slug = slug_for_title(updated.title)

    # If title (slug) changed, move upload folder first
    if new_slug != slug:
        move_tree(UPLOADS_DIR / slug, UPLOADS_DIR / new_slug)
        # Update stored image paths to point to new slug
        if updated.dish_image_path:
            updated.dish_image_path = updated.dish_image_path.replace(
                f"assets/uploads/{slug}/", f"assets/uploads/{new_slug}/"
            )

    # Handle delete image checkboxes before saving new ones
    def _unlink_if_exists(path_str: str | None, current_slug: str) -> None:
        if not path_str:
            return
        from pathlib import Path as _P
        target = UPLOADS_DIR / current_slug / _P(path_str).name
        if target.exists():
            try:
                target.unlink()
            except Exception:
                pass

    # Delete selected images
    if delete_dish is not None and updated.dish_image_path:
        _unlink_if_exists(updated.dish_image_path, new_slug)
        updated.dish_image_path = None
    # Delete requested step images from disk
    if delete_step_image:
        delset = set(delete_step_image)
        for path_str in delset:
            _unlink_if_exists(path_str, new_slug)
        # updated.steps already had those paths cleared during preservation

    try:
        if dish_image and dish_image.filename:
            # Replace existing cover with new one
            if updated.dish_image_path:
                _unlink_if_exists(updated.dish_image_path, new_slug)
            data = await dish_image.read()
            path = save_image(new_slug, dish_image.filename, data)
            updated.dish_image_path = path
        formdata = await request.form()
        files = formdata.getlist("step_image") if hasattr(formdata, "getlist") else []
        for idx, f in enumerate(files):
            if f and getattr(f, "filename", None) and idx < len(updated.steps):
                data = await f.read()
                path = save_image(new_slug, f.filename, data)
                updated.steps[idx].image_path = path
    except ValueError as e:
        errors = [
            "不支持的图片格式（仅支持 JPEG/PNG）" if "Unsupported image type" in str(e) else (
                "图片过大，请压缩后再上传" if "Image too large" in str(e) else str(e)
            )
        ]
        return templates.TemplateResponse(
            "recipes/form.html",
            {"request": request, "mode": "edit", "slug": slug, "errors": errors, "recipe": rec_ctx},
            status_code=400,
        )

    final_slug = write_recipe(slug, updated)
    return RedirectResponse(url=f"/recipes/{final_slug}", status_code=303)


@router.post("/recipes/{slug}/delete")
def recipe_delete_action(slug: str):
    ok = delete_recipe(slug)
    # Delete uploads folder if exists
    from yenu.utils import rmtree_silent

    rmtree_silent(UPLOADS_DIR / slug)
    return RedirectResponse(url="/", status_code=303)


@router.post("/recipes/bulk-delete")
def recipes_bulk_delete(slugs: str = Form("")):
    from yenu.utils import rmtree_silent

    # slugs is a comma-separated list from the index page
    items = [s.strip() for s in slugs.split(",") if s.strip()]
    for s in items:
        delete_recipe(s)
        rmtree_silent(UPLOADS_DIR / s)
    return RedirectResponse(url="/", status_code=303)
