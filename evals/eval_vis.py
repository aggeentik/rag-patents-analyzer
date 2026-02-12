"""
Visualization Script for RAGAS Evaluation Results

This script generates visual reports from RAGAS evaluation results.

Usage:
    uv run python scripts/visualize_ragas_results.py tests/ragas_results.json
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import json
import argparse
from typing import Dict, Any, List
from collections import defaultdict


def load_results(results_path: str) -> Dict[str, Any]:
    """Load RAGAS evaluation results."""
    with open(results_path, "r") as f:
        return json.load(f)


def print_summary_report(results: Dict[str, Any]):
    """Print summary report to console."""
    print("\n" + "="*80)
    print("RAGAS EVALUATION SUMMARY REPORT")
    print("="*80)

    # Overall statistics
    total_questions = len(results.get("questions", []))
    timestamp = results.get("evaluation_timestamp", "N/A")

    print(f"\nEvaluation Timestamp: {timestamp}")
    print(f"Total Questions: {total_questions}")

    # RAGAS metrics
    ragas_metrics = results.get("ragas_metrics", {})
    if ragas_metrics:
        print("\n" + "-"*80)
        print("RAGAS METRICS")
        print("-"*80)
        for metric, value in ragas_metrics.items():
            print(f"{metric:30s}: {value:.4f}")

    # Category-wise statistics
    category_stats = results.get("category_statistics", {})
    if category_stats:
        print("\n" + "-"*80)
        print("CATEGORY STATISTICS")
        print("-"*80)

        for category, stats in category_stats.items():
            print(f"\n{category}")
            print(f"  Questions: {stats['count']}")
            print(f"  Avg contexts retrieved: {stats['avg_contexts']:.1f}")
            print(f"  Avg BM25 hits: {stats['avg_bm25_hits']:.1f}")
            print(f"  Avg Semantic hits: {stats['avg_semantic_hits']:.1f}")
            print(f"  Avg Graph hits: {stats['avg_graph_hits']:.1f}")

    # Retriever contribution analysis
    print("\n" + "-"*80)
    print("RETRIEVER CONTRIBUTION ANALYSIS")
    print("-"*80)

    detailed_results = results.get("detailed_results", [])
    retriever_contribution = analyze_retriever_contribution(detailed_results)

    print(f"\nTotal retrievals: {retriever_contribution['total_retrievals']}")
    print(f"BM25 contributions: {retriever_contribution['bm25_contributions']} "
          f"({retriever_contribution['bm25_percentage']:.1f}%)")
    print(f"Semantic contributions: {retriever_contribution['semantic_contributions']} "
          f"({retriever_contribution['semantic_percentage']:.1f}%)")
    print(f"Graph contributions: {retriever_contribution['graph_contributions']} "
          f"({retriever_contribution['graph_percentage']:.1f}%)")


def analyze_retriever_contribution(detailed_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze how much each retriever contributed to results."""
    total_bm25 = 0
    total_semantic = 0
    total_graph = 0
    total_retrievals = 0

    for result in detailed_results:
        stats = result.get("retriever_stats", {})
        bm25 = stats.get("bm25_hits", 0)
        semantic = stats.get("semantic_hits", 0)
        graph = stats.get("graph_hits", 0)

        total_bm25 += bm25
        total_semantic += semantic
        total_graph += graph
        total_retrievals += bm25 + semantic + graph

    return {
        "total_retrievals": total_retrievals,
        "bm25_contributions": total_bm25,
        "semantic_contributions": total_semantic,
        "graph_contributions": total_graph,
        "bm25_percentage": (total_bm25 / total_retrievals * 100) if total_retrievals > 0 else 0,
        "semantic_percentage": (total_semantic / total_retrievals * 100) if total_retrievals > 0 else 0,
        "graph_percentage": (total_graph / total_retrievals * 100) if total_retrievals > 0 else 0
    }


def print_detailed_report(results: Dict[str, Any], max_questions: int = None):
    """Print detailed results for each question."""
    print("\n" + "="*80)
    print("DETAILED QUESTION-BY-QUESTION RESULTS")
    print("="*80)

    detailed_results = results.get("detailed_results", [])
    if max_questions:
        detailed_results = detailed_results[:max_questions]

    for idx, result in enumerate(detailed_results, 1):
        question_id = result.get("id", "Unknown")
        category = result.get("category", "Unknown")
        retrieval_type = result.get("retrieval_type", "Unknown")

        print(f"\n{'='*80}")
        print(f"[{idx}] {question_id} - {category}")
        print(f"Retrieval Type: {retrieval_type}")
        print(f"{'='*80}")

        # Question
        question = result.get("question", "")
        print(f"\nQuestion:\n{question}")

        # Ground truth
        ground_truth = result.get("ground_truth", "")
        print(f"\nGround Truth:\n{ground_truth[:300]}...")

        # Generated answer
        answer = result.get("answer", "")
        print(f"\nGenerated Answer:\n{answer[:300]}...")

        # Retriever stats
        stats = result.get("retriever_stats", {})
        print(f"\nRetriever Stats:")
        print(f"  BM25 hits: {stats.get('bm25_hits', 0)}")
        print(f"  Semantic hits: {stats.get('semantic_hits', 0)}")
        print(f"  Graph hits: {stats.get('graph_hits', 0)}")

        # Retrieved chunks
        chunks = result.get("retrieved_chunks", [])
        print(f"\nRetrieved Chunks ({len(chunks)}):")
        for chunk_idx, chunk in enumerate(chunks, 1):
            print(f"  [{chunk_idx}] Patent: {chunk.get('patent_id', 'Unknown')}, "
                  f"Section: {chunk.get('section', 'Unknown')}, "
                  f"RRF Score: {chunk.get('rrf_score', 0.0):.4f}")


def generate_markdown_report(results: Dict[str, Any], output_path: str):
    """Generate markdown report file."""
    with open(output_path, "w") as f:
        f.write("# RAGAS Evaluation Report\n\n")

        # Metadata
        timestamp = results.get("evaluation_timestamp", "N/A")
        total_questions = len(results.get("questions", []))
        f.write(f"**Evaluation Date:** {timestamp}\n\n")
        f.write(f"**Total Questions:** {total_questions}\n\n")

        # RAGAS Metrics
        ragas_metrics = results.get("ragas_metrics", {})
        if ragas_metrics:
            f.write("## RAGAS Metrics\n\n")
            f.write("| Metric | Score |\n")
            f.write("|--------|-------|\n")
            for metric, value in ragas_metrics.items():
                f.write(f"| {metric} | {value:.4f} |\n")
            f.write("\n")

        # Category Statistics
        category_stats = results.get("category_statistics", {})
        if category_stats:
            f.write("## Category Statistics\n\n")
            f.write("| Category | Questions | Avg Contexts | BM25 | Semantic | Graph |\n")
            f.write("|----------|-----------|--------------|------|----------|-------|\n")
            for category, stats in category_stats.items():
                f.write(f"| {category} | {stats['count']} | "
                       f"{stats['avg_contexts']:.1f} | "
                       f"{stats['avg_bm25_hits']:.1f} | "
                       f"{stats['avg_semantic_hits']:.1f} | "
                       f"{stats['avg_graph_hits']:.1f} |\n")
            f.write("\n")

        # Retriever Contribution
        detailed_results = results.get("detailed_results", [])
        retriever_contribution = analyze_retriever_contribution(detailed_results)

        f.write("## Retriever Contribution Analysis\n\n")
        f.write(f"Total retrievals: {retriever_contribution['total_retrievals']}\n\n")
        f.write("| Retriever | Contributions | Percentage |\n")
        f.write("|-----------|---------------|------------|\n")
        f.write(f"| BM25 | {retriever_contribution['bm25_contributions']} | "
               f"{retriever_contribution['bm25_percentage']:.1f}% |\n")
        f.write(f"| Semantic | {retriever_contribution['semantic_contributions']} | "
               f"{retriever_contribution['semantic_percentage']:.1f}% |\n")
        f.write(f"| Graph | {retriever_contribution['graph_contributions']} | "
               f"{retriever_contribution['graph_percentage']:.1f}% |\n")
        f.write("\n")

        # Detailed results
        f.write("## Question-by-Question Results\n\n")
        for idx, result in enumerate(detailed_results, 1):
            question_id = result.get("id", "Unknown")
            category = result.get("category", "Unknown")
            retrieval_type = result.get("retrieval_type", "Unknown")

            f.write(f"### {question_id}: {category}\n\n")
            f.write(f"**Retrieval Type:** {retrieval_type}\n\n")

            question = result.get("question", "")
            f.write(f"**Question:** {question}\n\n")

            # Retriever stats
            stats = result.get("retriever_stats", {})
            f.write(f"**Retriever Stats:** BM25={stats.get('bm25_hits', 0)}, "
                   f"Semantic={stats.get('semantic_hits', 0)}, "
                   f"Graph={stats.get('graph_hits', 0)}\n\n")

            # Ground truth (truncated)
            ground_truth = result.get("ground_truth", "")
            f.write(f"**Ground Truth:**\n```\n{ground_truth[:500]}...\n```\n\n")

            # Generated answer (truncated)
            answer = result.get("answer", "")
            f.write(f"**Generated Answer:**\n```\n{answer[:500]}...\n```\n\n")

            f.write("---\n\n")

    print(f"\nMarkdown report saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Visualize RAGAS evaluation results"
    )
    parser.add_argument(
        "results_file",
        help="Path to RAGAS results JSON file"
    )
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Print detailed question-by-question results"
    )
    parser.add_argument(
        "--max-questions",
        type=int,
        help="Maximum number of questions to show in detailed report"
    )
    parser.add_argument(
        "--markdown",
        help="Generate markdown report at specified path"
    )

    args = parser.parse_args()

    # Load results
    results = load_results(args.results_file)

    # Print summary report
    print_summary_report(results)

    # Print detailed report if requested
    if args.detailed:
        print_detailed_report(results, max_questions=args.max_questions)

    # Generate markdown report if requested
    if args.markdown:
        generate_markdown_report(results, args.markdown)


if __name__ == "__main__":
    main()
