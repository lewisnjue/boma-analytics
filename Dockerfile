FROM python:3.14-slim

# 1. Copy uv binary directly from official Astral image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /opt/app

# Optimize uv behavior for Docker environments
ENV UV_COMPILE_BYTECODE=1 \
  UV_LINK_MODE=copy

# 2. Copy dependency lockfiles first to utilize Docker layer caching
COPY pyproject.toml uv.lock /opt/app/

# 3. Install dependencies (skips source code build to cache dependencies)
RUN uv sync --frozen --no-install-project

# 4. Copy the rest of your application code
COPY . /opt/app/

# 5. Place virtualenv binaries in PATH
ENV PATH="/opt/app/.venv/bin:$PATH"

# Default command to run your app
CMD ["python", "main.py"]
