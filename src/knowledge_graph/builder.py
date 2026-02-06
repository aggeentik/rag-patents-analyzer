"""Build knowledge graph from extracted entities."""

from src.knowledge_graph.schema import Entity, Relationship, RelationType, EntityType


class KnowledgeGraphBuilder:
    """Build knowledge graph from extracted entities."""

    def __init__(self):
        self.entities: dict[str, Entity] = {}
        self.relationships: list[Relationship] = []

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
        - DESCRIBED_IN: Entity appears in chunk
        """
        for chunk in chunks:
            chunk_entities = [e for e in self.entities.values()
                           if chunk.chunk_id in e.chunk_ids]

            # DESCRIBED_IN: All entities → chunk
            for entity in chunk_entities:
                self._add_described_in(entity, chunk)

            # AFFECTS: Element + Property co-occurrence
            elements = [e for e in chunk_entities
                       if e.type == EntityType.CHEMICAL_ELEMENT]
            properties = [e for e in chunk_entities
                        if e.type == EntityType.PROPERTY]

            for element in elements:
                for prop in properties:
                    self._add_affects(element, prop, chunk)

            # REQUIRES: Process + Parameter co-occurrence
            processes = [e for e in chunk_entities
                        if e.type == EntityType.PROCESS]

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

            # MEASURED_IN: Property in table chunk
            if chunk.metadata.get("type") == "table":
                for prop in properties:
                    self._add_measured_in(prop, chunk)

    def _add_described_in(self, entity: Entity, chunk):
        """Add DESCRIBED_IN relationship."""
        rel = Relationship(
            id=f"described_{entity.id}_{chunk.chunk_id}",
            type=RelationType.DESCRIBED_IN,
            source_id=entity.id,
            target_id=chunk.chunk_id,
            properties={},
            patent_id=entity.patent_id,
            chunk_id=chunk.chunk_id,
        )
        self.relationships.append(rel)

    def _add_affects(self, element: Entity, prop: Entity, chunk):
        """Add AFFECTS relationship between element and property."""
        rel = Relationship(
            id=f"affects_{element.id}_{prop.id}",
            type=RelationType.AFFECTS,
            source_id=element.id,
            target_id=prop.id,
            properties={
                "context": chunk.content[:200],
            },
            patent_id=element.patent_id,
            chunk_id=chunk.chunk_id,
        )
        self.relationships.append(rel)

    def _add_requires_temperature(self, process: Entity, chunk):
        """Add REQUIRES relationship for process temperature."""
        temp_value = process.properties.get("temperature")
        if temp_value:
            rel = Relationship(
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
            self.relationships.append(rel)

    def _add_references(self, chunk, ref_entity: Entity):
        """Add REFERENCES relationship from chunk to table/formula."""
        rel = Relationship(
            id=f"ref_{chunk.chunk_id}_{ref_entity.id}",
            type=RelationType.REFERENCES,
            source_id=chunk.chunk_id,
            target_id=ref_entity.id,
            properties={},
            patent_id=chunk.patent_id,
            chunk_id=chunk.chunk_id,
        )
        self.relationships.append(rel)

    def _add_measured_in(self, prop: Entity, chunk):
        """Add MEASURED_IN relationship for property in table."""
        rel = Relationship(
            id=f"measured_{prop.id}_{chunk.chunk_id}",
            type=RelationType.MEASURED_IN,
            source_id=prop.id,
            target_id=chunk.chunk_id,
            properties={
                "table_type": "data_table",
            },
            patent_id=prop.patent_id,
            chunk_id=chunk.chunk_id,
        )
        self.relationships.append(rel)

    def export(self) -> dict:
        """Export KG as dictionary for storage."""
        return {
            "entities": {eid: self._entity_to_dict(e)
                        for eid, e in self.entities.items()},
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
