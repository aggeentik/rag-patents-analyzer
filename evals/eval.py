"""
RAGAS Evaluation Script for Patents Analyzer RAG System

This script:
1. Loads the RAGAS test dataset
2. Runs the hybrid retrieval system for each question
3. Generates answers using the LLM
4. Evaluates using RAGAS metrics
5. Generates a comprehensive evaluation report

Usage:
    uv run python scripts/evaluate_ragas.py [--top-k 5] [--output results.json]
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import argparse  # noqa: E402
import json  # noqa: E402
import logging  # noqa: E402
from datetime import datetime  # noqa: E402
from typing import Any  # noqa: E402

from src.knowledge_graph.store import KnowledgeGraphStore  # noqa: E402
from src.llm import AnswerGenerator, LLMClient  # noqa: E402
from src.logging_config import setup_logging  # noqa: E402
from src.retrieval import (  # noqa: E402
    BM25Retriever,
    GraphRetriever,
    HybridRetriever,
    SemanticRetriever,
)

logger = logging.getLogger(__name__)


def load_dataset(dataset_path: str) -> dict[str, Any]:
    """Load RAGAS dataset from JSON file."""
    with open(dataset_path, "r") as f:
        return json.load(f)


def load_chunks(chunks_path: str) -> list[dict[str, Any]]:
    """Load processed chunks."""
    with open(chunks_path, "r") as f:
        data = json.load(f)
        return data["chunks"]


def initialize_retrievers(chunks: list[dict[str, Any]], data_dir: Path) -> HybridRetriever:
    """Initialize BM25, Semantic, and Graph retrievers and combine them."""
    logger.info("Loading retrievers...")

    # Load BM25
    bm25 = BM25Retriever.load(str(data_dir / "bm25_index.pkl"), chunks)
    logger.info(f"✓ BM25 retriever loaded with {len(chunks)} chunks")

    # Load Semantic
    semantic = SemanticRetriever.load(
        str(data_dir / "faiss.index"), str(data_dir / "chunk_ids.json"), chunks
    )
    logger.info(f"✓ Semantic retriever loaded with {len(chunks)} chunks")

    # Load Graph
    kg_store = KnowledgeGraphStore(str(data_dir / "knowledge_graph.db"))
    kg_store.connect()
    graph = GraphRetriever.load("", chunks, kg_store, max_hops=2, score_decay=0.5)
    logger.info("✓ Graph retriever loaded")

    # Create hybrid retriever
    hybrid = HybridRetriever(
        bm25_retriever=bm25,
        semantic_retriever=semantic,
        graph_retriever=graph,
        weights={"bm25": 1.0, "semantic": 1.0, "graph": 0.5},
        rrf_k=60,
    )
    logger.info("✓ Hybrid retriever initialized")

    return hybrid


def run_evaluation(
    dataset: dict[str, Any],
    hybrid_retriever: HybridRetriever,
    answer_generator: AnswerGenerator,
    top_k: int = 5,
) -> dict[str, Any]:
    """
    Run RAG pipeline on all test cases and prepare data for RAGAS evaluation.

    Returns a dict with:
        - questions: List[str]
        - ground_truths: List[str]
        - contexts: List[List[str]] - retrieved contexts for each question
        - answers: List[str] - generated answers
        - detailed_results: List[Dict] - detailed results per question
    """
    results: dict[str, Any] = {
        "questions": [],
        "ground_truths": [],
        "contexts": [],
        "answers": [],
        "detailed_results": [],
    }

    total = len(dataset["test_cases"])

    for idx, test_case in enumerate(dataset["test_cases"], 1):
        question_id = test_case["id"]
        question = test_case["question"]
        ground_truth = test_case["ground_truth"]
        category = test_case["category"]

        logger.info(f"\n{'=' * 80}")
        logger.info(f"[{idx}/{total}] {question_id}: {category}")
        logger.info(f"Question: {question}")
        logger.info(f"{'=' * 80}")

        try:
            # Retrieve contexts
            logger.info(f"Retrieving top {top_k} chunks...")
            retrieved_chunks = hybrid_retriever.search(question, top_k=top_k)

            # Extract context strings
            context_list = [chunk["content"] for chunk in retrieved_chunks]

            # Get retriever statistics
            stats = hybrid_retriever.get_retriever_stats(retrieved_chunks)
            logger.info(
                f"Retriever stats: BM25={stats['bm25_hits']}, "
                f"Semantic={stats['semantic_hits']}, Graph={stats['graph_hits']}"
            )

            # Generate answer
            logger.info("Generating answer...")
            result = answer_generator.generate_answer(
                question=question,
                retrieved_chunks=retrieved_chunks,
                temperature=0.0,
                stream=False,  # Don't stream during evaluation
            )

            answer = result["answer"]

            logger.info(f"\nGenerated Answer:\n{answer[:200]}...")

            # Store results
            results["questions"].append(question)
            results["ground_truths"].append(ground_truth)
            results["contexts"].append(context_list)
            results["answers"].append(answer)

            # Detailed results for analysis
            detailed = {
                "id": question_id,
                "category": category,
                "retrieval_type": test_case["retrieval_type"],
                "question": question,
                "ground_truth": ground_truth,
                "contexts": context_list,
                "answer": answer,
                "retriever_stats": stats,
                "retrieved_chunks": [
                    {
                        "chunk_id": chunk["chunk_id"],
                        "patent_id": chunk.get("patent_id", ""),
                        "section": chunk.get("section", ""),
                        "page": chunk.get("page", ""),
                        "rrf_score": chunk.get("rrf_score", 0.0),
                        "content_preview": chunk["content"][:200],
                    }
                    for chunk in retrieved_chunks
                ],
                "metadata": result["metadata"],
            }
            results["detailed_results"].append(detailed)

        except Exception as e:
            logger.error(f"Error processing {question_id}: {e!s}")
            # Store partial results
            results["questions"].append(question)
            results["ground_truths"].append(ground_truth)
            results["contexts"].append([])
            results["answers"].append(f"ERROR: {e!s}")
            results["detailed_results"].append(
                {"id": question_id, "category": category, "error": str(e)}
            )

    return results


def calculate_ragas_metrics(
    results: dict[str, Any], llm_client: LLMClient | None = None, ragas_model: str | None = None
) -> dict[str, float]:
    """
    Calculate RAGAS metrics using the configured LLM.

    Requires: pip install ragas
    """
    try:
        import warnings  # noqa: PLC0415

        # Suppress RAGAS deprecation warnings
        # Note: Using legacy metrics API (deprecated but functional with LangChain LLMs)
        # RAGAS v1.0+ API requires using llm_factory() which is incompatible with LangChain
        warnings.filterwarnings("ignore", category=DeprecationWarning, message=".*ragas.metrics.*")

        from datasets import Dataset  # noqa: PLC0415  # type: ignore[attr-defined]
        from ragas import evaluate  # noqa: PLC0415
        from ragas.metrics import (  # noqa: PLC0415
            answer_relevancy,
            context_precision,
            context_recall,
            faithfulness,
        )

        # Try to import from new LangChain packages first, fall back to old ones
        try:
            from langchain_litellm import ChatLiteLLM  # noqa: PLC0415
        except ImportError:
            from langchain_community.chat_models import ChatLiteLLM  # noqa: PLC0415

        try:
            from langchain_huggingface import HuggingFaceEmbeddings  # noqa: PLC0415
        except ImportError:
            from langchain_community.embeddings import HuggingFaceEmbeddings  # noqa: PLC0415

    except ImportError as e:
        logger.warning(f"RAGAS library not installed or import error: {e}")
        logger.info("To install: uv pip install ragas datasets langchain-community")
        return {}

    logger.info("\n" + "=" * 80)
    logger.info("Calculating RAGAS metrics...")
    logger.info("=" * 80)

    try:
        # Configure RAGAS LLM
        if ragas_model:
            # Use the specified RAGAS model (e.g., gpt-3.5-turbo, gpt-4, azure/gpt-4)
            logger.info(f"Using dedicated LLM for RAGAS evaluation: {ragas_model}")
            if ragas_model.startswith("gpt-") and not ragas_model.startswith("gpt-4o"):
                # Standard OpenAI model
                from langchain_openai import ChatOpenAI  # noqa: PLC0415

                llm = ChatOpenAI(model=ragas_model)
            elif ragas_model.startswith("azure/"):
                # Azure OpenAI - use LiteLLM which handles Azure format
                logger.info("Using Azure OpenAI endpoint")
                llm = ChatLiteLLM(model=ragas_model)  # type: ignore[assignment]
            else:
                # LiteLLM for other providers (including gpt-4o, anthropic, etc.)
                llm = ChatLiteLLM(model=ragas_model)  # type: ignore[assignment]
        elif llm_client:
            # Use the main LLM client
            logger.info(f"Using main LLM for RAGAS evaluation: {llm_client.model}")
            llm = ChatLiteLLM(model=llm_client.model)  # type: ignore[assignment]
        else:
            # Fallback to OpenAI
            from langchain_openai import ChatOpenAI  # noqa: PLC0415

            logger.info("Using OpenAI GPT-3.5-turbo for RAGAS metrics")
            llm = ChatOpenAI(model="gpt-3.5-turbo")

        # Use HuggingFace embeddings (same as retrieval system)
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

        # Create dataset for RAGAS
        data = {
            "question": results["questions"],
            "answer": results["answers"],
            "contexts": results["contexts"],
            "ground_truth": results["ground_truths"],
        }

        dataset = Dataset.from_dict(data)

        # Calculate metrics with custom LLM and embeddings
        logger.info(
            "Computing faithfulness, answer_relevancy, context_precision, context_recall..."
        )
        evaluation_results = evaluate(
            dataset,
            metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
            llm=llm,
            embeddings=embeddings,
        )

        # Convert to dict (evaluation_results is an EvaluationResult object or DataFrame)
        metrics_dict = {}

        logger.info(f"Evaluation results type: {type(evaluation_results)}")
        logger.debug(f"Evaluation results repr: {repr(evaluation_results)}")

        try:
            # RAGAS v1.0+ returns an EvaluationResult object with a 'scores' attribute
            if hasattr(evaluation_results, "scores"):
                logger.info("Extracting metrics from .scores attribute...")
                scores = evaluation_results.scores

                # scores could be a DataFrame or a list of dicts
                if hasattr(scores, "to_dict"):
                    # It's a DataFrame - get the mean of each column
                    logger.info("Converting scores DataFrame to dict...")
                    if hasattr(scores, "mean"):
                        # Get mean values
                        mean_scores = scores.mean()
                        if hasattr(mean_scores, "to_dict"):
                            metrics_dict = {k: float(v) for k, v in mean_scores.to_dict().items()}
                        else:
                            # mean_scores might be a Series, try direct iteration
                            for key in scores.columns:
                                metrics_dict[key] = float(scores[key].mean())
                    else:
                        # No mean method, try to_dict directly
                        scores_dict = scores.to_dict()
                        # Might be column-oriented like {'metric': {0: val1, 1: val2}}
                        for key, values in scores_dict.items():
                            if isinstance(values, dict):
                                # Extract any numeric value
                                for val in values.values():
                                    if isinstance(val, (int, float)):
                                        metrics_dict[key] = float(val)
                                        break
                            elif isinstance(values, (int, float)):
                                metrics_dict[key] = float(values)

                elif isinstance(scores, (list, tuple)) and len(scores) > 0:
                    # It's a list of score dicts - aggregate them
                    logger.info(f"Aggregating {len(scores)} score entries...")
                    # Collect all values for each metric
                    metric_values = {}
                    for score_entry in scores:
                        if isinstance(score_entry, dict):
                            for key, value in score_entry.items():
                                if isinstance(value, (int, float)):
                                    if key not in metric_values:
                                        metric_values[key] = []
                                    metric_values[key].append(float(value))

                    # Calculate means
                    for key, values in metric_values.items():
                        if values:
                            metrics_dict[key] = sum(values) / len(values)

            # Fallback: Try dict() conversion (for dict-like objects)
            if not metrics_dict:
                try:
                    logger.info("Trying dict() conversion...")
                    result_dict = dict(evaluation_results)
                    logger.info(f"Converted to dict: {result_dict}")

                    for key, value in result_dict.items():
                        if isinstance(value, (int, float)):
                            metrics_dict[key] = float(value)
                        elif isinstance(value, dict) and len(value) > 0:
                            # Handle nested dict
                            for nested_val in value.values():
                                if isinstance(nested_val, (int, float)):
                                    metrics_dict[key] = float(nested_val)
                                    break

                except (TypeError, ValueError) as e:
                    logger.debug(f"dict() conversion failed: {e}")

                # Try direct dictionary access (for dict instances)
                if isinstance(evaluation_results, dict):
                    logger.info("Parsing as dict...")
                    for key, value in evaluation_results.items():
                        if isinstance(value, (int, float)):
                            metrics_dict[key] = float(value)
                        elif isinstance(value, dict) and len(value) > 0:
                            for nested_val in value.values():
                                if isinstance(nested_val, (int, float)):
                                    metrics_dict[key] = float(nested_val)
                                    break

                # Try to_dict() method (for pandas DataFrame and some Result objects)
                elif hasattr(evaluation_results, "to_dict"):
                    logger.info("Parsing with to_dict()...")
                    result_dict = evaluation_results.to_dict()
                    logger.debug(f"Result dict: {result_dict}")

                    for key, value in result_dict.items():
                        if isinstance(value, (int, float)):
                            metrics_dict[key] = float(value)
                        elif isinstance(value, dict) and len(value) > 0:
                            for nested_val in value.values():
                                if isinstance(nested_val, (int, float)):
                                    metrics_dict[key] = float(nested_val)
                                    break

                # Try as object attributes (for Result objects)
                else:
                    logger.info("Parsing as object attributes...")
                    for attr in [
                        "faithfulness",
                        "answer_relevancy",
                        "context_precision",
                        "context_recall",
                    ]:
                        if hasattr(evaluation_results, attr):
                            value = getattr(evaluation_results, attr)
                            if isinstance(value, (int, float)):
                                metrics_dict[attr] = float(value)

            logger.info(f"Extracted metrics: {metrics_dict}")

            if not metrics_dict:
                logger.warning("No metrics extracted! Trying alternative approaches...")
                # Last resort: check if it's a pandas DataFrame with mean values
                if hasattr(evaluation_results, "mean"):
                    logger.info("Trying DataFrame.mean()...")
                    mean_values = evaluation_results.mean()
                    if hasattr(mean_values, "to_dict"):
                        metrics_dict = {k: float(v) for k, v in mean_values.to_dict().items()}

        except Exception as e:
            logger.error(f"Error parsing evaluation results: {e}")
            logger.info(f"Evaluation results type: {type(evaluation_results)}")
            logger.info(f"Evaluation results dir: {dir(evaluation_results)}")
            # Try to show the actual structure
            if hasattr(evaluation_results, "__dict__"):
                logger.info(f"Evaluation results __dict__: {evaluation_results.__dict__}")

        return metrics_dict

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error calculating RAGAS metrics: {error_msg}")
        logger.warning("\n" + "!" * 80)
        logger.warning("RAGAS metrics calculation failed.")
        logger.warning("If using Ollama, make sure the model is running: ollama list")
        logger.warning("If using Bedrock, check AWS credentials are configured.")
        logger.warning("Evaluation results are still saved without RAGAS metrics.")
        logger.warning("!" * 80 + "\n")
        return {}


def generate_report(results: dict[str, Any], ragas_metrics: dict[str, float], output_path: str):
    """Generate comprehensive evaluation report."""

    # Add RAGAS metrics to results
    results["ragas_metrics"] = ragas_metrics
    results["evaluation_timestamp"] = datetime.now().isoformat()

    # Calculate category-wise statistics
    category_stats = {}
    for detail in results["detailed_results"]:
        category = detail.get("category", "Unknown")
        if category not in category_stats:
            category_stats[category] = {
                "count": 0,
                "avg_contexts": 0,
                "avg_bm25_hits": 0,
                "avg_semantic_hits": 0,
                "avg_graph_hits": 0,
            }

        stats = category_stats[category]
        stats["count"] += 1
        stats["avg_contexts"] += len(detail.get("contexts", []))

        retriever_stats = detail.get("retriever_stats", {})
        stats["avg_bm25_hits"] += retriever_stats.get("bm25_hits", 0)
        stats["avg_semantic_hits"] += retriever_stats.get("semantic_hits", 0)
        stats["avg_graph_hits"] += retriever_stats.get("graph_hits", 0)

    # Average out
    for _category, stats in category_stats.items():
        count = stats["count"]
        if count > 0:
            stats["avg_contexts"] = stats["avg_contexts"] / count  # type: ignore[assignment]
            stats["avg_bm25_hits"] = stats["avg_bm25_hits"] / count  # type: ignore[assignment]
            stats["avg_semantic_hits"] = stats["avg_semantic_hits"] / count  # type: ignore[assignment]
            stats["avg_graph_hits"] = stats["avg_graph_hits"] / count  # type: ignore[assignment]

    results["category_statistics"] = category_stats

    # Save to JSON (ensure output directory exists)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    logger.info(f"\n{'=' * 80}")
    logger.info("EVALUATION COMPLETE")
    logger.info(f"{'=' * 80}")
    logger.info(f"Total questions evaluated: {len(results['questions'])}")

    if ragas_metrics:
        logger.info("\nRAGAS Metrics:")
        for metric, value in ragas_metrics.items():
            logger.info(f"  {metric}: {value:.4f}")

    logger.info("\nCategory Statistics:")
    for category, stats in category_stats.items():
        logger.info(f"\n  {category}:")
        logger.info(f"    Questions: {stats['count']}")
        logger.info(f"    Avg contexts retrieved: {stats['avg_contexts']:.1f}")
        logger.info(f"    Avg BM25 hits: {stats['avg_bm25_hits']:.1f}")
        logger.info(f"    Avg Semantic hits: {stats['avg_semantic_hits']:.1f}")
        logger.info(f"    Avg Graph hits: {stats['avg_graph_hits']:.1f}")

    logger.info(f"\nDetailed results saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Evaluate Patents Analyzer RAG system using RAGAS")
    parser.add_argument(
        "--dataset",
        default="evals/datasets/ragas_dataset_20.json",
        help="Path to RAGAS dataset (default: evals/datasets/ragas_dataset_20.json)",
    )
    parser.add_argument(
        "--top-k", type=int, default=5, help="Number of chunks to retrieve (default: 5)"
    )
    parser.add_argument(
        "--output",
        default="evals/experiments/ragas_results.json",
        help="Output path for results (default: evals/experiments/ragas_results.json)",
    )
    parser.add_argument(
        "--data-dir",
        default="data/processed",
        help="Directory with processed data (default: data/processed)",
    )
    parser.add_argument("--skip-ragas", action="store_true", help="Skip RAGAS metrics calculation")
    parser.add_argument(
        "--ragas-model",
        default=None,
        help="LLM model to use for RAGAS evaluation (e.g., 'gpt-3.5-turbo', 'gpt-4'). If not specified, uses the main LLM from --model or .env",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    setup_logging(level=log_level)

    logger.info("=" * 80)
    logger.info("Patents Analyzer - RAGAS Evaluation")
    logger.info("=" * 80)

    # Load dataset
    logger.info(f"Loading dataset from {args.dataset}...")
    dataset = load_dataset(args.dataset)
    logger.info(
        f"Loaded {len(dataset['test_cases'])} test cases across "
        f"{len(dataset['metadata']['categories'])} categories"
    )

    # Load chunks
    data_dir = Path(args.data_dir)
    chunks_path = data_dir / "patents.json"
    logger.info(f"Loading chunks from {chunks_path}...")
    chunks = load_chunks(str(chunks_path))
    logger.info(f"Loaded {len(chunks)} chunks")

    # Initialize retrievers
    hybrid_retriever = initialize_retrievers(chunks, data_dir)

    # Initialize LLM and answer generator
    logger.info("Initializing LLM...")
    llm_client = LLMClient.from_env()
    answer_generator = AnswerGenerator(
        llm_client=llm_client, max_context_chunks=args.top_k, include_metadata=True
    )
    logger.info(f"✓ Using LLM model: {llm_client.model}")

    # Run evaluation
    results = run_evaluation(
        dataset=dataset,
        hybrid_retriever=hybrid_retriever,
        answer_generator=answer_generator,
        top_k=args.top_k,
    )

    # Calculate RAGAS metrics
    if args.skip_ragas:
        logger.info("\n" + "=" * 80)
        logger.info("Skipping RAGAS metrics calculation (--skip-ragas flag set)")
        logger.info("=" * 80)
        ragas_metrics = {}
    else:
        ragas_metrics = calculate_ragas_metrics(
            results, llm_client=llm_client, ragas_model=args.ragas_model
        )

    # Generate report
    generate_report(results, ragas_metrics, args.output)


if __name__ == "__main__":
    main()
