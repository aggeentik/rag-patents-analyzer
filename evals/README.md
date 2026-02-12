# Evaluation Framework

This directory contains the RAGAS evaluation framework for the Patents Analyzer RAG system.

## Structure

```
evals/
├── eval.py                           # Main evaluation script
├── eval_vis.py                       # Results visualization script
├── datasets/                         # Test datasets
│   ├── ragas_dataset_20.json        # Full dataset (20 questions)
│   ├── ragas_dataset_3.json         # Quick test (3 questions)
│   └── ragas_dataset_example.json   # Template for new tests
├── experiments/                      # Evaluation results
│   ├── ragas_results.json           # Latest results
│   └── evaluation_report.md         # Latest report
└── logs/                            # Evaluation logs

```

## Quick Start

### 1. Run Quick Evaluation (3 questions)

```bash
make evaluate-quick
```

This runs a quick test with 3 questions to verify everything works.

### 2. Run Full Evaluation (20 questions)

```bash
make evaluate
```

This runs the complete evaluation with all 20 test questions.

### 3. View Results

```bash
make report
```

Or directly:

```bash
# Console summary
uv run python evals/eval_vis.py evals/experiments/ragas_results.json

# Detailed report
uv run python evals/eval_vis.py evals/experiments/ragas_results.json --detailed

# Markdown report
uv run python evals/eval_vis.py evals/experiments/ragas_results.json --markdown evals/experiments/report.md
```

## Manual Usage

### Run Evaluation

```bash
# Full dataset (20 questions)
uv run python evals/eval.py

# Quick test (3 questions)
uv run python evals/eval.py --dataset evals/datasets/ragas_dataset_3.json

# Custom dataset
uv run python evals/eval.py --dataset evals/datasets/my_custom_dataset.json

# Adjust retrieval depth
uv run python evals/eval.py --top-k 10

# Custom output location
uv run python evals/eval.py --output evals/experiments/exp1_results.json

# Verbose logging
uv run python evals/eval.py --verbose

# Skip RAGAS metrics (faster, no LLM needed for evaluation)
uv run python evals/eval.py --skip-ragas
```

### Visualize Results

```bash
# Summary report
uv run python evals/eval_vis.py evals/experiments/ragas_results.json

# Detailed question-by-question
uv run python evals/eval_vis.py evals/experiments/ragas_results.json --detailed

# First 5 questions only
uv run python evals/eval_vis.py evals/experiments/ragas_results.json --detailed --max-questions 5

# Generate markdown report
uv run python evals/eval_vis.py evals/experiments/ragas_results.json --markdown evals/experiments/report.md
```

## Datasets

### ragas_dataset_20.json
Full test set with 20 questions across 5 categories:
- Keyword & Formula Precision (Q1-Q4)
- Tabular & Numerical Reasoning (Q5-Q8)
- Semantic & Conceptual (Q9-Q12)
- Entity-Relationship / Knowledge Graph (Q13-Q16)
- Multi-Document Synthesis (Q17-Q20)

### ragas_dataset_3.json
Quick test subset with 3 representative questions for rapid iteration.

### ragas_dataset_example.json
Template showing the dataset format for creating custom test cases.

## RAGAS Metrics

The evaluation calculates four key metrics:

1. **Faithfulness** (0-1) - Answer accuracy vs retrieved contexts
2. **Answer Relevancy** (0-1) - Answer relevance to question
3. **Context Precision** (0-1) - Precision of retrieved chunks
4. **Context Recall** (0-1) - Recall of ground truth information

**Target Scores:**
- Faithfulness > 0.8
- Answer Relevancy > 0.7
- Context Precision > 0.6
- Context Recall > 0.7

## Configuration

### LLM Configuration

RAGAS uses your LLM from `.env`:

```bash
# Ollama (default)
LLM_MODEL=ollama/mistral:7b
OLLAMA_API_BASE=http://localhost:11434

# AWS Bedrock
LLM_MODEL=bedrock/anthropic.claude-3-sonnet-20240229-v1:0
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION_NAME=us-east-1
```

### Retrieval Configuration

Edit `eval.py` to adjust retrieval parameters:

```python
# Change RRF fusion weights
hybrid = HybridRetriever(
    bm25_retriever=bm25,
    semantic_retriever=semantic,
    graph_retriever=graph,
    weights={"bm25": 1.5, "semantic": 1.0, "graph": 0.5},  # Emphasize BM25
    rrf_k=60
)

# Change graph traversal
graph = GraphRetriever.load("", chunks, kg_store, max_hops=3, score_decay=0.3)
```

## Experiments Workflow

### Baseline

```bash
# Run baseline with default settings
make eval
mv evals/experiments/ragas_results.json evals/experiments/baseline_results.json
```

### Experiment 1: BM25-Heavy

```bash
# Edit eval.py to increase BM25 weight
# weights={"bm25": 2.0, "semantic": 1.0, "graph": 0.5}

uv run python evals/eval.py --output evals/experiments/exp1_bm25_heavy.json
```

### Experiment 2: Graph-Heavy

```bash
# Edit eval.py to increase graph weight and depth
# weights={"bm25": 1.0, "semantic": 1.0, "graph": 1.5}
# max_hops=3

uv run python evals/eval.py --output evals/experiments/exp2_graph_heavy.json
```

### Compare Results

```bash
uv run python evals/eval_vis.py evals/experiments/baseline_results.json
uv run python evals/eval_vis.py evals/experiments/exp1_bm25_heavy.json
uv run python evals/eval_vis.py evals/experiments/exp2_graph_heavy.json
```

## Creating Custom Test Datasets

1. Copy the example template:

```bash
cp evals/datasets/ragas_dataset_example.json evals/datasets/my_dataset.json
```

2. Edit with your questions following this structure:

```json
{
  "metadata": {
    "description": "My custom test set",
    "format_version": "1.0"
  },
  "test_cases": [
    {
      "id": "CUSTOM_Q1",
      "category": "Keyword & Formula Precision",
      "retrieval_type": "Keyword (BM25)",
      "question": "Your question here",
      "ground_truth": "Expected answer here",
      "evidence": "Patent reference",
      "patent_ids": ["EP1234567"],
      "contexts": [],
      "answer": ""
    }
  ]
}
```

3. Run evaluation:

```bash
uv run python evals/eval.py --dataset evals/datasets/my_dataset.json
```

## Troubleshooting

### "FileNotFoundError: data/processed/patents.json"

Run the data ingestion pipeline first:

```bash
uv run python src/data_ingestion.py
```

### "LLM connection failed"

Check your LLM is running:

```bash
# For Ollama
curl http://localhost:11434/api/tags

# For Bedrock
aws sts get-caller-identity
```

### "RAGAS metrics calculation failed"

RAGAS requires additional dependencies:

```bash
uv pip install langchain-community
```

If still failing, run without RAGAS metrics:

```bash
uv run python evals/eval.py --skip-ragas
```

### Low RAGAS scores

Check:
1. **Low Faithfulness** - LLM hallucinating? Lower temperature, improve prompt
2. **Low Context Precision** - Too much noise? Adjust RRF weights, increase top-k threshold
3. **Low Context Recall** - Missing info? Increase top-k, improve chunking, expand KG
4. **Low Answer Relevancy** - Answer off-topic? Check prompt engineering, verify contexts

## Results Format

### ragas_results.json Structure

```json
{
  "questions": ["Q1", "Q2", ...],
  "ground_truths": ["Answer 1", "Answer 2", ...],
  "contexts": [["Context 1a", "Context 1b"], ...],
  "answers": ["Generated answer 1", ...],
  "ragas_metrics": {
    "faithfulness": 0.85,
    "answer_relevancy": 0.78,
    "context_precision": 0.72,
    "context_recall": 0.81
  },
  "category_statistics": {...},
  "detailed_results": [...]
}
```

## Integration with CI/CD

Add to your CI pipeline:

```bash
#!/bin/bash
set -e

echo "Running RAGAS evaluation..."
uv run python evals/eval.py --output evals/experiments/ci_results.json

echo "Checking metrics..."
python -c "
import json
results = json.load(open('evals/experiments/ci_results.json'))
metrics = results.get('ragas_metrics', {})

# Fail if metrics below threshold
assert metrics.get('faithfulness', 0) > 0.7, f'Faithfulness too low: {metrics.get(\"faithfulness\")}'
assert metrics.get('answer_relevancy', 0) > 0.6, f'Answer relevancy too low: {metrics.get(\"answer_relevancy\")}'

print('✓ All metrics passed!')
"
```

## References

- **Full documentation:** `tests/README.md`
- **Gold standard questions:** `tests/gold_standard_test_set.md`
- **RAGAS docs:** https://docs.ragas.io/
- **Project architecture:** `docs/HYBRID_RETRIEVAL_AND_LLM.md`
