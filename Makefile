.PHONY: setup run test lint docker

setup:
	uv sync
run:
	uv run uvicorn api.main:app --reload --port 8000
lint:
	uv run ruff check . --fix
	uv run mypy .
test:
	uv run pytest
docker:
	docker build -t atlas-slice .
