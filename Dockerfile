# STAGE 1: Builder
# Use astral-sh/uv for lightning-fast dependency resolution
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1
# Copy dependency definitions
COPY pyproject.toml uv.lock ./

# Sync dependencies to a specific virtual environment path
# --frozen ensures we don't accidentally upgrade packages without updating lockfile
RUN uv sync --frozen --no-install-project --no-dev

# STAGE 2: Runtime
# Use a minimal slim image for production
FROM python:3.11-slim-bookworm

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    MOCK_MODE=false

WORKDIR /app

# Create a non-root user (Rule 14)
RUN groupadd -r atlas && useradd -r -g atlas atlas

# Copy the virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY . .

# Change ownership to non-root user
RUN chown -R atlas:atlas /app

# Switch context
USER atlas

# Expose API port
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Launch with Uvicorn (production settings)
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
