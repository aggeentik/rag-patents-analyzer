#!/usr/bin/env python3
"""Quick demo of retrieval capabilities."""

import json
from pathlib import Path
from src.retrieval.bm25_retriever import BM25Retriever
from src.retrieval.semantic_retriever import SemanticRetriever
from src.knowledge_graph.store import KnowledgeGraphStore

# Load data
print("Loading indices...")
with open("data/processed/patents.json") as f:
    data = json.load(f)

chunks = []
for patent in data["patents"]:
    chunks.extend(patent["chunks"])

# Load retrievers
bm25 = BM25Retriever.load("data/processed/bm25_index.pkl", chunks)
semantic = SemanticRetriever.load(
    "data/processed/faiss.index",
    "data/processed/chunk_ids.json",
    chunks
)
kg_store = KnowledgeGraphStore("data/processed/knowledge_graph.db")
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
