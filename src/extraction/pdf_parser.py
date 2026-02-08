"""Layout-aware PDF parser for patent documents using Docling.

Replaces the previous unstructured+pdfplumber implementation with:
- Docling DocumentConverter for accurate multi-column PDF parsing
- State machine for patent section detection from Markdown headings
"""

import os
import re
from pathlib import Path

from docling.document_converter import DocumentConverter
from docling_core.types.doc.document import TableItem

from src.knowledge_graph.schema import PatentDocument, PatentSection


class PatentSectionStateMachine:
    """Track the current patent section as we scan Markdown lines.

    Transitions happen when a line matches a heading pattern (e.g.
    ``## CLAIMS`` or ``### DETAILED DESCRIPTION``).  The state remains
    until the next matching heading.
    """

    # Each tuple: (compiled regex for the heading text, target PatentSection)
    TRANSITIONS: list[tuple[re.Pattern, PatentSection]] = [
        (re.compile(r"^#{1,3}\s+ABSTRACT", re.IGNORECASE), PatentSection.ABSTRACT),
        (re.compile(r"^#{1,3}\s+CLAIMS?", re.IGNORECASE), PatentSection.CLAIMS),
        (re.compile(r"^#{1,3}\s+BACKGROUND", re.IGNORECASE), PatentSection.BACKGROUND),
        (re.compile(r"^#{1,3}\s+DETAILED\s+DESCRIPTION", re.IGNORECASE), PatentSection.DESCRIPTION),
        (re.compile(r"^#{1,3}\s+DESCRIPTION", re.IGNORECASE), PatentSection.DESCRIPTION),
        (re.compile(r"^#{1,3}\s+EXAMPLES?", re.IGNORECASE), PatentSection.EXAMPLES),
        (re.compile(r"^#{1,3}\s+EMBODIMENTS?", re.IGNORECASE), PatentSection.EMBODIMENTS),
        (re.compile(r"^#{1,3}\s+BRIEF\s+DESCRIPTION\s+OF.*(?:DRAWING|FIGURE)", re.IGNORECASE), PatentSection.FIGURES),
        (re.compile(r"^#{1,3}\s+SUMMARY", re.IGNORECASE), PatentSection.DESCRIPTION),
        (re.compile(r"^#{1,3}\s+FIELD\s+OF", re.IGNORECASE), PatentSection.BACKGROUND),
    ]

    def __init__(self):
        self.state = PatentSection.PREAMBLE

    def transition(self, line: str) -> PatentSection:
        """Check if *line* triggers a section transition. Returns current state."""
        stripped = line.strip()
        for pattern, section in self.TRANSITIONS:
            if pattern.match(stripped):
                self.state = section
                break
        return self.state


# Noise patterns commonly found in European / US patent Markdown output
_NOISE_PATTERNS: list[re.Pattern] = [
    # EP page headers like "EP 1 577 413 A1"
    re.compile(r"^EP\s+[\d\s]+[A-Z]\d?\s*$"),
    # US patent numbers as standalone lines
    re.compile(r"^US\s+[\d,]+\s*[A-Z]?\d?\s*$"),
    # Page numbers
    re.compile(r"^\d{1,3}\s*$"),
    # Blank markdown heading artefacts
    re.compile(r"^#{1,6}\s*$"),
]


class PatentPDFParser:
    """Parse patent PDFs into structured PatentDocument using Docling."""

    def __init__(self):
        self._converter = DocumentConverter()

    def extract(self, pdf_path: str) -> PatentDocument:
        """Extract structured content from a patent PDF.

        Pipeline:
        1. Docling ``DocumentConverter.convert()`` -> DoclingDocument
        2. ``export_to_markdown()`` -> full Markdown text
        3. Filter noise lines (page headers, page numbers)
        4. State machine assigns each line to a patent section
        5. Extract tables via ``docling_doc.tables``
        6. Build and return a ``PatentDocument``
        """
        pdf_path_obj = Path(pdf_path)
        print(f"Extracting {pdf_path_obj.name} with Docling...")

        # 1. Convert PDF
        result = self._converter.convert(pdf_path_obj)
        docling_doc = result.document

        # 2. Export full Markdown
        markdown_text = docling_doc.export_to_markdown()

        # 3. Extract patent ID and title
        patent_id = self._extract_patent_id(pdf_path, markdown_text)
        title = self._extract_title(docling_doc, markdown_text)

        # 4. Assign lines to sections via state machine
        sections = self._assign_sections(markdown_text)

        # 5. Extract tables as Markdown strings
        tables_md = self._extract_tables(docling_doc)

        # 6. Build metadata
        page_count = len(docling_doc.pages) if docling_doc.pages else 0
        metadata = {
            "filename": os.path.basename(pdf_path),
            "total_pages": page_count,
            "extraction_method": "docling",
        }

        return PatentDocument(
            patent_id=patent_id,
            title=title,
            sections=sections,
            tables_markdown=tables_md,
            metadata=metadata,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _assign_sections(self, markdown_text: str) -> dict[str, str]:
        """Walk Markdown lines through the state machine and group by section."""
        sm = PatentSectionStateMachine()
        section_lines: dict[str, list[str]] = {}

        for line in markdown_text.splitlines():
            # Skip noise lines
            if self._is_noise(line):
                continue

            section = sm.transition(line)
            section_name = section.value

            # Don't include the heading line itself in the section body
            stripped = line.strip()
            is_heading = stripped.startswith("#") and any(
                p.match(stripped) for p, _ in PatentSectionStateMachine.TRANSITIONS
            )
            if is_heading:
                section_lines.setdefault(section_name, [])
                continue

            section_lines.setdefault(section_name, []).append(line)

        # Join lines into text blocks per section
        return {
            name: "\n".join(lines).strip()
            for name, lines in section_lines.items()
            if "\n".join(lines).strip()
        }

    @staticmethod
    def _is_noise(line: str) -> bool:
        stripped = line.strip()
        if not stripped:
            return False  # keep blank lines for paragraph splitting
        for pattern in _NOISE_PATTERNS:
            if pattern.match(stripped):
                return True
        return False

    @staticmethod
    def _extract_tables(docling_doc) -> list[str]:
        """Extract each table as a Markdown string."""
        tables: list[str] = []
        for table_item in docling_doc.tables:
            try:
                md = table_item.export_to_markdown()
                if md and md.strip():
                    tables.append(md.strip())
            except Exception:
                pass
        return tables

    @staticmethod
    def _extract_patent_id(pdf_path: str, markdown_text: str) -> str:
        """Extract patent ID from filename or first page text."""
        filename = os.path.basename(pdf_path)

        # Try filename first
        match = re.search(r"(EP|US|WO|CN)\d+", filename, re.IGNORECASE)
        if match:
            return match.group(0).upper()

        # Try first ~2000 chars of Markdown
        first_page = markdown_text[:2000]
        match = re.search(r"(EP|US|WO|CN)\s*\d+", first_page, re.IGNORECASE)
        if match:
            return re.sub(r"\s+", "", match.group(0)).upper()

        return os.path.splitext(filename)[0]

    @staticmethod
    def _extract_title(docling_doc, markdown_text: str) -> str:
        """Heuristic title extraction: first substantial Markdown heading."""
        for line in markdown_text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                heading_text = re.sub(r"^#+\s*", "", stripped)
                if len(heading_text) > 10:
                    return heading_text
        return "Unknown Title"
