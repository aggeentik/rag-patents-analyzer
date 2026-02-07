#!/usr/bin/env python3
"""Quick demo of retrieval capabilities."""

import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.retrieval import BM25Retriever, SemanticRetriever
from src.knowledge_graph.store import KnowledgeGraphStore

# Paths
DATA_DIR = project_root / "data"
PROCESSED_DIR = DATA_DIR / "processed"

PATENTS_JSON = PROCESSED_DIR / "patents.json"
BM25_INDEX = PROCESSED_DIR / "bm25_index.pkl"
FAISS_INDEX = PROCESSED_DIR / "faiss.index"
CHUNK_IDS = PROCESSED_DIR / "chunk_ids.json"
KG_DATABASE = PROCESSED_DIR / "knowledge_graph.db"

# Load data
print("Loading indices...")
with open(PATENTS_JSON) as f:
    data = json.load(f)

chunks = []
for patent in data["patents"]:
    chunks.extend(patent["chunks"])

# Load retrievers
bm25 = BM25Retriever.load(str(BM25_INDEX), chunks)
semantic = SemanticRetriever.load(
    str(FAISS_INDEX),
    str(CHUNK_IDS),
    chunks
)
kg_store = KnowledgeGraphStore(str(KG_DATABASE))
kg_store.connect()

print(f"✓ Loaded {len(chunks)} chunks\n")

# Demo query
query = "What silicon content is needed for high yield strength?"
print(f"Query: {query}\n")

# BM25 results
print("=" * 70)
print("BM25 KEYWORD SEARCH:")
print("=" * 70)
bm25_results = bm25.search(query, top_k=3)
for i, r in enumerate(bm25_results, 1):
    print(f"\n{i}. {r['chunk_id']} (score: {r['bm25_score']:.2f})")
    print(f"   Section: {r['metadata'].get('section', 'Unknown')}")
    print(f"   Content: {r['content'][:200]}...")

# Semantic results
print("\n" + "=" * 70)
print("SEMANTIC SEARCH:")
print("=" * 70)
semantic_results = semantic.search(query, top_k=3)
for i, r in enumerate(semantic_results, 1):
    print(f"\n{i}. {r['chunk_id']} (score: {r['semantic_score']:.2f})")
    print(f"   Section: {r['metadata'].get('section', 'Unknown')}")
    print(f"   Content: {r['content'][:200]}...")

# Knowledge graph
print("\n" + "=" * 70)
print("KNOWLEDGE GRAPH ENTITIES:")
print("=" * 70)
si_entities = kg_store.find_entities("Si", entity_type="chemical_element")
print(f"\nFound {len(si_entities)} Silicon entities")
for e in si_entities[:3]:
    props = e['properties']
    print(f"  • {e['name']}: {props.get('value', '?')} {props.get('unit', '')}")

yield_entities = kg_store.find_entities("yield", entity_type="property")
print(f"\nFound {len(yield_entities)} yield stress entities")

kg_store.close()
print("\n✅ Demo complete!")
