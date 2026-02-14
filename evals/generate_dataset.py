import os
import sys
import warnings
from pathlib import Path
import argparse
import logging
import pandas as pd

from llama_parse import LlamaParse
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from ragas.testset import TestsetGenerator
from ragas.testset.synthesizers import default_query_distribution

logger = logging.getLogger(__name__)


def load_and_chunk_document(pdf_file: Path) -> list[Document]:
    """
    Load a single patent PDF using LlamaParse to preserve table structures as Markdown,
    then chunk it appropriately.
    """
    logger.info(f"Parsing {pdf_file.name} with LlamaParse...")

    # LlamaParse preserves tables and complex layouts as Markdown
    parser = LlamaParse(result_type="markdown")
    parsed_docs = parser.load_data(str(pdf_file))

    # Combine parsed pages into one markdown string
    full_text = "\n\n".join([doc.text for doc in parsed_docs])

    # Intelligently chunk the document so RAGAS isn't overwhelmed by massive context windows
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1500, chunk_overlap=200, separators=["\n\n", "\n", " ", ""]
    )

    chunks = text_splitter.split_text(full_text)

    # Convert back to LangChain Document objects with strict metadata
    langchain_docs = [
        Document(
            page_content=chunk,
            metadata={"patent_id": pdf_file.stem, "source": str(pdf_file), "chunk_index": i},
        )
        for i, chunk in enumerate(chunks)
    ]

    return langchain_docs


def build_llm_and_embeddings(model: str):
    """Build RAGAS-wrapped LLM and embeddings."""
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from langchain_openai import ChatOpenAI
    from langchain_huggingface import HuggingFaceEmbeddings

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
    parser = argparse.ArgumentParser(description="Generate synthetic QA dataset from patent PDFs")
    parser.add_argument("--pdf-dir", default="data/raw/")
    parser.add_argument("--testset-size", type=int, default=10)
    parser.add_argument("--output", default="evals/datasets/generated_testset.json")
    parser.add_argument("--model", default="gpt-4o")
    parser.add_argument("--llama-api-key", default=None, help="LlamaParse API key (or set LLAMA_CLOUD_API_KEY env var)")
    args = parser.parse_args()

    if args.llama_api_key:
        os.environ["LLAMA_CLOUD_API_KEY"] = args.llama_api_key

    pdf_dir = Path(args.pdf_dir)
    pdf_files = sorted(pdf_dir.glob("*.pdf"))

    if not pdf_files:
        raise FileNotFoundError(f"No PDF files found in {pdf_dir}")

    llm, embeddings = build_llm_and_embeddings(args.model)
    generator = TestsetGenerator(llm=llm, embedding_model=embeddings)

    # Customize distribution if you want fewer multi-hop questions
    query_distribution = default_query_distribution(llm)

    # Calculate how many questions to generate per document
    questions_per_doc = max(1, args.testset_size // len(pdf_files))
    all_dataframes = []

    # GENERATE PER DOCUMENT TO PREVENT CROSS-DOCUMENT HALLUCINATIONS
    for pdf_file in pdf_files:
        logger.info(f"Processing {pdf_file.name}...")

        # 1. Parse and chunk a single document
        docs = load_and_chunk_document(pdf_file)

        # 2. Generate testset strictly for this document
        try:
            testset = generator.generate_with_langchain_docs(
                documents=docs,
                testset_size=questions_per_doc,
                query_distribution=query_distribution,
            )
            df = testset.to_pandas()
            all_dataframes.append(df)
        except Exception as e:
            logger.error(f"Failed to generate questions for {pdf_file.name}: {e}")

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
