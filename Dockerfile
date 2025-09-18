# Multi-stage build for optimized image size
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# --- CHANGEMENTS CI-DESSOUS ---
# Copie les fichiers nécessaires à l'installation du package
COPY pyproject.toml README.md ./
COPY src ./src
# --- FIN DES CHANGEMENTS ---

# Installe le package et ses dépendances
RUN pip install --no-cache-dir --user .

# Production stage
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/root/.local/bin:$PATH

# Set working directory
WORKDIR /app

# Copy dependencies from builder
COPY --from=builder /root/.local /root/.local

# Copy application code (on le copie à nouveau pour la version finale)
COPY src/ ./src/
COPY static/ ./static/
COPY migrations/ ./migrations/
COPY pyproject.toml ./

# Installe le package en mode éditable
RUN pip install --no-cache-dir -e .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/health')" || exit 1

# Run the application
CMD ["python", "src/pubsub_ws.py"]
