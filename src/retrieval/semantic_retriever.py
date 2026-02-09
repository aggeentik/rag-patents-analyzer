"""FAISS-based semantic retrieval."""

import json
import logging

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class SemanticRetriever:
    """FAISS-based semantic retrieval."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        logger.info("Loading sentence transformer model: %s", model_name)
        self.model = SentenceTransformer(model_name)
        logger.info("Sentence transformer model loaded successfully")
        self.index: faiss.IndexFlatIP | None = None
        self.chunk_ids: list[str] = []
        self.chunks_by_id: dict[str, dict] = {}

    def build_index(self, chunks: list[dict]):
        """Build FAISS index from chunks."""
        logger.info("Building FAISS index for %d chunks...", len(chunks))
        self.chunks_by_id = {c["chunk_id"]: c for c in chunks}
        self.chunk_ids = [c["chunk_id"] for c in chunks]

        # Generate embeddings
        logger.debug("Encoding chunks with sentence transformers...")
        texts = [c["content"] for c in chunks]
        embeddings = self.model.encode(texts, show_progress_bar=True)

        # Normalize for cosine similarity
        logger.debug("Normalizing embeddings...")
        embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)

        # Build FAISS index
        logger.debug("Building FAISS index...")
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dimension)  # Inner product = cosine after normalization
        self.index.add(embeddings.astype(np.float32))
        logger.info(
            "FAISS index built with %d vectors (%d dimensions)",
            self.index.ntotal,
            dimension,
        )

    def search(self, query: str, top_k: int = 10) -> list[dict]:
        """Search and return chunks with semantic scores."""
        assert self.index is not None, "Index not built. Call build_index() first."

        # Encode query
        query_embedding = self.model.encode([query])
        query_embedding = query_embedding / np.linalg.norm(query_embedding)

        # Search
        scores, indices = self.index.search(query_embedding.astype(np.float32), top_k)

        results = []
        for i, (score, idx) in enumerate(zip(scores[0], indices[0])):
            chunk_id = self.chunk_ids[idx]
            chunk = self.chunks_by_id[chunk_id].copy()
            chunk["semantic_score"] = float(score)
            chunk["semantic_rank"] = i + 1
            results.append(chunk)

        return results

    def save(self, index_path: str, mapping_path: str):
        """Save FAISS index and mapping."""
        faiss.write_index(self.index, index_path)
        with open(mapping_path, "w") as f:
            json.dump(self.chunk_ids, f)
        logger.info("FAISS index saved to %s", index_path)
        logger.info("Chunk mapping saved to %s", mapping_path)

    @classmethod
    def load(
        cls,
        index_path: str,
        mapping_path: str,
        chunks: list[dict],
        model_name: str = "all-MiniLM-L6-v2",
    ) -> "SemanticRetriever":
        """Load index from disk."""
        retriever = cls(model_name)
        retriever.chunks_by_id = {c["chunk_id"]: c for c in chunks}

        logger.info("Loading FAISS index from %s", index_path)
        retriever.index = faiss.read_index(index_path)
        logger.info("Loading chunk mapping from %s", mapping_path)
        with open(mapping_path, "r") as f:
            retriever.chunk_ids = json.load(f)

        logger.info(
            "Semantic retriever loaded successfully with %d chunks", len(retriever.chunk_ids)
        )
        return retriever
