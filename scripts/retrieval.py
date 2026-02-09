#!/usr/bin/env python3
"""Quick demo of retrieval capabilities."""

import json
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.knowledge_graph.store import KnowledgeGraphStore
from src.logging_config import setup_logging
from src.retrieval import BM25Retriever, SemanticRetriever

logger = logging.getLogger(__name__)

# Paths
DATA_DIR = project_root / "data"
PROCESSED_DIR = DATA_DIR / "processed"

PATENTS_JSON = PROCESSED_DIR / "patents.json"
BM25_INDEX = PROCESSED_DIR / "bm25_index.pkl"
FAISS_INDEX = PROCESSED_DIR / "faiss.index"
CHUNK_IDS = PROCESSED_DIR / "chunk_ids.json"
KG_DATABASE = PROCESSED_DIR / "knowledge_graph.db"


def main():
    """Run retrieval demo."""
    setup_logging()

    # Load data
    logger.info("Loading indices...")
    with open(PATENTS_JSON) as f:
        data = json.load(f)

    chunks = data["chunks"]

    # Load retrievers
    bm25 = BM25Retriever.load(str(BM25_INDEX), chunks)
    semantic = SemanticRetriever.load(str(FAISS_INDEX), str(CHUNK_IDS), chunks)
    kg_store = KnowledgeGraphStore(str(KG_DATABASE))
    kg_store.connect()

    logger.info("Loaded %d chunks", len(chunks))

    # Demo query
    query = "What silicon content is needed for high yield strength?"
    logger.info("Query: %s", query)

    # BM25 results
    logger.info("=" * 70)
    logger.info("BM25 KEYWORD SEARCH:")
    logger.info("=" * 70)
    bm25_results = bm25.search(query, top_k=3)
    for i, r in enumerate(bm25_results, 1):
        logger.info(
            "%d. %s (score: %.2f)",
            i,
            r["chunk_id"],
            r["bm25_score"],
        )
        logger.info("   Section: %s", r["metadata"].get("section", "Unknown"))
        logger.info("   Content: %s...", r["content"][:200])

    # Semantic results
    logger.info("=" * 70)
    logger.info("SEMANTIC SEARCH:")
    logger.info("=" * 70)
    semantic_results = semantic.search(query, top_k=3)
    for i, r in enumerate(semantic_results, 1):
        logger.info(
            "%d. %s (score: %.2f)",
            i,
            r["chunk_id"],
            r["semantic_score"],
        )
        logger.info("   Section: %s", r["metadata"].get("section", "Unknown"))
        logger.info("   Content: %s...", r["content"][:200])

    # Knowledge graph
    logger.info("=" * 70)
    logger.info("KNOWLEDGE GRAPH ENTITIES:")
    logger.info("=" * 70)
    si_entities = kg_store.find_entities("Si", entity_type="chemical_element")
    logger.info("Found %d Silicon entities", len(si_entities))
    for e in si_entities[:3]:
        props = e["properties"]
        logger.info("  - %s: %s %s", e["name"], props.get("value", "?"), props.get("unit", ""))

    yield_entities = kg_store.find_entities("yield", entity_type="property")
    logger.info("Found %d yield stress entities", len(yield_entities))

    kg_store.close()
    logger.info("Demo complete!")


if __name__ == "__main__":
    main()
