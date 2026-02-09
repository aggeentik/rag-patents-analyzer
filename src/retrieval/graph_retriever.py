"""Knowledge graph-based retrieval."""

from typing import Optional
from src.knowledge_graph.schema import PatentChunk
from src.knowledge_graph.store import KnowledgeGraphStore
from src.knowledge_graph.traversal import KnowledgeGraphTraversal
from src.extraction.entity_extractor import EntityExtractor


class GraphRetriever:
    """Knowledge graph-based retrieval using entity extraction and traversal."""

    def __init__(
        self,
        kg_store: KnowledgeGraphStore,
        max_hops: int = 2,
        score_decay: float = 0.5
    ):
        """
        Initialize graph retriever.

        Args:
            kg_store: Knowledge graph store instance
            max_hops: Maximum number of hops for graph traversal
            score_decay: Score decay factor per hop distance (0-1)
        """
        self.kg_store = kg_store
        self.max_hops = max_hops
        self.score_decay = score_decay
        self.traversal = KnowledgeGraphTraversal(kg_store)
        self.entity_extractor = EntityExtractor()
        self.chunks_by_id = {}

    def build_index(self, chunks: list[dict]):
        """Build chunk mapping and graph structure."""
        print(f"Building graph retriever for {len(chunks)} chunks...")
        self.chunks_by_id = {c["chunk_id"]: c for c in chunks}

        # Build NetworkX graph for traversal
        print("  Building NetworkX graph for traversal...")
        self.traversal.build_networkx_graph()
        print("✓ Graph retriever ready")

    def search(self, query: str, top_k: int = 10) -> list[dict]:
        """
        Search using knowledge graph traversal.

        Algorithm:
        1. Extract entities from query
        2. Find matching entities in KG
        3. Traverse graph (BFS) to find related entities
        4. Collect chunks containing traversed entities
        5. Score chunks by entity relevance and distance
        """
        # Extract entities from query using a PatentChunk wrapper
        query_chunk = PatentChunk(
            content=query,
            chunk_id="query",
            patent_id="query",
        )
        query_entities = self.entity_extractor.extract_entities(query_chunk)
        entity_names = [e.name for e in query_entities]  # Entity objects, not dicts

        if not entity_names:
            print("  No entities found in query, returning empty results")
            return []

        print(f"  Extracted query entities: {entity_names[:5]}{'...' if len(entity_names) > 5 else ''}")

        # Use traversal to find related chunks
        chunk_scores = {}

        for entity_name in entity_names:
            # Find matching entities in KG
            matching_entities = self.kg_store.find_entities(entity_name)

            for entity in matching_entities:
                # Score chunks containing this entity directly (highest score)
                for chunk_id in entity["chunk_ids"]:
                    chunk_scores[chunk_id] = chunk_scores.get(chunk_id, 0) + 1.0

                # Traverse graph to find related entities
                related = self.traversal._bfs_traverse(entity["id"], self.max_hops)

                for rel_entity_id, distance in related:
                    rel_chunks = self.kg_store.get_chunks_for_entity(rel_entity_id)
                    for chunk_id in rel_chunks:
                        # Score decreases exponentially with distance
                        score = self.score_decay ** distance
                        chunk_scores[chunk_id] = chunk_scores.get(chunk_id, 0) + score

        # Sort by score and return top-k
        ranked_chunk_ids = sorted(
            chunk_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )[:top_k]

        results = []
        for rank, (chunk_id, score) in enumerate(ranked_chunk_ids, 1):
            if chunk_id in self.chunks_by_id:
                chunk = self.chunks_by_id[chunk_id].copy()
                chunk["graph_score"] = float(score)
                chunk["graph_rank"] = rank
                results.append(chunk)

        print(f"  Graph retrieval found {len(results)} chunks")
        return results

    def save(self, path: str):
        """Graph retriever doesn't need separate persistence (uses KG store)."""
        print(f"✓ Graph retriever state saved (using KG store)")

    @classmethod
    def load(
        cls,
        path: str,
        chunks: list[dict],
        kg_store: KnowledgeGraphStore,
        max_hops: int = 2,
        score_decay: float = 0.5
    ) -> "GraphRetriever":
        """Load graph retriever (rebuilds index from chunks)."""
        retriever = cls(kg_store, max_hops, score_decay)
        retriever.build_index(chunks)
        return retriever
