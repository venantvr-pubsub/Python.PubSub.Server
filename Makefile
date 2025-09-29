.PHONY: help test install dev update clean

PYTHON := $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
PIP := $(if $(wildcard .venv/bin/pip),.venv/bin/pip,pip3)
SOURCES := tests

# Default target
help:
	@echo "Available targets:"
	@echo "  test      Run tests"
	@echo "  clean     Clean up generated files"
	@echo "  install   Install dependencies and package in editable mode"
	@echo "  dev       Alias for install (development setup)"
	@echo "  update    Update dependencies"

# Testing
test:
	$(PYTHON) -m pytest tests/ -v --tb=short

# Installation
install:
	$(PIP) install -r requirements.txt
	$(PIP) install -r requirements-dev.txt
	$(PIP) install -e .  # Install package in editable mode for IDE import resolution

# Development setup (alias for install)
dev: install

# Updates
update:
	$(PIP) install --upgrade pip
	$(PIP) install --upgrade -r requirements.txt
	$(PIP) install --upgrade -r requirements-dev.txt

# Clean up
clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
