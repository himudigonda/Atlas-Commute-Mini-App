.PHONY: all setup dev test lint format clean docker-build docker-run dashboard

# Variables
IMAGE_NAME = atlas-orchestrator
CONTAINER_NAME = atlas-app

all: lint test

# --- Development ---
setup: ## Install dependencies with uv
	uv sync

dev: ## Run local development server
	uv run uvicorn api.main:app --reload --port 8000

dashboard: ## Launch the terminal observability dashboard
	uv run python scripts/dashboard.py

# --- Quality ---
lint: ## Run ruff and mypy
	uv run ruff check .
	uv run mypy .

format: ## Auto-format code
	uv run ruff check . --fix
	uv run ruff format .

test: ## Run unit and integration tests
	PYTHONPATH=. uv run pytest tests/ -v

# --- Docker / Production ---
docker-build: ## Build the production image
	docker build -t $(IMAGE_NAME) .

docker-run: ## Run the container locally (requires local Redis)
	docker run --rm -p 8000:8000 \
		--name $(CONTAINER_NAME) \
		-e GOOGLE_API_KEY=$(GOOGLE_API_KEY) \
		-e REDIS_URL=redis://host.docker.internal:6379 \
		$(IMAGE_NAME)

clean: ## Clean up artifacts
	rm -rf .venv
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
