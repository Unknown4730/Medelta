import math
from datetime import datetime, timedelta

from meddelta.delta import calculate_delta
from meddelta.models import Observation

def make_obs(val, unit, cval, cunit, hours_ago=0):
    dt = datetime(2023, 1, 1) - timedelta(hours=hours_ago)
    return Observation(
        record_id="r1", patient_id="p1", observed_at=dt,
        concept_code="c", concept_label="C", value=val, unit=unit,
        canonical_value=cval, canonical_unit=cunit
    )

def test_normal_delta():
    curr = make_obs(10, "mg", 10.0, "mg", 0)
    base = make_obs(5, "mg", 5.0, "mg", 24)
    res = calculate_delta(curr, base)
    assert res.absolute_change == 5.0
    assert res.percentage_change == 100.0
    assert res.change_per_day == 5.0
    assert res.status == "OK"

def test_zero_baseline():
    curr = make_obs(10, "mg", 10.0, "mg", 0)
    base = make_obs(0, "mg", 0.0, "mg", 24)
    res = calculate_delta(curr, base)
    assert res.percentage_change is None
    assert res.status == "PERCENTAGE_UNDEFINED"

def test_negative_elapsed():
    curr = make_obs(10, "mg", 10.0, "mg", 24)
    base = make_obs(5, "mg", 5.0, "mg", 0)
    res = calculate_delta(curr, base)
    assert res.status == "NOT_HISTORICAL"

def test_same_timestamp():
    curr = make_obs(10, "mg", 10.0, "mg", 0)
    base = make_obs(5, "mg", 5.0, "mg", 0)
    res = calculate_delta(curr, base)
    assert res.status == "NOT_HISTORICAL"

def test_precision():
    curr = make_obs(10, "mg", 1.0000001, "mg", 0)
    base = make_obs(10, "mg", 1.0000000, "mg", 24)
    res = calculate_delta(curr, base)
    assert abs(res.absolute_change - 0.0000001) < 1e-9

def test_nan_value():
    curr = make_obs(10, "mg", float('nan'), "mg", 0)
    base = make_obs(5, "mg", 5.0, "mg", 24)
    res = calculate_delta(curr, base)
    assert res.status == "INVALID_NUMERIC_VALUE"
