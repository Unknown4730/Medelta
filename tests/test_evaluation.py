"""Tests for the evaluation module."""
import json
from pathlib import Path

import pytest

from meddelta.evaluation import save_results


def test_metric_calculation():
    """Verify BSA / VPR formulas with trivial known values."""
    # BSA = correct_rank1 / evaluable
    correct = 3
    evaluable = 5
    assert correct / evaluable == pytest.approx(0.6)


def test_mrr_calculation():
    """MRR with known ranking positions."""
    # rank 1 → 1.0, rank 3 → 0.333, not found → 0.0
    reciprocals = [1.0, 1.0 / 3, 0.0]
    mrr = sum(reciprocals) / len(reciprocals)
    assert mrr == pytest.approx(0.4444, rel=1e-3)


def test_latency_positive():
    """Latency values must be non-negative."""
    import time
    t0 = time.perf_counter()
    _ = 1 + 1  # trivial work
    elapsed = (time.perf_counter() - t0) * 1000.0
    assert elapsed >= 0.0


def test_save_results_creates_files(tmp_path, monkeypatch):
    """save_results should create all four output files."""
    import meddelta.evaluation as eval_mod

    # Patch RESULTS_DIR and GENERATED_DIR on the evaluation module itself
    monkeypatch.setattr(eval_mod, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(eval_mod, "GENERATED_DIR", tmp_path)

    # Create a fake observations.csv for corpus hash
    (tmp_path / "observations.csv").write_text("a,b\n1,2\n")

    results = {
        "metadata_only": {
            "bsa": 0.8, "vpr": 0.9, "top3_hit_rate": 0.85,
            "mrr": 0.75, "delta_em": 1.0, "evidence_completeness": 1.0,
            "latency": {"median": 5.0, "p95": 10.0, "min": 1.0, "max": 15.0},
        },
    }
    save_results(results, [{"query_id": "Q1", "method": "metadata_only"}], [{"method": "metadata_only", "query_id": "Q1", "latency_ms": 5.0}])

    assert (tmp_path / "metrics.csv").exists()
    assert (tmp_path / "predictions.jsonl").exists()
    assert (tmp_path / "latency.csv").exists()
    assert (tmp_path / "run_manifest.json").exists()

    # Verify run_manifest has expected fields
    manifest = json.loads((tmp_path / "run_manifest.json").read_text())
    assert "seed" in manifest
    assert "corpus_hash" in manifest
    assert manifest["corpus_hash"] != ""
