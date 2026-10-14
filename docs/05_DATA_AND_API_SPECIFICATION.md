# Data and API Specification

## 1. Data principles

All data is synthetic, versioned, and reproducible. Store tabular artifacts as
CSV for inspection and JSON for nested evidence. Use ISO 8601 timestamps in UTC,
stable string identifiers, and canonical unit labels.

## 2. Observation schema

| Field | Type | Required | Description |
|---|---|---:|---|
| record_id | string | yes | Unique stable observation ID |
| patient_id | string | yes | Synthetic patient ID |
| observed_at | datetime | yes | Observation timestamp |
| concept_code | string | yes | Canonical measurement identifier |
| concept_label | string | yes | Human-readable name |
| value | number | yes | Original numeric value |
| unit | string | yes | Original unit |
| canonical_value | number | yes | Converted value |
| canonical_unit | string | yes | Unit used for comparison |
| condition_context | string | no | Normalized condition/context |
| anatomical_site | string | no | Required for site-dependent concepts |
| note_text | string | yes | Short synthetic note for retrieval |
| source_type | enum | yes | `lab`, `vital`, or `measurement` |
| is_synthetic | boolean | yes | Always true in this prototype |

## 3. Benchmark query schema

| Field | Type | Description |
|---|---|---|
| query_id | string | Unique benchmark query ID |
| current_record_id | string | Current observation |
| query_text | string | Retrieval text presented to methods |
| expected_baseline_id | string/null | Ground-truth prior record |
| expected_status | string | `OK` or expected failure code |
| distractor_ids | array[string] | Intentionally confusing candidates |
| split | string | `development` or `test` |
| generator_version | string | Dataset generator version |

The final test split must not be used to select ranking weights.

## 4. Canonical concept configuration

Maintain concept aliases, canonical units, conversion functions, and whether an
anatomical site is mandatory in one versioned configuration object. Each
conversion requires a round-trip or known-value test.

Initial conversions:

```text
creatinine: umol/L to mg/dL = value / 88.4
glucose: mmol/L to mg/dL = value * 18.0182
lesion_diameter: cm to mm = value * 10
```

Do not add a conversion unless its formula and expected precision are verified.

## 5. Internal service interfaces

```python
normalize_observation(observation) -> NormalizedObservation

is_comparable(current, candidate) -> EligibilityResult

retrieve_baseline(
    current,
    query_text,
    corpus,
    method,
    top_k=3,
) -> RetrievalResult

calculate_delta(current, baseline) -> DeltaResult

build_evidence_manifest(
    current,
    retrieval_result,
    delta_result,
) -> EvidenceManifest

evaluate_method(method, queries, corpus) -> EvaluationReport
```

## 6. Retrieval result contract

```json
{
  "method": "hybrid",
  "status": "OK",
  "selected_record_id": "R-0012",
  "ranked_candidates": [
    {
      "record_id": "R-0012",
      "rank": 1,
      "score": 0.873,
      "semantic_score": 0.81,
      "recency_score": 0.96,
      "context_score": 1.0
    }
  ],
  "rejected_candidates": [
    {"record_id": "R-0011", "reason": "CONCEPT_MISMATCH"}
  ]
}
```

## 7. Delta result contract

```json
{
  "status": "OK",
  "current_record_id": "R-0020",
  "baseline_record_id": "R-0012",
  "canonical_unit": "mg/dL",
  "baseline_value": 0.9,
  "current_value": 1.4,
  "absolute_change": 0.5,
  "percentage_change": 55.56,
  "elapsed_days": 180,
  "change_per_day": 0.002778,
  "formula_version": "1.0"
}
```

## 8. Status and rejection codes

- `OK`
- `NO_COMPARABLE_BASELINE`
- `PATIENT_MISMATCH`
- `NOT_HISTORICAL`
- `CONCEPT_MISMATCH`
- `INCOMPATIBLE_UNIT`
- `ANATOMICAL_SITE_MISMATCH`
- `INSUFFICIENT_CONTEXT`
- `INVALID_NUMERIC_VALUE`
- `PERCENTAGE_UNDEFINED`
- `EMBEDDING_UNAVAILABLE`

## 9. Output artifacts

```text
data/generated/observations.csv
data/generated/queries.json
data/generated/embeddings.npy
data/generated/corpus_manifest.json
data/results/metrics.csv
data/results/predictions.jsonl
data/results/latency.csv
data/results/run_manifest.json
```

The run manifest includes seed, git revision when available, dependency versions,
embedding model, ranking weights, timestamps, corpus hash, and machine details.

