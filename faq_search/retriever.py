#!/usr/bin/env python3
"""
retriever.py -- Runtime semantic retrieval engine for the SU Disability Supplement FAQ.

Features:
- Fast vector similarity search using sentence embeddings and L2-normalized dot products.
- Multi-variant scoring: aggregates the maximum similarity across canonical questions
  and phrasing variants for each FAQ record.
- Strict confidence routing:
    - >= 0.82 with margin >= 0.10: Single direct match.
    - 0.50 - 0.81: Multi-candidate clarification chips (top 2-3).
    - < 0.50: Out-of-scope / fallback prompt.
- Dual interface:
    - Direct knowledge retrieval: retrieve(query, top_k=3)
    - DCR candidate ranker: rank_candidates(query, candidates, last_context=None)
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

log = logging.getLogger(__name__)

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
DEFAULT_RECORDS_PATH = DATA_DIR / "faq_qa_records.json"
DEFAULT_VECTORS_PATH = DATA_DIR / "faq_embeddings.npy"
DEFAULT_META_PATH = DATA_DIR / "faq_embeddings_meta.json"


@dataclass
class SearchResult:
    id: str
    canonical_question: str
    matched_text: str
    matched_kind: str  # 'canonical' or 'variant'
    score: float
    answer_text: str
    citation: str
    topic: str
    availability: str | None


class FAQRetriever:
    def __init__(
        self,
        records_path: Path = DEFAULT_RECORDS_PATH,
        vectors_path: Path = DEFAULT_VECTORS_PATH,
        meta_path: Path = DEFAULT_META_PATH,
    ):
        self.records_path = Path(records_path)
        self.vectors_path = Path(vectors_path)
        self.meta_path = Path(meta_path)

        self._records_by_id: dict[str, dict] = {}
        self._vectors: np.ndarray | None = None
        self._meta: dict[str, Any] = {}
        self._model = None
        self._model_name: str = ""

        self._load_data()

    def _load_data(self) -> None:
        if not self.records_path.exists():
            raise FileNotFoundError(f"FAQ records not found at {self.records_path}")
        if not self.vectors_path.exists():
            raise FileNotFoundError(f"FAQ vectors not found at {self.vectors_path}. Run embed_faq_data.py first.")
        if not self.meta_path.exists():
            raise FileNotFoundError(f"FAQ vector metadata not found at {self.meta_path}")

        records_data = json.loads(self.records_path.read_text(encoding="utf-8"))
        self._records_by_id = {r["id"]: r for r in records_data.get("records", [])}

        self._vectors = np.load(self.vectors_path)
        self._meta = json.loads(self.meta_path.read_text(encoding="utf-8"))
        self._model_name = self._meta.get("model", "Qwen/Qwen3-Embedding-0.6B")

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            log.info("Loading sentence transformer model '%s'...", self._model_name)
            self._model = SentenceTransformer(self._model_name)
        return self._model

    def retrieve(self, query: str, top_k: int = 3) -> list[SearchResult]:
        """Perform semantic search for a query and return top_k unique FAQ records."""
        query = (query or "").strip()
        if not query or self._vectors is None:
            return []

        # Encode query and normalize
        query_vec = self.model.encode(
            [query],
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )[0].astype("float32")

        # Cosine similarity == dot product since rows and query are L2 normalized
        scores = np.dot(self._vectors, query_vec)

        # Aggregate max score per record id
        rows = self._meta.get("rows", [])
        best_by_id: dict[str, tuple[float, dict]] = {}

        for score, row in zip(scores, rows):
            rid = row["id"]
            float_score = float(score)
            if rid not in best_by_id or float_score > best_by_id[rid][0]:
                best_by_id[rid] = (float_score, row)

        # Sort descending
        sorted_records = sorted(best_by_id.items(), key=lambda item: item[1][0], reverse=True)

        results: list[SearchResult] = []
        for rid, (score, row_meta) in sorted_records[:top_k]:
            rec = self._records_by_id.get(rid, {})
            results.append(
                SearchResult(
                    id=rid,
                    canonical_question=rec.get("canonical_question", ""),
                    matched_text=row_meta.get("text", ""),
                    matched_kind=row_meta.get("kind", "canonical"),
                    score=score,
                    answer_text=rec.get("answer_text", ""),
                    citation=rec.get("citation", ""),
                    topic=rec.get("topic", ""),
                    availability=rec.get("availability"),
                )
            )
        return results

    def rank_candidates(
        self,
        query: str,
        candidates: list[dict],
        last_context: str | None = None,
        single_threshold: float = 0.82,
        min_threshold: float = 0.50,
        margin_threshold: float = 0.10,
    ) -> tuple[str, list[dict]]:
        """
        Rank DCR simulation candidate choices to match the openchat interface:
        returns (decision, rows) where decision is 'single_match' | 'clarify_match' | 'no_match',
        and rows contains [{'candidate_key': ..., 'score': ..., 'reason': ...}].
        """
        if not candidates or not query.strip():
            return "no_match", []

        # If user refers to prior context (e.g. "what about that?", "and then?"), combine gently
        effective_query = query
        if last_context and len(query.split()) <= 4 and any(w in query.lower() for w in ("that", "it", "this", "then", "more")):
            effective_query = f"{last_context} - {query}"

        # Retrieve top matches across all FAQ records
        top_matches = self.retrieve(effective_query, top_k=5)
        if not top_matches:
            return "no_match", []

        # Map candidate keys/questions to best match
        # Candidate questions can be matched by canonical question text or numeric id
        ranked_rows: list[dict] = []
        for match in top_matches:
            for cand in candidates:
                cand_q = cand.get("question", "").strip().lower()
                cand_key = cand.get("candidate_key", "")
                # Check for direct match with canonical question or match id
                if (
                    cand_q == match.canonical_question.lower()
                    or match.canonical_question.lower() in cand_q
                    or cand_q in match.canonical_question.lower()
                    or f"faq_{cand.get('value', '')}" == match.id.lower()
                    or f"faq_{int(cand.get('value', '0')) if str(cand.get('value')).isdigit() else 0:02d}" == match.id.lower()
                ):
                    ranked_rows.append({
                        "candidate_key": cand_key,
                        "score": round(match.score, 4),
                        "reason": f"Matched '{match.matched_text}' (score: {match.score:.2f})",
                        "question": cand.get("question", match.canonical_question),
                        "faq_id": match.id,
                    })
                    break

        if not ranked_rows:
            return "no_match", []

        top_score = ranked_rows[0]["score"]
        second_score = ranked_rows[1]["score"] if len(ranked_rows) > 1 else 0.0

        if top_score >= single_threshold and (top_score - second_score >= margin_threshold):
            return "single_match", ranked_rows[:1]
        elif top_score >= min_threshold:
            return "clarify_match", ranked_rows[:3]
        else:
            return "no_match", []


_DEFAULT_RETRIEVER: FAQRetriever | None = None


def get_retriever() -> FAQRetriever:
    global _DEFAULT_RETRIEVER
    if _DEFAULT_RETRIEVER is None:
        _DEFAULT_RETRIEVER = FAQRetriever()
    return _DEFAULT_RETRIEVER
