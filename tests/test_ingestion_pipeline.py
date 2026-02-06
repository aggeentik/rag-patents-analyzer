#!/usr/bin/env python3
"""Test the complete data ingestion pipeline end-to-end."""

import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.retrieval.bm25_retriever import BM25Retriever
from src.retrieval.semantic_retriever import SemanticRetriever
from src.knowledge_graph.store import KnowledgeGraphStore
from src.knowledge_graph.traversal import KnowledgeGraphTraversal


# Paths
PROCESSED_DIR = project_root / "data" / "processed"
PATENTS_JSON = PROCESSED_DIR / "patents.json"
BM25_INDEX = PROCESSED_DIR / "bm25_index.pkl"
FAISS_INDEX = PROCESSED_DIR / "faiss.index"
CHUNK_IDS = PROCESSED_DIR / "chunk_ids.json"
KG_DATABASE = PROCESSED_DIR / "knowledge_graph.db"


def test_patents_json():
    """Test 1: Verify patents.json exists and has correct structure."""
    print("Test 1: Testing patents.json...")

    assert PATENTS_JSON.exists(), f"❌ {PATENTS_JSON} not found"

    with open(PATENTS_JSON, "r") as f:
        data = json.load(f)

    assert "patents" in data, "❌ Missing 'patents' key"
    assert "total_patents" in data, "❌ Missing 'total_patents' key"
    assert "total_chunks" in data, "❌ Missing 'total_chunks' key"

    print(f"  ✓ Found {data['total_patents']} patents")
    print(f"  ✓ Found {data['total_chunks']} chunks")

    # Check chunk structure
    first_patent = data["patents"][0]
    assert "patent_id" in first_patent, "❌ Missing patent_id"
    assert "chunks" in first_patent, "❌ Missing chunks"

    first_chunk = first_patent["chunks"][0]
    assert "chunk_id" in first_chunk, "❌ Missing chunk_id"
    assert "content" in first_chunk, "❌ Missing content"
    assert "metadata" in first_chunk, "❌ Missing metadata"
    assert "entities" in first_chunk, "❌ Missing entities"

    print(f"  ✓ Chunk structure valid")
    print(f"  ✓ First chunk has {len(first_chunk['entities'])} entities")
    print("✅ Test 1 PASSED\n")

    return data


def test_bm25_index(chunks):
    """Test 2: Verify BM25 index works."""
    print("Test 2: Testing BM25 index...")

    assert BM25_INDEX.exists(), f"❌ {BM25_INDEX} not found"

    # Load BM25 index
    bm25 = BM25Retriever.load(str(BM25_INDEX), chunks)

    assert bm25.bm25 is not None, "❌ BM25 index not loaded"
    assert len(bm25.chunks) == len(chunks), f"❌ Chunk count mismatch"

    print(f"  ✓ Loaded BM25 index with {len(bm25.chunks)} chunks")

    # Test search
    query = "silicon content yield stress"
    results = bm25.search(query, top_k=5)

    assert len(results) == 5, f"❌ Expected 5 results, got {len(results)}"
    assert "bm25_score" in results[0], "❌ Missing bm25_score"
    assert "bm25_rank" in results[0], "❌ Missing bm25_rank"

    print(f"  ✓ Search returned {len(results)} results")
    print(f"  ✓ Top result score: {results[0]['bm25_score']:.4f}")
    print(f"  ✓ Top result: {results[0]['chunk_id']}")
    print("✅ Test 2 PASSED\n")

    return bm25


def test_faiss_index(chunks):
    """Test 3: Verify FAISS index works."""
    print("Test 3: Testing FAISS index...")

    assert FAISS_INDEX.exists(), f"❌ {FAISS_INDEX} not found"
    assert CHUNK_IDS.exists(), f"❌ {CHUNK_IDS} not found"

    # Load FAISS index
    semantic = SemanticRetriever.load(
        str(FAISS_INDEX),
        str(CHUNK_IDS),
        chunks
    )

    assert semantic.index is not None, "❌ FAISS index not loaded"
    assert semantic.index.ntotal == len(chunks), f"❌ Vector count mismatch"

    print(f"  ✓ Loaded FAISS index with {semantic.index.ntotal} vectors")
    print(f"  ✓ Vector dimension: {semantic.index.d}")

    # Test search
    query = "What is the optimal silicon content for high yield stress?"
    results = semantic.search(query, top_k=5)

    assert len(results) == 5, f"❌ Expected 5 results, got {len(results)}"
    assert "semantic_score" in results[0], "❌ Missing semantic_score"
    assert "semantic_rank" in results[0], "❌ Missing semantic_rank"

    print(f"  ✓ Search returned {len(results)} results")
    print(f"  ✓ Top result score: {results[0]['semantic_score']:.4f}")
    print(f"  ✓ Top result: {results[0]['chunk_id']}")
    print("✅ Test 3 PASSED\n")

    return semantic


def test_knowledge_graph():
    """Test 4: Verify knowledge graph works."""
    print("Test 4: Testing knowledge graph...")

    assert KG_DATABASE.exists(), f"❌ {KG_DATABASE} not found"

    # Connect to KG
    kg_store = KnowledgeGraphStore(str(KG_DATABASE))
    kg_store.connect()

    # Check entities
    all_entities = kg_store.get_entities_by_type("chemical_element")
    print(f"  ✓ Found {len(all_entities)} chemical element entities")

    properties = kg_store.get_entities_by_type("property")
    print(f"  ✓ Found {len(properties)} property entities")

    processes = kg_store.get_entities_by_type("process")
    print(f"  ✓ Found {len(processes)} process entities")

    # Test entity search
    si_entities = kg_store.find_entities("Si")
    assert len(si_entities) > 0, "❌ No Silicon entities found"
    print(f"  ✓ Found {len(si_entities)} Silicon entities")

    # Test traversal
    traversal = KnowledgeGraphTraversal(kg_store)
    traversal.build_networkx_graph()

    print(f"  ✓ Built graph with {traversal.graph.number_of_nodes()} nodes")
    print(f"  ✓ Built graph with {traversal.graph.number_of_edges()} edges")

    # Test finding related chunks
    related_chunks = traversal.find_related_chunks(["Si", "yield stress"], max_hops=2)
    print(f"  ✓ Found {len(related_chunks)} related chunks via graph traversal")

    kg_store.close()
    print("✅ Test 4 PASSED\n")


def test_integration(bm25, semantic):
    """Test 5: Integration test - compare retrieval methods."""
    print("Test 5: Integration test - comparing retrieval methods...")

    query = "silicon content for high yield strength steel"

    # BM25 results
    bm25_results = bm25.search(query, top_k=3)
    print(f"  ✓ BM25 top 3:")
    for i, r in enumerate(bm25_results, 1):
        print(f"    {i}. {r['chunk_id']} (score: {r['bm25_score']:.4f})")

    # Semantic results
    semantic_results = semantic.search(query, top_k=3)
    print(f"  ✓ Semantic top 3:")
    for i, r in enumerate(semantic_results, 1):
        print(f"    {i}. {r['chunk_id']} (score: {r['semantic_score']:.4f})")

    # Check for overlap
    bm25_ids = set(r['chunk_id'] for r in bm25_results)
    semantic_ids = set(r['chunk_id'] for r in semantic_results)
    overlap = bm25_ids & semantic_ids

    print(f"  ✓ Overlap: {len(overlap)}/3 chunks")
    print("✅ Test 5 PASSED\n")


def main():
    """Run all tests."""
    print("=" * 70)
    print("DATA INGESTION PIPELINE - END-TO-END TEST")
    print("=" * 70)
    print()

    try:
        # Test 1: patents.json
        data = test_patents_json()

        # Flatten chunks for testing
        chunks = []
        for patent in data["patents"]:
            chunks.extend(patent["chunks"])

        # Test 2: BM25 index
        bm25 = test_bm25_index(chunks)

        # Test 3: FAISS index
        semantic = test_faiss_index(chunks)

        # Test 4: Knowledge graph
        test_knowledge_graph()

        # Test 5: Integration
        test_integration(bm25, semantic)

        # Summary
        print("=" * 70)
        print("✅ ALL TESTS PASSED!")
        print("=" * 70)
        print()
        print("Data Ingestion Pipeline Status:")
        print(f"  ✅ PDF Parsing (Phase 1)")
        print(f"  ✅ Entity Extraction & KG (Phase 2)")
        print(f"  ✅ Index Building (Phase 3a)")
        print()
        print("Files ready:")
        print(f"  • patents.json      - {PATENTS_JSON.stat().st_size / 1024 / 1024:.1f} MB")
        print(f"  • bm25_index.pkl    - {BM25_INDEX.stat().st_size / 1024 / 1024:.1f} MB")
        print(f"  • faiss.index       - {FAISS_INDEX.stat().st_size / 1024 / 1024:.1f} MB")
        print(f"  • chunk_ids.json    - {CHUNK_IDS.stat().st_size / 1024:.1f} KB")
        print(f"  • knowledge_graph.db - {KG_DATABASE.stat().st_size / 1024:.1f} KB")
        print()
        print("Ready for Phase 3b: Query Pipeline!")

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {str(e)}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
