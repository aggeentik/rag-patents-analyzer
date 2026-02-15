# Changelog

All notable changes to the Patents Analyzer project are documented in this file.

---

## [0.2.0] - 2026-02-15

### PR #9: Evaluation Framework, Knowledge Graph Expansion, and Reranker

**29 commits** | 42 files changed | +19,272 / -2,733 lines

---

### Added

#### RAGAS Evaluation Framework
- **`evals/eval.py`** - Full RAGAS evaluation script: loads test datasets, runs hybrid retrieval + LLM answer generation per question, computes RAGAS metrics (faithfulness, answer relevancy, context precision, context recall), and saves timestamped results
- **`evals/eval_vis.py`** - Results visualization script: generates console summaries, per-question analysis, retriever statistics, and formatted Markdown evaluation reports
- **`evals/generate_dataset.py`** - Synthetic QA dataset generator using RAGAS `TestsetGenerator`: groups chunks by patent/section, generates questions per-document to prevent cross-document hallucinations, outputs JSON and CSV
- **`evals/README.md`** - Evaluation framework documentation with quick start, dataset format, and experiment workflow
- **`docs/4. EVALS.md`** - Comprehensive evaluation guide covering RAGAS metrics, running evaluations, interpreting results, best practices, and troubleshooting
- **`evals/datasets/generated_testset.json`** - Synthetic QA dataset generated from patent chunks
- **`evals/datasets/ragas_dataset_20.json`** - Curated 20-question dataset across 5 categories (keyword precision, tabular reasoning, semantic, KG, multi-document)
- 5 evaluation experiment runs with full results and reports in `evals/experiments/`
- Makefile targets: `evaluate`, `report`, `generate-dataset`, `generate-dataset-large`

#### Cross-Encoder Reranker
- **`src/retrieval/reranker.py`** - Cross-encoder reranker using HuggingFace models (default: `BAAI/bge-reranker-v2-m3`): jointly encodes (query, document) pairs for more accurate relevance scoring after RRF fusion
- `CrossEncoderReranker` class with configurable model and batch size
- `reranker_from_env()` factory: reads `RERANKER_ENABLED` and `RERANKER_MODEL` from environment
- Integrated into `HybridRetriever` as an optional post-fusion step via `Reranker` protocol
- Reranker status displayed in Streamlit UI sidebar

#### Knowledge Graph Expansion
- 7 new entity types: `inventor`, `assignee`, `patent_reference`, `application`, `material`, `problem`, `solution`, `patent_doc_reference`
- 5 new relationship types: `CITES`, `ADDRESSES_PROBLEM`, `USED_FOR`, `INVENTED_BY`, `ASSIGNEE_OF`
- `PatentMeta` Pydantic model for structured patent-level metadata extraction (inventors, assignees, cited patents, applications, materials, problems, solutions)
- `APPLICATIONS` vocabulary (8 entries): electric vehicles, transformers, electric motors, generators, inductors, sensors, energy storage, power electronics
- `MATERIALS` vocabulary (8 entries): grain-oriented electrical steel, non-oriented electrical steel, silicon steel, high-strength steel, stainless steel, carbon steel, rare earth metals, etc.
- 9 additional chemical elements: La, Ce, Nd, Y, Ca, Bi, Sn, Sb, Mg (total: 27)
- New entity extraction methods in `EntityExtractor` for applications, materials, patent metadata
- New relationship inference methods in `KnowledgeGraphBuilder` for CITES, USED_FOR, INVENTED_BY, ASSIGNEE_OF, ADDRESSES_PROBLEM
- Expanded `KnowledgeGraphStore` with queries for new entity/relationship types
- Enhanced `KnowledgeGraphTraversal` with semantic similarity-based KB retrieval

#### Dependencies
- `ragas==0.4.3` - RAG evaluation framework
- `datasets==4.5.0` - Dataset handling for RAGAS
- LangChain ecosystem: `langchain-core`, `langchain-community`, `langchain-openai`, `langchain-huggingface`, `langchain-litellm`, `langchain-text-splitters`
- LangGraph ecosystem: `langgraph`, `langgraph-checkpoint`, `langgraph-prebuilt`, `langgraph-sdk`
- Supporting libraries: `llama-parse`, `dataclasses-json`, `marshmallow`, `orjson`, etc.
- All eval dependencies in optional `[evals]` group

### Changed

#### Hybrid Retriever
- `HybridRetriever` now accepts an optional `reranker` parameter implementing the `Reranker` protocol
- "Wide Retrieval, Narrow Generation" strategy: fetch large candidate pool via RRF, then rerank with cross-encoder before returning final `top_k`
- RRF fusion logic refactored to use `_FUSION_FIELDS` set for cleaner field management
- Default graph weight updated from 0.5 to 1.2 in `.env.example`

#### Answer Generator
- Optimized prompt engineering for more concise, relevant answers
- Improved source citation formatting

#### Streamlit UI
- Simplified to single `top_k` slider (removed separate retriever sliders)
- Added reranker status indicator in sidebar
- Minor UI refinements

#### Entity Extractor
- Now supports hybrid extraction: regex (default) + optional LLM via Instructor
- Added extraction patterns for applications, materials, and patent metadata

#### Data Ingestion
- `scripts/retrieval.py` and `scripts/retrieval_generation.py` moved to `src/`
- Pipeline script updated to use new entity extraction capabilities

#### Configuration
- `.env.example` updated with `RERANKER_ENABLED`, `RERANKER_MODEL`, and `RETRIEVER_*_WEIGHT` settings

### Removed

- `docs/IMPLEMENTATION_PLAN.md` (2,248 lines) - superseded by completed implementation and updated documentation
- `docs/SOLUTION_OVERVIEW.md` - consolidated into other documentation
- Old test files and datasets removed during project restructure
- `scripts/` directory removed (scripts moved to `src/`)

### Documentation

- **`CLAUDE.md`** - Major update: 16 entity types, 17 relationship types, reranker module, Azure AI provider, evaluation framework, corrected file paths and cross-references
- **`docs/1. DATA_INGESTION_PIPELINE.md`** - Updated to Docling (replaced unstructured references), corrected patents.json format, updated entity/relationship counts, removed non-existent script references
- **`docs/2. RETRIEVAL_GENERATION.md`** - Added reranker documentation, Azure AI provider, marked all phases complete
- **`docs/3. E2E_PIPELINE.md`** - Added reranker to pipeline diagram, Azure AI to providers, updated RRF examples with new graph weight
- **`docs/4. EVALS.md`** - New comprehensive evaluation guide
- **`evals/README.md`** - New evaluation framework quick start
- **`README.md`** - Added reranker and Azure AI to tech stack

---

## [0.1.0] - 2026-02-07

### Initial Release

- Complete RAG pipeline: PDF ingestion, chunking, entity extraction, knowledge graph, hybrid retrieval (BM25 + Semantic + Graph), RRF fusion, LLM answer generation
- Streamlit web UI with PDF viewer, citation linking, and streaming answers
- Support for Ollama, AWS Bedrock, and OpenAI via LiteLLM
- 9 entity types, 12 relationship types, 18 chemical elements
- Docling-based PDF parsing with section detection and table stitching
- Code quality tooling: ruff, mypy, bandit, deptry, pip-audit
