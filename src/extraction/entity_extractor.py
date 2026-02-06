"""Rule-based entity extraction from patent text."""

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

    def _compile_patterns(self):
        """Compile regex patterns for efficiency."""
        self.percentage_re = re.compile(self.PERCENTAGE_PATTERN)
        self.temperature_re = re.compile(self.TEMPERATURE_PATTERN)
        self.range_re = re.compile(self.RANGE_PATTERN)
        self.mpa_re = re.compile(self.MPa_PATTERN)
        self.table_re = re.compile(self.TABLE_PATTERN, re.IGNORECASE)
        self.formula_re = re.compile(self.FORMULA_PATTERN, re.IGNORECASE)
        self.sample_re = re.compile(self.SAMPLE_PATTERN)

    def extract_entities(self, chunk) -> list[Entity]:
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

    def _extract_chemical_elements(self, text: str, chunk) -> list[Entity]:
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

    def _extract_properties(self, text: str, chunk) -> list[Entity]:
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

    def _extract_processes(self, text: str, chunk) -> list[Entity]:
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

    def _extract_references(self, text: str, chunk) -> list[Entity]:
        """Extract table, formula, and figure references."""
        entities = []

        # Tables
        for match in self.table_re.finditer(text):
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
        for match in self.formula_re.finditer(text):
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

    def _extract_samples(self, text: str, chunk) -> list[Entity]:
        """Extract sample/material identifiers."""
        entities = []

        for match in self.sample_re.finditer(text):
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
