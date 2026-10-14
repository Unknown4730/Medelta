from __future__ import annotations
import math

from meddelta.models import Observation, EligibilityResult
from meddelta.config import SUPPORTED_CONCEPTS

_CACHE = {}

def clear_eligibility_cache():
    _CACHE.clear()

def is_comparable(current: Observation, candidate: Observation) -> EligibilityResult:
    """
    Determines if a candidate observation is comparable to the current observation.
    Returns the first failure encountered or OK if eligible.
    """
    cache_key = (current.record_id, candidate.record_id)
    if cache_key in _CACHE:
        return _CACHE[cache_key]
        
    if current.patient_id != candidate.patient_id:
        return EligibilityResult(False, "PATIENT_MISMATCH")
        
    if candidate.observed_at >= current.observed_at:
        return EligibilityResult(False, "NOT_HISTORICAL")
        
    if current.concept_code != candidate.concept_code:
        return EligibilityResult(False, "CONCEPT_MISMATCH")
        
    if current.canonical_unit != candidate.canonical_unit:
        return EligibilityResult(False, "INCOMPATIBLE_UNIT")
        
    concept_info = SUPPORTED_CONCEPTS.get(current.concept_code, {})
    # For testing and fallback if config doesn't have it explicitly
    site_required = concept_info.get("site_required", current.concept_code == 'lesion_diameter')
    
    if site_required:
        if not current.anatomical_site or not candidate.anatomical_site:
            return EligibilityResult(False, "INSUFFICIENT_CONTEXT")
        if current.anatomical_site != candidate.anatomical_site:
            return EligibilityResult(False, "ANATOMICAL_SITE_MISMATCH")
            
    try:
        cur_val = float(current.canonical_value)
        can_val = float(candidate.canonical_value)
        if math.isnan(cur_val) or math.isnan(can_val) or math.isinf(cur_val) or math.isinf(can_val):
            return EligibilityResult(False, "INVALID_NUMERIC_VALUE")
    except (TypeError, ValueError):
        res = EligibilityResult(False, "INVALID_NUMERIC_VALUE")
        _CACHE[cache_key] = res
        return res
        
    res = EligibilityResult(True, "OK")
    _CACHE[cache_key] = res
    return res
