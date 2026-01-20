.PHONY: all setup dev test lint format clean docker-build docker-run docker-up docker-down dashboard

# Variables
IMAGE_NAME = atlas-orchestrator
CONTAINER_NAME = atlas-app
NETWORK_NAME = atlas-network
REDIS_CONTAINER = atlas-redis

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

docker-up: docker-build ## Launch the full stack (Redis + Atlas) using a dedicated network
	docker network create $(NETWORK_NAME) || true
	docker stop $(REDIS_CONTAINER) || true && docker rm $(REDIS_CONTAINER) || true
	docker stop $(CONTAINER_NAME) || true && docker rm $(CONTAINER_NAME) || true
	docker run -d --name $(REDIS_CONTAINER) --network $(NETWORK_NAME) -p 6379:6379 redis:alpine
	# We use --env-file to pull variables from .env if it exists.
	# We only pass -e GOOGLE_API_KEY if it's explicitly set in the shell/command, 
	# otherwise let .env handle it to avoid masking with an empty value.
	docker run --rm -p 8000:8000 \
		--name $(CONTAINER_NAME) \
		--network $(NETWORK_NAME) \
		$$( [ -f .env ] && echo "--env-file .env" ) \
		$$( [ -n "$(GOOGLE_API_KEY)" ] && echo "-e GOOGLE_API_KEY=$(GOOGLE_API_KEY)" ) \
		-e REDIS_URL=redis://$(REDIS_CONTAINER):6379/0 \
		$(IMAGE_NAME)

docker-down: ## Tear down the docker stack
	docker stop $(CONTAINER_NAME) || true
	docker stop $(REDIS_CONTAINER) || true
	docker network rm $(NETWORK_NAME) || true

docker-run: ## Alias for backwards compatibility (Host-based Redis)
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
