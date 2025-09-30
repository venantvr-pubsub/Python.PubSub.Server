# =============================================================================
# VARIABLES
# =============================================================================
# Cible par défaut si aucune n'est spécifiée
.DEFAULT_GOAL := help

# Définition de l'environnement virtuel.
# Ces variables pointent TOUJOURS vers le .venv, elles n'essaient plus d'utiliser les outils système.
VENV_DIR := .venv
PYTHON   := $(VENV_DIR)/bin/python
PIP      := $(VENV_DIR)/bin/pip

# =============================================================================
# CIBLES PRINCIPALES
# =============================================================================

# Déclare les cibles qui ne sont pas des fichiers pour éviter les conflits.
.PHONY: help install dev test clean venv

help: ## ✨ Affiche l'aide pour les commandes disponibles
	@echo "Commandes disponibles :"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

install: venv ## 📦 Installe les dépendances et le projet en mode éditable
	@echo "--- Installation des dépendances ---"
	@$(PIP) install -r requirements.txt
	@$(PIP) install -r requirements-dev.txt
	@$(PIP) install -e .

dev: install ## 🛠️  Alias pour la commande d'installation

test: venv ## 🔬 Lance les tests avec pytest
	@echo "--- Lancement des tests ---"
	@$(PYTHON) -m pytest tests/ -v --tb=short

clean: ## 🧹 Nettoie les fichiers temporaires et de build
	@echo "--- Nettoyage du projet ---"
	@rm -rf build/ dist/ *.egg-info .pytest_cache/
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete

# =============================================================================
# CIBLE UTILITAIRE (LA MAGIE EST ICI)
# =============================================================================

venv: $(PYTHON) ## 🌐 Crée l'environnement virtuel s'il n'existe pas

$(PYTHON):
	@echo "--- Création de l'environnement virtuel (.venv) ---"
	python3 -m venv $(VENV_DIR)
	@echo "--- Mise à jour de pip ---"
	@$(PIP) install --upgrade pip
