# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    YENU_BASE_DIR=/app \
    PYTHONPATH=/app/src

WORKDIR /app

# System deps for Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg62-turbo libpng16-16 \
    && rm -rf /var/lib/apt/lists/*

COPY environment.yml /app/

# Use pip instead of conda inside container for smaller image
RUN pip install --upgrade pip && \
    pip install fastapi uvicorn pydantic pyyaml jinja2 python-multipart pillow python-slugify pypinyin requests

COPY src /app/src


EXPOSE 8000

CMD ["python","-m","uvicorn","yenu.main:app","--host","0.0.0.0","--port","8000"]
