from __future__ import annotations

from yenu.models import Ingredient, Recipe
from yenu.services.recipes_yaml import create_recipe


def main():
    sample = Recipe(
        title="Tomato Egg Stir-fry",
        tags=["home", "quick"],
        ingredients=[
            Ingredient(name="Egg", weight=3, unit="pcs"),
            Ingredient(name="Tomato", weight=2, unit="pcs"),
            Ingredient(name="Salt", weight=2, unit="g"),
        ],
        steps=[
            "Beat eggs and fry until set.",
            "Stir-fry tomatoes until soft.",
            "Combine, season, and serve.",
        ],
    )
    slug = create_recipe(sample)
    print(f"Seeded recipe: {slug}")


if __name__ == "__main__":
    main()

