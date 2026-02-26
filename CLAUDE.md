# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Patents Analyzer** - An agentic RAG system for extracting insights from patent PDFs using hybrid retrieval (BM25 + Semantic Search + Knowledge Graph). Designed for steel manufacturing patents with complex multi-column layouts, fragmented data (tables, formulas, cross-references), and technical specifications.

**Current Status:** Complete RAG system with web UI and evaluation framework operational. Successfully implemented:
- Data ingestion: PDF → chunks → entities → knowledge graph
- Hybrid retrieval: BM25 + FAISS + Graph with RRF fusion ✓
- Cross-encoder reranking: Optional post-fusion reranking ✓
- LLM integration: Ollama/Bedrock/Azure AI/OpenAI support via LiteLLM ✓
- Streamlit UI: Interactive search with PDF viewer, citation linking, and streaming answers ✓
- Evaluation: RAGAS-based evaluation with synthetic dataset generation ✓

## Technology Stack

- **Python 3.13** with `uv` package manager
- **PDF Processing:** Docling, PyMuPDF
- **Knowledge Graph:** NetworkX, SQLite
- **Retrieval:** BM25 (`rank-bm25`), FAISS (`faiss-cpu`), sentence-transformers
- **Reranking:** Cross-encoder (`sentence-transformers` CrossEncoder, default: `BAAI/bge-reranker-v2-m3`)
- **LLM Integration:** LiteLLM (Ollama, AWS Bedrock, Azure AI, OpenAI)
- **UI:** Streamlit
- **NLP:** `nltk`, `tiktoken`
- **Evaluation:** RAGAS, LangChain (optional, see Evaluation Setup)

## Commands

### Environment Setup
```bash
# Install core dependencies (uv handles virtual env automatically)
uv sync

# Install with evaluation dependencies (for running RAGAS evals)
uv sync --group evals

# Install with development tools
uv sync --group dev

# Install everything (core + evals + dev)
uv sync --all-groups

# Run with uv (ensures correct environment)
uv run python <script.py>
```

### Evaluation Setup
The evaluation system uses RAGAS for measuring RAG quality. Install eval dependencies:

```bash
# Install evaluation dependencies
uv sync --group evals

# Verify installation
uv run python -c "import ragas; print(f'RAGAS {ragas.__version__} installed')"

# Run full evaluation (uses generated_testset.json)
make evaluate
```

**Note:** Evaluation dependencies are **optional**. The core system works without them. Only install if you need to run quality evaluations.

### Data Processing Pipeline
```bash
# Full extraction: PDFs → chunks → entities → indices
uv run python src/data_ingestion.py

# Demo retrieval system (BM25 + Semantic only)
uv run python src/retrieval.py

# Demo hybrid retrieval + LLM answer generation
uv run python src/retrieval_generation.py
```

### Running the Web Application
```bash
# Start Streamlit UI (requires processed data and LLM setup)
uv run streamlit run src/app/app.py

# Then open browser at http://localhost:8501
```

### Testing
```bash
# Run all quality checks (lint, format, typecheck, security, deps)
make check

# Tests directory exists but is currently empty
# Previous test files were removed during code refactoring
# TODO: Add new integration tests for the complete pipeline
```

### Development
```bash
# Check Python path (should be .venv)
which python

# List project structure
tree -I '.venv|__pycache__|*.pyc'
```

## Architecture

### Data Flow

```
Raw PDFs (data/raw/)
    ↓
[PDF Parser] → layout-aware extraction with section detection
    ↓
[Chunker] → 500-token chunks with 50-token overlap
    ↓
[Entity Extractor] → chemical elements, properties, processes
    ↓
[KG Builder] → entities + relationships (AFFECTS, REQUIRES, etc.)
    ↓
[BM25 + FAISS Indexers] → keyword + semantic search indices
    ↓
data/processed/
    ├── patents.json (2075 chunks with metadata)
    ├── knowledge_graph.db (244 entities, 1541 relationships)
    ├── bm25_index.pkl (keyword index)
    ├── faiss.index (semantic vectors)
    └── chunk_ids.json (FAISS mapping)

Query Flow (RAG Pipeline):
User Query
    ↓
[Entity Extraction] ← Extract entities from query
    ↓
[Hybrid Retriever]
    ├── BM25 Retriever (keyword matching)
    ├── Semantic Retriever (vector similarity)
    └── Graph Retriever (entity graph traversal)
    ↓
[RRF Fusion] ← Combine results with weighted scores
    ↓
[Reranker] ← Optional cross-encoder reranking (BAAI/bge-reranker-v2-m3)
    ↓
[Answer Generator]
    ├── Context Building (top K chunks)
    ├── Prompt Construction
    └── LLM Generation (Ollama/Bedrock/Azure AI/OpenAI)
    ↓
Answer + Sources
```

### Module Organization

**`src/extraction/`** - PDF parsing and entity extraction
- `pdf_parser.py` - Layout-aware extraction using Docling (handles multi-column PDFs, tables, formulas)
- `entity_extractor.py` - Hybrid entity extraction (regex default, optional LLM via Instructor)

**`src/chunking/`** - Text chunking
- `chunker.py` - Token-based semantic chunking with cross-reference detection (500 tokens, 50 overlap)

**`src/knowledge_graph/`** - Knowledge graph construction
- `schema.py` - 16 entity types (chemical_element, property, process, material, application, etc.), 17 relationship types
- `builder.py` - Constructs entities and infers relationships from co-occurrence
- `store.py` - SQLite persistence with indexed queries
- `traversal.py` - NetworkX-based graph traversal (BFS with configurable hops)

**`src/retrieval/`** - Hybrid search system
- `bm25_retriever.py` - Sparse keyword retrieval with BM25Okapi
- `semantic_retriever.py` - Dense vector search using FAISS + sentence-transformers
- `graph_retriever.py` - Knowledge graph traversal with entity-based retrieval ✓
- `hybrid_retriever.py` - RRF (Reciprocal Rank Fusion) combining all three retrievers ✓
- `reranker.py` - Cross-encoder reranking using HuggingFace models (optional, post-fusion)

**`src/llm/`** - LLM integration and answer generation ✓
- `llm_client.py` - Unified LLM interface using LiteLLM (Ollama/Bedrock/Azure AI/OpenAI)
- `answer_generator.py` - RAG pipeline for generating answers from retrieved chunks

**`src/app/`** - Streamlit web application
- `app.py` - Interactive UI: hybrid retrieval search, streaming LLM answers, PDF viewer with text
  highlighting, inline citation badges with click-to-scroll, patent selection filter
  - `_render_pdf_page_base()` — cached page render keyed by (path, page) only; `render_pdf_page()` applies highlights fresh via PIL overlay on top of the cached base
  - Empty-results guard: skips LLM call and shows a warning when retrieval returns no passages
- `static/` - Static assets for UI

**`evals/`** - Evaluation framework (RAGAS)
- `eval.py` - Main RAGAS evaluation script with hybrid retrieval + LLM answer generation
- `eval_vis.py` - Results visualization and markdown report generation
- `generate_dataset.py` - Synthetic QA dataset generator using RAGAS TestsetGenerator
- `datasets/` - Test datasets (generated and curated)
- `experiments/` - Timestamped evaluation results and reports

### Logging Configuration

The project uses Python's standard `logging` module with a centralized configuration in `src/logging_config.py`.

**In library modules (`src/`):**
```python
import logging
logger = logging.getLogger(__name__)

# Use appropriate log levels
logger.debug("Detailed debugging info")
logger.info("Progress/status messages")
logger.warning("Warning messages")
logger.error("Error messages")
```

**In scripts (`scripts/`):**
```python
from src.logging_config import setup_logging
import logging

logger = logging.getLogger(__name__)

def main():
    setup_logging()  # Call at start of script
    # or setup_logging(level=logging.DEBUG) for verbose output
    logger.info("Script started")
```

**Note:** LLM streaming output (`print(content, end="", flush=True)`) intentionally uses print() for real-time terminal output, not logging.

## Key Concepts

### Chunking Strategy
- **One unified approach:** 500 tokens/chunk, 50-token overlap, sentence-boundary splitting
- **Smart handling:** Tables never split, formulas get context, process steps kept whole
- **Metadata preservation:** Section, page, type, references (Table X, Formula Y)
- Each chunk tracks entities and cross-references for graph enrichment

### Knowledge Graph Schema
**Entity Types (16):** chemical_element, property, process, parameter, composition_range, table, formula, sample, figure, inventor, assignee, patent_reference, application, material, problem, solution, patent_doc_reference

**Predefined Vocabularies:** 27 chemical elements, 7 properties, 6 processes, 8 applications, 8 materials

**Relationships (17):** DESCRIBED_IN (entity↔chunk), AFFECTS (element→property), REQUIRES (process→parameter), REFERENCES (chunk→table/formula), MEASURED_IN (property→table), CONTAINS, HAS_VALUE, ACHIEVED_IN, SHOWN_IN, SATISFIES, NEXT_STEP, MENTIONS, CITES, ADDRESSES_PROBLEM, USED_FOR, INVENTED_BY, ASSIGNEE_OF

**Graph Storage:** SQLite with 3 tables (entities, relationships, chunk_entities) + 6 indices for fast queries. NetworkX used for traversal algorithms (BFS, path finding).

### Retrieval System (Hybrid) ✓ IMPLEMENTED
1. **BM25** - Keyword matching for exact terms (chemical symbols, numeric values)
2. **Semantic (FAISS)** - Dense retrieval using sentence-transformers (all-MiniLM-L6-v2, 384-dim)
3. **Graph** - Entity-aware retrieval via knowledge graph traversal (2-hop BFS, configurable decay)
4. **Fusion** - RRF (Reciprocal Rank Fusion) combines all three with configurable weights
   - Formula: `RRF_score = Σ weight_i / (k + rank_i)` where k=60
   - Default weights: BM25=1.0, Semantic=1.0, Graph=1.2
5. **Reranker** (optional) - Cross-encoder post-fusion reranking using `BAAI/bge-reranker-v2-m3`
   - Enabled via `RERANKER_ENABLED=true` in `.env`
   - **Graph entity lookup mode** - controls how query entities are matched in the KG:
     - Default (`GRAPH_SEMANTIC_ENTITY_SEARCH=false`): exact/pattern matching via SQL LIKE — fast, no embeddings required
     - Optional (`GRAPH_SEMANTIC_ENTITY_SEARCH=true`): cosine-similarity lookup — requires entity embeddings pre-built in the KG

### LLM Integration ✓ IMPLEMENTED
- **LiteLLM** - Unified interface for multiple LLM providers
- **Supported providers:**
  - Ollama (local models: llama3.1, mistral, etc.)
  - AWS Bedrock (Claude, Titan, Llama)
  - Azure AI (GPT-4.1, etc.)
  - OpenAI (GPT-4, GPT-3.5)
- **Answer Generation** - RAG pipeline with context building and prompt engineering
- **Configuration** - Environment-based (.env file) or programmatic

### Patent Structure Handling
- **Multi-column PDFs:** Docling DocumentConverter with pypdfium2 backend
- **Section detection:** Abstract, Claims, Background, Detailed Description, Examples, Embodiments
- **Cross-references:** Automatic resolution of "Table 1", "Formula (2)", "FIG. 3"
- **Chemical formulas:** Pattern-based detection: `Formula\s*\(\d+\)`, `[Element]/\d+`

## File Locations

### Configuration
- `pyproject.toml` - Dependencies and project metadata
- No config.py yet - hardcoded paths in scripts (use `Path(__file__).parent` patterns)

### Data Directories
```
data/
├── raw/           # Original patent PDFs (not in git)
└── processed/     # Generated indices and databases (not in git)
    ├── patents.json          # 3.2 MB - all chunks + metadata
    ├── bm25_index.pkl        # 1.4 MB - keyword index (pickle - trusted internal data)
    ├── faiss.index           # 3.0 MB - semantic vectors
    ├── chunk_ids.json        # 36 KB - FAISS position mapping
    └── knowledge_graph.db    # 708 KB - SQLite entities + relationships
```

### Documentation
- `docs/1. DATA_INGESTION_PIPELINE.md` - **Comprehensive Phase 1-3a guide** (PDF parsing, chunking, KG, index building)
- `docs/2. RETRIEVAL_GENERATION.md` - **Phase 3b-4 guide:** Hybrid retrieval + LLM integration
- `docs/3. E2E_PIPELINE.md` - **Complete pipeline explanation** (plain-English walkthrough of all phases)
- `docs/4. EVALS.md` - **Evaluation system guide** (RAGAS metrics, running evals, interpreting results)
- `.env.example` - LLM, retriever, and reranker configuration template

## Development Patterns

### Adding New Entity Types
1. Add to `EntityType` enum in `src/knowledge_graph/schema.py`
2. Add extraction patterns to `EntityExtractor._extract_*()` methods
3. Update relationship inference in `KnowledgeGraphBuilder.build_relationships()`

### Adding New Retrievers
1. Create class in `src/retrieval/` inheriting common interface
2. Implement `build_index(chunks)`, `search(query, top_k)`, `save()`, `load()` methods
3. Integrate into `src/data_ingestion.py` build phase
4. Add to `src/retrieval/hybrid_retriever.py` fusion logic

### Working with Knowledge Graph
```python
from src.knowledge_graph.store import KnowledgeGraphStore
from src.knowledge_graph.traversal import KnowledgeGraphTraversal

store = KnowledgeGraphStore("data/processed/knowledge_graph.db")
store.connect()

# Query entities
si_entities = store.find_entities("Si", entity_type="chemical_element")
properties = store.get_entities_by_type("property")

# Graph traversal
traversal = KnowledgeGraphTraversal(store)
traversal.build_networkx_graph()
related_chunks = traversal.find_related_chunks(
    query_entities=["Si", "yield_stress"],
    max_hops=2,
    max_chunks=10
)

store.close()
```

### Using Hybrid Retriever
```python
from src.retrieval import BM25Retriever, SemanticRetriever, GraphRetriever, HybridRetriever
from src.knowledge_graph.store import KnowledgeGraphStore
import json

# Load chunks
with open("data/processed/patents.json") as f:
    chunks = json.load(f)["chunks"]

# Initialize retrievers
bm25 = BM25Retriever.load("data/processed/bm25_index.pkl", chunks)
semantic = SemanticRetriever.load(
    "data/processed/faiss.index",
    "data/processed/chunk_ids.json",
    chunks
)

kg_store = KnowledgeGraphStore("data/processed/knowledge_graph.db")
kg_store.connect()
graph = GraphRetriever.load("", chunks, kg_store, max_hops=2, score_decay=0.5)

# Create hybrid retriever
hybrid = HybridRetriever(
    bm25_retriever=bm25,
    semantic_retriever=semantic,
    graph_retriever=graph,
    weights={"bm25": 1.0, "semantic": 1.0, "graph": 0.5},
    rrf_k=60
)

# Search
results = hybrid.search("What is the effect of silicon on magnetic properties?", top_k=10)

# Analyze results
for r in results:
    print(f"RRF: {r['rrf_score']:.4f} | {r['score_breakdown']}")
    print(f"Content: {r['content'][:100]}...")

# Get statistics
stats = hybrid.get_retriever_stats(results)
print(f"BM25 hits: {stats['bm25_hits']}, Semantic: {stats['semantic_hits']}, Graph: {stats['graph_hits']}")

kg_store.close()
```

### Using LLM Integration
```python
from src.llm import LLMClient, AnswerGenerator

# Initialize LLM (loads from .env or defaults to ollama/llama3.1:8b)
llm = LLMClient.from_env()
# Or explicitly:
# llm = LLMClient(model="ollama/llama3.1:8b")
# llm = LLMClient(model="azure_ai/gpt-4.1")
# llm = LLMClient(model="bedrock/anthropic.claude-3-sonnet-20240229-v1:0")

# Create answer generator
generator = AnswerGenerator(
    llm_client=llm,
    max_context_chunks=5,
    include_metadata=True
)

# Generate answer from retrieved chunks
result = generator.generate_answer(
    question="What is the effect of silicon on magnetic properties?",
    retrieved_chunks=results,  # from hybrid retriever
    temperature=0.0,
    stream=True  # Stream output to console
)

print(result["answer"])
print(f"\nUsed {result['metadata']['chunk_count']} chunks")

# Generate summary
summary = generator.generate_summary(results[:5])

# Compare patents
comparison = generator.generate_comparison(
    question="How do annealing processes differ?",
    chunks_a=[c for c in results if c['patent_id'] == 'patent_1'],
    chunks_b=[c for c in results if c['patent_id'] == 'patent_2']
)
```

**Configuration (.env file):**
```env
# Ollama (local)
LLM_MODEL=ollama/llama3.1:8b
OLLAMA_API_BASE=http://localhost:11434

# AWS Bedrock
# LLM_MODEL=bedrock/anthropic.claude-3-sonnet-20240229-v1:0
# AWS_ACCESS_KEY_ID=your_key
# AWS_SECRET_ACCESS_KEY=your_secret
# AWS_REGION_NAME=us-east-1

LLM_TEMPERATURE=0.0
LLM_MAX_TOKENS=2048

# Hybrid Retriever Weights
RETRIEVER_BM25_WEIGHT=1.0
RETRIEVER_SEMANTIC_WEIGHT=1.0
RETRIEVER_GRAPH_WEIGHT=1.2
RETRIEVER_RRF_K=60

# Graph Retriever: semantic entity lookup (cosine similarity vs exact pattern match)
# Set to true only if entity embeddings have been built in the knowledge graph
GRAPH_SEMANTIC_ENTITY_SEARCH=false

# Reranker (optional)
RERANKER_ENABLED=false
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
```

### Testing New Features
1. Create new test files in `tests/` directory (currently empty)
2. Use `pytest` patterns with assertions
3. Test with small dataset first (1-2 PDFs)
4. Validate output file formats and indices
5. Consider adding end-to-end pipeline tests

## Common Tasks

### Processing New Patents
1. Place PDFs in `data/raw/`
2. Run `uv run python src/data_ingestion.py`
3. Validate output: check `data/processed/patents.json` has expected chunk count
4. Run the web app and test retrieval interactively: `uv run streamlit run src/app/app.py`

### Configuring PDF Extraction
The PDF parser uses Docling's DocumentConverter with pypdfium2 backend:

- Handles multi-column patent layouts automatically
- No OCR required for text-based PDFs
- Extraction time: ~30-60 seconds per patent
- Backend configured in `PatentPDFParser.__init__()` in `src/extraction/pdf_parser.py`

### Debugging Extraction Issues
- **No entities found:** Check patterns in `entity_extractor.py` against actual PDF text
- **Wrong sections:** Update state machine transitions in `PatentSectionStateMachine.TRANSITIONS`
- **Poor chunking:** Adjust chunk_size/overlap in `PatentChunker.__init__()`
- **Missing tables:** Check Docling's table extraction; tables are automatically detected and stitched across page breaks

### Performance Optimization
- **Slow extraction:** Docling typically processes patents in 30-60 seconds; batch processing recommended for many PDFs
- **Memory issues:** Process PDFs in batches, not all at once
- **Slow FAISS:** Use smaller embedding model or reduce chunk count

## Important Notes

### Security
- **Pickle usage:** `bm25_index.pkl` uses pickle serialization. This is safe for this use case because the index is generated from our own trusted patent data (not loaded from external sources). The pickle file contains only the BM25 model state and tokenized corpus. Never load pickle files from untrusted sources in general applications.

### Dependencies
- Docling uses pypdfium2 backend for PDF parsing (no external system dependencies required)
- FAISS CPU version used (no GPU required, but slower for large datasets)
- Python 3.13 required due to `uv.lock` specifications

### Git Workflow
- Main branch: `main`
- Data files (`data/`) excluded via `.gitignore`

### Implementation Status
- **Phase 1-3a:** ✅ Data ingestion, entity extraction, KG, BM25/FAISS indices
- **Phase 3b:** ✅ Graph retriever + hybrid fusion with RRF + optional cross-encoder reranking
- **Phase 4:** ✅ LLM integration (Bedrock/Ollama/Azure AI/OpenAI) for answer generation
- **Phase 5:** ✅ Streamlit UI with PDF viewer, citation linking, and streaming answers
  - PDF rendering split: cached base render (`_render_pdf_page_base`) + fresh PIL highlight overlay
  - Empty-results guard: skips LLM call, clears stale session state, shows actionable warning
- **Evaluation:** ✅ RAGAS evaluation framework with synthetic dataset generation

## Troubleshooting

**Error: `ModuleNotFoundError: No module named 'docling'`**
→ Run `uv sync` to install dependencies

**Error: `FileNotFoundError: data/processed/patents.json`**
→ Run extraction pipeline first: `uv run python src/data_ingestion.py`

**Empty results from retrieval**
→ Check indices exist in `data/processed/`. If missing, rebuild with `uv run python src/data_ingestion.py`

**Slow PDF extraction (>2 min per patent)**
→ Docling typically processes in 30-60 seconds. If slower, check PDF complexity or system resources

**FAISS dimension mismatch**
→ Embeddings changed. Delete `faiss.index` and `chunk_ids.json`, rebuild indices

**SQLite locked error**
→ Close previous database connections: `store.close()` before reopening

**Error: `ModuleNotFoundError: No module named 'src'`**
→ Script missing path setup. Ensure these lines are at the top of your script:
```python
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
```

**Warning: "embeddings.position_ids | UNEXPECTED" when loading sentence-transformers**
→ This is normal and safe to ignore. The model was trained for a different task and is being repurposed for embeddings. Does not affect quality.

**Search returns no results / "No matching passages found" warning in the UI**
→ The query likely contains no recognised chemical symbols, property names, or process terms (BM25 and Graph retrievers need entity overlap). Add specific terms: element symbols (Si, Mn, Al), temperatures (850°C), or properties (yield stress, iron loss). Semantic retrieval always returns candidates, so a completely empty result set is rare but possible when all selected patents are filtered out by the patent filter.

**LLM answer stream stops mid-sentence with no error**
→ Network interruption to the LLM provider (Azure AI, Bedrock, etc.). The partial answer is already displayed. Re-submit the same query — subsequent calls hit cached retrieval results so only the LLM call repeats. Alternatively switch to a local provider: set `LLM_MODEL=ollama/llama3.1:8b` and ensure `ollama serve` is running.

## References

- **Data ingestion (Phase 1-3a):** See `docs/1. DATA_INGESTION_PIPELINE.md` for detailed component usage
- **Hybrid retrieval + LLM (Phase 3b-4):** See `docs/2. RETRIEVAL_GENERATION.md` for RRF fusion and LLM integration
- **Full pipeline walkthrough:** See `docs/3. E2E_PIPELINE.md` for plain-English explanation of all phases
- **Evaluation system:** See `docs/4. EVALS.md` for comprehensive evaluation guide (RAGAS metrics, running evals, interpreting results)
- **Configuration:** See `.env.example` for LLM, retriever, and reranker settings
