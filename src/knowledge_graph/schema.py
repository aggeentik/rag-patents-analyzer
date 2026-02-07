"""Knowledge graph schema definitions for patent entities and relationships."""

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
