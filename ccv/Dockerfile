FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POETRY_VERSION=1.7.1 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_CREATE=false \
    PATH="$POETRY_HOME/bin:$PATH"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python -

WORKDIR /app

# Copy dependency files
# We copy across the entire monorepo package structure because
# Poetry will look for path dependencies in packages/
COPY pyproject.toml poetry.lock ./
COPY packages/ ./packages/

# Install dependencies using Poetry
RUN poetry config installer.max-workers 10
RUN poetry install --no-interaction --no-ansi --no-root --only main

# Copy remaining project files
COPY . .

# Install the root project itself
RUN poetry install --no-interaction --no-ansi --only main

# Ensure local packages are in PYTHONPATH for direct execution
ENV PYTHONPATH="/app/packages/shared:/app/packages/api_service:/app/packages/scan_runner:/app/packages/analysis_agent:/app/packages/kb_service"

# Expose the port Cloud Run expects
EXPOSE 8080

# Start the FastAPI server via Uvicorn
CMD ["uvicorn", "api_service.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers"]
