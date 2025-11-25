from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Any

from pydantic import BaseModel, Field, validator


class Ingredient(BaseModel):
    name: str = Field(..., min_length=1)
    weight: Optional[float] = Field(default=None)  # None means 适量，不写入 YAML
    unit: Optional[str] = Field(default="", min_length=0)

    # If weight is empty/zero, force unit to empty string per rule
    @validator("unit", always=True)
    def _unit_when_no_weight(cls, v: Optional[str], values):  # type: ignore[override]
        w = values.get("weight", None)
        if w in (None, 0, 0.0):
            return ""
        return (v or "").strip()


class Step(BaseModel):
    text: str = Field(..., min_length=1)
    image_path: Optional[str] = None


class Recipe(BaseModel):
    title: str = Field(..., min_length=1)
    tags: List[str] | None = Field(default=None)
    ingredients: List[Ingredient] = Field(..., min_items=1)
    steps: List[Step] = Field(..., min_items=1)
    # Single cover image for dish
    dish_image_path: Optional[str] = None

    @validator("tags", pre=True)
    def _normalize_tags(cls, v: Optional[List[str]]):  # type: ignore[override]
        if v is None:
            return None
        tags = [str(t).strip() for t in v if str(t).strip()]
        return tags or None

    @validator("steps", pre=True)
    def _normalize_steps(cls, v: Any):  # type: ignore[override]
        # Accept list of strings, dicts, or Step objects
        items = v or []
        out: List[dict] = []
        for s in items:
            if isinstance(s, str):
                t = s.strip()
                if t:
                    out.append({"text": t})
            elif isinstance(s, dict):
                t = str(s.get("text", "")).strip()
                if t:
                    p = s.get("image_path")
                    out.append({"text": t, "image_path": p})
            else:
                # Attempt to read attributes (Step instance or similar)
                t = str(getattr(s, "text", "")).strip()
                if t:
                    p = getattr(s, "image_path", None)
                    out.append({"text": t, "image_path": p})
        return out

    @validator("dish_image_path", pre=True)
    def _normalize_cover(cls, v):  # type: ignore[override]
        # accept legacy list field from older YAML and take first element
        if isinstance(v, list):
            return v[0] if v else None
        return v

    def dict_for_yaml(self) -> dict:
        data = self.dict()
        # Ensure image paths are stored as forward-slash relative paths
        if data.get("dish_image_path"):
            data["dish_image_path"] = str(Path(data["dish_image_path"]).as_posix())
        # Steps as list of dicts with normalized path
        steps_out = []
        for s in data.get("steps", []) or []:
            item = {"text": s.get("text")}
            p = s.get("image_path")
            if p:
                item["image_path"] = str(Path(p).as_posix())
            steps_out.append(item)
        data["steps"] = steps_out
        # Clean ingredients: drop weight if None, drop unit if empty
        cleaned_ings = []
        for ing in data.get("ingredients", []) or []:
            item = dict(ing)
            if item.get("weight", None) is None:
                item.pop("weight", None)
            else:
                # normalize 0.0 to 0 if it occurs (though we set None when empty)
                try:
                    wv = float(item["weight"])
                    if wv.is_integer():
                        item["weight"] = int(wv)
                except Exception:
                    pass
            if not item.get("unit"):
                item.pop("unit", None)
            cleaned_ings.append(item)
        data["ingredients"] = cleaned_ings
        return data
