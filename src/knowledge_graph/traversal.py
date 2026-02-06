"""Graph traversal and query operations."""

from typing import Optional
import networkx as nx
from src.knowledge_graph.store import KnowledgeGraphStore


class KnowledgeGraphTraversal:
    """Graph traversal and query operations."""

    def __init__(self, store: KnowledgeGraphStore):
        self.store = store
        self.graph = None

    def build_networkx_graph(self):
        """Build NetworkX graph for traversal algorithms."""
        self.graph = nx.DiGraph()

        # Add all entities as nodes
        cursor = self.store.conn.execute("SELECT * FROM entities")
        for row in cursor.fetchall():
            self.graph.add_node(
                row["id"],
                type=row["type"],
                name=row["name"],
            )

        # Add all relationships as edges
        cursor = self.store.conn.execute("SELECT * FROM relationships")
        for row in cursor.fetchall():
            self.graph.add_edge(
                row["source_id"],
                row["target_id"],
                type=row["type"],
            )

    def find_related_chunks(
        self,
        query_entities: list[str],
        max_hops: int = 2,
        max_chunks: int = 10
    ) -> list[str]:
        """
        Find chunks related to query entities via graph traversal.

        Algorithm:
        1. Start from query entity nodes
        2. BFS/DFS up to max_hops
        3. Collect all chunks containing traversed entities
        4. Rank by number of connections
        """
        visited_entities = set()
        chunk_scores = {}

        # BFS from each query entity
        for entity_name in query_entities:
            # Find matching entities
            entities = self.store.find_entities(entity_name)

            for entity in entities:
                # Get chunks for this entity
                chunks = entity["chunk_ids"]
                for chunk_id in chunks:
                    chunk_scores[chunk_id] = chunk_scores.get(chunk_id, 0) + 2  # Direct match

                # Traverse relationships
                related = self._bfs_traverse(entity["id"], max_hops)
                for rel_entity_id, distance in related:
                    rel_chunks = self.store.get_chunks_for_entity(rel_entity_id)
                    for chunk_id in rel_chunks:
                        # Score decreases with distance
                        score = 1 / (distance + 1)
                        chunk_scores[chunk_id] = chunk_scores.get(chunk_id, 0) + score

        # Sort by score
        ranked = sorted(chunk_scores.items(), key=lambda x: x[1], reverse=True)
        return [chunk_id for chunk_id, score in ranked[:max_chunks]]

    def _bfs_traverse(
        self,
        start_entity_id: str,
        max_hops: int
    ) -> list[tuple[str, int]]:
        """BFS traverse from entity, return (entity_id, distance) pairs."""
        if not self.graph or start_entity_id not in self.graph:
            return []

        visited = set()
        result = []
        queue = [(start_entity_id, 0)]

        while queue:
            entity_id, distance = queue.pop(0)

            if entity_id in visited or distance > max_hops:
                continue

            visited.add(entity_id)
            if distance > 0:  # Don't include start node
                result.append((entity_id, distance))

            # Add neighbors
            for neighbor in self.graph.neighbors(entity_id):
                if neighbor not in visited:
                    queue.append((neighbor, distance + 1))

        return result

    def get_entity_context(self, entity_id: str) -> dict:
        """Get full context for an entity including relationships."""
        entity = self.store.conn.execute(
            "SELECT * FROM entities WHERE id = ?", (entity_id,)
        ).fetchone()

        if not entity:
            return {}

        # Get outgoing relationships
        outgoing = self.store.conn.execute("""
            SELECT r.*, e.name as target_name, e.type as target_type
            FROM relationships r
            JOIN entities e ON r.target_id = e.id
            WHERE r.source_id = ?
        """, (entity_id,)).fetchall()

        # Get incoming relationships
        incoming = self.store.conn.execute("""
            SELECT r.*, e.name as source_name, e.type as source_type
            FROM relationships r
            JOIN entities e ON r.source_id = e.id
            WHERE r.target_id = ?
        """, (entity_id,)).fetchall()

        return {
            "entity": self.store._row_to_entity(entity),
            "outgoing": [dict(row) for row in outgoing],
            "incoming": [dict(row) for row in incoming],
        }
