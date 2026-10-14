from __future__ import annotations

import math
import numpy as np

from meddelta.config import TREND_EPSILON, TRAJECTORY_TOP_K
from meddelta.models import DeltaResult, Observation, TrajectoryResult

def calculate_delta(current: Observation, baseline: Observation) -> DeltaResult:
    """Calculates the delta between current and baseline observations."""
    c = current.canonical_value
    b = baseline.canonical_value
    
    if math.isnan(c) or math.isnan(b) or math.isinf(c) or math.isinf(b):
        return DeltaResult(
            absolute_change=0.0,
            percentage_change=None,
            change_per_day=0.0,
            elapsed_days=0.0,
            status="INVALID_NUMERIC_VALUE"
        )
        
    elapsed_days = (current.observed_at - baseline.observed_at).total_seconds() / 86400.0
    
    if elapsed_days <= 0:
        return DeltaResult(
            absolute_change=0.0,
            percentage_change=None,
            change_per_day=0.0,
            elapsed_days=elapsed_days,
            status="NOT_HISTORICAL"
        )
        
    absolute_change = c - b
    change_per_day = absolute_change / elapsed_days
    
    status = "OK"
    percentage_change = None
    if b != 0:
        percentage_change = (absolute_change / abs(b)) * 100.0
    else:
        status = "PERCENTAGE_UNDEFINED"
        
    return DeltaResult(
        absolute_change=absolute_change,
        percentage_change=percentage_change,
        change_per_day=change_per_day,
        elapsed_days=elapsed_days,
        status=status
    )

def calculate_trajectory(
    current: Observation,
    baselines: list[Observation],
) -> TrajectoryResult:
    """Calculates the trajectory (OLS linear regression) over historical baselines and current observation.

    Mathematical Formulation:
    Given K observations {(t_i, v_i)}, where t_i is elapsed days from the earliest observation:
        t̄ = mean(t_i)
        v̄ = mean(v_i)
        β₁ = Σ(tᵢ − t̄)(vᵢ − v̄) / Σ(tᵢ − t̄)²
        β₀ = v̄ − β₁ · t̄
        SS_res = Σ(vᵢ − β₀ − β₁·tᵢ)²
        SS_tot = Σ(vᵢ − v̄)²
        R² = 1 − SS_res / SS_tot (if SS_tot > 0 else 0.0)
        
    Trend Classification:
        Let ε = TREND_EPSILON.get(current.concept_code, 0.01).
        If |β₁| < ε → 'STABLE'
        If β₁ ≥ ε → 'INCREASING'
        If β₁ ≤ −ε → 'DECREASING'
    """
    if len(baselines) < 1:
        return TrajectoryResult(
            slope=0.0,
            intercept=current.canonical_value,
            r_squared=0.0,
            trend="STABLE",
            num_points=1,
            point_record_ids=[current.record_id],
            elapsed_span_days=0.0,
            status="INSUFFICIENT_DATA"
        )
        
    # Filter valid observations (exclude NaN/inf)
    valid_obs = []
    for obs in baselines + [current]:
        v = obs.canonical_value
        if not (math.isnan(v) or math.isinf(v)):
            valid_obs.append(obs)
            
    if len(valid_obs) < 2:
        return TrajectoryResult(
            slope=0.0,
            intercept=current.canonical_value,
            r_squared=0.0,
            trend="STABLE",
            num_points=len(valid_obs),
            point_record_ids=[obs.record_id for obs in valid_obs],
            elapsed_span_days=0.0,
            status="INSUFFICIENT_DATA"
        )
        
    # Sort chronologically
    valid_obs.sort(key=lambda o: o.observed_at)
    
    min_date = valid_obs[0].observed_at
    max_date = valid_obs[-1].observed_at
    elapsed_span_days = (max_date - min_date).total_seconds() / 86400.0
    
    t_vals = np.array([(obs.observed_at - min_date).total_seconds() / 86400.0 for obs in valid_obs], dtype=np.float64)
    v_vals = np.array([obs.canonical_value for obs in valid_obs], dtype=np.float64)
    
    t_mean = np.mean(t_vals)
    v_mean = np.mean(v_vals)
    
    t_diff = t_vals - t_mean
    t_diff_sq_sum = np.sum(t_diff**2)
    
    point_record_ids = [obs.record_id for obs in valid_obs]
    num_points = len(valid_obs)
    
    if t_diff_sq_sum == 0.0:
        return TrajectoryResult(
            slope=0.0,
            intercept=float(v_mean),
            r_squared=0.0,
            trend="STABLE",
            num_points=num_points,
            point_record_ids=point_record_ids,
            elapsed_span_days=float(elapsed_span_days),
            status="INSUFFICIENT_DATA"
        )
        
    beta_1 = np.sum(t_diff * (v_vals - v_mean)) / t_diff_sq_sum
    beta_0 = v_mean - beta_1 * t_mean
    
    v_pred = beta_0 + beta_1 * t_vals
    ss_res = np.sum((v_vals - v_pred)**2)
    ss_tot = np.sum((v_vals - v_mean)**2)
    
    if ss_tot == 0.0:
        r_squared = 1.0
        status = "ZERO_VARIANCE"
        trend = "STABLE"
    else:
        r_squared = 1.0 - (ss_res / ss_tot)
        status = "OK"
        
        epsilon = TREND_EPSILON.get(current.concept_code, 0.01)
        if abs(beta_1) < epsilon:
            trend = "STABLE"
        elif beta_1 >= epsilon:
            trend = "INCREASING"
        else:
            trend = "DECREASING"
            
    return TrajectoryResult(
        slope=float(beta_1),
        intercept=float(beta_0),
        r_squared=float(r_squared),
        trend=trend,
        num_points=num_points,
        point_record_ids=point_record_ids,
        elapsed_span_days=float(elapsed_span_days),
        status=status
    )
