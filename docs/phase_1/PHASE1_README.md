# Phase 1: PDF Parsing - Implementation Complete

## Overview

Phase 1 implements layout-aware PDF extraction and semantic chunking for patent documents.

## What's Implemented

### 1. PDF Parser (`src/extraction/pdf_parser.py`)

**PatentPDFParser** class that provides:
- Layout-aware extraction using `unstructured` library
- Backup table extraction with `pdfplumber`
- Automatic patent ID detection from filename or content
- Section detection (Abstract, Claims, Description, etc.)
- Formula/equation detection
- Multi-column PDF support

**Features:**
- Extracts structured elements (titles, paragraphs, tables, lists, formulas)
- Preserves page numbers and section context
- Handles multi-column layouts
- Detects patent sections automatically

### 2. Chunker (`src/extraction/chunker.py`)

**PatentChunker** class that provides:
- Semantic chunking with configurable sizes
- Token-based chunking using tiktoken
- Sentence-boundary splitting
- Chunk overlap for context preservation
- Cross-reference extraction (Table X, Formula Y, Figure Z)

**Features:**
- Tables → single chunk (never split)
- Formulas → single chunk with context
- Paragraphs → split at sentence boundaries
- Preserves section context in metadata
- Extracts references to tables, formulas, figures

## Installation

```bash
# Install Phase 1 dependencies
pip install -r requirements-phase1.txt
```

## Usage

### Basic Usage

```python
from src.extraction.pdf_parser import PatentPDFParser
from src.extraction.chunker import PatentChunker

# Initialize
parser = PatentPDFParser(use_hi_res=True)
chunker = PatentChunker(chunk_size=500, chunk_overlap=50)

# Extract PDF
patent_data = parser.extract("data/raw/patent.pdf")

# Create chunks
chunks = chunker.chunk_patent(patent_data)

# Access results
for chunk in chunks:
    print(f"Chunk: {chunk.chunk_id}")
    print(f"Section: {chunk.metadata['section']}")
    print(f"Content: {chunk.content[:100]}...")
```

### Test Script

Run the test script to verify Phase 1 works:

```bash
# Add some PDF files to data/raw/ first
python test_phase1.py
```

## Data Structures

### ExtractedElement

```python
@dataclass
class ExtractedElement:
    text: str                    # Element text content
    element_type: str            # "title", "paragraph", "table", "list", "formula"
    page: int                    # Page number
    section: Optional[str]       # Section name (Abstract, Claims, etc.)
    coordinates: Optional[dict]  # Bounding box
    table_data: Optional[list]   # Table data if applicable
```

### Chunk

```python
@dataclass
class Chunk:
    chunk_id: str               # Unique identifier (patent_id_0001)
    patent_id: str              # Patent identifier
    content: str                # Chunk text content
    metadata: dict              # {section, page, type, ...}
    entities: list              # Extracted entities (Phase 2)
    references: list            # Cross-references (Table 1, etc.)
```

### Patent Data Dictionary

```python
{
    "patent_id": str,           # Patent identifier
    "title": str,               # Patent title
    "elements": list,           # List of ExtractedElement objects
    "tables": list,             # Separately extracted tables
    "metadata": {
        "filename": str,
        "total_pages": int,
        "extraction_method": str
    }
}
```

## Configuration

### PatentPDFParser

```python
PatentPDFParser(
    use_hi_res: bool = True    # Use hi-res OCR (slower but more accurate)
)
```

### PatentChunker

```python
PatentChunker(
    chunk_size: int = 500,      # Target chunk size in tokens
    chunk_overlap: int = 50,    # Overlap between chunks in tokens
    min_chunk_size: int = 100   # Minimum chunk size in tokens
)
```

## Section Detection

Automatically detects these patent sections:
- Abstract
- Claims
- Background
- Detailed Description
- Examples
- Embodiments
- Brief Description
- Summary
- Field

## Reference Extraction

Automatically extracts references to:
- Tables (Table 1, Table 2, etc.)
- Formulas (Formula (1), Formula (2), etc.)
- Figures (FIG. 1, Figure 2, etc.)
- Equations (Equation (1), etc.)

## Next Steps

Phase 1 is complete. Next phases:
- **Phase 2**: Knowledge Graph (entity extraction, relationships)
- **Phase 3**: Hybrid Retrieval (BM25, semantic, graph-based)
- **Phase 4**: LLM Integration (Bedrock/Ollama)
- **Phase 5**: Streamlit UI

## Testing

To test with your own PDFs:

1. Place PDF files in `data/raw/`
2. Run `python test_phase1.py`
3. Review the output showing extraction and chunking results

## Troubleshooting

**Issue: "unstructured" installation fails**
- Try: `pip install "unstructured[pdf]" --no-cache-dir`
- Or use conda: `conda install -c conda-forge unstructured`

**Issue: Slow extraction**
- Set `use_hi_res=False` for faster (but less accurate) extraction
- Hi-res mode uses OCR which is slower but handles complex layouts better

**Issue: Missing dependencies**
- unstructured may require system dependencies:
  - `poppler-utils` (for PDF processing)
  - `tesseract` (for OCR in hi-res mode)
