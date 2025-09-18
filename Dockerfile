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

# --- CHANGEMENT 1 ---
# Installe le package et ses dépendances de manière GLOBALE (on retire --user)
RUN pip install --no-cache-dir .

# --- FIN DU CHANGEMENT 1 ---

# Production stage
FROM python:3.11-slim

# Set environment variables (PATH n'est plus nécessaire ici)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# --- CHANGEMENT 2 ---
# Copie les dépendances depuis le site-packages GLOBAL du builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
# --- FIN DU CHANGEMENT 2 ---

# Copie le code de l'application
COPY src/ ./src/
COPY static/ ./static/
COPY migrations/ ./migrations/

# --- CHANGEMENT 3 ---
# Il n'y a PLUS BESOIN de réinstaller le package ici, les dépendances sont déjà copiées.
# Cette étape est supprimée pour un build plus rapide et plus propre.
# --- FIN DU CHANGEMENT 3 ---

# Create non-root user (inchangé)
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port (inchangé)
EXPOSE 5000

# Health check (inchangé)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/health')" || exit 1

# Run the application (inchangé)
CMD ["python", "src/pubsub_ws.py"]
