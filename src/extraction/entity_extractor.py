"""Hybrid entity extraction from patent text.

Supports two modes:
- **Regex-only (default):**  Fast, no external dependencies beyond the codebase.
- **LLM + Instructor:**      Uses ``instructor`` with ``litellm.completion``
  to extract structured ``ChunkExtractionResult`` per chunk.

Table / Formula / Figure / Sample references are always extracted via regex.
"""

import logging
import re
from typing import ClassVar

from src.knowledge_graph.schema import (
    APPLICATIONS,
    CHEMICAL_ELEMENTS,
    MATERIALS,
    PROCESSES,
    PROPERTIES,
    ChunkExtractionResult,
    Entity,
    EntityType,
    PatentChunk,
)

logger = logging.getLogger(__name__)


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
    PERCENTAGE_PATTERN = re.compile(r"(\d+\.?\d*)\s*(%|mass\s*%|wt\s*%)", re.IGNORECASE)
    TEMPERATURE_PATTERN = re.compile(r"(\d+)\s*°?C")
    RANGE_PATTERN = re.compile(
        r"(\d+\.?\d*)\s*(?:to|-)\s*(\d+\.?\d*)\s*(%|°C|MPa|T)", re.IGNORECASE
    )
    TABLE_RE = re.compile(r"Table\s*(\d+)", re.IGNORECASE)
    FORMULA_RE = re.compile(r"Formula\s*\((\d+)\)", re.IGNORECASE)
    FIGURE_RE = re.compile(r"FIG\.?\s*(\d+)|Figure\s*(\d+)", re.IGNORECASE)
    SAMPLE_RE = re.compile(r"(?:Sample|Symbol|Material)\s+([a-zA-Z]\d+)")

    # Patent-intelligence patterns
    PATENT_REF_RE = re.compile(
        r"(?:US|EP|WO|JP|CN|KR|DE|GB|FR)\s*[\d,./\-]{4,}(?:\s*[AB]\d)?\b",
        re.IGNORECASE,
    )
    INVENTOR_RE = re.compile(r"[Ii]nventor(?:s)?\s*[:;]\s*(.+?)(?:\n|$)")
    ASSIGNEE_RE = re.compile(r"(?:[Aa]ssignee|[Aa]pplicant)(?:s)?\s*[:;]\s*(.+?)(?:\n|$)")
    PATENT_DOC_RE = re.compile(
        r"Patent\s+(?:Document|Literature|Lit\.?)\s+(\d+)",
        re.IGNORECASE,
    )

    PROBLEM_PHRASES: ClassVar[list[str]] = [
        "problem",
        "drawback",
        "disadvantage",
        "limitation",
        "difficulty",
        "deficiency",
        "shortcoming",
        "insufficient",
    ]
    SOLUTION_PHRASES: ClassVar[list[str]] = [
        "the present invention provides",
        "advantage of the invention",
        "object of the invention",
        "the invention overcomes",
        "the invention solves",
        "according to the present invention",
        "an object of the present invention",
    ]

    def __init__(self, llm_client=None, use_llm: bool = False):
        self._llm_client = llm_client
        self._use_llm = use_llm and llm_client is not None
        self._instructor_client = None

        if self._use_llm:
            self._init_instructor()

    def _init_instructor(self):
        """Lazily initialise the Instructor-wrapped LiteLLM client."""
        try:
            import instructor  # noqa: PLC0415
            import litellm  # noqa: PLC0415

            self._instructor_client = instructor.from_litellm(litellm.completion)
        except ImportError:
            logger.warning("instructor not installed, falling back to regex-only extraction")
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
        entities.extend(self._extract_patent_references(text, chunk))
        entities.extend(self._extract_inventors(text, chunk))
        entities.extend(self._extract_assignees(text, chunk))
        entities.extend(self._extract_applications(text, chunk))
        entities.extend(self._extract_materials(text, chunk))
        entities.extend(self._extract_patent_doc_references(text, chunk))
        entities.extend(self._extract_problems(text, chunk))
        entities.extend(self._extract_solutions(text, chunk))

        return entities

    # ------------------------------------------------------------------
    # LLM extraction via Instructor
    # ------------------------------------------------------------------

    def _extract_with_llm(self, text: str, chunk: PatentChunk) -> list[Entity]:
        """Use Instructor to extract structured data from chunk text."""
        entities: list[Entity] = []

        try:
            assert self._instructor_client is not None, "Instructor client not initialized"
            result: ChunkExtractionResult = self._instructor_client.chat.completions.create(
                model=self._llm_client.model,
                response_model=ChunkExtractionResult,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Extract chemical compositions, material properties, "
                            "process steps, and patent metadata from this patent text. "
                            "Patent metadata includes: inventor names, assignee/applicant "
                            "names, cited patent numbers, application domains (use cases), "
                            "material/alloy names, problems or limitations of prior art, "
                            "and advantages or solutions of the invention. "
                            "Return only what is explicitly stated."
                        ),
                    },
                    {"role": "user", "content": text},
                ],
                temperature=0.0,
                max_tokens=1024,
            )
        except Exception as e:
            logger.warning("LLM extraction failed for %s: %s", chunk.chunk_id, e)
            return entities

        # Convert compositions -> Entity
        for comp in result.compositions:
            entity = Entity(
                id=f"{chunk.patent_id}_{comp.element}_llm_{len(entities)}",
                type=EntityType.CHEMICAL_ELEMENT,
                name=comp.element,
                properties={
                    "min_val": comp.min_val,
                    "max_val": comp.max_val,
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

        # Convert patent_meta -> Entities
        meta = result.patent_meta
        for name in meta.inventors:
            norm = name.strip()
            entities.append(
                Entity(
                    id=f"{chunk.patent_id}_inventor_{norm.lower().replace(' ', '_')}",
                    type=EntityType.INVENTOR,
                    name=norm,
                    properties={"source": "llm"},
                    patent_id=chunk.patent_id,
                    chunk_ids=[chunk.chunk_id],
                )
            )
        for name in meta.assignees:
            norm = name.strip()
            entities.append(
                Entity(
                    id=f"{chunk.patent_id}_assignee_{norm.lower().replace(' ', '_')}",
                    type=EntityType.ASSIGNEE,
                    name=norm,
                    properties={"source": "llm"},
                    patent_id=chunk.patent_id,
                    chunk_ids=[chunk.chunk_id],
                )
            )
        for ref in meta.cited_patents:
            norm = ref.strip()
            entities.append(
                Entity(
                    id=f"{chunk.patent_id}_cited_{norm.replace(' ', '')}",
                    type=EntityType.PATENT_REFERENCE,
                    name=norm,
                    properties={"source": "llm"},
                    patent_id=chunk.patent_id,
                    chunk_ids=[chunk.chunk_id],
                )
            )
        for app in meta.applications:
            norm = app.strip().lower()
            entities.append(
                Entity(
                    id=f"{chunk.patent_id}_app_{norm.replace(' ', '_')}",
                    type=EntityType.APPLICATION,
                    name=norm,
                    properties={"source": "llm"},
                    patent_id=chunk.patent_id,
                    chunk_ids=[chunk.chunk_id],
                )
            )
        for mat in meta.materials:
            norm = mat.strip().lower()
            entities.append(
                Entity(
                    id=f"{chunk.patent_id}_material_{norm.replace(' ', '_')}",
                    type=EntityType.MATERIAL,
                    name=norm,
                    properties={"source": "llm"},
                    patent_id=chunk.patent_id,
                    chunk_ids=[chunk.chunk_id],
                )
            )
        for prob in meta.problems:
            norm = prob.strip()
            entities.append(
                Entity(
                    id=f"{chunk.patent_id}_problem_{len(entities)}",
                    type=EntityType.PROBLEM,
                    name=norm,
                    properties={"source": "llm"},
                    patent_id=chunk.patent_id,
                    chunk_ids=[chunk.chunk_id],
                )
            )
        for sol in meta.solutions:
            norm = sol.strip()
            entities.append(
                Entity(
                    id=f"{chunk.patent_id}_solution_{len(entities)}",
                    type=EntityType.SOLUTION,
                    name=norm,
                    properties={"source": "llm"},
                    patent_id=chunk.patent_id,
                    chunk_ids=[chunk.chunk_id],
                )
            )

        return entities

    # ------------------------------------------------------------------
    # Regex extraction (unchanged logic, adapted for PatentChunk)
    # ------------------------------------------------------------------

    def _extract_chemical_elements(self, text: str, chunk: PatentChunk) -> list[Entity]:
        entities: list[Entity] = []
        seen_spans: set[tuple[int, int]] = set()  # avoid duplicate overlapping matches

        for symbol, name in CHEMICAL_ELEMENTS.items():
            # --- Pattern A: element-first  "Si: 2.5%" / "Si = 2.5 mass%" ---
            pat_a = rf"\b{symbol}\s*[:=]?\s*(\d+\.?\d*)\s*(%|mass\s*%|wt\s*%)"
            for match in re.finditer(pat_a, text, re.IGNORECASE):
                span = match.span()
                if span in seen_spans:
                    continue
                seen_spans.add(span)
                entities.append(
                    Entity(
                        id=f"{chunk.patent_id}_{symbol}_{len(entities)}",
                        type=EntityType.CHEMICAL_ELEMENT,
                        name=symbol,
                        properties={
                            "full_name": name,
                            "value": float(match.group(1)),
                            "unit": match.group(2),
                        },
                        patent_id=chunk.patent_id,
                        chunk_ids=[chunk.chunk_id],
                    )
                )

            # --- Pattern B: element-first range  "Si: 2.5-10%" ---
            pat_b = (
                rf"\b{symbol}\s*[:=]?\s*(\d+\.?\d*)\s*(?:to|-)\s*(\d+\.?\d*)\s*(%|mass\s*%|wt\s*%)"
            )
            for match in re.finditer(pat_b, text, re.IGNORECASE):
                span = match.span()
                if span in seen_spans:
                    continue
                seen_spans.add(span)
                entities.append(
                    Entity(
                        id=f"{chunk.patent_id}_{symbol}_range_{len(entities)}",
                        type=EntityType.COMPOSITION_RANGE,
                        name=f"{symbol}_range",
                        properties={
                            "element": symbol,
                            "min_val": float(match.group(1)),
                            "max_val": float(match.group(2)),
                            "unit": "%",
                        },
                        patent_id=chunk.patent_id,
                        chunk_ids=[chunk.chunk_id],
                    )
                )

            # --- Pattern C (claims): value-first range  "2.5% to 10% by mass of Si" ---
            pat_c = (
                rf"(\d+\.?\d*)\s*(%|mass\s*%|wt\s*%)\s*"  # min + unit
                rf"(?:to|-)\s*"  # separator
                rf"(\d+\.?\d*)\s*(%|mass\s*%|wt\s*%)"  # max + unit
                rf"(?:\s+by\s+mass)?"  # optional "by mass" qualifier
                rf"\s+(?:of\s+)?\b{symbol}\b"  # "of Si"
            )
            for match in re.finditer(pat_c, text, re.IGNORECASE):
                span = match.span()
                if span in seen_spans:
                    continue
                seen_spans.add(span)
                entities.append(
                    Entity(
                        id=f"{chunk.patent_id}_{symbol}_range_{len(entities)}",
                        type=EntityType.COMPOSITION_RANGE,
                        name=f"{symbol}_range",
                        properties={
                            "element": symbol,
                            "min_val": float(match.group(1)),
                            "max_val": float(match.group(3)),
                            "unit": "%",
                        },
                        patent_id=chunk.patent_id,
                        chunk_ids=[chunk.chunk_id],
                    )
                )

            # --- Pattern D (claims): single value-first  "0.006% by mass or less of C" ---
            pat_d = (
                rf"(\d+\.?\d*)\s*(%|mass\s*%|wt\s*%)"
                rf"(?:\s+by\s+mass)?"
                rf"\s+(?:or\s+less\s+)?(?:of\s+)?\b{symbol}\b"
            )
            for match in re.finditer(pat_d, text, re.IGNORECASE):
                span = match.span()
                if span in seen_spans:
                    continue
                seen_spans.add(span)
                entities.append(
                    Entity(
                        id=f"{chunk.patent_id}_{symbol}_{len(entities)}",
                        type=EntityType.CHEMICAL_ELEMENT,
                        name=symbol,
                        properties={
                            "full_name": name,
                            "value": float(match.group(1)),
                            "unit": match.group(2),
                        },
                        patent_id=chunk.patent_id,
                        chunk_ids=[chunk.chunk_id],
                    )
                )

        return entities

    def _extract_properties(self, text: str, chunk: PatentChunk) -> list[Entity]:
        entities: list[Entity] = []
        for prop_id, aliases in PROPERTIES.items():
            for alias in aliases:
                if alias.lower() in text.lower():
                    pattern = rf"{re.escape(alias)}\s*(?:of|:)?\s*(\d+)\s*(MPa|%|T|W/kg)"
                    match = re.search(pattern, text, re.IGNORECASE)
                    properties: dict[str, str | float | int] = {"alias": alias}
                    if match:
                        properties["value"] = float(match.group(1))
                        properties["unit"] = match.group(2)
                    entities.append(
                        Entity(
                            id=f"{chunk.patent_id}_{prop_id}_{len(entities)}",
                            type=EntityType.PROPERTY,
                            name=prop_id,
                            properties=properties,
                            patent_id=chunk.patent_id,
                            chunk_ids=[chunk.chunk_id],
                        )
                    )
                    break
        return entities

    def _extract_processes(self, text: str, chunk: PatentChunk) -> list[Entity]:
        entities: list[Entity] = []
        for process_id, aliases in PROCESSES.items():
            for alias in aliases:
                if alias.lower() in text.lower():
                    temp_pattern = rf"{re.escape(alias)}.*?(\d+)\s*°?C"
                    temp_match = re.search(temp_pattern, text, re.IGNORECASE)
                    process_props: dict[str, str | float | int] = {"alias": alias}
                    if temp_match:
                        process_props["temperature"] = int(temp_match.group(1))
                        process_props["temperature_unit"] = "°C"
                    entities.append(
                        Entity(
                            id=f"{chunk.patent_id}_{process_id}_{len(entities)}",
                            type=EntityType.PROCESS,
                            name=process_id,
                            properties=process_props,
                            patent_id=chunk.patent_id,
                            chunk_ids=[chunk.chunk_id],
                        )
                    )
                    break
        return entities

    def _extract_references(self, text: str, chunk: PatentChunk) -> list[Entity]:
        entities: list[Entity] = []

        for match in self.TABLE_RE.finditer(text):
            table_num = match.group(1)
            entities.append(
                Entity(
                    id=f"{chunk.patent_id}_table_{table_num}",
                    type=EntityType.TABLE,
                    name=f"Table {table_num}",
                    properties={"table_number": int(table_num)},
                    patent_id=chunk.patent_id,
                    chunk_ids=[chunk.chunk_id],
                )
            )

        for match in self.FORMULA_RE.finditer(text):
            formula_num = match.group(1)
            entities.append(
                Entity(
                    id=f"{chunk.patent_id}_formula_{formula_num}",
                    type=EntityType.FORMULA,
                    name=f"Formula {formula_num}",
                    properties={"formula_number": int(formula_num)},
                    patent_id=chunk.patent_id,
                    chunk_ids=[chunk.chunk_id],
                )
            )

        for match in self.FIGURE_RE.finditer(text):
            fig_num = match.group(1) or match.group(2)
            entities.append(
                Entity(
                    id=f"{chunk.patent_id}_figure_{fig_num}",
                    type=EntityType.FIGURE,
                    name=f"Figure {fig_num}",
                    properties={"figure_number": int(fig_num)},
                    patent_id=chunk.patent_id,
                    chunk_ids=[chunk.chunk_id],
                )
            )

        return entities

    def _extract_samples(self, text: str, chunk: PatentChunk) -> list[Entity]:
        entities: list[Entity] = []
        for match in self.SAMPLE_RE.finditer(text):
            sample_id = match.group(1)
            entities.append(
                Entity(
                    id=f"{chunk.patent_id}_sample_{sample_id}",
                    type=EntityType.SAMPLE,
                    name=f"Sample {sample_id}",
                    properties={"sample_id": sample_id},
                    patent_id=chunk.patent_id,
                    chunk_ids=[chunk.chunk_id],
                )
            )
        return entities

    # ------------------------------------------------------------------
    # Patent-intelligence regex extraction
    # ------------------------------------------------------------------

    def _extract_patent_references(self, text: str, chunk: PatentChunk) -> list[Entity]:
        """Extract cited patent numbers (e.g. US 7,234,567, EP1577413)."""
        entities: list[Entity] = []
        seen: set[str] = set()
        for match in self.PATENT_REF_RE.finditer(text):
            raw = match.group(0).strip()
            norm = raw.replace(" ", "").replace(",", "")
            if norm in seen:
                continue
            seen.add(norm)
            entities.append(
                Entity(
                    id=f"{chunk.patent_id}_cited_{norm}",
                    type=EntityType.PATENT_REFERENCE,
                    name=raw,
                    properties={"normalized": norm},
                    patent_id=chunk.patent_id,
                    chunk_ids=[chunk.chunk_id],
                )
            )
        return entities

    def _extract_patent_doc_references(self, text: str, chunk: PatentChunk) -> list[Entity]:
        """Extract internal patent document references (e.g. 'Patent Document 2', 'Patent Literature 1')."""
        entities: list[Entity] = []
        seen: set[str] = set()
        for match in self.PATENT_DOC_RE.finditer(text):
            num = match.group(1)
            name = f"Patent Document {num}"
            if name in seen:
                continue
            seen.add(name)
            entities.append(
                Entity(
                    id=f"{chunk.patent_id}_patdoc_{num}",
                    type=EntityType.PATENT_DOC_REFERENCE,
                    name=name,
                    properties={"doc_number": int(num)},
                    patent_id=chunk.patent_id,
                    chunk_ids=[chunk.chunk_id],
                )
            )
        return entities

    def _extract_inventors(self, text: str, chunk: PatentChunk) -> list[Entity]:
        """Extract inventor names from 'Inventor(s): ...' lines."""
        entities: list[Entity] = []
        for match in self.INVENTOR_RE.finditer(text):
            names_str = match.group(1)
            for name in re.split(r"[;,]", names_str):
                stripped_name = name.strip()
                if len(stripped_name) < 3:
                    continue
                norm = stripped_name.lower().replace(" ", "_")
                entities.append(
                    Entity(
                        id=f"{chunk.patent_id}_inventor_{norm}",
                        type=EntityType.INVENTOR,
                        name=stripped_name,
                        properties={},
                        patent_id=chunk.patent_id,
                        chunk_ids=[chunk.chunk_id],
                    )
                )
        return entities

    def _extract_assignees(self, text: str, chunk: PatentChunk) -> list[Entity]:
        """Extract assignee/applicant names from 'Assignee: ...' lines."""
        entities: list[Entity] = []
        for match in self.ASSIGNEE_RE.finditer(text):
            names_str = match.group(1)
            for name in re.split(r"[;,]", names_str):
                stripped_name = name.strip()
                if len(stripped_name) < 3:
                    continue
                norm = stripped_name.lower().replace(" ", "_")
                entities.append(
                    Entity(
                        id=f"{chunk.patent_id}_assignee_{norm}",
                        type=EntityType.ASSIGNEE,
                        name=stripped_name,
                        properties={},
                        patent_id=chunk.patent_id,
                        chunk_ids=[chunk.chunk_id],
                    )
                )
        return entities

    def _extract_applications(self, text: str, chunk: PatentChunk) -> list[Entity]:
        """Extract application domains via vocabulary matching."""
        entities: list[Entity] = []
        text_lower = text.lower()
        for app_id, aliases in APPLICATIONS.items():
            for alias in aliases:
                # Use word-boundary matching to prevent short aliases (e.g. "EV")
                # from matching inside longer words (e.g. "achieve", "ever").
                if re.search(rf"\b{re.escape(alias.lower())}\b", text_lower):
                    entities.append(
                        Entity(
                            id=f"{chunk.patent_id}_app_{app_id}",
                            type=EntityType.APPLICATION,
                            name=app_id,
                            properties={"matched_alias": alias},
                            patent_id=chunk.patent_id,
                            chunk_ids=[chunk.chunk_id],
                        )
                    )
                    break
        return entities

    def _extract_materials(self, text: str, chunk: PatentChunk) -> list[Entity]:
        """Extract named materials / alloy types via vocabulary matching."""
        entities: list[Entity] = []
        text_lower = text.lower()
        for mat_id, aliases in MATERIALS.items():
            for alias in aliases:
                if re.search(rf"\b{re.escape(alias.lower())}\b", text_lower):
                    entities.append(
                        Entity(
                            id=f"{chunk.patent_id}_material_{mat_id}",
                            type=EntityType.MATERIAL,
                            name=mat_id,
                            properties={"matched_alias": alias},
                            patent_id=chunk.patent_id,
                            chunk_ids=[chunk.chunk_id],
                        )
                    )
                    break
        return entities

    def _extract_problems(self, text: str, chunk: PatentChunk) -> list[Entity]:
        """Extract problem/limitation sentences from background sections."""
        entities: list[Entity] = []
        text_lower = text.lower()
        for phrase in self.PROBLEM_PHRASES:
            if phrase in text_lower:
                # Find the sentence containing the phrase
                sentence = self._sentence_around(text, phrase)
                if sentence:
                    entities.append(
                        Entity(
                            id=f"{chunk.patent_id}_problem_{len(entities)}_{phrase}",
                            type=EntityType.PROBLEM,
                            name=sentence,
                            properties={"trigger_phrase": phrase},
                            patent_id=chunk.patent_id,
                            chunk_ids=[chunk.chunk_id],
                        )
                    )
                break  # one problem entity per chunk to avoid noise
        return entities

    def _extract_solutions(self, text: str, chunk: PatentChunk) -> list[Entity]:
        """Extract solution/advantage sentences from description sections."""
        entities: list[Entity] = []
        text_lower = text.lower()
        for phrase in self.SOLUTION_PHRASES:
            if phrase in text_lower:
                sentence = self._sentence_around(text, phrase)
                if sentence:
                    entities.append(
                        Entity(
                            id=f"{chunk.patent_id}_solution_{len(entities)}_{phrase.replace(' ', '_')[:20]}",
                            type=EntityType.SOLUTION,
                            name=sentence,
                            properties={"trigger_phrase": phrase},
                            patent_id=chunk.patent_id,
                            chunk_ids=[chunk.chunk_id],
                        )
                    )
                break  # one solution entity per chunk
        return entities

    @staticmethod
    def _sentence_around(text: str, phrase: str) -> str | None:
        """Return the sentence containing *phrase*, truncated to 300 chars."""
        idx = text.lower().find(phrase)
        if idx == -1:
            return None
        # Walk backwards to sentence start
        start = max(0, text.rfind(".", 0, idx) + 1)
        # Walk forwards to sentence end
        end_dot = text.find(".", idx)
        end = end_dot + 1 if end_dot != -1 else len(text)
        sentence = text[start:end].strip()
        return sentence[:300] if sentence else None
