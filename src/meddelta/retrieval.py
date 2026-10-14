from __future__ import annotations

import math
import heapq
from typing import Any

import numpy as np

from meddelta.config import (
    BIOMED_MODEL_NAME,
    CONCEPT_DECAY_DAYS,
    CONTEXT_WEIGHT,
    DSW_WEIGHTS,
    RECENCY_HALF_LIFE_DAYS,
    RECENCY_WEIGHT,
    SEMANTIC_WEIGHT,
    VOLATILITY_CLASS,
)
from meddelta.eligibility import is_comparable
from meddelta.embed import cosine_similarity_scores, encode_query
from meddelta.models import Observation, RankedCandidate, RetrievalResult


# ── Module-level caches for external models ───────────────────────
_biobert_model = None
_bm25_index = None
_bm25_corpus_ids: list[str] = []
_bm25_corpus_texts: list[str] = []


def retrieve_baseline(
    current: Observation, 
    query_text: str, 
    corpus: list[Observation], 
    method: str, 
    embeddings: tuple[np.ndarray, list[str], dict[str, int]] | None = None, 
    query_embeddings: dict[str, np.ndarray] | None = None,
    top_k: int = 3
) -> RetrievalResult:
    """Retrieves baseline records using the specified strategy."""
    if method == "metadata_only":
        return metadata_only(current, corpus, top_k)
    elif method == "semantic_only":
        return semantic_only(current, query_text, corpus, embeddings, query_embeddings, top_k)
    elif method == "bm25":
        return bm25_retrieval(current, query_text, corpus, top_k)
    elif method == "biobert_semantic":
        return biobert_semantic(current, query_text, corpus, top_k)
    elif method == "hybrid":
        return hybrid(current, query_text, corpus, embeddings, query_embeddings, top_k)
    elif method == "hybrid_csad":
        return hybrid_csad(current, query_text, corpus, embeddings, query_embeddings, top_k)
    elif method == "hybrid_dsw":
        return hybrid_dsw(current, query_text, corpus, embeddings, query_embeddings, top_k)
    elif method == "hybrid_csad_dsw":
        return hybrid_csad_dsw(current, query_text, corpus, embeddings, query_embeddings, top_k)
    elif method == "no_eligibility":
        return no_eligibility(current, query_text, corpus, embeddings, query_embeddings, top_k)
    elif method == "no_context":
        return no_context(current, query_text, corpus, embeddings, query_embeddings, top_k)
    else:
        raise ValueError(f"Unknown retrieval method: {method}")


def metadata_only(current: Observation, corpus: list[Observation], top_k: int) -> RetrievalResult:
    candidates = [
        obs for obs in corpus 
        if obs.patient_id == current.patient_id 
        and obs.concept_code == current.concept_code 
        and obs.observed_at < current.observed_at
    ]
    
    candidates.sort(key=lambda x: x.observed_at, reverse=True)
    
    if not candidates:
        return RetrievalResult(method="metadata_only", query_id="", ranked_candidates=[], status="NO_COMPARABLE_BASELINE")
        
    ranked = []
    for i, obs in enumerate(candidates[:top_k]):
        ranked.append(RankedCandidate(
            record_id=obs.record_id,
            observation=obs,
            rank=i + 1,
            score=1.0 - (i * 0.01),
            score_components={}
        ))
        
    return RetrievalResult(method="metadata_only", query_id="", ranked_candidates=ranked, status="OK")


def semantic_only(
    current: Observation, 
    query_text: str, 
    corpus: list[Observation], 
    embeddings: tuple[np.ndarray, list[str], dict[str, int]] | None, 
    query_embeddings: dict[str, np.ndarray] | None,
    top_k: int
) -> RetrievalResult:
    candidates = [
        obs for obs in corpus 
        if obs.patient_id == current.patient_id 
        and obs.observed_at < current.observed_at
    ]
    
    if not candidates or embeddings is None:
        return RetrievalResult(method="semantic_only", query_id="", ranked_candidates=[], status="NO_COMPARABLE_BASELINE")
        
    emb_matrix, emb_ids, id_to_idx = embeddings
    if query_embeddings is not None and query_text in query_embeddings:
        query_emb = query_embeddings[query_text]
    else:
        query_emb = encode_query(query_text)
    
    candidate_scores = []
    for obs in candidates:
        if obs.record_id in id_to_idx:
            idx = id_to_idx[obs.record_id]
            score = cosine_similarity_scores(query_emb, emb_matrix[idx:idx+1])[0]
            candidate_scores.append((score, obs))
            
    top_candidates = heapq.nlargest(top_k, candidate_scores, key=lambda x: (x[0], x[1].observed_at.timestamp(), -hash(x[1].record_id)))
    
    if not candidate_scores:
        return RetrievalResult(method="semantic_only", query_id="", ranked_candidates=[], status="NO_COMPARABLE_BASELINE")
        
    ranked = []
    for i, (score, obs) in enumerate(top_candidates):
        ranked.append(RankedCandidate(
            record_id=obs.record_id,
            observation=obs,
            rank=i + 1,
            score=float(score),
            score_components={"semantic": float(score)}
        ))
        
    return RetrievalResult(method="semantic_only", query_id="", ranked_candidates=ranked, status="OK")


def _hybrid_core(
    current: Observation, 
    query_text: str, 
    corpus: list[Observation], 
    embeddings: tuple[np.ndarray, list[str], dict[str, int]] | None, 
    query_embeddings: dict[str, np.ndarray] | None,
    top_k: int,
    method_name: str,
    use_csad: bool = False,
    use_dsw: bool = False,
) -> RetrievalResult:
    if embeddings is None:
        return RetrievalResult(method=method_name, query_id="", ranked_candidates=[], status="NO_COMPARABLE_BASELINE")
        
    emb_matrix, emb_ids, id_to_idx = embeddings
    if query_embeddings is not None and query_text in query_embeddings:
        query_emb = query_embeddings[query_text]
    else:
        query_emb = encode_query(query_text)
    
    eligible = []
    for obs in corpus:
        if obs.patient_id != current.patient_id:
            continue
        eligibility = is_comparable(current, obs)
        if eligibility.is_eligible and obs.record_id in id_to_idx:
            eligible.append((obs, eligibility))
            
    if not eligible:
        return RetrievalResult(method=method_name, query_id="", ranked_candidates=[], status="NO_COMPARABLE_BASELINE")
        
    # Determine decay parameters
    if use_csad:
        decay_days = CONCEPT_DECAY_DAYS.get(current.concept_code, float(RECENCY_HALF_LIFE_DAYS))
    else:
        decay_days = float(RECENCY_HALF_LIFE_DAYS)

    # Determine weight parameters
    if use_dsw:
        volatility = VOLATILITY_CLASS.get(current.concept_code, "medium")
        w_s, w_r, w_x = DSW_WEIGHTS[volatility]
    else:
        w_s, w_r, w_x = SEMANTIC_WEIGHT, RECENCY_WEIGHT, CONTEXT_WEIGHT

    # Get candidate indices for matrix slicing
    candidate_indices = [id_to_idx[obs.record_id] for obs, _ in eligible]
    candidate_matrix = emb_matrix[candidate_indices]

    # Vectorized semantic scoring for candidate records only
    all_semantic_scores = cosine_similarity_scores(query_emb, candidate_matrix)

    scored_candidates = []
    for i, (obs, eligibility) in enumerate(eligible):
        semantic_score = float(all_semantic_scores[i])
        
        elapsed_days = (current.observed_at - obs.observed_at).total_seconds() / 86400.0
        recency_score = math.exp(-elapsed_days / decay_days)
        
        ctx_match = current.condition_context == obs.condition_context
        site_match = current.anatomical_site == obs.anatomical_site
        
        if ctx_match and site_match:
            context_score = 1.0
        elif ctx_match or site_match:
            context_score = 0.5
        else:
            context_score = 0.0
            
        hybrid_score = (w_s * semantic_score) + (w_r * recency_score) + (w_x * context_score)
        
        scored_candidates.append({
            "obs": obs,
            "eligibility": eligibility,
            "semantic_score": semantic_score,
            "recency_score": recency_score,
            "context_score": context_score,
            "hybrid_score": hybrid_score
        })
        
    top_candidates = heapq.nlargest(top_k, scored_candidates, key=lambda x: (x["hybrid_score"], x["obs"].observed_at.timestamp(), -hash(x["obs"].record_id)))
    
    ranked = []
    for i, item in enumerate(top_candidates):
        obs = item["obs"]
        ranked.append(RankedCandidate(
            record_id=obs.record_id,
            observation=obs,
            rank=i + 1,
            score=item["hybrid_score"],
            score_components={
                "semantic": item["semantic_score"],
                "recency": item["recency_score"],
                "context": item["context_score"]
            },
            eligibility=item["eligibility"]
        ))
        
    return RetrievalResult(method=method_name, query_id="", ranked_candidates=ranked, status="OK")


def hybrid(
    current: Observation, 
    query_text: str, 
    corpus: list[Observation], 
    embeddings: tuple[np.ndarray, list[str], dict[str, int]] | None, 
    query_embeddings: dict[str, np.ndarray] | None,
    top_k: int
) -> RetrievalResult:
    return _hybrid_core(
        current, query_text, corpus, embeddings, query_embeddings, top_k,
        method_name="hybrid",
        use_csad=False,
        use_dsw=False,
    )


def hybrid_csad(
    current: Observation, 
    query_text: str, 
    corpus: list[Observation], 
    embeddings: tuple[np.ndarray, list[str], dict[str, int]] | None, 
    query_embeddings: dict[str, np.ndarray] | None,
    top_k: int
) -> RetrievalResult:
    return _hybrid_core(
        current, query_text, corpus, embeddings, query_embeddings, top_k,
        method_name="hybrid_csad",
        use_csad=True,
        use_dsw=False,
    )


def hybrid_dsw(
    current: Observation, 
    query_text: str, 
    corpus: list[Observation], 
    embeddings: tuple[np.ndarray, list[str], dict[str, int]] | None, 
    query_embeddings: dict[str, np.ndarray] | None,
    top_k: int
) -> RetrievalResult:
    return _hybrid_core(
        current, query_text, corpus, embeddings, query_embeddings, top_k,
        method_name="hybrid_dsw",
        use_csad=False,
        use_dsw=True,
    )


def hybrid_csad_dsw(
    current: Observation, 
    query_text: str, 
    corpus: list[Observation], 
    embeddings: tuple[np.ndarray, list[str], dict[str, int]] | None, 
    query_embeddings: dict[str, np.ndarray] | None,
    top_k: int
) -> RetrievalResult:
    return _hybrid_core(
        current, query_text, corpus, embeddings, query_embeddings, top_k,
        method_name="hybrid_csad_dsw",
        use_csad=True,
        use_dsw=True,
    )


# ═══════════════════════════════════════════════════════════════════
#  EXTERNAL BASELINES
# ═══════════════════════════════════════════════════════════════════


def _get_bm25_index(corpus: list[Observation]):
    """Build or return cached BM25 index."""
    global _bm25_index, _bm25_corpus_ids, _bm25_corpus_texts
    corpus_ids = [obs.record_id for obs in corpus]
    if _bm25_index is not None and _bm25_corpus_ids == corpus_ids:
        return _bm25_index
    from rank_bm25 import BM25Okapi
    tokenized = [obs.note_text.lower().split() for obs in corpus]
    _bm25_index = BM25Okapi(tokenized)
    _bm25_corpus_ids = corpus_ids
    _bm25_corpus_texts = [obs.note_text for obs in corpus]
    return _bm25_index


def bm25_retrieval(
    current: Observation,
    query_text: str,
    corpus: list[Observation],
    top_k: int,
) -> RetrievalResult:
    """BM25 sparse retrieval — external baseline (no eligibility gate)."""
    candidates = [
        obs for obs in corpus
        if obs.patient_id == current.patient_id
        and obs.observed_at < current.observed_at
    ]
    if not candidates:
        return RetrievalResult(method="bm25", query_id="", ranked_candidates=[], status="NO_COMPARABLE_BASELINE")

    bm25 = _get_bm25_index(corpus)
    query_tokens = query_text.lower().split()
    # Get scores for ALL corpus docs, then filter to candidates
    all_scores = bm25.get_scores(query_tokens)
    id_to_corpus_idx = {obs.record_id: i for i, obs in enumerate(corpus)}

    candidate_scores = []
    for obs in candidates:
        idx = id_to_corpus_idx.get(obs.record_id)
        if idx is not None:
            candidate_scores.append((float(all_scores[idx]), obs))

    candidate_scores.sort(key=lambda x: x[0], reverse=True)

    ranked = []
    for i, (score, obs) in enumerate(candidate_scores[:top_k]):
        ranked.append(RankedCandidate(
            record_id=obs.record_id,
            observation=obs,
            rank=i + 1,
            score=score,
            score_components={"bm25": score},
        ))

    return RetrievalResult(method="bm25", query_id="", ranked_candidates=ranked, status="OK")


def _get_biobert_model():
    """Lazy-load BioBERT model."""
    global _biobert_model
    if _biobert_model is None:
        from sentence_transformers import SentenceTransformer
        _biobert_model = SentenceTransformer(BIOMED_MODEL_NAME)
    return _biobert_model


def biobert_semantic(
    current: Observation,
    query_text: str,
    corpus: list[Observation],
    top_k: int,
) -> RetrievalResult:
    """BioBERT dense retrieval — external baseline (no eligibility gate)."""
    candidates = [
        obs for obs in corpus
        if obs.patient_id == current.patient_id
        and obs.observed_at < current.observed_at
    ]
    if not candidates:
        return RetrievalResult(method="biobert_semantic", query_id="", ranked_candidates=[], status="NO_COMPARABLE_BASELINE")

    model = _get_biobert_model()
    query_emb = model.encode(query_text, normalize_embeddings=True)
    candidate_texts = [obs.note_text for obs in candidates]
    candidate_embs = model.encode(candidate_texts, normalize_embeddings=True)

    scores = candidate_embs @ query_emb
    scored = list(zip(scores.tolist(), candidates))
    scored.sort(key=lambda x: x[0], reverse=True)

    ranked = []
    for i, (score, obs) in enumerate(scored[:top_k]):
        ranked.append(RankedCandidate(
            record_id=obs.record_id,
            observation=obs,
            rank=i + 1,
            score=float(score),
            score_components={"biobert_cosine": float(score)},
        ))

    return RetrievalResult(method="biobert_semantic", query_id="", ranked_candidates=ranked, status="OK")


# ═══════════════════════════════════════════════════════════════════
#  COMPONENT ABLATION VARIANTS
# ═══════════════════════════════════════════════════════════════════


def no_eligibility(
    current: Observation,
    query_text: str,
    corpus: list[Observation],
    embeddings: tuple[np.ndarray, list[str], dict[str, int]] | None,
    query_embeddings: dict[str, np.ndarray] | None,
    top_k: int,
) -> RetrievalResult:
    """M6 minus eligibility gate — shows importance of the gate."""
    if embeddings is None:
        return RetrievalResult(method="no_eligibility", query_id="", ranked_candidates=[], status="NO_COMPARABLE_BASELINE")

    emb_matrix, emb_ids, id_to_idx = embeddings
    if query_embeddings is not None and query_text in query_embeddings:
        query_emb = query_embeddings[query_text]
    else:
        query_emb = encode_query(query_text)

    # Filter by patient + historical ONLY (no eligibility gate)
    candidates = [
        obs for obs in corpus
        if obs.patient_id == current.patient_id
        and obs.observed_at < current.observed_at
        and obs.record_id in id_to_idx
    ]
    if not candidates:
        return RetrievalResult(method="no_eligibility", query_id="", ranked_candidates=[], status="NO_COMPARABLE_BASELINE")

    # Use CSAD + DSW scoring (same as M6) but WITHOUT the eligibility filter
    decay_days = CONCEPT_DECAY_DAYS.get(current.concept_code, float(RECENCY_HALF_LIFE_DAYS))
    volatility = VOLATILITY_CLASS.get(current.concept_code, "medium")
    w_s, w_r, w_x = DSW_WEIGHTS[volatility]

    # Get candidate indices for matrix slicing
    candidate_indices = [id_to_idx[obs.record_id] for obs in candidates]
    candidate_matrix = emb_matrix[candidate_indices]

    all_semantic_scores = cosine_similarity_scores(query_emb, candidate_matrix)

    scored_candidates = []
    for i, obs in enumerate(candidates):
        semantic_score = float(all_semantic_scores[i])
        elapsed_days = (current.observed_at - obs.observed_at).total_seconds() / 86400.0
        recency_score = math.exp(-elapsed_days / decay_days)
        ctx_match = current.condition_context == obs.condition_context
        site_match = current.anatomical_site == obs.anatomical_site
        context_score = 1.0 if (ctx_match and site_match) else (0.5 if (ctx_match or site_match) else 0.0)
        hybrid_score = (w_s * semantic_score) + (w_r * recency_score) + (w_x * context_score)
        scored_candidates.append({"obs": obs, "score": hybrid_score, "sem": semantic_score, "rec": recency_score, "ctx": context_score})

    top_candidates = heapq.nlargest(top_k, scored_candidates, key=lambda x: (x["score"], x["obs"].observed_at.timestamp(), -hash(x["obs"].record_id)))

    ranked = []
    for i, item in enumerate(top_candidates):
        obs = item["obs"]
        ranked.append(RankedCandidate(
            record_id=obs.record_id, observation=obs, rank=i + 1, score=item["score"],
            score_components={"semantic": item["sem"], "recency": item["rec"], "context": item["ctx"]},
        ))

    return RetrievalResult(method="no_eligibility", query_id="", ranked_candidates=ranked, status="OK")


def no_context(
    current: Observation,
    query_text: str,
    corpus: list[Observation],
    embeddings: tuple[np.ndarray, list[str], dict[str, int]] | None,
    query_embeddings: dict[str, np.ndarray] | None,
    top_k: int,
) -> RetrievalResult:
    """M6 minus context score — ψ_ctx forced to 0, weight redistributed."""
    if embeddings is None:
        return RetrievalResult(method="no_context", query_id="", ranked_candidates=[], status="NO_COMPARABLE_BASELINE")

    emb_matrix, emb_ids, id_to_idx = embeddings
    if query_embeddings is not None and query_text in query_embeddings:
        query_emb = query_embeddings[query_text]
    else:
        query_emb = encode_query(query_text)

    eligible = []
    for obs in corpus:
        if obs.patient_id != current.patient_id:
            continue
        eligibility = is_comparable(current, obs)
        if eligibility.is_eligible and obs.record_id in id_to_idx:
            eligible.append(obs)

    if not eligible:
        return RetrievalResult(method="no_context", query_id="", ranked_candidates=[], status="NO_COMPARABLE_BASELINE")

    decay_days = CONCEPT_DECAY_DAYS.get(current.concept_code, float(RECENCY_HALF_LIFE_DAYS))
    # No context: redistribute context weight equally to semantic and recency
    volatility = VOLATILITY_CLASS.get(current.concept_code, "medium")
    w_s_orig, w_r_orig, w_x_orig = DSW_WEIGHTS[volatility]
    w_s = w_s_orig + w_x_orig / 2.0
    w_r = w_r_orig + w_x_orig / 2.0

    # Get candidate indices for matrix slicing
    candidate_indices = [id_to_idx[obs.record_id] for obs in eligible]
    candidate_matrix = emb_matrix[candidate_indices]

    all_semantic_scores = cosine_similarity_scores(query_emb, candidate_matrix)

    scored_candidates = []
    for i, obs in enumerate(eligible):
        semantic_score = float(all_semantic_scores[i])
        elapsed_days = (current.observed_at - obs.observed_at).total_seconds() / 86400.0
        recency_score = math.exp(-elapsed_days / decay_days)
        hybrid_score = (w_s * semantic_score) + (w_r * recency_score)
        scored_candidates.append({"obs": obs, "score": hybrid_score, "sem": semantic_score, "rec": recency_score})

    top_candidates = heapq.nlargest(top_k, scored_candidates, key=lambda x: (x["score"], x["obs"].observed_at.timestamp(), -hash(x["obs"].record_id)))

    ranked = []
    for i, item in enumerate(top_candidates):
        obs = item["obs"]
        ranked.append(RankedCandidate(
            record_id=obs.record_id, observation=obs, rank=i + 1, score=item["score"],
            score_components={"semantic": item["sem"], "recency": item["rec"], "context": 0.0},
        ))

    return RetrievalResult(method="no_context", query_id="", ranked_candidates=ranked, status="OK")

