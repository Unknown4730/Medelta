#!/usr/bin/env python
"""Error analysis — profiling failures from the ablation predictions.

Analyzes predictions.jsonl to extract:
- False positive/negative distributions
- Failure categorization by type
- Concrete qualitative examples (3 successes, 2 failures)
"""
import sys
import json
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from meddelta.config import RESULTS_DIR, GENERATED_DIR


def load_predictions():
    """Load predictions for hybrid_csad_dsw (M6)."""
    preds = []
    with open(RESULTS_DIR / "predictions.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            p = json.loads(line.strip())
            if p.get("method") == "hybrid_csad_dsw":
                preds.append(p)
    return preds


def load_corpus_lookup():
    """Load observations for context enrichment."""
    import pandas as pd
    df = pd.read_csv(GENERATED_DIR / "observations.csv")
    lookup = {}
    for _, row in df.iterrows():
        lookup[str(row["record_id"])] = {
            "concept_code": str(row["concept_code"]),
            "canonical_value": float(row["canonical_value"]),
            "canonical_unit": str(row["canonical_unit"]),
            "patient_id": str(row["patient_id"]),
            "observed_at": str(row["observed_at"]),
            "condition_context": str(row.get("condition_context", "")),
            "anatomical_site": str(row.get("anatomical_site", "")),
            "note_text": str(row.get("note_text", ""))[:100],
        }
    return lookup


def categorize_failure(pred, corpus):
    """Categorize why a prediction failed."""
    expected = pred.get("expected_baseline_id")
    predicted = pred.get("predicted_baseline_id")

    if not expected or not predicted:
        return "NO_BASELINE_FOUND"

    exp_obs = corpus.get(expected, {})
    pred_obs = corpus.get(predicted, {})

    # Same concept but wrong record
    if exp_obs.get("concept_code") == pred_obs.get("concept_code"):
        # Same concept — ranking failure
        if exp_obs.get("condition_context") != pred_obs.get("condition_context"):
            return "CONTEXT_MISMATCH_RANKING"
        if exp_obs.get("anatomical_site") != pred_obs.get("anatomical_site"):
            return "SITE_MISMATCH_RANKING"
        return "RECENCY_TIE_BREAK"

    # Different concept retrieved
    return "CONCEPT_CONFUSION"


def main():
    print("=" * 60)
    print("  ERROR ANALYSIS — MedDelta-RAG M6")
    print("=" * 60)

    preds = load_predictions()
    corpus = load_corpus_lookup()

    if not preds:
        print("ERROR: No predictions found. Run experiments first.")
        return

    # Categorize all predictions
    correct = []
    failures = []
    for p in preds:
        if p["predicted_baseline_id"] == p["expected_baseline_id"]:
            correct.append(p)
        else:
            failures.append(p)

    total = len(preds)
    print(f"\n  Total queries: {total}")
    print(f"  Correct: {len(correct)} ({100*len(correct)/total:.1f}%)")
    print(f"  Failures: {len(failures)} ({100*len(failures)/total:.1f}%)")

    # Failure categorization
    failure_types = Counter()
    failure_examples = {}
    for f in failures:
        cat = categorize_failure(f, corpus)
        failure_types[cat] += 1
        if cat not in failure_examples:
            failure_examples[cat] = f

    print("\n  Failure Distribution:")
    print(f"  {'Type':<30} {'Count':>6} {'%':>8}")
    print("  " + "-" * 46)
    for ftype, count in failure_types.most_common():
        print(f"  {ftype:<30} {count:>6} {100*count/len(failures):>7.1f}%")

    # Qualitative examples: 3 successes
    success_examples = []
    seen_concepts = set()
    for s in correct:
        exp_id = s.get("expected_baseline_id", "")
        exp_obs = corpus.get(exp_id, {})
        concept = exp_obs.get("concept_code", "")
        if concept not in seen_concepts and len(success_examples) < 3:
            seen_concepts.add(concept)
            success_examples.append({
                "query_id": s["query_id"],
                "concept": concept,
                "predicted": s["predicted_baseline_id"],
                "expected": s["expected_baseline_id"],
                "scores": s.get("scores", {}),
                "trajectory_trend": s.get("trajectory_trend"),
            })

    # Qualitative examples: 2 failures
    failure_quals = []
    seen_ftypes = set()
    for ftype, example in failure_examples.items():
        if len(failure_quals) < 2 and ftype not in seen_ftypes:
            seen_ftypes.add(ftype)
            pred_obs = corpus.get(example.get("predicted_baseline_id", ""), {})
            exp_obs = corpus.get(example.get("expected_baseline_id", ""), {})
            failure_quals.append({
                "query_id": example["query_id"],
                "failure_type": ftype,
                "predicted_id": example["predicted_baseline_id"],
                "expected_id": example["expected_baseline_id"],
                "predicted_concept": pred_obs.get("concept_code", "N/A"),
                "expected_concept": exp_obs.get("concept_code", "N/A"),
                "predicted_note": pred_obs.get("note_text", "N/A"),
                "expected_note": exp_obs.get("note_text", "N/A"),
                "scores": example.get("scores", {}),
            })

    # Save
    output = {
        "total_queries": total,
        "correct": len(correct),
        "failures": len(failures),
        "accuracy": round(len(correct) / total, 6),
        "failure_distribution": dict(failure_types.most_common()),
        "success_examples": success_examples,
        "failure_examples": failure_quals,
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_DIR / "error_analysis.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\n  Qualitative Examples:")
    print(f"  Successes: {len(success_examples)} (diverse concepts)")
    print(f"  Failures:  {len(failure_quals)} (diverse failure types)")
    print(f"\n  Results saved to {RESULTS_DIR / 'error_analysis.json'}")


if __name__ == "__main__":
    main()
