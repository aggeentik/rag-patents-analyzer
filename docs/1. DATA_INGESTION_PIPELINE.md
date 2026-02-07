# Data Ingestion Pipeline - Complete Guide

**Status:** ✅ **COMPLETE & TESTED**
**Date:** February 7, 2026
**Version:** 1.0

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Phase 1: PDF Parsing](#phase-1-pdf-parsing)
4. [Phase 2: Knowledge Graph](#phase-2-knowledge-graph)
5. [Phase 3a: Index Building](#phase-3a-index-building)
6. [Storage Architecture](#storage-architecture)
7. [Usage Guide](#usage-guide)
8. [Testing](#testing)
9. [Troubleshooting](#troubleshooting)
10. [Performance](#performance)

---

## Overview

The data ingestion pipeline processes patent PDF documents into multiple searchable indices, enabling hybrid retrieval with keyword, semantic, and graph-based search capabilities.

### Pipeline Flow

```
Raw PDFs → PDF Parsing → Entity Extraction → Index Building → Query-Ready Indices
(Phase 1)     (Phase 1)      (Phase 2)          (Phase 3a)        (Output)
```

### Key Statistics

- **Input:** 10 patent PDFs (4.3 MB total)
- **Output:** 2,075 searchable chunks, 244 entities, 1,541 relationships
- **Processing Time:** ~12 minutes total
- **Storage:** 8.3 MB across 5 index files
- **Retrieval Speed:** <50ms per query

---

## Architecture

### Single Chunking Strategy

The pipeline uses **one unified chunking strategy** for all purposes:
- **Method:** Layout-aware, token-based chunking
- **Size:** 500 tokens per chunk (target)
- **Overlap:** 50 tokens between chunks
- **Used for:** BM25 indexing, semantic embeddings, entity extraction, knowledge graph

### Data Flow

```
PDFs
  ↓
[PatentPDFParser]
  ↓ elements
[PatentChunker]
  ↓ chunks
[EntityExtractor] → entities → [KnowledgeGraphBuilder] → [KnowledgeGraphStore]
  ↓                                                              ↓
[BM25Retriever]                                          knowledge_graph.db
  ↓
bm25_index.pkl
  ↓
[SemanticRetriever]
  ↓
faiss.index + chunk_ids.json
```

### Components Overview

| Phase | Component | Input | Output | Purpose |
|-------|-----------|-------|--------|---------|
| 1 | PDF Parser | PDFs | Elements | Layout-aware extraction |
| 1 | Chunker | Elements | Chunks | Semantic chunking |
| 2 | Entity Extractor | Chunks | Entities | Domain entity recognition |
| 2 | KG Builder | Entities | Relationships | Graph construction |
| 2 | KG Store | Entities + Rels | SQLite DB | Persistent storage |
| 3a | BM25 Retriever | Chunks | BM25 Index | Keyword search |
| 3a | Semantic Retriever | Chunks | FAISS Index | Semantic search |

---

## Phase 1: PDF Parsing

### Overview

Phase 1 extracts structured content from patent PDFs with layout awareness, section detection, and semantic chunking.

### Components

#### 1. PatentPDFParser (`src/extraction/pdf_parser.py`)

**Features:**
- Multi-column PDF support via `unstructured` library
- Backup table extraction with `pdfplumber`
- Automatic patent ID detection
- Section detection (Abstract, Claims, Description, Examples, etc.)
- Formula/equation detection
- Preserves page numbers and coordinates

**Usage:**
```python
from src.extraction.pdf_parser import PatentPDFParser

parser = PatentPDFParser(use_hi_res=True)
patent_data = parser.extract("data/raw/EP1234567.pdf")

# Returns:
# {
#     "patent_id": "EP1234567",
#     "title": "Steel composition...",
#     "elements": [ExtractedElement, ...],
#     "tables": [...],
#     "metadata": {"filename": "...", "total_pages": 28}
# }
```

**Extracted Elements:**
- Text elements (titles, paragraphs, lists)
- Tables with structure preservation
- Formulas/equations
- Section boundaries
- Page numbers and coordinates

#### 2. PatentChunker (`src/extraction/chunker.py`)

**Features:**
- Token-based chunking with `tiktoken`
- Sentence-boundary splitting
- Configurable chunk size and overlap
- Cross-reference extraction (Table X, Formula Y, Figure Z)
- Smart chunking rules:
  - Tables → single chunk (never split)
  - Formulas → single chunk with context
  - Paragraphs → split at sentence boundaries

**Usage:**
```python
from src.extraction.chunker import PatentChunker

chunker = PatentChunker(
    chunk_size=500,      # tokens
    chunk_overlap=50,    # tokens
    min_chunk_size=100   # tokens
)

chunks = chunker.chunk_patent(patent_data)

# Each chunk:
# Chunk(
#     chunk_id="EP1234567_0001",
#     patent_id="EP1234567",
#     content="...",
#     metadata={"section": "Abstract", "page": 1, "type": "paragraph"},
#     entities=[],  # Populated in Phase 2
#     references=["Table 1", "Formula (2)"]
# )
```

### Configuration

**PatentPDFParser:**
- `use_hi_res=True` - Use OCR for better accuracy (slower)
- `use_hi_res=False` - Fast mode without OCR

**PatentChunker:**
- `chunk_size=500` - Target tokens per chunk
- `chunk_overlap=50` - Overlap for context preservation
- `min_chunk_size=100` - Minimum viable chunk size

### Section Detection

Automatically detects:
- Abstract
- Claims
- Background
- Detailed Description
- Examples
- Embodiments
- Brief Description
- Summary
- Field

---

## Phase 2: Knowledge Graph

### Overview

Phase 2 extracts domain entities and builds a knowledge graph with automatic relationship inference.

### Components

#### 1. Schema (`src/knowledge_graph/schema.py`)

**Entity Types (9 total):**
- `chemical_element` - Si, Cr, Mn, Al, etc. (18 predefined)
- `property` - yield stress, tensile strength, elongation, etc. (7 predefined)
- `process` - hot rolling, annealing, cold rolling, etc. (6 predefined)
- `parameter` - temperature, pressure, time
- `composition_range` - alloy composition ranges
- `table` - table references
- `formula` - formula references
- `sample` - material samples
- `figure` - figure references

**Relationship Types (11 total):**
- `DESCRIBED_IN` - Entity ↔ Chunk (entity appears in chunk)
- `AFFECTS` - Element → Property (element affects property)
- `REQUIRES` - Process → Parameter (process requires parameter)
- `REFERENCES` - Chunk → Table/Formula (chunk references table)
- `MEASURED_IN` - Property → Table (property measured in table)
- `CONTAINS` - Composition → Element
- `HAS_VALUE` - Entity → Value
- `ACHIEVED_IN` - Property → Process
- `SHOWN_IN` - Entity → Figure
- `SATISFIES` - Sample → Property
- `NEXT_STEP` - Process → Process

#### 2. Entity Extractor (`src/extraction/entity_extractor.py`)

**Extraction Patterns:**

**Chemical Elements:**
```python
# Patterns: "Si: 2.5%", "Cr = 1.5 mass%", "Mn 0.5-1.0%"
entities = extractor.extract_entities(chunk)
# Returns: Entity(type="chemical_element", name="Si",
#                 properties={"value": "2.5", "unit": "%"})
```

**Properties:**
```python
# Patterns: "yield stress of 700 MPa", "tensile strength: 850 MPa"
# Extracts: property name, value, unit
```

**Processes:**
```python
# Patterns: "annealing at 850°C", "hot rolling temperature"
# Extracts: process name, temperature, parameters
```

**Usage:**
```python
from src.extraction.entity_extractor import EntityExtractor

extractor = EntityExtractor()

for chunk in chunks:
    entities = extractor.extract_entities(chunk)
    # entities list contains all extracted entities with metadata
```

#### 3. Knowledge Graph Builder (`src/knowledge_graph/builder.py`)

**Features:**
- Entity deduplication and merging
- Automatic relationship inference from co-occurrence
- Five relationship types created automatically:
  - DESCRIBED_IN (all entities → chunks)
  - AFFECTS (elements + properties in same chunk)
  - REQUIRES (processes + parameters in same chunk)
  - REFERENCES (chunks → tables/formulas)
  - MEASURED_IN (properties + tables in same chunk)

**Usage:**
```python
from src.knowledge_graph.builder import KnowledgeGraphBuilder

builder = KnowledgeGraphBuilder()

# Add entities from all chunks
for chunk in chunks:
    entities = extractor.extract_entities(chunk)
    builder.add_entities(entities)

# Build relationships
builder.build_relationships(chunks)

# Export graph data
kg_data = builder.export()
# Returns: {
#   "entities": {entity_id: Entity},
#   "relationships": [Relationship, ...]
# }
```

#### 4. Knowledge Graph Store (`src/knowledge_graph/store.py`)

**Storage Schema (SQLite):**
```sql
CREATE TABLE entities (
    id TEXT PRIMARY KEY,
    type TEXT,
    name TEXT,
    properties TEXT,  -- JSON
    patent_id TEXT,
    chunk_ids TEXT    -- JSON list
);

CREATE TABLE relationships (
    id TEXT PRIMARY KEY,
    type TEXT,
    source_id TEXT,
    target_id TEXT,
    properties TEXT,  -- JSON
    chunk_id TEXT
);

CREATE TABLE chunk_entities (
    chunk_id TEXT,
    entity_id TEXT,
    PRIMARY KEY (chunk_id, entity_id)
);

-- Indexes for fast queries
CREATE INDEX idx_entities_type ON entities(type);
CREATE INDEX idx_entities_name ON entities(name);
CREATE INDEX idx_relationships_source ON relationships(source_id);
CREATE INDEX idx_relationships_target ON relationships(target_id);
CREATE INDEX idx_chunk_entities_chunk ON chunk_entities(chunk_id);
```

**Query Methods:**
```python
from src.knowledge_graph.store import KnowledgeGraphStore

store = KnowledgeGraphStore("data/processed/knowledge_graph.db")
store.connect()

# Find entities by name pattern
si_entities = store.find_entities("Si")

# Get entities by type
elements = store.get_entities_by_type("chemical_element")

# Get entities in a chunk
chunk_entities = store.get_entities_by_chunk("EP1234567_0001")

# Get related entities
related = store.get_related_entities(
    entity_id="EP1234567_Si_0",
    relationship_type="affects"
)

# Get chunks containing an entity
chunks = store.get_chunks_for_entity("EP1234567_Si_0")

store.close()
```

#### 5. Knowledge Graph Traversal (`src/knowledge_graph/traversal.py`)

**Features:**
- NetworkX integration for graph algorithms
- BFS traversal with configurable max hops
- Chunk discovery via entity relationships
- Distance-based scoring

**Usage:**
```python
from src.knowledge_graph.traversal import KnowledgeGraphTraversal

traversal = KnowledgeGraphTraversal(store)
traversal.build_networkx_graph()

# Find chunks related to query entities
related_chunks = traversal.find_related_chunks(
    query_entities=["Si", "yield stress"],
    max_hops=2,        # Maximum relationship hops
    max_chunks=10      # Maximum chunks to return
)

# Returns: [
#   {"chunk_id": "...", "score": 1.0, "distance": 0},
#   {"chunk_id": "...", "score": 0.5, "distance": 1},
#   ...
# ]

# Get entity context (incoming/outgoing relationships)
context = traversal.get_entity_context("EP1234567_Si_0")
# Returns: {
#   "entity": Entity,
#   "outgoing": [Relationship, ...],
#   "incoming": [Relationship, ...]
# }
```

### Complete Example: Phase 2 Usage

```python
from src.extraction.entity_extractor import EntityExtractor
from src.knowledge_graph.builder import KnowledgeGraphBuilder
from src.knowledge_graph.store import KnowledgeGraphStore
from src.knowledge_graph.traversal import KnowledgeGraphTraversal

# 1. Extract entities
extractor = EntityExtractor()
builder = KnowledgeGraphBuilder()

for chunk in chunks:
    entities = extractor.extract_entities(chunk)
    builder.add_entities(entities)

# 2. Build relationships
builder.build_relationships(chunks)

# 3. Save to database
store = KnowledgeGraphStore("data/processed/knowledge_graph.db")
store.connect()

kg_data = builder.export()
for entity in kg_data["entities"].values():
    store.save_entity(entity)
for rel in kg_data["relationships"]:
    store.save_relationship(rel)

# 4. Query the graph
si_entities = store.find_entities("Si")
print(f"Found {len(si_entities)} Silicon entities")

# 5. Traverse the graph
traversal = KnowledgeGraphTraversal(store)
traversal.build_networkx_graph()

related_chunks = traversal.find_related_chunks(
    query_entities=["Si", "yield stress"],
    max_hops=2
)
print(f"Found {len(related_chunks)} related chunks")

store.close()
```

---

## Phase 3a: Index Building

### Overview

Phase 3a builds BM25 and FAISS indices for keyword and semantic retrieval.

**Note on Storage:** BM25 index uses pickle for serialization. This is safe for our use case since the index is generated from our own trusted data sources (parsed patents). Pickle should only be used with trusted data.

### Components

#### 1. BM25 Retriever (`src/retrieval/bm25_retriever.py`)

**Features:**
- BM25Okapi algorithm for keyword-based retrieval
- Tokenization with `nltk.word_tokenize`
- Pickle storage for trained index (safe for trusted internal data)
- Fast keyword matching

**Usage:**
```python
from src.retrieval.bm25_retriever import BM25Retriever

# Build index
bm25 = BM25Retriever()
bm25.build_index(chunks)
bm25.save("data/processed/bm25_index.pkl")

# Load index
bm25 = BM25Retriever.load("data/processed/bm25_index.pkl", chunks)

# Search
results = bm25.search("silicon content yield stress", top_k=5)

# Returns: [
#   {
#     "chunk_id": "EP1234567_0137",
#     "content": "...",
#     "metadata": {...},
#     "bm25_score": 12.14,
#     "bm25_rank": 1
#   },
#   ...
# ]
```

**Algorithm Details:**
- BM25Okapi parameters: k1=1.5, b=0.75 (default)
- Tokenization: lowercase + word tokenization
- Scoring: term frequency, inverse document frequency, document length normalization

#### 2. Semantic Retriever (`src/retrieval/semantic_retriever.py`)

**Features:**
- Dense vector retrieval with FAISS
- sentence-transformers model: `all-MiniLM-L6-v2`
- 384-dimensional embeddings
- Cosine similarity via normalized vectors + IndexFlatIP
- Fast approximate nearest neighbor search

**Usage:**
```python
from src.retrieval.semantic_retriever import SemanticRetriever

# Build index
semantic = SemanticRetriever()
semantic.build_index(chunks)
semantic.save(
    "data/processed/faiss.index",
    "data/processed/chunk_ids.json"
)

# Load index
semantic = SemanticRetriever.load(
    "data/processed/faiss.index",
    "data/processed/chunk_ids.json",
    chunks
)

# Search
results = semantic.search(
    "What is the optimal silicon content for high yield stress?",
    top_k=5
)

# Returns: [
#   {
#     "chunk_id": "EP2679695_0116",
#     "content": "...",
#     "metadata": {...},
#     "semantic_score": 0.58,
#     "semantic_rank": 1
#   },
#   ...
# ]
```

**Implementation Details:**
- Model: `sentence-transformers/all-MiniLM-L6-v2`
- Embedding dimension: 384
- Normalization: L2 normalization for cosine similarity
- Index type: FAISS IndexFlatIP (inner product)
- Similarity metric: Cosine similarity (normalized inner product)

### Building Indices

**Script:** `scripts/build_indices.py`

```python
#!/usr/bin/env python3
"""Build BM25 and FAISS indices from patents.json."""

import json
from src.retrieval.bm25_retriever import BM25Retriever
from src.retrieval.semantic_retriever import SemanticRetriever

# Load chunks
with open("data/processed/patents.json") as f:
    data = json.load(f)

chunks = []
for patent in data["patents"]:
    chunks.extend(patent["chunks"])

print(f"Building indices for {len(chunks)} chunks...")

# Build BM25 index
print("\n1. Building BM25 index...")
bm25 = BM25Retriever()
bm25.build_index(chunks)
bm25.save("data/processed/bm25_index.pkl")
print("✓ BM25 index saved")

# Build FAISS index
print("\n2. Building FAISS index...")
semantic = SemanticRetriever()
semantic.build_index(chunks)
semantic.save(
    "data/processed/faiss.index",
    "data/processed/chunk_ids.json"
)
print("✓ FAISS index saved")

print("\n✅ All indices built successfully!")
```

**Run:**
```bash
uv run python scripts/build_indices.py
```

---

## Storage Architecture

### File Structure

```
data/processed/
├── patents.json           3.2 MB   # All chunks + metadata
├── bm25_index.pkl         1.4 MB   # BM25 keyword index (trusted internal data)
├── faiss.index            3.0 MB   # Vector embeddings
├── chunk_ids.json         36 KB    # FAISS position mapping
└── knowledge_graph.db     708 KB   # SQLite KG database

Total: 8.3 MB
```

### Data Formats

#### 1. patents.json

```json
{
  "total_patents": 10,
  "total_chunks": 2075,
  "patents": [
    {
      "patent_id": "EP1234567",
      "title": "Steel composition...",
      "chunks": [
        {
          "chunk_id": "EP1234567_0001",
          "patent_id": "EP1234567",
          "content": "The steel contains...",
          "metadata": {
            "section": "Examples",
            "page": 5,
            "type": "paragraph",
            "start_page": 5,
            "end_page": 5
          },
          "entities": [
            {
              "id": "EP1234567_Si_0",
              "type": "chemical_element",
              "name": "Si",
              "properties": {"value": "2.5", "unit": "%"},
              "context": "...",
              "patent_id": "EP1234567",
              "chunk_ids": ["EP1234567_0001"]
            }
          ],
          "references": ["Table 1", "Formula (2)"]
        }
      ]
    }
  ]
}
```

#### 2. bm25_index.pkl

Binary pickle file containing:
- Tokenized corpus (list of token lists)
- BM25Okapi model instance
- No chunk data (loaded separately)

**Security Note:** This file uses pickle serialization, which is safe for our use case since it contains only our own generated BM25 index from trusted patent data. Never load pickle files from untrusted sources.

#### 3. faiss.index

Binary FAISS file containing:
- 2,075 × 384-dimensional float32 vectors
- IndexFlatIP (inner product index)
- Normalized vectors for cosine similarity

#### 4. chunk_ids.json

```json
{
  "0": "EP1234567_0001",
  "1": "EP1234567_0002",
  ...
}
```
Maps FAISS vector position (integer) to chunk_id (string).

#### 5. knowledge_graph.db

SQLite database with 3 tables:
- `entities` - 244 entities (122 elements, 53 properties, 69 processes)
- `relationships` - 1,541 relationships
- `chunk_entities` - Many-to-many mapping

---

## Usage Guide

### Full Pipeline: PDFs to Indices

**Script:** `scripts/extract_patents.py`

```bash
# Process PDFs and build all indices
uv run python scripts/extract_patents.py
```

This script:
1. Finds all PDFs in `data/raw/`
2. Extracts and chunks each PDF (Phase 1)
3. Extracts entities from chunks (Phase 2)
4. Builds knowledge graph (Phase 2)
5. Saves `patents.json` and `knowledge_graph.db`
6. Builds BM25 and FAISS indices (Phase 3a)
7. Saves all index files

### Rebuild Indices Only

```bash
# If patents.json already exists, just rebuild indices
uv run python scripts/build_indices.py
```

### Load and Query Indices

```python
import json
from src.retrieval.bm25_retriever import BM25Retriever
from src.retrieval.semantic_retriever import SemanticRetriever
from src.knowledge_graph.store import KnowledgeGraphStore

# Load chunks
with open("data/processed/patents.json") as f:
    data = json.load(f)
chunks = [c for p in data["patents"] for c in p["chunks"]]

# Load BM25
bm25 = BM25Retriever.load("data/processed/bm25_index.pkl", chunks)
bm25_results = bm25.search("silicon content for high strength", top_k=5)

# Load FAISS
semantic = SemanticRetriever.load(
    "data/processed/faiss.index",
    "data/processed/chunk_ids.json",
    chunks
)
semantic_results = semantic.search(
    "optimal Si content for yield stress",
    top_k=5
)

# Load Knowledge Graph
kg_store = KnowledgeGraphStore("data/processed/knowledge_graph.db")
kg_store.connect()
si_entities = kg_store.find_entities("Si")
kg_store.close()
```

### Demo Script

**Run:** `uv run python demo_retrieval.py`

Shows BM25, semantic, and knowledge graph retrieval in action.

---

## Testing

### End-to-End Test

**Run:** `uv run python tests/test_ingestion_pipeline.py`

**Tests:**
1. **patents.json validation** - Structure, chunk count, metadata
2. **BM25 index** - Loading, searching, scoring
3. **FAISS index** - Loading, searching, vector count
4. **Knowledge graph** - Entity counts, graph structure, traversal
5. **Integration** - BM25 vs semantic comparison, ranking differences

**Expected Output:**
```
======================================================================
DATA INGESTION PIPELINE - END-TO-END TEST
======================================================================

✅ Test 1: patents.json - PASSED
  • 10 patents processed
  • 2,075 chunks created
  • Chunk structure valid

✅ Test 2: BM25 Index - PASSED
  • Loaded 2,075 chunks
  • Search working (query: "silicon content yield stress")
  • Top result: EP2278034_0137 (score: 12.1401)

✅ Test 3: FAISS Index - PASSED
  • Loaded 2,075 vectors (384 dimensions)
  • Semantic search working
  • Top result: EP2679695_0116 (score: 0.5804)

✅ Test 4: Knowledge Graph - PASSED
  • 122 chemical element entities
  • 53 property entities
  • 69 process entities
  • 924 graph nodes, 1,541 edges
  • Graph traversal working

✅ Test 5: Integration - PASSED
  • BM25 and semantic retrieval both working
  • Different ranking strategies (expected)
======================================================================
✅ ALL TESTS PASSED!
======================================================================
```

### Individual Phase Tests

```bash
# Phase 1 - PDF parsing
python test_phase1.py

# Phase 2 - Knowledge graph
uv run python tests/test_phase2_kg.py
```

---

## Troubleshooting

### Installation Issues

**Problem:** `unstructured` installation fails

**Solutions:**
```bash
# Try without cache
pip install "unstructured[pdf]" --no-cache-dir

# Or use conda
conda install -c conda-forge unstructured

# System dependencies may be required
brew install poppler tesseract  # macOS
apt-get install poppler-utils tesseract-ocr  # Ubuntu
```

**Problem:** `ModuleNotFoundError: No module named 'unstructured'`

**Solution:**
```bash
# Sync dependencies with uv
uv sync

# Or install with pip
pip install -r requirements.txt
```

### Processing Issues

**Problem:** PDF extraction is slow

**Solutions:**
- Set `use_hi_res=False` for faster extraction
- Hi-res mode uses OCR (slower but more accurate)
- Expected: ~1 minute per PDF in fast mode, ~2-3 minutes in hi-res mode

**Problem:** No entities extracted

**Solutions:**
- Check text contains recognizable patterns (Si:, Mn:, yield stress, etc.)
- Verify entity vocabularies in `schema.py` include your terms
- Check extraction patterns in `entity_extractor.py`

**Problem:** FAISS encoding is slow

**Solutions:**
- Expected time: ~2 minutes for 2,000 chunks
- Uses sentence-transformers model (runs on CPU by default)
- For GPU acceleration: `pip install faiss-gpu` (optional)

### Index Issues

**Problem:** BM25 search returns no results

**Solutions:**
- Verify index was built: check `bm25_index.pkl` exists
- Check tokenization: query should contain meaningful tokens
- Try different queries with common words from patents

**Problem:** FAISS returns wrong results

**Solutions:**
- Verify chunk_ids.json matches faiss.index
- Rebuild indices if files are out of sync
- Check normalization is applied (cosine similarity requires it)

**Problem:** Knowledge graph has no relationships

**Solutions:**
- Ensure entities are extracted (check `patents.json`)
- Verify co-occurrence in chunks (entities must be in same chunk)
- Check relationship building logic in `builder.py`

### Performance Issues

**Problem:** Slow graph traversal

**Solutions:**
- Reduce `max_hops` parameter (default: 2)
- Build NetworkX graph once and reuse
- Use database indexes (created automatically)

**Problem:** High memory usage

**Solutions:**
- Process PDFs in batches (not all at once)
- Disable hi-res mode for PDF parsing
- Use `faiss.IndexIVFFlat` for large datasets (>100K vectors)

---

## Performance

### Processing Time

| Operation | Time | Details |
|-----------|------|---------|
| PDF extraction | ~10 min | 10 PDFs (hi-res mode) |
| Entity extraction | Included | Part of extraction |
| KG building | ~30 sec | 244 entities, 1,541 rels |
| BM25 indexing | ~10 sec | 2,075 chunks |
| FAISS encoding | ~2 min | 2,075 × 384 vectors |
| **Total** | **~12 min** | Full pipeline |

### Retrieval Speed

| Operation | Latency | Details |
|-----------|---------|---------|
| BM25 search | <10 ms | Keyword matching |
| FAISS search | <20 ms | Nearest neighbor search |
| KG traversal | <50 ms | 2 hops, 10 chunks |

### Storage Efficiency

| Component | Size | Format |
|-----------|------|--------|
| Raw PDFs | 4.3 MB | Original files |
| patents.json | 3.2 MB | JSON (text + metadata) |
| BM25 index | 1.4 MB | Pickle (tokenized) |
| FAISS index | 3.0 MB | Binary (2075×384×4 bytes) |
| chunk_ids | 36 KB | JSON mapping |
| KG database | 708 KB | SQLite |
| **Total** | **8.3 MB** | All indices |

**Compression ratio:** 1.93x (8.3 MB indices from 4.3 MB PDFs)

### Scalability

**Current dataset:**
- 10 patents
- 2,075 chunks
- 244 entities
- 1,541 relationships

**Expected scaling:**
- **100 patents:** ~20K chunks, ~10-20 min processing, ~80 MB storage
- **1,000 patents:** ~200K chunks, ~2-3 hours processing, ~800 MB storage
- **10,000 patents:** ~2M chunks, ~20-30 hours processing, ~8 GB storage

**Optimization recommendations for large datasets:**
- Use FAISS IVF index for >100K vectors
- Batch PDF processing
- Distributed processing for >10K patents
- PostgreSQL for >1M entities

---

## Statistics

### Patent Coverage
- **Patents:** 10 (EP series, steel manufacturing)
- **Pages:** ~150 pages total
- **Chunks:** 2,075 chunks
- **Avg chunk size:** ~450 tokens

### Entity Extraction
- **Total entities:** 244 unique
  - Chemical elements: 122
  - Properties: 53
  - Processes: 69
- **Relationships:** 1,541
- **Graph connectivity:** 924 nodes, 1,541 edges

### Index Sizes
- **BM25:** 1.4 MB (tokenized text)
- **FAISS:** 3.0 MB (2,075 × 384 × 4 bytes)
- **Metadata:** 3.2 MB (full text + entities)
- **KG:** 708 KB (SQLite)

---

## Next Steps: Phase 3b - Query Pipeline

Now that the data ingestion pipeline is complete, proceed to:

1. **Graph Retriever** - Use KG for entity-aware retrieval
2. **Hybrid Retriever** - Combine BM25 + Semantic + Graph with RRF
3. **Test hybrid retrieval** - Validate fusion works correctly

Then:
- **Phase 4:** LLM Integration (Bedrock/Ollama for answer generation)
- **Phase 5:** Streamlit UI (interactive search interface)

---

## Summary

✅ **Phase 1:** PDF parsing with layout awareness - **COMPLETE**
✅ **Phase 2:** Entity extraction & knowledge graph - **COMPLETE**
✅ **Phase 3a:** BM25 & FAISS index building - **COMPLETE**

**Data Ingestion Pipeline Status:** Ready for Production

**Output Files:**
- ✅ `data/processed/patents.json` - 2,075 chunks with metadata
- ✅ `data/processed/bm25_index.pkl` - Keyword search index
- ✅ `data/processed/faiss.index` - Semantic search index
- ✅ `data/processed/chunk_ids.json` - FAISS position mapping
- ✅ `data/processed/knowledge_graph.db` - Entity graph database

**All tests passing. Ready for Phase 3b (Query Pipeline).**

---

**Document Version:** 1.0
**Last Updated:** February 7, 2026
**Status:** Complete & Validated
