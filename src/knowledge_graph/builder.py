"""Build knowledge graph from extracted entities."""

import re

from src.knowledge_graph.schema import Entity, EntityType, Relationship, RelationType


class KnowledgeGraphBuilder:
    """Build knowledge graph from extracted entities."""

    _TABLE_MENTION_RE = re.compile(r"Table\s*(\d+)", re.IGNORECASE)

    def __init__(self):
        self.entities: dict[str, Entity] = {}
        self.relationships: list[Relationship] = []
        self._relationship_ids: set[str] = set()
        self._table_chunks: dict[str, str] = {}  # "Table 1" -> chunk_id

    def add_entities(self, entities: list[Entity]):
        """Add entities, merging duplicates."""
        for entity in entities:
            if entity.id in self.entities:
                # Merge chunk_ids
                existing = self.entities[entity.id]
                existing.chunk_ids = list(set(existing.chunk_ids + entity.chunk_ids))
            else:
                self.entities[entity.id] = entity

    def build_relationships(self, chunks: list):
        """
        Infer relationships from co-occurrence and patterns.

        Relationship types:
        - AFFECTS: Element mentioned with property in same chunk
        - REQUIRES: Process mentioned with parameter
        - MEASURED_IN: Property with value in table chunk
        - REFERENCES: Chunk references table/formula
        - MENTIONS: Text chunk mentions a table by name -> table chunk
        - DESCRIBED_IN: Entity appears in chunk
        """
        # Build a lookup: normalised label -> table chunk_id
        self._table_chunks.clear()
        for chunk in chunks:
            if chunk.chunk_type == "table":
                # Try to match "Table N" in table content (caption row)
                for m in self._TABLE_MENTION_RE.finditer(chunk.content):
                    label = f"Table {m.group(1)}"
                    self._table_chunks.setdefault(label, chunk.chunk_id)

        for chunk in chunks:
            chunk_entities = [e for e in self.entities.values() if chunk.chunk_id in e.chunk_ids]

            # DESCRIBED_IN: All entities → chunk
            for entity in chunk_entities:
                self._add_described_in(entity, chunk)

            # AFFECTS: Element + Property co-occurrence
            elements = [e for e in chunk_entities if e.type == EntityType.CHEMICAL_ELEMENT]
            properties = [e for e in chunk_entities if e.type == EntityType.PROPERTY]

            for element in elements:
                for prop in properties:
                    self._add_affects(element, prop, chunk)

            # REQUIRES: Process + Parameter co-occurrence
            processes = [e for e in chunk_entities if e.type == EntityType.PROCESS]

            for process in processes:
                if "temperature" in process.properties:
                    self._add_requires_temperature(process, chunk)

            # REFERENCES: Chunk → Table/Formula
            tables = [e for e in chunk_entities if e.type == EntityType.TABLE]
            formulas = [e for e in chunk_entities if e.type == EntityType.FORMULA]

            for table in tables:
                self._add_references(chunk, table)
            for formula in formulas:
                self._add_references(chunk, formula)

            # MENTIONS: Non-table chunk mentions "Table N" -> table chunk
            if chunk.chunk_type != "table":
                for m in self._TABLE_MENTION_RE.finditer(chunk.content):
                    label = f"Table {m.group(1)}"
                    target_id = self._table_chunks.get(label)
                    if target_id:
                        self._add_mentions(chunk, target_id)

            # MEASURED_IN: Property in table chunk
            if chunk.chunk_type == "table":
                for prop in properties:
                    self._add_measured_in(prop, chunk)

            # USED_FOR: Material + Application co-occurrence
            materials = [e for e in chunk_entities if e.type == EntityType.MATERIAL]
            applications = [e for e in chunk_entities if e.type == EntityType.APPLICATION]

            for material in materials:
                for application in applications:
                    self._add_used_for(material, application, chunk)

            # CITES: Patent reference found in chunk
            patent_refs = [e for e in chunk_entities if e.type == EntityType.PATENT_REFERENCE]
            for ref in patent_refs:
                self._add_cites(ref, chunk)

            # ADDRESSES_PROBLEM: Material or patent + Problem co-occurrence
            problems = [e for e in chunk_entities if e.type == EntityType.PROBLEM]
            for problem in problems:
                for material in materials:
                    self._add_addresses_problem(material, problem, chunk)
                # If no materials, link problem to the patent itself
                if not materials and chunk.patent_id:
                    self._add_addresses_problem_patent(chunk.patent_id, problem, chunk)

            # INVENTED_BY: Inventor entity in chunk
            inventors = [e for e in chunk_entities if e.type == EntityType.INVENTOR]
            for inventor in inventors:
                if chunk.patent_id:
                    self._add_invented_by(chunk.patent_id, inventor, chunk)

            # ASSIGNEE_OF: Assignee entity in chunk
            assignees = [e for e in chunk_entities if e.type == EntityType.ASSIGNEE]
            for assignee in assignees:
                if chunk.patent_id:
                    self._add_assignee_of(assignee, chunk.patent_id, chunk)

    def _add_relationship(self, rel: Relationship, deduplicate: bool = False) -> None:
        """Append a relationship, optionally skipping if its ID was already seen.

        Using a set for dedup (O(1) lookup) instead of scanning the full list.
        """
        if deduplicate:
            if rel.id in self._relationship_ids:
                return
            self._relationship_ids.add(rel.id)
        self.relationships.append(rel)

    def _add_described_in(self, entity: Entity, chunk):
        """Add DESCRIBED_IN relationship."""
        self._add_relationship(
            Relationship(
                id=f"described_{entity.id}_{chunk.chunk_id}",
                type=RelationType.DESCRIBED_IN,
                source_id=entity.id,
                target_id=chunk.chunk_id,
                properties={},
                patent_id=entity.patent_id,
                chunk_id=chunk.chunk_id,
            )
        )

    def _add_affects(self, element: Entity, prop: Entity, chunk):
        """Add AFFECTS relationship between element and property."""
        self._add_relationship(
            Relationship(
                id=f"affects_{element.id}_{prop.id}",
                type=RelationType.AFFECTS,
                source_id=element.id,
                target_id=prop.id,
                properties={"context": chunk.content[:200]},
                patent_id=element.patent_id,
                chunk_id=chunk.chunk_id,
            )
        )

    def _add_requires_temperature(self, process: Entity, chunk):
        """Add REQUIRES relationship for process temperature."""
        temp_value = process.properties.get("temperature")
        if not temp_value:
            return
        self._add_relationship(
            Relationship(
                id=f"requires_{process.id}_temp",
                type=RelationType.REQUIRES,
                source_id=process.id,
                target_id=f"{process.id}_temp_param",
                properties={
                    "parameter_type": "temperature",
                    "value": temp_value,
                    "unit": "°C",
                },
                patent_id=process.patent_id,
                chunk_id=chunk.chunk_id,
            )
        )

    def _add_references(self, chunk, ref_entity: Entity):
        """Add REFERENCES relationship from chunk to table/formula."""
        self._add_relationship(
            Relationship(
                id=f"ref_{chunk.chunk_id}_{ref_entity.id}",
                type=RelationType.REFERENCES,
                source_id=chunk.chunk_id,
                target_id=ref_entity.id,
                properties={},
                patent_id=chunk.patent_id,
                chunk_id=chunk.chunk_id,
            )
        )

    def _add_mentions(self, chunk, table_chunk_id: str):
        """Add MENTIONS relationship from a text chunk to a table chunk."""
        self._add_relationship(
            Relationship(
                id=f"mentions_{chunk.chunk_id}_{table_chunk_id}",
                type=RelationType.MENTIONS,
                source_id=chunk.chunk_id,
                target_id=table_chunk_id,
                properties={},
                patent_id=chunk.patent_id,
                chunk_id=chunk.chunk_id,
            ),
            deduplicate=True,
        )

    def _add_measured_in(self, prop: Entity, chunk):
        """Add MEASURED_IN relationship for property in table."""
        self._add_relationship(
            Relationship(
                id=f"measured_{prop.id}_{chunk.chunk_id}",
                type=RelationType.MEASURED_IN,
                source_id=prop.id,
                target_id=chunk.chunk_id,
                properties={"table_type": "data_table"},
                patent_id=prop.patent_id,
                chunk_id=chunk.chunk_id,
            )
        )

    def _add_used_for(self, material: Entity, application: Entity, chunk):
        """Add USED_FOR relationship between material and application."""
        self._add_relationship(
            Relationship(
                id=f"used_for_{material.id}_{application.id}",
                type=RelationType.USED_FOR,
                source_id=material.id,
                target_id=application.id,
                properties={"context": chunk.content[:200]},
                patent_id=material.patent_id,
                chunk_id=chunk.chunk_id,
            ),
            deduplicate=True,
        )

    def _add_cites(self, patent_ref: Entity, chunk):
        """Add CITES relationship from current patent to a patent reference."""
        self._add_relationship(
            Relationship(
                id=f"cites_{chunk.patent_id}_{patent_ref.id}",
                type=RelationType.CITES,
                source_id=chunk.patent_id,
                target_id=patent_ref.id,
                properties={},
                patent_id=chunk.patent_id,
                chunk_id=chunk.chunk_id,
            ),
            deduplicate=True,
        )

    def _add_addresses_problem(self, material: Entity, problem: Entity, chunk):
        """Add ADDRESSES_PROBLEM relationship between material and problem."""
        self._add_relationship(
            Relationship(
                id=f"addresses_{material.id}_{problem.id}",
                type=RelationType.ADDRESSES_PROBLEM,
                source_id=material.id,
                target_id=problem.id,
                properties={"context": chunk.content[:200]},
                patent_id=material.patent_id,
                chunk_id=chunk.chunk_id,
            ),
            deduplicate=True,
        )

    def _add_addresses_problem_patent(self, patent_id: str, problem: Entity, chunk):
        """Add ADDRESSES_PROBLEM relationship from patent to problem."""
        self._add_relationship(
            Relationship(
                id=f"addresses_{patent_id}_{problem.id}",
                type=RelationType.ADDRESSES_PROBLEM,
                source_id=patent_id,
                target_id=problem.id,
                properties={"context": chunk.content[:200]},
                patent_id=patent_id,
                chunk_id=chunk.chunk_id,
            ),
            deduplicate=True,
        )

    def _add_invented_by(self, patent_id: str, inventor: Entity, chunk):
        """Add INVENTED_BY relationship from patent to inventor."""
        self._add_relationship(
            Relationship(
                id=f"invented_by_{patent_id}_{inventor.id}",
                type=RelationType.INVENTED_BY,
                source_id=patent_id,
                target_id=inventor.id,
                properties={},
                patent_id=patent_id,
                chunk_id=chunk.chunk_id,
            ),
            deduplicate=True,
        )

    def _add_assignee_of(self, assignee: Entity, patent_id: str, chunk):
        """Add ASSIGNEE_OF relationship from assignee to patent."""
        self._add_relationship(
            Relationship(
                id=f"assignee_of_{assignee.id}_{patent_id}",
                type=RelationType.ASSIGNEE_OF,
                source_id=assignee.id,
                target_id=patent_id,
                properties={},
                patent_id=patent_id,
                chunk_id=chunk.chunk_id,
            ),
            deduplicate=True,
        )

    def export(self) -> dict:
        """Export KG as dictionary for storage."""
        return {
            "entities": {eid: self._entity_to_dict(e) for eid, e in self.entities.items()},
            "relationships": [self._rel_to_dict(r) for r in self.relationships],
        }

    def _entity_to_dict(self, entity: Entity) -> dict:
        return {
            "id": entity.id,
            "type": entity.type.value,
            "name": entity.name,
            "properties": entity.properties,
            "patent_id": entity.patent_id,
            "chunk_ids": entity.chunk_ids,
        }

    def _rel_to_dict(self, rel: Relationship) -> dict:
        return {
            "id": rel.id,
            "type": rel.type.value,
            "source_id": rel.source_id,
            "target_id": rel.target_id,
            "properties": rel.properties,
            "patent_id": rel.patent_id,
            "chunk_id": rel.chunk_id,
        }
