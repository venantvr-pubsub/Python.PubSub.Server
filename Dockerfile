# Multi-stage build for optimized image size
FROM python:3.11-slim as builder

# Le WORKDIR du builder peut rester /app
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*

# Copy files required for package installation
COPY pyproject.toml README.md ./
COPY src ./src

# Install the package and its dependencies globally
RUN pip install --no-cache-dir .

# --- Production stage ---
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# --- CORRECTION 1: Changer le WORKDIR ---
# Le répertoire de travail est maintenant /app/src, là où se trouve le script principal.
WORKDIR /app/src

# Copie les dépendances depuis le builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# Copie le code de l'application DANS /app (un niveau au-dessus du WORKDIR)
COPY src/ /app/src/

# --- CORRECTION 2: Copier les fichiers statiques AU BON ENDROIT ---
# Copie les fichiers web dans /app/src, pour que send_from_directory(".", ...) les trouve.
COPY static/ /app/src/static/
COPY migrations/ /app/src/migrations/
COPY client.html /app/src/client.html
COPY activity.html /app/src/activity.html

# Création de l'utilisateur non-root
# On lui donne les droits sur /app entier
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/health')" || exit 1

# --- CORRECTION 3: Lancer le script directement ---
# Puisque nous sommes dans /app/src, on lance directement le script.
CMD ["python", "pubsub_ws.py"]