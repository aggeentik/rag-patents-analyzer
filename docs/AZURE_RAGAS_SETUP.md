# Using Azure OpenAI for RAGAS Evaluation

This guide shows how to use Azure AI Foundry (Azure OpenAI) GPT-4 specifically for RAGAS metrics evaluation while keeping your local Ollama for answer generation.

## Prerequisites

1. Azure OpenAI resource in Azure AI Foundry
2. A deployed GPT-4 model
3. Your API key and endpoint

## Setup

### 1. Get Your Azure OpenAI Credentials

From Azure AI Foundry portal:
- **Endpoint:** `https://your-resource.openai.azure.com/`
- **API Key:** Found in "Keys and Endpoint" section
- **Deployment Name:** Your GPT-4 deployment name (e.g., `gpt-4`)
- **API Version:** Usually `2024-02-15-preview` or latest

### 2. Set Environment Variables

#### Option A: In Terminal (temporary)

```bash
# Azure OpenAI credentials
export AZURE_API_KEY="your-azure-api-key"
export AZURE_API_BASE="https://your-resource.openai.azure.com/"
export AZURE_API_VERSION="2024-02-15-preview"

# Verify
echo $AZURE_API_KEY
```

#### Option B: In .env file (permanent)

Add to your `.env` file:

```bash
# Main LLM (for answer generation) - Ollama
LLM_MODEL=ollama/mistral:7b
OLLAMA_API_BASE=http://localhost:11434

# Azure OpenAI (for RAGAS evaluation only)
AZURE_API_KEY=your-azure-api-key
AZURE_API_BASE=https://your-resource.openai.azure.com/
AZURE_API_VERSION=2024-02-15-preview
```

### 3. Run Evaluation with Azure GPT-4

Use the format `azure/<deployment-name>`:

```bash
# Quick test (3 questions)
uv run python evals/eval.py \
    --dataset evals/datasets/ragas_dataset_3.json \
    --ragas-model azure/gpt-4 \
    --output evals/experiments/ragas_results_quick.json

# Full evaluation (20 questions)
uv run python evals/eval.py \
    --ragas-model azure/gpt-4 \
    --output evals/experiments/ragas_results.json
```

### 4. View Results

```bash
# Generate report
uv run python evals/eval_vis.py evals/experiments/ragas_results_quick.json

# Or use Makefile
make report
```

## What Happens

1. **Answer Generation** (slow, local):
   - Uses Ollama/Mistral from `.env`
   - Generates answers to test questions
   - ~30-60 seconds per question

2. **RAGAS Evaluation** (fast, Azure):
   - Uses Azure GPT-4 from environment variables
   - Calculates faithfulness, answer_relevancy, context_precision, context_recall
   - ~5-10 seconds per question

## Deployment Names

Your `--ragas-model` should match your Azure deployment name:

```bash
# If your deployment is named "gpt-4"
--ragas-model azure/gpt-4

# If your deployment is named "gpt-4-turbo"
--ragas-model azure/gpt-4-turbo

# If your deployment is named "my-gpt4-deployment"
--ragas-model azure/my-gpt4-deployment
```

## Complete Example

```bash
# 1. Set Azure credentials
export AZURE_API_KEY="abc123..."
export AZURE_API_BASE="https://my-resource.openai.azure.com/"
export AZURE_API_VERSION="2024-02-15-preview"

# 2. Make sure Ollama is running for answer generation
ollama list

# 3. Run quick evaluation (3 questions)
uv run python evals/eval.py \
    --dataset evals/datasets/ragas_dataset_3.json \
    --ragas-model azure/gpt-4 \
    --output evals/experiments/ragas_results_quick.json \
    --verbose

# 4. View results
uv run python evals/eval_vis.py evals/experiments/ragas_results_quick.json --detailed
```

## Expected Output

```
Using main LLM for answer generation: ollama/mistral:7b
Using dedicated LLM for RAGAS evaluation: azure/gpt-4

[1/3] Q1: Keyword & Formula Precision
Retriever stats: BM25=5, Semantic=5, Graph=0
Generating answer... ✓

...

Calculating RAGAS metrics...
Computing faithfulness, answer_relevancy, context_precision, context_recall...
Evaluating: 100%|██████████| 12/12 [00:45<00:00]

RAGAS Metrics:
  faithfulness: 0.8234
  answer_relevancy: 0.7891
  context_precision: 0.7123
  context_recall: 0.8456
```

## Cost Estimate

Azure OpenAI GPT-4 pricing (approximate):
- **Quick eval (3 questions):** ~$0.10-0.20
- **Full eval (20 questions):** ~$0.60-1.00

The cost comes from RAGAS evaluation only (making multiple GPT-4 calls to assess each metric). Answer generation uses your free local Ollama.

## Troubleshooting

### Error: "AuthenticationError: Incorrect API key"

```bash
# Check your key is set
echo $AZURE_API_KEY

# Make sure no extra spaces
export AZURE_API_KEY="your-key-here"
```

### Error: "The API deployment for this resource does not exist"

Your deployment name is wrong. Check it in Azure portal:
1. Go to Azure OpenAI resource
2. Click "Deployments"
3. Use exact deployment name

```bash
# If deployment is "my-gpt4"
--ragas-model azure/my-gpt4
```

### Error: "Connection timeout"

```bash
# Check endpoint format (should have trailing slash)
export AZURE_API_BASE="https://your-resource.openai.azure.com/"

# Verify API version
export AZURE_API_VERSION="2024-02-15-preview"
```

### RAGAS metrics still empty

Check the logs for specific errors:

```bash
uv run python evals/eval.py \
    --dataset evals/datasets/ragas_dataset_3.json \
    --ragas-model azure/gpt-4 \
    --verbose 2>&1 | grep -A 5 "ERROR"
```

## Alternative: Azure with Standard OpenAI SDK

If you prefer using Azure through the standard OpenAI SDK:

```bash
# Set this instead
export OPENAI_API_TYPE="azure"
export OPENAI_API_KEY="your-azure-key"
export OPENAI_API_BASE="https://your-resource.openai.azure.com/"
export OPENAI_API_VERSION="2024-02-15-preview"

# Then use standard format
--ragas-model gpt-4
```

## Verification Script

Quick test to verify Azure OpenAI is working:

```bash
# Test Azure connection
python3 << 'EOF'
from litellm import completion
import os

response = completion(
    model="azure/gpt-4",
    messages=[{"role": "user", "content": "Say 'Azure OpenAI is working!'"}],
    api_key=os.getenv("AZURE_API_KEY"),
    api_base=os.getenv("AZURE_API_BASE"),
    api_version=os.getenv("AZURE_API_VERSION")
)
print(response.choices[0].message.content)
EOF
```

Expected output: `Azure OpenAI is working!`

## Summary

**Two-LLM Setup:**
- 🏠 **Local Ollama/Mistral:** Generates answers (slow but free)
- ☁️ **Azure GPT-4:** Evaluates quality (fast but costs ~$0.10-1.00)

This gives you high-quality RAGAS metrics without needing a fast local LLM!

## Next Steps

After successful evaluation:
1. View detailed report: `make report`
2. Compare metrics across experiments
3. Iterate on retrieval weights
4. Run full 20-question evaluation
