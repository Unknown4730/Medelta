from __future__ import annotations

from meddelta.config import FORMULA_VERSION
from meddelta.models import DeltaResult, EvidenceManifest, Observation, RetrievalResult

def build_evidence_manifest(
    current: Observation, 
    retrieval_result: RetrievalResult, 
    delta_result: DeltaResult | None
) -> EvidenceManifest:
    """Builds an evidence manifest for the current observation and retrieval result."""
    baseline_record = None
    if retrieval_result.ranked_candidates:
        baseline_record = retrieval_result.ranked_candidates[0].observation
        
    warnings = []
    if retrieval_result.status != "OK":
        warnings.append(retrieval_result.status)
    if delta_result is not None and delta_result.status != "OK":
        warnings.append(delta_result.status)
        
    return EvidenceManifest(
        current_record=current,
        baseline_record=baseline_record,
        retrieval_result=retrieval_result,
        delta_result=delta_result,
        formula_version=FORMULA_VERSION,
        warnings=warnings
    )
