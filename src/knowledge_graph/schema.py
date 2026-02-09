"""Knowledge graph schema definitions for patent entities and relationships.

All models use Pydantic BaseModel for validation and serialization.
"""

from enum import Enum

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


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

    CONTAINS = "contains"
    HAS_VALUE = "has_value"
    AFFECTS = "affects"
    REQUIRES = "requires"
    ACHIEVED_IN = "achieved_in"
    MEASURED_IN = "measured_in"
    DESCRIBED_IN = "described_in"
    SHOWN_IN = "shown_in"
    SATISFIES = "satisfies"
    REFERENCES = "references"
    MENTIONS = "mentions"
    NEXT_STEP = "next_step"


class PatentSection(Enum):
    """Sections of a patent document."""

    PREAMBLE = "preamble"
    ABSTRACT = "abstract"
    CLAIMS = "claims"
    BACKGROUND = "background"
    DESCRIPTION = "description"
    EXAMPLES = "examples"
    EMBODIMENTS = "embodiments"
    FIGURES = "figures"


# ---------------------------------------------------------------------------
# Instructor extraction models (used by LLM-based entity extraction)
# ---------------------------------------------------------------------------


class ChemicalComposition(BaseModel):
    """A chemical element with its composition range."""

    element: str = Field(description="Chemical symbol, e.g. 'Si', 'Cr'")
    min_val: float | None = Field(default=None, description="Minimum value")
    max_val: float | None = Field(default=None, description="Maximum value")
    unit: str = Field(default="%", description="Unit of measurement")


class PropertyMeasurement(BaseModel):
    """A measured material property."""

    name: str = Field(description="Property name, e.g. 'yield_stress'")
    value: float | None = Field(default=None, description="Measured value")
    unit: str | None = Field(default=None, description="Unit, e.g. 'MPa'")
    condition: str | None = Field(default=None, description="Measurement condition")


class ProcessStep(BaseModel):
    """A manufacturing process step."""

    name: str = Field(description="Process name, e.g. 'annealing'")
    temperature: str | None = Field(default=None, description="Temperature, e.g. '1100 C'")
    duration: str | None = Field(default=None, description="Duration, e.g. '30 min'")
    parameters: dict = Field(default_factory=dict, description="Additional parameters")


class ChunkExtractionResult(BaseModel):
    """Structured extraction result from a single chunk (used by Instructor)."""

    compositions: list[ChemicalComposition] = Field(default_factory=list)
    properties: list[PropertyMeasurement] = Field(default_factory=list)
    processes: list[ProcessStep] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Reference model
# ---------------------------------------------------------------------------


class StructuredReference(BaseModel):
    """A resolved cross-reference found in chunk text."""

    raw_text: str = Field(description="Original text, e.g. 'Table 1'")
    ref_type: EntityType = Field(description="TABLE, FORMULA, or FIGURE")
    ref_id: str = Field(description="Resolved ID, e.g. 'EP1577413_TABLE_01'")


# ---------------------------------------------------------------------------
# Document models
# ---------------------------------------------------------------------------


class PatentChunk(BaseModel):
    """A single chunk ready for retrieval."""

    chunk_id: str = ""
    patent_id: str = ""
    content: str = ""
    section: str = "unknown"
    page: int = 1
    chunk_type: str = "paragraph"  # paragraph, table, formula, claim
    references: list[StructuredReference] = Field(default_factory=list)
    entities: list = Field(default_factory=list)  # populated after extraction

    def to_retrieval_dict(self) -> dict:
        """Serialize for patents.json and retrieval indices."""
        return {
            "chunk_id": self.chunk_id,
            "patent_id": self.patent_id,
            "content": self.content,
            "metadata": {
                "section": self.section,
                "page": self.page,
                "type": self.chunk_type,
            },
            "entities": [
                {
                    "id": e.id,
                    "type": e.type.value if hasattr(e.type, "value") else str(e.type),
                    "name": e.name,
                    "properties": e.properties,
                }
                for e in self.entities
            ],
            "references": [
                {
                    "raw_text": r.raw_text,
                    "ref_type": r.ref_type.value,
                    "ref_id": r.ref_id,
                }
                for r in self.references
            ],
        }


class PatentDocument(BaseModel):
    """Parsed patent document produced by the PDF parser."""

    patent_id: str = ""
    title: str = "Unknown Title"
    sections: dict[str, str] = Field(default_factory=dict)  # section_name -> text
    tables_markdown: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# KG models (Pydantic replacements for old dataclasses)
# ---------------------------------------------------------------------------


class Entity(BaseModel):
    """Knowledge graph entity."""

    id: str
    type: EntityType
    name: str
    properties: dict = Field(default_factory=dict)
    patent_id: str = ""
    chunk_ids: list[str] = Field(default_factory=list)


class Relationship(BaseModel):
    """Knowledge graph relationship."""

    id: str
    type: RelationType
    source_id: str
    target_id: str
    properties: dict = Field(default_factory=dict)
    patent_id: str = ""
    chunk_id: str | None = None


# ---------------------------------------------------------------------------
# Predefined entity vocabularies (unchanged)
# ---------------------------------------------------------------------------

CHEMICAL_ELEMENTS = {
    "Si": "Silicon",
    "Cr": "Chromium",
    "Mn": "Manganese",
    "Al": "Aluminum",
    "Cu": "Copper",
    "Ni": "Nickel",
    "Ti": "Titanium",
    "Nb": "Niobium",
    "V": "Vanadium",
    "Zr": "Zirconium",
    "C": "Carbon",
    "N": "Nitrogen",
    "S": "Sulfur",
    "P": "Phosphorus",
    "Mo": "Molybdenum",
    "B": "Boron",
    "Fe": "Iron",
    "Co": "Cobalt",
}

PROPERTIES = {
    "yield_stress": ["yield stress", "yield strength", "\u03c3y"],
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
