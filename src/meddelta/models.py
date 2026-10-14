"""Typed data models for MedDelta-RAG.

Every public dataclass mirrors the schema tables in
``docs/05_DATA_AND_API_SPECIFICATION.md``.
"""

from __future__ import annotations

import dataclasses as dc
from datetime import datetime
from typing import Optional


# ── Core data records ──────────────────────────────────────────────


@dc.dataclass
class Observation:
    """A single clinical observation record."""

    record_id: str
    patient_id: str
    observed_at: datetime
    concept_code: str
    concept_label: str
    value: float
    unit: str
    canonical_value: float
    canonical_unit: str
    condition_context: Optional[str] = None
    anatomical_site: Optional[str] = None
    note_text: str = ""
    source_type: str = "lab"  # lab | vital | measurement
    is_synthetic: bool = True


@dc.dataclass
class BenchmarkQuery:
    """A benchmark evaluation query with known ground truth."""

    query_id: str
    current_record_id: str
    query_text: str
    expected_baseline_id: Optional[str]
    expected_status: str  # "OK" or a rejection code
    distractor_ids: list[str] = dc.field(default_factory=list)
    split: str = "test"  # development | test
    generator_version: str = "1.0.0"


# ── Eligibility ────────────────────────────────────────────────────


@dc.dataclass(frozen=True)
class EligibilityResult:
    """Result of the comparability predicate."""

    is_eligible: bool
    reason_code: str  # "OK" or one of the rejection codes


# ── Retrieval ──────────────────────────────────────────────────────


@dc.dataclass
class RankedCandidate:
    """A single candidate in the retrieval ranking."""

    record_id: str
    observation: Observation
    rank: int
    score: float
    score_components: dict = dc.field(default_factory=dict)
    eligibility: Optional[EligibilityResult] = None


@dc.dataclass
class RetrievalResult:
    """Result from a retrieval strategy."""

    method: str  # "metadata_only" | "semantic_only" | "hybrid"
    query_id: str
    ranked_candidates: list[RankedCandidate] = dc.field(default_factory=list)
    status: str = "OK"
    scores_breakdown: dict = dc.field(default_factory=dict)


# ── Delta computation ──────────────────────────────────────────────


@dc.dataclass
class DeltaResult:
    """Deterministic temporal-change computation."""

    absolute_change: float
    percentage_change: Optional[float]  # None when baseline is zero
    change_per_day: float
    elapsed_days: float
    status: str = "OK"  # "OK" | "PERCENTAGE_UNDEFINED" | rejection code


# ── Evidence manifest ──────────────────────────────────────────────


@dc.dataclass
class EvidenceManifest:
    """Complete evidence package for a displayed delta."""

    current_record: Observation
    baseline_record: Optional[Observation]
    retrieval_result: RetrievalResult
    delta_result: Optional[DeltaResult]
    formula_version: str
    warnings: list[str] = dc.field(default_factory=list)
    trajectory: Optional["TrajectoryResult"] = None


# ── Trajectory computation (TAR) ──────────────────────────────────


@dc.dataclass
class TrajectoryResult:
    """Temporal trend computed via OLS linear regression over K baselines.

    Formula:
        β₁ = Σ(tᵢ − t̄)(vᵢ − v̄) / Σ(tᵢ − t̄)²
        R² = 1 − SS_res / SS_tot
    """

    slope: float                   # β₁ (canonical_unit / day)
    intercept: float               # β₀
    r_squared: float               # coefficient of determination
    trend: str                     # INCREASING | DECREASING | STABLE
    num_points: int                # K (number of historical points used)
    point_record_ids: list[str]    # record_ids forming the trajectory
    elapsed_span_days: float       # time span from oldest to newest point
    status: str = "OK"             # OK | INSUFFICIENT_DATA | ZERO_VARIANCE

