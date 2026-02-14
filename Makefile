.PHONY: help install lint format typecheck security deps check all clean evaluate evaluate-quick report generate-dataset generate-dataset-large

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
	@echo "  generate-dataset  - Generate synthetic QA dataset (10 questions)"
	@echo "  generate-dataset-large - Generate large synthetic QA dataset (50 questions)"
	@echo "  clean             - Clean cache files"

# Install development dependencies
install:
	uv add --dev ruff mypy bandit deptry pip-audit

# Ruff linter
lint:
	uv run ruff check src/ evals/

# Ruff linter with auto-fix
lint-fix:
	uv run ruff check --fix src/ evals/

# Ruff formatter (check only)
format:
	uv run ruff format --check src/ evals/

# Ruff formatter (apply changes)
format-fix:
	uv run ruff format src/ evals/

# MyPy type checker
typecheck:
	uv run mypy src/

# Bandit security linter
security:
	uv run bandit -r src/ evals/ -c pyproject.toml

# Deptry dependency checker
deps:
	uv run deptry src/

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
	@echo "Note: RAGAS will use your LLM from .env (Ollama/Bedrock)."
	$(eval TIMESTAMP := $(shell date +%Y%m%d_%H%M%S))
	uv run python evals/eval.py \
		--dataset evals/datasets/ragas_dataset_20.json \
		--ragas-model azure_ai/gpt-4.1 \
		--output evals/experiments/ragas_results_$(TIMESTAMP).json
	@echo "Generating report..."
	uv run python evals/eval_vis.py \
		evals/experiments/ragas_results_$(TIMESTAMP).json \
		--markdown evals/experiments/evaluation_report_$(TIMESTAMP).md
	@echo "Evaluation complete! Results saved:"
	@echo "  JSON: evals/experiments/ragas_results_$(TIMESTAMP).json"
	@echo "  Report: evals/experiments/evaluation_report_$(TIMESTAMP).md"

# Run quick evaluation test (3 questions)
evaluate-quick:
	@echo "Running quick RAGAS evaluation (3 questions)..."
	@echo "Note: RAGAS will use your LLM from .env (Ollama/Bedrock)."
	$(eval TIMESTAMP := $(shell date +%Y%m%d_%H%M%S))
	uv run python evals/eval.py \
		--dataset evals/datasets/ragas_dataset_3.json \
		--ragas-model azure_ai/gpt-4.1 \
		--output evals/experiments/ragas_results_quick_$(TIMESTAMP).json
	@echo "Generating report..."
	uv run python evals/eval_vis.py \
		evals/experiments/ragas_results_quick_$(TIMESTAMP).json \
		--markdown evals/experiments/evaluation_report_quick_$(TIMESTAMP).md
	@echo "Quick evaluation complete! Results saved:"
	@echo "  JSON: evals/experiments/ragas_results_quick_$(TIMESTAMP).json"
	@echo "  Report: evals/experiments/evaluation_report_quick_$(TIMESTAMP).md"

# Generate report from latest or specific results file
report:
	@if [ -z "$(FILE)" ]; then \
		LATEST=$$(ls -t evals/experiments/ragas_results_*.json 2>/dev/null | head -1); \
		if [ -z "$$LATEST" ]; then \
			echo "Error: No evaluation results found in evals/experiments/"; \
			echo "Run 'make evaluate' or 'make evaluate-quick' first."; \
			exit 1; \
		fi; \
		echo "Generating report from latest results: $$LATEST"; \
		BASENAME=$$(basename $$LATEST .json); \
		uv run python evals/eval_vis.py $$LATEST --markdown evals/experiments/$${BASENAME}_report.md; \
		echo "Report saved: evals/experiments/$${BASENAME}_report.md"; \
	else \
		echo "Generating report from: $(FILE)"; \
		BASENAME=$$(basename $(FILE) .json); \
		uv run python evals/eval_vis.py $(FILE) --markdown evals/experiments/$${BASENAME}_report.md; \
		echo "Report saved: evals/experiments/$${BASENAME}_report.md"; \
	fi

# Generate synthetic QA dataset (10 questions)
generate-dataset:
	@echo "Generating synthetic QA dataset (10 questions)..."
	uv run python evals/generate_dataset.py --testset-size 10
	@echo "Dataset generated: evals/datasets/generated_testset.json"

# Generate large synthetic QA dataset (50 questions)
generate-dataset-large:
	@echo "Generating large synthetic QA dataset (50 questions)..."
	uv run python evals/generate_dataset.py --testset-size 50 \
		--output evals/datasets/generated_testset_large.json
	@echo "Dataset generated: evals/datasets/generated_testset_large.json"
