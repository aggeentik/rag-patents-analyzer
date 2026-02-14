"""
RAGAS Testset Generation Pipeline

Generates synthetic QA pairs from raw patent PDFs using RAGAS's TestsetGenerator.
This automates dataset creation for evaluation, scaling beyond hand-crafted questions.

Usage:
    uv run python evals/generate_dataset.py --testset-size 10
    uv run python evals/generate_dataset.py --testset-size 50 --save-kg evals/datasets/kg.json
    uv run python evals/generate_dataset.py --load-kg evals/datasets/kg.json --testset-size 20
"""

import sys
import warnings
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import argparse
import logging

from src.logging_config import setup_logging

logger = logging.getLogger(__name__)


def load_documents(pdf_dir: str) -> list:
    """Load patent PDFs as LangChain Documents using PyMuPDFLoader.

    Pages are merged into one document per patent so that RAGAS's
    HeadlinesExtractor sees long documents (>500 tokens) and populates
    the 'headlines' property that HeadlineSplitter requires.
    """
    from langchain_community.document_loaders import PyMuPDFLoader
    from langchain_core.documents import Document

    pdf_path = Path(pdf_dir)
    pdf_files = sorted(pdf_path.glob("*.pdf"))

    if not pdf_files:
        raise FileNotFoundError(f"No PDF files found in {pdf_dir}")

    logger.info(f"Found {len(pdf_files)} PDF files in {pdf_dir}")

    all_docs = []
    for pdf_file in pdf_files:
        patent_id = pdf_file.stem
        logger.info(f"Loading {pdf_file.name}...")
        loader = PyMuPDFLoader(str(pdf_file))
        pages = loader.load()

        # Merge all pages into a single document per patent
        merged_content = "\n\n".join(page.page_content for page in pages)
        merged_doc = Document(
            page_content=merged_content,
            metadata={"patent_id": patent_id, "source": str(pdf_file), "total_pages": len(pages)},
        )
        all_docs.append(merged_doc)
        logger.debug(f"  {pdf_file.name}: {len(pages)} pages merged into 1 document")

    logger.info(f"Loaded {len(all_docs)} documents from {len(pdf_files)} PDFs")
    return all_docs


def load_knowledge_graph(kg_path: str):
    """Load a previously saved KnowledgeGraph."""
    from ragas.testset.graph import KnowledgeGraph

    logger.info(f"Loading KnowledgeGraph from {kg_path}...")
    kg = KnowledgeGraph.load(kg_path)
    logger.info(
        f"KnowledgeGraph loaded: {len(kg.nodes)} nodes, {len(kg.relationships)} relationships"
    )
    return kg


def build_llm_and_embeddings(model: str):
    """Build RAGAS-wrapped LLM and embeddings matching the eval pipeline pattern."""
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper

    try:
        from langchain_litellm import ChatLiteLLM
    except ImportError:
        from langchain_community.chat_models import ChatLiteLLM

    try:
        from langchain_huggingface import HuggingFaceEmbeddings
    except ImportError:
        from langchain_community.embeddings import HuggingFaceEmbeddings

    logger.info(f"Initializing LLM: {model}")
    langchain_llm = ChatLiteLLM(model=model)

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=DeprecationWarning)
        llm = LangchainLLMWrapper(langchain_llm)

    logger.info("Initializing embeddings: sentence-transformers/all-MiniLM-L6-v2")
    langchain_embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=DeprecationWarning)
        embeddings = LangchainEmbeddingsWrapper(langchain_embeddings)

    return llm, embeddings


def main():
    parser = argparse.ArgumentParser(
        description="Generate synthetic QA dataset from patent PDFs using RAGAS"
    )
    parser.add_argument(
        "--pdf-dir",
        default="data/raw/",
        help="Directory containing patent PDFs (default: data/raw/)",
    )
    parser.add_argument(
        "--testset-size",
        type=int,
        default=10,
        help="Number of test samples to generate (default: 10)",
    )
    parser.add_argument(
        "--output",
        default="evals/datasets/generated_testset.json",
        help="Output path for generated dataset (default: evals/datasets/generated_testset.json)",
    )
    parser.add_argument(
        "--model",
        default="azure_ai/gpt-4.1",
        help="LLM model for generation (default: azure_ai/gpt-4.1)",
    )
    parser.add_argument(
        "--save-kg",
        default=None,
        help="Save KnowledgeGraph to file for reuse (optional)",
    )
    parser.add_argument(
        "--load-kg",
        default=None,
        help="Load existing KnowledgeGraph instead of rebuilding (optional)",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    setup_logging(level=logging.DEBUG if args.verbose else logging.INFO)
    logger.info("RAGAS Testset Generation Pipeline")

    from ragas.testset import TestsetGenerator
    from ragas.testset.synthesizers import default_query_distribution

    llm, embeddings = build_llm_and_embeddings(args.model)

    generator = TestsetGenerator(llm=llm, embedding_model=embeddings)
    query_distribution = default_query_distribution(llm)

    if args.load_kg:
        # Use pre-built KG: load it, assign to generator, call generate() directly
        kg = load_knowledge_graph(args.load_kg)
        generator.knowledge_graph = kg

        logger.info(f"Generating {args.testset_size} test samples from loaded KG...")
        testset = generator.generate(
            testset_size=args.testset_size, query_distribution=query_distribution
        )
    else:
        # Build KG from documents and generate in one step
        docs = load_documents(args.pdf_dir)

        logger.info(
            f"Generating {args.testset_size} test samples "
            f"(includes KG construction, this may take a while)..."
        )
        testset = generator.generate_with_langchain_docs(
            documents=docs,
            testset_size=args.testset_size,
            query_distribution=query_distribution,
        )

        # Save KG for reuse if requested
        if args.save_kg:
            save_path = Path(args.save_kg)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            generator.knowledge_graph.save(args.save_kg)
            logger.info(f"KnowledgeGraph saved to {args.save_kg}")

    # Export as DataFrame -> CSV and JSON
    df = testset.to_pandas()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df.to_json(output_path, orient="records", indent=2)
    logger.info(f"Saved JSON: {output_path}")

    csv_path = output_path.with_suffix(".csv")
    df.to_csv(csv_path, index=False)
    logger.info(f"Saved CSV: {csv_path}")

    logger.info(f"Generated {len(df)} test samples with columns: {list(df.columns)}")
    logger.info("Done!")


if __name__ == "__main__":
    main()
