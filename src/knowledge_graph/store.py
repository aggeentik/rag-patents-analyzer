"""SQLite storage for knowledge graph."""

import sqlite3
import json
from pathlib import Path
from typing import Optional


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
        self.conn = None

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

    def save_entity(self, entity: dict):
        """Save or update an entity."""
        self.conn.execute("""
            INSERT OR REPLACE INTO entities
            (id, type, name, properties, patent_id, chunk_ids)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            entity["id"],
            entity["type"],
            entity["name"],
            json.dumps(entity["properties"]),
            entity["patent_id"],
            json.dumps(entity["chunk_ids"]),
        ))

        # Update chunk_entities index
        for chunk_id in entity["chunk_ids"]:
            self.conn.execute("""
                INSERT OR IGNORE INTO chunk_entities (chunk_id, entity_id)
                VALUES (?, ?)
            """, (chunk_id, entity["id"]))

        self.conn.commit()

    def save_relationship(self, rel: dict):
        """Save a relationship."""
        self.conn.execute("""
            INSERT OR REPLACE INTO relationships
            (id, type, source_id, target_id, properties, patent_id, chunk_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            rel["id"],
            rel["type"],
            rel["source_id"],
            rel["target_id"],
            json.dumps(rel["properties"]),
            rel["patent_id"],
            rel["chunk_id"],
        ))
        self.conn.commit()

    def get_entities_by_chunk(self, chunk_id: str) -> list[dict]:
        """Get all entities in a chunk."""
        cursor = self.conn.execute("""
            SELECT e.* FROM entities e
            JOIN chunk_entities ce ON e.id = ce.entity_id
            WHERE ce.chunk_id = ?
        """, (chunk_id,))
        return [self._row_to_entity(row) for row in cursor.fetchall()]

    def get_entities_by_type(self, entity_type: str) -> list[dict]:
        """Get all entities of a type."""
        cursor = self.conn.execute(
            "SELECT * FROM entities WHERE type = ?", (entity_type,)
        )
        return [self._row_to_entity(row) for row in cursor.fetchall()]

    def get_related_entities(
        self,
        entity_id: str,
        relationship_type: Optional[str] = None
    ) -> list[dict]:
        """Get entities related to given entity."""
        if relationship_type:
            cursor = self.conn.execute("""
                SELECT e.* FROM entities e
                JOIN relationships r ON e.id = r.target_id
                WHERE r.source_id = ? AND r.type = ?
            """, (entity_id, relationship_type))
        else:
            cursor = self.conn.execute("""
                SELECT e.* FROM entities e
                JOIN relationships r ON e.id = r.target_id
                WHERE r.source_id = ?
            """, (entity_id,))
        return [self._row_to_entity(row) for row in cursor.fetchall()]

    def find_entities(
        self,
        name_pattern: str,
        entity_type: Optional[str] = None
    ) -> list[dict]:
        """Search entities by name pattern."""
        if entity_type:
            cursor = self.conn.execute("""
                SELECT * FROM entities
                WHERE name LIKE ? AND type = ?
            """, (f"%{name_pattern}%", entity_type))
        else:
            cursor = self.conn.execute(
                "SELECT * FROM entities WHERE name LIKE ?",
                (f"%{name_pattern}%",)
            )
        return [self._row_to_entity(row) for row in cursor.fetchall()]

    def get_chunks_for_entity(self, entity_id: str) -> list[str]:
        """Get chunk IDs where entity appears."""
        cursor = self.conn.execute(
            "SELECT chunk_ids FROM entities WHERE id = ?", (entity_id,)
        )
        row = cursor.fetchone()
        if row:
            return json.loads(row["chunk_ids"])
        return []

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
