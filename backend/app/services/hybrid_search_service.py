"""Hybrid Search engine combining BM25 lexical search with FAISS dense vector retrieval via Reciprocal Rank Fusion (RRF).

Security Invariant:
Both BM25 and Dense FAISS searches are partitioned strictly by security level
(PUBLIC, INTERNAL, CONFIDENTIAL). Chunks outside the caller's permitted levels
are NEVER indexed, scored, or ranked.
"""

from collections import Counter
from dataclasses import dataclass
import logging
import math
import re
from typing import Literal, Sequence

from app.services.vector_store_service import ChunkMetadata, SearchResult, get_vector_store


logger = logging.getLogger(__name__)

STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "as", "at", "be", "because", "been", "before", "being", "below",
    "between", "both", "but", "by", "could", "did", "do", "does", "doing", "down",
    "during", "each", "few", "for", "from", "further", "had", "has", "have", "having",
    "he", "her", "here", "hers", "herself", "him", "himself", "his", "how", "i",
    "if", "in", "into", "is", "it", "its", "itself", "me", "more", "most", "my",
    "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other",
    "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "she", "should",
    "so", "some", "such", "than", "that", "the", "their", "theirs", "them", "themselves",
    "then", "there", "these", "they", "this", "those", "through", "to", "too", "under",
    "until", "up", "very", "was", "we", "were", "what", "when", "where", "which",
    "while", "who", "whom", "why", "with", "would", "you", "your", "yours", "yourself",
}


def tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase alphanumeric and symbol terms, preserving numbers and codes."""
    if not text:
        return []
    terms = re.findall(r"[A-Za-z0-9_$.%-]+", text.lower())
    clean_terms: list[str] = []
    for t in terms:
        cleaned = t.strip(".,;:!?\"'()[]{}")
        if not cleaned:
            continue
        if cleaned in STOPWORDS:
            continue
        if len(cleaned) > 1 or cleaned.isdigit():
            clean_terms.append(cleaned)
    return clean_terms


class BM25PartitionIndex:
    """In-memory BM25Okapi index for a single security level partition."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus: list[ChunkMetadata] = []
        self.tokenized_corpus: list[list[str]] = []
        self.doc_lengths: list[int] = []
        self.avgdl: float = 0.0
        self.doc_freqs: dict[str, int] = {}
        self.num_docs: int = 0

    def fit(self, chunks: Sequence[ChunkMetadata]) -> None:
        """Build the index from chunk metadata."""
        self.corpus = list(chunks)
        self.num_docs = len(self.corpus)
        if self.num_docs == 0:
            self.tokenized_corpus = []
            self.doc_lengths = []
            self.avgdl = 0.0
            self.doc_freqs = {}
            return

        self.tokenized_corpus = [tokenize(c.text) for c in self.corpus]
        self.doc_lengths = [len(doc) for doc in self.tokenized_corpus]
        self.avgdl = sum(self.doc_lengths) / max(1, self.num_docs)

        # Calculate document frequency for each term
        self.doc_freqs = {}
        for doc in self.tokenized_corpus:
            unique_terms = set(doc)
            for term in unique_terms:
                self.doc_freqs[term] = self.doc_freqs.get(term, 0) + 1

    def score_query(self, query: str) -> list[float]:
        """Compute BM25 score for every document in this partition."""
        if self.num_docs == 0:
            return []

        q_terms = tokenize(query)
        if not q_terms:
            return [0.0] * self.num_docs

        scores = [0.0] * self.num_docs
        for term in q_terms:
            n_q = self.doc_freqs.get(term, 0)
            if n_q == 0:
                continue
            # Standard smoothed IDF
            idf = math.log((self.num_docs - n_q + 0.5) / (n_q + 0.5) + 1.0)

            for idx, (doc, doc_len) in enumerate(zip(self.tokenized_corpus, self.doc_lengths)):
                # Term frequency in this document
                freq = doc.count(term)
                if freq == 0:
                    continue
                num = freq * (self.k1 + 1.0)
                denom = freq + self.k1 * (1.0 - self.b + self.b * (doc_len / self.avgdl))
                scores[idx] += idf * (num / denom)

        return scores

    def search(self, query: str, top_k: int = 10) -> list[SearchResult]:
        """Return top-k scored chunks in this partition."""
        if self.num_docs == 0:
            return []

        scores = self.score_query(query)
        results = [
            SearchResult(chunk=self.corpus[i], score=scores[i])
            for i in range(self.num_docs)
            if scores[i] > 0.0
        ]
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]


class HybridSearchService:
    """Coordinates partitioned Dense Vector search and partitioned BM25 search.

    Implements Reciprocal Rank Fusion (RRF) to merge ranks across both retrievers:
      RRF_score(d) = sum( 1 / (60 + rank_i(d)) )
    """

    def __init__(self):
        self._bm25_indices: dict[tuple[int, str, tuple[str, ...]], BM25PartitionIndex] = {}

    def clear_cache(self) -> None:
        self._bm25_indices.clear()

    def _get_bm25_index(self, level: str) -> BM25PartitionIndex:
        """Return or lazily update the BM25 index for the specified security level."""
        store = get_vector_store()
        current_chunks = store.metadata_by_level.get(level, [])
        cache_key = (id(store), level, tuple(c.chunk_id for c in current_chunks))

        if cache_key in self._bm25_indices:
            return self._bm25_indices[cache_key]

        index = BM25PartitionIndex()
        index.fit(current_chunks)
        self._bm25_indices[cache_key] = index
        return index

    def search(
        self,
        query: str,
        allowed_security_levels: Sequence[str],
        top_k: int = 5,
        mode: Literal["hybrid", "dense", "bm25"] = "hybrid",
        rrf_k: int = 60,
    ) -> list[SearchResult]:
        """Perform permission-constrained search using Dense, BM25, or Hybrid RRF fusion.

        Guarantees that unauthorized security levels are never searched or scored.
        """
        store = get_vector_store()

        # 1. PURE DENSE SEARCH
        if mode == "dense":
            return store.search(
                query=query,
                allowed_security_levels=allowed_security_levels,
                top_k=top_k,
            )

        # 2. PURE BM25 SEARCH
        if mode == "bm25":
            bm25_candidates: list[SearchResult] = []
            for lvl in allowed_security_levels:
                lvl_upper = lvl.upper()
                index = self._get_bm25_index(lvl_upper)
                bm25_candidates.extend(index.search(query, top_k=top_k))

            bm25_candidates.sort(key=lambda r: r.score, reverse=True)
            # Normalize BM25 scores to [0.0, 1.0] relative to top candidate for consistency
            if bm25_candidates and bm25_candidates[0].score > 0:
                max_s = bm25_candidates[0].score
                for r in bm25_candidates:
                    r.score = round(r.score / max_s, 4)
            return bm25_candidates[:top_k]

        # 3. HYBRID RECIPROCAL RANK FUSION (RRF)
        # Fetch top dense candidates (constrained strictly to allowed levels)
        dense_results = store.search(
            query=query,
            allowed_security_levels=allowed_security_levels,
            top_k=max(top_k * 2, 10),
        )

        # Fetch top BM25 candidates (constrained strictly to allowed levels)
        bm25_results: list[SearchResult] = []
        for lvl in allowed_security_levels:
            lvl_upper = lvl.upper()
            index = self._get_bm25_index(lvl_upper)
            bm25_results.extend(index.search(query, top_k=max(top_k * 2, 10)))
        bm25_results.sort(key=lambda r: r.score, reverse=True)

        if not dense_results and not bm25_results:
            return []

        # Build rank maps
        dense_ranks: dict[str, int] = {
            r.chunk.chunk_id: rank + 1 for rank, r in enumerate(dense_results)
        }
        dense_scores: dict[str, float] = {
            r.chunk.chunk_id: r.score for r in dense_results
        }

        bm25_ranks: dict[str, int] = {
            r.chunk.chunk_id: rank + 1 for rank, r in enumerate(bm25_results)
        }
        bm25_scores: dict[str, float] = {
            r.chunk.chunk_id: r.score for r in bm25_results
        }

        # Collect all candidate chunks
        all_chunks: dict[str, ChunkMetadata] = {}
        for r in dense_results:
            all_chunks[r.chunk.chunk_id] = r.chunk
        for r in bm25_results:
            all_chunks[r.chunk.chunk_id] = r.chunk

        # Theoretical max RRF score for item ranked #1 in both lists
        max_rrf_possible = (1.0 / (rrf_k + 1)) + (1.0 / (rrf_k + 1))

        fused_candidates: list[SearchResult] = []
        for chunk_id, chunk in all_chunks.items():
            dense_s = dense_scores.get(chunk_id, 0.0)
            has_bm25 = chunk_id in bm25_ranks and bm25_scores.get(chunk_id, 0.0) > 0.0

            # Anti-hallucination safeguard: If a chunk has no lexical match and low semantic similarity,
            # do not artificially elevate it via relative rank order.
            if not has_bm25 and dense_s < 0.32:
                final_score = dense_s
            else:
                rrf_score = 0.0
                if chunk_id in dense_ranks:
                    rrf_score += 1.0 / (rrf_k + dense_ranks[chunk_id])
                if chunk_id in bm25_ranks:
                    rrf_score += 1.0 / (rrf_k + bm25_ranks[chunk_id])

                normalized_rrf = min(1.0, rrf_score / max_rrf_possible)
                final_score = max(normalized_rrf, dense_s)

            fused_candidates.append(
                SearchResult(
                    chunk=chunk,
                    score=round(final_score, 4),
                )
            )

        fused_candidates.sort(key=lambda r: r.score, reverse=True)
        return fused_candidates[:top_k]


_hybrid_service_instance: HybridSearchService | None = None


def get_hybrid_search_service() -> HybridSearchService:
    """Return the global HybridSearchService singleton."""
    global _hybrid_service_instance
    if _hybrid_service_instance is None:
        _hybrid_service_instance = HybridSearchService()
    return _hybrid_service_instance


def reset_hybrid_search_service() -> None:
    """Reset the global HybridSearchService instance and clear index caches."""
    global _hybrid_service_instance
    if _hybrid_service_instance is not None:
        _hybrid_service_instance.clear_cache()
    _hybrid_service_instance = None
