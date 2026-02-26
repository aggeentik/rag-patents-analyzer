"""Knowledge graph-based retrieval."""

import logging
import os

from sentence_transformers import SentenceTransformer

from src.extraction.entity_extractor import EntityExtractor
from src.knowledge_graph.schema import PatentChunk
from src.knowledge_graph.store import KnowledgeGraphStore
from src.knowledge_graph.traversal import KnowledgeGraphTraversal

logger = logging.getLogger(__name__)

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"


class GraphRetriever:
    """Knowledge graph-based retrieval using entity extraction and traversal."""

    def __init__(
        self,
        kg_store: KnowledgeGraphStore,
        max_hops: int = 2,
        score_decay: float = 0.5,
        use_semantic_entity_search: bool | None = None,
    ):
        """
        Initialize graph retriever.

        Args:
            kg_store: Knowledge graph store instance
            max_hops: Maximum number of hops for graph traversal
            score_decay: Score decay factor per hop distance (0-1)
            use_semantic_entity_search: Use cosine-similarity entity lookup instead of
                exact/pattern matching. Reads GRAPH_SEMANTIC_ENTITY_SEARCH env var when
                None (default: true).
        """
        self.kg_store = kg_store
        self.max_hops = max_hops
        self.score_decay = score_decay

        if use_semantic_entity_search is None:
            use_semantic_entity_search = os.getenv(
                "GRAPH_SEMANTIC_ENTITY_SEARCH", "false"
            ).lower() in ("true", "1", "yes")
        self.use_semantic_entity_search = use_semantic_entity_search
        logger.info(
            "Graph retriever: semantic entity search %s",
            "enabled" if use_semantic_entity_search else "disabled (set GRAPH_SEMANTIC_ENTITY_SEARCH=true to enable)",
        )

        self.embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        self.traversal = KnowledgeGraphTraversal(kg_store, embedding_model=self.embedding_model)
        self.entity_extractor = EntityExtractor()
        self.chunks_by_id: dict[str, dict] = {}

    def build_index(self, chunks: list[dict]):
        """Build chunk mapping and graph structure."""
        logger.info("Building graph retriever for %d chunks...", len(chunks))
        self.chunks_by_id = {c["chunk_id"]: c for c in chunks}

        # Build NetworkX graph for traversal
        logger.debug("Building NetworkX graph for traversal...")
        self.traversal.build_networkx_graph()
        logger.info("Graph retriever ready")

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
            logger.debug("No entities found in query, returning empty results")
            return []

        display_entities = entity_names[:5]
        suffix = "..." if len(entity_names) > 5 else ""
        logger.debug("Extracted query entities: %s%s", display_entities, suffix)

        # Use traversal to find related chunks
        chunk_scores: dict[str, float] = {}
        _seed_id_seen: set[str] = set()  # entity IDs — skip duplicate BFS traversals

        for entity_name in entity_names:
            # Find matching entities in KG
            if self.use_semantic_entity_search:
                # Returns list[tuple[dict, float]] — unpack to entity dicts only
                matching_entities = [
                    entity
                    for entity, _score in self.kg_store.find_entities_semantic(
                        self.embedding_model.encode(entity_name)
                    )
                ]
            else:
                matching_entities = self.kg_store.find_entities(entity_name)

            for entity in matching_entities:
                eid = entity["id"]

                # Score chunks containing this entity directly (highest score)
                for chunk_id in entity["chunk_ids"]:
                    chunk_scores[chunk_id] = chunk_scores.get(chunk_id, 0) + 1.0

                # Traverse graph to find related entities (skip if already traversed from this node)
                if eid not in _seed_id_seen:
                    _seed_id_seen.add(eid)
                    related = self.traversal._bfs_traverse(entity["id"], self.max_hops)

                    for rel_entity_id, distance in related:
                        rel_chunks = self.kg_store.get_chunks_for_entity(rel_entity_id)
                        for chunk_id in rel_chunks:
                            # Score decreases exponentially with distance
                            score = self.score_decay**distance
                            chunk_scores[chunk_id] = chunk_scores.get(chunk_id, 0) + score

        # Sort by score and return top-k
        ranked_chunk_ids = sorted(chunk_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

        results = []
        for rank, (chunk_id, score) in enumerate(ranked_chunk_ids, 1):
            if chunk_id in self.chunks_by_id:
                chunk = self.chunks_by_id[chunk_id].copy()
                chunk["graph_score"] = float(score)
                chunk["graph_rank"] = rank
                results.append(chunk)

        logger.debug("Graph retrieval found %d chunks", len(results))
        return results

    def save(self, path: str):
        """Graph retriever doesn't need separate persistence (uses KG store)."""
        logger.debug("Graph retriever state saved (using KG store)")

    @classmethod
    def load(
        cls,
        path: str,
        chunks: list[dict],
        kg_store: KnowledgeGraphStore,
        max_hops: int = 2,
        score_decay: float = 0.5,
        use_semantic_entity_search: bool | None = None,
    ) -> "GraphRetriever":
        """Load graph retriever (rebuilds index from chunks)."""
        retriever = cls(kg_store, max_hops, score_decay, use_semantic_entity_search)
        retriever.build_index(chunks)
        return retriever
