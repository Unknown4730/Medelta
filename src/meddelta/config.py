"""Central configuration for MedDelta-RAG.

All tunable values live here: seed, score weights, model name, paths, and
numeric tolerances.  The hybrid weights (0.50 / 0.30 / 0.20) are fixed and
must NOT be tuned on the held-out test split.

Formula Reference
─────────────────
CSAD recency:   R_c(Δt) = exp(−Δt / λ_c)
DSW score:      S_c = w_s^(V) · φ_sem + w_r^(V) · R_c(Δt) + w_x^(V) · ψ_ctx
TAR velocity:   β₁ = Σ(tᵢ−t̄)(vᵢ−v̄) / Σ(tᵢ−t̄)²
"""

from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
GENERATED_DIR = DATA_DIR / "generated"
RESULTS_DIR = DATA_DIR / "results"

# ── Reproducibility ───────────────────────────────────────────────
RANDOM_SEED = 42

# ── Corpus generation ─────────────────────────────────────────────
NUM_PATIENTS = 200          # increased for laboratory-grade experiments
OBSERVATIONS_PER_PATIENT = (8, 18)  # wider range for richer trajectories
MIN_QUERIES = 120
DEV_SPLIT_RATIO = 0.30  # 30 % development, 70 % test

# ── Embedding models ──────────────────────────────────────────────
MODEL_NAME = "all-MiniLM-L6-v2"
BIOMED_MODEL_NAME = "dmis-lab/biobert-base-cased-v1.2"  # biomedical dense baseline

# ── Hybrid retrieval weights (FIXED – not tuned on test queries) ──
# Used by M3 (static hybrid baseline)
SEMANTIC_WEIGHT = 0.50
RECENCY_WEIGHT = 0.30
CONTEXT_WEIGHT = 0.20
RECENCY_HALF_LIFE_DAYS = 365  # global static decay for M3

# ── Numeric tolerances ────────────────────────────────────────────
NUMERIC_TOLERANCE = 1e-6
LATENCY_TARGET_MS = 500  # median warm-query target

# ── Formula versioning ────────────────────────────────────────────
FORMULA_VERSION = "2.0.0"  # bumped: CSAD + DSW + TAR

# ── Disclaimer (must appear on every UI screen) ──────────────────
DISCLAIMER = "Research prototype \u2013 synthetic data \u2013 not for clinical use."

# ═══════════════════════════════════════════════════════════════════
# NOVELTY 4 — Concept-Specific Adaptive Decay (CSAD)
# ═══════════════════════════════════════════════════════════════════
#
# Clinical rationale: physiological signals have different temporal
# half-lives.  The decay constant λ_c (in days) controls how fast
# the recency score drops for concept c:
#
#     R_c(Δt) = exp(−Δt / λ_c)
#
# When Δt = λ_c, recency ≈ 0.368 (1/e).
#
# Calibration: constants are set so that the typical EHR observation
# gap (~200 days for labs, ~300+ for imaging) yields a discriminative
# recency score (0.2–0.7 range).  The ratio between the fastest
# (glucose, λ=180) and slowest (lesion, λ=450) concept is 2.5×,
# reflecting clinical re-test frequency differences.

CONCEPT_DECAY_DAYS: dict[str, float] = {
    "glucose":         180.0,   # volatile — quarterly lab monitoring
    "systolic_bp":     240.0,   # moderate — quarterly vitals
    "creatinine":      300.0,   # semi-stable — biannual renal panels
    "HbA1c":           270.0,   # 3-month glycated average, biannual tests
    "lesion_diameter": 450.0,   # slow — annual/biannual imaging
}

# ═══════════════════════════════════════════════════════════════════
# NOVELTY 5 — Trajectory-Aware Retrieval (TAR)
# ═══════════════════════════════════════════════════════════════════
#
# Given K eligible historical observations {(t_i, v_i)}:
#
# Trend velocity (OLS slope):
#     β₁ = Σ(tᵢ - t̄)(vᵢ - v̄) / Σ(tᵢ - t̄)²
#
# Intercept:
#     β₀ = v̄ - β₁ · t̄
#
# Coefficient of determination:
#     R² = 1 − SS_res / SS_tot
#     SS_res = Σ(vᵢ − β₀ − β₁tᵢ)²
#     SS_tot = Σ(vᵢ − v̄)²
#
# Trend classification (per concept threshold ε_c):
#     |β₁| < ε_c  →  STABLE
#      β₁ ≥ ε_c   →  INCREASING
#      β₁ ≤ −ε_c  →  DECREASING

TRAJECTORY_TOP_K = 5  # number of historical points for trajectory

# Trend-classification thresholds per concept (canonical units / day)
TREND_EPSILON: dict[str, float] = {
    "creatinine":       0.002,   # mg/dL per day
    "glucose":          0.50,    # mg/dL per day
    "lesion_diameter":  0.01,    # mm per day
    "systolic_bp":      0.10,    # mmHg per day
    "HbA1c":            0.001,   # % per day
}

# ═══════════════════════════════════════════════════════════════════
# NOVELTY 6 — Dynamic Score Weighting (DSW)
# ═══════════════════════════════════════════════════════════════════
#
# Instead of fixed (0.50, 0.30, 0.20), the weight vector is selected
# from a volatility-class lookup:
#
#     S_c = w_s^(V) · φ_sem  +  w_r^(V) · R_c(Δt)  +  w_x^(V) · ψ_ctx
#
# where V = volatility_class(c) ∈ {high, medium, low}.
# All weight triplets sum to exactly 1.0.
#
# High-volatility concepts (glucose, systolic_bp):
#     Recency is most important — a stale baseline is clinically useless.
# Medium-volatility concepts (creatinine, HbA1c):
#     Balanced — semantic and recency equally relevant.
# Low-volatility concepts (lesion_diameter):
#     Context (anatomical site) dominates — wrong site is a critical error.

VOLATILITY_CLASS: dict[str, str] = {
    "glucose":          "high",
    "systolic_bp":      "high",
    "creatinine":       "medium",
    "HbA1c":            "medium",
    "lesion_diameter":  "low",
}

# Weight vectors indexed by volatility class: (semantic, recency, context)
DSW_WEIGHTS: dict[str, tuple[float, float, float]] = {
    "high":   (0.35, 0.45, 0.20),  # boost recency
    "medium": (0.45, 0.30, 0.25),  # balanced
    "low":    (0.40, 0.20, 0.40),  # boost context (site)
}

# ── Supported concepts ────────────────────────────────────────────
SUPPORTED_CONCEPTS = {
    "creatinine": {"canonical_unit": "mg/dL", "source_type": "lab"},
    "glucose": {"canonical_unit": "mg/dL", "source_type": "lab"},
    "lesion_diameter": {
        "canonical_unit": "mm",
        "source_type": "measurement",
        "site_required": True,
    },
    "systolic_bp": {"canonical_unit": "mmHg", "source_type": "vital"},
    "HbA1c": {"canonical_unit": "%", "source_type": "lab"},
}

# ── Unit conversion map ───────────────────────────────────────────
# Each entry: (concept, from_unit) → multiplier  (canonical = value × multiplier)
UNIT_CONVERSIONS: dict[tuple[str, str], float] = {
    ("creatinine", "umol/L"): 1.0 / 88.4,
    ("glucose", "mmol/L"): 18.0182,
    ("lesion_diameter", "cm"): 10.0,
}

# ── All experiment methods (ablation study) ───────────────────────
# Internal baselines:
# M1: metadata_only          — structured filter, no semantics
# M2: semantic_only          — cosine similarity (MiniLM), no eligibility gate
# External baselines:
# E1: bm25                   — sparse retrieval (BM25), no eligibility gate
# E2: biobert_semantic        — dense retrieval (BioBERT), no eligibility gate
# Proposed system ablations:
# M3: hybrid                 — eligibility + static weights + static decay
# M4: hybrid_csad            — M3 + concept-specific adaptive decay
# M5: hybrid_dsw             — M3 + dynamic score weighting
# M6: hybrid_csad_dsw        — M3 + CSAD + DSW (full proposed system)
# Component ablations (remove one component from M6):
# A1: no_eligibility         — M6 minus eligibility gate
# A2: no_context             — M6 minus context score (ψ_ctx = 0)
# A3: no_trajectory          — M6 with trajectory disabled (report only)
ALL_METHODS = [
    "metadata_only",
    "semantic_only",
    "bm25",
    "biobert_semantic",
    "hybrid",
    "hybrid_csad",
    "hybrid_dsw",
    "hybrid_csad_dsw",
    "no_eligibility",
    "no_context",
]

# Core methods for the 10-seed statistical run (skip slow ablations)
CORE_METHODS = [
    "metadata_only",
    "semantic_only",
    "bm25",
    "biobert_semantic",
    "hybrid",
    "hybrid_csad",
    "hybrid_dsw",
    "hybrid_csad_dsw",
]
