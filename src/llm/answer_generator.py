"""Answer generation using retrieved chunks and LLM."""

import logging
from typing import Optional

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
        self,
        llm_client: LLMClient,
        max_context_chunks: int = 5,
        include_metadata: bool = True
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
        stream: bool = False
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
        context_chunks = retrieved_chunks[:self.max_context_chunks]

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
            {"role": "user", "content": prompt}
        ]

        answer = self.llm_client.generate(
            messages,
            temperature=temperature,
            stream=stream
        )

        return {
            "answer": answer,
            "sources": [
                {
                    "chunk_id": chunk["chunk_id"],
                    "patent_id": chunk.get("patent_id", "unknown"),
                    "section": chunk.get("metadata", {}).get("section", "unknown"),
                    "page": chunk.get("metadata", {}).get("page", "unknown"),
                    "rrf_score": chunk.get("rrf_score", 0.0),
                    "preview": chunk["content"][:200] + "..." if len(chunk["content"]) > 200 else chunk["content"]
                }
                for chunk in context_chunks
            ],
            "metadata": {
                "model": self.llm_client.model,
                "chunk_count": len(context_chunks),
                "total_retrieved": len(retrieved_chunks),
                "temperature": temperature
            }
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
        context_chunks = retrieved_chunks[:self.max_context_chunks]
        context = self._build_context(context_chunks)
        prompt = self._build_prompt(question, context)
        system_message = self._get_system_message()

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt},
        ]

        stream = self.llm_client.generate_stream(
            messages, temperature=temperature
        )

        metadata = {
            "answer": "",  # placeholder, filled by caller after streaming
            "sources": [
                {
                    "chunk_id": chunk["chunk_id"],
                    "patent_id": chunk.get("patent_id", "unknown"),
                    "section": chunk.get("metadata", {}).get("section", "unknown"),
                    "page": chunk.get("metadata", {}).get("page", "unknown"),
                    "rrf_score": chunk.get("rrf_score", 0.0),
                    "preview": chunk["content"][:200] + "..." if len(chunk["content"]) > 200 else chunk["content"],
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
        """Build context string from chunks."""
        context_parts = []

        for i, chunk in enumerate(chunks, 1):
            # Build chunk header with metadata
            header = f"[Source {i}]"
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

    def _build_prompt(self, question: str, context: str) -> str:
        """Build prompt for LLM."""
        prompt = f"""Based on the following patent excerpts, answer the question below.

PATENT EXCERPTS:
{context}

QUESTION:
{question}

INSTRUCTIONS:
1. Provide a comprehensive answer based ONLY on the information in the patent excerpts
2. Include specific technical details, numerical values, and formulas when available
3. Reference the source numbers [Source X] when citing specific information
4. If the excerpts don't contain enough information to answer completely, state what's missing
5. Organize your answer clearly with sections if answering multiple aspects
6. Use technical language appropriate for patent analysis

ANSWER:"""

        return prompt

    def _get_system_message(self) -> str:
        """Get system message for LLM."""
        return """You are a patent analysis assistant specializing in steel manufacturing and metallurgy.

Your role is to:
- Analyze patent documents and extract relevant technical information
- Provide accurate, detailed answers based on patent content
- Cite sources and reference specific patent sections
- Explain complex metallurgical processes and compositions
- Identify key innovations, methods, and technical specifications

Always base your answers on the provided patent excerpts. If information is not available in the excerpts, clearly state this limitation."""

    def generate_summary(self, chunks: list[dict]) -> str:
        """
        Generate a summary of the retrieved patent chunks.

        Args:
            chunks: Chunks to summarize

        Returns:
            Summary text
        """
        context = self._build_context(chunks[:self.max_context_chunks])

        prompt = f"""Summarize the key technical information from these patent excerpts:

{context}

Provide a concise summary highlighting:
1. Main technical innovations or methods
2. Key materials, compositions, or elements mentioned
3. Important process parameters or conditions
4. Notable results or achievements

SUMMARY:"""

        messages = [
            {"role": "system", "content": self._get_system_message()},
            {"role": "user", "content": prompt}
        ]

        return self.llm_client.generate(messages, temperature=0.0)

    def generate_comparison(
        self,
        question: str,
        chunks_a: list[dict],
        chunks_b: list[dict],
        label_a: str = "Set A",
        label_b: str = "Set B"
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
        context_a = self._build_context(chunks_a[:self.max_context_chunks])
        context_b = self._build_context(chunks_b[:self.max_context_chunks])

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

COMPARISON:"""

        messages = [
            {"role": "system", "content": self._get_system_message()},
            {"role": "user", "content": prompt}
        ]

        return self.llm_client.generate(messages, temperature=0.0)
