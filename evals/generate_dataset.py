import argparse
import json
import logging
import warnings
from pathlib import Path

import pandas as pd
from langchain_core.documents import Document
from ragas.testset import TestsetGenerator
from ragas.testset.synthesizers import default_query_distribution

logger = logging.getLogger(__name__)


def load_chunks_as_documents(chunks_path: str) -> dict[str, list[Document]]:
    """Load Docling-processed chunks, merge by section into larger documents for RAGAS.

    RAGAS requires documents with >100 tokens. Individual chunks (~500 tokens) can be
    shorter (headers, small tables), so we concatenate chunks sharing the same section
    within each patent into single Documents. The text still comes from Docling's
    extraction, ensuring ground truths align with the RAG pipeline.
    """
    with open(chunks_path) as f:
        data = json.load(f)

    # Group chunks by (patent_id, section)
    grouped: dict[str, dict[str, list[dict]]] = {}
    for chunk in data["chunks"]:
        patent_id = chunk["patent_id"]
        section = chunk.get("metadata", {}).get("section", "unknown")
        grouped.setdefault(patent_id, {}).setdefault(section, []).append(chunk)

    docs_by_patent: dict[str, list[Document]] = {}
    for patent_id, sections in grouped.items():
        for section, chunks in sections.items():
            # Concatenate all chunks in this section into one document
            content = "\n\n".join(c["content"] for c in chunks)
            doc = Document(
                page_content=content,
                metadata={
                    "patent_id": patent_id,
                    "source": patent_id,
                    "section": section,
                    "chunk_count": len(chunks),
                },
            )
            docs_by_patent.setdefault(patent_id, []).append(doc)

    return docs_by_patent


def build_llm_and_embeddings(model: str):
    """Build RAGAS-wrapped LLM and embeddings."""
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_openai import ChatOpenAI
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper

    logger.info(f"Initializing LLM: {model}")
    if model.startswith("gpt-"):
        from langchain_openai import ChatOpenAI

        langchain_llm = ChatOpenAI(model=model)
    else:
        try:
            from langchain_litellm import ChatLiteLLM
        except ImportError:
            from langchain_community.chat_models import ChatLiteLLM
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
    parser = argparse.ArgumentParser(description="Generate synthetic QA dataset from patent chunks")
    parser.add_argument(
        "--chunks-path",
        default="data/processed/patents.json",
        help="Path to Docling-processed patents.json",
    )
    parser.add_argument("--testset-size", type=int, default=10)
    parser.add_argument("--output", default="evals/datasets/generated_testset.json")
    parser.add_argument("--model", default="azure_ai/gpt-4.1")
    args = parser.parse_args()

    chunks_path = Path(args.chunks_path)
    if not chunks_path.exists():
        raise FileNotFoundError(
            f"Chunks file not found: {chunks_path}. Run the data ingestion pipeline first."
        )

    # Load pre-processed chunks grouped by patent
    docs_by_patent = load_chunks_as_documents(str(chunks_path))
    patent_ids = sorted(docs_by_patent.keys())
    logger.info(f"Loaded chunks for {len(patent_ids)} patents: {patent_ids}")

    llm, embeddings = build_llm_and_embeddings(args.model)
    generator = TestsetGenerator(llm=llm, embedding_model=embeddings)

    # Customize distribution if you want fewer multi-hop questions
    query_distribution = default_query_distribution(llm)

    # Calculate how many questions to generate per document
    questions_per_doc = max(1, args.testset_size // len(patent_ids))
    all_dataframes = []

    # GENERATE PER DOCUMENT TO PREVENT CROSS-DOCUMENT HALLUCINATIONS
    for patent_id in patent_ids:
        docs = docs_by_patent[patent_id]
        logger.info(f"Processing {patent_id} ({len(docs)} chunks)...")

        try:
            testset = generator.generate_with_langchain_docs(
                documents=docs,
                testset_size=questions_per_doc,
                query_distribution=query_distribution,
            )
            df = testset.to_pandas()
            all_dataframes.append(df)
        except Exception as e:
            logger.error(f"Failed to generate questions for {patent_id}: {e}")

    # Combine all individual testsets
    final_df = pd.concat(all_dataframes, ignore_index=True)

    # Save outputs
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    final_df.to_json(output_path, orient="records", indent=2)
    final_df.to_csv(output_path.with_suffix(".csv"), index=False)
    logger.info(f"Successfully generated {len(final_df)} QA pairs.")


if __name__ == "__main__":
    main()
