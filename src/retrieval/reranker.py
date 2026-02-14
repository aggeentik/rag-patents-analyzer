"""Cross-encoder reranker for post-fusion relevance scoring."""

import logging
import os

from sentence_transformers import CrossEncoder

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "BAAI/bge-reranker-v2-m3"


def reranker_from_env() -> "CrossEncoderReranker | None":
    """Create a reranker if enabled via environment variables.

    Reads:
        RERANKER_ENABLED: "true" to enable (default: "false")
        RERANKER_MODEL: HuggingFace model ID (default: BAAI/bge-reranker-v2-m3)

    Returns:
        CrossEncoderReranker instance if enabled, None otherwise.
    """
    enabled = os.getenv("RERANKER_ENABLED", "false").lower() in ("true", "1", "yes")
    if not enabled:
        logger.info("Reranker disabled (set RERANKER_ENABLED=true to enable)")
        return None

    model = os.getenv("RERANKER_MODEL", DEFAULT_MODEL)
    return CrossEncoderReranker(model_name=model)


class CrossEncoderReranker:
    """Reranks retrieval results using a cross-encoder model.

    Cross-encoders jointly encode (query, document) pairs and produce a single
    relevance score, giving much higher accuracy than bi-encoder similarity
    at the cost of speed — which is fine when applied to a small candidate pool
    (e.g. top-20 RRF results).
    """

    def __init__(self, model_name: str = DEFAULT_MODEL, batch_size: int = 32):
        """
        Args:
            model_name: HuggingFace cross-encoder model identifier.
            batch_size: Batch size for scoring pairs.
        """
        self.model_name = model_name
        self.batch_size = batch_size
        logger.info("Loading cross-encoder model: %s", model_name)
        self.model = CrossEncoder(model_name)
        logger.info("Cross-encoder model loaded successfully")

    def score(self, query: str, chunks: list[dict]) -> list[float]:
        """Score each chunk against the query.

        Args:
            query: The search query.
            chunks: List of chunk dicts (must contain a "content" key).

        Returns:
            List of relevance scores, one per chunk (higher = more relevant).
        """
        if not chunks:
            return []

        pairs = [(query, chunk["content"]) for chunk in chunks]
        scores = self.model.predict(pairs, batch_size=self.batch_size).tolist()

        logger.debug(
            "Reranked %d chunks (score range: %.4f – %.4f)",
            len(scores),
            min(scores),
            max(scores),
        )
        return scores
