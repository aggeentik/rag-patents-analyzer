# Patent Search

Extract insights from patent PDFs using hybrid retrieval combining BM25, semantic search, and knowledge graphs.

## Tech Stack

- **Python 3.13** with [uv](https://docs.astral.sh/uv/) package manager
- **PDF Processing**: Docling (parsing), PyMuPDF (rendering)
- **Retrieval**: BM25 (rank-bm25), FAISS (vector search), sentence-transformers
- **Knowledge Graph**: NetworkX, SQLite
- **LLM**: LiteLLM (supports Ollama and 100+ models across providers)
- **UI**: Streamlit

## Quickstart

### 1. Install dependencies

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/getting-started/installation/).

Navigate to the project directory and run:

```bash
uv sync
```

### 2. Set up Ollama (local LLM inference)

Install [Ollama](https://ollama.com/download), then pull a model:

```bash
ollama pull mistral:7b     # you can start with mistral:7b
ollama serve               # starts the API at localhost:11434
```

**Recommended small models:**

| Model | Size | Notes |
|---|---|---|
| `mistral:7b` | 7B | Best overall for patent Q&A at this size |
| `llama3` | 8B | Strong reasoning, good with technical text |
| `gemma2` | 9B | Competitive quality, slightly larger |
| `phi3` | 3.8B | Fastest option, works on low-RAM machines |

### 3. Configure environment variables

```bash
cp .env.example .env
```

Update your `.env` file with:

```
LLM_MODEL=ollama/mistral:7b
OLLAMA_API_BASE=http://localhost:11434
LOG_LEVEL=INFO  # Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
```

**Logging:** Set `LOG_LEVEL=DEBUG` in `.env` to see detailed logs from retrievers and LLM during searches. Defaults to `INFO` if not specified.

### 4. Run data ingestion (optional)

**Note:** Skip this step if `data/processed/` already contains indexed files and chunks.

Place patent PDFs in `data/raw/`, then run:

```bash
uv run python src/data_ingestion.py
```

This will parse PDFs, chunk text, extract entities, build a knowledge graph, and create search indices in `data/processed/`.

### 5. Run the app

```bash
uv run streamlit run src/app/app.py
```

Open a browser at `http://localhost:8501` where you can perform hybrid search queries and get LLM-powered answers from your patent documents.




