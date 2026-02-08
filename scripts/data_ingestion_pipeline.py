#!/usr/bin/env python3
"""Extract patents, build chunks, entities, and all indices."""

import argparse
import json
import sys
from pathlib import Path
from tqdm import tqdm

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.extraction.pdf_parser import PatentPDFParser
from src.chunking.chunker import PatentChunker
from src.extraction.entity_extractor import EntityExtractor
from src.knowledge_graph.builder import KnowledgeGraphBuilder
from src.knowledge_graph.store import KnowledgeGraphStore

# Import retrieval modules (will add after creating them)
try:
    from src.retrieval.bm25_retriever import BM25Retriever
    from src.retrieval.semantic_retriever import SemanticRetriever
    RETRIEVAL_AVAILABLE = True
except ImportError:
    RETRIEVAL_AVAILABLE = False
    print("⚠️  Retrieval modules not yet available. Will skip building BM25/FAISS indices.")


# Paths
DATA_DIR = project_root / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

PATENTS_JSON = PROCESSED_DIR / "patents.json"
BM25_INDEX = PROCESSED_DIR / "bm25_index.pkl"
FAISS_INDEX = PROCESSED_DIR / "faiss.index"
CHUNK_IDS = PROCESSED_DIR / "chunk_ids.json"
KG_DATABASE = PROCESSED_DIR / "knowledge_graph.db"


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Extract patents, build chunks, entities, and all indices.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process all PDFs in data/raw/
  python data_ingestion_pipeline.py

  # Process specific patents
  python data_ingestion_pipeline.py patent1.pdf patent2.pdf

  # Process patents with wildcards
  python data_ingestion_pipeline.py US*.pdf
        """
    )
    parser.add_argument(
        "patents",
        nargs="*",
        help="Specific patent PDF filenames to process (optional). If not specified, all PDFs in data/raw/ will be processed."
    )
    return parser.parse_args()


def main(patent_names=None):
    """Run full extraction pipeline."""
    print("=" * 70)
    print("PATENT EXTRACTION PIPELINE")
    print("=" * 70)
    print()

    # Ensure directories exist
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # Initialize components
    print("Initializing components...")

    # Configure PDF extraction
    # use_hi_res=True: Better accuracy, slower (~5+ min/patent), uses OCR
    # use_hi_res=False: Faster extraction (~30s/patent), may miss some layout details
    parser = PatentPDFParser(use_hi_res=True)

    chunker = PatentChunker()
    entity_extractor = EntityExtractor()
    kg_builder = KnowledgeGraphBuilder()
    print("✓ Components initialized\n")

    # Process PDFs
    all_pdf_files = sorted(RAW_DIR.glob("*.pdf"))

    # Filter PDF files based on patent_names argument
    if patent_names:
        # Create a set of requested patent names (without path, case-insensitive)
        requested_names = {name.lower() for name in patent_names}
        pdf_files = [
            pdf for pdf in all_pdf_files
            if pdf.name.lower() in requested_names
        ]

        # Check if all requested patents were found
        found_names = {pdf.name.lower() for pdf in pdf_files}
        missing_names = requested_names - found_names
        if missing_names:
            print(f"⚠️  Warning: The following patents were not found in {RAW_DIR}:")
            for name in missing_names:
                print(f"   • {name}")
            print()

        print(f"Processing {len(pdf_files)} of {len(all_pdf_files)} PDF files from {RAW_DIR}")
        if pdf_files:
            print("Selected patents:")
            for pdf in pdf_files:
                print(f"  • {pdf.name}")
    else:
        pdf_files = all_pdf_files
        print(f"Found {len(pdf_files)} PDF files in {RAW_DIR}")

    print()

    # Exit if no PDF files to process
    if not pdf_files:
        print("❌ No PDF files to process. Exiting.")
        return

    patents = []
    all_chunks = []

    for pdf_path in tqdm(pdf_files, desc="📄 Extracting PDFs"):
        try:
            # Extract
            patent_data = parser.extract(str(pdf_path))

            # Chunk
            chunks = chunker.chunk_patent(patent_data)

            # Extract entities from each chunk
            for chunk in chunks:
                entities = entity_extractor.extract_entities(chunk)
                chunk.entities = entities
                kg_builder.add_entities(entities)

            # Convert chunks to dictionaries for JSON serialization
            chunk_dicts = []
            for chunk in chunks:
                chunk_dict = {
                    "chunk_id": chunk.chunk_id,
                    "patent_id": chunk.patent_id,
                    "content": chunk.content,
                    "metadata": chunk.metadata,
                    "entities": [
                        {
                            "id": e.id,
                            "type": e.type.value,
                            "name": e.name,
                            "properties": e.properties,
                        }
                        for e in chunk.entities
                    ],
                    "references": chunk.references,
                }
                chunk_dicts.append(chunk_dict)

            patent_data["chunks"] = chunk_dicts
            patents.append(patent_data)
            all_chunks.extend(chunks)

        except Exception as e:
            print(f"\n❌ Error processing {pdf_path.name}: {str(e)}")
            continue

    print(f"\n✓ Extracted {len(patents)} patents with {len(all_chunks)} chunks")

    # Build relationships
    print("\n📊 Building knowledge graph relationships...")
    kg_builder.build_relationships(all_chunks)
    print(f"✓ Built {len(kg_builder.relationships)} relationships")

    # Save patents.json
    print("\n💾 Saving patents.json...")
    output = {
        "patents": patents,
        "total_patents": len(patents),
        "total_chunks": len(all_chunks),
        "extraction_config": {
            "chunk_size": 500,
            "overlap": 50,
        },
    }
    with open(PATENTS_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str, ensure_ascii=False)
    print(f"✓ Saved to {PATENTS_JSON}")

    # Save knowledge graph
    print("\n📊 Saving knowledge graph to database...")
    kg_store = KnowledgeGraphStore(str(KG_DATABASE))
    kg_store.connect()

    kg_data = kg_builder.export()
    for entity in tqdm(kg_data["entities"].values(), desc="  Saving entities"):
        kg_store.save_entity(entity)

    for rel in tqdm(kg_data["relationships"], desc="  Saving relationships"):
        kg_store.save_relationship(rel)

    kg_store.close()
    print(f"✓ Saved {len(kg_data['entities'])} entities and {len(kg_data['relationships'])} relationships")

    # Build BM25 index (if available)
    if RETRIEVAL_AVAILABLE:
        print("\n🔍 Building BM25 index...")
        # Convert chunks to dicts for BM25
        chunk_dicts = []
        for chunk in all_chunks:
            chunk_dicts.append({
                "chunk_id": chunk.chunk_id,
                "patent_id": chunk.patent_id,
                "content": chunk.content,
                "metadata": chunk.metadata,
            })

        bm25 = BM25Retriever()
        bm25.build_index(chunk_dicts)
        bm25.save(str(BM25_INDEX))
        print(f"✓ Saved BM25 index to {BM25_INDEX}")

        # Build FAISS index
        print("\n🔍 Building FAISS index (this may take a while)...")
        semantic = SemanticRetriever()
        semantic.build_index(chunk_dicts)
        semantic.save(str(FAISS_INDEX), str(CHUNK_IDS))
        print(f"✓ Saved FAISS index to {FAISS_INDEX}")
    else:
        print("\n⚠️  Skipping BM25 and FAISS index building (retrieval modules not available)")

    # Final summary
    print("\n" + "=" * 70)
    print("✅ EXTRACTION COMPLETE!")
    print("=" * 70)
    print(f"\nSummary:")
    print(f"  📄 Patents processed: {len(patents)}")
    print(f"  📝 Chunks created: {len(all_chunks)}")
    print(f"  🏷️  Entities extracted: {len(kg_data['entities'])}")
    print(f"  🔗 Relationships built: {len(kg_data['relationships'])}")
    print(f"\nOutput files:")
    print(f"  • {PATENTS_JSON}")
    print(f"  • {KG_DATABASE}")
    if RETRIEVAL_AVAILABLE:
        print(f"  • {BM25_INDEX}")
        print(f"  • {FAISS_INDEX}")
        print(f"  • {CHUNK_IDS}")
    print()


if __name__ == "__main__":
    args = parse_arguments()
    main(patent_names=args.patents if args.patents else None)
