import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

import json
import math
import numpy as np
import pandas as pd
from datetime import datetime
from scipy.stats import wilcoxon

from meddelta.config import ALL_METHODS, GENERATED_DIR, RESULTS_DIR
from meddelta.generate_data import generate_corpus, save_corpus
from meddelta.embed import build_embeddings, load_embeddings
from meddelta.evaluation import evaluate_method
from meddelta.models import BenchmarkQuery, Observation

def cliffs_delta(x, y):
    n = len(x) * len(y)
    more = sum(1 for xi in x for yi in y if xi > yi)
    less = sum(1 for xi in x for yi in y if xi < yi)
    d = (more - less) / n
    abs_d = abs(d)
    if abs_d < 0.147:
        label = "negligible"
    elif abs_d < 0.33:
        label = "small"
    elif abs_d < 0.474:
        label = "medium"
    else:
        label = "large"
    return d, label

def holm_bonferroni(p_values):
    n = len(p_values)
    sorted_indices = sorted(range(n), key=lambda i: p_values[i])
    corrected = [0.0] * n
    for rank, idx in enumerate(sorted_indices):
        corrected[idx] = min(p_values[idx] * (n - rank), 1.0)
    return corrected

def run_wilcoxon(x, y):
    if np.allclose(x, y):
        return 1.0
    try:
        res = wilcoxon(x, y)
        return res.pvalue
    except ValueError:
        return 1.0

def main():
    seeds = [42, 43, 44, 45, 46, 47, 48, 49, 50, 51]
    
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    
    per_seed = {}

    for seed in seeds:
        print(f"--- Running seed {seed} ---")
        # a. Call generate_corpus and save_corpus
        obs, queries_raw = generate_corpus(seed=seed)
        save_corpus(obs, queries_raw)
        
        # b. Call build_embeddings
        build_embeddings(obs)

        # c. Load queries
        with open(GENERATED_DIR / "queries.json", "r", encoding="utf-8") as f:
            saved_queries = json.load(f)
        
        # d. Filter to split == 'test'
        queries = [BenchmarkQuery(**q) for q in saved_queries if q.get("split") == "test"]
        
        # e. Load embeddings
        embeddings = load_embeddings()
        
        # f. Load corpus
        df = pd.read_csv(GENERATED_DIR / "observations.csv")
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

        # g. Evaluate each method
        seed_results = {}
        for method in ALL_METHODS:
            res = evaluate_method(method, queries, corpus, embeddings)
            res["hr@1"] = res.get("bsa", 0.0)
            seed_results[method] = res
            
        per_seed[str(seed)] = seed_results

    # 2. After all 10 seeds: Compute summary
    summary = {}
    metrics = ["bsa", "mrr", "hr@1", "hr@3", "dem", "vpr"]
    for method in ALL_METHODS:
        summary[method] = {}
        for m in metrics:
            vals = [per_seed[str(seed)][method].get(m, 0.0) for seed in seeds]
            mean_val = np.mean(vals)
            std_val = np.std(vals, ddof=1) if len(vals) > 1 else 0.0
            ci = 1.96 * std_val / math.sqrt(len(vals)) if len(vals) > 0 else 0.0
            summary[method][f"{m}_mean"] = float(mean_val)
            summary[method][f"{m}_std"] = float(std_val)
            summary[method][f"{m}_ci95_lo"] = float(mean_val - ci)
            summary[method][f"{m}_ci95_hi"] = float(mean_val + ci)

    # b. Wilcoxon Signed Rank Test
    m3_bsa = [per_seed[str(seed)]["hybrid"]["bsa"] for seed in seeds]
    m6_bsa = [per_seed[str(seed)]["hybrid_csad_dsw"]["bsa"] for seed in seeds]
    m4_bsa = [per_seed[str(seed)]["hybrid_csad"]["bsa"] for seed in seeds]
    m5_bsa = [per_seed[str(seed)]["hybrid_dsw"]["bsa"] for seed in seeds]

    comps = [
        ("M3_vs_M6", m3_bsa, m6_bsa),
        ("M3_vs_M4", m3_bsa, m4_bsa),
        ("M3_vs_M5", m3_bsa, m5_bsa)
    ]

    p_raws = []
    cd_results = []
    
    for name, x, y in comps:
        p = run_wilcoxon(x, y)
        # We pass y, x to get a positive delta if y > x (since y is the new method)
        d, label = cliffs_delta(y, x)
        p_raws.append(p)
        cd_results.append((d, label))

    p_corrected = holm_bonferroni(p_raws)

    hypothesis_tests = []
    for i, (name, x, y) in enumerate(comps):
        d, label = cd_results[i]
        hypothesis_tests.append({
            "comparison": name,
            "test": "wilcoxon",
            "p_raw": float(p_raws[i]),
            "p_corrected": float(p_corrected[i]),
            "cliffs_delta": float(d),
            "effect_size_label": label,
            "significant": bool(p_corrected[i] < 0.05)
        })

    # 3. Save results
    final_output = {
        "seeds": seeds,
        "per_seed": per_seed,
        "summary": summary,
        "hypothesis_tests": hypothesis_tests
    }
    
    out_path = RESULTS_DIR / "statistical_summary.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(final_output, f, indent=2)

    # 4. Print a human-readable summary table
    print("\n" + "="*80)
    print("STATISTICAL VALIDATION SUMMARY (10 Seeds)")
    print("="*80)
    print(f"{'Method':<20} | {'BSA Mean (95% CI)':<25} | {'MRR Mean':<10} | {'HR@3 Mean':<10}")
    print("-" * 75)
    for method in ALL_METHODS:
        m = summary[method]
        bsa_str = f"{m['bsa_mean']:.3f} ± {m['bsa_ci95_hi'] - m['bsa_mean']:.3f}"
        print(f"{method:<20} | {bsa_str:<25} | {m['mrr_mean']:.3f}     | {m['hr@3_mean']:.3f}")
    
    print("\nHYPOTHESIS TESTS (Wilcoxon Signed-Rank + Holm-Bonferroni)")
    print("-" * 80)
    print(f"{'Comparison':<15} | {'p (raw)':<10} | {'p (corr)':<10} | {'Significant?':<12} | {'Cliff s Delta':<15}")
    print("-" * 80)
    for ht in hypothesis_tests:
        sig = "YES" if ht["significant"] else "NO"
        cd_str = f"{ht['cliffs_delta']:.3f} ({ht['effect_size_label']})"
        print(f"{ht['comparison']:<15} | {ht['p_raw']:<10.4f} | {ht['p_corrected']:<10.4f} | {sig:<12} | {cd_str:<15}")
    print("="*80)

if __name__ == "__main__":
    main()
