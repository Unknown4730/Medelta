"""Evaluation module — runs all retrieval methods on benchmark queries.

Computes per-method:
  BSA   Baseline Selection Accuracy (rank-1 exact match)
  VPR   Valid Pair Rate (fraction of rank-1 results that pass eligibility)
  HR@3  Top-3 Hit Rate
  MRR   Mean Reciprocal Rank
  DEM   Delta Exact Match (absolute_change matches within tolerance)
  EC    Evidence Completeness (all manifest fields populated)
  TAA   Trajectory Alignment Accuracy (trend direction match)

Also records per-query warm latency and computes trajectory statistics.
"""
from __future__ import annotations

import csv
import hashlib
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

import numpy as np
import pandas as pd

from meddelta.config import (
    ALL_METHODS,
    FORMULA_VERSION,
    GENERATED_DIR,
    MODEL_NAME,
    NUMERIC_TOLERANCE,
    RANDOM_SEED,
    RESULTS_DIR,
    TRAJECTORY_TOP_K,
)
from meddelta.delta import calculate_delta, calculate_trajectory
from meddelta.eligibility import is_comparable
from meddelta.embed import load_embeddings
from meddelta.evidence import build_evidence_manifest
from meddelta.models import BenchmarkQuery, DeltaResult, Observation, TrajectoryResult
from meddelta.retrieval import retrieve_baseline


# ── Metric helpers ────────────────────────────────────────────────


def _percentile(values: list[float], pct: float) -> float:
    """Return the *pct*-th percentile of *values* (0–100 scale)."""
    if not values:
        return 0.0
    s = sorted(values)
    idx = min(int(len(s) * pct / 100.0), len(s) - 1)
    return s[idx]


# ── Single-method evaluation ──────────────────────────────────────


def evaluate_method(
    method: str,
    queries: list[BenchmarkQuery],
    corpus: list[Observation],
    embeddings: tuple[np.ndarray, list[str], dict[str, int]] | None = None,
    fast_mode: bool = False,
) -> dict:
    """Evaluate *method* on *queries* and return metrics + raw predictions."""

    predictions: list[dict] = []
    latencies: list[dict] = []

    correct_rank1 = 0
    evaluable_queries = 0
    comparable_rank1_pairs = 0
    queries_returning_result = 0
    queries_expected_in_top3 = 0
    mrr_sum = 0.0
    correct_delta = 0
    valid_pairs = 0
    manifests_complete = 0
    total_manifests = 0

    # Trajectory metrics
    trajectory_correct_trend = 0
    trajectory_total = 0

    corpus_by_id = {obs.record_id: obs for obs in corpus}
    
    from collections import defaultdict
    patient_index = defaultdict(list)
    for obs in corpus:
        patient_index[obs.patient_id].append(obs)
        
    from meddelta.embed import encode_query
    query_embeddings = {q.query_text: encode_query(q.query_text) for q in queries}
    
    from meddelta.eligibility import clear_eligibility_cache
    clear_eligibility_cache()
    
    global_methods = {"bm25", "biobert_semantic"}

    for i, query in enumerate(queries):
        if i > 0 and i % 500 == 0:
            print(f"    [{method}] Processed {i}/{len(queries)} queries...")
            
        current = corpus_by_id.get(query.current_record_id)
        if current is None:
            continue

        # ── Warm-query timing ──
        t0 = time.perf_counter()
        target_corpus = corpus if method in global_methods else patient_index.get(current.patient_id, [])
        
        result = retrieve_baseline(
            current, query.query_text, target_corpus, method, embeddings, query_embeddings, top_k=TRAJECTORY_TOP_K
        )
        latency_ms = (time.perf_counter() - t0) * 1000.0
        latencies.append(
            {"method": method, "query_id": query.query_id, "latency_ms": latency_ms}
        )

        predicted_id: str | None = None
        predicted_status = result.status
        scores: dict = {}

        if result.ranked_candidates:
            predicted_id = result.ranked_candidates[0].record_id
            scores = result.ranked_candidates[0].score_components
            queries_returning_result += 1
            if predicted_status == "OK":
                comparable_rank1_pairs += 1

        evaluable_queries += 1

        # ── Baseline Selection Accuracy (rank-1) ──
        if predicted_id == query.expected_baseline_id:
            correct_rank1 += 1

        # ── Top-3 Hit Rate & MRR ──
        candidate_ids = [c.record_id for c in result.ranked_candidates]
        if query.expected_baseline_id and query.expected_baseline_id in candidate_ids:
            rank = candidate_ids.index(query.expected_baseline_id) + 1
            if rank <= 3:
                queries_expected_in_top3 += 1
            mrr_sum += 1.0 / rank

        # ── Delta Exact Match & Evidence Completeness ──
        delta_result: DeltaResult | None = None
        trajectory: TrajectoryResult | None = None

        if not fast_mode and result.ranked_candidates and predicted_status == "OK":
            baseline_obs = result.ranked_candidates[0].observation
            delta_result = calculate_delta(current, baseline_obs)
            valid_pairs += 1

            # Delta correctness vs expected baseline
            expected_baseline = corpus_by_id.get(query.expected_baseline_id or "")
            if (
                expected_baseline is not None
                and predicted_id == query.expected_baseline_id
            ):
                expected_delta = calculate_delta(current, expected_baseline)
                if abs(delta_result.absolute_change - expected_delta.absolute_change) < NUMERIC_TOLERANCE:
                    correct_delta += 1

            # Evidence manifest completeness
            manifest = build_evidence_manifest(current, result, delta_result)
            total_manifests += 1
            if all([
                manifest.current_record,
                manifest.baseline_record,
                manifest.retrieval_result,
                manifest.delta_result,
                manifest.formula_version,
            ]):
                manifests_complete += 1

            # ── Trajectory computation (TAR) ──
            baseline_observations = [
                c.observation for c in result.ranked_candidates
                if c.observation.concept_code == current.concept_code
                and c.observation.canonical_unit == current.canonical_unit
            ]
            if len(baseline_observations) >= 2:
                trajectory = calculate_trajectory(current, baseline_observations)
                trajectory_total += 1

                # Trend alignment: check if the trajectory slope direction
                # agrees with the pairwise delta direction
                if delta_result.absolute_change > NUMERIC_TOLERANCE:
                    expected_trend = "INCREASING"
                elif delta_result.absolute_change < -NUMERIC_TOLERANCE:
                    expected_trend = "DECREASING"
                else:
                    expected_trend = "STABLE"

                if trajectory.trend == expected_trend:
                    trajectory_correct_trend += 1

        predictions.append({
            "query_id": query.query_id,
            "method": method,
            "predicted_baseline_id": predicted_id,
            "predicted_status": predicted_status,
            "expected_baseline_id": query.expected_baseline_id,
            "expected_status": query.expected_status,
            "scores": scores,
            "trajectory_trend": trajectory.trend if trajectory else None,
            "trajectory_r2": trajectory.r_squared if trajectory else None,
            "trajectory_slope": trajectory.slope if trajectory else None,
        })

    # ── Aggregate metrics ──
    bsa = correct_rank1 / evaluable_queries if evaluable_queries else 0.0
    vpr = comparable_rank1_pairs / queries_returning_result if queries_returning_result else 0.0
    top3 = queries_expected_in_top3 / evaluable_queries if evaluable_queries else 0.0
    mrr = mrr_sum / evaluable_queries if evaluable_queries else 0.0
    delta_em = correct_delta / valid_pairs if valid_pairs else 0.0
    ev_comp = manifests_complete / total_manifests if total_manifests else 0.0
    taa = trajectory_correct_trend / trajectory_total if trajectory_total else 0.0

    lat_vals = [l["latency_ms"] for l in latencies]
    latency_stats = {
        "median": median(lat_vals) if lat_vals else 0.0,
        "p95": _percentile(lat_vals, 95),
        "min": min(lat_vals) if lat_vals else 0.0,
        "max": max(lat_vals) if lat_vals else 0.0,
    }

    return {
        "method": method,
        "bsa": bsa,
        "vpr": vpr,
        "top3_hit_rate": top3,
        "mrr": mrr,
        "delta_em": delta_em,
        "evidence_completeness": ev_comp,
        "trajectory_alignment": taa,
        "trajectory_count": trajectory_total,
        "latency": latency_stats,
        "predictions": predictions,
        "latencies": latencies,
    }


# ── Run all experiments ───────────────────────────────────────────


def run_all_experiments(
    queries: list[BenchmarkQuery],
    corpus: list[Observation],
    embeddings: tuple[np.ndarray, list[str], dict[str, int]] | None = None,
) -> dict:
    results: dict[str, dict] = {}
    for method in ALL_METHODS:
        print(f"  [{method}] evaluating...")
        results[method] = evaluate_method(method, queries, corpus, embeddings, fast_mode=False)
    return results


# ── Save result artifacts ─────────────────────────────────────────


def save_results(
    results: dict[str, dict],
    predictions: list[dict],
    latencies: list[dict],
) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # ── metrics.csv ──
    header = [
        "method", "bsa", "vpr", "top3_hit_rate", "mrr",
        "delta_em", "evidence_completeness", "trajectory_alignment",
        "trajectory_count",
        "latency_median", "latency_p95", "latency_min", "latency_max",
    ]
    with open(RESULTS_DIR / "metrics.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for method, res in results.items():
            lat = res["latency"]
            w.writerow([
                method,
                f"{res['bsa']:.6f}", f"{res['vpr']:.6f}",
                f"{res['top3_hit_rate']:.6f}", f"{res['mrr']:.6f}",
                f"{res['delta_em']:.6f}", f"{res['evidence_completeness']:.6f}",
                f"{res['trajectory_alignment']:.6f}",
                res['trajectory_count'],
                f"{lat['median']:.4f}", f"{lat['p95']:.4f}",
                f"{lat['min']:.4f}", f"{lat['max']:.4f}",
            ])

    # ── predictions.jsonl ──
    with open(RESULTS_DIR / "predictions.jsonl", "w", encoding="utf-8") as f:
        for p in predictions:
            f.write(json.dumps(p, default=str) + "\n")

    # ── latency.csv ──
    with open(RESULTS_DIR / "latency.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["method", "query_id", "latency_ms"])
        w.writeheader()
        w.writerows(latencies)

    # ── run_manifest.json ──
    corpus_hash = ""
    obs_csv = GENERATED_DIR / "observations.csv"
    if obs_csv.exists():
        corpus_hash = hashlib.sha256(obs_csv.read_bytes()).hexdigest()

    manifest = {
        "seed": RANDOM_SEED,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "model_name": MODEL_NAME,
        "formula_version": FORMULA_VERSION,
        "corpus_hash": corpus_hash,
        "machine": {
            "processor": platform.processor(),
            "architecture": platform.machine(),
        },
        "methods": ALL_METHODS,
        "num_queries": len(predictions) // max(len(results), 1),
    }
    with open(RESULTS_DIR / "run_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    # ── ablation_summary.json (for paper tables) ──
    summary = {}
    for method, res in results.items():
        summary[method] = {
            "BSA": round(res["bsa"], 6),
            "VPR": round(res["vpr"], 6),
            "HR@3": round(res["top3_hit_rate"], 6),
            "MRR": round(res["mrr"], 6),
            "DEM": round(res["delta_em"], 6),
            "EC": round(res["evidence_completeness"], 6),
            "TAA": round(res["trajectory_alignment"], 6),
            "latency_median_ms": round(res["latency"]["median"], 4),
            "latency_p95_ms": round(res["latency"]["p95"], 4),
        }
    with open(RESULTS_DIR / "ablation_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)


# ── Convenience entry point ───────────────────────────────────────


def run_full_evaluation() -> None:
    """Load generated data, run all experiments, and save results."""
    print("Loading corpus...")
    obs_csv = GENERATED_DIR / "observations.csv"
    queries_json = GENERATED_DIR / "queries.json"

    if not obs_csv.exists() or not queries_json.exists():
        print("ERROR: Generated data not found.  Run  python scripts/generate_dataset.py  first.")
        return

    # ── Load observations from CSV ──
    df = pd.read_csv(obs_csv)
    corpus: list[Observation] = []
    for row in df.itertuples(index=False):
        corpus.append(
            Observation(
                record_id=str(row.record_id),
                patient_id=str(row.patient_id),
                observed_at=datetime.fromisoformat(str(row.observed_at)),
                concept_code=str(row.concept_code),
                concept_label=str(row.concept_label),
                value=float(row.value),
                unit=str(row.unit),
                canonical_value=float(row.canonical_value),
                canonical_unit=str(row.canonical_unit),
                condition_context=str(row.condition_context) if pd.notna(getattr(row, "condition_context", None)) else None,
                anatomical_site=str(row.anatomical_site) if pd.notna(getattr(row, "anatomical_site", None)) else None,
                note_text=str(getattr(row, "note_text", "")),
                source_type=str(getattr(row, "source_type", "lab")),
                is_synthetic=True,
            )
        )

    # ── Load queries ──
    with open(queries_json, "r", encoding="utf-8") as f:
        q_data = json.load(f)
    queries = [BenchmarkQuery(**q) for q in q_data]

    # ── Load embeddings ──
    print("Loading embeddings...")
    embeddings = load_embeddings()

    # ── Run experiments (6-method ablation) ──
    print(f"Running {len(ALL_METHODS)}-method ablation study...")
    results = run_all_experiments(queries, corpus, embeddings)

    # ── Collect all predictions and latencies ──
    all_predictions: list[dict] = []
    all_latencies: list[dict] = []
    for res in results.values():
        all_predictions.extend(res["predictions"])
        all_latencies.extend(res["latencies"])

    # ── Save ──
    print("Saving results...")
    save_results(results, all_predictions, all_latencies)

    # ── Summary ──
    print("\n" + "=" * 72)
    print("  ABLATION STUDY RESULTS — MedDelta-RAG v2.0")
    print("=" * 72)
    header = f"{'Method':<20} {'BSA':>8} {'VPR':>8} {'HR@3':>8} {'MRR':>8} {'DEM':>8} {'EC':>8} {'TAA':>8} {'Lat(ms)':>8}"
    print(header)
    print("-" * len(header))
    for method, res in results.items():
        print(
            f"{method:<20} "
            f"{res['bsa']:>8.4f} "
            f"{res['vpr']:>8.4f} "
            f"{res['top3_hit_rate']:>8.4f} "
            f"{res['mrr']:>8.4f} "
            f"{res['delta_em']:>8.4f} "
            f"{res['evidence_completeness']:>8.4f} "
            f"{res['trajectory_alignment']:>8.4f} "
            f"{res['latency']['median']:>8.1f}"
        )
    print("=" * 72)
    print(f"Results saved to {RESULTS_DIR}")
