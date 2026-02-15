"""SQLite storage for knowledge graph."""

import json
import sqlite3
from typing import Any

import numpy as np


class KnowledgeGraphStore:
    """SQLite storage for knowledge graph."""

    SCHEMA = """
    -- Entities table
    CREATE TABLE IF NOT EXISTS entities (
        id TEXT PRIMARY KEY,
        type TEXT NOT NULL,
        name TEXT NOT NULL,
        properties TEXT,  -- JSON
        patent_id TEXT NOT NULL,
        chunk_ids TEXT    -- JSON array
    );

    -- Relationships table
    CREATE TABLE IF NOT EXISTS relationships (
        id TEXT PRIMARY KEY,
        type TEXT NOT NULL,
        source_id TEXT NOT NULL,
        target_id TEXT NOT NULL,
        properties TEXT,  -- JSON
        patent_id TEXT NOT NULL,
        chunk_id TEXT
    );

    -- Chunk-Entity index for fast lookup
    CREATE TABLE IF NOT EXISTS chunk_entities (
        chunk_id TEXT,
        entity_id TEXT,
        PRIMARY KEY (chunk_id, entity_id)
    );

    -- Entity embeddings for semantic matching
    CREATE TABLE IF NOT EXISTS entity_embeddings (
        entity_id TEXT PRIMARY KEY,
        embedding BLOB NOT NULL
    );

    -- Indices
    CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);
    CREATE INDEX IF NOT EXISTS idx_entities_patent ON entities(patent_id);
    CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name);
    CREATE INDEX IF NOT EXISTS idx_rel_source ON relationships(source_id);
    CREATE INDEX IF NOT EXISTS idx_rel_target ON relationships(target_id);
    CREATE INDEX IF NOT EXISTS idx_rel_type ON relationships(type);
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn: sqlite3.Connection | None = None

    def connect(self, check_same_thread: bool = True):
        """Connect to database and create schema."""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=check_same_thread)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(self.SCHEMA)
        self.conn.commit()

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

    def save_entity(self, entity: dict[str, Any]) -> None:
        """Save or update an entity."""
        assert self.conn is not None, "Database connection not established"
        self.conn.execute(
            """
            INSERT OR REPLACE INTO entities
            (id, type, name, properties, patent_id, chunk_ids)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                entity["id"],
                entity["type"],
                entity["name"],
                json.dumps(entity["properties"]),
                entity["patent_id"],
                json.dumps(entity["chunk_ids"]),
            ),
        )

        # Update chunk_entities index
        for chunk_id in entity["chunk_ids"]:
            self.conn.execute(
                """
                INSERT OR IGNORE INTO chunk_entities (chunk_id, entity_id)
                VALUES (?, ?)
            """,
                (chunk_id, entity["id"]),
            )

        self.conn.commit()

    def save_relationship(self, rel: dict):
        """Save a relationship."""
        self.conn.execute(
            """
            INSERT OR REPLACE INTO relationships
            (id, type, source_id, target_id, properties, patent_id, chunk_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                rel["id"],
                rel["type"],
                rel["source_id"],
                rel["target_id"],
                json.dumps(rel["properties"]),
                rel["patent_id"],
                rel["chunk_id"],
            ),
        )
        self.conn.commit()

    def get_entities_by_chunk(self, chunk_id: str) -> list[dict]:
        """Get all entities in a chunk."""
        cursor = self.conn.execute(
            """
            SELECT e.* FROM entities e
            JOIN chunk_entities ce ON e.id = ce.entity_id
            WHERE ce.chunk_id = ?
        """,
            (chunk_id,),
        )
        return [self._row_to_entity(row) for row in cursor.fetchall()]

    def get_entities_by_type(self, entity_type: str) -> list[dict]:
        """Get all entities of a type."""
        cursor = self.conn.execute("SELECT * FROM entities WHERE type = ?", (entity_type,))
        return [self._row_to_entity(row) for row in cursor.fetchall()]

    def get_related_entities(
        self, entity_id: str, relationship_type: str | None = None
    ) -> list[dict]:
        """Get entities related to given entity."""
        if relationship_type:
            cursor = self.conn.execute(
                """
                SELECT e.* FROM entities e
                JOIN relationships r ON e.id = r.target_id
                WHERE r.source_id = ? AND r.type = ?
            """,
                (entity_id, relationship_type),
            )
        else:
            cursor = self.conn.execute(
                """
                SELECT e.* FROM entities e
                JOIN relationships r ON e.id = r.target_id
                WHERE r.source_id = ?
            """,
                (entity_id,),
            )
        return [self._row_to_entity(row) for row in cursor.fetchall()]

    def find_entities(self, name_pattern: str, entity_type: str | None = None) -> list[dict]:
        """Search entities by name pattern."""
        if entity_type:
            cursor = self.conn.execute(
                """
                SELECT * FROM entities
                WHERE name LIKE ? AND type = ?
            """,
                (f"%{name_pattern}%", entity_type),
            )
        else:
            cursor = self.conn.execute(
                "SELECT * FROM entities WHERE name LIKE ?", (f"%{name_pattern}%",)
            )
        return [self._row_to_entity(row) for row in cursor.fetchall()]

    def get_chunks_for_entity(self, entity_id: str) -> list[str]:
        """Get chunk IDs where entity appears."""
        cursor = self.conn.execute("SELECT chunk_ids FROM entities WHERE id = ?", (entity_id,))
        row = cursor.fetchone()
        if row:
            return json.loads(row["chunk_ids"])
        return []

    def save_entity_embedding(self, entity_id: str, embedding: np.ndarray) -> None:
        """Save embedding vector for an entity."""
        assert self.conn is not None, "Database connection not established"
        self.conn.execute(
            "INSERT OR REPLACE INTO entity_embeddings (entity_id, embedding) VALUES (?, ?)",
            (entity_id, embedding.astype(np.float32).tobytes()),
        )
        self.conn.commit()

    def save_entity_embeddings_batch(self, embeddings: list[tuple[str, np.ndarray]]) -> None:
        """Save multiple entity embeddings in a single transaction."""
        assert self.conn is not None, "Database connection not established"
        self.conn.executemany(
            "INSERT OR REPLACE INTO entity_embeddings (entity_id, embedding) VALUES (?, ?)",
            [(eid, emb.astype(np.float32).tobytes()) for eid, emb in embeddings],
        )
        self.conn.commit()

    def get_all_entity_embeddings(self) -> list[tuple[str, np.ndarray]]:
        """Load all entity embeddings for in-memory search."""
        assert self.conn is not None, "Database connection not established"
        cursor = self.conn.execute("SELECT entity_id, embedding FROM entity_embeddings")
        results = []
        for row in cursor.fetchall():
            embedding = np.frombuffer(row["embedding"], dtype=np.float32)
            results.append((row["entity_id"], embedding))
        return results

    def find_entities_semantic(
        self, query_embedding: np.ndarray, top_k: int = 5, threshold: float = 0.3
    ) -> list[tuple[dict, float]]:
        """Find entities by cosine similarity to query embedding.

        Returns list of (entity_dict, similarity_score) pairs above threshold.
        """
        all_embeddings = self.get_all_entity_embeddings()
        if not all_embeddings:
            return []

        entity_ids = [eid for eid, _ in all_embeddings]
        emb_matrix = np.stack([emb for _, emb in all_embeddings])

        # Cosine similarity
        query_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-10)
        emb_norms = emb_matrix / (np.linalg.norm(emb_matrix, axis=1, keepdims=True) + 1e-10)
        similarities = emb_norms @ query_norm

        # Filter and rank
        results = []
        for idx in np.argsort(similarities)[::-1][:top_k]:
            score = float(similarities[idx])
            if score < threshold:
                break
            entity = self._get_entity_by_id(entity_ids[idx])
            if entity:
                results.append((entity, score))

        return results

    def _get_entity_by_id(self, entity_id: str) -> dict | None:
        """Get a single entity by ID."""
        assert self.conn is not None, "Database connection not established"
        cursor = self.conn.execute("SELECT * FROM entities WHERE id = ?", (entity_id,))
        row = cursor.fetchone()
        return self._row_to_entity(row) if row else None

    def _row_to_entity(self, row: sqlite3.Row) -> dict:
        """Convert database row to entity dict."""
        return {
            "id": row["id"],
            "type": row["type"],
            "name": row["name"],
            "properties": json.loads(row["properties"]) if row["properties"] else {},
            "patent_id": row["patent_id"],
            "chunk_ids": json.loads(row["chunk_ids"]) if row["chunk_ids"] else [],
        }
