<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.11+"/>
  <img src="https://img.shields.io/badge/Streamlit-Dashboard-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white" alt="Streamlit"/>
  <img src="https://img.shields.io/badge/Research-Prototype-4CAF50?style=for-the-badge" alt="Research Prototype"/>
  <img src="https://img.shields.io/badge/Data-Synthetic%20Only-FFA500?style=for-the-badge" alt="Synthetic Data"/>
  <img src="https://img.shields.io/badge/License-Proprietary-red?style=for-the-badge" alt="License"/>
</p>

<h1 align="center">🔬 MedDelta-RAG</h1>
<h3 align="center">Comparability-First Retrieval for Evidence-Linked Temporal Change Detection</h3>

<p align="center">
  <em>A research prototype demonstrating that <strong>comparability-first hybrid retrieval</strong> selects superior longitudinal baselines compared to metadata-only or semantic-only strategies — with every displayed delta source-linked, deterministic, and fully reproducible.</em>
</p>

---

> ⚠️ **IMPORTANT DISCLAIMER**
> MedDelta-RAG is a **research prototype** operating exclusively on **synthetic, de-identified data**. It is **not a medical device**, not validated for clinical use, and must **never** be used for diagnosis, treatment decisions, or any clinical workflow. All observations are procedurally generated and bear no relationship to any real patient.

---

## 📋 Table of Contents

1. [What Is MedDelta-RAG?](#what-is-meddelta-rag)
2. [Research Question](#research-question)
3. [Key Contributions](#key-contributions)
4. [Architecture Overview](#architecture-overview)
5. [Retrieval Methods Evaluated](#retrieval-methods-evaluated)
6. [Project Structure](#project-structure)
7. [Quick Start](#quick-start)
8. [Running the Dashboard](#running-the-dashboard)
9. [Running Experiments](#running-experiments)
10. [Documentation](#documentation)
11. [Testing](#testing)
12. [Reproducibility](#reproducibility)
13. [Limitations & Future Work](#limitations--future-work)
14. [License](#license)

---

## What Is MedDelta-RAG?

Clinical decision support often requires answering the question:

> *"How has this patient's measurement changed since the last comparable observation?"*

This sounds simple, but it is deceptively hard. A naïve retrieval system might compare a creatinine reading against a glucose reading from the same patient (wrong concept), or compare a lesion diameter measured at the left lung against one measured at the right lung (wrong anatomical site), or pick a reading that is semantically similar in notes but clinically irrelevant.

**MedDelta-RAG** introduces a **comparability-first hybrid retrieval** pipeline that enforces clinical eligibility constraints *before* semantic ranking, ensuring every retrieved baseline is a valid comparator. It then computes an exact, source-linked delta — not an LLM-generated estimate.

The system is an **architecture and methodology paper** prototype. Its evaluation is explicitly positioned as a controlled verification of the retrieval mechanics, not a clinical validation study.

---

## Research Question

> **Does comparability-first hybrid retrieval (eligibility gate + adaptive decay + dynamic score weighting) select significantly better longitudinal baselines than metadata-only, semantic-only, or static hybrid retrieval?**

### Hypotheses

| ID | Hypothesis |
|---|---|
| **H1** | Eligibility-gated retrieval significantly improves baseline selection accuracy over standard semantic retrieval |
| **H2** | Concept-Specific Adaptive Decay (CSAD) improves temporal relevance over static decay |
| **H3** | Dynamic Score Weighting (DSW) improves longitudinal ranking over fixed weights |
| **H4** | The complete architecture (M6: Hybrid + CSAD + DSW) significantly outperforms every individual ablation |

---

## Key Contributions

MedDelta-RAG makes **six architectural contributions**:

1. **Comparability Predicate** — A structured eligibility gate that rejects clinically incomparable candidates (wrong concept, wrong site, future observations) before any embedding computation occurs.

2. **Evidence-Linked Delta** — Every temporal change displayed in the UI is computed from exactly two dated source records using transparent arithmetic, making it fully auditable.

3. **Evidence Manifest** — A structured provenance package bundled with every displayed delta, containing source record IDs, formula version, scores, and warnings.

4. **Concept-Specific Adaptive Decay (CSAD)** — Instead of a single global recency decay constant, each clinical concept has its own half-life `λ_c`, calibrated to its clinical re-test frequency:

   ```
   R_c(Δt) = exp(−Δt / λ_c)
   ```

5. **Trajectory-Aware Retrieval (TAR)** — An OLS linear regression over the K most recent historical observations computes the temporal trend (velocity `β₁` and `R²`), enriching the evidence manifest with trajectory context.

6. **Dynamic Score Weighting (DSW)** — Instead of fixed hybrid weights `(0.50, 0.30, 0.20)`, the weighting vector is selected from a volatility-class lookup per concept, so high-volatility signals (glucose, BP) prioritize recency while low-volatility signals (lesion size) prioritize anatomical context.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         MedDelta-RAG Pipeline                        │
│                                                                       │
│   Current Observation                                                 │
│         │                                                             │
│         ▼                                                             │
│  ┌─────────────────┐    REJECT (incompatible concept, site,          │
│  │ Eligibility Gate│ ──────────────────────────────────────────►  ✗  │
│  └────────┬────────┘    or future timestamp)                         │
│           │ ELIGIBLE candidates only                                  │
│           ▼                                                           │
│  ┌─────────────────────────────────────────────────────┐             │
│  │              Hybrid Scoring (DSW)                    │             │
│  │  S_c = w_s^(V)·φ_sem + w_r^(V)·R_c(Δt) + w_x^(V)·ψ_ctx │        │
│  │           ↑ CSAD decay per concept                   │             │
│  └──────────────────────────┬──────────────────────────┘             │
│                             │ top-k ranked candidates                 │
│                             ▼                                         │
│               ┌────────────────────────┐                             │
│               │   Best Baseline        │                             │
│               └──────────┬─────────────┘                             │
│                          │                                            │
│         ┌────────────────┼────────────────────────┐                  │
│         ▼                ▼                         ▼                  │
│  ┌────────────┐  ┌──────────────┐  ┌──────────────────────┐         │
│  │Delta Calc. │  │ TAR (Trend)  │  │  Evidence Manifest   │         │
│  │ Abs / % / │  │  OLS β₁, R² │  │  (source-linked pkg) │         │
│  │ per-day   │  └──────────────┘  └──────────────────────┘         │
│  └────────────┘                                                       │
│         │                                                             │
│         ▼                                                             │
│    Streamlit Dashboard (evidence panel + timeline)                    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Retrieval Methods Evaluated

The ablation study evaluates **10 methods** against the same benchmark corpus:

| ID | Method | Description |
|---|---|---|
| **M1** | `metadata_only` | Structured filter only — no semantic ranking |
| **M2** | `semantic_only` | Cosine similarity (MiniLM-L6-v2) — no eligibility gate |
| **E1** | `bm25` | Sparse BM25 retrieval — no eligibility gate |
| **E2** | `biobert_semantic` | Dense BioBERT retrieval — no eligibility gate |
| **M3** | `hybrid` | Eligibility + static weights `(0.50, 0.30, 0.20)` + global decay |
| **M4** | `hybrid_csad` | M3 + Concept-Specific Adaptive Decay |
| **M5** | `hybrid_dsw` | M3 + Dynamic Score Weighting |
| **M6** | `hybrid_csad_dsw` | **Full proposed system**: M3 + CSAD + DSW |
| **A1** | `no_eligibility` | M6 minus eligibility gate (ablation) |
| **A2** | `no_context` | M6 minus context score `ψ_ctx = 0` (ablation) |

---

## Project Structure

```
meddelta-rag/
│
├── src/meddelta/              # Core research library
│   ├── config.py              # All tunable constants (seed, weights, paths)
│   ├── models.py              # Typed dataclasses (Observation, DeltaResult, …)
│   ├── eligibility.py         # Comparability predicate (the eligibility gate)
│   ├── retrieval.py           # All retrieval strategies (M1–M6, A1–A2)
│   ├── delta.py               # Deterministic delta computation
│   ├── embed.py               # Embedding build & load (sentence-transformers)
│   ├── normalize.py           # Unit canonicalization
│   ├── evidence.py            # Evidence manifest builder
│   ├── evaluation.py          # Full evaluation pipeline (BSA, MRR, HR@k, …)
│   └── generate_data.py       # Synthetic corpus generator
│
├── scripts/
│   ├── generate_dataset.py    # Step 1: Generate corpus + embeddings
│   ├── run_experiments.py     # Step 2: Run full ablation evaluation
│   ├── run_statistical.py     # Step 3: Statistical significance tests
│   ├── run_robustness.py      # Step 4: Robustness benchmarks
│   ├── run_scalability.py     # Step 5: Scalability benchmarks
│   ├── run_sensitivity.py     # Step 6: Hyperparameter sensitivity
│   └── run_error_analysis.py  # Step 7: Qualitative error analysis
│
├── tests/                     # pytest unit tests
│   ├── test_delta.py
│   ├── test_eligibility.py
│   ├── test_evaluation.py
│   ├── test_normalize.py
│   └── test_retrieval.py
│
├── docs/                      # Full research documentation
│   ├── 01_RESEARCH_SPECIFICATION.md
│   ├── 02_PROJECT_SPECIFICATION.md
│   ├── 03_ARCHITECTURE_AND_WORKFLOW.md
│   ├── 04_PROJECT_LIFECYCLE.md
│   ├── 05_DATA_AND_API_SPECIFICATION.md
│   ├── 06_EVALUATION_PLAN.md
│   ├── 07_PAPER_OUTLINE.md
│   ├── 08_AI_IMPLEMENTATION_PROMPT.md
│   └── 09_INITIALIZATION_CHECKLIST.md
│
├── data/
│   ├── generated/             # Generated by scripts — NOT committed to git
│   └── results/               # Experiment outputs — NOT committed to git
│
├── app.py                     # Streamlit dashboard entry point
├── pyproject.toml             # Project metadata & dependencies
├── AGENTS.md                  # Research engineering governance
├── CLAUDE.md                  # AI assistant research constitution
└── LICENSE                    # Proprietary copyright
```

---

## Quick Start

### Prerequisites

- Python **3.11** or higher
- A working internet connection on first run (to download the embedding model ~80 MB)

### Installation

```bash
# Clone the repository
git clone https://github.com/<your-username>/meddelta-rag.git
cd meddelta-rag

# Create and activate a virtual environment
python -m venv .venv

# On Windows
.venv\Scripts\activate

# On macOS / Linux
source .venv/bin/activate

# Install all dependencies
pip install -e ".[dev]"
```

### Step 1 — Generate the Synthetic Dataset

```bash
python scripts/generate_dataset.py
```

This creates:
- `data/generated/observations.csv` — 200 synthetic patients × 8–18 observations each
- `data/generated/queries.json` — benchmark queries with known ground truth
- `data/generated/embeddings.npy` + `embedding_ids.json` — persisted MiniLM embeddings

All generation is seeded with `RANDOM_SEED = 42` for full reproducibility.

---

## Running the Dashboard

```bash
streamlit run app.py
```

The dashboard opens in your browser. Use the sidebar to:
- Select a **retrieval method** (M1 — Metadata-only, M2 — Semantic-only, M3 — Hybrid)
- Select a **patient** and a **current observation**
- Inspect the retrieved baseline, delta results, evidence manifest, and patient timeline

---

## Running Experiments

The full research pipeline runs in seven steps:

```bash
# Step 1: Generate corpus & embeddings (if not done yet)
python scripts/generate_dataset.py

# Step 2: Run full ablation evaluation (all 10 methods)
python scripts/run_experiments.py

# Step 3: Statistical significance tests (Wilcoxon + Bonferroni + Cliff's δ)
python scripts/run_statistical.py

# Step 4: Robustness benchmarks (corpus-size sensitivity)
python scripts/run_robustness.py

# Step 5: Scalability benchmarks (query-latency profiling)
python scripts/run_scalability.py

# Step 6: Hyperparameter sensitivity (weight grid search)
python scripts/run_sensitivity.py

# Step 7: Qualitative error analysis
python scripts/run_error_analysis.py
```

All results are written to `data/results/`.

---

## Documentation

The `docs/` directory contains the full research and engineering documentation:

| Document | Description |
|---|---|
| [01 — Research Specification](docs/01_RESEARCH_SPECIFICATION.md) | Research question, hypotheses, variables, falsification criteria |
| [02 — Project Specification](docs/02_PROJECT_SPECIFICATION.md) | Scope, constraints, and non-goals |
| [03 — Architecture & Workflow](docs/03_ARCHITECTURE_AND_WORKFLOW.md) | System design, data flow, component responsibilities |
| [04 — Project Lifecycle](docs/04_PROJECT_LIFECYCLE.md) | Development phases and milestones |
| [05 — Data & API Specification](docs/05_DATA_AND_API_SPECIFICATION.md) | Schema definitions for all dataclasses |
| [06 — Evaluation Plan](docs/06_EVALUATION_PLAN.md) | Metrics, baselines, statistical tests, and evaluation protocol |
| [07 — Paper Outline](docs/07_PAPER_OUTLINE.md) | Structure for the conference paper |
| [08 — AI Implementation Prompt](docs/08_AI_IMPLEMENTATION_PROMPT.md) | AI assistant prompting guide used during development |
| [09 — Initialization Checklist](docs/09_INITIALIZATION_CHECKLIST.md) | Repository setup checklist |

---

## Testing

```bash
# Run all unit tests
pytest

# With verbose output
pytest -v

# Run a specific test module
pytest tests/test_eligibility.py -v
```

The test suite covers:
- `test_eligibility.py` — Comparability predicate correctness
- `test_delta.py` — Delta computation edge cases (zero baseline, date ordering)
- `test_retrieval.py` — Retrieval strategy contracts
- `test_evaluation.py` — Metric computation correctness
- `test_normalize.py` — Unit canonicalization

---

## Reproducibility

This project is designed for full reproducibility:

| Parameter | Value |
|---|---|
| Random seed | `42` (fixed in `config.py`) |
| Python version | 3.11 |
| Embedding model | `all-MiniLM-L6-v2` |
| Corpus size | 200 patients × (8–18 obs each) |
| Dev / test split | 30 % / 70 % |
| Hybrid weights (M3) | Fixed at `(0.50, 0.30, 0.20)` — **not tuned on test data** |
| Statistical test | Wilcoxon signed-rank (paired), Bonferroni correction, Cliff's δ effect size |

All weights are fixed before any test-split evaluation. No hyperparameter tuning was performed on the held-out test set.

---

## Limitations & Future Work

### Current Limitations

| Limitation | Detail |
|---|---|
| **Synthetic data only** | All observations are procedurally generated. Generalization to real EHRs is not demonstrated. |
| **Five concepts** | The prototype covers glucose, creatinine, HbA1c, systolic BP, and lesion diameter only. |
| **No LLM generation** | The system computes arithmetic deltas — it does not generate clinical text. |
| **No clinical validation** | Statistical significance on synthetic benchmarks ≠ clinical utility. |
| **Local deployment only** | No authentication, no multi-user, no cloud infrastructure. |

### Future Work

- Clinical validation on MIMIC-IV or similar real-world EHR datasets
- Extension to additional clinical concepts and lab panels
- Integration with HL7 FHIR APIs
- Regulatory pathway analysis (FDA SaMD considerations)
- Multi-modal support (imaging measurements)

---

## Evaluation Metrics

| Metric | Abbreviation | Description |
|---|---|---|
| Baseline Selection Accuracy | **BSA** | Exact match between predicted and ground-truth baseline |
| Mean Reciprocal Rank | **MRR** | Average reciprocal rank of the correct baseline |
| Hit Rate @ k | **HR@k** | Fraction of queries where correct baseline appears in top-k |
| Delta Exact Match | **DEM** | Whether the computed delta matches the expected delta |
| Valid Prediction Rate | **VPR** | Fraction of queries that return any valid baseline |

---

## License

Copyright © 2026 Prathamesh P Koli. All rights reserved.

This software is proprietary. See the [LICENSE](LICENSE) file for full terms.

---

<p align="center">
  Made with ❤️ for reproducible, evidence-linked clinical AI research
</p>
