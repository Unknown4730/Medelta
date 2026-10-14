import sys
import json
import copy
import concurrent.futures
import random
from pathlib import Path
from datetime import datetime, timedelta

# Setup paths
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from meddelta.config import GENERATED_DIR, RESULTS_DIR, RANDOM_SEED
from meddelta.embed import load_embeddings
from meddelta.evaluation import evaluate_method
from meddelta.models import BenchmarkQuery, Observation
import numpy as np
import pandas as pd


def load_base_corpus() -> list[Observation]:
    obs_csv = GENERATED_DIR / "observations.csv"
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
    return corpus


def load_base_queries() -> list[BenchmarkQuery]:
    queries_json = GENERATED_DIR / "queries.json"
    with open(queries_json, "r", encoding="utf-8") as f:
        q_data = json.load(f)
    return [BenchmarkQuery(**q) for q in q_data]


def perturb_misspellings(corpus: list[Observation], rate: float, rng: random.Random) -> list[Observation]:
    if rate == 0: return corpus
    mod = []
    mapping = {
        'creatinine': ['creatinne', 'creatanine'],
        'glucose': ['glucos', 'gloucose'],
        'systolic_bp': ['systolc_bp', 'systolic_BP'],
        'HbA1c': ['hba1C', 'Hba1c'],
        'lesion_diameter': ['lesion_diamter', 'lession_diameter']
    }
    for obs in corpus:
        o = copy.copy(obs)
        if rng.random() < rate and o.concept_code in mapping:
            o.concept_code = rng.choice(mapping[o.concept_code])
        mod.append(o)
    return mod


def perturb_missing_units(corpus: list[Observation], rate: float, rng: random.Random) -> list[Observation]:
    if rate == 0: return corpus
    mod = []
    for obs in corpus:
        o = copy.copy(obs)
        if rng.random() < rate:
            o.unit = ''
            o.canonical_unit = ''
        mod.append(o)
    return mod


def perturb_timestamp_noise(corpus: list[Observation], rate: float, rng: random.Random) -> list[Observation]:
    if rate == 0: return corpus
    mod = []
    for obs in corpus:
        o = copy.copy(obs)
        if rng.random() < rate:
            jitter = timedelta(hours=rng.uniform(-48, 48))
            o.observed_at += jitter
        mod.append(o)
    return mod


def perturb_outliers(corpus: list[Observation], rate: float, rng: random.Random) -> list[Observation]:
    if rate == 0: return corpus
    mod = []
    outliers = {
        'glucose': 5000.0,
        'creatinine': 100.0,
        'systolic_bp': 500.0,
        'HbA1c': 50.0,
        'lesion_diameter': 1000.0
    }
    for obs in corpus:
        o = copy.copy(obs)
        if rng.random() < rate and o.concept_code in outliers:
            o.canonical_value = outliers[o.concept_code]
        mod.append(o)
    return mod


def perturb_abbreviations(corpus: list[Observation], rate: float, rng: random.Random) -> list[Observation]:
    if rate == 0: return corpus
    mod = []
    abbreviations = {
        'creatinine': 'Cr',
        'glucose': 'BG',
        'systolic_bp': 'SBP',
        'HbA1c': 'A1C',
        'lesion_diameter': 'LD'
    }
    for obs in corpus:
        o = copy.copy(obs)
        if rng.random() < rate and o.concept_code in abbreviations:
            o.concept_code = abbreviations[o.concept_code]
        mod.append(o)
    return mod


def perturb_duplicates(corpus: list[Observation], rate: float, rng: random.Random) -> list[Observation]:
    if rate == 0: return corpus
    mod = [copy.copy(obs) for obs in corpus]
    to_dup = [copy.copy(obs) for obs in corpus if rng.random() < rate]
    mod.extend(to_dup)
    return mod


def perturb_ambiguous(corpus: list[Observation], rate: float, rng: random.Random) -> list[Observation]:
    if rate == 0: return corpus
    mod = []
    mapping = {
        'creatinine': 'renal_marker',
        'glucose': 'metabolic_panel'
    }
    for obs in corpus:
        o = copy.copy(obs)
        if rng.random() < rate and o.concept_code in mapping:
            o.concept_code = mapping[o.concept_code]
        mod.append(o)
    return mod


def _evaluate_perturbation(args):
    p_name, p_func, rates, base_corpus, base_queries, embeddings = args
    row_results = {}
    row_str = f"{p_name:<25} |"
    for r in rates:
        rng = random.Random(84)
        mod_corpus = p_func(base_corpus, r / 100.0, rng)
        res = evaluate_method("hybrid_csad_dsw", base_queries, mod_corpus, embeddings, fast_mode=True)
        bsa = res["bsa"]
        row_results[str(r)] = bsa
        row_str += f" {bsa:>6.4f} |"
    return p_name, row_results, row_str


def main():
    print("Loading base corpus and queries...")
    base_corpus = load_base_corpus()
    base_queries = load_base_queries()
    
    print("Loading embeddings...")
    embeddings = load_embeddings()
    
    rates = [0, 5, 10, 20, 30]
    
    perturbations = {
        "misspellings": perturb_misspellings,
        "missing_units": perturb_missing_units,
        "timestamp_noise": perturb_timestamp_noise,
        "outlier_values": perturb_outliers,
        "abbreviations": perturb_abbreviations,
        "duplicated_observations": perturb_duplicates,
        "ambiguous_aliases": perturb_ambiguous
    }
    
    results = {}
    
    print("\nStarting robustness evaluation on hybrid_csad_dsw (M6)...")
    header = f"{'Perturbation':<25} | {'0%':>6} | {'5%':>6} | {'10%':>6} | {'20%':>6} | {'30%':>6}"
    print("-" * len(header))
    print(header)
    print("-" * len(header))
    
    with concurrent.futures.ProcessPoolExecutor() as executor:
        args_list = [(p_name, p_func, rates, base_corpus, base_queries, embeddings) 
                     for p_name, p_func in perturbations.items()]
        futures = {executor.submit(_evaluate_perturbation, args): args[0] for args in args_list}
        for future in concurrent.futures.as_completed(futures):
            p_name, row_results, row_str = future.result()
            results[p_name] = row_results
            print(row_str)
            
    print("-" * len(header))
    
    output_data = {
        "perturbation_type": results
    }
    
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_file = RESULTS_DIR / "robustness.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)
        
    print(f"\nRobustness results saved to {out_file}")

if __name__ == "__main__":
    main()
