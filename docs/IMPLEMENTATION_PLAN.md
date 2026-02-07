# Patent Search Demo - Full Implementation Plan

## Overview

Build a patent search system with knowledge graph, hybrid retrieval, and LLM-powered answers.

**Stack**:
- PDF Parsing: `unstructured` + `pdfplumber` (layout-aware)
- Knowledge Graph: SQLite + NetworkX (entities + relationships)
- Retrieval: Hybrid (BM25 + FAISS + Graph traversal)
- LLM: Amazon Bedrock OR Ollama (configurable)
- UI: Streamlit

---

## Project Structure

```
patent-demo/
├── app.py                        # Streamlit main application
├── requirements.txt              # Python dependencies
├── README.md                     # Setup and run instructions
├── .env.example                  # Environment variables template
├── config.py                     # Configuration (LLM provider, paths, etc.)
│
├── data/
│   ├── raw/                      # Original PDF files (10 patents)
│   └── processed/
│       ├── patents.json          # Extracted & chunked patent data
│       ├── bm25_index.pkl        # BM25 index
│       ├── faiss.index           # FAISS vector index
│       ├── chunk_ids.json        # FAISS position → chunk_id mapping
│       └── knowledge_graph.db    # SQLite database for KG
│
├── src/
│   ├── __init__.py
│   │
│   ├── extraction/
│   │   ├── __init__.py
│   │   ├── pdf_parser.py         # Layout-aware PDF extraction
│   │   ├── chunker.py            # Semantic chunking with metadata
│   │   └── entity_extractor.py   # Rule-based entity extraction
│   │
│   ├── knowledge_graph/
│   │   ├── __init__.py
│   │   ├── schema.py             # KG schema definitions
│   │   ├── builder.py            # Build KG from extracted data
│   │   ├── store.py              # SQLite storage layer
│   │   └── traversal.py          # Graph queries and traversal
│   │
│   ├── retrieval/
│   │   ├── __init__.py
│   │   ├── bm25_retriever.py     # BM25 sparse retrieval
│   │   ├── semantic_retriever.py # FAISS dense retrieval
│   │   ├── graph_retriever.py    # KG-based retrieval
│   │   └── hybrid_retriever.py   # Fusion of all three
│   │
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── base.py               # Abstract LLM interface
│   │   ├── bedrock.py            # Amazon Bedrock implementation
│   │   ├── ollama.py             # Ollama implementation
│   │   └── generator.py          # Answer generation with citations
│   │
│   └── utils/
│       ├── __init__.py
│       └── helpers.py            # Common utilities
│
└── scripts/
    ├── extract_patents.py        # Full extraction pipeline
    ├── build_indices.py          # Build all search indices
    └── test_retrieval.py         # Test retrieval quality
```

---

## Phase 1: PDF Parsing

### 1.1 PDF Parser (`src/extraction/pdf_parser.py`)

**Purpose**: Layout-aware extraction handling multi-column PDFs

```python
from unstructured.partition.pdf import partition_pdf
from unstructured.documents.elements import (
    Title, NarrativeText, Table, ListItem, Footer, Header
)
import pdfplumber
from dataclasses import dataclass
from typing import Optional
import re


@dataclass
class ExtractedElement:
    """Single extracted element from PDF."""
    text: str
    element_type: str          # "title", "paragraph", "table", "list", "formula"
    page: int
    section: Optional[str]     # "Abstract", "Claims", "Description", etc.
    coordinates: Optional[dict] # Bounding box for layout analysis
    table_data: Optional[list]  # Structured table data if type == "table"


class PatentPDFParser:
    """Layout-aware PDF parser for patent documents."""
    
    # Patent section patterns
    SECTION_PATTERNS = [
        (r"^ABSTRACT\s*$", "Abstract"),
        (r"^CLAIMS?\s*$", "Claims"),
        (r"^BACKGROUND", "Background"),
        (r"^DETAILED\s+DESCRIPTION", "Detailed Description"),
        (r"^EXAMPLES?\s*$", "Examples"),
        (r"^EMBODIMENTS?", "Embodiments"),
        (r"^BRIEF\s+DESCRIPTION", "Brief Description"),
        (r"^SUMMARY", "Summary"),
        (r"^FIELD\s+OF", "Field"),
    ]
    
    # Formula detection patterns
    FORMULA_PATTERNS = [
        r"Formula\s*\(\d+\)",
        r"Equation\s*\(\d+\)",
        r"\[\w+\]/\d+",  # Chemical formulas like [Nb]/93
    ]
    
    def __init__(self, use_hi_res: bool = True):
        self.use_hi_res = use_hi_res
    
    def extract(self, pdf_path: str) -> dict:
        """
        Extract structured content from patent PDF.
        
        Returns:
            {
                "patent_id": str,
                "title": str,
                "elements": list[ExtractedElement],
                "tables": list[dict],       # Separately extracted tables
                "metadata": {
                    "filename": str,
                    "total_pages": int,
                    "extraction_method": str
                }
            }
        """
        pass
    
    def _extract_with_unstructured(self, pdf_path: str) -> list[ExtractedElement]:
        """Primary extraction using unstructured library."""
        elements = partition_pdf(
            filename=pdf_path,
            strategy="hi_res" if self.use_hi_res else "fast",
            infer_table_structure=True,
            include_page_breaks=True,
        )
        # Convert to ExtractedElement objects
        pass
    
    def _extract_tables_with_pdfplumber(self, pdf_path: str) -> list[dict]:
        """Backup table extraction using pdfplumber."""
        tables = []
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                page_tables = page.extract_tables()
                for table in page_tables:
                    tables.append({
                        "page": page_num,
                        "headers": table[0] if table else [],
                        "rows": table[1:] if table else [],
                    })
        return tables
    
    def _detect_section(self, text: str) -> Optional[str]:
        """Detect patent section from text."""
        for pattern, section_name in self.SECTION_PATTERNS:
            if re.match(pattern, text.strip(), re.IGNORECASE):
                return section_name
        return None
    
    def _detect_formula(self, text: str) -> bool:
        """Check if text contains a formula."""
        for pattern in self.FORMULA_PATTERNS:
            if re.search(pattern, text):
                return True
        return False
    
    def _extract_patent_id(self, pdf_path: str, first_page_text: str) -> str:
        """Extract patent ID from filename or content."""
        # Try filename first
        filename = os.path.basename(pdf_path)
        match = re.search(r"(EP|US|WO|CN)\d+", filename, re.IGNORECASE)
        if match:
            return match.group(0).upper()
        
        # Try first page content
        match = re.search(r"(EP|US|WO|CN)\s*\d+", first_page_text, re.IGNORECASE)
        if match:
            return re.sub(r"\s+", "", match.group(0)).upper()
        
        # Fallback to filename without extension
        return os.path.splitext(filename)[0]
```

### 1.2 Chunker (`src/extraction/chunker.py`)

**Purpose**: Create retrieval-ready chunks with metadata

```python
from dataclasses import dataclass
from typing import Optional
import tiktoken


@dataclass
class Chunk:
    """Single chunk for retrieval."""
    chunk_id: str
    patent_id: str
    content: str
    metadata: dict  # section, page, type, etc.
    entities: list[dict]  # Extracted entities
    references: list[str]  # Cross-references (Table 1, Formula 2)


class PatentChunker:
    """Semantic chunking for patent documents."""
    
    # Reference patterns
    REFERENCE_PATTERNS = [
        r"Table\s*\d+",
        r"Formula\s*\(\d+\)",
        r"FIG\.?\s*\d+",
        r"Figure\s*\d+",
        r"Equation\s*\(\d+\)",
    ]
    
    def __init__(
        self, 
        chunk_size: int = 500,      # Target tokens
        chunk_overlap: int = 50,     # Overlap tokens
        min_chunk_size: int = 100,   # Minimum tokens
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
    
    def chunk_patent(self, patent_data: dict) -> list[Chunk]:
        """
        Create chunks from extracted patent data.
        
        Rules:
        1. Tables → single chunk (never split)
        2. Formulas → single chunk with surrounding context
        3. Paragraphs → split at sentence boundaries if too large
        4. Preserve section context in every chunk
        5. Extract cross-references from each chunk
        """
        chunks = []
        current_section = "Unknown"
        
        for element in patent_data["elements"]:
            # Update current section
            if element.element_type == "title":
                detected = self._detect_section(element.text)
                if detected:
                    current_section = detected
                    continue
            
            # Tables: single chunk
            if element.element_type == "table":
                chunk = self._create_table_chunk(
                    element, patent_data["patent_id"], current_section
                )
                chunks.append(chunk)
            
            # Formulas: include context
            elif element.element_type == "formula":
                chunk = self._create_formula_chunk(
                    element, patent_data["patent_id"], current_section
                )
                chunks.append(chunk)
            
            # Text: chunk with overlap
            else:
                text_chunks = self._chunk_text(
                    element, patent_data["patent_id"], current_section
                )
                chunks.extend(text_chunks)
        
        # Assign sequential IDs
        for i, chunk in enumerate(chunks):
            chunk.chunk_id = f"{patent_data['patent_id']}_{i:04d}"
        
        return chunks
    
    def _chunk_text(
        self, 
        element: ExtractedElement, 
        patent_id: str, 
        section: str
    ) -> list[Chunk]:
        """Split text into chunks at sentence boundaries."""
        pass
    
    def _create_table_chunk(
        self, 
        element: ExtractedElement, 
        patent_id: str, 
        section: str
    ) -> Chunk:
        """Create a single chunk for a table."""
        # Format table as text
        content = self._format_table(element)
        references = self._extract_references(content)
        
        return Chunk(
            chunk_id="",  # Will be assigned later
            patent_id=patent_id,
            content=content,
            metadata={
                "section": section,
                "page": element.page,
                "type": "table",
                "table_data": element.table_data,
            },
            entities=[],  # Will be extracted later
            references=references,
        )
    
    def _extract_references(self, text: str) -> list[str]:
        """Extract cross-references from text."""
        references = []
        for pattern in self.REFERENCE_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            references.extend(matches)
        return list(set(references))
    
    def _count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.tokenizer.encode(text))
```

---

## Phase 2: Knowledge Graph

### 2.1 KG Schema (`src/knowledge_graph/schema.py`)

**Purpose**: Define entity types and relationships

```python
from enum import Enum
from dataclasses import dataclass
from typing import Optional


class EntityType(Enum):
    """Types of entities in patent KG."""
    CHEMICAL_ELEMENT = "chemical_element"
    PROPERTY = "property"
    PROCESS = "process"
    PARAMETER = "parameter"
    COMPOSITION_RANGE = "composition_range"
    TABLE = "table"
    FORMULA = "formula"
    SAMPLE = "sample"
    FIGURE = "figure"


class RelationType(Enum):
    """Types of relationships in patent KG."""
    CONTAINS = "contains"           # Composition contains element
    HAS_VALUE = "has_value"         # Element has percentage value
    AFFECTS = "affects"             # Element affects property
    REQUIRES = "requires"           # Process requires parameter
    ACHIEVED_IN = "achieved_in"     # Property achieved in sample
    MEASURED_IN = "measured_in"     # Property measured in table
    DESCRIBED_IN = "described_in"   # Entity described in chunk
    SHOWN_IN = "shown_in"           # Data shown in figure
    SATISFIES = "satisfies"         # Composition satisfies formula
    REFERENCES = "references"       # Chunk references table/formula
    NEXT_STEP = "next_step"         # Process step sequence


@dataclass
class Entity:
    """Knowledge graph entity."""
    id: str
    type: EntityType
    name: str
    properties: dict          # Additional attributes
    patent_id: str
    chunk_ids: list[str]      # Chunks where this entity appears


@dataclass
class Relationship:
    """Knowledge graph relationship."""
    id: str
    type: RelationType
    source_id: str
    target_id: str
    properties: dict          # e.g., value, unit, confidence
    patent_id: str
    chunk_id: Optional[str]   # Chunk where relationship is stated


# Predefined entity vocabularies
CHEMICAL_ELEMENTS = {
    "Si": "Silicon", "Cr": "Chromium", "Mn": "Manganese", 
    "Al": "Aluminum", "Cu": "Copper", "Ni": "Nickel",
    "Ti": "Titanium", "Nb": "Niobium", "V": "Vanadium",
    "Zr": "Zirconium", "C": "Carbon", "N": "Nitrogen",
    "S": "Sulfur", "P": "Phosphorus", "Mo": "Molybdenum",
    "B": "Boron", "Fe": "Iron", "Co": "Cobalt",
}

PROPERTIES = {
    "yield_stress": ["yield stress", "yield strength", "σy"],
    "tensile_strength": ["tensile strength", "UTS"],
    "elongation": ["elongation", "fracture elongation"],
    "core_loss": ["core loss", "iron loss", "W/kg"],
    "magnetic_flux": ["magnetic flux density", "B50", "B8"],
    "resistivity": ["resistivity", "electrical resistivity"],
    "hardness": ["hardness", "Vickers hardness", "HV"],
}

PROCESSES = {
    "hot_rolling": ["hot rolling", "hot rolled", "hot-rolling"],
    "cold_rolling": ["cold rolling", "cold rolled", "cold-rolling"],
    "annealing": ["annealing", "annealed", "finish annealing"],
    "pickling": ["pickling", "pickled", "acid pickling"],
    "coating": ["coating", "coated", "insulation coating"],
    "heat_treatment": ["heat treatment", "heat treated"],
}
```

### 2.2 Entity Extractor (`src/extraction/entity_extractor.py`)

**Purpose**: Rule-based entity extraction (no LLM needed)

```python
import re
from typing import Optional
from src.knowledge_graph.schema import (
    Entity, EntityType, CHEMICAL_ELEMENTS, PROPERTIES, PROCESSES
)


class EntityExtractor:
    """Rule-based entity extraction from patent text."""
    
    # Patterns for extracting values
    PERCENTAGE_PATTERN = r"(\d+\.?\d*)\s*(%|mass\s*%|wt\s*%)"
    TEMPERATURE_PATTERN = r"(\d+)\s*°?C"
    RANGE_PATTERN = r"(\d+\.?\d*)\s*(?:to|-)\s*(\d+\.?\d*)\s*(%|°C|MPa|T)"
    MPa_PATTERN = r"(\d+)\s*MPa"
    TABLE_PATTERN = r"Table\s*(\d+)"
    FORMULA_PATTERN = r"Formula\s*\((\d+)\)"
    SAMPLE_PATTERN = r"(?:Sample|Symbol|Material)\s+([a-zA-Z]\d+)"
    
    def __init__(self):
        # Compile regex patterns for efficiency
        self._compile_patterns()
    
    def extract_entities(self, chunk: Chunk) -> list[Entity]:
        """
        Extract all entities from a chunk.
        
        Returns list of Entity objects with:
        - Chemical elements with values
        - Properties with measurements
        - Process steps with parameters
        - Table/Formula/Figure references
        """
        entities = []
        text = chunk.content
        
        # Extract chemical elements
        elements = self._extract_chemical_elements(text, chunk)
        entities.extend(elements)
        
        # Extract properties
        properties = self._extract_properties(text, chunk)
        entities.extend(properties)
        
        # Extract processes
        processes = self._extract_processes(text, chunk)
        entities.extend(processes)
        
        # Extract tables, formulas, figures
        references = self._extract_references(text, chunk)
        entities.extend(references)
        
        # Extract samples
        samples = self._extract_samples(text, chunk)
        entities.extend(samples)
        
        return entities
    
    def _extract_chemical_elements(self, text: str, chunk: Chunk) -> list[Entity]:
        """Extract chemical element mentions with values."""
        entities = []
        
        for symbol, name in CHEMICAL_ELEMENTS.items():
            # Pattern: Si: 2.5% or Si = 2.5 mass%
            pattern = rf"\b{symbol}\s*[:=]?\s*(\d+\.?\d*)\s*(%|mass\s*%|wt\s*%)"
            matches = re.finditer(pattern, text, re.IGNORECASE)
            
            for match in matches:
                value = float(match.group(1))
                unit = match.group(2)
                
                entity = Entity(
                    id=f"{chunk.patent_id}_{symbol}_{len(entities)}",
                    type=EntityType.CHEMICAL_ELEMENT,
                    name=symbol,
                    properties={
                        "full_name": name,
                        "value": value,
                        "unit": unit,
                        "context": self._get_context(text, match.start(), match.end()),
                    },
                    patent_id=chunk.patent_id,
                    chunk_ids=[chunk.chunk_id],
                )
                entities.append(entity)
            
            # Also capture ranges: Si: 2.5-10%
            range_pattern = rf"\b{symbol}\s*[:=]?\s*(\d+\.?\d*)\s*(?:to|-)\s*(\d+\.?\d*)\s*(%|mass\s*%)"
            range_matches = re.finditer(range_pattern, text, re.IGNORECASE)
            
            for match in range_matches:
                min_val = float(match.group(1))
                max_val = float(match.group(2))
                
                entity = Entity(
                    id=f"{chunk.patent_id}_{symbol}_range_{len(entities)}",
                    type=EntityType.COMPOSITION_RANGE,
                    name=f"{symbol}_range",
                    properties={
                        "element": symbol,
                        "min_value": min_val,
                        "max_value": max_val,
                        "unit": "%",
                    },
                    patent_id=chunk.patent_id,
                    chunk_ids=[chunk.chunk_id],
                )
                entities.append(entity)
        
        return entities
    
    def _extract_properties(self, text: str, chunk: Chunk) -> list[Entity]:
        """Extract material properties with values."""
        entities = []
        
        for prop_id, aliases in PROPERTIES.items():
            for alias in aliases:
                # Find property mentions
                if alias.lower() in text.lower():
                    # Try to find associated value
                    # Pattern: yield stress of 700 MPa
                    pattern = rf"{re.escape(alias)}\s*(?:of|:)?\s*(\d+)\s*(MPa|%|T|W/kg)"
                    match = re.search(pattern, text, re.IGNORECASE)
                    
                    properties = {"alias": alias}
                    if match:
                        properties["value"] = float(match.group(1))
                        properties["unit"] = match.group(2)
                    
                    entity = Entity(
                        id=f"{chunk.patent_id}_{prop_id}_{len(entities)}",
                        type=EntityType.PROPERTY,
                        name=prop_id,
                        properties=properties,
                        patent_id=chunk.patent_id,
                        chunk_ids=[chunk.chunk_id],
                    )
                    entities.append(entity)
                    break  # Only add once per property type
        
        return entities
    
    def _extract_processes(self, text: str, chunk: Chunk) -> list[Entity]:
        """Extract process steps with parameters."""
        entities = []
        
        for process_id, aliases in PROCESSES.items():
            for alias in aliases:
                if alias.lower() in text.lower():
                    # Try to find temperature parameter
                    temp_pattern = rf"{re.escape(alias)}.*?(\d+)\s*°?C"
                    temp_match = re.search(temp_pattern, text, re.IGNORECASE)
                    
                    properties = {"alias": alias}
                    if temp_match:
                        properties["temperature"] = int(temp_match.group(1))
                        properties["temperature_unit"] = "°C"
                    
                    entity = Entity(
                        id=f"{chunk.patent_id}_{process_id}_{len(entities)}",
                        type=EntityType.PROCESS,
                        name=process_id,
                        properties=properties,
                        patent_id=chunk.patent_id,
                        chunk_ids=[chunk.chunk_id],
                    )
                    entities.append(entity)
                    break
        
        return entities
    
    def _extract_references(self, text: str, chunk: Chunk) -> list[Entity]:
        """Extract table, formula, and figure references."""
        entities = []
        
        # Tables
        for match in re.finditer(self.TABLE_PATTERN, text, re.IGNORECASE):
            table_num = match.group(1)
            entity = Entity(
                id=f"{chunk.patent_id}_table_{table_num}",
                type=EntityType.TABLE,
                name=f"Table {table_num}",
                properties={"table_number": int(table_num)},
                patent_id=chunk.patent_id,
                chunk_ids=[chunk.chunk_id],
            )
            entities.append(entity)
        
        # Formulas
        for match in re.finditer(self.FORMULA_PATTERN, text, re.IGNORECASE):
            formula_num = match.group(1)
            entity = Entity(
                id=f"{chunk.patent_id}_formula_{formula_num}",
                type=EntityType.FORMULA,
                name=f"Formula {formula_num}",
                properties={"formula_number": int(formula_num)},
                patent_id=chunk.patent_id,
                chunk_ids=[chunk.chunk_id],
            )
            entities.append(entity)
        
        return entities
    
    def _extract_samples(self, text: str, chunk: Chunk) -> list[Entity]:
        """Extract sample/material identifiers."""
        entities = []
        
        for match in re.finditer(self.SAMPLE_PATTERN, text):
            sample_id = match.group(1)
            entity = Entity(
                id=f"{chunk.patent_id}_sample_{sample_id}",
                type=EntityType.SAMPLE,
                name=f"Sample {sample_id}",
                properties={"sample_id": sample_id},
                patent_id=chunk.patent_id,
                chunk_ids=[chunk.chunk_id],
            )
            entities.append(entity)
        
        return entities
    
    def _get_context(self, text: str, start: int, end: int, window: int = 50) -> str:
        """Get surrounding context for a match."""
        context_start = max(0, start - window)
        context_end = min(len(text), end + window)
        return text[context_start:context_end]
```

### 2.3 KG Builder (`src/knowledge_graph/builder.py`)

**Purpose**: Build relationships between entities

```python
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
    
    def build_relationships(self, chunks: list[Chunk]):
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
    
    def _add_described_in(self, entity: Entity, chunk: Chunk):
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
    
    def _add_affects(self, element: Entity, prop: Entity, chunk: Chunk):
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
    
    def _add_references(self, chunk: Chunk, ref_entity: Entity):
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
```

### 2.4 KG Store (`src/knowledge_graph/store.py`)

**Purpose**: SQLite storage for KG

```python
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
    
    def connect(self):
        """Connect to database and create schema."""
        self.conn = sqlite3.connect(self.db_path)
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
```

### 2.5 KG Traversal (`src/knowledge_graph/traversal.py`)

**Purpose**: Graph queries for retrieval

```python
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
```

---

## Phase 3: Hybrid Retrieval

### 3.1 BM25 Retriever (`src/retrieval/bm25_retriever.py`)

```python
import pickle
from rank_bm25 import BM25Okapi
import nltk
from nltk.tokenize import word_tokenize


class BM25Retriever:
    """BM25 sparse retrieval."""
    
    def __init__(self):
        self.bm25 = None
        self.chunks = []
        self.tokenized_corpus = []
        
        # Ensure nltk data is available
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            nltk.download('punkt')
    
    def build_index(self, chunks: list[dict]):
        """Build BM25 index from chunks."""
        self.chunks = chunks
        self.tokenized_corpus = [
            word_tokenize(chunk["content"].lower())
            for chunk in chunks
        ]
        self.bm25 = BM25Okapi(self.tokenized_corpus)
    
    def search(self, query: str, top_k: int = 10) -> list[dict]:
        """Search and return chunks with BM25 scores."""
        tokenized_query = word_tokenize(query.lower())
        scores = self.bm25.get_scores(tokenized_query)
        
        # Get top-k indices
        top_indices = scores.argsort()[-top_k:][::-1]
        
        results = []
        for idx in top_indices:
            chunk = self.chunks[idx].copy()
            chunk["bm25_score"] = float(scores[idx])
            chunk["bm25_rank"] = len(results) + 1
            results.append(chunk)
        
        return results
    
    def save(self, path: str):
        """Save index to disk."""
        with open(path, "wb") as f:
            pickle.dump({
                "bm25": self.bm25,
                "tokenized_corpus": self.tokenized_corpus,
            }, f)
    
    @classmethod
    def load(cls, path: str, chunks: list[dict]) -> "BM25Retriever":
        """Load index from disk."""
        retriever = cls()
        retriever.chunks = chunks
        
        with open(path, "rb") as f:
            data = pickle.load(f)
            retriever.bm25 = data["bm25"]
            retriever.tokenized_corpus = data["tokenized_corpus"]
        
        return retriever
```

### 3.2 Semantic Retriever (`src/retrieval/semantic_retriever.py`)

```python
import json
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer


class SemanticRetriever:
    """FAISS-based semantic retrieval."""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)
        self.index = None
        self.chunk_ids = []
        self.chunks_by_id = {}
    
    def build_index(self, chunks: list[dict]):
        """Build FAISS index from chunks."""
        self.chunks_by_id = {c["chunk_id"]: c for c in chunks}
        self.chunk_ids = [c["chunk_id"] for c in chunks]
        
        # Generate embeddings
        texts = [c["content"] for c in chunks]
        embeddings = self.model.encode(texts, show_progress_bar=True)
        
        # Normalize for cosine similarity
        embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
        
        # Build FAISS index
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dimension)  # Inner product = cosine after normalization
        self.index.add(embeddings.astype(np.float32))
    
    def search(self, query: str, top_k: int = 10) -> list[dict]:
        """Search and return chunks with semantic scores."""
        # Encode query
        query_embedding = self.model.encode([query])
        query_embedding = query_embedding / np.linalg.norm(query_embedding)
        
        # Search
        scores, indices = self.index.search(query_embedding.astype(np.float32), top_k)
        
        results = []
        for i, (score, idx) in enumerate(zip(scores[0], indices[0])):
            chunk_id = self.chunk_ids[idx]
            chunk = self.chunks_by_id[chunk_id].copy()
            chunk["semantic_score"] = float(score)
            chunk["semantic_rank"] = i + 1
            results.append(chunk)
        
        return results
    
    def save(self, index_path: str, mapping_path: str):
        """Save FAISS index and mapping."""
        faiss.write_index(self.index, index_path)
        with open(mapping_path, "w") as f:
            json.dump(self.chunk_ids, f)
    
    @classmethod
    def load(
        cls, 
        index_path: str, 
        mapping_path: str, 
        chunks: list[dict],
        model_name: str = "all-MiniLM-L6-v2"
    ) -> "SemanticRetriever":
        """Load index from disk."""
        retriever = cls(model_name)
        retriever.chunks_by_id = {c["chunk_id"]: c for c in chunks}
        
        retriever.index = faiss.read_index(index_path)
        with open(mapping_path, "r") as f:
            retriever.chunk_ids = json.load(f)
        
        return retriever
```

### 3.3 Graph Retriever (`src/retrieval/graph_retriever.py`)

```python
from src.knowledge_graph.store import KnowledgeGraphStore
from src.knowledge_graph.traversal import KnowledgeGraphTraversal
from src.knowledge_graph.schema import CHEMICAL_ELEMENTS, PROPERTIES, PROCESSES


class GraphRetriever:
    """Knowledge graph-based retrieval."""
    
    def __init__(self, kg_store: KnowledgeGraphStore, chunks: list[dict]):
        self.store = kg_store
        self.traversal = KnowledgeGraphTraversal(kg_store)
        self.traversal.build_networkx_graph()
        self.chunks_by_id = {c["chunk_id"]: c for c in chunks}
    
    def search(self, query: str, top_k: int = 10) -> list[dict]:
        """
        Search using knowledge graph.
        
        Steps:
        1. Extract entities from query
        2. Find matching entities in KG
        3. Traverse graph to find related chunks
        4. Score and rank chunks
        """
        # Extract query entities
        query_entities = self._extract_query_entities(query)
        
        if not query_entities:
            return []
        
        # Find related chunks via graph traversal
        chunk_ids = self.traversal.find_related_chunks(
            query_entities, 
            max_hops=2,
            max_chunks=top_k * 2
        )
        
        # Build results with scores
        results = []
        for i, chunk_id in enumerate(chunk_ids[:top_k]):
            if chunk_id in self.chunks_by_id:
                chunk = self.chunks_by_id[chunk_id].copy()
                chunk["graph_score"] = 1.0 / (i + 1)  # Simple rank-based score
                chunk["graph_rank"] = i + 1
                
                # Add entity info
                chunk["matched_entities"] = self.store.get_entities_by_chunk(chunk_id)
                results.append(chunk)
        
        return results
    
    def _extract_query_entities(self, query: str) -> list[str]:
        """Extract entity names from query."""
        entities = []
        query_lower = query.lower()
        
        # Check for chemical elements
        for symbol in CHEMICAL_ELEMENTS.keys():
            if symbol.lower() in query_lower or symbol in query:
                entities.append(symbol)
        
        # Check for properties
        for prop_id, aliases in PROPERTIES.items():
            for alias in aliases:
                if alias.lower() in query_lower:
                    entities.append(prop_id)
                    break
        
        # Check for processes
        for proc_id, aliases in PROCESSES.items():
            for alias in aliases:
                if alias.lower() in query_lower:
                    entities.append(proc_id)
                    break
        
        return entities
```

### 3.4 Hybrid Retriever (`src/retrieval/hybrid_retriever.py`)

```python
from typing import Optional
from src.retrieval.bm25_retriever import BM25Retriever
from src.retrieval.semantic_retriever import SemanticRetriever
from src.retrieval.graph_retriever import GraphRetriever


class HybridRetriever:
    """
    Hybrid retrieval combining BM25 + Semantic + Graph.
    
    Uses Reciprocal Rank Fusion (RRF) to combine results.
    """
    
    def __init__(
        self,
        bm25: BM25Retriever,
        semantic: SemanticRetriever,
        graph: GraphRetriever,
        chunks: list[dict],
    ):
        self.bm25 = bm25
        self.semantic = semantic
        self.graph = graph
        self.chunks_by_id = {c["chunk_id"]: c for c in chunks}
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        patent_filter: Optional[list[str]] = None,
        bm25_weight: float = 0.35,
        semantic_weight: float = 0.35,
        graph_weight: float = 0.30,
        rrf_k: int = 60,
    ) -> list[dict]:
        """
        Hybrid search with three-way RRF fusion.
        
        Args:
            query: Natural language question
            top_k: Number of results to return
            patent_filter: Optional list of patent_ids to include
            bm25_weight: Weight for BM25 in fusion
            semantic_weight: Weight for semantic in fusion
            graph_weight: Weight for graph in fusion
            rrf_k: RRF constant (higher = more emphasis on top results)
        
        Returns:
            List of chunks with hybrid scores and component rankings
        """
        # Get results from each retriever
        fetch_k = top_k * 3  # Fetch more for better fusion
        
        bm25_results = self.bm25.search(query, top_k=fetch_k)
        semantic_results = self.semantic.search(query, top_k=fetch_k)
        graph_results = self.graph.search(query, top_k=fetch_k)
        
        # Apply patent filter if specified
        if patent_filter:
            bm25_results = [r for r in bm25_results if r["patent_id"] in patent_filter]
            semantic_results = [r for r in semantic_results if r["patent_id"] in patent_filter]
            graph_results = [r for r in graph_results if r["patent_id"] in patent_filter]
        
        # RRF Fusion
        scores = {}
        rankings = {}
        
        # BM25 contribution
        for rank, result in enumerate(bm25_results, 1):
            chunk_id = result["chunk_id"]
            scores[chunk_id] = scores.get(chunk_id, 0) + bm25_weight / (rrf_k + rank)
            if chunk_id not in rankings:
                rankings[chunk_id] = {}
            rankings[chunk_id]["bm25_rank"] = rank
        
        # Semantic contribution
        for rank, result in enumerate(semantic_results, 1):
            chunk_id = result["chunk_id"]
            scores[chunk_id] = scores.get(chunk_id, 0) + semantic_weight / (rrf_k + rank)
            if chunk_id not in rankings:
                rankings[chunk_id] = {}
            rankings[chunk_id]["semantic_rank"] = rank
        
        # Graph contribution
        for rank, result in enumerate(graph_results, 1):
            chunk_id = result["chunk_id"]
            scores[chunk_id] = scores.get(chunk_id, 0) + graph_weight / (rrf_k + rank)
            if chunk_id not in rankings:
                rankings[chunk_id] = {}
            rankings[chunk_id]["graph_rank"] = rank
            # Also store matched entities
            if "matched_entities" in result:
                rankings[chunk_id]["matched_entities"] = result["matched_entities"]
        
        # Sort by fused score
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        # Build final results
        results = []
        for chunk_id, score in ranked[:top_k]:
            chunk = self.chunks_by_id[chunk_id].copy()
            chunk["hybrid_score"] = score
            chunk["bm25_rank"] = rankings.get(chunk_id, {}).get("bm25_rank")
            chunk["semantic_rank"] = rankings.get(chunk_id, {}).get("semantic_rank")
            chunk["graph_rank"] = rankings.get(chunk_id, {}).get("graph_rank")
            chunk["matched_entities"] = rankings.get(chunk_id, {}).get("matched_entities", [])
            results.append(chunk)
        
        return results
```

---

## Phase 4: LLM Integration

### 4.1 Base LLM Interface (`src/llm/base.py`)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMResponse:
    """Standardized LLM response."""
    text: str
    model: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None


class BaseLLM(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        """Generate text from prompt."""
        pass
    
    @abstractmethod
    def get_model_name(self) -> str:
        """Return model identifier."""
        pass
```

### 4.2 Amazon Bedrock (`src/llm/bedrock.py`)

```python
import boto3
import json
from typing import Optional
from src.llm.base import BaseLLM, LLMResponse


class BedrockLLM(BaseLLM):
    """Amazon Bedrock LLM implementation."""
    
    def __init__(
        self,
        model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0",
        region: str = "us-east-1",
        max_tokens: int = 2048,
    ):
        self.model_id = model_id
        self.max_tokens = max_tokens
        self.client = boto3.client("bedrock-runtime", region_name=region)
    
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        """Generate using Bedrock Claude."""
        messages = [{"role": "user", "content": prompt}]
        
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": self.max_tokens,
            "messages": messages,
        }
        
        if system_prompt:
            body["system"] = system_prompt
        
        response = self.client.invoke_model(
            modelId=self.model_id,
            body=json.dumps(body),
        )
        
        result = json.loads(response["body"].read())
        
        return LLMResponse(
            text=result["content"][0]["text"],
            model=self.model_id,
            input_tokens=result.get("usage", {}).get("input_tokens"),
            output_tokens=result.get("usage", {}).get("output_tokens"),
        )
    
    def get_model_name(self) -> str:
        return self.model_id
```

### 4.3 Ollama (`src/llm/ollama.py`)

```python
import requests
from typing import Optional
from src.llm.base import BaseLLM, LLMResponse


class OllamaLLM(BaseLLM):
    """Ollama local LLM implementation."""
    
    def __init__(
        self,
        model: str = "llama3.2",
        base_url: str = "http://localhost:11434",
        max_tokens: int = 2048,
    ):
        self.model = model
        self.base_url = base_url
        self.max_tokens = max_tokens
    
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        """Generate using Ollama."""
        url = f"{self.base_url}/api/generate"
        
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        
        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "num_predict": self.max_tokens,
            },
        }
        
        response = requests.post(url, json=payload)
        response.raise_for_status()
        result = response.json()
        
        return LLMResponse(
            text=result["response"],
            model=self.model,
        )
    
    def get_model_name(self) -> str:
        return f"ollama/{self.model}"
```

### 4.4 Answer Generator (`src/llm/generator.py`)

```python
from typing import Optional
from src.llm.base import BaseLLM, LLMResponse
from src.llm.bedrock import BedrockLLM
from src.llm.ollama import OllamaLLM


SYSTEM_PROMPT = """You are a technical assistant specializing in steel manufacturing patents.
Your task is to answer questions based ONLY on the provided patent excerpts.

Rules:
1. Only use information from the provided context
2. Always cite your sources using [Patent ID, Section, Page X] format
3. If the context doesn't contain enough information, say so clearly
4. Be precise with technical values (percentages, temperatures, etc.)
5. When referencing tables or formulas, mention them explicitly
6. Structure your answer clearly with the key information first"""


USER_PROMPT_TEMPLATE = """
Context from patents:
{context}

---

Question: {question}

Provide a detailed answer with citations. Format citations as [Patent ID, Section, Page X].
"""


class AnswerGenerator:
    """Generate answers with citations from retrieved chunks."""
    
    def __init__(self, llm_provider: str = "ollama", **kwargs):
        """
        Initialize generator with LLM provider.
        
        Args:
            llm_provider: "bedrock" or "ollama"
            **kwargs: Provider-specific arguments
        """
        if llm_provider == "bedrock":
            self.llm = BedrockLLM(**kwargs)
        elif llm_provider == "ollama":
            self.llm = OllamaLLM(**kwargs)
        else:
            raise ValueError(f"Unknown LLM provider: {llm_provider}")
    
    def generate(self, query: str, chunks: list[dict]) -> dict:
        """
        Generate answer with citations.
        
        Returns:
            {
                "answer": str,
                "citations": list[dict],
                "model": str,
                "chunks_used": int,
            }
        """
        # Format context
        context = self._format_context(chunks)
        
        # Build prompt
        prompt = USER_PROMPT_TEMPLATE.format(
            context=context,
            question=query,
        )
        
        # Generate
        response = self.llm.generate(prompt, system_prompt=SYSTEM_PROMPT)
        
        # Extract citations
        citations = self._extract_citations(response.text, chunks)
        
        return {
            "answer": response.text,
            "citations": citations,
            "model": self.llm.get_model_name(),
            "chunks_used": len(chunks),
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
        }
    
    def _format_context(self, chunks: list[dict]) -> str:
        """Format chunks into context string."""
        context_parts = []
        
        for i, chunk in enumerate(chunks, 1):
            meta = chunk.get("metadata", {})
            header = f"[Source {i}: {chunk['patent_id']}, {meta.get('section', 'Unknown')}, Page {meta.get('page', '?')}]"
            
            # Add entity info if available
            entities = chunk.get("matched_entities", [])
            if entities:
                entity_names = [e.get("name", "") for e in entities[:5]]
                header += f"\nEntities: {', '.join(entity_names)}"
            
            context_parts.append(f"{header}\n{chunk['content']}")
        
        return "\n\n---\n\n".join(context_parts)
    
    def _extract_citations(self, answer: str, chunks: list[dict]) -> list[dict]:
        """Extract and validate citations from answer."""
        import re
        
        citations = []
        # Pattern: [EP1234567, Section, Page X]
        pattern = r"\[([A-Z]{2}\d+),\s*([^,]+),\s*Page\s*(\d+)\]"
        
        for match in re.finditer(pattern, answer):
            patent_id = match.group(1)
            section = match.group(2).strip()
            page = int(match.group(3))
            
            # Find matching chunk
            for chunk in chunks:
                if (chunk["patent_id"] == patent_id and 
                    chunk.get("metadata", {}).get("page") == page):
                    citations.append({
                        "patent_id": patent_id,
                        "section": section,
                        "page": page,
                        "chunk_id": chunk["chunk_id"],
                        "excerpt": chunk["content"][:200],
                    })
                    break
        
        return citations
```

---

## Phase 5: Streamlit UI

### 5.1 Main Application (`app.py`)

```python
import streamlit as st
import json
from pathlib import Path

from src.retrieval.hybrid_retriever import HybridRetriever
from src.retrieval.bm25_retriever import BM25Retriever
from src.retrieval.semantic_retriever import SemanticRetriever
from src.retrieval.graph_retriever import GraphRetriever
from src.knowledge_graph.store import KnowledgeGraphStore
from src.llm.generator import AnswerGenerator
from config import Config

# Page config
st.set_page_config(
    page_title="Patent Search Demo",
    page_icon="🔬",
    layout="wide",
)

# Custom CSS
st.markdown("""
<style>
    .entity-tag {
        background-color: #e3f2fd;
        padding: 2px 8px;
        border-radius: 12px;
        margin: 2px;
        display: inline-block;
        font-size: 0.85em;
    }
    .entity-element { background-color: #e8f5e9; }
    .entity-property { background-color: #fff3e0; }
    .entity-process { background-color: #f3e5f5; }
    .citation {
        background-color: #f5f5f5;
        padding: 4px 8px;
        border-radius: 4px;
        font-family: monospace;
    }
    .score-badge {
        background-color: #e0e0e0;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.8em;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def load_system():
    """Load all system components (cached)."""
    # Load patents data
    with open(Config.PATENTS_JSON, "r") as f:
        patents_data = json.load(f)
    
    # Flatten chunks
    all_chunks = []
    for patent in patents_data["patents"]:
        all_chunks.extend(patent["chunks"])
    
    # Load retrievers
    bm25 = BM25Retriever.load(Config.BM25_INDEX, all_chunks)
    semantic = SemanticRetriever.load(
        Config.FAISS_INDEX,
        Config.CHUNK_IDS,
        all_chunks,
    )
    
    # Load KG
    kg_store = KnowledgeGraphStore(Config.KG_DATABASE)
    kg_store.connect()
    graph = GraphRetriever(kg_store, all_chunks)
    
    # Build hybrid retriever
    hybrid = HybridRetriever(bm25, semantic, graph, all_chunks)
    
    # Load LLM generator
    generator = AnswerGenerator(
        llm_provider=Config.LLM_PROVIDER,
        **Config.LLM_CONFIG,
    )
    
    return hybrid, generator, patents_data, all_chunks


# Load system
retriever, generator, patents_data, all_chunks = load_system()

# Sidebar
with st.sidebar:
    st.header("📁 Patent Selection")
    all_patent_ids = [p["patent_id"] for p in patents_data["patents"]]
    selected_patents = st.multiselect(
        "Select patents to search:",
        options=all_patent_ids,
        default=all_patent_ids,
    )
    
    st.header("⚙️ Search Settings")
    top_k = st.slider("Results to retrieve:", 3, 10, 5)
    
    with st.expander("🎛️ Retrieval Weights"):
        bm25_weight = st.slider("BM25 (keyword)", 0.0, 1.0, 0.35)
        semantic_weight = st.slider("Semantic", 0.0, 1.0, 0.35)
        graph_weight = st.slider("Knowledge Graph", 0.0, 1.0, 0.30)
    
    st.header("📊 System Stats")
    col1, col2 = st.columns(2)
    col1.metric("Patents", len(patents_data["patents"]))
    col2.metric("Chunks", len(all_chunks))
    
    st.caption(f"LLM: {Config.LLM_PROVIDER}")

# Main content
st.title("🔬 Patent Search Demo")
st.markdown("Ask questions about steel manufacturing patents with Knowledge Graph-enhanced retrieval.")

# Query input
query = st.text_input(
    "💬 Ask a question:",
    placeholder="e.g., What Si content is needed for yield stress above 700 MPa?",
)

# Example questions
if not query:
    st.subheader("💡 Example questions:")
    examples = [
        "What is the optimal Si content for high yield stress?",
        "What annealing temperatures are recommended?",
        "How does Cr content affect core loss?",
        "What are the cold rolling parameters for electrical steel?",
    ]
    cols = st.columns(2)
    for i, q in enumerate(examples):
        if cols[i % 2].button(q, key=f"ex_{i}"):
            query = q
            st.rerun()

# Search
if st.button("🔍 Search", type="primary") or query:
    if query:
        # Retrieval
        with st.spinner("🔍 Searching patents..."):
            chunks = retriever.search(
                query,
                top_k=top_k,
                patent_filter=selected_patents if len(selected_patents) < len(all_patent_ids) else None,
                bm25_weight=bm25_weight,
                semantic_weight=semantic_weight,
                graph_weight=graph_weight,
            )
        
        if not chunks:
            st.warning("No relevant content found. Try a different question.")
        else:
            # Generation
            with st.spinner("🤖 Generating answer..."):
                result = generator.generate(query, chunks)
            
            # Display answer
            st.subheader("📝 Answer")
            st.markdown(result["answer"])
            
            # Display sources
            st.subheader("📚 Sources")
            for i, chunk in enumerate(chunks, 1):
                meta = chunk.get("metadata", {})
                
                # Build header with scores
                header = f"{i}. {chunk['patent_id']} | {meta.get('section', 'Unknown')} | Page {meta.get('page', '?')}"
                
                with st.expander(header, expanded=(i <= 2)):
                    # Scores
                    score_cols = st.columns(4)
                    score_cols[0].metric("Hybrid", f"{chunk.get('hybrid_score', 0):.4f}")
                    score_cols[1].metric("BM25", f"#{chunk.get('bm25_rank', '-')}")
                    score_cols[2].metric("Semantic", f"#{chunk.get('semantic_rank', '-')}")
                    score_cols[3].metric("Graph", f"#{chunk.get('graph_rank', '-')}")
                    
                    # Entities
                    entities = chunk.get("matched_entities", [])
                    if entities:
                        st.markdown("**🏷️ Matched Entities:**")
                        entity_html = ""
                        for e in entities[:8]:
                            etype = e.get("type", "")
                            css_class = f"entity-{etype}" if etype in ["element", "property", "process"] else ""
                            entity_html += f'<span class="entity-tag {css_class}">{e.get("name", "")}</span>'
                        st.markdown(entity_html, unsafe_allow_html=True)
                    
                    # Content
                    st.markdown("**📄 Content:**")
                    content = chunk["content"]
                    if len(content) > 500:
                        content = content[:500] + "..."
                    st.markdown(content)
            
            # Debug info
            with st.expander("🔧 Debug Info"):
                st.json({
                    "model": result["model"],
                    "chunks_used": result["chunks_used"],
                    "input_tokens": result.get("input_tokens"),
                    "output_tokens": result.get("output_tokens"),
                })
```

### 5.2 Configuration (`config.py`)

```python
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration."""
    
    # Paths
    BASE_DIR = Path(__file__).parent
    DATA_DIR = BASE_DIR / "data"
    RAW_DIR = DATA_DIR / "raw"
    PROCESSED_DIR = DATA_DIR / "processed"
    
    PATENTS_JSON = PROCESSED_DIR / "patents.json"
    BM25_INDEX = PROCESSED_DIR / "bm25_index.pkl"
    FAISS_INDEX = PROCESSED_DIR / "faiss.index"
    CHUNK_IDS = PROCESSED_DIR / "chunk_ids.json"
    KG_DATABASE = PROCESSED_DIR / "knowledge_graph.db"
    
    # LLM Configuration
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")  # "bedrock" or "ollama"
    
    # Bedrock config
    BEDROCK_MODEL = os.getenv("BEDROCK_MODEL", "anthropic.claude-3-sonnet-20240229-v1:0")
    BEDROCK_REGION = os.getenv("BEDROCK_REGION", "us-east-1")
    
    # Ollama config
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    
    @classmethod
    @property
    def LLM_CONFIG(cls) -> dict:
        """Get LLM configuration based on provider."""
        if cls.LLM_PROVIDER == "bedrock":
            return {
                "model_id": cls.BEDROCK_MODEL,
                "region": cls.BEDROCK_REGION,
            }
        else:
            return {
                "model": cls.OLLAMA_MODEL,
                "base_url": cls.OLLAMA_BASE_URL,
            }
```

---

## Phase 6: Scripts & Documentation

### 6.1 Extraction Script (`scripts/extract_patents.py`)

```python
#!/usr/bin/env python3
"""Extract patents, build chunks, entities, and all indices."""

import json
from pathlib import Path
from tqdm import tqdm

from src.extraction.pdf_parser import PatentPDFParser
from src.extraction.chunker import PatentChunker
from src.extraction.entity_extractor import EntityExtractor
from src.knowledge_graph.builder import KnowledgeGraphBuilder
from src.knowledge_graph.store import KnowledgeGraphStore
from src.retrieval.bm25_retriever import BM25Retriever
from src.retrieval.semantic_retriever import SemanticRetriever
from config import Config


def main():
    # Ensure directories exist
    Config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    
    # Initialize components
    parser = PatentPDFParser()
    chunker = PatentChunker()
    entity_extractor = EntityExtractor()
    kg_builder = KnowledgeGraphBuilder()
    
    # Process PDFs
    pdf_files = list(Config.RAW_DIR.glob("*.pdf"))
    print(f"Found {len(pdf_files)} PDF files")
    
    patents = []
    all_chunks = []
    
    for pdf_path in tqdm(pdf_files, desc="Extracting PDFs"):
        # Extract
        patent_data = parser.extract(str(pdf_path))
        
        # Chunk
        chunks = chunker.chunk_patent(patent_data)
        
        # Extract entities from each chunk
        for chunk in chunks:
            entities = entity_extractor.extract_entities(chunk)
            chunk.entities = entities
            kg_builder.add_entities(entities)
        
        patent_data["chunks"] = [chunk.__dict__ for chunk in chunks]
        patents.append(patent_data)
        all_chunks.extend(chunks)
    
    # Build relationships
    print("Building knowledge graph relationships...")
    kg_builder.build_relationships(all_chunks)
    
    # Save patents.json
    print("Saving patents.json...")
    output = {
        "patents": patents,
        "total_chunks": len(all_chunks),
        "extraction_config": {
            "chunk_size": 500,
            "overlap": 50,
        },
    }
    with open(Config.PATENTS_JSON, "w") as f:
        json.dump(output, f, indent=2, default=str)
    
    # Save knowledge graph
    print("Saving knowledge graph...")
    kg_store = KnowledgeGraphStore(str(Config.KG_DATABASE))
    kg_store.connect()
    kg_data = kg_builder.export()
    for entity in tqdm(kg_data["entities"].values(), desc="Saving entities"):
        kg_store.save_entity(entity)
    for rel in tqdm(kg_data["relationships"], desc="Saving relationships"):
        kg_store.save_relationship(rel)
    kg_store.close()
    
    # Build BM25 index
    print("Building BM25 index...")
    chunk_dicts = [c.__dict__ for c in all_chunks]
    bm25 = BM25Retriever()
    bm25.build_index(chunk_dicts)
    bm25.save(str(Config.BM25_INDEX))
    
    # Build FAISS index
    print("Building FAISS index (this may take a while)...")
    semantic = SemanticRetriever()
    semantic.build_index(chunk_dicts)
    semantic.save(str(Config.FAISS_INDEX), str(Config.CHUNK_IDS))
    
    print("\n✅ Extraction complete!")
    print(f"   Patents: {len(patents)}")
    print(f"   Chunks: {len(all_chunks)}")
    print(f"   Entities: {len(kg_data['entities'])}")
    print(f"   Relationships: {len(kg_data['relationships'])}")


if __name__ == "__main__":
    main()
```

### 6.2 Requirements (`requirements.txt`)

```
# PDF Processing
unstructured[pdf]==0.12.0
pdfplumber==0.10.3
tiktoken==0.5.2

# Knowledge Graph
networkx==3.2.1

# Retrieval
rank-bm25==0.2.2
sentence-transformers==2.3.1
faiss-cpu==1.7.4
nltk==3.8.1

# LLM - Bedrock
boto3==1.34.0

# LLM - Ollama
requests==2.31.0

# UI
streamlit==1.31.0

# Utilities
python-dotenv==1.0.0
tqdm==4.66.1
numpy==1.26.3
```

### 6.3 Environment Template (`.env.example`)

```bash
# LLM Provider: "bedrock" or "ollama"
LLM_PROVIDER=ollama

# Ollama settings (if using Ollama)
OLLAMA_MODEL=llama3.2
OLLAMA_BASE_URL=http://localhost:11434

# Bedrock settings (if using Bedrock)
BEDROCK_MODEL=anthropic.claude-3-sonnet-20240229-v1:0
BEDROCK_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
```

---

## Implementation Order

### Stage 1
1. Project structure setup
2. `requirements.txt`
3. `pdf_parser.py` - PDF extraction
4. `chunker.py` - Chunking logic
5. `entity_extractor.py` - Entity extraction
6. Test extraction on 2-3 patents

### Stage 2
7. `schema.py` - KG schema
8. `builder.py` - KG builder
9. `store.py` - SQLite storage
10. `traversal.py` - Graph queries
11. `bm25_retriever.py`
12. `semantic_retriever.py`

### Stage 3
13. `graph_retriever.py`
14. `hybrid_retriever.py`
15. `base.py`, `bedrock.py`, `ollama.py` - LLM abstraction
16. `generator.py` - Answer generation
17. Test end-to-end retrieval + generation

### Stage 4
18. `app.py` - Streamlit UI
19. `config.py` - Configuration
20. UI polish (loading, errors, styling)
21. `extract_patents.py` - Full pipeline script

### Stage 5
22. Run full extraction on all 10 patents
23. End-to-end testing
24. Bug fixes
25. README.md
26. Final polish

---

## Success Criteria

1. ✅ Layout-aware PDF extraction handles multi-column patents
2. ✅ Knowledge graph captures entities and relationships
3. ✅ Hybrid retrieval combines BM25 + semantic + graph
4. ✅ LLM generates answers with proper citations
5. ✅ UI shows entities, scores, and sources clearly
6. ✅ Supports both Bedrock and Ollama
7. ✅ Runs locally with simple setup
8. ✅ No visible bugs in demo flow
