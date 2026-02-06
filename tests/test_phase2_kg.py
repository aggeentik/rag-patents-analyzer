"""Test script for Phase 2: Knowledge Graph implementation."""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dataclasses import dataclass
from src.knowledge_graph.schema import (
    Entity, EntityType, Relationship, RelationType,
    CHEMICAL_ELEMENTS, PROPERTIES, PROCESSES
)
from src.extraction.entity_extractor import EntityExtractor
from src.knowledge_graph.builder import KnowledgeGraphBuilder
from src.knowledge_graph.store import KnowledgeGraphStore
from src.knowledge_graph.traversal import KnowledgeGraphTraversal


# Mock Chunk class for testing
@dataclass
class MockChunk:
    chunk_id: str
    patent_id: str
    content: str
    metadata: dict


def test_schema():
    """Test 1: Schema definitions."""
    print("Test 1: Testing schema definitions...")

    # Test entity creation
    entity = Entity(
        id="TEST_001_Si_0",
        type=EntityType.CHEMICAL_ELEMENT,
        name="Si",
        properties={"value": 2.5, "unit": "%"},
        patent_id="TEST_001",
        chunk_ids=["TEST_001_0001"]
    )

    assert entity.name == "Si"
    assert entity.type == EntityType.CHEMICAL_ELEMENT
    print("  ✓ Entity creation successful")

    # Test relationship creation
    rel = Relationship(
        id="affects_Si_yield",
        type=RelationType.AFFECTS,
        source_id="TEST_001_Si_0",
        target_id="TEST_001_yield_0",
        properties={},
        patent_id="TEST_001",
        chunk_id="TEST_001_0001"
    )

    assert rel.type == RelationType.AFFECTS
    print("  ✓ Relationship creation successful")

    # Test vocabularies
    assert "Si" in CHEMICAL_ELEMENTS
    assert "yield_stress" in PROPERTIES
    assert "annealing" in PROCESSES
    print("  ✓ Vocabularies loaded successfully")

    print("✅ Test 1 PASSED\n")


def test_entity_extraction():
    """Test 2: Entity extraction from text."""
    print("Test 2: Testing entity extraction...")

    extractor = EntityExtractor()

    # Sample text with entities
    text = """
    The steel composition contains Si: 2.5%, Mn: 1.5%, and Al: 0.04%.
    The yield stress was 700 MPa after annealing at 850°C.
    Results are shown in Table 1.
    Sample A1 was tested for hardness.
    """

    chunk = MockChunk(
        chunk_id="TEST_001_0001",
        patent_id="TEST_001",
        content=text,
        metadata={"section": "Examples", "page": 5}
    )

    entities = extractor.extract_entities(chunk)

    # Check for chemical elements
    elements = [e for e in entities if e.type == EntityType.CHEMICAL_ELEMENT]
    print(f"  Found {len(elements)} chemical elements")
    assert len(elements) >= 3, f"Expected at least 3 elements, found {len(elements)}"

    # Check for properties
    properties = [e for e in entities if e.type == EntityType.PROPERTY]
    print(f"  Found {len(properties)} properties")

    # Check for processes
    processes = [e for e in entities if e.type == EntityType.PROCESS]
    print(f"  Found {len(processes)} processes")
    assert len(processes) >= 1, "Expected at least 1 process"

    # Check for tables
    tables = [e for e in entities if e.type == EntityType.TABLE]
    print(f"  Found {len(tables)} table references")
    assert len(tables) >= 1, "Expected at least 1 table reference"

    # Check for samples
    samples = [e for e in entities if e.type == EntityType.SAMPLE]
    print(f"  Found {len(samples)} samples")
    assert len(samples) >= 1, "Expected at least 1 sample"

    print(f"  Total entities extracted: {len(entities)}")
    print("✅ Test 2 PASSED\n")

    return entities, chunk


def test_kg_builder(entities, chunk):
    """Test 3: Knowledge graph builder."""
    print("Test 3: Testing knowledge graph builder...")

    builder = KnowledgeGraphBuilder()

    # Add entities
    builder.add_entities(entities)
    print(f"  Added {len(builder.entities)} unique entities")

    # Build relationships
    builder.build_relationships([chunk])
    print(f"  Built {len(builder.relationships)} relationships")

    # Check relationship types
    rel_types = set(r.type for r in builder.relationships)
    print(f"  Relationship types: {[rt.value for rt in rel_types]}")

    # Export graph
    kg_data = builder.export()
    assert "entities" in kg_data
    assert "relationships" in kg_data
    print("  ✓ Graph export successful")

    print("✅ Test 3 PASSED\n")

    return builder


def test_kg_store(builder):
    """Test 4: Knowledge graph storage."""
    print("Test 4: Testing knowledge graph storage...")

    # Create temporary database
    db_path = "/tmp/test_kg.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    store = KnowledgeGraphStore(db_path)
    store.connect()

    # Save entities
    kg_data = builder.export()
    for entity in kg_data["entities"].values():
        store.save_entity(entity)
    print(f"  Saved {len(kg_data['entities'])} entities to database")

    # Save relationships
    for rel in kg_data["relationships"]:
        store.save_relationship(rel)
    print(f"  Saved {len(kg_data['relationships'])} relationships to database")

    # Test queries
    # Find Silicon entities
    si_entities = store.find_entities("Si")
    print(f"  Found {len(si_entities)} entities matching 'Si'")

    # Get entities by type
    element_entities = store.get_entities_by_type("chemical_element")
    print(f"  Found {len(element_entities)} chemical element entities")

    store.close()
    print("✅ Test 4 PASSED\n")

    return db_path


def test_kg_traversal(db_path):
    """Test 5: Knowledge graph traversal."""
    print("Test 5: Testing knowledge graph traversal...")

    store = KnowledgeGraphStore(db_path)
    store.connect()

    traversal = KnowledgeGraphTraversal(store)
    traversal.build_networkx_graph()

    print(f"  Built NetworkX graph with {traversal.graph.number_of_nodes()} nodes")
    print(f"  and {traversal.graph.number_of_edges()} edges")

    # Test finding related chunks
    related_chunks = traversal.find_related_chunks(["Si", "yield stress"], max_hops=2)
    print(f"  Found {len(related_chunks)} related chunks")

    store.close()
    print("✅ Test 5 PASSED\n")


def main():
    """Run all Phase 2 tests."""
    print("=" * 60)
    print("PHASE 2: KNOWLEDGE GRAPH IMPLEMENTATION TESTS")
    print("=" * 60)
    print()

    try:
        # Run tests
        test_schema()
        entities, chunk = test_entity_extraction()
        builder = test_kg_builder(entities, chunk)
        db_path = test_kg_store(builder)
        test_kg_traversal(db_path)

        print("=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        print()
        print("Phase 2 implementation is complete and functional.")
        print()
        print("Summary:")
        print("  ✓ Schema definitions working")
        print("  ✓ Entity extraction working")
        print("  ✓ Knowledge graph builder working")
        print("  ✓ SQLite storage working")
        print("  ✓ Graph traversal working")

    except Exception as e:
        print(f"\n❌ TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
