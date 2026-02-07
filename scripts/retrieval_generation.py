"""
Demo script for hybrid retrieval + LLM answer generation.

This demonstrates the complete RAG pipeline:
1. Load all indices (BM25, FAISS, Knowledge Graph)
2. Initialize hybrid retriever with RRF fusion
3. Initialize LLM client (Ollama/Bedrock)
4. Retrieve relevant chunks for a query
5. Generate comprehensive answers using LLM

Usage:
    uv run python scripts/demo_hybrid_llm.py
"""

import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.retrieval import BM25Retriever, SemanticRetriever, GraphRetriever, HybridRetriever
from src.knowledge_graph.store import KnowledgeGraphStore
from src.llm import LLMClient, AnswerGenerator


def load_chunks(data_path: Path) -> list[dict]:
    """Load chunks from patents.json."""
    print(f"Loading chunks from {data_path}...")
    with open(data_path) as f:
        data = json.load(f)

    # Flatten chunks from all patents
    all_chunks = []
    for patent in data["patents"]:
        all_chunks.extend(patent["chunks"])

    print(f"✓ Loaded {len(all_chunks)} chunks from {data['total_patents']} patents\n")
    return all_chunks


def initialize_retrievers(data_dir: Path, chunks: list[dict]) -> dict:
    """Initialize all retrievers."""
    print("="*80)
    print("INITIALIZING RETRIEVERS")
    print("="*80)

    # BM25 Retriever
    print("\n[1/3] BM25 Retriever")
    bm25_retriever = BM25Retriever.load(
        str(data_dir / "bm25_index.pkl"),
        chunks
    )

    # Semantic Retriever
    print("\n[2/3] Semantic Retriever")
    semantic_retriever = SemanticRetriever.load(
        str(data_dir / "faiss.index"),
        str(data_dir / "chunk_ids.json"),
        chunks
    )

    # Graph Retriever
    print("\n[3/3] Graph Retriever")
    kg_store = KnowledgeGraphStore(str(data_dir / "knowledge_graph.db"))
    kg_store.connect()
    graph_retriever = GraphRetriever.load(
        path="",  # Not used, KG store is persistent
        chunks=chunks,
        kg_store=kg_store,
        max_hops=2,
        score_decay=0.5
    )

    print(f"\n{'='*80}\n")

    return {
        "bm25": bm25_retriever,
        "semantic": semantic_retriever,
        "graph": graph_retriever,
        "kg_store": kg_store
    }


def demo_hybrid_retrieval(hybrid_retriever: HybridRetriever, query: str, top_k: int = 5):
    """Demonstrate hybrid retrieval."""
    print("\n" + "="*80)
    print("HYBRID RETRIEVAL DEMO")
    print("="*80)

    results = hybrid_retriever.search(query, top_k=top_k)

    # Display results
    print("\n" + "="*80)
    print("TOP RESULTS")
    print("="*80)

    for i, result in enumerate(results, 1):
        print(f"\n[Result {i}] RRF Score: {result['rrf_score']:.4f}")
        metadata = result.get('metadata', {})
        print(f"Patent: {result.get('patent_id', 'unknown')} | Section: {metadata.get('section', 'unknown')} | Page: {metadata.get('page', 'unknown')}")
        print(f"Scores - {result.get('score_breakdown', 'N/A')}")
        print(f"Content: {result['content'][:200]}...")
        print("-"*80)

    # Show retriever statistics
    stats = hybrid_retriever.get_retriever_stats(results)
    print("\n" + "="*80)
    print("RETRIEVER STATISTICS")
    print("="*80)
    print(f"Total results: {stats['total_results']}")
    print(f"BM25 hits: {stats['bm25_hits']}")
    print(f"Semantic hits: {stats['semantic_hits']}")
    print(f"Graph hits: {stats['graph_hits']}")
    print(f"Multi-retriever hits: {stats['multi_retriever_hits']}")
    print("="*80 + "\n")

    return results


def demo_answer_generation(answer_generator: AnswerGenerator, query: str, chunks: list[dict]):
    """Demonstrate LLM answer generation."""
    print("\n" + "="*80)
    print("ANSWER GENERATION")
    print("="*80)
    print(f"Question: {query}\n")

    result = answer_generator.generate_answer(
        question=query,
        retrieved_chunks=chunks,
        temperature=0.0,
        stream=True  # Stream the answer for better UX
    )

    print("\n" + "="*80)
    print("SOURCES USED")
    print("="*80)
    for i, source in enumerate(result["sources"], 1):
        print(f"\n[Source {i}]")
        print(f"  Chunk ID: {source['chunk_id']}")
        print(f"  Patent: {source['patent_id']} | Section: {source['section']} | Page: {source['page']}")
        print(f"  RRF Score: {source['rrf_score']:.4f}")
        print(f"  Preview: {source['preview']}")

    print("\n" + "="*80)
    print("METADATA")
    print("="*80)
    print(f"Model: {result['metadata']['model']}")
    print(f"Chunks used: {result['metadata']['chunk_count']} / {result['metadata']['total_retrieved']} retrieved")
    print(f"Temperature: {result['metadata']['temperature']}")
    print("="*80 + "\n")

    return result


def main():
    """Run the demo."""
    # Paths
    data_dir = project_root / "data" / "processed"
    patents_path = data_dir / "patents.json"

    # Check if data exists
    if not patents_path.exists():
        print("❌ Error: patents.json not found!")
        print("Please run the data ingestion pipeline first:")
        print("  uv run python scripts/data_ingestion_pipeline.py")
        return

    # Load chunks
    chunks = load_chunks(patents_path)

    # Initialize retrievers
    retrievers = initialize_retrievers(data_dir, chunks)

    # Create hybrid retriever
    print("="*80)
    print("CREATING HYBRID RETRIEVER")
    print("="*80)
    hybrid_retriever = HybridRetriever(
        bm25_retriever=retrievers["bm25"],
        semantic_retriever=retrievers["semantic"],
        graph_retriever=retrievers["graph"],
        weights={
            "bm25": 1.0,      # Keyword matching
            "semantic": 1.0,  # Semantic similarity
            "graph": 0.5      # Knowledge graph (less weight)
        },
        rrf_k=60
    )
    print("="*80 + "\n")

    # Initialize LLM client
    print("="*80)
    print("INITIALIZING LLM CLIENT")
    print("="*80)

    # Try to load from environment, fallback to Ollama
    try:
        llm_client = LLMClient.from_env()
    except Exception as e:
        print(f"⚠️  Could not load from env: {e}")
        print("Using default: ollama/llama2")
        llm_client = LLMClient(model="ollama/llama2")

    print("="*80 + "\n")

    # Create answer generator
    answer_generator = AnswerGenerator(
        llm_client=llm_client,
        max_context_chunks=5,
        include_metadata=True
    )

    # Sample queries
    queries = [
        "What is the effect of silicon content on magnetic properties of steel?",
        "What are the annealing conditions for grain-oriented electrical steel?",
        "How does chromium affect the core loss in electrical steel?"
    ]

    print("="*80)
    print("AVAILABLE QUERIES")
    print("="*80)
    for i, q in enumerate(queries, 1):
        print(f"{i}. {q}")
    print("="*80 + "\n")

    # Run demo with first query
    query = queries[0]
    print(f"Running demo with query: {query}\n")

    # Step 1: Hybrid Retrieval
    retrieved_chunks = demo_hybrid_retrieval(hybrid_retriever, query, top_k=10)

    # Step 2: Answer Generation
    answer_result = demo_answer_generation(answer_generator, query, retrieved_chunks)

    # Cleanup
    retrievers["kg_store"].close()

    print("\n" + "="*80)
    print("DEMO COMPLETE")
    print("="*80)
    print("\nTo try other queries, modify the 'query' variable in the script")
    print("To use Bedrock, set these environment variables in .env:")
    print("  LLM_MODEL=bedrock/anthropic.claude-3-sonnet-20240229-v1:0")
    print("  AWS_ACCESS_KEY_ID=your_key")
    print("  AWS_SECRET_ACCESS_KEY=your_secret")
    print("  AWS_REGION_NAME=us-east-1")
    print("\nTo use different Ollama models:")
    print("  LLM_MODEL=ollama/mistral")
    print("  LLM_MODEL=ollama/llama2")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
