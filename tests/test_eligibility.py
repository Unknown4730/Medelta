from __future__ import annotations
import math
from datetime import datetime
import pytest

from meddelta.models import Observation, EligibilityResult
from meddelta.eligibility import is_comparable

def create_obs(patient_id, observed_at, concept_code, canonical_value, canonical_unit, anatomical_site=None) -> Observation:
    return Observation(
        record_id="r1",
        patient_id=patient_id,
        observed_at=observed_at,
        concept_code=concept_code,
        concept_label="Test Label",
        value=canonical_value,
        unit=canonical_unit,
        canonical_value=canonical_value,
        canonical_unit=canonical_unit,
        anatomical_site=anatomical_site
    )

def test_eligible_pair():
    current = create_obs("p1", datetime(2023, 2, 1), "creatinine", 1.0, "mg/dL")
    candidate = create_obs("p1", datetime(2023, 1, 1), "creatinine", 1.2, "mg/dL")
    result = is_comparable(current, candidate)
    assert result.is_eligible is True
    assert result.reason_code == "OK"

def test_patient_mismatch():
    current = create_obs("p1", datetime(2023, 2, 1), "creatinine", 1.0, "mg/dL")
    candidate = create_obs("p2", datetime(2023, 1, 1), "creatinine", 1.2, "mg/dL")
    result = is_comparable(current, candidate)
    assert result.is_eligible is False
    assert result.reason_code == "PATIENT_MISMATCH"

def test_not_historical():
    current = create_obs("p1", datetime(2023, 1, 1), "creatinine", 1.0, "mg/dL")
    candidate = create_obs("p1", datetime(2023, 2, 1), "creatinine", 1.2, "mg/dL")
    result = is_comparable(current, candidate)
    assert result.is_eligible is False
    assert result.reason_code == "NOT_HISTORICAL"

def test_concept_mismatch():
    current = create_obs("p1", datetime(2023, 2, 1), "creatinine", 1.0, "mg/dL")
    candidate = create_obs("p1", datetime(2023, 1, 1), "glucose", 1.2, "mg/dL")
    result = is_comparable(current, candidate)
    assert result.is_eligible is False
    assert result.reason_code == "CONCEPT_MISMATCH"

def test_incompatible_unit():
    current = create_obs("p1", datetime(2023, 2, 1), "creatinine", 1.0, "mg/dL")
    candidate = create_obs("p1", datetime(2023, 1, 1), "creatinine", 88.4, "umol/L")
    result = is_comparable(current, candidate)
    assert result.is_eligible is False
    assert result.reason_code == "INCOMPATIBLE_UNIT"

def test_anatomical_site_mismatch():
    current = create_obs("p1", datetime(2023, 2, 1), "lesion_diameter", 15.0, "mm", "lung")
    candidate = create_obs("p1", datetime(2023, 1, 1), "lesion_diameter", 20.0, "mm", "liver")
    result = is_comparable(current, candidate)
    assert result.is_eligible is False
    assert result.reason_code == "ANATOMICAL_SITE_MISMATCH"

def test_missing_site_insufficient_context():
    current = create_obs("p1", datetime(2023, 2, 1), "lesion_diameter", 15.0, "mm", None)
    candidate = create_obs("p1", datetime(2023, 1, 1), "lesion_diameter", 20.0, "mm", "lung")
    result = is_comparable(current, candidate)
    assert result.is_eligible is False
    assert result.reason_code == "INSUFFICIENT_CONTEXT"

def test_invalid_numeric():
    current = create_obs("p1", datetime(2023, 2, 1), "creatinine", float('nan'), "mg/dL")
    candidate = create_obs("p1", datetime(2023, 1, 1), "creatinine", 1.2, "mg/dL")
    result = is_comparable(current, candidate)
    assert result.is_eligible is False
    assert result.reason_code == "INVALID_NUMERIC_VALUE"
