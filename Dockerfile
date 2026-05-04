# Use a lightweight Debian image as the base
FROM debian:bookworm-slim

# Install system dependencies needed for uv and python
RUN apt-get update && apt-get install -y curl ca-certificates && rm -rf /var/lib/apt/lists/*

# Create a non-root user for the application (CWE-250 mitigation)
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid 1000 --create-home appuser

# Install uv using the official installer script (as root, before switching user)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Add uv to PATH (installed to /root/.local/bin by the installer)
ENV PATH="/root/.local/bin:$PATH"

# Set the working directory
WORKDIR /app

# Install Python 3.14 explicitly using uv
RUN uv python install 3.14

# Copy project configuration files first to leverage Docker cache
COPY pyproject.toml uv.lock ./

# Install project dependencies (excluding dev dependencies)
# We use --frozen to ensure deterministic builds from uv.lock
RUN uv sync --frozen --no-dev

# Copy the rest of the application code
COPY . .

# Transfer ownership and switch to non-root user
RUN chown -R appuser:appuser /app
USER appuser

# Expose the default port (Render will override this dynamically with $PORT)
EXPOSE 8082

# Start the application using uv run to ensure the right environment is used
CMD ["uv", "run", "python", "server.py"]
