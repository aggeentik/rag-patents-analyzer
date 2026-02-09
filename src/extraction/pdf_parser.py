"""Layout-aware PDF parser for patent documents using Docling.

Replaces the previous unstructured+pdfplumber implementation with:
- Docling DocumentConverter for accurate multi-column PDF parsing
- State machine for patent section detection from Markdown headings
"""

import html
import logging
import re
from pathlib import Path
from typing import ClassVar

from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.datamodel.base_models import InputFormat
from docling.document_converter import DocumentConverter, PdfFormatOption

from src.knowledge_graph.schema import PatentDocument, PatentSection

logger = logging.getLogger(__name__)


class PatentSectionStateMachine:
    """Track the current patent section as we scan Markdown lines.

    Transitions happen when a line matches a heading pattern (e.g.
    ``## CLAIMS`` or ``### DETAILED DESCRIPTION``).  The state remains
    until the next matching heading.
    """

    # Each tuple: (compiled regex for the heading text, target PatentSection)
    TRANSITIONS: ClassVar[list[tuple[re.Pattern, PatentSection]]] = [
        (re.compile(r"^#{1,3}\s+ABSTRACT", re.IGNORECASE), PatentSection.ABSTRACT),
        (re.compile(r"^#{1,3}\s+CLAIMS?", re.IGNORECASE), PatentSection.CLAIMS),
        (re.compile(r"^#{1,3}\s+BACKGROUND", re.IGNORECASE), PatentSection.BACKGROUND),
        (re.compile(r"^#{1,3}\s+DETAILED\s+DESCRIPTION", re.IGNORECASE), PatentSection.DESCRIPTION),
        (re.compile(r"^#{1,3}\s+DESCRIPTION", re.IGNORECASE), PatentSection.DESCRIPTION),
        (re.compile(r"^#{1,3}\s+EXAMPLES?", re.IGNORECASE), PatentSection.EXAMPLES),
        (re.compile(r"^#{1,3}\s+EMBODIMENTS?", re.IGNORECASE), PatentSection.EMBODIMENTS),
        (
            re.compile(r"^#{1,3}\s+BRIEF\s+DESCRIPTION\s+OF.*(?:DRAWING|FIGURE)", re.IGNORECASE),
            PatentSection.FIGURES,
        ),
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


class TableStitcher:
    """Merge consecutive Markdown tables that have the same column count.

    Patent tables frequently span page breaks, causing Docling to emit
    two separate ``TableItem`` objects for what is logically one table.
    This post-processor detects consecutive tables with identical column
    counts and merges them into a single Markdown table.
    """

    @staticmethod
    def _column_count(table_md: str) -> int:
        """Count columns from the first data row (``| ... | ... |``)."""
        for line in table_md.splitlines():
            stripped = line.strip()
            if stripped.startswith("|") and "---" not in stripped:
                return stripped.count("|") - 1
        return 0

    @staticmethod
    def _data_rows(table_md: str) -> list[str]:
        """Return only the data rows (skip header and separator lines)."""
        rows: list[str] = []
        past_separator = False
        for line in table_md.splitlines():
            stripped = line.strip()
            if not stripped.startswith("|"):
                continue
            if "---" in stripped:
                past_separator = True
                continue
            if past_separator:
                rows.append(stripped)
        return rows

    @staticmethod
    def _header_block(table_md: str) -> str:
        """Return the header row + separator line."""
        lines: list[str] = []
        for line in table_md.splitlines():
            stripped = line.strip()
            if not stripped.startswith("|"):
                continue
            lines.append(stripped)
            if "---" in stripped:
                break
        return "\n".join(lines)

    def stitch(self, tables: list[str], table_pages: list[int]) -> list[str]:
        """Return a new list of tables with compatible neighbours merged.

        Also mutates *table_pages* in-place to keep it parallel with the
        returned (possibly shorter) table list.
        """
        if not tables:
            return tables

        merged: list[str] = []
        merged_pages: list[int] = []
        current = tables[0]
        current_cols = self._column_count(current)
        current_page = table_pages[0] if table_pages else 1

        for i, next_table in enumerate(tables[1:], start=1):
            next_cols = self._column_count(next_table)

            if next_cols == current_cols and current_cols > 0:
                # Same column count → append data rows of next to current
                header = self._header_block(current)
                existing_rows = self._data_rows(current)
                new_rows = self._data_rows(next_table)
                all_rows = existing_rows + new_rows
                current = header + "\n" + "\n".join(all_rows)
                # current_page stays (use the first table's page)
            else:
                merged.append(current)
                merged_pages.append(current_page)
                current = next_table
                current_cols = next_cols
                current_page = table_pages[i] if i < len(table_pages) else 1

        merged.append(current)
        merged_pages.append(current_page)

        # Update table_pages in-place to match merged result
        table_pages[:] = merged_pages
        return merged


class PatentPDFParser:
    """Parse patent PDFs into structured PatentDocument using Docling."""

    def __init__(self):
        # Use pypdfium2 backend: handles patent PDFs that lack explicit
        # page-dimension entries (which cause docling-parse to fail).
        self._converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    backend=PyPdfiumDocumentBackend,
                )
            }
        )

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
        logger.info("Extracting %s with Docling...", pdf_path_obj.name)

        # 1. Convert PDF
        result = self._converter.convert(pdf_path_obj)
        docling_doc = result.document

        # 2. Export full Markdown (with page-break markers for page tracking)
        markdown_text = docling_doc.export_to_markdown(page_break_placeholder="<!-- PB -->")

        # 3. Extract patent ID and title
        patent_id = self._extract_patent_id(pdf_path, markdown_text)
        title = self._extract_title(docling_doc, markdown_text)

        # 4. Assign lines to sections via state machine
        sections = self._assign_sections(markdown_text)

        # 5. Extract tables as Markdown strings, then stitch page-split tables
        tables_md, table_pages = self._extract_tables(docling_doc)
        tables_md = TableStitcher().stitch(tables_md, table_pages)

        # 6. Build metadata
        page_count = len(docling_doc.pages) if docling_doc.pages else 0
        metadata = {
            "filename": Path(pdf_path).name,
            "total_pages": page_count,
            "extraction_method": "docling",
            "table_pages": table_pages,
        }

        # Extract INID metadata from preamble
        preamble = sections.get(PatentSection.PREAMBLE.value, "")
        inid_metadata = self._extract_inid_metadata(preamble, pdf_path)
        metadata.update(inid_metadata)

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
        """Walk Markdown lines through the state machine and group by section.

        Tracks page breaks emitted by Docling's ``page_break_placeholder``
        and embeds ``<!-- PB:N -->`` markers into section text so the chunker
        can assign correct page numbers.
        """
        sm = PatentSectionStateMachine()
        section_lines: dict[str, list[str]] = {}
        current_page = 1
        section_last_page: dict[str, int] = {}

        for line in markdown_text.splitlines():
            stripped = line.strip()

            # Intercept page-break placeholders from Docling
            # Docling's Markdown export escapes `!` → `\!`, so the actual
            # output is `<\!-- PB -->` rather than `<!-- PB -->`.
            if stripped in ("<!-- PB -->", r"<\!-- PB -->"):
                current_page += 1
                continue

            # Skip noise lines
            if self._is_noise(line):
                continue

            section = sm.transition(line)
            section_name = section.value

            # Don't include the heading line itself in the section body
            is_heading = stripped.startswith("#") and any(
                p.match(stripped) for p, _ in PatentSectionStateMachine.TRANSITIONS
            )
            if is_heading:
                section_lines.setdefault(section_name, [])
                section_last_page.setdefault(section_name, current_page)
                continue

            # Emit a page marker when:
            # 1. This is the first content line in the section (to establish initial page)
            # 2. The page changes within a section
            section_list = section_lines.get(section_name, [])
            is_first_content_line = len(section_list) == 0

            if is_first_content_line or section_last_page.get(section_name) != current_page:
                section_lines.setdefault(section_name, []).append(f"<!-- PB:{current_page} -->")
                section_last_page[section_name] = current_page

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
        return any(pattern.match(stripped) for pattern in _NOISE_PATTERNS)

    @staticmethod
    def _extract_tables(docling_doc) -> tuple[list[str], list[int]]:
        """Extract each table as a Markdown string, with its page number.

        Returns:
            Tuple of (table_markdowns, table_pages) where each list has the
            same length. Page numbers default to 1 if provenance is missing.
        """
        tables: list[str] = []
        pages: list[int] = []
        for table_item in docling_doc.tables:
            try:
                md = table_item.export_to_markdown(doc=docling_doc)
                if md and md.strip():
                    tables.append(md.strip())
                    page = 1
                    if table_item.prov:
                        page = table_item.prov[0].page_no
                    pages.append(page)
            except Exception:
                pass
        return tables, pages

    @staticmethod
    def _extract_patent_id(pdf_path: str, markdown_text: str) -> str:
        """Extract patent ID from filename or first page text."""
        filename = Path(pdf_path).name

        # Try filename first
        match = re.search(r"(EP|US|WO|CN)\d+", filename, re.IGNORECASE)
        if match:
            return match.group(0).upper()

        # Try first ~2000 chars of Markdown
        first_page = markdown_text[:2000]
        match = re.search(r"(EP|US|WO|CN)\s*\d+", first_page, re.IGNORECASE)
        if match:
            return re.sub(r"\s+", "", match.group(0)).upper()

        return Path(filename).stem

    @staticmethod
    def _extract_title(_docling_doc, markdown_text: str) -> str:
        """Title extraction: prefer (54) INID heading, fallback to first substantial heading."""
        for line in markdown_text.splitlines():
            stripped = line.strip()
            if re.match(r"^#{1,3}\s+\(54\)", stripped):
                title = re.sub(r"^#{1,3}\s+\(54\)\s*", "", stripped).strip()
                if title:
                    return title
        # Fallback: first substantial heading
        for line in markdown_text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                heading_text = re.sub(r"^#+\s*", "", stripped)
                if len(heading_text) > 10:
                    return heading_text
        return "Unknown Title"

    @staticmethod
    def _extract_inid_metadata(preamble_text: str, pdf_path: str) -> dict:
        """Extract INID code metadata from the patent preamble section.

        Parses standardized INID codes (e.g. (43) publication date, (71) applicant)
        from the Docling-generated Markdown preamble and returns a dict of
        structured metadata fields.
        """
        lines = preamble_text.splitlines()
        metadata: dict = {}

        # Regex patterns
        inid_re = re.compile(r"^[-\s]*\((\d+)\)\s*(.*)")
        date_re = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})")
        ipc_re = re.compile(r"[A-H]\d{2}[A-Z]\s*\d+/\d+")

        def _normalize_date(text: str) -> str | None:
            """Convert DD.MM.YYYY to YYYY-MM-DD."""
            m = date_re.search(text)
            if m:
                day, month, year = m.group(1), m.group(2), m.group(3)
                return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            return None

        def _next_value(rest: str, idx: int) -> str:
            """Get value from inline text (after colon) or next non-blank line."""
            # Try inline: text after the label colon
            if ":" in rest:
                val = rest.split(":", 1)[1].strip()
                if val:
                    return val
            elif rest.strip():
                return rest.strip()
            # Fall through to next non-blank line
            for j in range(idx + 1, min(idx + 5, len(lines))):
                candidate = lines[j].strip().lstrip("- ")
                if candidate and not inid_re.match(candidate):
                    return candidate
            return ""

        def _collect_until_next_inid(idx: int) -> str:
            """Collect all text from idx+1 until the next INID marker."""
            parts = []
            for j in range(idx + 1, len(lines)):
                line = lines[j].strip()
                if inid_re.match(line):
                    break
                if line:
                    parts.append(line.lstrip("- "))
            return " ".join(parts)

        i = 0
        while i < len(lines):
            line = lines[i].strip()
            m = inid_re.match(line)
            if not m:
                i += 1
                continue

            code = m.group(1)
            rest = m.group(2)

            if code == "43":  # Publication date
                combined = rest + " " + _collect_until_next_inid(i)
                date = _normalize_date(combined)
                if date:
                    metadata["publication_date"] = date

            elif code == "21":  # Application number
                val = _next_value(rest, i)
                if val:
                    metadata["application_number"] = val

            elif code == "22":  # Filing date
                combined = rest + " " + _collect_until_next_inid(i)
                date = _normalize_date(combined)
                if date:
                    metadata["filing_date"] = date

            elif code == "51":  # IPC classes
                combined = rest + " " + _collect_until_next_inid(i)
                classes = ipc_re.findall(combined)
                if classes:
                    metadata["ipc_classes"] = [c.strip() for c in classes]

            elif code == "30":  # Priority date
                combined = rest + " " + _collect_until_next_inid(i)
                date = _normalize_date(combined)
                if date:
                    metadata["priority_date"] = date

            elif code == "71":  # Applicant
                val = _next_value(rest, i)
                if val:
                    # Strip address/country suffix like "Tokyo, 100-0011 (JP)"
                    # The applicant name is typically the first line
                    metadata["applicant"] = val

            elif code == "72":  # Inventors
                inventors = []

                def _clean_inventor(raw: str) -> str | None:
                    """Extract inventor name, stripping address/affiliation."""
                    raw = raw.strip().lstrip("- ")
                    if not raw:
                        return None
                    # Skip lines that are purely addresses
                    if re.match(r"^\d", raw):  # starts with zip/number
                        return None
                    if re.match(r"^\(", raw):  # starts with parenthesis
                        return None
                    # Extract name part: before ", c/o" or address suffixes
                    name = re.split(r",\s*c/o\b", raw, flags=re.IGNORECASE)[0]
                    name = re.split(r",\s*(?:\d|[A-Z]{2}\b)", name)[0]
                    name = name.strip().rstrip(",")
                    if not name:
                        return None
                    # Skip if remaining name looks like an address (city + country)
                    if re.search(r"\([A-Z]{2}\)\s*$", name):
                        return None
                    return name

                # Check for inline name: "(72) Inventor: NAME, Given"
                if ":" in rest:
                    inline = rest.split(":", 1)[1].strip()
                    inv_name = _clean_inventor(inline)
                    if inv_name:
                        inventors.append(inv_name)

                # Check subsequent lines for additional inventors
                for j in range(i + 1, len(lines)):
                    inv_line = lines[j].strip()
                    if inid_re.match(inv_line):
                        break
                    inv_name = _clean_inventor(inv_line)
                    if inv_name:
                        inventors.append(inv_name)
                if inventors:
                    metadata["inventors"] = inventors

            i += 1

        # Kind code from filename (e.g. EP1577413_A1.pdf -> A1)
        kind_match = re.search(r"_([A-Z]\d)\.pdf$", Path(pdf_path).name, re.IGNORECASE)
        if kind_match:
            metadata["kind_code"] = kind_match.group(1).upper()

        # Decode HTML entities (e.g. &amp; -> &) from Markdown source
        for key, val in list(metadata.items()):
            if isinstance(val, str):
                metadata[key] = html.unescape(val)
            elif val is not None and isinstance(val, list):
                metadata[key] = [html.unescape(v) if isinstance(v, str) else v for v in val]

        return metadata
