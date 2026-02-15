#!/usr/bin/env python3
"""Extract patents, build chunks, entities, and all indices.

Uses:
- Docling for PDF parsing (replaces unstructured + pdfplumber)
- Atomic-unit chunking (replaces token-based splitting)
- Hybrid entity extraction (regex default, optional LLM via --use-llm-extraction)
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from tqdm import tqdm

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.logging_config import setup_logging  # noqa: E402

logger = logging.getLogger(__name__)

from src.chunking.chunker import PatentChunker  # noqa: E402
from src.extraction.entity_extractor import EntityExtractor  # noqa: E402
from src.extraction.pdf_parser import PatentPDFParser  # noqa: E402
from src.knowledge_graph.builder import KnowledgeGraphBuilder  # noqa: E402
from src.knowledge_graph.store import KnowledgeGraphStore  # noqa: E402

# Import retrieval modules (optional)
try:
    from src.retrieval.bm25_retriever import BM25Retriever
    from src.retrieval.semantic_retriever import SemanticRetriever

    RETRIEVAL_AVAILABLE = True
except ImportError:
    RETRIEVAL_AVAILABLE = False
    # Note: Will log warning after setup_logging() is called in main()


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

  # Process with LLM-based entity extraction
  python data_ingestion_pipeline.py --use-llm-extraction
        """,
    )
    parser.add_argument(
        "patents",
        nargs="*",
        help="Specific patent PDF filenames to process (optional). If not specified, all PDFs in data/raw/ will be processed.",
    )
    parser.add_argument(
        "--use-llm-extraction",
        action="store_true",
        default=False,
        help="Enable LLM-based entity extraction via Instructor (requires LLM configured in .env).",
    )
    return parser.parse_args()


def main(patent_names=None, use_llm_extraction=False):
    """Run full extraction pipeline."""
    # Set up logging
    setup_logging()

    logger.info("=" * 70)
    logger.info("PATENT EXTRACTION PIPELINE")
    logger.info("=" * 70)

    if not RETRIEVAL_AVAILABLE:
        logger.warning("Retrieval modules not available. Will skip building BM25/FAISS indices.")

    # Ensure directories exist
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # Initialize components
    logger.info("Initializing components...")
    pdf_parser = PatentPDFParser()
    chunker = PatentChunker()

    # Entity extractor: optionally with LLM
    llm_client = None
    if use_llm_extraction:
        from src.llm.llm_client import LLMClient  # noqa: PLC0415

        llm_client = LLMClient.from_env()
        logger.info("LLM extraction enabled: %s", llm_client.model)

    entity_extractor = EntityExtractor(llm_client=llm_client, use_llm=use_llm_extraction)
    kg_builder = KnowledgeGraphBuilder()
    logger.info("Components initialized")

    # Process PDFs
    all_pdf_files = sorted(RAW_DIR.glob("*.pdf"))

    # Filter PDF files based on patent_names argument
    if patent_names:
        requested_names = {name.lower() for name in patent_names}
        pdf_files = [pdf for pdf in all_pdf_files if pdf.name.lower() in requested_names]

        found_names = {pdf.name.lower() for pdf in pdf_files}
        missing_names = requested_names - found_names
        if missing_names:
            logger.warning("The following patents were not found in %s:", RAW_DIR)
            for name in missing_names:
                logger.warning("   - %s", name)

        logger.info(
            "Processing %d of %d PDF files from %s",
            len(pdf_files),
            len(all_pdf_files),
            RAW_DIR,
        )
        if pdf_files:
            logger.info("Selected patents:")
            for pdf in pdf_files:
                logger.info("  - %s", pdf.name)
    else:
        pdf_files = all_pdf_files
        logger.info("Found %d PDF files in %s", len(pdf_files), RAW_DIR)

    if not pdf_files:
        logger.warning("No PDF files to process. Exiting.")
        return

    all_chunks = []
    patent_summaries = []

    for pdf_path in tqdm(pdf_files, desc="Extracting PDFs"):
        try:
            # 1. Parse PDF -> PatentDocument
            patent_doc = pdf_parser.extract(str(pdf_path))

            # 2. Chunk -> list[PatentChunk]
            chunks = chunker.chunk_patent(patent_doc)

            # 3. Extract entities from each chunk
            for chunk in chunks:
                entities = entity_extractor.extract_entities(chunk)
                chunk.entities = entities
                kg_builder.add_entities(entities)

            all_chunks.extend(chunks)

            patent_summaries.append(
                {
                    "patent_id": patent_doc.patent_id,
                    "title": patent_doc.title,
                    "num_chunks": len(chunks),
                    "metadata": patent_doc.metadata,
                }
            )

        except Exception as e:
            logger.error("Error processing %s: %s", pdf_path.name, str(e))
            continue

    logger.info("Extracted %d patents with %d chunks", len(patent_summaries), len(all_chunks))

    # Build relationships
    logger.info("Building knowledge graph relationships...")
    kg_builder.build_relationships(all_chunks)
    logger.info("Built %d relationships", len(kg_builder.relationships))

    # Save patents.json using to_retrieval_dict()
    logger.info("Saving patents.json...")
    chunk_dicts = [chunk.to_retrieval_dict() for chunk in all_chunks]
    output = {
        "patents": patent_summaries,
        "chunks": chunk_dicts,
        "total_patents": len(patent_summaries),
        "total_chunks": len(all_chunks),
        "extraction_config": {
            "parser": "docling",
            "chunking": "atomic_unit",
            "llm_extraction": use_llm_extraction,
        },
    }
    with open(PATENTS_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str, ensure_ascii=False)
    logger.info("Saved to %s", PATENTS_JSON)

    # Save knowledge graph
    logger.info("Saving knowledge graph to database...")
    kg_store = KnowledgeGraphStore(str(KG_DATABASE))
    kg_store.connect()

    kg_data = kg_builder.export()
    for entity in tqdm(kg_data["entities"].values(), desc="  Saving entities"):
        kg_store.save_entity(entity)

    for rel in tqdm(kg_data["relationships"], desc="  Saving relationships"):
        kg_store.save_relationship(rel)

    # Embed entity names for semantic matching
    logger.info("Embedding entity names for semantic matching...")
    from sentence_transformers import SentenceTransformer  # noqa: PLC0415

    embed_model = SentenceTransformer("all-MiniLM-L6-v2")
    entity_items = list(kg_data["entities"].items())
    entity_names = [entity["name"] for _, entity in entity_items]
    embeddings = embed_model.encode(entity_names, show_progress_bar=False)

    embedding_pairs = [(entity["id"], embeddings[i]) for i, (_, entity) in enumerate(entity_items)]
    kg_store.save_entity_embeddings_batch(embedding_pairs)
    logger.info("Saved %d entity embeddings", len(embedding_pairs))

    kg_store.close()
    logger.info(
        "Saved %d entities and %d relationships",
        len(kg_data["entities"]),
        len(kg_data["relationships"]),
    )

    # Build BM25 index (if available)
    if RETRIEVAL_AVAILABLE:
        logger.info("Building BM25 index...")
        bm25 = BM25Retriever()
        bm25.build_index(chunk_dicts)
        bm25.save(str(BM25_INDEX))

        logger.info("Building FAISS index (this may take a while)...")
        semantic = SemanticRetriever()
        semantic.build_index(chunk_dicts)
        semantic.save(str(FAISS_INDEX), str(CHUNK_IDS))
    else:
        logger.info("Skipping BM25 and FAISS index building (retrieval modules not available)")

    # Final summary
    logger.info("=" * 70)
    logger.info("EXTRACTION COMPLETE!")
    logger.info("=" * 70)
    logger.info("Summary:")
    logger.info("  Patents processed: %d", len(patent_summaries))
    logger.info("  Chunks created: %d", len(all_chunks))
    logger.info("  Entities extracted: %d", len(kg_data["entities"]))
    logger.info("  Relationships built: %d", len(kg_data["relationships"]))
    logger.info("Output files:")
    logger.info("  - %s", PATENTS_JSON)
    logger.info("  - %s", KG_DATABASE)
    if RETRIEVAL_AVAILABLE:
        logger.info("  - %s", BM25_INDEX)
        logger.info("  - %s", FAISS_INDEX)
        logger.info("  - %s", CHUNK_IDS)


if __name__ == "__main__":
    args = parse_arguments()
    main(
        patent_names=args.patents if args.patents else None,
        use_llm_extraction=args.use_llm_extraction,
    )
