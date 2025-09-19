# Multi-stage build for optimized image size
FROM python:3.11-slim as builder

WORKDIR /app

# Install system dependencies (inchangé)
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copie les fichiers nécessaires (inchangé)
COPY pyproject.toml README.md ./
COPY src ./src

# Installe le package et ses dépendances de manière GLOBALE (on retire --user)
RUN pip install --no-cache-dir .

# Production stage
FROM python:3.11-slim

# Set environment variables (PATH n'est plus nécessaire ici)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Copie les dépendances depuis le site-packages GLOBAL du builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# Copie le code de l'application et les fichiers web
COPY src/ ./src/
COPY static/ ./static/
COPY migrations/ ./migrations/
# --- AJOUT ---
# Copie le fichier client.html à la racine du répertoire de travail /app
COPY client.html .
# --- FIN DE L'AJOUT ---

# Create non-root user (inchangé)
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port (inchangé)
EXPOSE 5000

# Health check (inchangé)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/health')" || exit 1

# Run the application (inchangé)
# CMD ["python", "src/pubsub_ws.py"]
CMD ["python", "-m", "pubsub_ws"]