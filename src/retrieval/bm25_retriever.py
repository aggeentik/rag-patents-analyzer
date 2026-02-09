"""BM25 sparse retrieval."""

import logging
import pickle

import nltk
from nltk.tokenize import word_tokenize
from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)


class BM25Retriever:
    """BM25 sparse retrieval."""

    def __init__(self):
        self.bm25 = None
        self.chunks = []
        self.tokenized_corpus = []

        # Ensure nltk data is available
        try:
            nltk.data.find("tokenizers/punkt")
        except LookupError:
            logger.info("Downloading NLTK punkt tokenizer...")
            nltk.download("punkt")
            nltk.download("punkt_tab")

    def build_index(self, chunks: list[dict]):
        """Build BM25 index from chunks."""
        logger.info("Building BM25 index for %d chunks...", len(chunks))
        self.chunks = chunks
        self.tokenized_corpus = [word_tokenize(chunk["content"].lower()) for chunk in chunks]
        self.bm25 = BM25Okapi(self.tokenized_corpus)
        logger.info("BM25 index built successfully")

    def search(self, query: str, top_k: int = 10) -> list[dict]:
        """Search and return chunks with BM25 scores."""
        tokenized_query = word_tokenize(query.lower())
        scores = self.bm25.get_scores(tokenized_query)

        # Get top-k indices
        top_indices = scores.argsort()[-top_k:][::-1]

        results: list[dict] = []
        for idx in top_indices:
            chunk = self.chunks[idx].copy()
            chunk["bm25_score"] = float(scores[idx])
            chunk["bm25_rank"] = len(results) + 1
            results.append(chunk)

        return results

    def save(self, path: str):
        """Save index to disk."""
        # Note: Using pickle for BM25 index storage (trusted data source)
        with open(path, "wb") as f:
            pickle.dump(
                {
                    "bm25": self.bm25,
                    "tokenized_corpus": self.tokenized_corpus,
                },
                f,
            )
        logger.info("BM25 index saved to %s", path)

    @classmethod
    def load(cls, path: str, chunks: list[dict]) -> "BM25Retriever":
        """Load index from disk."""
        retriever = cls()
        retriever.chunks = chunks

        with open(path, "rb") as f:
            data = pickle.load(f)
            retriever.bm25 = data["bm25"]
            retriever.tokenized_corpus = data["tokenized_corpus"]

        return retriever
