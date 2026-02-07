"""
Test the graph retriever with different query types.

This demonstrates when the graph retriever is helpful vs when it returns 0 results.
"""

import sys
import json
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.retrieval import GraphRetriever
from src.knowledge_graph.store import KnowledgeGraphStore


def test_queries():
    """Test different query types with the graph retriever."""

    # Load data
    data_path = project_root / "data" / "processed" / "patents.json"
    with open(data_path) as f:
        data = json.load(f)

    # Flatten chunks
    chunks = []
    for patent in data["patents"]:
        chunks.extend(patent["chunks"])

    # Initialize graph retriever
    kg_store = KnowledgeGraphStore(str(project_root / "data" / "processed" / "knowledge_graph.db"))
    kg_store.connect()

    graph_retriever = GraphRetriever(kg_store, max_hops=2, score_decay=0.5)
    graph_retriever.build_index(chunks)

    # Test queries
    queries = [
        {
            "type": "Natural Language",
            "query": "What is the effect of silicon content on magnetic properties of steel?",
            "expected": "0 chunks (no entities extracted)"
        },
        {
            "type": "Technical (Symbol)",
            "query": "What is the effect of Si on magnetic properties?",
            "expected": "Many chunks (Si is a chemical symbol)"
        },
        {
            "type": "Technical (Multiple)",
            "query": "How do Si and Cr affect core loss?",
            "expected": "Many chunks (Si and Cr are entities)"
        },
        {
            "type": "Technical (Numeric)",
            "query": "What happens at 2.5% Si content?",
            "expected": "Some chunks (Si + numeric pattern)"
        },
        {
            "type": "Process-focused",
            "query": "How does annealing affect grain structure?",
            "expected": "Some chunks (annealing is a process)"
        },
    ]

    print("="*80)
    print("GRAPH RETRIEVER TEST: Entity Extraction Sensitivity")
    print("="*80)
    print("\nThis shows when the graph retriever finds entities vs returns empty.\n")

    for i, test_case in enumerate(queries, 1):
        print(f"\n{'-'*80}")
        print(f"Query {i}: {test_case['type']}")
        print(f"{'-'*80}")
        print(f"Query: {test_case['query']}")
        print(f"Expected: {test_case['expected']}\n")

        # Run search
        results = graph_retriever.search(test_case['query'], top_k=5)

        print(f"Results: {len(results)} chunks retrieved")

        if results:
            print("\nTop 3 chunks:")
            for j, result in enumerate(results[:3], 1):
                print(f"  [{j}] Score: {result['graph_score']:.3f}")
                print(f"      Patent: {result['patent_id']}")
                print(f"      Preview: {result['content'][:80]}...")
        else:
            print("  (Graph retriever found no entities in query)")

        print(f"\n✓ This is {'expected!' if (len(results) > 0) == ('Many' in test_case['expected'] or 'Some' in test_case['expected']) else 'unexpected.'}")

    kg_store.close()

    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print("""
Graph retriever works best with:
  ✓ Chemical symbols (Si, Cr, Mn, Al, etc.)
  ✓ Specific property names (core_loss, yield_stress, etc.)
  ✓ Process terms (annealing, hot_rolling, etc.)
  ✓ Numeric values with units (2.5%, 1200°C, etc.)

Graph retriever struggles with:
  ✗ Full element names ("silicon" instead of "Si")
  ✗ General phrases ("magnetic properties" instead of "core_loss")
  ✗ Natural language questions

This is WHY we use HYBRID retrieval:
  - BM25 handles keyword matching (silicon → Si in text)
  - Semantic handles conceptual similarity
  - Graph handles entity relationships
  - RRF combines all three strengths!
    """)
    print("="*80 + "\n")


if __name__ == "__main__":
    test_queries()
