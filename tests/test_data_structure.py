"""Test script to verify data structure is correct."""

import json
from pathlib import Path

project_root = Path(__file__).parent.parent
data_path = project_root / "data" / "processed" / "patents.json"

print("="*80)
print("DATA STRUCTURE VERIFICATION")
print("="*80)

# Load data
print(f"\nLoading: {data_path}")
with open(data_path) as f:
    data = json.load(f)

print(f"\n✓ File loaded successfully")
print(f"  Top-level keys: {list(data.keys())}")
print(f"  Total patents: {data['total_patents']}")
print(f"  Total chunks: {data['total_chunks']}")

# Flatten chunks
all_chunks = []
for patent in data["patents"]:
    all_chunks.extend(patent["chunks"])

print(f"\n✓ Chunks extracted")
print(f"  Flattened chunks: {len(all_chunks)}")

# Show sample chunk
if all_chunks:
    sample = all_chunks[0]
    print(f"\n✓ Sample chunk structure:")
    print(f"  chunk_id: {sample['chunk_id']}")
    print(f"  patent_id: {sample['patent_id']}")
    print(f"  metadata: {sample.get('metadata', {})}")
    print(f"  content length: {len(sample['content'])} chars")
    print(f"  entities: {len(sample.get('entities', []))} entities")
    print(f"  references: {sample.get('references', {})}")

print("\n" + "="*80)
print("✓ DATA STRUCTURE VERIFICATION PASSED")
print("="*80)
print("\nReady to run:")
print("  uv run python scripts/demo_hybrid_llm.py")
print("="*80 + "\n")
