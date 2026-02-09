# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Patents Analyzer** - An agentic RAG system for extracting insights from patent PDFs using hybrid retrieval (BM25 + Semantic Search + Knowledge Graph). Designed for steel manufacturing patents with complex multi-column layouts, fragmented data (tables, formulas, cross-references), and technical specifications.

**Current Status:** Complete RAG pipeline operational (feat/data-ingestion-pipeline branch). Successfully implemented:
- Data ingestion: 10 patents → 2075 chunks with entity extraction and KG construction
- Hybrid retrieval: BM25 + FAISS + Graph with RRF fusion ✓
- LLM integration: Ollama/Bedrock support via LiteLLM ✓

## Technology Stack

- **Python 3.13** with `uv` package manager
- **PDF Processing:** Docling, PyMuPDF
- **Knowledge Graph:** NetworkX, SQLite
- **Retrieval:** BM25 (`rank-bm25`), FAISS (`faiss-cpu`), sentence-transformers
- **LLM Integration:** LiteLLM (Ollama, AWS Bedrock, OpenAI)
- **NLP:** `nltk`, `tiktoken`

## Commands

### Environment Setup
```bash
# Install dependencies (uv handles virtual env automatically)
uv sync

# Run with uv (ensures correct environment)
uv run python <script.py>
```

### Data Processing Pipeline
```bash
# Full extraction: PDFs → chunks → entities → indices
uv run python scripts/data_ingestion_pipeline.py

# Rebuild indices only (requires patents.json)
uv run python scripts/build_indices.py

# Demo retrieval system (BM25 + Semantic only)
uv run python scripts/demo_retrieval.py

# Demo hybrid retrieval + LLM answer generation
uv run python scripts/demo_hybrid_llm.py
```

### Testing
```bash
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
[Answer Generator]
    ├── Context Building (top K chunks)
    ├── Prompt Construction
    └── LLM Generation (Ollama/Bedrock)
    ↓
Answer + Sources
```

### Module Organization

**`src/extraction/`** - PDF parsing and entity extraction
- `pdf_parser.py` - Layout-aware extraction using Docling (handles multi-column PDFs, tables, formulas)
- `entity_extractor.py` - Rule-based entity extraction (no LLM needed)

**`src/chunking/`** - Text chunking
- `chunker.py` - Token-based semantic chunking with cross-reference detection (500 tokens, 50 overlap)

**`src/knowledge_graph/`** - Knowledge graph construction
- `schema.py` - 9 entity types (chemical_element, property, process, etc.), 11 relationship types
- `builder.py` - Constructs entities and infers relationships from co-occurrence
- `store.py` - SQLite persistence with indexed queries
- `traversal.py` - NetworkX-based graph traversal (BFS with configurable hops)

**`src/retrieval/`** - Hybrid search system
- `bm25_retriever.py` - Sparse keyword retrieval with BM25Okapi
- `semantic_retriever.py` - Dense vector search using FAISS + sentence-transformers
- `graph_retriever.py` - Knowledge graph traversal with entity-based retrieval ✓
- `hybrid_retriever.py` - RRF (Reciprocal Rank Fusion) combining all three retrievers ✓

**`src/llm/`** - LLM integration and answer generation ✓
- `llm_client.py` - Unified LLM interface using LiteLLM (Ollama/Bedrock/OpenAI)
- `answer_generator.py` - RAG pipeline for generating answers from retrieved chunks

**`scripts/`** - Pipeline execution scripts
- `data_ingestion_pipeline.py` - **Main pipeline:** PDF → chunks → entities → KG → indices (all phases)
- `build_indices.py` - Rebuild BM25/FAISS indices from existing patents.json
- `demo_retrieval.py` - Demo of BM25 + Semantic retrieval (Phase 3a)
- `demo_hybrid_llm.py` - **Full RAG demo:** Hybrid retrieval + LLM answer generation ✓

**`tests/`** - Integration and unit tests
- Currently empty (tests removed during refactoring)
- TODO: Add comprehensive integration tests

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
**Entity Types (9):** chemical_element (Si, Cr, Mn), property (yield_stress, core_loss), process (annealing, hot_rolling), parameter, composition_range, table, formula, sample, figure

**Relationships (11):** DESCRIBED_IN (entity↔chunk), AFFECTS (element→property), REQUIRES (process→parameter), REFERENCES (chunk→table/formula), MEASURED_IN (property→table), plus CONTAINS, HAS_VALUE, ACHIEVED_IN, SHOWN_IN, SATISFIES, NEXT_STEP

**Graph Storage:** SQLite with 3 tables (entities, relationships, chunk_entities) + 6 indices for fast queries. NetworkX used for traversal algorithms (BFS, path finding).

### Retrieval System (Hybrid) ✓ IMPLEMENTED
1. **BM25** - Keyword matching for exact terms (chemical symbols, numeric values)
2. **Semantic (FAISS)** - Dense retrieval using sentence-transformers (all-MiniLM-L6-v2, 384-dim)
3. **Graph** - Entity-aware retrieval via knowledge graph traversal (2-hop BFS, configurable decay)
4. **Fusion** - RRF (Reciprocal Rank Fusion) combines all three with configurable weights
   - Formula: `RRF_score = Σ weight_i / (k + rank_i)` where k=60
   - Default weights: BM25=1.0, Semantic=1.0, Graph=0.5

### LLM Integration ✓ IMPLEMENTED
- **LiteLLM** - Unified interface for multiple LLM providers
- **Supported providers:**
  - Ollama (local models: llama2, mistral, etc.)
  - AWS Bedrock (Claude, Titan, Llama)
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
- `docs/DATA_INGESTION_PIPELINE.md` - **Comprehensive Phase 1-3a guide** (1030 lines)
- `docs/HYBRID_RETRIEVAL_AND_LLM.md` - **Phase 3b-4 guide:** Hybrid retrieval + LLM integration ✓
- `docs/patent-demo-full-plan.md` - **Original implementation plan** (all phases)
- `docs/solution.md` - **Problem analysis and architecture** (diagrams, roadmap)
- `.env.example` - LLM and retriever configuration template

## Development Patterns

### Adding New Entity Types
1. Add to `EntityType` enum in `src/knowledge_graph/schema.py`
2. Add extraction patterns to `EntityExtractor._extract_*()` methods
3. Update relationship inference in `KnowledgeGraphBuilder.build_relationships()`

### Adding New Retrievers
1. Create class in `src/retrieval/` inheriting common interface
2. Implement `build_index(chunks)`, `search(query, top_k)`, `save()`, `load()` methods
3. Integrate into `data_ingestion_pipeline.py` build phase
4. Add to hybrid fusion in future `hybrid_retriever.py`

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

# Initialize LLM (loads from .env or defaults to ollama/llama2)
llm = LLMClient.from_env()
# Or explicitly:
# llm = LLMClient(model="ollama/llama2")
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
LLM_MODEL=ollama/llama2
OLLAMA_API_BASE=http://localhost:11434

# AWS Bedrock
# LLM_MODEL=bedrock/anthropic.claude-3-sonnet-20240229-v1:0
# AWS_ACCESS_KEY_ID=your_key
# AWS_SECRET_ACCESS_KEY=your_secret
# AWS_REGION_NAME=us-east-1

LLM_TEMPERATURE=0.0
LLM_MAX_TOKENS=2048
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
2. Run `uv run python scripts/data_ingestion_pipeline.py`
3. Validate output: check `data/processed/patents.json` has expected chunk count
4. Test retrieval: `uv run python scripts/demo_retrieval.py`

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
- Current branch: `feat/data-ingestion-pipeline`
- Previous work: `feat/phase1`, `feat/phase2` (merged)
- Data files (`data/`) excluded via `.gitignore`

### Implementation Status
- **Phase 1-3a:** ✅ Data ingestion, entity extraction, KG, BM25/FAISS indices
- **Phase 3b:** ✅ Graph retriever + hybrid fusion with RRF
- **Phase 4:** ✅ LLM integration (Bedrock/Ollama) for answer generation
- **Phase 5:** ⏳ Streamlit UI for interactive search (TODO)

## Troubleshooting

**Error: `ModuleNotFoundError: No module named 'docling'`**
→ Run `uv sync` to install dependencies

**Error: `FileNotFoundError: data/processed/patents.json`**
→ Run extraction pipeline first: `uv run python scripts/data_ingestion_pipeline.py`

**Empty results from retrieval**
→ Check indices exist in `data/processed/`. If missing, rebuild with `build_indices.py`

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

## References

- **Full architecture:** See `docs/solution.md` for diagrams and phase breakdown
- **Data ingestion (Phase 1-3a):** See `docs/DATA_INGESTION_PIPELINE.md` for detailed component usage
- **Hybrid retrieval + LLM (Phase 3b-4):** See `docs/HYBRID_RETRIEVAL_AND_LLM.md` for RRF fusion and LLM integration
- **Implementation plan:** See `docs/patent-demo-full-plan.md` for complete code examples
- **Configuration:** See `.env.example` for LLM and retriever settings
