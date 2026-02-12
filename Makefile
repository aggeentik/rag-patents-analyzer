.PHONY: help install lint format typecheck security deps check all clean evaluate evaluate-quick report

# Default target
help:
	@echo "Available targets:"
	@echo "  install           - Install development dependencies"
	@echo "  lint              - Run ruff linter"
	@echo "  format            - Run ruff formatter (check only)"
	@echo "  format-fix        - Run ruff formatter (apply changes)"
	@echo "  typecheck         - Run mypy type checker"
	@echo "  security          - Run bandit security checks"
	@echo "  deps              - Run deptry dependency checker"
	@echo "  audit             - Run pip-audit for vulnerability scanning"
	@echo "  check             - Run all checks (lint + format + typecheck + security + deps)"
	@echo "  all               - Run all checks including audit"
	@echo "  evaluate          - Run full evaluation with RAGAS metrics (20 questions)"
	@echo "  evaluate-quick    - Run quick evaluation test (3 questions)"
	@echo "  report            - Generate evaluation report from latest results"
	@echo "  clean             - Clean cache files"

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

# Run full evaluation with RAGAS metrics (20 questions)
evaluate:
	@echo "Running full RAGAS evaluation (20 questions)..."
	@echo "Note: RAGAS will use your LLM from .env (Ollama/Bedrock). Make sure it's running."
	uv run python evals/eval.py --output evals/experiments/ragas_results.json
	@echo "Generating report..."
	uv run python evals/eval_vis.py evals/experiments/ragas_results.json --markdown evals/experiments/evaluation_report.md
	@echo "Evaluation complete! Check evals/experiments/"

# Run quick evaluation (3 questions)
evaluate-quick:
	@echo "Running quick evaluation (3 questions)..."
	uv run python evals/eval.py --dataset evals/datasets/ragas_dataset_3.json --output evals/experiments/ragas_results_quick.json
	@echo "Generating report..."
	uv run python evals/eval_vis.py evals/experiments/ragas_results_quick.json
	@echo "Quick evaluation complete! Check evals/experiments/"

# Generate report from latest results
report:
	@echo "Generating report from evals/experiments/ragas_results.json..."
	uv run python evals/eval_vis.py evals/experiments/ragas_results.json
	uv run python evals/eval_vis.py evals/experiments/ragas_results.json --markdown evals/experiments/evaluation_report.md
	@echo "Report saved to evals/experiments/evaluation_report.md"
