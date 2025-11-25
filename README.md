# Yenu — Local Recipe Manager

FastAPI app to manage recipes stored as YAML files with optional images, designed to run locally or on a Synology NAS via Docker Compose.

## Features
- YAML-based recipes under `data/recipes/`
- CRUD via web UI and JSON API
- Search by title/tag and ingredient
- Image uploads to `assets/uploads/<slug>/` with validation and resize to 800px
- Import/Export JSON and Zip backup
- Responsive Jinja2 templates
- Healthcheck at `/healthz`

## Dev Setup (macOS)
1. Install Conda
2. `make setup`
3. `make run` then open `http://localhost:8000`
  4. Optional `make seed`

Commands:
- `make test` — run pytest
- `make lint` — format and lint

Environment variables:
- `YENU_RECIPES_DIR` (default `data/recipes`)
- `YENU_UPLOADS_DIR` (default `assets/uploads`)
- `YENU_MAX_IMAGE_MB` (default `8`)
- `YENU_THUMB_MAX_PX` (default `800`)

## JSON API
- `GET /api/recipes` — list with `q`, `tag`, `ingredient`, `page`, `page_size`
- `POST /api/recipes` — multipart/form with `title`, `tags`, `ingredients` (JSON), `steps` (JSON), and optional images
- `GET /api/recipes/{slug}` — get one
- `PUT /api/recipes/{slug}` — update (multipart)
- `DELETE /api/recipes/{slug}` — delete
- `GET /api/export` — JSON array export
- `POST /api/import` — form field `payload` with export JSON
- `GET /api/backup.zip` — zip of recipes directory

## Docker
Build: `make docker-build`

Run: `make docker-up` then open `http://NAS_IP:8000`

Compose mounts:
- `./data` to `/data/recipes`
- `./assets/uploads` to `/data/uploads`
