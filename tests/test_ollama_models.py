"""
Test different Ollama models for patent analysis.

This script tests multiple models with a sample patent query to help you
choose the best model for your use case.
"""

import sys
import time
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.llm import LLMClient


# Sample patent query
TEST_QUERY = """Based on this patent excerpt:

"The grain-oriented electrical steel sheet contains Si: 2.5-4.0%, with the
remainder being Fe and unavoidable impurities. The steel is subjected to
hot rolling at 1100-1200°C, followed by cold rolling and final annealing
at 1200°C in a hydrogen atmosphere."

Question: What is the silicon content range and why is it important?"""


MODELS_TO_TEST = [
#    "ollama/qwen2.5:7b",
    "ollama/mistral:7b"#,
#    "ollama/llama3.1:8b",
#    "ollama/phi3:3.8b",
#    "ollama/gemma2:9b",
]


def test_model(model_name: str, query: str) -> dict:
    """Test a single model and return performance metrics."""
    print(f"\n{'='*80}")
    print(f"Testing: {model_name}")
    print(f"{'='*80}")

    try:
        # Initialize client
        client = LLMClient(model=model_name, temperature=0.0, max_tokens=300)

        # Measure response time
        start_time = time.time()

        response = client.chat(
            user_message=query,
            system_message="You are a metallurgy expert analyzing patent documents."
        )

        end_time = time.time()
        response_time = end_time - start_time

        # Calculate approximate tokens/sec (rough estimate)
        response_length = len(response.split())
        tokens_per_sec = response_length / response_time if response_time > 0 else 0

        print(f"\n✓ Response received in {response_time:.2f}s")
        print(f"  (~{tokens_per_sec:.1f} tokens/sec)")
        print(f"\nAnswer Preview (first 200 chars):")
        print(f"{response[:200]}...")

        return {
            "model": model_name,
            "success": True,
            "response_time": response_time,
            "tokens_per_sec": tokens_per_sec,
            "response": response,
            "error": None
        }

    except Exception as e:
        print(f"\n✗ Error: {str(e)}")

        if "Connection" in str(e):
            print("  → Make sure Ollama is running: ollama serve")
        elif "not found" in str(e).lower() or "does not exist" in str(e).lower():
            print(f"  → Model not installed. Run: ollama pull {model_name.replace('ollama/', '')}")

        return {
            "model": model_name,
            "success": False,
            "response_time": None,
            "tokens_per_sec": None,
            "response": None,
            "error": str(e)
        }


def main():
    """Test all models and display results."""
    print("="*80)
    print("OLLAMA MODEL COMPARISON FOR PATENT ANALYSIS")
    print("="*80)
    print("\nThis will test several models with a sample patent query.")
    print("Models that aren't installed will be skipped with instructions.")
    print("\nTIP: Install models with: ollama pull <model-name>")
    print("     For example: ollama pull qwen2.5:7b")

    results = []

    for model in MODELS_TO_TEST:
        result = test_model(model, TEST_QUERY)
        results.append(result)
        time.sleep(1)  # Brief pause between tests

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    successful_results = [r for r in results if r["success"]]

    if successful_results:
        print("\nSuccessful Tests:")
        print(f"{'Model':<25} {'Time (s)':<12} {'Speed (tok/s)':<15} {'Status'}")
        print("-"*80)

        for result in successful_results:
            print(f"{result['model']:<25} "
                  f"{result['response_time']:<12.2f} "
                  f"{result['tokens_per_sec']:<15.1f} "
                  f"✓")

        # Find fastest
        fastest = min(successful_results, key=lambda x: x['response_time'])
        print(f"\n⚡ Fastest: {fastest['model']} ({fastest['response_time']:.2f}s)")

    failed_results = [r for r in results if not r["success"]]
    if failed_results:
        print("\n\nFailed/Skipped Models:")
        for result in failed_results:
            print(f"  ✗ {result['model']}")
            if "not found" in str(result['error']).lower():
                model_name = result['model'].replace('ollama/', '')
                print(f"    → Install with: ollama pull {model_name}")

    print("\n" + "="*80)
    print("RECOMMENDATIONS FOR MAC MINI M4 16GB")
    print("="*80)
    print("""
1. Best Overall: qwen2.5:7b
   - Excellent at technical content, good speed, 128K context

2. Most Reliable: mistral:7b
   - Industry standard, consistent quality, well-tested

3. Fastest: phi3:3.8b
   - Lower memory, very fast, good for quick queries

Edit .env to set your preferred model:
  LLM_MODEL=ollama/qwen2.5:7b
    """)

    if successful_results:
        print("\nTo run the full demo with your chosen model:")
        print("  uv run python scripts/demo_hybrid_llm.py")
    else:
        print("\n⚠️  No models were successfully tested.")
        print("   Make sure Ollama is running: ollama serve")
        print("   Then install a model: ollama pull qwen2.5:7b")

    print("="*80 + "\n")


if __name__ == "__main__":
    main()
