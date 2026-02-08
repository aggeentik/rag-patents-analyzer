#!/usr/bin/env python3
"""Build BM25 and FAISS indices from existing patents.json."""

import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.retrieval.bm25_retriever import BM25Retriever
from src.retrieval.semantic_retriever import SemanticRetriever

# Paths
DATA_DIR = project_root / "data"
PROCESSED_DIR = DATA_DIR / "processed"

PATENTS_JSON = PROCESSED_DIR / "patents.json"
BM25_INDEX = PROCESSED_DIR / "bm25_index.pkl"
FAISS_INDEX = PROCESSED_DIR / "faiss.index"
CHUNK_IDS = PROCESSED_DIR / "chunk_ids.json"


def main():
    """Build search indices from patents.json."""
    print("=" * 70)
    print("BUILD SEARCH INDICES")
    print("=" * 70)
    print()

    # Load patents.json
    print(f"Loading {PATENTS_JSON}...")
    with open(PATENTS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    all_chunks = data["chunks"]

    print(f"Loaded {len(data['patents'])} patents with {len(all_chunks)} chunks")
    print()

    # Build BM25 index
    print("=" * 70)
    print("Building BM25 Index")
    print("=" * 70)
    bm25 = BM25Retriever()
    bm25.build_index(all_chunks)
    bm25.save(str(BM25_INDEX))
    print()

    # Build FAISS index
    print("=" * 70)
    print("Building FAISS Index")
    print("=" * 70)
    semantic = SemanticRetriever()
    semantic.build_index(all_chunks)
    semantic.save(str(FAISS_INDEX), str(CHUNK_IDS))
    print()

    # Summary
    print("=" * 70)
    print("✅ INDEX BUILDING COMPLETE!")
    print("=" * 70)
    print()
    print("Output files:")
    print(f"  • {BM25_INDEX}")
    print(f"  • {FAISS_INDEX}")
    print(f"  • {CHUNK_IDS}")
    print()
    print("All indices ready for retrieval!")
    print()


if __name__ == "__main__":
    main()
