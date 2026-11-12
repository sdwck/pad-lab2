# Production-optimized, non-root, minimal Python image for PAD Microservices
FROM python:3.12-slim

# Prevent Python from writing .pyc files and force unbuffered stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Create non-root system user and group (Least Privilege Security Principle)
RUN addgroup --system --gid 10001 appgroup && \
    adduser --system --uid 10001 --ingroup appgroup --no-create-home appuser

WORKDIR /app

# Dependency layer caching: install requirements first so Docker reuses cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy microservices application code
COPY services/ /app/services/

# Ensure runtime data directory exists and is owned by appuser
RUN mkdir -p /data && chown -R appuser:appgroup /data /app

# Switch to unprivileged user
USER appuser

# Default fallback command (overridden per-service in docker-compose / k8s)
CMD ["python", "-m", "uvicorn", "services.auth.main:app", "--host", "0.0.0.0", "--port", "8001"]
