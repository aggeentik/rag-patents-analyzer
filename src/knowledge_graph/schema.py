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
    INVENTOR = "inventor"
    ASSIGNEE = "assignee"
    PATENT_REFERENCE = "patent_reference"
    APPLICATION = "application"
    MATERIAL = "material"
    PROBLEM = "problem"
    SOLUTION = "solution"
    PATENT_DOC_REFERENCE = "patent_doc_reference"


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
    CITES = "cites"
    ADDRESSES_PROBLEM = "addresses_problem"
    USED_FOR = "used_for"
    INVENTED_BY = "invented_by"
    ASSIGNEE_OF = "assignee_of"


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


class PatentMeta(BaseModel):
    """Patent-level metadata extracted from a chunk."""

    inventors: list[str] = Field(default_factory=list, description="Inventor names")
    assignees: list[str] = Field(default_factory=list, description="Assignee / applicant names")
    cited_patents: list[str] = Field(
        default_factory=list, description="Cited patent numbers, e.g. 'US 7,234,567'"
    )
    applications: list[str] = Field(
        default_factory=list, description="Use-case / application domains, e.g. 'electric vehicles'"
    )
    materials: list[str] = Field(
        default_factory=list, description="Named materials / alloy types, e.g. 'grain-oriented electrical steel'"
    )
    problems: list[str] = Field(
        default_factory=list, description="Problems or limitations of prior art"
    )
    solutions: list[str] = Field(
        default_factory=list, description="Advantages or solutions provided by the invention"
    )


class ChunkExtractionResult(BaseModel):
    """Structured extraction result from a single chunk (used by Instructor)."""

    compositions: list[ChemicalComposition] = Field(default_factory=list)
    properties: list[PropertyMeasurement] = Field(default_factory=list)
    processes: list[ProcessStep] = Field(default_factory=list)
    patent_meta: PatentMeta = Field(default_factory=PatentMeta)


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
    "La": "Lanthanum",
    "Ce": "Cerium",
    "Nd": "Neodymium",
    "Y": "Yttrium",
    "Ca": "Calcium",
    "Bi": "Bismuth",
    "Sn": "Tin",
    "Sb": "Antimony",
    "Mg": "Magnesium",
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

APPLICATIONS = {
    "electric_vehicle": ["electric vehicle", "EV", "electric car", "electric motor vehicle"],
    "transformer": ["transformer", "power transformer", "distribution transformer"],
    "electric_motor": ["electric motor", "motor core", "rotating machine"],
    "generator": ["generator", "power generator", "wind turbine generator"],
    "inductor": ["inductor", "reactor", "choke coil"],
    "sensor": ["sensor", "magnetic sensor"],
    "energy_storage": ["energy storage", "battery", "fuel cell"],
    "power_electronics": ["power electronics", "inverter", "converter"],
}

MATERIALS = {
    "grain_oriented_electrical_steel": [
        "grain-oriented electrical steel",
        "grain oriented electrical steel",
        "GO steel",
        "GO electrical steel",
    ],
    "non_oriented_electrical_steel": [
        "non-oriented electrical steel",
        "non oriented electrical steel",
        "NO steel",
        "NO electrical steel",
    ],
    "electrical_steel_sheet": ["electrical steel sheet", "magnetic steel sheet"],
    "silicon_steel": ["silicon steel", "Si steel", "Fe-Si"],
    "high_strength_steel": ["high strength steel", "high-strength steel", "HSLA steel"],
    "stainless_steel": ["stainless steel", "austenitic stainless", "ferritic stainless"],
    "carbon_steel": ["carbon steel", "low carbon steel", "ultra-low carbon steel"],
    "rare_earth_metal": [
        "rare earth metal", "rare earth metals", "REM", "REMs",
        "rare earth element", "rare earth elements", "REE",
        "REM oxysulfide", "REM oxysulfides",
    ],
}
