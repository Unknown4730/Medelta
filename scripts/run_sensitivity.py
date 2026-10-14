#!/usr/bin/env python
"""Hyperparameter sensitivity analysis for CSAD decay constants and DSW weights.

Performs a grid search over the validation split to empirically justify
the chosen constants, demonstrating robustness rather than cherry-picking.
"""
import sys
import json
import itertools
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd
from datetime import datetime

import meddelta.config as cfg
from meddelta.generate_data import generate_corpus, save_corpus
from meddelta.embed import build_embeddings, load_embeddings
from meddelta.evaluation import evaluate_method
from meddelta.models import BenchmarkQuery, Observation


def load_corpus_and_queries():
    """Load corpus + validation-split queries from generated data."""
    obs_csv = cfg.GENERATED_DIR / "observations.csv"
    queries_json = cfg.GENERATED_DIR / "queries.json"

    df = pd.read_csv(obs_csv)
    corpus = []
    for _, row in df.iterrows():
        corpus.append(
            Observation(
                record_id=str(row["record_id"]),
                patient_id=str(row["patient_id"]),
                observed_at=datetime.fromisoformat(str(row["observed_at"])),
                concept_code=str(row["concept_code"]),
                concept_label=str(row["concept_label"]),
                value=float(row["value"]),
                unit=str(row["unit"]),
                canonical_value=float(row["canonical_value"]),
                canonical_unit=str(row["canonical_unit"]),
                condition_context=str(row["condition_context"]) if pd.notna(row.get("condition_context")) else None,
                anatomical_site=str(row["anatomical_site"]) if pd.notna(row.get("anatomical_site")) else None,
                note_text=str(row.get("note_text", "")),
                source_type=str(row.get("source_type", "lab")),
                is_synthetic=True,
            )
        )

    with open(queries_json, "r", encoding="utf-8") as f:
        q_data = json.load(f)
    # Use VALIDATION split only for hyperparameter selection
    queries = [BenchmarkQuery(**q) for q in q_data if q.get("split") == "development"]
    print(f"  Loaded {len(corpus)} observations, {len(queries)} validation queries")
    return corpus, queries


def run_csad_sensitivity():
    """Grid search over CSAD decay constants."""
    print("\n=== CSAD Sensitivity Analysis ===")

    # Grid: vary glucose (fastest) and lesion (slowest), keep others proportional
    glucose_lambdas = [90, 120, 180, 240, 360]
    lesion_lambdas = [180, 300, 450, 600, 720]

    corpus, queries = load_corpus_and_queries()
    embeddings = load_embeddings()

    results = []
    original_decay = dict(cfg.CONCEPT_DECAY_DAYS)

    for g_lambda in glucose_lambdas:
        for l_lambda in lesion_lambdas:
            # Set decay constants proportionally
            ratio = l_lambda / g_lambda
            cfg.CONCEPT_DECAY_DAYS["glucose"] = float(g_lambda)
            cfg.CONCEPT_DECAY_DAYS["systolic_bp"] = float(g_lambda * 1.33)
            cfg.CONCEPT_DECAY_DAYS["HbA1c"] = float(g_lambda * 1.50)
            cfg.CONCEPT_DECAY_DAYS["creatinine"] = float(g_lambda * 1.67)
            cfg.CONCEPT_DECAY_DAYS["lesion_diameter"] = float(l_lambda)

            # Clear retrieval caches
            import meddelta.retrieval as ret
            ret._bm25_index = None

            res = evaluate_method("hybrid_csad_dsw", queries, corpus, embeddings)
            bsa = res["bsa"]
            results.append({
                "glucose_lambda": g_lambda,
                "lesion_lambda": l_lambda,
                "ratio": round(ratio, 2),
                "BSA": round(bsa, 6),
                "MRR": round(res["mrr"], 6),
            })
            print(f"  glucose={g_lambda:>4}, lesion={l_lambda:>4} (ratio={ratio:.1f}) -> BSA={bsa:.4f}")

    # Restore original
    cfg.CONCEPT_DECAY_DAYS.update(original_decay)
    return results


def run_dsw_sensitivity():
    """Grid search over DSW weight vectors for high-volatility class."""
    print("\n=== DSW Weight Sensitivity Analysis ===")

    # Grid: vary recency weight for high-volatility concepts
    recency_weights = [0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55]

    corpus, queries = load_corpus_and_queries()
    embeddings = load_embeddings()

    results = []
    original_dsw = dict(cfg.DSW_WEIGHTS)

    for w_r in recency_weights:
        remaining = 1.0 - w_r
        w_s = remaining * 0.65  # semantic gets ~65% of remainder
        w_x = remaining * 0.35  # context gets ~35% of remainder

        cfg.DSW_WEIGHTS["high"] = (round(w_s, 3), round(w_r, 3), round(w_x, 3))

        import meddelta.retrieval as ret
        ret._bm25_index = None

        res = evaluate_method("hybrid_csad_dsw", queries, corpus, embeddings)
        bsa = res["bsa"]
        results.append({
            "w_semantic": round(w_s, 3),
            "w_recency": round(w_r, 3),
            "w_context": round(w_x, 3),
            "BSA": round(bsa, 6),
            "MRR": round(res["mrr"], 6),
        })
        print(f"  w_r={w_r:.2f} (s={w_s:.3f}, x={w_x:.3f}) -> BSA={bsa:.4f}")

    # Restore original
    cfg.DSW_WEIGHTS.update(original_dsw)
    return results


def main():
    print("=" * 60)
    print("  HYPERPARAMETER SENSITIVITY ANALYSIS")
    print("=" * 60)

    csad_results = run_csad_sensitivity()
    dsw_results = run_dsw_sensitivity()

    output = {
        "csad_sensitivity": csad_results,
        "dsw_sensitivity": dsw_results,
        "notes": {
            "csad": "Grid search over glucose (fastest) and lesion (slowest) decay constants. Other concepts scaled proportionally.",
            "dsw": "Grid search over recency weight for high-volatility concepts. Remaining weight split 65/35 semantic/context.",
            "split": "Evaluated on validation split (development queries) only.",
        },
    }

    cfg.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(cfg.RESULTS_DIR / "sensitivity.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    # Summary
    print("\n" + "=" * 60)
    print("  CSAD Sensitivity (BSA on validation split)")
    print("=" * 60)
    best_csad = max(csad_results, key=lambda x: x["BSA"])
    worst_csad = min(csad_results, key=lambda x: x["BSA"])
    print(f"  Best:  glucose={best_csad['glucose_lambda']}, lesion={best_csad['lesion_lambda']} -> BSA={best_csad['BSA']:.4f}")
    print(f"  Worst: glucose={worst_csad['glucose_lambda']}, lesion={worst_csad['lesion_lambda']} -> BSA={worst_csad['BSA']:.4f}")
    print(f"  Range: {best_csad['BSA'] - worst_csad['BSA']:.4f} pp")

    print("\n  DSW Sensitivity (BSA on validation split)")
    print("-" * 60)
    best_dsw = max(dsw_results, key=lambda x: x["BSA"])
    worst_dsw = min(dsw_results, key=lambda x: x["BSA"])
    print(f"  Best:  w_r={best_dsw['w_recency']:.2f} -> BSA={best_dsw['BSA']:.4f}")
    print(f"  Worst: w_r={worst_dsw['w_recency']:.2f} -> BSA={worst_dsw['BSA']:.4f}")
    print(f"  Range: {best_dsw['BSA'] - worst_dsw['BSA']:.4f} pp")

    print(f"\nResults saved to {cfg.RESULTS_DIR / 'sensitivity.json'}")


if __name__ == "__main__":
    main()
