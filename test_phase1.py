#!/usr/bin/env python3
"""Test script for Phase 1: PDF Parsing and Chunking."""

import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.extraction.pdf_parser import PatentPDFParser
from src.extraction.chunker import PatentChunker


def test_phase1():
    """Test PDF parsing and chunking."""

    print("=" * 60)
    print("Testing Phase 1: PDF Parsing")
    print("=" * 60)

    # Check if we have any PDFs
    raw_dir = Path("data/raw")
    pdf_files = list(raw_dir.glob("*.pdf"))

    if not pdf_files:
        print("\n⚠️  No PDF files found in data/raw/")
        print("Please add some PDF files to data/raw/ to test extraction.")
        return

    print(f"\n✓ Found {len(pdf_files)} PDF file(s)")

    # Test with first PDF
    pdf_file=pdf_files[2]
    pdf_path = str(pdf_file)
    print(f"\nTesting with: {pdf_file.name}")
    print("-" * 60)

    # Initialize components
    parser = PatentPDFParser(use_hi_res=True)  # Use fast mode for testing
    chunker = PatentChunker(chunk_size=500, chunk_overlap=50)

    try:
        # Extract PDF
        print("\n1. Extracting PDF...")
        patent_data = parser.extract(pdf_path)

        print(f"   ✓ Patent ID: {patent_data['patent_id']}")
        print(f"   ✓ Title: {patent_data['title'][:80]}...")
        print(f"   ✓ Elements extracted: {len(patent_data['elements'])}")
        print(f"   ✓ Tables found: {len(patent_data['tables'])}")
        print(f"   ✓ Total pages: {patent_data['metadata']['total_pages']}")

        # Sample elements
        print("\n   First 5 elements:")
        for i, elem in enumerate(patent_data['elements'][:5], 1):
            text_preview = elem.text[:60].replace('\n', ' ')
            print(f"     {i}. [{elem.element_type}] {text_preview}...")

        # Chunk the patent
        print("\n2. Chunking patent...")
        chunks = chunker.chunk_patent(patent_data)

        print(f"   ✓ Chunks created: {len(chunks)}")

        # Show chunk statistics
        sections = {}
        for chunk in chunks:
            section = chunk.metadata.get('section', 'Unknown')
            sections[section] = sections.get(section, 0) + 1

        print("\n   Chunks by section:")
        for section, count in sorted(sections.items()):
            print(f"     - {section}: {count} chunks")

        # Sample chunks
        print("\n   Sample chunks:")
        for i, chunk in enumerate(chunks[:3], 1):
            print(f"\n   Chunk {i} ({chunk.chunk_id}):")
            print(f"     Section: {chunk.metadata.get('section', 'Unknown')}")
            print(f"     Page: {chunk.metadata.get('page', '?')}")
            print(f"     Type: {chunk.metadata.get('type', 'unknown')}")
            print(f"     Content length: {len(chunk.content)} chars")
            print(f"     References: {chunk.references}")
            content_preview = chunk.content[:150].replace('\n', ' ')
            print(f"     Preview: {content_preview}...")

        # Save chunks
        print("\n3. Saving chunks...")
        output_dir = Path("data/processed")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_file = output_dir / f"{patent_data['patent_id']}_chunks.json"
        chunks_data = [
            {
                "chunk_id": c.chunk_id,
                "content": c.content,
                "metadata": c.metadata,
                "references": c.references
            }
            for c in chunks
        ]
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(chunks_data, f, indent=2, ensure_ascii=False)
        
        print(f"   ✓ Saved to: {output_file}")

        print("\n" + "=" * 60)
        print("✅ Phase 1 test completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error during extraction: {e}")
        import traceback
        traceback.print_exc()
        return


if __name__ == "__main__":
    test_phase1()
