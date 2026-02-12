"""
Demo script for hybrid retrieval + LLM answer generation.

This demonstrates the complete RAG pipeline:
1. Load all indices (BM25, FAISS, Knowledge Graph)
2. Initialize hybrid retriever with RRF fusion
3. Initialize LLM client (Ollama/Bedrock)
4. Retrieve relevant chunks for a query
5. Generate comprehensive answers using LLM

Usage:
    uv run python src/retrieval_generation.py
"""

import json
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.knowledge_graph.store import KnowledgeGraphStore  # noqa: E402
from src.llm import AnswerGenerator, LLMClient  # noqa: E402
from src.logging_config import setup_logging  # noqa: E402
from src.retrieval import (  # noqa: E402
    BM25Retriever,
    GraphRetriever,
    HybridRetriever,
    SemanticRetriever,
)

logger = logging.getLogger(__name__)


def load_chunks(data_path: Path) -> list[dict]:
    """Load chunks from patents.json."""
    logger.info("Loading chunks from %s...", data_path)
    with open(data_path) as f:
        data = json.load(f)

    all_chunks = data["chunks"]

    logger.info("Loaded %d chunks from %d patents", len(all_chunks), data["total_patents"])
    return all_chunks


def initialize_retrievers(data_dir: Path, chunks: list[dict]) -> dict:
    """Initialize all retrievers."""
    logger.info("=" * 80)
    logger.info("INITIALIZING RETRIEVERS")
    logger.info("=" * 80)

    # BM25 Retriever
    logger.info("[1/3] BM25 Retriever")
    bm25_retriever = BM25Retriever.load(str(data_dir / "bm25_index.pkl"), chunks)

    # Semantic Retriever
    logger.info("[2/3] Semantic Retriever")
    semantic_retriever = SemanticRetriever.load(
        str(data_dir / "faiss.index"), str(data_dir / "chunk_ids.json"), chunks
    )

    # Graph Retriever
    logger.info("[3/3] Graph Retriever")
    kg_store = KnowledgeGraphStore(str(data_dir / "knowledge_graph.db"))
    kg_store.connect()
    graph_retriever = GraphRetriever.load(
        path="",  # Not used, KG store is persistent
        chunks=chunks,
        kg_store=kg_store,
        max_hops=2,
        score_decay=0.5,
    )

    logger.info("=" * 80)

    return {
        "bm25": bm25_retriever,
        "semantic": semantic_retriever,
        "graph": graph_retriever,
        "kg_store": kg_store,
    }


def demo_hybrid_retrieval(hybrid_retriever: HybridRetriever, query: str, top_k: int = 5):
    """Demonstrate hybrid retrieval."""
    logger.info("=" * 80)
    logger.info("HYBRID RETRIEVAL DEMO")
    logger.info("=" * 80)

    results = hybrid_retriever.search(query, top_k=top_k)

    # Display results
    logger.info("=" * 80)
    logger.info("TOP RESULTS")
    logger.info("=" * 80)

    for i, result in enumerate(results, 1):
        metadata = result.get("metadata", {})
        logger.info(
            "[Result %d] RRF Score: %.4f",
            i,
            result["rrf_score"],
        )
        logger.info(
            "Patent: %s | Section: %s | Page: %s",
            result.get("patent_id", "unknown"),
            metadata.get("section", "unknown"),
            metadata.get("page", "unknown"),
        )
        logger.info("Scores - %s", result.get("score_breakdown", "N/A"))
        logger.info("Content: %s...", result["content"][:200])
        logger.info("-" * 80)

    # Show retriever statistics
    stats = hybrid_retriever.get_retriever_stats(results)
    logger.info("=" * 80)
    logger.info("RETRIEVER STATISTICS")
    logger.info("=" * 80)
    logger.info("Total results: %d", stats["total_results"])
    logger.info("BM25 hits: %d", stats["bm25_hits"])
    logger.info("Semantic hits: %d", stats["semantic_hits"])
    logger.info("Graph hits: %d", stats["graph_hits"])
    logger.info("Multi-retriever hits: %d", stats["multi_retriever_hits"])
    logger.info("=" * 80)

    return results


def demo_answer_generation(answer_generator: AnswerGenerator, query: str, chunks: list[dict]):
    """Demonstrate LLM answer generation."""
    logger.info("=" * 80)
    logger.info("ANSWER GENERATION")
    logger.info("=" * 80)
    logger.info("Question: %s", query)

    result = answer_generator.generate_answer(
        question=query,
        retrieved_chunks=chunks,
        temperature=0.0,
        stream=True,  # Stream the answer for better UX
    )

    logger.info("=" * 80)
    logger.info("SOURCES USED")
    logger.info("=" * 80)
    for i, source in enumerate(result["sources"], 1):
        logger.info("[Source %d]", i)
        logger.info("  Chunk ID: %s", source["chunk_id"])
        logger.info(
            "  Patent: %s | Section: %s | Page: %s",
            source["patent_id"],
            source["section"],
            source["page"],
        )
        logger.info("  RRF Score: %.4f", source["rrf_score"])
        logger.info("  Preview: %s", source["preview"])

    logger.info("=" * 80)
    logger.info("METADATA")
    logger.info("=" * 80)
    logger.info("Model: %s", result["metadata"]["model"])
    logger.info(
        "Chunks used: %d / %d retrieved",
        result["metadata"]["chunk_count"],
        result["metadata"]["total_retrieved"],
    )
    logger.info("Temperature: %s", result["metadata"]["temperature"])
    logger.info("=" * 80)

    return result


def main():
    """Run the demo."""
    setup_logging()

    # Paths
    data_dir = project_root / "data" / "processed"
    patents_path = data_dir / "patents.json"

    # Check if data exists
    if not patents_path.exists():
        logger.error("patents.json not found!")
        logger.info("Please run the data ingestion pipeline first:")
        logger.info("  uv run python scripts/data_ingestion_pipeline.py")
        return

    # Load chunks
    chunks = load_chunks(patents_path)

    # Initialize retrievers
    retrievers = initialize_retrievers(data_dir, chunks)

    # Create hybrid retriever
    logger.info("=" * 80)
    logger.info("CREATING HYBRID RETRIEVER")
    logger.info("=" * 80)
    hybrid_retriever = HybridRetriever(
        bm25_retriever=retrievers["bm25"],
        semantic_retriever=retrievers["semantic"],
        graph_retriever=retrievers["graph"],
        weights={
            "bm25": 1.0,  # Keyword matching
            "semantic": 1.0,  # Semantic similarity
            "graph": 0.5,  # Knowledge graph (less weight)
        },
        rrf_k=60,
    )
    logger.info("=" * 80)

    # Initialize LLM client
    logger.info("=" * 80)
    logger.info("INITIALIZING LLM CLIENT")
    logger.info("=" * 80)

    # Try to load from environment, fallback to Ollama
    try:
        llm_client = LLMClient.from_env()
    except Exception as e:
        logger.warning("Could not load from env: %s", e)
        logger.info("Using default: ollama/llama2")
        llm_client = LLMClient(model="ollama/llama2")

    logger.info("=" * 80)

    # Create answer generator
    answer_generator = AnswerGenerator(
        llm_client=llm_client, max_context_chunks=5, include_metadata=True
    )

    # Sample queries
    queries = [
        "What is the effect of silicon content on magnetic properties of steel?",
        "What are the annealing conditions for grain-oriented electrical steel?",
        "How does chromium affect the core loss in electrical steel?",
    ]

    logger.info("=" * 80)
    logger.info("AVAILABLE QUERIES")
    logger.info("=" * 80)
    for i, q in enumerate(queries, 1):
        logger.info("%d. %s", i, q)
    logger.info("=" * 80)

    # Run demo with first query
    query = queries[0]
    logger.info("Running demo with query: %s", query)

    # Step 1: Hybrid Retrieval
    retrieved_chunks = demo_hybrid_retrieval(hybrid_retriever, query, top_k=10)

    # Step 2: Answer Generation
    demo_answer_generation(answer_generator, query, retrieved_chunks)

    # Cleanup
    retrievers["kg_store"].close()

    logger.info("=" * 80)
    logger.info("DEMO COMPLETE")
    logger.info("=" * 80)
    logger.info("To try other queries, modify the 'query' variable in the script")
    logger.info("To use Bedrock, set these environment variables in .env:")
    logger.info("  LLM_MODEL=bedrock/anthropic.claude-3-sonnet-20240229-v1:0")
    logger.info("  AWS_ACCESS_KEY_ID=your_key")
    logger.info("  AWS_SECRET_ACCESS_KEY=your_secret")
    logger.info("  AWS_REGION_NAME=us-east-1")
    logger.info("To use different Ollama models:")
    logger.info("  LLM_MODEL=ollama/mistral")
    logger.info("  LLM_MODEL=ollama/llama2")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
