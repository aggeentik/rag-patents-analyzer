# Phase 1 Quick Start Guide

## Installation

```bash
# Install dependencies
pip install -r requirements-phase1.txt
```

## Add Test PDFs

Place your patent PDF files in the `data/raw/` directory:

```bash
# Example structure
data/
└── raw/
    ├── patent1.pdf
    ├── patent2.pdf
    └── patent3.pdf
```

## Run Test

```bash
python test_phase1.py
```

## Expected Output

The test script will:
1. Find PDF files in `data/raw/`
2. Extract the first PDF using PatentPDFParser
3. Create chunks using PatentChunker
4. Display statistics and sample outputs

Example output:
```
============================================================
Testing Phase 1: PDF Parsing
============================================================

✓ Found 3 PDF file(s)

Testing with: patent1.pdf
------------------------------------------------------------

1. Extracting PDF...
   ✓ Patent ID: EP1234567
   ✓ Title: Steel composition for high strength applications...
   ✓ Elements extracted: 245
   ✓ Tables found: 8
   ✓ Total pages: 28

2. Chunking patent...
   ✓ Chunks created: 87

   Chunks by section:
     - Abstract: 3 chunks
     - Background: 12 chunks
     - Claims: 25 chunks
     - Detailed Description: 40 chunks
     - Examples: 7 chunks

============================================================
✅ Phase 1 test completed successfully!
============================================================
```

## Usage in Code

```python
from src.extraction.pdf_parser import PatentPDFParser
from src.extraction.chunker import PatentChunker

# Initialize
parser = PatentPDFParser(use_hi_res=False)  # Fast mode
chunker = PatentChunker(chunk_size=500, chunk_overlap=50)

# Process a patent
patent_data = parser.extract("data/raw/your_patent.pdf")
chunks = chunker.chunk_patent(patent_data)

# Examine results
print(f"Patent: {patent_data['patent_id']}")
print(f"Total chunks: {len(chunks)}")

for chunk in chunks[:5]:
    print(f"\nChunk ID: {chunk.chunk_id}")
    print(f"Section: {chunk.metadata['section']}")
    print(f"Content: {chunk.content[:100]}...")
```

## Troubleshooting

### No PDF files found

Make sure you have PDF files in `data/raw/`:
```bash
ls -l data/raw/*.pdf
```

### Installation errors

If `unstructured[pdf]` fails to install, try:
```bash
pip install unstructured --no-cache-dir
pip install "unstructured[pdf]" --no-cache-dir
```

### Slow extraction

Set `use_hi_res=False` in PatentPDFParser for faster extraction:
```python
parser = PatentPDFParser(use_hi_res=False)
```

## Next Steps

Once Phase 1 is working:
- **Phase 2**: Entity extraction and knowledge graph
- **Phase 3**: Retrieval systems (BM25, semantic, graph)
- **Phase 4**: LLM integration
- **Phase 5**: Streamlit UI
