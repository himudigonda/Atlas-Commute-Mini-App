# STAGE 1: Builder
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Copy dependency definitions
COPY pyproject.toml uv.lock ./

# Sync dependencies to a specific virtual environment path
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# STAGE 2: Runtime
FROM python:3.12-slim-bookworm
WORKDIR /app

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    MOCK_MODE=false

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends curl tzdata && \
    rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN groupadd -r atlas && useradd -r -g atlas atlas

# Copy the virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code (excluding .venv via .dockerignore)
COPY . .

# Change ownership to non-root user
RUN chown -R atlas:atlas /app

# Switch context
USER atlas

# Expose API port
EXPOSE 8000

# Healthcheck using curl for simplicity and reliability
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Launch with Uvicorn via python -m to avoid shebang path issues
CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--proxy-headers"]
