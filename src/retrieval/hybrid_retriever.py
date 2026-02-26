"""Hybrid retrieval combining BM25, Semantic, and Graph retrievers using RRF."""

import logging
from typing import Protocol

logger = logging.getLogger(__name__)

# Fields managed by the fusion logic (not retriever-specific metadata)
_FUSION_FIELDS = {
    "bm25_rank",
    "bm25_score",
    "semantic_rank",
    "semantic_score",
    "graph_rank",
    "graph_score",
    "rrf_score",
    "score_breakdown",
    "final_rank",
    "rerank_score",
}


class Retriever(Protocol):
    """Protocol for individual retrievers (BM25, Semantic, Graph)."""

    def search(self, query: str, top_k: int = 10) -> list[dict]:
        """Return ranked chunks matching the query."""
        ...


class Reranker(Protocol):
    """Protocol for cross-encoder rerankers."""

    def score(self, query: str, chunks: list[dict]) -> list[float]:
        """Return a relevance score for each chunk against the query."""
        ...


# Short labels for RRF score breakdown display
_DISPLAY_LABELS = {"bm25": "BM25", "semantic": "Sem", "graph": "Graph"}


class HybridRetriever:
    """
    Hybrid retrieval using Reciprocal Rank Fusion (RRF).

    Combines results from multiple retrievers using the RRF formula:
        RRF_score(chunk) = sum(weight_i / (k + rank_i))

    where k is a constant (typically 60) and rank_i is the rank from retriever i.

    Supports an optional cross-encoder reranker for "Wide Retrieval, Narrow Generation":
    fetch a large candidate pool, fuse with RRF, then rerank with a cross-encoder
    before returning the final top_k results.
    """

    def __init__(
        self,
        bm25_retriever=None,
        semantic_retriever=None,
        graph_retriever=None,
        weights: dict[str, float] | None = None,
        rrf_k: int = 60,
        reranker: Reranker | None = None,
    ):
        """
        Initialize hybrid retriever.

        Args:
            bm25_retriever: BM25 retriever instance
            semantic_retriever: Semantic retriever instance
            graph_retriever: Graph retriever instance
            weights: Weight for each retriever {"bm25": 1.0, "semantic": 1.0, "graph": 1.2}
            rrf_k: RRF constant (typically 60)
            reranker: Optional cross-encoder reranker for post-fusion reranking
        """
        self.rrf_k = rrf_k
        self.reranker = reranker

        # Default weights: Graph gets a boost for highly specific entity hits
        self.weights = weights or {"bm25": 1.0, "semantic": 1.0, "graph": 1.2}

        # Map retriever names to instances (only those provided)
        self._retrievers: dict[str, Retriever] = {}
        if bm25_retriever:
            self._retrievers["bm25"] = bm25_retriever
        if semantic_retriever:
            self._retrievers["semantic"] = semantic_retriever
        if graph_retriever:
            self._retrievers["graph"] = graph_retriever

        logger.info(
            "Hybrid retriever initialized with: %s (reranker: %s)",
            ", ".join(self._retrievers),
            "enabled" if reranker else "disabled",
        )

    def _merge_result(self, all_results: dict, result: dict, retriever: str):
        """Merge a retriever result into the combined results dict, preserving all metadata."""
        chunk_id = result["chunk_id"]
        if chunk_id not in all_results:
            all_results[chunk_id] = result.copy()
        else:
            # Preserve any retriever-specific metadata fields (e.g. hop distances,
            # relationship types) that aren't already present in the merged entry.
            existing = all_results[chunk_id]
            for key, value in result.items():
                if key not in existing and key not in _FUSION_FIELDS:
                    existing[key] = value

        # Always set the retriever-specific rank/score fields
        all_results[chunk_id][f"{retriever}_rank"] = result.get(f"{retriever}_rank", 0)
        all_results[chunk_id][f"{retriever}_score"] = result.get(f"{retriever}_score", 0)

    def search(
        self,
        query: str,
        top_k: int = 10,
        retriever_top_k: int | None = None,
        rerank_top_n: int = 20,
    ) -> list[dict]:
        """
        Search using hybrid retrieval with RRF fusion and optional reranking.

        Uses a "Wide Retrieval, Narrow Generation" strategy:
        1. Fetch a deep pool of candidates from each retriever.
        2. Fuse with RRF to get an initial ranking.
        3. Optionally rerank the top candidates with a cross-encoder.
        4. Return the final top_k results.

        Args:
            query: Search query
            top_k: Number of final results to return
            retriever_top_k: Number of results from each retriever
                           (default: 50 for deep candidate pool)
            rerank_top_n: Number of RRF results to pass to the reranker (default: 20)

        Returns:
            List of chunks with RRF scores and detailed scoring breakdown
        """
        if retriever_top_k is None:
            retriever_top_k = 50

        logger.info("Hybrid retrieval query: %s", query)

        # Collect results from all active retrievers
        all_results: dict[str, dict] = {}

        for name, retriever in self._retrievers.items():
            logger.debug("Running %s retrieval...", name)
            results = retriever.search(query, top_k=retriever_top_k)
            logger.debug("%s retrieved %d chunks", name, len(results))
            for result in results:
                self._merge_result(all_results, result, name)

        # Calculate RRF scores
        logger.debug("Calculating RRF fusion scores...")
        for chunk in all_results.values():
            rrf_score = 0.0
            score_breakdown = []

            for name in self._retrievers:
                rank = chunk.get(f"{name}_rank", 0)
                if rank > 0:
                    contribution = 1 / (self.rrf_k + rank)
                    rrf_score += self.weights[name] * contribution
                    score_breakdown.append(f"{_DISPLAY_LABELS[name]}: {contribution:.4f}")

            chunk["rrf_score"] = rrf_score
            chunk["score_breakdown"] = " + ".join(score_breakdown)

        # Sort by RRF score
        ranked_results = sorted(all_results.values(), key=lambda x: x["rrf_score"], reverse=True)

        logger.info(
            "RRF fusion: %d unique chunks from pool",
            len(all_results),
        )

        # Rerank with cross-encoder if available
        if self.reranker:
            candidates = ranked_results[:rerank_top_n]
            logger.debug("Reranking top %d RRF results with cross-encoder...", len(candidates))
            scores = self.reranker.score(query, candidates)
            for chunk, rerank_score in zip(candidates, scores):
                chunk["rerank_score"] = rerank_score
            ranked_results = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)
            logger.info("Reranker applied: top %d -> final %d", rerank_top_n, top_k)

        # Trim to final top_k
        ranked_results = ranked_results[:top_k]

        # Add final ranks
        for rank, result in enumerate(ranked_results, 1):
            result["final_rank"] = rank

        logger.info("Returning %d results", len(ranked_results))

        return ranked_results

    def set_weights(self, weights: dict[str, float]):
        """Update retriever weights dynamically."""
        self.weights.update(weights)
        logger.info("Updated weights: %s", self.weights)

    def get_retriever_stats(self, results: list[dict]) -> dict:
        """
        Analyze which retrievers contributed to the results.

        Returns statistics about retriever performance.
        """
        stats = {
            "total_results": len(results),
            "bm25_hits": 0,
            "semantic_hits": 0,
            "graph_hits": 0,
            "multi_retriever_hits": 0,
        }

        for result in results:
            hit_count = 0
            if result.get("bm25_rank", 0) > 0:
                stats["bm25_hits"] += 1
                hit_count += 1
            if result.get("semantic_rank", 0) > 0:
                stats["semantic_hits"] += 1
                hit_count += 1
            if result.get("graph_rank", 0) > 0:
                stats["graph_hits"] += 1
                hit_count += 1
            if hit_count > 1:
                stats["multi_retriever_hits"] += 1

        return stats
