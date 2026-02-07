"""Hybrid retrieval combining BM25, Semantic, and Graph retrievers using RRF."""

from typing import Optional
from collections import defaultdict


class HybridRetriever:
    """
    Hybrid retrieval using Reciprocal Rank Fusion (RRF).

    Combines results from multiple retrievers using the RRF formula:
        RRF_score(chunk) = sum(1 / (k + rank_i))

    where k is a constant (typically 60) and rank_i is the rank from retriever i.
    """

    def __init__(
        self,
        bm25_retriever=None,
        semantic_retriever=None,
        graph_retriever=None,
        weights: Optional[dict[str, float]] = None,
        rrf_k: int = 60
    ):
        """
        Initialize hybrid retriever.

        Args:
            bm25_retriever: BM25 retriever instance
            semantic_retriever: Semantic retriever instance
            graph_retriever: Graph retriever instance
            weights: Weight for each retriever {"bm25": 1.0, "semantic": 1.0, "graph": 0.5}
            rrf_k: RRF constant (typically 60)
        """
        self.bm25_retriever = bm25_retriever
        self.semantic_retriever = semantic_retriever
        self.graph_retriever = graph_retriever
        self.rrf_k = rrf_k

        # Default weights: BM25 and Semantic get equal weight, Graph gets less
        self.weights = weights or {
            "bm25": 1.0,
            "semantic": 1.0,
            "graph": 0.5
        }

        # Track which retrievers are available
        self.active_retrievers = []
        if bm25_retriever:
            self.active_retrievers.append("bm25")
        if semantic_retriever:
            self.active_retrievers.append("semantic")
        if graph_retriever:
            self.active_retrievers.append("graph")

        print(f"Hybrid retriever initialized with: {', '.join(self.active_retrievers)}")

    def search(
        self,
        query: str,
        top_k: int = 10,
        retriever_top_k: Optional[int] = None
    ) -> list[dict]:
        """
        Search using hybrid retrieval with RRF fusion.

        Args:
            query: Search query
            top_k: Number of final results to return
            retriever_top_k: Number of results to retrieve from each retriever
                           (default: 3x top_k to ensure good coverage)

        Returns:
            List of chunks with RRF scores and detailed scoring breakdown
        """
        if retriever_top_k is None:
            retriever_top_k = top_k * 3

        print(f"\n{'='*80}")
        print(f"Hybrid Retrieval Query: {query}")
        print(f"{'='*80}")

        # Collect results from all retrievers
        all_results = {}

        # BM25 retrieval (keyword-based)
        if self.bm25_retriever:
            print("\n[BM25 Retrieval]")
            bm25_results = self.bm25_retriever.search(query, top_k=retriever_top_k)
            print(f"  Retrieved {len(bm25_results)} chunks")
            for result in bm25_results:
                chunk_id = result["chunk_id"]
                if chunk_id not in all_results:
                    all_results[chunk_id] = result.copy()
                all_results[chunk_id]["bm25_rank"] = result.get("bm25_rank", 0)
                all_results[chunk_id]["bm25_score"] = result.get("bm25_score", 0)

        # Semantic retrieval (dense vectors)
        if self.semantic_retriever:
            print("\n[Semantic Retrieval]")
            semantic_results = self.semantic_retriever.search(query, top_k=retriever_top_k)
            print(f"  Retrieved {len(semantic_results)} chunks")
            for result in semantic_results:
                chunk_id = result["chunk_id"]
                if chunk_id not in all_results:
                    all_results[chunk_id] = result.copy()
                all_results[chunk_id]["semantic_rank"] = result.get("semantic_rank", 0)
                all_results[chunk_id]["semantic_score"] = result.get("semantic_score", 0)

        # Graph retrieval (knowledge graph traversal)
        if self.graph_retriever:
            print("\n[Graph Retrieval]")
            graph_results = self.graph_retriever.search(query, top_k=retriever_top_k)
            print(f"  Retrieved {len(graph_results)} chunks")
            for result in graph_results:
                chunk_id = result["chunk_id"]
                if chunk_id not in all_results:
                    all_results[chunk_id] = result.copy()
                all_results[chunk_id]["graph_rank"] = result.get("graph_rank", 0)
                all_results[chunk_id]["graph_score"] = result.get("graph_score", 0)

        # Calculate RRF scores
        print("\n[RRF Fusion]")
        for chunk_id, chunk in all_results.items():
            rrf_score = 0.0
            score_breakdown = []

            # BM25 contribution
            if "bm25_rank" in chunk and chunk["bm25_rank"] > 0:
                bm25_rrf = 1 / (self.rrf_k + chunk["bm25_rank"])
                rrf_score += self.weights["bm25"] * bm25_rrf
                score_breakdown.append(f"BM25: {bm25_rrf:.4f}")

            # Semantic contribution
            if "semantic_rank" in chunk and chunk["semantic_rank"] > 0:
                sem_rrf = 1 / (self.rrf_k + chunk["semantic_rank"])
                rrf_score += self.weights["semantic"] * sem_rrf
                score_breakdown.append(f"Sem: {sem_rrf:.4f}")

            # Graph contribution
            if "graph_rank" in chunk and chunk["graph_rank"] > 0:
                graph_rrf = 1 / (self.rrf_k + chunk["graph_rank"])
                rrf_score += self.weights["graph"] * graph_rrf
                score_breakdown.append(f"Graph: {graph_rrf:.4f}")

            chunk["rrf_score"] = rrf_score
            chunk["score_breakdown"] = " + ".join(score_breakdown)

        # Sort by RRF score and return top-k
        ranked_results = sorted(
            all_results.values(),
            key=lambda x: x["rrf_score"],
            reverse=True
        )[:top_k]

        # Add final ranks
        for rank, result in enumerate(ranked_results, 1):
            result["final_rank"] = rank

        print(f"  Fused {len(all_results)} unique chunks → Top {len(ranked_results)}")
        print(f"{'='*80}\n")

        return ranked_results

    def set_weights(self, weights: dict[str, float]):
        """Update retriever weights dynamically."""
        self.weights.update(weights)
        print(f"Updated weights: {self.weights}")

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
            "multi_retriever_hits": 0
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
