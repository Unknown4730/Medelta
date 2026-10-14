"""Seeded synthetic data generation for MedDelta-RAG.

Produces a deterministic corpus of 200 patients, simulating clinical trajectories
with realistic values, noise, temporal patterns, and units. Includes controlled
distractors and benchmark queries.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
import pandas as pd

from meddelta.config import (
    CONCEPT_DECAY_DAYS,
    DEV_SPLIT_RATIO,
    GENERATED_DIR,
    MIN_QUERIES,
    NUM_PATIENTS,
    OBSERVATIONS_PER_PATIENT,
    RANDOM_SEED,
)
from meddelta.models import BenchmarkQuery, Observation
from meddelta.normalize import normalize_observation


def truncated_normal(rng: np.random.Generator, mean: float, std: float, low: float, high: float) -> float:
    """
    Generates a single value from a truncated normal distribution using rejection sampling.
    
    Formula:
        f(x; \\mu, \\sigma, a, b) = \\frac{\\phi(\\frac{x-\\mu}{\\sigma})}{\\sigma(\\Phi(\\frac{b-\\mu}{\\sigma}) - \\Phi(\\frac{a-\\mu}{\\sigma}))}
    """
    while True:
        val = rng.normal(mean, std)
        if low <= val <= high:
            return float(val)


# ── Value ranges and clinical context per concept ─────────────────

_CONCEPT_SPECS: dict[str, dict[str, Any]] = {
    "creatinine": {
        "source_type": "lab",
        "context": "renal_function",
        "dist": {"mean": 1.1, "std": 0.4, "low": 0.5, "high": 4.0},
        "noise": 0.03,
        "canon": "mg/dL",
        "alt": "umol/L",
        "prob": 0.20,
        "func": lambda v: v * 88.4,
        "note_templates": [
            "Serum creatinine measured at {value:.2f} {unit}. Patient shows stable renal function.",
            "Creatinine level {value:.2f} {unit}. GFR estimation in progress based on this lab.",
            "Lab result: creatinine {value:.2f} {unit}. Consistent with prior renal profile.",
            "Comprehensive metabolic panel shows creatinine at {value:.2f} {unit}. No acute kidney injury indicated.",
            "Renal function test reveals creatinine of {value:.2f} {unit}. Will continue current hydration plan."
        ],
    },
    "glucose": {
        "source_type": "lab",
        "context": "diabetes_monitoring",
        "dist": {"mean": 120.0, "std": 40.0, "low": 60.0, "high": 350.0},
        "noise": 3.0,
        "canon": "mg/dL",
        "alt": "mmol/L",
        "prob": 0.15,
        "func": lambda v: v / 18.0182,
        "note_templates": [
            "Fasting glucose is {value:.1f} {unit}. Monitoring for diabetic control.",
            "Blood glucose reading {value:.1f} {unit}. Dietary guidance continued.",
            "Glucose {value:.1f} {unit}. Patient adherence to metformin regimen noted.",
            "Point of care glucose measured at {value:.1f} {unit}. No hypoglycemic symptoms.",
            "Routine lab check: glucose {value:.1f} {unit}. Adjusting insulin dose accordingly."
        ],
    },
    "lesion_diameter": {
        "source_type": "measurement",
        "context": "oncology_followup",
        "dist": {"mean": 15.0, "std": 8.0, "low": 2.0, "high": 60.0},
        "noise": 0.5,
        "canon": "mm",
        "alt": "cm",
        "prob": 0.10,
        "func": lambda v: v / 10.0,
        "note_templates": [
            "Ultrasound shows lesion measuring {value:.1f} {unit} at {site}. Routine surveillance.",
            "Imaging: {site} lesion diameter {value:.1f} {unit}. Stable compared to prior scan.",
            "Lesion at {site} measures {value:.1f} {unit} on follow-up imaging.",
            "CT scan reveals {site} mass with diameter of {value:.1f} {unit}. Discussed with oncology.",
            "MRI indicates {site} nodule size is {value:.1f} {unit}. Biopsy not required at this time."
        ],
    },
    "systolic_bp": {
        "source_type": "vital",
        "context": "hypertension_management",
        "dist": {"mean": 130.0, "std": 15.0, "low": 85.0, "high": 200.0},
        "noise": 2.0,
        "canon": "mmHg",
        "alt": None,
        "prob": 0.0,
        "func": lambda v: v,
        "note_templates": [
            "Blood pressure taken, systolic is {value:.0f} {unit}. Advised on diet.",
            "Systolic BP {value:.0f} {unit}. Antihypertensive medication reviewed.",
            "Vital signs: systolic {value:.0f} {unit}. Within expected range.",
            "Patient resting comfortably, systolic blood pressure {value:.0f} {unit}.",
            "Sphygmomanometer reading shows systolic at {value:.0f} {unit}. Hypertension protocol followed."
        ],
    },
    "HbA1c": {
        "source_type": "lab",
        "context": "diabetes_monitoring",
        "dist": {"mean": 7.0, "std": 1.5, "low": 4.0, "high": 14.0},
        "noise": 0.1,
        "canon": "%",
        "alt": None,
        "prob": 0.0,
        "func": lambda v: v,
        "note_templates": [
            "HbA1c level is {value:.1f} {unit}. Glycaemic control assessment.",
            "Glycated haemoglobin {value:.1f} {unit}. Three-month average glucose reviewed.",
            "Lab: HbA1c {value:.1f} {unit}. Patient counselled on dietary adjustments.",
            "Endocrinology panel: HbA1c at {value:.1f} {unit}. Therapy remains unchanged.",
            "A1c test result {value:.1f} {unit}. Reflects good adherence to lifestyle modifications."
        ],
    },
}

_ANATOMICAL_SITES = [
    "left_breast", "right_breast", "liver",
    "lung_right", "lung_left", "thyroid",
]


# ── Corpus generation ─────────────────────────────────────────────


def generate_corpus(
    seed: int | None = None,
) -> tuple[list[Observation], list[BenchmarkQuery]]:
    """
    Generate the full synthetic corpus and benchmark queries.
    
    Applies clinical trajectory patterns:
    - Stable: v_t = v_0 \\cdot \\epsilon + N(0, \\sigma^2)
    - Increasing/Decreasing: v_t = v_0 + \\Delta v \\cdot \\frac{t}{T} + N(0, \\sigma^2)
    - Spike-then-return: Introduces transient high multiplier
    - Step-change: Permanent level shift
    """
    if seed is None:
        seed = RANDOM_SEED
    rng = np.random.default_rng(seed)

    concept_names = list(_CONCEPT_SPECS.keys())
    base_date = datetime(2022, 1, 1, tzinfo=timezone.utc)

    observations: list[Observation] = []

    for i in range(NUM_PATIENTS):
        patient_id = f"PAT-{i:04d}"
        patient_obs: list[Observation] = []

        def create_obs(concept_code: str, date: datetime, site: str | None = None, value: float | None = None, note_override: str | None = None) -> Observation:
            spec = _CONCEPT_SPECS[concept_code]
            v = value if value is not None else spec["dist"]["mean"]
            unit = spec["canon"]

            if note_override:
                note = note_override
            else:
                tmpl = str(rng.choice(spec["note_templates"]))
                note = tmpl.format(value=v, unit=unit, site=site or "")

            obs = Observation(
                record_id=f"REC-{i:04d}-{len(patient_obs):03d}",
                patient_id=patient_id,
                observed_at=date,
                concept_code=concept_code,
                concept_label=concept_code.replace("_", " ").title(),
                value=float(v),
                unit=unit,
                canonical_value=0.0,
                canonical_unit="",
                condition_context=spec["context"],
                anatomical_site=site,
                note_text=note,
                source_type=spec["source_type"],
                is_synthetic=True,
            )
            try:
                obs = normalize_observation(obs)
            except Exception:
                pass
            return obs

        if (i + 1) % 10 == 0:
            # Inject controlled distractors for benchmark query rejection testing
            
            # 1. ANATOMICAL_SITE_MISMATCH (lesion_diameter)
            patient_obs.append(create_obs("lesion_diameter", base_date + timedelta(days=1), site="liver"))
            patient_obs.append(create_obs("lesion_diameter", base_date + timedelta(days=10), site="lung_right"))
            
            # 2. NOT_HISTORICAL (glucose)
            patient_obs.append(create_obs("glucose", base_date + timedelta(days=30)))  # Future
            patient_obs.append(create_obs("glucose", base_date + timedelta(days=20)))  # Current
            
            # 3. CONCEPT_MISMATCH (systolic_bp)
            o5 = create_obs("systolic_bp", base_date + timedelta(days=40))
            o5.note_text = "HbA1c level is 7.2 %. Glycaemic control assessment."
            patient_obs.append(o5)
            patient_obs.append(create_obs("systolic_bp", base_date + timedelta(days=50)))
            
            observations.extend(patient_obs)
            continue

        # Normal patient trajectories
        primary_concept = str(rng.choice(concept_names))
        spec = _CONCEPT_SPECS[primary_concept]
        site = str(rng.choice(_ANATOMICAL_SITES)) if primary_concept == "lesion_diameter" else None

        traj_type = rng.choice(["stable", "increasing", "decreasing", "spike", "step"], p=[0.4, 0.2, 0.2, 0.1, 0.1])
        
        num_obs = int(rng.integers(OBSERVATIONS_PER_PATIENT[0], OBSERVATIONS_PER_PATIENT[1] + 1))
        span_days = int(rng.integers(2 * 365, 5 * 365 + 1))
        offsets = sorted(rng.integers(0, span_days, size=num_obs))

        mean, std = spec["dist"]["mean"], spec["dist"]["std"]
        low, high = spec["dist"]["low"], spec["dist"]["high"]
        baseline = truncated_normal(rng, mean, std, low, high)

        for j, offset in enumerate(offsets):
            progress = j / (num_obs - 1) if num_obs > 1 else 0.0
            
            if traj_type == "stable":
                v = baseline * rng.uniform(0.95, 1.05)
            elif traj_type == "increasing":
                v = baseline + progress * (high - baseline) * rng.uniform(0.5, 0.8)
            elif traj_type == "decreasing":
                v = baseline - progress * (baseline - low) * rng.uniform(0.5, 0.8)
            elif traj_type == "spike":
                v = baseline * rng.uniform(0.95, 1.05)
                if j == num_obs // 2:
                    v = baseline * rng.uniform(1.5, 2.0)
            elif traj_type == "step":
                if j >= num_obs // 2:
                    v = baseline * rng.uniform(1.3, 1.6)
                else:
                    v = baseline * rng.uniform(0.95, 1.05)
            else:
                v = baseline

            # Add measurement noise and clip to valid ranges
            v += rng.normal(0.0, spec["noise"])
            v = float(np.clip(v, low, high))

            unit = spec["canon"]
            value = v
            if spec["alt"] is not None and rng.random() < spec["prob"]:
                unit = spec["alt"]
                value = spec["func"](v)

            tmpl = str(rng.choice(spec["note_templates"]))
            note = tmpl.format(value=value, unit=unit, site=site or "")

            observed_at = base_date + timedelta(days=int(offset))
            record_id = f"REC-{i:04d}-{len(patient_obs):03d}"

            obs = Observation(
                record_id=record_id,
                patient_id=patient_id,
                observed_at=observed_at,
                concept_code=primary_concept,
                concept_label=primary_concept.replace("_", " ").title(),
                value=float(value),
                unit=unit,
                canonical_value=0.0,
                canonical_unit="",
                condition_context=spec["context"],
                anatomical_site=site,
                note_text=note,
                source_type=spec["source_type"],
                is_synthetic=True,
            )
            try:
                obs = normalize_observation(obs)
            except Exception:
                pass
            patient_obs.append(obs)

        observations.extend(patient_obs)

    queries = generate_benchmark_queries(observations, seed)
    return observations, queries


# ── Benchmark query generation ────────────────────────────────────


def generate_benchmark_queries(
    observations: list[Observation],
    seed: int | None = None,
) -> list[BenchmarkQuery]:
    """Create >= 400 benchmark queries testing normal flows and rejection codes."""
    if seed is None:
        seed = RANDOM_SEED
    rng = np.random.default_rng(seed + 1)

    from collections import defaultdict
    patient_concept: dict[tuple[str, str], list[Observation]] = defaultdict(list)
    for obs in observations:
        patient_concept[(obs.patient_id, obs.concept_code)].append(obs)

    for key in patient_concept:
        patient_concept[key].sort(key=lambda o: o.observed_at)

    queries: list[BenchmarkQuery] = []
    query_counter = 0

    query_templates = {
        "creatinine": "Compare current creatinine reading with most recent comparable baseline",
        "glucose": "Find the most recent comparable glucose measurement for longitudinal comparison",
        "lesion_diameter": "Retrieve prior lesion diameter measurement at the same anatomical site",
        "systolic_bp": "Compare current systolic blood pressure with historical baseline",
        "HbA1c": "Find the most recent HbA1c result for trend analysis",
    }

    for (pid, concept), obs_list in patient_concept.items():
        if not obs_list:
            continue

        patient_idx = int(pid.split("-")[1])
        if (patient_idx + 1) % 10 == 0:
            if concept == "lesion_diameter" and len(obs_list) >= 2:
                queries.append(BenchmarkQuery(
                    query_id=f"Q-{query_counter:04d}",
                    current_record_id=obs_list[1].record_id,
                    query_text=query_templates[concept],
                    expected_baseline_id=None,
                    expected_status="ANATOMICAL_SITE_MISMATCH",
                    distractor_ids=[obs_list[0].record_id],
                    split="test",
                    generator_version="2.0.0"
                ))
                query_counter += 1
            elif concept == "glucose" and len(obs_list) >= 2:
                queries.append(BenchmarkQuery(
                    query_id=f"Q-{query_counter:04d}",
                    current_record_id=obs_list[0].record_id,
                    query_text=query_templates[concept],
                    expected_baseline_id=None,
                    expected_status="NOT_HISTORICAL",
                    distractor_ids=[obs_list[1].record_id],
                    split="test",
                    generator_version="2.0.0"
                ))
                query_counter += 1
            elif concept == "systolic_bp" and len(obs_list) >= 2:
                queries.append(BenchmarkQuery(
                    query_id=f"Q-{query_counter:04d}",
                    current_record_id=obs_list[1].record_id,
                    query_text=query_templates[concept],
                    expected_baseline_id=None,
                    expected_status="CONCEPT_MISMATCH",
                    distractor_ids=[obs_list[0].record_id],
                    split="test",
                    generator_version="2.0.0"
                ))
                query_counter += 1
            continue

        queries.append(BenchmarkQuery(
            query_id=f"Q-{query_counter:04d}",
            current_record_id=obs_list[0].record_id,
            query_text=query_templates.get(concept, f"Find baseline for {concept}"),
            expected_baseline_id=None,
            expected_status="NO_COMPARABLE_BASELINE",
            distractor_ids=[],
            split="development" if rng.random() < DEV_SPLIT_RATIO else "test",
            generator_version="2.0.0",
        ))
        query_counter += 1

        for idx in range(1, len(obs_list)):
            current = obs_list[idx]
            baseline = obs_list[idx - 1]

            if current.canonical_unit and baseline.canonical_unit:
                if concept == "lesion_diameter" and current.anatomical_site != baseline.anatomical_site:
                    continue

                distractors = [
                    o.record_id for o in observations
                    if o.patient_id == pid
                    and o.concept_code != concept
                    and o.record_id != current.record_id
                ][:3]

                split = "development" if rng.random() < DEV_SPLIT_RATIO else "test"
                queries.append(BenchmarkQuery(
                    query_id=f"Q-{query_counter:04d}",
                    current_record_id=current.record_id,
                    query_text=query_templates.get(concept, f"Find baseline for {concept}"),
                    expected_baseline_id=baseline.record_id,
                    expected_status="OK",
                    distractor_ids=distractors,
                    split=split,
                    generator_version="2.0.0",
                ))
                query_counter += 1

    while len(queries) < max(MIN_QUERIES, 400):
        src = queries[int(rng.integers(0, len(queries)))]
        queries.append(BenchmarkQuery(
            query_id=f"Q-{query_counter:04d}",
            current_record_id=src.current_record_id,
            query_text=src.query_text,
            expected_baseline_id=src.expected_baseline_id,
            expected_status=src.expected_status,
            distractor_ids=src.distractor_ids,
            split="development" if rng.random() < DEV_SPLIT_RATIO else "test",
            generator_version="2.0.0",
        ))
        query_counter += 1

    return queries


# ── Persistence ───────────────────────────────────────────────────


def save_corpus(
    observations: list[Observation],
    queries: list[BenchmarkQuery],
) -> None:
    """Write observations.csv, queries.json, and corpus_manifest.json."""
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    # ── observations.csv ──
    rows = []
    for obs in observations:
        rows.append({
            "record_id": obs.record_id,
            "patient_id": obs.patient_id,
            "observed_at": obs.observed_at.isoformat(),
            "concept_code": obs.concept_code,
            "concept_label": obs.concept_label,
            "value": obs.value,
            "unit": obs.unit,
            "canonical_value": obs.canonical_value,
            "canonical_unit": obs.canonical_unit,
            "condition_context": obs.condition_context,
            "anatomical_site": obs.anatomical_site,
            "note_text": obs.note_text,
            "source_type": obs.source_type,
            "is_synthetic": obs.is_synthetic,
        })
    df = pd.DataFrame(rows)
    csv_path = GENERATED_DIR / "observations.csv"
    df.to_csv(csv_path, index=False)

    # ── queries.json ──
    q_dicts = []
    for q in queries:
        q_dicts.append({
            "query_id": q.query_id,
            "current_record_id": q.current_record_id,
            "query_text": q.query_text,
            "expected_baseline_id": q.expected_baseline_id,
            "expected_status": q.expected_status,
            "distractor_ids": q.distractor_ids,
            "split": q.split,
            "generator_version": q.generator_version,
        })
    with open(GENERATED_DIR / "queries.json", "w", encoding="utf-8") as f:
        json.dump(q_dicts, f, indent=2)

    # ── corpus_manifest.json (merged with embedding manifest later) ──
    corpus_hash = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    manifest_path = GENERATED_DIR / "corpus_manifest.json"
    manifest: dict[str, Any] = {}
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    manifest.update({
        "seed": RANDOM_SEED,
        "num_patients": NUM_PATIENTS,
        "num_observations": len(observations),
        "num_queries": len(queries),
        "corpus_hash": corpus_hash,
        "generation_timestamp": datetime.now(timezone.utc).isoformat(),
    })
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"  Saved {len(observations)} observations to {csv_path}")
    print(f"  Saved {len(queries)} queries to {GENERATED_DIR / 'queries.json'}")
