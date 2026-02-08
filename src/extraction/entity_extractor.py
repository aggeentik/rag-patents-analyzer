"""Hybrid entity extraction from patent text.

Supports two modes:
- **Regex-only (default):**  Fast, no external dependencies beyond the codebase.
- **LLM + Instructor:**      Uses ``instructor`` with ``litellm.completion``
  to extract structured ``ChunkExtractionResult`` per chunk.

Table / Formula / Figure / Sample references are always extracted via regex.
"""

import re
from typing import Optional

from src.knowledge_graph.schema import (
    CHEMICAL_ELEMENTS,
    PROCESSES,
    PROPERTIES,
    ChunkExtractionResult,
    Entity,
    EntityType,
    PatentChunk,
)


class EntityExtractor:
    """Extract entities from PatentChunk objects.

    Args:
        llm_client: Optional ``LLMClient`` instance.  When provided **and**
            ``use_llm`` is True, the extractor will use Instructor to call
            the LLM for structured extraction.
        use_llm: Whether to actually invoke the LLM. Defaults to False
            (regex-only).
    """

    # ---- compiled regex patterns ----
    PERCENTAGE_PATTERN = re.compile(
        r"(\d+\.?\d*)\s*(%|mass\s*%|wt\s*%)", re.IGNORECASE
    )
    TEMPERATURE_PATTERN = re.compile(r"(\d+)\s*°?C")
    RANGE_PATTERN = re.compile(
        r"(\d+\.?\d*)\s*(?:to|-)\s*(\d+\.?\d*)\s*(%|°C|MPa|T)", re.IGNORECASE
    )
    TABLE_RE = re.compile(r"Table\s*(\d+)", re.IGNORECASE)
    FORMULA_RE = re.compile(r"Formula\s*\((\d+)\)", re.IGNORECASE)
    FIGURE_RE = re.compile(r"FIG\.?\s*(\d+)|Figure\s*(\d+)", re.IGNORECASE)
    SAMPLE_RE = re.compile(r"(?:Sample|Symbol|Material)\s+([a-zA-Z]\d+)")

    def __init__(self, llm_client=None, use_llm: bool = False):
        self._llm_client = llm_client
        self._use_llm = use_llm and llm_client is not None
        self._instructor_client = None

        if self._use_llm:
            self._init_instructor()

    def _init_instructor(self):
        """Lazily initialise the Instructor-wrapped LiteLLM client."""
        try:
            import instructor
            import litellm
            self._instructor_client = instructor.from_litellm(litellm.completion)
        except ImportError:
            print("Warning: instructor not installed, falling back to regex-only extraction")
            self._use_llm = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_entities(self, chunk: PatentChunk) -> list[Entity]:
        """Extract all entities from a single chunk.

        If LLM mode is active, structured extraction runs first and its
        results are merged with regex results.  Otherwise only regex runs.
        """
        entities: list[Entity] = []
        text = chunk.content

        # LLM-based extraction (optional)
        if self._use_llm and self._instructor_client:
            llm_entities = self._extract_with_llm(text, chunk)
            entities.extend(llm_entities)

        # Regex-based extraction (always runs)
        entities.extend(self._extract_chemical_elements(text, chunk))
        entities.extend(self._extract_properties(text, chunk))
        entities.extend(self._extract_processes(text, chunk))
        entities.extend(self._extract_references(text, chunk))
        entities.extend(self._extract_samples(text, chunk))

        return entities

    # ------------------------------------------------------------------
    # LLM extraction via Instructor
    # ------------------------------------------------------------------

    def _extract_with_llm(self, text: str, chunk: PatentChunk) -> list[Entity]:
        """Use Instructor to extract structured data from chunk text."""
        entities: list[Entity] = []

        try:
            result: ChunkExtractionResult = self._instructor_client.chat.completions.create(
                model=self._llm_client.model,
                response_model=ChunkExtractionResult,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Extract chemical compositions, material properties, "
                            "and process steps from this patent text. "
                            "Return only what is explicitly stated."
                        ),
                    },
                    {"role": "user", "content": text},
                ],
                temperature=0.0,
                max_tokens=1024,
            )
        except Exception as e:
            print(f"  LLM extraction failed for {chunk.chunk_id}: {e}")
            return entities

        # Convert compositions -> Entity
        for comp in result.compositions:
            entity = Entity(
                id=f"{chunk.patent_id}_{comp.element}_llm_{len(entities)}",
                type=EntityType.CHEMICAL_ELEMENT,
                name=comp.element,
                properties={
                    "value_min": comp.value_min,
                    "value_max": comp.value_max,
                    "unit": comp.unit,
                    "source": "llm",
                },
                patent_id=chunk.patent_id,
                chunk_ids=[chunk.chunk_id],
            )
            entities.append(entity)

        # Convert properties -> Entity
        for prop in result.properties:
            entity = Entity(
                id=f"{chunk.patent_id}_{prop.name}_llm_{len(entities)}",
                type=EntityType.PROPERTY,
                name=prop.name,
                properties={
                    "value": prop.value,
                    "unit": prop.unit,
                    "condition": prop.condition,
                    "source": "llm",
                },
                patent_id=chunk.patent_id,
                chunk_ids=[chunk.chunk_id],
            )
            entities.append(entity)

        # Convert processes -> Entity
        for proc in result.processes:
            entity = Entity(
                id=f"{chunk.patent_id}_{proc.name}_llm_{len(entities)}",
                type=EntityType.PROCESS,
                name=proc.name,
                properties={
                    "temperature": proc.temperature,
                    "duration": proc.duration,
                    **proc.parameters,
                    "source": "llm",
                },
                patent_id=chunk.patent_id,
                chunk_ids=[chunk.chunk_id],
            )
            entities.append(entity)

        return entities

    # ------------------------------------------------------------------
    # Regex extraction (unchanged logic, adapted for PatentChunk)
    # ------------------------------------------------------------------

    def _extract_chemical_elements(self, text: str, chunk: PatentChunk) -> list[Entity]:
        entities: list[Entity] = []
        for symbol, name in CHEMICAL_ELEMENTS.items():
            # Exact value pattern
            pattern = rf"\b{symbol}\s*[:=]?\s*(\d+\.?\d*)\s*(%|mass\s*%|wt\s*%)"
            for match in re.finditer(pattern, text, re.IGNORECASE):
                value = float(match.group(1))
                unit = match.group(2)
                entities.append(Entity(
                    id=f"{chunk.patent_id}_{symbol}_{len(entities)}",
                    type=EntityType.CHEMICAL_ELEMENT,
                    name=symbol,
                    properties={"full_name": name, "value": value, "unit": unit},
                    patent_id=chunk.patent_id,
                    chunk_ids=[chunk.chunk_id],
                ))

            # Range pattern
            range_pattern = rf"\b{symbol}\s*[:=]?\s*(\d+\.?\d*)\s*(?:to|-)\s*(\d+\.?\d*)\s*(%|mass\s*%)"
            for match in re.finditer(range_pattern, text, re.IGNORECASE):
                entities.append(Entity(
                    id=f"{chunk.patent_id}_{symbol}_range_{len(entities)}",
                    type=EntityType.COMPOSITION_RANGE,
                    name=f"{symbol}_range",
                    properties={
                        "element": symbol,
                        "min_value": float(match.group(1)),
                        "max_value": float(match.group(2)),
                        "unit": "%",
                    },
                    patent_id=chunk.patent_id,
                    chunk_ids=[chunk.chunk_id],
                ))
        return entities

    def _extract_properties(self, text: str, chunk: PatentChunk) -> list[Entity]:
        entities: list[Entity] = []
        for prop_id, aliases in PROPERTIES.items():
            for alias in aliases:
                if alias.lower() in text.lower():
                    pattern = rf"{re.escape(alias)}\s*(?:of|:)?\s*(\d+)\s*(MPa|%|T|W/kg)"
                    match = re.search(pattern, text, re.IGNORECASE)
                    properties = {"alias": alias}
                    if match:
                        properties["value"] = float(match.group(1))
                        properties["unit"] = match.group(2)
                    entities.append(Entity(
                        id=f"{chunk.patent_id}_{prop_id}_{len(entities)}",
                        type=EntityType.PROPERTY,
                        name=prop_id,
                        properties=properties,
                        patent_id=chunk.patent_id,
                        chunk_ids=[chunk.chunk_id],
                    ))
                    break
        return entities

    def _extract_processes(self, text: str, chunk: PatentChunk) -> list[Entity]:
        entities: list[Entity] = []
        for process_id, aliases in PROCESSES.items():
            for alias in aliases:
                if alias.lower() in text.lower():
                    temp_pattern = rf"{re.escape(alias)}.*?(\d+)\s*°?C"
                    temp_match = re.search(temp_pattern, text, re.IGNORECASE)
                    properties = {"alias": alias}
                    if temp_match:
                        properties["temperature"] = int(temp_match.group(1))
                        properties["temperature_unit"] = "°C"
                    entities.append(Entity(
                        id=f"{chunk.patent_id}_{process_id}_{len(entities)}",
                        type=EntityType.PROCESS,
                        name=process_id,
                        properties=properties,
                        patent_id=chunk.patent_id,
                        chunk_ids=[chunk.chunk_id],
                    ))
                    break
        return entities

    def _extract_references(self, text: str, chunk: PatentChunk) -> list[Entity]:
        entities: list[Entity] = []

        for match in self.TABLE_RE.finditer(text):
            table_num = match.group(1)
            entities.append(Entity(
                id=f"{chunk.patent_id}_table_{table_num}",
                type=EntityType.TABLE,
                name=f"Table {table_num}",
                properties={"table_number": int(table_num)},
                patent_id=chunk.patent_id,
                chunk_ids=[chunk.chunk_id],
            ))

        for match in self.FORMULA_RE.finditer(text):
            formula_num = match.group(1)
            entities.append(Entity(
                id=f"{chunk.patent_id}_formula_{formula_num}",
                type=EntityType.FORMULA,
                name=f"Formula {formula_num}",
                properties={"formula_number": int(formula_num)},
                patent_id=chunk.patent_id,
                chunk_ids=[chunk.chunk_id],
            ))

        for match in self.FIGURE_RE.finditer(text):
            fig_num = match.group(1) or match.group(2)
            entities.append(Entity(
                id=f"{chunk.patent_id}_figure_{fig_num}",
                type=EntityType.FIGURE,
                name=f"Figure {fig_num}",
                properties={"figure_number": int(fig_num)},
                patent_id=chunk.patent_id,
                chunk_ids=[chunk.chunk_id],
            ))

        return entities

    def _extract_samples(self, text: str, chunk: PatentChunk) -> list[Entity]:
        entities: list[Entity] = []
        for match in self.SAMPLE_RE.finditer(text):
            sample_id = match.group(1)
            entities.append(Entity(
                id=f"{chunk.patent_id}_sample_{sample_id}",
                type=EntityType.SAMPLE,
                name=f"Sample {sample_id}",
                properties={"sample_id": sample_id},
                patent_id=chunk.patent_id,
                chunk_ids=[chunk.chunk_id],
            ))
        return entities
