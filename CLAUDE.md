# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Patents Analyzer** - An agentic RAG system for extracting insights from patent PDFs using hybrid retrieval (BM25 + Semantic Search + Knowledge Graph). Designed for steel manufacturing patents with complex multi-column layouts, fragmented data (tables, formulas, cross-references), and technical specifications.

**Current Status:** Phase 2 complete (feat/phase2 branch). Data ingestion pipeline operational with PDF parsing, entity extraction, knowledge graph construction, and BM25/FAISS indexing.

## Technology Stack

- **Python 3.13** with `uv` package manager
- **PDF Processing:** `unstructured[pdf]`, `pdfplumber`
- **Knowledge Graph:** NetworkX, SQLite
- **Retrieval:** BM25 (`rank-bm25`), FAISS (`faiss-cpu`), sentence-transformers
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
uv run python scripts/extract_patents.py

# Rebuild indices only (requires patents.json)
uv run python scripts/build_indices.py

# Demo retrieval system
uv run python scripts/demo_retrieval.py
```

### Testing
```bash
# End-to-end pipeline test
uv run python tests/test_ingestion_pipeline.py

# Knowledge graph tests
uv run python tests/test_phase2_kg.py

# Phase 1 tests (legacy)
uv run python scripts/test_phase1.py
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
```

### Module Organization

**`src/extraction/`** - PDF parsing and chunking
- `pdf_parser.py` - Layout-aware extraction using `unstructured` (handles multi-column PDFs, tables, formulas)
- `chunker.py` - Token-based semantic chunking with cross-reference detection
- `entity_extractor.py` - Rule-based entity extraction (no LLM needed)

**`src/knowledge_graph/`** - Knowledge graph construction
- `schema.py` - 9 entity types (chemical_element, property, process, etc.), 11 relationship types
- `builder.py` - Constructs entities and infers relationships from co-occurrence
- `store.py` - SQLite persistence with indexed queries
- `traversal.py` - NetworkX-based graph traversal (BFS with configurable hops)

**`src/retrieval/`** - Hybrid search system
- `bm25_retriever.py` - Sparse keyword retrieval with BM25Okapi
- `semantic_retriever.py` - Dense vector search using FAISS + sentence-transformers
- Future: `graph_retriever.py`, `hybrid_retriever.py` (RRF fusion)

**`scripts/`** - Pipeline execution scripts
- `extract_patents.py` - **Main pipeline:** PDF → entities → indices (all phases)
- `build_indices.py` - Rebuild BM25/FAISS from existing patents.json
- `demo_retrieval.py` - Test retrieval with sample queries

**`tests/`** - Integration and unit tests
- `test_ingestion_pipeline.py` - **Primary E2E test:** validates all output files
- `test_phase2_kg.py` - Knowledge graph specific tests

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

### Retrieval System (Hybrid)
1. **BM25** - Keyword matching for exact terms (chemical symbols, numeric values)
2. **Semantic (FAISS)** - Dense retrieval using sentence-transformers (all-MiniLM-L6-v2, 384-dim)
3. **Graph** - Entity-aware retrieval via knowledge graph traversal (2-hop BFS)
4. **Fusion** - RRF (Reciprocal Rank Fusion) combines all three with configurable weights

### Patent Structure Handling
- **Multi-column PDFs:** `unstructured` library with hi-res strategy
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
- `docs/patent-demo-full-plan.md` - **Original implementation plan** (all phases)
- `docs/solution.md` - **Problem analysis and architecture** (diagrams, roadmap)

## Development Patterns

### Adding New Entity Types
1. Add to `EntityType` enum in `src/knowledge_graph/schema.py`
2. Add extraction patterns to `EntityExtractor._extract_*()` methods
3. Update relationship inference in `KnowledgeGraphBuilder.build_relationships()`

### Adding New Retrievers
1. Create class in `src/retrieval/` inheriting common interface
2. Implement `build_index(chunks)`, `search(query, top_k)`, `save()`, `load()` methods
3. Integrate into `extract_patents.py` build phase
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

### Testing New Features
1. Add tests to `tests/test_ingestion_pipeline.py` (preferred) or create new test file
2. Use `pytest` patterns with assertions
3. Test with small dataset first (1-2 PDFs)
4. Validate output file formats and indices

## Common Tasks

### Processing New Patents
1. Place PDFs in `data/raw/`
2. Run `uv run python scripts/extract_patents.py`
3. Validate output: check `data/processed/patents.json` has expected chunk count
4. Test retrieval: `uv run python scripts/demo_retrieval.py`

### Debugging Extraction Issues
- **No entities found:** Check patterns in `entity_extractor.py` against actual PDF text
- **Wrong sections:** Update `SECTION_PATTERNS` in `pdf_parser.py`
- **Poor chunking:** Adjust chunk_size/overlap in `PatentChunker.__init__()`
- **Missing tables:** Verify `pdfplumber` fallback in `pdf_parser.py`

### Performance Optimization
- **Slow extraction:** Set `use_hi_res=False` in PatentPDFParser (trades accuracy for speed)
- **Memory issues:** Process PDFs in batches, not all at once
- **Slow FAISS:** Use smaller embedding model or reduce chunk count

## Important Notes

### Security
- **Pickle usage:** `bm25_index.pkl` uses pickle serialization. This is safe for this use case because the index is generated from our own trusted patent data (not loaded from external sources). The pickle file contains only the BM25 model state and tokenized corpus. Never load pickle files from untrusted sources in general applications.

### Dependencies
- `unstructured[pdf]` requires system libraries: `poppler`, `tesseract` (for hi-res OCR)
- FAISS CPU version used (no GPU required, but slower for large datasets)
- Python 3.13 required due to `uv.lock` specifications

### Git Workflow
- Main branch: `main`
- Feature branch: `feat/phase2` (current)
- Data files (`data/`) excluded via `.gitignore`

### Next Phases (Not Yet Implemented)
- **Phase 3b:** Graph retriever + hybrid fusion with RRF
- **Phase 4:** LLM integration (Bedrock/Ollama) for answer generation
- **Phase 5:** Streamlit UI for interactive search

## Troubleshooting

**Error: `ModuleNotFoundError: No module named 'unstructured'`**
→ Run `uv sync` to install dependencies

**Error: `FileNotFoundError: data/processed/patents.json`**
→ Run extraction pipeline first: `uv run python scripts/extract_patents.py`

**Empty results from retrieval**
→ Check indices exist in `data/processed/`. If missing, rebuild with `build_indices.py`

**Slow PDF extraction (>5 min per patent)**
→ Expected in hi-res mode. Disable OCR: `PatentPDFParser(use_hi_res=False)`

**FAISS dimension mismatch**
→ Embeddings changed. Delete `faiss.index` and `chunk_ids.json`, rebuild indices

**SQLite locked error**
→ Close previous database connections: `store.close()` before reopening

## References

- **Full architecture:** See `docs/solution.md` for diagrams and phase breakdown
- **Pipeline guide:** See `docs/DATA_INGESTION_PIPELINE.md` for detailed component usage
- **Implementation plan:** See `docs/patent-demo-full-plan.md` for complete code examples
