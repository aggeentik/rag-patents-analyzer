# patents-analyzer

Agentic RAG system for extracting insights from patent PDFs using hybrid retrieval (BM25 + Semantic Search + Knowledge Graph).

## Quickstart

### 1. Install UV ()

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/getting-started/installation/).

```bash
uv sync
cp .env.example .env   # configure your LLM provider
```

### 4. Set up Ollama (local LLM)

Install [Ollama](https://ollama.com), then pull a model:

```bash
ollama pull mistral        # 7B, good balance of speed and quality
ollama serve               # starts the API at localhost:11434
```

Set in your `.env`:

```
LLM_MODEL=ollama/mistral
OLLAMA_API_BASE=http://localhost:11434
```

### 2. Run data ingestion

Place patent PDFs into `data/raw/`, then:

```bash
uv run python scripts/data_ingestion_pipeline.py
```

This parses PDFs, chunks text, extracts entities, builds a knowledge graph, and creates search indices under `data/processed/`.

### 3. Run the UI

```bash
uv run streamlit run src/app/app.py
```

Opens a browser at `http://localhost:8501` with hybrid search and LLM-powered answers.



**Recommended small models:**

| Model | Size | Notes |
|---|---|---|
| `mistral` | 7B | Best overall for patent Q&A at this size |
| `llama3` | 8B | Strong reasoning, good with technical text |
| `gemma2` | 9B | Competitive quality, slightly larger |
| `phi3` | 3.8B | Fastest option, works on low-RAM machines |
