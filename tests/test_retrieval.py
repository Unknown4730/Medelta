"""Tests for retrieval strategies (metadata-only, semantic-only, hybrid)."""
from datetime import datetime, timedelta

import numpy as np

from meddelta.models import EligibilityResult, Observation, RetrievalResult
from meddelta.retrieval import retrieve_baseline


def make_obs(pid, cc, days_ago, ctx="ctx1", site="site1", rec_id="r1"):
    dt = datetime(2023, 1, 1) - timedelta(days=days_ago)
    return Observation(
        record_id=rec_id, patient_id=pid, observed_at=dt,
        concept_code=cc, concept_label="C", value=1.0, unit="mg",
        canonical_value=1.0, canonical_unit="mg",
        condition_context=ctx, anatomical_site=site,
    )


# ── Metadata-only ─────────────────────────────────────────────────


def test_metadata_only_returns_correct_baseline():
    curr = make_obs("p1", "c1", 0)
    corpus = [
        make_obs("p1", "c1", 1, rec_id="r2"),
        make_obs("p1", "c1", 2, rec_id="r3"),
        make_obs("p2", "c1", 1, rec_id="r4"),
    ]
    res = retrieve_baseline(curr, "query", corpus, method="metadata_only")
    assert res.status == "OK"
    assert len(res.ranked_candidates) == 2
    assert res.ranked_candidates[0].record_id == "r2"


def test_metadata_only_no_baseline():
    curr = make_obs("p1", "c1", 0)
    corpus = [make_obs("p1", "c2", 1)]
    res = retrieve_baseline(curr, "query", corpus, method="metadata_only")
    assert res.status == "NO_COMPARABLE_BASELINE"


# ── Hybrid (monkeypatch on meddelta.retrieval where imports live) ─


def test_hybrid_eligibility_gate(monkeypatch):
    import meddelta.retrieval as ret_mod

    monkeypatch.setattr(ret_mod, "is_comparable",
                        lambda c, b: EligibilityResult(
                            is_eligible=(b.record_id == "r2"),
                            reason_code="OK" if b.record_id == "r2" else "CONCEPT_MISMATCH"))
    monkeypatch.setattr(ret_mod, "encode_query", lambda q: np.array([1.0]))
    monkeypatch.setattr(ret_mod, "cosine_similarity_scores",
                        lambda q, c: np.array([0.9]))

    curr = make_obs("p1", "c1", 0)
    corpus = [
        make_obs("p1", "c1", 1, rec_id="r2"),
        make_obs("p1", "c1", 2, rec_id="r3"),
    ]
    embeddings = (np.array([[1.0], [1.0]]), ["r2", "r3"])

    res = retrieve_baseline(curr, "query", corpus, method="hybrid", embeddings=embeddings)
    assert len(res.ranked_candidates) == 1
    assert res.ranked_candidates[0].record_id == "r2"


def test_hybrid_tie_breaking(monkeypatch):
    import meddelta.retrieval as ret_mod

    monkeypatch.setattr(ret_mod, "is_comparable",
                        lambda c, b: EligibilityResult(is_eligible=True, reason_code="OK"))
    monkeypatch.setattr(ret_mod, "encode_query", lambda q: np.array([1.0]))
    monkeypatch.setattr(ret_mod, "cosine_similarity_scores",
                        lambda q, c: np.array([1.0]))

    curr = make_obs("p1", "c1", 0)
    corpus = [
        make_obs("p1", "c1", 1, rec_id="A"),
        make_obs("p1", "c1", 1, rec_id="B"),
    ]
    embeddings = (np.array([[1.0], [1.0]]), ["A", "B"])

    res = retrieve_baseline(curr, "query", corpus, method="hybrid", embeddings=embeddings)
    # Tie-break: same timestamp → lexicographic record_id → "A" < "B"
    assert res.ranked_candidates[0].record_id == "A"


def test_all_methods_return_retrieval_result(monkeypatch):
    import meddelta.retrieval as ret_mod

    monkeypatch.setattr(ret_mod, "is_comparable",
                        lambda c, b: EligibilityResult(is_eligible=True, reason_code="OK"))
    monkeypatch.setattr(ret_mod, "encode_query", lambda q: np.array([1.0]))
    monkeypatch.setattr(ret_mod, "cosine_similarity_scores",
                        lambda q, c: np.array([1.0]))

    curr = make_obs("p1", "c1", 0)
    corpus = [make_obs("p1", "c1", 1)]
    embeddings = (np.array([[1.0]]), ["r1"])

    for m in ["metadata_only", "semantic_only", "hybrid"]:
        res = retrieve_baseline(curr, "query", corpus, method=m, embeddings=embeddings)
        assert isinstance(res, RetrievalResult)
        assert res.method == m
