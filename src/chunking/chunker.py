"""Atomic-unit chunking for patent documents.

Each chunk is a natural semantic unit (claim, paragraph, table, formula).
No token-based splitting or overlap -- boundaries come from document structure.
"""

import re
from typing import ClassVar

from src.knowledge_graph.schema import (
    EntityType,
    PatentChunk,
    PatentDocument,
    PatentSection,
    StructuredReference,
)


class PatentChunker:
    """Create chunks from a PatentDocument using an atomic-unit strategy.

    Chunking rules:
    - **Claims:**   Each numbered claim (``1.``, ``2.``, ...) is one chunk.
    - **Paragraphs:** Split on ``[00XX]`` tags first; fall back to blank lines.
    - **Tables:**    Each table Markdown string is one chunk.
    - **Formulas:**  Paragraphs containing formula patterns are tagged ``formula``.
    """

    # Reference patterns (used to build StructuredReference objects)
    _REF_PATTERNS: ClassVar[list[tuple[re.Pattern, EntityType]]] = [
        (re.compile(r"Table\s*(\d+)", re.IGNORECASE), EntityType.TABLE),
        (re.compile(r"Formula\s*\((\d+)\)", re.IGNORECASE), EntityType.FORMULA),
        (re.compile(r"FIG\.?\s*(\d+)", re.IGNORECASE), EntityType.FIGURE),
        (re.compile(r"Figure\s*(\d+)", re.IGNORECASE), EntityType.FIGURE),
        (re.compile(r"Equation\s*\((\d+)\)", re.IGNORECASE), EntityType.FORMULA),
    ]

    # Formula detection (to tag paragraph chunks that contain formulas)
    _FORMULA_RE = re.compile(
        r"Formula\s*\(\d+\)|Equation\s*\(\d+\)|\[\w+\]/\d+",
        re.IGNORECASE,
    )

    # Page-break marker emitted by the parser (<!-- PB:N -->)
    _PAGE_MARKER_RE = re.compile(r"<!--\s*PB:(\d+)\s*-->")

    # Numbered claim start: "1.", "2.", etc. at the beginning of a line
    _CLAIM_START_RE = re.compile(r"^\d+\.\s")

    # [00XX] paragraph tag used in patent descriptions
    _PARA_TAG_RE = re.compile(r"^\[\d{4}\]")

    def chunk_patent(self, patent_doc: PatentDocument) -> list[PatentChunk]:
        """Produce a list of PatentChunk from a PatentDocument."""
        chunks: list[PatentChunk] = []

        # 1. Section-based text chunks
        for section_name, text in patent_doc.sections.items():
            if section_name == PatentSection.CLAIMS.value:
                chunks.extend(self._chunk_claims(text, patent_doc.patent_id))
            else:
                chunks.extend(self._chunk_section(text, patent_doc.patent_id, section_name))

        # 2. Table chunks (from Docling-extracted tables)
        table_pages = patent_doc.metadata.get("table_pages", [])
        for idx, table_md in enumerate(patent_doc.tables_markdown):
            page = table_pages[idx] if idx < len(table_pages) else 1
            chunk = PatentChunk(
                patent_id=patent_doc.patent_id,
                content=table_md,
                section="unknown",
                chunk_type="table",
                page=page,
                references=self._extract_references(table_md, patent_doc.patent_id),
            )
            chunks.append(chunk)

        # 3. Assign sequential IDs
        for i, chunk in enumerate(chunks):
            chunk.chunk_id = f"{patent_doc.patent_id}_{i:04d}"

        return chunks

    # ------------------------------------------------------------------
    # Claims chunking
    # ------------------------------------------------------------------

    def _chunk_claims(self, text: str, patent_id: str) -> list[PatentChunk]:
        """Split claims section: each numbered claim becomes one chunk."""
        # Split on lines that start with a claim number
        claim_blocks: list[str] = []
        current: list[str] = []

        for line in text.splitlines():
            if self._CLAIM_START_RE.match(line.strip()) and current:
                claim_blocks.append("\n".join(current).strip())
                current = [line]
            else:
                current.append(line)

        if current:
            claim_blocks.append("\n".join(current).strip())

        chunks: list[PatentChunk] = []
        current_page = 1
        for block in claim_blocks:
            if not block:
                continue
            page, clean_block = self._extract_page_and_clean(block, current_page)
            current_page = page  # propagate to next block
            if not clean_block:
                continue
            chunks.append(
                PatentChunk(
                    patent_id=patent_id,
                    content=clean_block,
                    section=PatentSection.CLAIMS.value,
                    chunk_type="claim",
                    page=page,
                    references=self._extract_references(clean_block, patent_id),
                )
            )
        return chunks

    # ------------------------------------------------------------------
    # General section chunking
    # ------------------------------------------------------------------

    def _chunk_section(self, text: str, patent_id: str, section_name: str) -> list[PatentChunk]:
        """Split section text into atomic paragraphs.

        Strategy:
        1. Try splitting on ``[00XX]`` paragraph tags.
        2. Fallback to splitting on blank lines.
        """
        paragraphs = self._split_paragraphs(text)

        chunks: list[PatentChunk] = []
        current_page = 1
        for para in paragraphs:
            stripped_para = para.strip()
            if not stripped_para:
                continue

            page, clean_para = self._extract_page_and_clean(para, current_page)
            current_page = page  # propagate to next paragraph
            if not clean_para:
                continue

            chunk_type = "paragraph"
            if self._FORMULA_RE.search(clean_para):
                chunk_type = "formula"

            chunks.append(
                PatentChunk(
                    patent_id=patent_id,
                    content=clean_para,
                    section=section_name,
                    chunk_type=chunk_type,
                    page=page,
                    references=self._extract_references(clean_para, patent_id),
                )
            )
        return chunks

    def _split_paragraphs(self, text: str) -> list[str]:
        """Split text by [00XX] tags or blank lines."""
        # Check if text contains [00XX] paragraph tags
        if self._PARA_TAG_RE.search(text):
            return self._split_by_para_tags(text)
        return self._split_by_blank_lines(text)

    @staticmethod
    def _split_by_para_tags(text: str) -> list[str]:
        """Split on ``[00XX]`` markers, keeping each tagged paragraph together."""
        parts: list[str] = []
        current: list[str] = []

        for line in text.splitlines():
            stripped = line.strip()
            if re.match(r"^\[\d{4}\]", stripped) and current:
                parts.append("\n".join(current).strip())
                current = [line]
            else:
                current.append(line)

        if current:
            parts.append("\n".join(current).strip())

        return [p for p in parts if p]

    @staticmethod
    def _split_by_blank_lines(text: str) -> list[str]:
        """Fallback: split on one or more blank lines."""
        blocks = re.split(r"\n\s*\n", text)
        return [b.strip() for b in blocks if b.strip()]

    # ------------------------------------------------------------------
    # Page marker handling
    # ------------------------------------------------------------------

    @classmethod
    def _extract_page_and_clean(cls, text: str, default_page: int = 1) -> tuple[int, str]:
        """Extract page number from ``<!-- PB:N -->`` markers and strip them.

        Args:
            text: Chunk text potentially containing page markers.
            default_page: Page number to use if no marker is found (allows
                the caller to propagate the last known page).

        Returns:
            ``(page, cleaned_text)`` where *page* is the first marker's value
            (or *default_page* if none found) and *cleaned_text* has all
            markers removed.
        """
        match = cls._PAGE_MARKER_RE.search(text)
        page = int(match.group(1)) if match else default_page
        cleaned = cls._PAGE_MARKER_RE.sub("", text).strip()
        # Collapse any double blank lines left by marker removal
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return page, cleaned

    # ------------------------------------------------------------------
    # Reference resolution
    # ------------------------------------------------------------------

    def _extract_references(self, text: str, patent_id: str) -> list[StructuredReference]:
        """Find and resolve cross-references (e.g. 'Table 1' -> patent-scoped ID)."""
        refs: list[StructuredReference] = []
        seen: set[tuple[EntityType, str]] = set()

        for pattern, ref_type in self._REF_PATTERNS:
            for match in pattern.finditer(text):
                raw_text = match.group(0)
                num = match.group(1)

                type_label = ref_type.value.upper()
                ref_id = f"{patent_id}_{type_label}_{int(num):02d}"

                key = (ref_type, ref_id)
                if key in seen:
                    continue
                seen.add(key)

                refs.append(
                    StructuredReference(
                        raw_text=raw_text,
                        ref_type=ref_type,
                        ref_id=ref_id,
                    )
                )
        return refs
