SHELL := /bin/bash
IMAGE ?= docker.io/bossamelon/yenu
VERSION ?= latest

.PHONY: setup run test lint seed docker-build docker-build-amd64 docker-up

setup:
	conda env update -n yenu -f environment.yml --prune || conda env create -n yenu -f environment.yml

run:
	PYTHONPATH=src conda run -n yenu uvicorn yenu.main:app --host 0.0.0.0 --port 8000 --reload

test:
	conda run -n yenu pytest -q

lint:
	conda run -n yenu black src tests
	conda run -n yenu ruff check src tests

seed:
	PYTHONPATH=src conda run -n yenu python scripts/seed.py

docker-build:
	docker build -t yenu:latest .

docker-build-amd64:
	# Ensure buildx builder is available for cross-arch builds
	docker buildx use yenu-builder || docker buildx create --name yenu-builder --use
	docker buildx build --platform linux/amd64 \
		-t $(IMAGE):$(VERSION) \
		-t $(IMAGE):latest \
		--push .

docker-up:
	docker compose up -d
