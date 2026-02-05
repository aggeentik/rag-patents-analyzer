from unstructured.partition.pdf import partition_pdf
from unstructured.documents.elements import (
    Title, NarrativeText, Table, ListItem, Footer, Header
)
import pdfplumber
from dataclasses import dataclass
from typing import Optional
import re
import os


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
        print(f"Extracting {pdf_path}...")

        # Primary extraction with unstructured
        elements = self._extract_with_unstructured(pdf_path)

        # Backup table extraction with pdfplumber
        tables = self._extract_tables_with_pdfplumber(pdf_path)

        # Get first page text for patent ID extraction
        first_page_text = ""
        if elements:
            first_page_text = " ".join([e.text for e in elements[:10]])

        # Extract patent ID
        patent_id = self._extract_patent_id(pdf_path, first_page_text)

        # Extract title (usually first significant text)
        title = "Unknown Title"
        for elem in elements:
            if elem.element_type == "title" and len(elem.text) > 10:
                title = elem.text
                break

        # Get page count
        total_pages = 0
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)

        return {
            "patent_id": patent_id,
            "title": title,
            "elements": elements,
            "tables": tables,
            "metadata": {
                "filename": os.path.basename(pdf_path),
                "total_pages": total_pages,
                "extraction_method": "unstructured+pdfplumber"
            }
        }

    def _extract_with_unstructured(self, pdf_path: str) -> list[ExtractedElement]:
        """Primary extraction using unstructured library."""
        elements = partition_pdf(
            filename=pdf_path,
            strategy="hi_res" if self.use_hi_res else "fast",
            infer_table_structure=True,
            include_page_breaks=True,
        )

        # Convert to ExtractedElement objects
        extracted = []
        current_section = None

        for elem in elements:
            # Determine element type
            elem_type = "paragraph"
            if isinstance(elem, Title):
                elem_type = "title"
            elif isinstance(elem, Table):
                elem_type = "table"
            elif isinstance(elem, ListItem):
                elem_type = "list"
            elif isinstance(elem, (Header, Footer)):
                continue  # Skip headers and footers

            # Get text
            text = str(elem)
            if not text or len(text.strip()) < 3:
                continue

            # Detect if this is a section header
            detected_section = self._detect_section(text)
            if detected_section:
                current_section = detected_section
                if elem_type != "title":
                    elem_type = "title"

            # Detect formulas
            if self._detect_formula(text):
                elem_type = "formula"

            # Get page number
            page = getattr(elem, 'metadata', {}).get('page_number', 1) if hasattr(elem, 'metadata') else 1

            # Get coordinates
            coordinates = None
            if hasattr(elem, 'metadata') and hasattr(elem.metadata, 'coordinates'):
                coordinates = elem.metadata.coordinates

            # Get table data if table
            table_data = None
            if elem_type == "table" and hasattr(elem, 'metadata'):
                table_data = getattr(elem.metadata, 'text_as_html', None)

            extracted.append(ExtractedElement(
                text=text,
                element_type=elem_type,
                page=page,
                section=current_section,
                coordinates=coordinates,
                table_data=table_data
            ))

        return extracted

    def _extract_tables_with_pdfplumber(self, pdf_path: str) -> list[dict]:
        """Backup table extraction using pdfplumber."""
        tables = []
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                page_tables = page.extract_tables()
                for table in page_tables:
                    if table:
                        tables.append({
                            "page": page_num,
                            "headers": table[0] if table else [],
                            "rows": table[1:] if len(table) > 1 else [],
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
