# Project Lifecycle Document

## 1. Delivery constraint

The prototype and paper-ready results must be complete by **30 July 2026** for
final submission checks on 31 July. This schedule assumes one developer, a local
machine capable of running a small sentence-transformer model, and no external
data-access approval.

## 2. Lifecycle model

Use a four-day evidence-first lifecycle. Each implementation task must either
support a research question, generate a paper artifact, or satisfy
reproducibility. Defer everything else.

## 3. Milestones

### 27 July: specification and research lock

- Freeze title, research questions, scope, metrics, and three retrieval methods.
- Create the repository skeleton and environment configuration.
- Define data models, comparability rules, and unit conversions.
- Implement seeded data and benchmark generation.
- Exit criterion: generated records validate and contain known baseline IDs.

### 28 July: end-to-end prototype

- Implement normalization, embeddings, retrieval baselines, hybrid ranking,
  deterministic deltas, and evidence manifests.
- Add unit tests for every comparability rule and calculation edge case.
- Build the single-screen Streamlit dashboard.
- Exit criterion: one query works end-to-end and all core tests pass.

### 29 July: experiments and figures

- Freeze the dataset and benchmark seeds before running final experiments.
- Run all three retrieval methods on at least 120 queries.
- Export metrics, errors, latency distributions, and configuration metadata.
- Generate the architecture figure, result table, example evidence figure, and
  dashboard screenshot.
- Exit criterion: every claimed result exists in an exported artifact.

### 30 July: paper completion and reproducibility

- Write methods and results from exported artifacts, not from memory.
- Complete introduction, related work, discussion, limitations, and conclusion.
- Run the project from a clean environment using only documented commands.
- Check IEEE formatting, anonymity rules, references, figure readability, and
  page limits.
- Exit criterion: submission PDF and reproducibility bundle are complete.

### 31 July: submission-only buffer

- Proofread names, affiliations, metadata, and PDF rendering.
- Confirm portal time zone and upload requirements.
- Do not add features or change experimental data unless correcting a critical
  reproducibility error.

## 4. Work priorities

**P0 - required:** data generation, comparability gate, three retrieval methods,
delta engine, evidence manifest, automated metrics, tests, paper tables.

**P1 - required for demonstration:** timeline dashboard and JSON evidence export.

**P2 - optional:** bootstrap confidence intervals, small usability study, error
inspection panel, Docker packaging.

**P3 - future work:** real records, FHIR/DICOM, images, LLM summaries, security,
clinical trials, and SNNs.

Drop P2 work immediately if any P0 item is incomplete by the end of 29 July.

## 5. Quality gates

- **Specification gate:** each claimed contribution maps to an experiment.
- **Data gate:** no real patient data; all generated rows pass schema validation.
- **Logic gate:** unit, eligibility, and arithmetic tests pass.
- **Experiment gate:** all methods use the same frozen test queries.
- **Claim gate:** abstract and conclusion state only measured outcomes.
- **Reproducibility gate:** clean setup regenerates tables from a fixed seed.
- **Submission gate:** PDF satisfies the conference's current portal/template
  requirements, which must be checked directly before upload.

## 6. Risk register

| Risk | Probability | Impact | Mitigation |
|---|---:|---:|---|
| Model download or dependency failure | Medium | High | Cache early; provide TF-IDF fallback and disclose it |
| Hybrid method shows no improvement | Medium | High | Report honestly; analyze failure cases; do not fabricate results |
| Synthetic benchmark is too easy | High | Medium | Add controlled distractors and ambiguous notes |
| Dashboard consumes paper time | Medium | Medium | Build only after evaluation path works |
| Unit-conversion errors | Medium | High | Keep conversion map small and unit test it |
| Paper overclaims clinical value | Medium | High | Use decision-support and synthetic-data language throughout |
| Portal deadline/time-zone mismatch | Low | High | Verify portal immediately and submit before the final hours |

## 7. Change control

After the experiment seed is frozen, changes to generation, comparability rules,
weights, or metrics require a new run ID and regeneration of every affected
paper table. Record limitations instead of silently modifying the benchmark to
improve results.

## 8. Final deliverables

- source code and tests;
- generated synthetic corpus and benchmark manifest;
- experiment configuration and machine-readable results;
- architecture and dashboard figures;
- IEEE-formatted manuscript and references;
- README with exact reproduction commands;
- disclosure that the work uses synthetic data and is not clinically validated.

