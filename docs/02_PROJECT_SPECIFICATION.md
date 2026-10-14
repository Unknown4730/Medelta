# Project Specification Document

## 1. Purpose

Build a local research prototype demonstrating retrieval of a comparable prior
clinical observation and deterministic calculation of change over time. The
software exists to generate evidence for the accompanying paper.

## 2. Users

- **Researcher:** generates data, runs experiments, and exports metrics.
- **Demonstration user:** selects a synthetic patient and current observation,
  then inspects the retrieved baseline, delta, timeline, and evidence.
- **Reviewer:** reproduces the benchmark and verifies the claimed results.

## 3. In-scope user journey

1. Open the dashboard and see the research-use warning.
2. Select a synthetic patient.
3. Select a current observation or enter a short retrieval query.
4. Run one of three retrieval methods.
5. Inspect the selected prior baseline and rejection reasons for invalid records.
6. Review absolute, percentage, and time-normalized change.
7. Inspect both source records and the calculation manifest.
8. View the patient's timeline and optionally export the evidence as JSON.

## 4. Functional requirements

- **FR-01 Data generation:** Generate a deterministic synthetic corpus and
  benchmark from a configurable random seed.
- **FR-02 Validation:** Reject malformed dates, missing identifiers, non-numeric
  observation values, and unsupported units with explicit reasons.
- **FR-03 Normalization:** Map supported concepts and units to canonical forms.
- **FR-04 Embedding:** Embed note text once and persist embeddings locally.
- **FR-05 Metadata baseline:** Return the latest earlier observation matching
  patient and normalized concept.
- **FR-06 Semantic baseline:** Rank earlier records by cosine similarity.
- **FR-07 Hybrid baseline:** Apply the comparability contract, then rank eligible
  candidates using semantic, recency, and context scores.
- **FR-08 Delta calculation:** Calculate absolute change, percentage change when
  defined, elapsed days, and change per day.
- **FR-09 Traceability:** Return an evidence manifest for every computed result.
- **FR-10 Dashboard:** Display method, current record, baseline, result, timeline,
  source evidence, and warnings without generating a diagnosis.
- **FR-11 Evaluation:** Run all retrieval methods on the same benchmark and write
  machine-readable and tabular results.
- **FR-12 Reproducibility:** Record seed, package versions, model identifier,
  corpus size, machine information, and run timestamp.

## 5. Non-functional requirements

- Local operation after model download; no patient data leaves the machine.
- Deterministic data generation and stable ranking tie-breakers.
- Median warm-query latency target below 500 ms for the paper corpus.
- Unit-tested normalization, eligibility, ranking, and arithmetic modules.
- Typed Python interfaces and clear validation errors.
- Keyboard-accessible dashboard controls and readable color contrast.
- No hidden LLM calls and no generated clinical advice.

## 6. Acceptance criteria

- A fresh environment can be installed using one documented command.
- One command generates the corpus and benchmark.
- One command runs tests.
- One command runs all experiments and exports results.
- One command starts the dashboard.
- At least 120 ground-truth queries and 60 synthetic patients are generated.
- Results include all primary metrics for all three methods.
- Every displayed delta identifies both source record IDs.
- Division-by-zero, incompatible-unit, missing-value, and no-baseline cases are
  handled without crashing.

## 7. Out of scope

- Real or identifiable patient data
- Diagnosis, treatment, triage, or prognostic recommendations
- EHR/FHIR/DICOM integration
- Medical-image interpretation or segmentation
- Hosted vector databases, cloud deployment, and multi-user authentication
- LLM-generated summaries
- Spiking neural networks or biological computing
- Clinical trials or claims of improved patient outcomes

## 8. Recommended repository structure

```text
meddelta-rag/
|-- README.md
|-- pyproject.toml
|-- .gitignore
|-- app.py
|-- src/meddelta/
|   |-- __init__.py
|   |-- config.py
|   |-- models.py
|   |-- generate_data.py
|   |-- normalize.py
|   |-- embed.py
|   |-- eligibility.py
|   |-- retrieval.py
|   |-- delta.py
|   |-- evidence.py
|   `-- evaluation.py
|-- scripts/
|   |-- generate_dataset.py
|   `-- run_experiments.py
|-- data/
|   |-- generated/.gitkeep
|   `-- results/.gitkeep
|-- tests/
|   |-- test_normalize.py
|   |-- test_eligibility.py
|   |-- test_retrieval.py
|   |-- test_delta.py
|   `-- test_evaluation.py
`-- docs/
```

## 9. Definition of done

The project is done when the acceptance criteria pass, screenshots and result
tables are available for the paper, the paper contains no unsupported clinical
claims, and another user can reproduce the reported experiment from the README.
