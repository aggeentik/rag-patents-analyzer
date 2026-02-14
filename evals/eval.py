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

import argparse
import json
import logging
from datetime import datetime
from typing import Any

from src.knowledge_graph.store import KnowledgeGraphStore
from src.llm import AnswerGenerator, LLMClient
from src.logging_config import setup_logging
from src.retrieval import (
    BM25Retriever,
    GraphRetriever,
    HybridRetriever,
    SemanticRetriever,
)

logger = logging.getLogger(__name__)


def load_dataset(dataset_path: str) -> dict[str, Any]:
    """Load dataset from JSON file, supporting both custom and RAGAS-native formats.

    Custom format: {"metadata": {...}, "test_cases": [{"id", "question", "ground_truth", ...}]}
    RAGAS-native format: [{"user_input", "reference", "reference_contexts", "synthesizer_name"}]

    Both are normalized into the custom format structure for downstream processing.
    """
    with open(dataset_path, "r") as f:
        raw = json.load(f)

    # Already in custom format
    if isinstance(raw, dict) and "test_cases" in raw:
        return raw

    # RAGAS-native format (list of records from TestsetGenerator)
    if isinstance(raw, list) and raw and "user_input" in raw[0]:
        categories = sorted({r.get("synthesizer_name", "generated") for r in raw})
        test_cases = []
        for idx, record in enumerate(raw, 1):
            test_cases.append(
                {
                    "id": f"G{idx}",
                    "question": record["user_input"],
                    "ground_truth": record.get("reference", ""),
                    "category": record.get("synthesizer_name", "generated"),
                    "retrieval_type": "hybrid",
                    "reference_contexts": record.get("reference_contexts", []),
                }
            )
        return {
            "metadata": {
                "description": "RAGAS-generated synthetic dataset",
                "total_questions": len(test_cases),
                "categories": categories,
                "format": "ragas_native",
            },
            "test_cases": test_cases,
        }

    raise ValueError(
        f"Unrecognized dataset format in {dataset_path}. "
        "Expected either custom format (dict with 'test_cases') or "
        "RAGAS-native format (list of records with 'user_input')."
    )


def load_chunks(chunks_path: str) -> list[dict[str, Any]]:
    """Load processed chunks."""
    with open(chunks_path, "r") as f:
        data = json.load(f)
        return data["chunks"]


def initialize_retrievers(chunks: list[dict[str, Any]], data_dir: Path) -> HybridRetriever:
    """Initialize BM25, Semantic, and Graph retrievers and combine them."""
    logger.info("Loading retrievers...")

    bm25 = BM25Retriever.load(str(data_dir / "bm25_index.pkl"), chunks)
    semantic = SemanticRetriever.load(
        str(data_dir / "faiss.index"), str(data_dir / "chunk_ids.json"), chunks
    )

    kg_store = KnowledgeGraphStore(str(data_dir / "knowledge_graph.db"))
    kg_store.connect()
    graph = GraphRetriever.load("", chunks, kg_store, max_hops=2, score_decay=0.5)

    hybrid = HybridRetriever(
        bm25_retriever=bm25,
        semantic_retriever=semantic,
        graph_retriever=graph,
        weights={"bm25": 1.0, "semantic": 1.0, "graph": 0.5},
        rrf_k=60,
    )
    logger.info(f"Hybrid retriever initialized with {len(chunks)} chunks")
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

        logger.info(f"[{idx}/{total}] {question_id} ({category}): {question}")

        try:
            retrieved_chunks = hybrid_retriever.search(question, top_k=top_k)
            context_list = [chunk["content"] for chunk in retrieved_chunks]
            stats = hybrid_retriever.get_retriever_stats(retrieved_chunks)
            logger.debug(
                f"Retriever stats: BM25={stats['bm25_hits']}, "
                f"Semantic={stats['semantic_hits']}, Graph={stats['graph_hits']}"
            )

            result = answer_generator.generate_answer(
                question=question,
                retrieved_chunks=retrieved_chunks,
                temperature=0.0,
                stream=False,
            )

            answer = result["answer"]
            logger.debug(f"Answer: {answer[:200]}...")

            # Store results
            results["questions"].append(question)
            results["ground_truths"].append(ground_truth)
            results["contexts"].append(context_list)
            results["answers"].append(answer)

            # Detailed results for analysis
            detailed = {
                "id": question_id,
                "category": category,
                "retrieval_type": test_case.get("retrieval_type", "hybrid"),
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


def _extract_numeric_values(source: Any) -> dict[str, float]:
    """Extract string->float pairs from a dict-like object, handling nested dicts.

    Uses float() conversion instead of isinstance to handle numpy scalar types
    (e.g. numpy.float64) that RAGAS may return.
    """
    result = {}
    items = source.items() if hasattr(source, "items") else []
    for key, value in items:
        try:
            result[key] = float(value)
        except (TypeError, ValueError):
            if isinstance(value, dict):
                for nested_val in value.values():
                    try:
                        result[key] = float(nested_val)
                        break
                    except (TypeError, ValueError):
                        continue
    return result


def _build_ragas_llm(
    ragas_model: str | None, llm_client: LLMClient | None, ChatLiteLLM: type
) -> Any:
    """Build the LangChain LLM instance for RAGAS evaluation."""
    if ragas_model:
        logger.info(f"Using dedicated LLM for RAGAS evaluation: {ragas_model}")
        if ragas_model.startswith("gpt-") and not ragas_model.startswith("gpt-4o"):
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(model=ragas_model)
        return ChatLiteLLM(model=ragas_model)

    if llm_client:
        logger.info(f"Using main LLM for RAGAS evaluation: {llm_client.model}")
        return ChatLiteLLM(model=llm_client.model)

    from langchain_openai import ChatOpenAI

    logger.info("Using OpenAI GPT-3.5-turbo for RAGAS metrics")
    return ChatOpenAI(model="gpt-3.5-turbo")


def _parse_evaluation_results(evaluation_results: Any) -> dict[str, float]:
    """
    Parse RAGAS evaluation results into a flat {metric_name: score} dict.

    Handles multiple RAGAS result formats:
    1. dict-like objects (EvaluationResult with __iter__)
    2. Objects with a .scores DataFrame or list attribute
    3. Objects with named metric attributes
    """
    logger.debug(f"Parsing {type(evaluation_results).__name__}: {repr(evaluation_results)[:200]}")

    # Strategy 1: _repr_dict (RAGAS 0.4.x stores aggregated means here)
    if hasattr(evaluation_results, "_repr_dict"):
        metrics = _extract_numeric_values(evaluation_results._repr_dict)
        if metrics:
            return metrics

    # Strategy 2: dict() conversion (older RAGAS versions)
    try:
        metrics = _extract_numeric_values(dict(evaluation_results))
        if metrics:
            return metrics
    except (TypeError, ValueError):
        pass

    # Strategy 3: .scores attribute (list of per-row dicts)
    if hasattr(evaluation_results, "scores"):
        scores = evaluation_results.scores
        if isinstance(scores, (list, tuple)):
            metric_values: dict[str, list[float]] = {}
            for entry in scores:
                if isinstance(entry, dict):
                    for key, value in entry.items():
                        try:
                            metric_values.setdefault(key, []).append(float(value))
                        except (TypeError, ValueError):
                            continue
            return {k: sum(v) / len(v) for k, v in metric_values.items() if v}
        if hasattr(scores, "mean"):
            mean_scores = scores.mean()
            if hasattr(mean_scores, "to_dict"):
                return {k: float(v) for k, v in mean_scores.to_dict().items()}

    return {}


def calculate_ragas_metrics(
    results: dict[str, Any], llm_client: LLMClient | None = None, ragas_model: str | None = None
) -> dict[str, float]:
    """
    Calculate RAGAS metrics using the configured LLM.

    Requires: pip install ragas
    """
    try:
        import warnings

        # Suppress RAGAS deprecation warnings for legacy metrics API
        warnings.filterwarnings("ignore", category=DeprecationWarning, message=".*ragas.metrics.*")

        from datasets import Dataset  # type: ignore[attr-defined]
        from ragas import evaluate
        from ragas.metrics import (
            answer_relevancy,
            context_precision,
            context_recall,
            faithfulness,
        )

        try:
            from langchain_litellm import ChatLiteLLM
        except ImportError:
            from langchain_community.chat_models import ChatLiteLLM

        try:
            from langchain_huggingface import HuggingFaceEmbeddings
        except ImportError:
            from langchain_community.embeddings import HuggingFaceEmbeddings

    except ImportError as e:
        logger.warning(f"RAGAS not installed: {e}. Install with: uv sync --group evals")
        return {}

    logger.info("Calculating RAGAS metrics...")

    try:
        llm = _build_ragas_llm(ragas_model, llm_client, ChatLiteLLM)
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

        dataset = Dataset.from_dict(
            {
                "question": results["questions"],
                "answer": results["answers"],
                "contexts": results["contexts"],
                "ground_truth": results["ground_truths"],
            }
        )

        logger.info(
            "Computing faithfulness, answer_relevancy, context_precision, context_recall..."
        )
        evaluation_results = evaluate(
            dataset,
            metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
            llm=llm,
            embeddings=embeddings,
        )

        metrics_dict = _parse_evaluation_results(evaluation_results)
        if metrics_dict:
            logger.info(f"RAGAS metrics: {metrics_dict}")
        else:
            logger.warning(
                f"Could not extract metrics from {type(evaluation_results).__name__}. "
                f"Available attrs: {[a for a in dir(evaluation_results) if not a.startswith('_')]}"
            )
        return metrics_dict

    except Exception as e:
        logger.error(f"RAGAS metrics calculation failed: {e}")
        logger.warning(
            "If using Ollama, ensure the model is running (ollama list). "
            "If using Bedrock, check AWS credentials. "
            "Results are saved without RAGAS metrics."
        )
        return {}


def generate_report(results: dict[str, Any], ragas_metrics: dict[str, float], output_path: str):
    """Generate comprehensive evaluation report."""
    results["ragas_metrics"] = ragas_metrics
    results["evaluation_timestamp"] = datetime.now().isoformat()

    # Calculate category-wise statistics
    category_stats: dict[str, dict[str, Any]] = {}
    avg_fields = ["avg_contexts", "avg_bm25_hits", "avg_semantic_hits", "avg_graph_hits"]
    retriever_field_map = {
        "avg_bm25_hits": "bm25_hits",
        "avg_semantic_hits": "semantic_hits",
        "avg_graph_hits": "graph_hits",
    }

    for detail in results["detailed_results"]:
        category = detail.get("category", "Unknown")
        if category not in category_stats:
            category_stats[category] = {"count": 0, **dict.fromkeys(avg_fields, 0)}

        stats = category_stats[category]
        stats["count"] += 1
        stats["avg_contexts"] += len(detail.get("contexts", []))

        retriever_stats = detail.get("retriever_stats", {})
        for avg_field, retriever_field in retriever_field_map.items():
            stats[avg_field] += retriever_stats.get(retriever_field, 0)

    for stats in category_stats.values():
        count = stats["count"]
        if count > 0:
            for field in avg_fields:
                stats[field] = stats[field] / count

    results["category_statistics"] = category_stats

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    # Log summary
    logger.info(f"Evaluation complete: {len(results['questions'])} questions evaluated")

    if ragas_metrics:
        metrics_str = ", ".join(f"{m}: {v:.4f}" for m, v in ragas_metrics.items())
        logger.info(f"RAGAS Metrics: {metrics_str}")

    for category, stats in category_stats.items():
        logger.info(
            f"  {category}: {stats['count']} questions, "
            f"avg contexts={stats['avg_contexts']:.1f}, "
            f"BM25={stats['avg_bm25_hits']:.1f}, "
            f"Semantic={stats['avg_semantic_hits']:.1f}, "
            f"Graph={stats['avg_graph_hits']:.1f}"
        )

    logger.info(f"Results saved to: {output_path}")


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

    setup_logging(level=logging.DEBUG if args.verbose else logging.INFO)
    logger.info("Patents Analyzer - RAGAS Evaluation")

    # Load dataset and chunks
    dataset = load_dataset(args.dataset)
    logger.info(
        f"Loaded {len(dataset['test_cases'])} test cases across "
        f"{len(dataset['metadata']['categories'])} categories"
    )

    data_dir = Path(args.data_dir)
    chunks = load_chunks(str(data_dir / "patents.json"))
    logger.info(f"Loaded {len(chunks)} chunks")

    # Initialize retrieval and generation
    hybrid_retriever = initialize_retrievers(chunks, data_dir)

    llm_client = LLMClient.from_env()
    answer_generator = AnswerGenerator(
        llm_client=llm_client, max_context_chunks=args.top_k, include_metadata=True
    )
    logger.info(f"Using LLM model: {llm_client.model}")

    # Run evaluation
    results = run_evaluation(
        dataset=dataset,
        hybrid_retriever=hybrid_retriever,
        answer_generator=answer_generator,
        top_k=args.top_k,
    )

    # Calculate RAGAS metrics
    if args.skip_ragas:
        logger.info("Skipping RAGAS metrics (--skip-ragas)")
        ragas_metrics = {}
    else:
        ragas_metrics = calculate_ragas_metrics(
            results, llm_client=llm_client, ragas_model=args.ragas_model
        )

    generate_report(results, ragas_metrics, args.output)


if __name__ == "__main__":
    main()
