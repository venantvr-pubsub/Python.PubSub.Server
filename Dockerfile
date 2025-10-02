# Multi-stage build for optimized image size
FROM python:3.11-slim as builder

# Le WORKDIR du builder peut rester /app
WORKDIR /app

# Install system dependencies (git nécessaire pour installer depuis GitHub)
RUN apt-get update && apt-get install -y gcc git && rm -rf /var/lib/apt/lists/*

# Copy files required for package installation
COPY pyproject.toml README.md ./
COPY src/python_pubsub_server ./src/python_pubsub_server
COPY migrations ./src/python_pubsub_server/migrations

# Install the package and its dependencies globally
RUN pip install --no-cache-dir .

# --- Production stage ---
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Répertoire de travail est /app
WORKDIR /app

# Copie les dépendances depuis le builder (incluant le package installé avec les migrations)
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# Création de l'utilisateur non-root
# On lui donne les droits sur /app entier
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/health')" || exit 1

# Lancer via le module Python
CMD ["python", "-m", "python_pubsub_server.pubsub_ws"]