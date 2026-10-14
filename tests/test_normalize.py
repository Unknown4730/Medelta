from __future__ import annotations
import math
import pytest
from datetime import datetime

from meddelta.models import Observation
from meddelta.normalize import resolve_concept, convert_value, normalize_observation

def create_obs(concept_code, value, unit) -> Observation:
    return Observation(
        record_id="r1",
        patient_id="p1",
        observed_at=datetime(2023, 1, 1),
        concept_code=concept_code,
        concept_label="Test Label",
        value=value,
        unit=unit,
        canonical_value=0.0,
        canonical_unit=""
    )

def test_creatinine_umol_to_mgdl():
    val, unit = convert_value('creatinine', 88.4, 'umol/L')
    assert math.isclose(val, 1.0, rel_tol=1e-6)
    assert unit == 'mg/dL'

def test_glucose_mmol_to_mgdl():
    val, unit = convert_value('glucose', 5.5, 'mmol/L')
    assert math.isclose(val, 99.1001, rel_tol=1e-6)
    assert unit == 'mg/dL'

def test_lesion_cm_to_mm():
    val, unit = convert_value('lesion_diameter', 1.5, 'cm')
    assert val == 15.0
    assert unit == 'mm'

def test_identity_conversion():
    val, unit = convert_value('creatinine', 1.5, 'mg/dL')
    assert val == 1.5
    assert unit == 'mg/dL'

def test_alias_resolution():
    assert resolve_concept('serum_creatinine') == 'creatinine'
    assert resolve_concept('a1c') == 'HbA1c'
    assert resolve_concept('sbp') == 'systolic_bp'
    assert resolve_concept('tumor_diameter') == 'lesion_diameter'

def test_unsupported_unit_raises():
    with pytest.raises(ValueError):
        convert_value('creatinine', 1.0, 'oz')

def test_round_trip():
    obs = create_obs('creat', 88.4, 'umol/L')
    norm_obs = normalize_observation(obs)
    assert norm_obs.concept_code == 'creatinine'
    assert norm_obs.canonical_unit == 'mg/dL'
    assert math.isclose(norm_obs.canonical_value, 1.0, rel_tol=1e-6)
