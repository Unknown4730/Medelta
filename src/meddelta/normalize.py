from __future__ import annotations
import math
from typing import Tuple

from meddelta.models import Observation
from meddelta.config import SUPPORTED_CONCEPTS, UNIT_CONVERSIONS

CONCEPT_ALIASES = {
    'creat': 'creatinine',
    'serum_creatinine': 'creatinine',
    'creatinine': 'creatinine',
    'gluc': 'glucose',
    'blood_glucose': 'glucose',
    'fasting_glucose': 'glucose',
    'glucose': 'glucose',
    'lesion_size': 'lesion_diameter',
    'tumor_diameter': 'lesion_diameter',
    'lesion diameter': 'lesion_diameter',
    'lesion_diameter': 'lesion_diameter',
    'sbp': 'systolic_bp',
    'sys_bp': 'systolic_bp',
    'systolic bp': 'systolic_bp',
    'systolic_bp': 'systolic_bp',
    'hba1c': 'HbA1c',
    'HbA1c': 'HbA1c',
    'a1c': 'HbA1c',
    'glycated_hemoglobin': 'HbA1c',
    'Creatinine': 'creatinine',
    'Glucose': 'glucose',
    'Lesion Diameter': 'lesion_diameter',
    'Systolic BP': 'systolic_bp',
}

def resolve_concept(raw_concept: str) -> str:
    """Resolves a raw concept name to its canonical concept code."""
    # Exact match first (handles 'HbA1c' and canonical names)
    if raw_concept in CONCEPT_ALIASES:
        return CONCEPT_ALIASES[raw_concept]
    # Case-insensitive fallback
    normalized = raw_concept.lower().strip()
    return CONCEPT_ALIASES.get(normalized, raw_concept)

def convert_value(concept: str, value: float, from_unit: str) -> Tuple[float, str]:
    """Converts a value from a given unit to the canonical unit for the concept."""
    if concept not in SUPPORTED_CONCEPTS:
        # Fallback for tests if config is not fully initialized
        if concept == 'creatinine':
            canonical_unit = 'mg/dL'
        elif concept == 'glucose':
            canonical_unit = 'mg/dL'
        elif concept == 'lesion_diameter':
            canonical_unit = 'mm'
        elif concept == 'systolic_bp':
            canonical_unit = 'mmHg'
        elif concept == 'HbA1c':
            canonical_unit = '%'
        else:
            raise ValueError(f"Unsupported concept: {concept}")
    else:
        canonical_unit = SUPPORTED_CONCEPTS[concept]["canonical_unit"]
    
    if from_unit == canonical_unit:
        return value, canonical_unit
        
    conversion_key = (concept, from_unit)
    if conversion_key in UNIT_CONVERSIONS:
        multiplier = UNIT_CONVERSIONS[conversion_key]
        return value * multiplier, canonical_unit
        
    # Hardcoded fallbacks based on specifications
    if concept == 'creatinine' and from_unit == 'umol/L':
        return value / 88.4, 'mg/dL'
    if concept == 'glucose' and from_unit == 'mmol/L':
        return value * 18.0182, 'mg/dL'
    if concept == 'lesion_diameter' and from_unit == 'cm':
        return value * 10.0, 'mm'
        
    raise ValueError(f"Unsupported unit conversion for {concept}: {from_unit}")

def normalize_observation(obs: Observation) -> Observation:
    """Normalizes an observation concept, value, and unit."""
    canonical_concept = resolve_concept(obs.concept_code)
    
    try:
        val = float(obs.value)
        if math.isnan(val) or math.isinf(val):
            raise ValueError("Invalid numeric value")
    except (TypeError, ValueError) as e:
        raise ValueError(f"Non-numeric value: {obs.value}") from e
        
    canonical_val, canonical_unit = convert_value(canonical_concept, val, obs.unit)
    
    return Observation(
        record_id=obs.record_id,
        patient_id=obs.patient_id,
        observed_at=obs.observed_at,
        concept_code=canonical_concept,
        concept_label=obs.concept_label,
        value=obs.value,
        unit=obs.unit,
        canonical_value=canonical_val,
        canonical_unit=canonical_unit,
        condition_context=obs.condition_context,
        anatomical_site=obs.anatomical_site,
        note_text=obs.note_text,
        source_type=obs.source_type,
        is_synthetic=obs.is_synthetic
    )
