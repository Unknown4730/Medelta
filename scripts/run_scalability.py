import sys, json, time, tracemalloc
from pathlib import Path
import os
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

import meddelta.config as cfg
from meddelta.generate_data import generate_corpus, save_corpus
from meddelta.embed import build_embeddings, load_embeddings
from meddelta.evaluation import evaluate_method
from meddelta.models import BenchmarkQuery, Observation
import numpy as np
import pandas as pd
from datetime import datetime

def main():
    sizes = [50, 100, 200, 500, 1000]
    
    results_dir = Path("data/results")
    results_dir.mkdir(parents=True, exist_ok=True)
    
    benchmarks = []
    
    for size in sizes:
        print(f"\n--- Benchmarking size: {size} patients ---")
        
        # We need to start tracemalloc to track peak memory
        tracemalloc.start()
        
        # 1. Generate corpus
        import meddelta.generate_data
        meddelta.generate_data.NUM_PATIENTS = size
        cfg.NUM_PATIENTS = size
        obs, queries = generate_corpus(seed=42)
        save_corpus(obs, queries)
        
        # 2. Build embeddings
        t0 = time.time()
        build_embeddings(obs)
        embed_time_s = time.time() - t0
        
        embed_tuple = load_embeddings()
        
        # 3. Load test-split queries
        test_queries = [q for q in queries if q.split == "test"]
        
        # 4. Run M6 (hybrid_csad_dsw)
        metrics = evaluate_method("hybrid_csad_dsw", test_queries, obs, embeddings=embed_tuple)
        
        _, peak_mem_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        peak_memory_mb = peak_mem_bytes / (1024 * 1024)
        
        embed_size_bytes = (cfg.GENERATED_DIR / "embeddings.npy").stat().st_size
        corpus_size_bytes = (cfg.GENERATED_DIR / "observations.csv").stat().st_size
        
        obs_count = len(obs)
        query_count = len(test_queries)
        
        latency_median_ms = metrics["latency"]["median"]
        latency_p95_ms = metrics["latency"]["p95"]
        bsa = metrics["bsa"]
        
        res = {
            "patients": size,
            "observations": obs_count,
            "queries": query_count,
            "bsa": bsa,
            "latency_median_ms": latency_median_ms,
            "latency_p95_ms": latency_p95_ms,
            "peak_memory_mb": peak_memory_mb,
            "embed_time_s": embed_time_s,
            "embed_size_bytes": embed_size_bytes,
            "corpus_size_bytes": corpus_size_bytes
        }
        benchmarks.append(res)
        
        print(f"Observations: {obs_count}, Test Queries: {query_count}")
        print(f"Median Latency: {latency_median_ms:.2f} ms")
        print(f"Peak Memory: {peak_memory_mb:.2f} MB")
        
    output_path = results_dir / "scalability.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"benchmarks": benchmarks}, f, indent=2)
        
    # Analyze asymptotic complexity
    try:
        from scipy.optimize import curve_fit
        
        def linear_model(n, a, b):
            return a * n + b

        def nlogn_model(n, a, b):
            return a * n * np.log2(np.maximum(n, 1)) + b

        ns = np.array([b["observations"] for b in benchmarks])
        lats = np.array([b["latency_median_ms"] for b in benchmarks])
        
        print("\n=== Asymptotic Complexity Estimate ===")
        
        popt_lin, _ = curve_fit(linear_model, ns, lats)
        popt_nlogn, _ = curve_fit(nlogn_model, ns, lats)
        
        ss_tot = np.sum((lats - np.mean(lats))**2)
        
        ss_res_lin = np.sum((lats - linear_model(ns, *popt_lin))**2)
        r2_lin = 1 - (ss_res_lin / ss_tot)
        
        ss_res_nlogn = np.sum((lats - nlogn_model(ns, *popt_nlogn))**2)
        r2_nlogn = 1 - (ss_res_nlogn / ss_tot)
        
        print(f"O(n)       fit R^2: {r2_lin:.4f}")
        print(f"O(n log n) fit R^2: {r2_nlogn:.4f}")
        
        if r2_nlogn > r2_lin:
            print("Conclusion: Latency exhibits closer to O(n log n) behavior.")
        else:
            print("Conclusion: Latency exhibits closer to O(n) behavior.")
    except ImportError:
        print("\n=== Asymptotic Complexity Estimate ===")
        print("scipy not installed. Skipping curve fitting.")
    except Exception as e:
        print("\n=== Asymptotic Complexity Estimate ===")
        print(f"Could not fit curves: {e}")

    # Print summary table
    print("\n=== Scalability Summary ===")
    df = pd.DataFrame(benchmarks)
    cols = ["patients", "observations", "queries", "latency_median_ms", "latency_p95_ms", "peak_memory_mb", "embed_time_s", "bsa"]
    print(df[cols].to_string(index=False))

if __name__ == "__main__":
    main()
