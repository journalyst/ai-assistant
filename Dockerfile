# Stage 1: Builder - Install dependencies
FROM python:3.10-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Install build dependencies and project dependencies
COPY pyproject.toml uv.lock ./

# Use PyTorch CPU-only index to avoid CUDA (~2-3GB savings)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-install-project --no-dev \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    --index-strategy unsafe-best-match

# Copy necessary application files (each to its own directory)
COPY src/ ./src/
COPY test_client/ ./test_client/
COPY sample_data/ ./sample_data/
COPY docker_scripts/ ./scripts/

# Stage 2: Final - Minimal runtime image
# Use slim (not alpine) to maintain glibc compatibility with compiled packages
FROM python:3.10-slim AS runtime

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Set cache directories for HuggingFace/transformers models
    HF_HOME=/app/.cache/huggingface \
    TRANSFORMERS_CACHE=/app/.cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/app/.cache/sentence-transformers

# Create non-root user (Debian syntax)
RUN groupadd -g 1001 appgroup && \
    useradd -u 1001 -g appgroup -d /app -s /sbin/nologin appuser

WORKDIR /app

# Create cache directories with proper ownership
RUN mkdir -p /app/.cache/huggingface /app/.cache/sentence-transformers && \
    chown -R appuser:appgroup /app/.cache

# Copy from builder (each directory separately to preserve structure)
COPY --from=builder --chown=appuser:appgroup /app/.venv ./.venv
COPY --from=builder --chown=appuser:appgroup /app/src ./src
COPY --from=builder --chown=appuser:appgroup /app/test_client ./test_client
COPY --from=builder --chown=appuser:appgroup /app/sample_data ./sample_data
COPY --from=builder --chown=appuser:appgroup /app/scripts ./scripts

# Make scripts executable
RUN chmod +x ./scripts/*.sh

USER appuser

ENTRYPOINT ["python", "-m", "uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]