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
            page = 1
            if hasattr(elem, 'metadata'):
                page = getattr(elem.metadata, 'page_number', 1)

            # Get coordinates
            coordinates = None
            if hasattr(elem, 'metadata') and hasattr(elem.metadata, 'coordinates'):
                coords = elem.metadata.coordinates
                if coords:
                    # Convert to dict format
                    coordinates = {
                        'x1': coords.points[0][0] if hasattr(coords, 'points') and coords.points else None,
                        'y1': coords.points[0][1] if hasattr(coords, 'points') and coords.points else None,
                        'x2': coords.points[2][0] if hasattr(coords, 'points') and len(coords.points) > 2 else None,
                        'y2': coords.points[2][1] if hasattr(coords, 'points') and len(coords.points) > 2 else None,
                    }

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

        # Apply post-processing to fix column/layout issues
        extracted = self._post_process_elements(extracted)

        # Apply intra-element text cleanup
        extracted = self._clean_element_text(extracted)

        return extracted

    def _clean_element_text(self, elements: list[ExtractedElement]) -> list[ExtractedElement]:
        """Clean up text within individual elements (dehyphenation, spacing)."""
        cleaned = []

        for elem in elements:
            text = elem.text

            # Fix hyphenation with space (e.g., "contain- ing" -> "containing")
            text = re.sub(r'(\w)- (\w)', r'\1\2', text)

            # Fix hyphenation at end of line (e.g., "word-\ning" -> "wording")
            text = re.sub(r'(\w)-\n(\w)', r'\1\2', text)

            # Fix missing spaces between words (basic heuristic)
            # Look for lowercase followed by uppercase
            text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)

            # Create new element with cleaned text
            cleaned.append(ExtractedElement(
                text=text,
                element_type=elem.element_type,
                page=elem.page,
                section=elem.section,
                coordinates=elem.coordinates,
                table_data=elem.table_data
            ))

        return cleaned

    def _post_process_elements(self, elements: list[ExtractedElement]) -> list[ExtractedElement]:
        """
        Post-process extracted elements to fix common issues:
        - Dehyphenation across column/page breaks
        - Text flow continuity
        - Column reading order validation
        """
        if not elements:
            return elements

        processed = []
        i = 0

        while i < len(elements):
            current = elements[i]

            # Skip if this is a table (don't merge tables)
            if current.element_type == "table":
                processed.append(current)
                i += 1
                continue

            # Look ahead to find next mergeable element (skip page headers/titles)
            next_idx, next_elem = self._find_next_mergeable(elements, i)

            if next_elem:
                # Merge if text ends with hyphen and continues in next element
                if self._should_dehyphenate(current, next_elem):
                    merged = self._merge_dehyphenated(current, next_elem)
                    processed.append(merged)
                    # Add any skipped elements (like page headers)
                    for j in range(i + 1, next_idx):
                        if elements[j].element_type in ["title"] and len(elements[j].text.strip()) < 20:
                            continue  # Skip short titles (likely page headers)
                        processed.append(elements[j])
                    i = next_idx + 1
                    continue

                # Merge if sentence is incomplete (mid-word break)
                elif self._should_merge_incomplete(current, next_elem):
                    merged = self._merge_elements(current, next_elem)
                    processed.append(merged)
                    # Add skipped elements
                    for j in range(i + 1, next_idx):
                        if elements[j].element_type in ["title"] and len(elements[j].text.strip()) < 20:
                            continue
                        processed.append(elements[j])
                    i = next_idx + 1
                    continue

            processed.append(current)
            i += 1

        # Sort by reading order using coordinates (if available)
        processed = self._sort_by_reading_order(processed)

        return processed

    def _find_next_mergeable(self, elements: list[ExtractedElement], current_idx: int) -> tuple[int, ExtractedElement]:
        """
        Find the next element that could be merged, skipping page headers/footers.
        Returns: (index, element) or (None, None)
        """
        current = elements[current_idx]

        # Look at next 3 elements (to skip page headers)
        for i in range(current_idx + 1, min(current_idx + 4, len(elements))):
            next_elem = elements[i]

            # Skip very short titles (likely page headers like "EP 1 577 413 A1")
            if next_elem.element_type == "title" and len(next_elem.text.strip()) < 20:
                continue

            # Must be same type (or close enough)
            if current.element_type == next_elem.element_type:
                return i, next_elem

            # Paragraph can merge with list
            if current.element_type in ["paragraph", "list"] and next_elem.element_type in ["paragraph", "list"]:
                return i, next_elem

        return None, None

    def _should_dehyphenate(self, current: ExtractedElement, next_elem: ExtractedElement) -> bool:
        """Check if current element ends with hyphen and should be joined with next."""
        # Don't merge different types (but allow paragraph + list)
        if current.element_type not in ["paragraph", "list"]:
            return False
        if next_elem.element_type not in ["paragraph", "list"]:
            return False

        # Don't merge if pages are too far apart
        if abs(current.page - next_elem.page) > 1:
            return False

        # Check if ends with hyphen (with optional space after)
        text = current.text.strip()

        # Handle "word- " or "word-" patterns
        if '- ' in text and text.rstrip().endswith('- '):
            # Remove trailing spaces to check
            text = text.rstrip()

        if not text.endswith('-'):
            return False

        # Next element should start with lowercase letter (continuation)
        next_text = next_elem.text.lstrip()
        if next_text and next_text[0].islower():
            return True

        return False

    def _should_merge_incomplete(self, current: ExtractedElement, next_elem: ExtractedElement) -> bool:
        """Check if current element has incomplete text that continues in next."""
        # Only merge same types
        if current.element_type != next_elem.element_type:
            return False

        # Don't merge titles or formulas
        if current.element_type in ["title", "formula"]:
            return False

        # Must be on same or adjacent pages
        if abs(current.page - next_elem.page) > 1:
            return False

        # Skip if next is likely a new paragraph (starts with capital, has proper spacing)
        next_text = next_elem.text.strip()
        if not next_text:
            return False

        # If next starts with lowercase, likely continuation
        if next_text[0].islower():
            return True

        # If current ends mid-sentence (no period, exclamation, question mark)
        current_text = current.text.rstrip()
        if current_text and current_text[-1] not in '.!?;:':
            # Check if it looks like it was cut off
            words = current_text.split()
            if words:
                last_word = words[-1].rstrip(',-')
                # If last word is very short (1-3 chars), might be incomplete
                if len(last_word) <= 3 and not last_word.isupper():
                    return True

        return False

    def _merge_dehyphenated(self, current: ExtractedElement, next_elem: ExtractedElement) -> ExtractedElement:
        """Merge elements where word is split by hyphen at line break."""
        # Remove trailing hyphen and whitespace from current
        current_text = current.text.rstrip()

        # Handle both "word-" and "word- " patterns
        if current_text.endswith('- '):
            current_text = current_text[:-2]  # Remove "- "
        elif current_text.endswith('-'):
            current_text = current_text[:-1]  # Remove "-"

        # Join directly without space (it's the same word)
        merged_text = current_text + next_elem.text.lstrip()

        return ExtractedElement(
            text=merged_text,
            element_type=current.element_type,
            page=current.page,
            section=current.section,
            coordinates=current.coordinates,
            table_data=current.table_data
        )

    def _merge_elements(self, current: ExtractedElement, next_elem: ExtractedElement) -> ExtractedElement:
        """Merge two elements with appropriate spacing."""
        # Join with space
        merged_text = current.text.rstrip() + ' ' + next_elem.text.lstrip()

        return ExtractedElement(
            text=merged_text,
            element_type=current.element_type,
            page=current.page,
            section=current.section,
            coordinates=current.coordinates,
            table_data=current.table_data
        )

    def _sort_by_reading_order(self, elements: list[ExtractedElement]) -> list[ExtractedElement]:
        """
        Sort elements by natural reading order using coordinates.
        For multi-column layout: left-to-right within columns, top-to-bottom overall.
        """
        # Group by page first
        pages = {}
        for elem in elements:
            if elem.page not in pages:
                pages[elem.page] = []
            pages[elem.page].append(elem)

        sorted_elements = []

        for page_num in sorted(pages.keys()):
            page_elements = pages[page_num]

            # Try to sort by coordinates if available
            elements_with_coords = [e for e in page_elements if e.coordinates]
            elements_without_coords = [e for e in page_elements if not e.coordinates]

            if elements_with_coords:
                # Detect if multi-column layout
                sorted_page = self._sort_multi_column(elements_with_coords)
                sorted_elements.extend(sorted_page)
                sorted_elements.extend(elements_without_coords)
            else:
                # No coordinates, keep original order
                sorted_elements.extend(page_elements)

        return sorted_elements

    def _sort_multi_column(self, elements: list[ExtractedElement]) -> list[ExtractedElement]:
        """Sort elements in multi-column layout."""
        if not elements:
            return elements

        # Calculate page width to detect column boundaries
        x_positions = []
        for elem in elements:
            if elem.coordinates and elem.coordinates.get('x1') is not None:
                x_positions.append(elem.coordinates['x1'])

        if not x_positions:
            return elements

        # Detect if there are two distinct column regions
        x_positions.sort()
        page_width = max(x_positions) - min(x_positions)

        # Simple heuristic: if elements cluster in left half and right half, it's 2-column
        midpoint = min(x_positions) + page_width / 2
        left_col = [e for e in elements if e.coordinates and e.coordinates.get('x1', 0) < midpoint]
        right_col = [e for e in elements if e.coordinates and e.coordinates.get('x1', 0) >= midpoint]

        # If significant elements in both columns, treat as multi-column
        if len(left_col) > 2 and len(right_col) > 2:
            # Sort each column by y-coordinate (top to bottom)
            left_col.sort(key=lambda e: e.coordinates.get('y1', 0) if e.coordinates else 0)
            right_col.sort(key=lambda e: e.coordinates.get('y1', 0) if e.coordinates else 0)

            # Return left column first, then right column
            return left_col + right_col
        else:
            # Single column or unclear, sort by y-coordinate only
            return sorted(elements, key=lambda e: e.coordinates.get('y1', 0) if e.coordinates else 0)

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
