# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

MedDelta-RAG is a local research prototype that retrieves a clinically comparable historical observation for a synthetic current observation, computes deterministic temporal change, and exposes full source evidence. It supports a controlled comparison of three retrieval methods (metadata-only, semantic-only, hybrid) for an academic paper. It is not a medical device and must never generate clinical advice.

## Commands

```bash
# Install (once)
pip install -e ".[dev]"

# Generate synthetic corpus and benchmark
python scripts/generate_dataset.py

# Run tests
pytest

# Run a single test file
pytest tests/test_normalize.py

# Run all experiments and write result artifacts
python scripts/run_experiments.py

# Start the dashboard
streamlit run app.py
```

These commands are the acceptance criteria; they must all work from a clean environment. If a command is not yet wired up, note it explicitly rather than skipping it.

## Repository structure

```
src/meddelta/
  config.py          # seed, weights, model name, paths — all tunable values live here
  models.py          # typed dataclasses: Observation, BenchmarkQuery, RetrievalResult, DeltaResult, EvidenceManifest
  generate_data.py   # seeded synthetic patients, observations, notes, distractors, dev/test splits
  normalize.py       # concept alias → canonical concept; unit conversion map
  embed.py           # encode note text once, persist as NumPy matrix + record-ID manifest
  eligibility.py     # pure comparability predicate returning (bool, reason_code)
  retrieval.py       # metadata-only (M1), semantic-only (M2), hybrid (M3) strategies
  delta.py           # deterministic absolute/percentage/per-day change; handles all edge cases
  evidence.py        # assembles EvidenceManifest from current record + retrieval + delta results
  evaluation.py      # runs all methods on identical benchmark queries, writes metrics/predictions/latency
scripts/
  generate_dataset.py   # thin CLI entry point → generate_data + embed
  run_experiments.py    # thin CLI entry point → evaluation
app.py               # Streamlit dashboard; research logic stays in src/meddelta, not in callbacks
data/
  generated/         # observations.csv, queries.json, embeddings.npy, corpus_manifest.json
  results/           # metrics.csv, predictions.jsonl, latency.csv, run_manifest.json
tests/
  test_normalize.py, test_eligibility.py, test_retrieval.py, test_delta.py, test_evaluation.py
```

## Architecture

The pipeline has three stages separated by a hard eligibility gate:

**1. Ingest / normalize / embed** — `generate_data.py` produces a reproducible corpus from a configured seed. `normalize.py` maps aliases to canonical concepts and converts units (e.g. umol/L → mg/dL for creatinine). `embed.py` encodes each record's `note_text` once and caches it; the embedding matrix and matching record-ID list are stored as `.npy` files.

**2. Retrieval** — all three methods receive the same current observation + query text + corpus:
- M1 metadata-only: filter by patient, concept, earlier timestamp; pick most-recent.
- M2 semantic-only: filter by patient and earlier timestamp only; rank by cosine similarity (intentionally allows non-comparable candidates as a weak baseline).
- M3 hybrid: **eligibility gate runs first** (patient, concept, unit, timestamp, anatomical site); then rank eligible candidates with `0.50 × semantic + 0.30 × recency + 0.20 × context`. Ties break on latest timestamp, then lexicographic record ID.

Eligibility and ranking are intentionally separated. A high semantic score must never override an incompatible concept, unit, site, or time direction.

Recency score: `exp(-elapsed_days / 365)`. Context score: 1.0 exact / 0.5 partial / 0.0 mismatch (anatomical mismatch is an eligibility failure when site is mandatory).

**3. Delta + evidence** — `delta.py` computes `absolute = c - b`, `percentage = (c-b)/|b| × 100`, `per_day = (c-b)/t`. Zero baseline omits percentage; future/same timestamp rejects the candidate. `evidence.py` packages both source records, canonical values, timestamps, all score components, rejection reasons, and `formula_version` into the manifest shown in the dashboard.

## Key invariants

- **Scope**: synthetic data only; no real patient data, no LLM calls, no diagnosis/treatment output, no cloud, no authentication.
- **Determinism**: random seed, score weights, model name, and tie-breaking rules are config values. Corpus hash must be stable across repeated generation with the same seed.
- **Eligibility before ranking**: enforced in `eligibility.py` before `retrieval.py` scores anything.
- **No test-set tuning**: score weights (`0.50 / 0.30 / 0.20`) are fixed; the held-out test split must not influence them.
- **Traceability**: every displayed delta must show both source record IDs. The dashboard must carry the permanent text `"Research prototype – synthetic data – not for clinical use."`.
- **Numeric tolerances**: normalized values exact to `1e-6`; percentage and velocity rounded only for display.

## Status / rejection codes

`OK`, `NO_COMPARABLE_BASELINE`, `PATIENT_MISMATCH`, `NOT_HISTORICAL`, `CONCEPT_MISMATCH`, `INCOMPATIBLE_UNIT`, `ANATOMICAL_SITE_MISMATCH`, `INSUFFICIENT_CONTEXT`, `INVALID_NUMERIC_VALUE`, `PERCENTAGE_UNDEFINED`, `EMBEDDING_UNAVAILABLE`

## Supported concepts and conversions

| Concept | Canonical unit | Conversions |
|---|---|---|
| creatinine | mg/dL | umol/L ÷ 88.4 |
| glucose | mg/dL | mmol/L × 18.0182 |
| lesion_diameter | mm | cm × 10 (anatomical site required) |
| systolic_bp | mmHg | — |
| HbA1c | % | — |

Do not add a conversion without a round-trip or known-value test.

## Evaluation metrics

Baseline Selection Accuracy, Valid Pair Rate, Top-3 Hit Rate, MRR, Delta Exact Match, Evidence Completeness, median/p95/min/max warm-query latency. Cold model-load latency is reported separately.

## Stack

Python 3.11, Streamlit, pandas, Plotly, NumPy, sentence-transformers, pytest. If the transformer model cannot be installed, use a deterministic TF-IDF fallback and record the actual encoder in all run manifests.
