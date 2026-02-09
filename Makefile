.PHONY: help install lint format typecheck security deps check all clean

# Default target
help:
	@echo "Available targets:"
	@echo "  install     - Install development dependencies"
	@echo "  lint        - Run ruff linter"
	@echo "  format      - Run ruff formatter (check only)"
	@echo "  format-fix  - Run ruff formatter (apply changes)"
	@echo "  typecheck   - Run mypy type checker"
	@echo "  security    - Run bandit security checks"
	@echo "  deps        - Run deptry dependency checker"
	@echo "  audit       - Run pip-audit for vulnerability scanning"
	@echo "  check       - Run all checks (lint + format + typecheck + security + deps)"
	@echo "  all         - Run all checks including audit"
	@echo "  clean       - Clean cache files"

# Install development dependencies
install:
	uv add --dev ruff mypy bandit deptry pip-audit

# Ruff linter
lint:
	uv run ruff check src/ scripts/

# Ruff linter with auto-fix
lint-fix:
	uv run ruff check --fix src/ scripts/

# Ruff formatter (check only)
format:
	uv run ruff format --check src/ scripts/

# Ruff formatter (apply changes)
format-fix:
	uv run ruff format src/ scripts/

# MyPy type checker
typecheck:
	uv run mypy src/ scripts/

# Bandit security linter
security:
	uv run bandit -r src/ scripts/ -c pyproject.toml

# Deptry dependency checker
deps:
	uv run deptry src/ scripts/

# Pip-audit vulnerability scanner
audit:
	uv run pip-audit

# Run all checks (fast, no network)
check: lint format typecheck security deps
	@echo "All checks passed!"

# Run all checks including audit (slower, requires network)
all: check audit
	@echo "All checks including audit passed!"

# Clean cache files
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "Cache files cleaned"
