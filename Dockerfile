# Use a lightweight Debian image as the base
FROM debian:bookworm-slim

# Install system dependencies needed for uv and python
RUN apt-get update && apt-get install -y curl ca-certificates && rm -rf /var/lib/apt/lists/*

# Create a non-root user for the application (CWE-250 mitigation)
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid 1000 --create-home appuser

# Switch to the non-root user early so all installations belong to appuser
USER appuser

# Install uv using the official installer script
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Add uv to PATH (installed to /home/appuser/.local/bin)
ENV PATH="/home/appuser/.local/bin:$PATH"

# Set the working directory
WORKDIR /app

# Install Python 3.14 explicitly using uv
RUN uv python install 3.14

# Copy project configuration files first to leverage Docker cache
COPY --chown=appuser:appuser pyproject.toml uv.lock README.md .env.example ./

# Install project dependencies (excluding dev dependencies)
# We use --frozen to ensure deterministic builds from uv.lock
RUN uv sync --frozen --no-dev

# Copy the rest of the application code
COPY --chown=appuser:appuser . .



# Expose the default port (Render will override this dynamically with $PORT)
EXPOSE 8082

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8082}/health || exit 1

# Start the application using uv run to ensure the right environment is used
CMD ["uv", "run", "python", "server.py"]
