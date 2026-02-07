from dataclasses import dataclass, field
from typing import Optional
import tiktoken
import re


@dataclass
class Chunk:
    """Single chunk for retrieval."""
    chunk_id: str
    patent_id: str
    content: str
    metadata: dict  # section, page, type, etc.
    entities: list = field(default_factory=list)  # Extracted entities
    references: list = field(default_factory=list)  # Cross-references (Table 1, Formula 2)


class PatentChunker:
    """Semantic chunking for patent documents."""

    # Reference patterns
    REFERENCE_PATTERNS = [
        r"Table\s*\d+",
        r"Formula\s*\(\d+\)",
        r"FIG\.?\s*\d+",
        r"Figure\s*\d+",
        r"Equation\s*\(\d+\)",
    ]

    def __init__(
        self,
        chunk_size: int = 500,      # Target tokens
        chunk_overlap: int = 50,     # Overlap tokens
        min_chunk_size: int = 100,   # Minimum tokens
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        self.tokenizer = tiktoken.get_encoding("cl100k_base")

    def chunk_patent(self, patent_data: dict) -> list[Chunk]:
        """
        Create chunks from extracted patent data.

        Rules:
        1. Tables → single chunk (never split)
        2. Formulas → single chunk with surrounding context
        3. Paragraphs → split at sentence boundaries if too large
        4. Preserve section context in every chunk
        5. Extract cross-references from each chunk
        """
        chunks = []
        current_section = "Unknown"

        for element in patent_data["elements"]:
            # Update current section
            if element.element_type == "title":
                detected = self._detect_section(element.text)
                if detected:
                    current_section = detected
                    continue

            # Tables: single chunk
            if element.element_type == "table":
                chunk = self._create_table_chunk(
                    element, patent_data["patent_id"], current_section
                )
                chunks.append(chunk)

            # Formulas: include context
            elif element.element_type == "formula":
                chunk = self._create_formula_chunk(
                    element, patent_data["patent_id"], current_section
                )
                chunks.append(chunk)

            # Text: chunk with overlap
            else:
                text_chunks = self._chunk_text(
                    element, patent_data["patent_id"], current_section
                )
                chunks.extend(text_chunks)

        # Assign sequential IDs
        for i, chunk in enumerate(chunks):
            chunk.chunk_id = f"{patent_data['patent_id']}_{i:04d}"

        return chunks

    def _chunk_text(
        self,
        element,
        patent_id: str,
        section: str
    ) -> list[Chunk]:
        """Split text into chunks at sentence boundaries."""
        text = element.text
        tokens = self._count_tokens(text)

        # If small enough, return as single chunk
        if tokens <= self.chunk_size:
            references = self._extract_references(text)
            return [Chunk(
                chunk_id="",  # Will be assigned later
                patent_id=patent_id,
                content=text,
                metadata={
                    "section": section,
                    "page": element.page,
                    "type": element.element_type,
                },
                entities=[],  # Will be extracted later
                references=references,
            )]

        # Split into sentences
        sentences = self._split_sentences(text)
        chunks = []
        current_chunk_sentences = []
        current_tokens = 0

        for sentence in sentences:
            sentence_tokens = self._count_tokens(sentence)

            # If adding this sentence exceeds chunk_size, save current chunk
            if current_tokens + sentence_tokens > self.chunk_size and current_chunk_sentences:
                chunk_text = " ".join(current_chunk_sentences)
                references = self._extract_references(chunk_text)

                chunks.append(Chunk(
                    chunk_id="",
                    patent_id=patent_id,
                    content=chunk_text,
                    metadata={
                        "section": section,
                        "page": element.page,
                        "type": element.element_type,
                    },
                    entities=[],
                    references=references,
                ))

                # Keep overlap sentences
                overlap_sentences = []
                overlap_tokens = 0
                for sent in reversed(current_chunk_sentences):
                    sent_tokens = self._count_tokens(sent)
                    if overlap_tokens + sent_tokens <= self.chunk_overlap:
                        overlap_sentences.insert(0, sent)
                        overlap_tokens += sent_tokens
                    else:
                        break

                current_chunk_sentences = overlap_sentences
                current_tokens = overlap_tokens

            # Add sentence to current chunk
            current_chunk_sentences.append(sentence)
            current_tokens += sentence_tokens

        # Add remaining sentences as final chunk
        if current_chunk_sentences:
            chunk_text = " ".join(current_chunk_sentences)
            if self._count_tokens(chunk_text) >= self.min_chunk_size:
                references = self._extract_references(chunk_text)
                chunks.append(Chunk(
                    chunk_id="",
                    patent_id=patent_id,
                    content=chunk_text,
                    metadata={
                        "section": section,
                        "page": element.page,
                        "type": element.element_type,
                    },
                    entities=[],
                    references=references,
                ))

        return chunks

    def _create_table_chunk(
        self,
        element,
        patent_id: str,
        section: str
    ) -> Chunk:
        """Create a single chunk for a table."""
        # Format table as text
        content = self._format_table(element)
        references = self._extract_references(content)

        return Chunk(
            chunk_id="",  # Will be assigned later
            patent_id=patent_id,
            content=content,
            metadata={
                "section": section,
                "page": element.page,
                "type": "table",
                "table_data": element.table_data,
            },
            entities=[],  # Will be extracted later
            references=references,
        )

    def _create_formula_chunk(
        self,
        element,
        patent_id: str,
        section: str
    ) -> Chunk:
        """Create a single chunk for a formula."""
        content = element.text
        references = self._extract_references(content)

        return Chunk(
            chunk_id="",
            patent_id=patent_id,
            content=content,
            metadata={
                "section": section,
                "page": element.page,
                "type": "formula",
            },
            entities=[],
            references=references,
        )

    def _format_table(self, element) -> str:
        """Format table element as readable text."""
        # Simple text representation of table
        if element.table_data:
            return f"Table:\n{element.text}"
        return element.text

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences."""
        # Simple sentence splitting on period, exclamation, question mark
        # followed by space and capital letter or end of string
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
        return [s.strip() for s in sentences if s.strip()]

    def _extract_references(self, text: str) -> list[str]:
        """Extract cross-references from text."""
        references = []
        for pattern in self.REFERENCE_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            references.extend(matches)
        return list(set(references))

    def _detect_section(self, text: str) -> Optional[str]:
        """Detect section from title text."""
        # Common patent sections
        sections = {
            "abstract": "Abstract",
            "claim": "Claims",
            "background": "Background",
            "description": "Detailed Description",
            "example": "Examples",
            "embodiment": "Embodiments",
            "brief": "Brief Description",
            "summary": "Summary",
            "field": "Field",
        }

        text_lower = text.lower()
        for key, section_name in sections.items():
            if key in text_lower:
                return section_name
        return None

    def _count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.tokenizer.encode(text))
