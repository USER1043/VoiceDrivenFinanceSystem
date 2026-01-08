# -----------------------------
# Base image
# -----------------------------
FROM python:3.11-slim

# -----------------------------
# Python environment
# -----------------------------
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# -----------------------------
# Working directory
# -----------------------------
WORKDIR /app

# -----------------------------
# System dependencies
# -----------------------------
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# -----------------------------
# Install uv (project manager)
# -----------------------------
RUN pip install --no-cache-dir uv

# -----------------------------
# Copy dependency files first
# -----------------------------
COPY pyproject.toml uv.lock ./

# -----------------------------
# Install Python dependencies
# -----------------------------
RUN uv sync --frozen

# -----------------------------
# Copy application source
# -----------------------------
COPY app ./app
COPY alembic.ini .

# -----------------------------
# Expose FastAPI port
# -----------------------------
EXPOSE 8000

# -----------------------------
# Start FastAPI using python -m
# -----------------------------
CMD ["uv", "run", "python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
