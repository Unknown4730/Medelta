# Research Specification Document

## 1. Working title

**MedDelta-RAG: Comparability-First Retrieval and Evidence-Linked Temporal
Change Detection for Longitudinal Clinical Records**

## 2. Problem statement

Longitudinal records contain many dated observations, but finding the correct
historical baseline for a current result is time-consuming. Semantic retrieval
can return topically relevant records that use a different measurement, unit,
anatomical context, or time direction. Generative summaries can also obscure
which records support a reported change.

The research problem is therefore not general medical question answering. It is
the narrower problem of selecting a *comparable* earlier observation and
producing a change statement that is mathematically reproducible and linked to
its evidence.

## 3. Research gap

The paper will investigate an under-evaluated intersection of established
techniques:

- semantic retrieval is usually evaluated for topical relevance;
- structured filtering is usually treated as a database operation;
- clinical dashboards show trends but do not normally expose retrieval quality;
- RAG systems often evaluate generated answers rather than baseline-pair
  validity and arithmetic traceability.

The paper must not claim that clinical RAG, timelines, hybrid search, or trend
calculation are individually new. Its contribution is a comparability-first
retrieval contract and an evaluation centered on valid temporal pairs.

## 4. Research objective

Design and evaluate a lightweight pipeline that:

1. rejects historical candidates that are not clinically comparable;
2. ranks eligible candidates using semantic and temporal/contextual signals;
3. computes deterministic changes without generative arithmetic; and
4. exposes the exact source records and calculation for verification.

## 5. Research questions

- **RQ1:** Does comparability-first hybrid retrieval improve valid-baseline
  selection over metadata-only and semantic-only retrieval?
- **RQ2:** Can a deterministic delta engine achieve exact agreement with a
  generated ground-truth benchmark after unit normalization?
- **RQ3:** Can the complete local pipeline respond within an interactive latency
  target on a small longitudinal dataset?
- **RQ4 (optional):** Does the evidence-linked display reduce the time required
  to verify a historical change in a small non-clinical usability study?

## 6. Hypotheses

- **H1:** Hybrid retrieval will improve Baseline Selection Accuracy and Valid
  Pair Rate by at least 10 percentage points over semantic-only retrieval.
- **H2:** Delta accuracy will be 100% on valid pairs covered by the unit map.
- **H3:** Median end-to-end latency will be below 500 ms after embeddings are
  loaded on the evaluation machine.

H1 is a target, not a result. It must be accepted or rejected from measured data.

## 7. Proposed contribution

The principal contribution is a **comparability contract** applied before
semantic ranking. A candidate baseline is eligible only when it has:

- the same patient;
- a timestamp earlier than the current observation;
- the same normalized measurement concept;
- a compatible canonical unit;
- a matching anatomical site when site is applicable; and
- a parseable numeric value.

The secondary contribution is an **evidence manifest** containing record IDs,
timestamps, original and normalized values, elapsed time, formula, and retrieval
score for every displayed delta.

## 8. Method

Generate a seeded synthetic dataset of 60 patients, each with 6-12 dated
observations and short notes. Include controlled distractors: same condition but
different measurement, future records, incompatible units, wrong anatomical
site, and semantically similar notes from the same patient.

Create at least 120 benchmark queries with known correct baselines. Compare:

1. metadata-only retrieval;
2. semantic-only cosine retrieval; and
3. comparability-first hybrid retrieval.

Run all methods over the same candidate corpus and report aggregate metrics with
bootstrap 95% confidence intervals where time permits.

## 9. Variables and metrics

Independent variable: retrieval strategy.

Primary dependent metrics:

- Baseline Selection Accuracy at rank 1
- Valid Pair Rate at rank 1
- Top-3 Hit Rate and Mean Reciprocal Rank
- Delta Exact Match after normalization
- Evidence Completeness Rate
- median and p95 latency

Optional usability metrics: task completion time and answer correctness.

## 10. Threats to validity

- Synthetic data may not reflect real documentation noise or clinical workflow.
- The benchmark encodes the same comparability policy implemented by the system.
- The small corpus may overestimate scalability and latency performance.
- A non-clinical usability sample cannot support claims about physician outcomes.
- Embedding-model results may not generalize to other models or languages.

## 11. Ethics and safety

Use no real patient data. Label all records as synthetic. Do not produce
diagnoses, treatment recommendations, risk scores, or alerts. The interface must
display: "Research prototype - synthetic data - not for clinical use."

## 12. Success criteria

The research prototype is complete when it runs end-to-end from a clean setup,
the benchmark is reproducible from a fixed seed, all arithmetic tests pass, all
three retrieval strategies are evaluated, and every result table in the paper
can be regenerated by one documented command.
