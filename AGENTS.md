# Project Goal / Overview
Build a **local recipe manager** using Python and FastAPI, designed to run entirely on a home network **without any SQL database**.  
All recipe data will be stored as **YAML files** on local disk, and optional images (dish / ingredients) will be stored under `assets/uploads/`.  
The app provides a responsive web UI (desktop + mobile) accessible via LAN IP and allows users to create, view, and edit recipes.

Recipes include:
- `title`
- `tags` (optional list)
- `ingredients`: list of `{name, weight, unit}`
- `steps`: ordered list of instructions
- `dish_image_path`, `ingredient_image_path` (optional)

The system runs locally on macOS (Apple Silicon) during development, and will later be deployed on a **Synology NAS via Docker Compose**.

---

# Requirements / Features

### Core Features
- **Recipe CRUD**
  - Create, read, update, delete YAML files under `data/recipes/`
  - Auto-generate filename from title (slug-safe)
  - Fields: `title`, `tags`, `ingredients`, `steps`, `dish_image_path`, `ingredient_image_path`

- **Listing & Search**
  - List all YAML recipes
  - Search by title or tag
  - Optional: fuzzy search by ingredient name

- **Media Handling**
  - Upload dish/ingredient photos via the UI
  - Store images under `assets/uploads/<slug>/`
  - Save only the relative image path in YAML
  - Auto-generate safe filenames; validate image type/size
  - Optional: generate 800px thumbnails to optimize mobile bandwidth

- **Import / Export**
  - Export all YAMLs as a single JSON
  - Import from JSON (deduplicate by title)
  - Backup/export entire `data/recipes` directory as `.zip`

- **Validation & Error Handling**
  - Validate recipe structure using Pydantic schema (title non-empty, ingredients ≥1, steps ≥1)
  - Return structured JSON errors for invalid inputs

- **Responsive Web UI**
  - Server-side rendered pages using **Jinja2**
  - Responsive CSS (Tailwind or minimalist custom)
  - Consistent layout across desktop & mobile

- **Healthcheck**
  - `/healthz` → `{status:"ok"}`

---

# Tech Stack / Constraints
- **Language**: Python 3.11+
- **Framework**: FastAPI + Jinja2
- **Storage**: YAML files in `data/recipes/`
- **Image Handling**: Pillow (optional thumbnail generation)
- **Static / Media**
  - Static assets under `src/yenu/static/`
  - User uploads under `assets/uploads/`
- **Environment (Conda)**
  - Environment name: `yenu`
  - Defined in `environment.yml` (authoritative); avoid venv/pip-only workflows. Ensure packages are compatible with Python 3.11 on arm64 (Apple Silicon & Synology NAS).
- **Platform**
  - Development on macOS M4 (Apple Silicon)
  - Deployment on Synology NAS (via Docker Compose, arm64/x86_64)
- **Code Quality**
  - Format: `black`
  - Lint: `ruff`
  - Type hints required
  - Tests: `pytest`

---

# Directory Structure
```
src/
  yenu/
    __init__.py
    main.py                # FastAPI entry point, router + static setup
    models.py              # Pydantic schemas for Recipe, Ingredient
    services/
      recipes_yaml.py      # Read/write recipes from YAML
    routers/
      pages.py             # Web routes for viewing and editing
      api.py               # JSON API endpoints
    templates/
      base.html
      recipes/
        index.html
        detail.html
        form.html
    static/
      css/
assets/
  uploads/                 # user-uploaded images
data/
  recipes/                 # YAML recipe files
scripts/
  seed.py                  # populate sample recipes
tests/
  test_recipes_api.py
  test_pages.py
environment.yml
Makefile
README.md
Dockerfile
docker-compose.yml
```

---

# API & Routes (High level)
- **HTML pages**
  - `GET /` → Recipe list (search + pagination)
  - `GET /recipes/{slug}` → Detail page (slug from title)
  - `GET /recipes/new` → Create form
  - `GET /recipes/{slug}/edit` → Edit form
- **JSON API** (prefix `/api`)
  - `GET /api/recipes` (query: `q`, `tag`, `ingredient`, `page`, `page_size`)
  - `POST /api/recipes` (multipart for optional images)
  - `GET /api/recipes/{slug}`
  - `PUT /api/recipes/{slug}` (multipart supported)
  - `DELETE /api/recipes/{slug}`
  - `GET /api/export` → JSON dump of all YAMLs
  - `POST /api/import` → JSON import (dedupe by title)
- **Health**
  - `GET /healthz` → `{status:"ok"}`

---

# Implementation Guidelines

## Data Storage
- Store each recipe as a separate YAML file:
  ```
  data/recipes/hongshaorou.yaml
  ```
- File format:
  ```yaml
  title: 红烧肉
  tags: [家常菜, 肉类]
  ingredients:
    - name: 五花肉
      weight: 500
      unit: g
    - name: 冰糖
      weight: 20
      unit: g
  steps:
    - 焯水去腥
    - 炒糖色
    - 炖至入味
  dish_image_path: assets/uploads/hongshaorou.jpg
  ingredient_image_path: assets/uploads/hongshaorou_ingredients.jpg
  ```
- Filenames must be **slugified** from title (e.g., `"红烧肉"` → `hongshaorou.yaml`).  
- Reads/writes are performed on demand with **atomic writes** (temp file + rename) to avoid corruption.

## File Operations
- Use `PyYAML` for reading/writing YAML.
- On title change, rename the YAML file and image subfolder (`assets/uploads/<old_slug>` → `<new_slug>`).
- On delete, remove YAML and its corresponding image folder.

## Media Upload
- Accept **JPEG/PNG**; validate MIME and size (config via env var).
- Save under `assets/uploads/<slug>/`.
- Generate **800px max-dimension** thumbnails with Pillow (optional).
- Serve uploads via:
  ```python
  app.mount("/uploads", StaticFiles(directory="assets/uploads"), name="uploads")
  ```

## Validation
- Pydantic schema enforces:
  - `title` non-empty
  - at least **1 ingredient**
  - at least **1 step**
- Return 400 with JSON payload describing invalid fields.

## Search / Listing
- Scan `data/recipes/*.yaml`, parse front-matter, and filter in Python.
- Support case-insensitive matches on `title`/`tags`; optional fuzzy search on ingredient names.
- Paginate in Python.

## Security
- Sanitize filenames; deny path traversal.
- Never interpret YAML as arbitrary objects (`safe_load` only).

## Responsiveness
- Mobile-first layout; forms/tables/buttons adapt to small screens.

---

# Commands / Build Instructions
- `make setup` → Create or update Conda env `yenu` from `environment.yml`
- `make run` → Start dev server via Conda:
  ```
  conda run -n yenu uvicorn src.yenu.main:app --host 0.0.0.0 --port 8000 --reload
  ```
- `make test` → `conda run -n yenu pytest -q`
- `make lint` → `conda run -n yenu black src tests && conda run -n yenu ruff check src tests`
- `make seed` → `conda run -n yenu python scripts/seed.py`
- `make docker-build` → Build Docker image for local/NAS deployment
- `make docker-up` → Run app with Docker Compose

---

# Deliverables / Output Expectations
- A working FastAPI app with:
  - Responsive HTML UI (list/detail/create/edit)
  - Complete JSON API for CRUD, search, import/export
  - **YAML-based persistence** (no SQL/ORM)
  - Local image upload and storage
  - Tests covering CRUD and search flows
- Dockerfile and docker-compose.yml ready for Synology NAS (arm64/x86_64)
- README with instructions for macOS local run and NAS deployment

---

# Repository Guidelines (Optional)
This section provides general repository hygiene rules and is not required for AI generation.

- Use `src/` for all code modules and `tests/` as a sibling mirror tree.  
- Run `make lint` and `make test` before every commit.  
- Keep commits short and descriptive (e.g., “add recipe form validation”).  
- Follow PEP8; enforce formatting via `black` and `ruff`.  
- Add regression tests for every bug fix.  
- Use Docker Compose for production deployment; avoid system Python dependencies.