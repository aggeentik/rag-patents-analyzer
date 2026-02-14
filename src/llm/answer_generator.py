"""Answer generation using retrieved chunks and LLM."""

import logging

from src.llm.llm_client import LLMClient

logger = logging.getLogger(__name__)


class AnswerGenerator:
    """
    Generate answers to questions using retrieved patent chunks and LLM.

    Workflow:
    1. Takes retrieved chunks from hybrid retriever
    2. Constructs context from top chunks
    3. Builds prompt with context and question
    4. Uses LLM to generate comprehensive answer
    """

    def __init__(
        self, llm_client: LLMClient, max_context_chunks: int = 5, include_metadata: bool = True
    ):
        """
        Initialize answer generator.

        Args:
            llm_client: LLM client instance
            max_context_chunks: Maximum number of chunks to include in context
            include_metadata: Whether to include chunk metadata in context
        """
        self.llm_client = llm_client
        self.max_context_chunks = max_context_chunks
        self.include_metadata = include_metadata

    def generate_answer(
        self,
        question: str,
        retrieved_chunks: list[dict],
        temperature: float = 0.0,
        stream: bool = False,
    ) -> dict:
        """
        Generate answer to question using retrieved chunks.

        Args:
            question: User's question
            retrieved_chunks: Chunks from hybrid retriever (sorted by relevance)
            temperature: LLM temperature
            stream: Whether to stream the response

        Returns:
            Dict with:
                - answer: Generated answer
                - sources: List of chunks used as context
                - metadata: Additional information (model, chunk_count, etc.)
        """
        # Select top chunks for context
        context_chunks = retrieved_chunks[: self.max_context_chunks]

        # Build context from chunks
        context = self._build_context(context_chunks)

        # Build prompt
        prompt = self._build_prompt(question, context)

        # System message for the LLM
        system_message = self._get_system_message()

        # Generate answer
        logger.info("Generating answer with %d context chunks...", len(context_chunks))

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt},
        ]

        answer = self.llm_client.generate(messages, temperature=temperature, stream=stream)

        return {
            "answer": answer,
            "sources": [
                {
                    "chunk_id": chunk["chunk_id"],
                    "patent_id": chunk.get("patent_id", "unknown"),
                    "section": chunk.get("metadata", {}).get("section", "unknown"),
                    "page": chunk.get("metadata", {}).get("page", "unknown"),
                    "rrf_score": chunk.get("rrf_score", 0.0),
                    "preview": chunk["content"][:200] + "..."
                    if len(chunk["content"]) > 200
                    else chunk["content"],
                }
                for chunk in context_chunks
            ],
            "metadata": {
                "model": self.llm_client.model,
                "chunk_count": len(context_chunks),
                "total_retrieved": len(retrieved_chunks),
                "temperature": temperature,
            },
        }

    def stream_answer(
        self,
        question: str,
        retrieved_chunks: list[dict],
        temperature: float = 0.0,
    ) -> tuple:
        """
        Prepare a streaming answer generation.

        Returns:
            (stream_generator, metadata) where stream_generator yields str
            chunks suitable for st.write_stream(), and metadata is a dict
            with sources and model info.
        """
        context_chunks = retrieved_chunks[: self.max_context_chunks]
        context = self._build_context(context_chunks)
        prompt = self._build_prompt(question, context)
        system_message = self._get_system_message()

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt},
        ]

        stream = self.llm_client.generate_stream(messages, temperature=temperature)

        metadata = {
            "answer": "",  # placeholder, filled by caller after streaming
            "sources": [
                {
                    "chunk_id": chunk["chunk_id"],
                    "patent_id": chunk.get("patent_id", "unknown"),
                    "section": chunk.get("metadata", {}).get("section", "unknown"),
                    "page": chunk.get("metadata", {}).get("page", "unknown"),
                    "rrf_score": chunk.get("rrf_score", 0.0),
                    "preview": chunk["content"][:200] + "..."
                    if len(chunk["content"]) > 200
                    else chunk["content"],
                }
                for chunk in context_chunks
            ],
            "metadata": {
                "model": self.llm_client.model,
                "chunk_count": len(context_chunks),
                "total_retrieved": len(retrieved_chunks),
                "temperature": temperature,
            },
        }

        return stream, metadata

    def _build_context(self, chunks: list[dict]) -> str:
        """Build context string from chunks with signal-quality labels."""
        context_parts = []

        for i, chunk in enumerate(chunks, 1):
            # Build chunk header with metadata
            header = f"[Source {i}]"

            # Label high-signal graph connections so the LLM can prioritise them
            signal_label = self._get_signal_label(chunk)
            if signal_label:
                header += f" {signal_label}"

            if self.include_metadata:
                metadata_parts = []
                if "patent_id" in chunk:
                    metadata_parts.append(f"Patent: {chunk['patent_id']}")

                chunk_metadata = chunk.get("metadata", {})
                if "section" in chunk_metadata:
                    metadata_parts.append(f"Section: {chunk_metadata['section']}")
                if "page" in chunk_metadata:
                    metadata_parts.append(f"Page: {chunk_metadata['page']}")

                if metadata_parts:
                    header += f" ({', '.join(metadata_parts)})"

            # Add chunk content
            context_parts.append(f"{header}\n{chunk['content']}\n")

        return "\n".join(context_parts)

    @staticmethod
    def _get_signal_label(chunk: dict) -> str:
        """Return a signal-quality label based on retrieval scores.

        High graph_rank (low number = high rank) or high rrf_score indicate
        chunks that came from precise entity-graph traversal rather than
        broad keyword matching — these tend to carry the specific technical
        data needed for faithful answers.
        """
        graph_rank = chunk.get("graph_rank", 0)
        rrf_score = chunk.get("rrf_score", 0.0)

        # Top-5 graph hit OR top-3 overall RRF score → high-signal
        if (graph_rank > 0 and graph_rank <= 5) or rrf_score >= 0.03:
            return "[HIGH-SIGNAL GRAPH CONNECTION]"
        return ""

    def _build_prompt(self, question: str, context: str) -> str:
        """Build prompt with Chain-of-Note evaluation logic."""
        prompt = f"""PATENT EXCERPTS:
{context}

QUESTION:
{question}

INSTRUCTIONS — follow these two steps in order:

STEP 1 — EVALUATE (do this mentally, do NOT write it out):
For each Source above, decide:
  • "Technical Signal" — contains specific numbers, compositions, process parameters, or quantitative results relevant to the question.
  • "General Background" — contains definitions, broad context, or information unrelated to the question.
Only use "Technical Signal" sources to build your answer. Ignore "General Background" sources entirely.

STEP 2 — ANSWER:
Write your answer following this structure:
  1. **Direct conclusion first** — state the key technical finding in 1–2 sentences with citations.
  2. **Supporting data** — present the specific values, compositions, or parameters that support the conclusion. Cite every claim with [Source X].
  3. **Gaps** — if the excerpts lack data to fully answer, state what is missing.

RULES:
- Use ONLY information explicitly stated in the excerpts. Do not infer or add outside knowledge.
- Cite with [Source 1], [Source 2], etc. NEVER mention section names, page numbers, or patent IDs.
- Prefer sources marked [HIGH-SIGNAL GRAPH CONNECTION] — they contain entity-linked technical data.
- If no source contains relevant technical data for the question, say so directly.

ANSWER:"""

        return prompt

    def _get_system_message(self) -> str:
        """Get system message for LLM."""
        return """You are a Senior Patent Metallurgist with deep expertise in steel manufacturing, alloy design, and thermomechanical processing. You think like an engineer, not a summariser.

PRIORITY HIERARCHY — follow this strictly:
1. HIGH-SIGNAL DATA (use as primary evidence):
   - Numerical values: chemical compositions (e.g. Si 0.05–0.10 wt%), temperatures (e.g. 1150 °C), mechanical properties (e.g. yield stress ≥ 350 MPa)
   - Specific process parameters: rolling speeds, annealing times, cooling rates
   - Quantitative results from tables, formulas, and examples
   - Sources marked [HIGH-SIGNAL GRAPH CONNECTION] — these contain precise entity-linked data

2. BACKGROUND NOISE (ignore unless directly asked):
   - Generic definitions ("Steel is an alloy of iron and carbon…")
   - Broad industry context or prior-art summaries
   - Vague statements without specific values or conditions

CITATION RULES (mandatory):
- For every sentence you write, you must first identify the [Source X] you are using. If you cannot find a specific [Source X] for a claim, do not include that claim in your answer.
- Use ONLY [Source 1], [Source 2], etc. NEVER write section names, page numbers, or patent IDs in your text
- If a claim draws from multiple sources, list them: [Source 1, Source 3]

FAITHFULNESS:
- State ONLY what is explicitly written in the provided excerpts
- Do NOT infer, extrapolate, or add knowledge from outside the excerpts
- If a specific value (e.g., an exact percentage or temperature) is not found in the provided sources, you must explicitly say "data not available in sources" rather than providing a general range or estimate
- If the excerpts lack sufficient data, say so clearly"""

    def generate_summary(self, chunks: list[dict]) -> str:
        """
        Generate a summary of the retrieved patent chunks.

        Args:
            chunks: Chunks to summarize

        Returns:
            Summary text
        """
        context = self._build_context(chunks[: self.max_context_chunks])

        prompt = f"""Summarize the key technical information from these patent excerpts:

{context}

Provide a concise summary highlighting:
1. Main technical innovations or methods
2. Key materials, compositions, or elements mentioned
3. Important process parameters or conditions
4. Notable results or achievements

IMPORTANT: Cite information using [Source X] format only. Do not mention section names or page numbers directly.

SUMMARY:"""

        messages = [
            {"role": "system", "content": self._get_system_message()},
            {"role": "user", "content": prompt},
        ]

        return self.llm_client.generate(messages, temperature=0.0)

    def generate_comparison(
        self,
        question: str,
        chunks_a: list[dict],
        chunks_b: list[dict],
        label_a: str = "Set A",
        label_b: str = "Set B",
    ) -> str:
        """
        Compare two sets of chunks (e.g., different patents or approaches).

        Args:
            question: Comparison question
            chunks_a: First set of chunks
            chunks_b: Second set of chunks
            label_a: Label for first set
            label_b: Label for second set

        Returns:
            Comparison answer
        """
        context_a = self._build_context(chunks_a[: self.max_context_chunks])
        context_b = self._build_context(chunks_b[: self.max_context_chunks])

        prompt = f"""Compare the following two sets of patent excerpts and answer the question.

{label_a}:
{context_a}

{label_b}:
{context_b}

QUESTION:
{question}

Provide a detailed comparison highlighting:
1. Similarities between the approaches
2. Key differences in methods, materials, or results
3. Relative advantages or disadvantages
4. Technical innovations unique to each

IMPORTANT: Cite information using [Source X] format only. Do not mention section names or page numbers directly.

COMPARISON:"""

        messages = [
            {"role": "system", "content": self._get_system_message()},
            {"role": "user", "content": prompt},
        ]

        return self.llm_client.generate(messages, temperature=0.0)
