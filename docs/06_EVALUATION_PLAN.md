# Evaluation Plan

## 1. Goal

Test whether comparability-first hybrid retrieval selects the intended earlier
measurement more reliably than simple alternatives, while preserving exact and
traceable arithmetic.

## 2. Experimental dataset

- 60 synthetic patients
- 6-12 observations per patient
- at least 120 benchmark queries
- 30% development and 70% held-out test queries
- fixed random seed recorded in the run manifest
- at least one controlled distractor in 60% of queries

Distractor categories should be balanced across different concepts, incompatible
units, wrong sites, future dates, semantically similar notes, and missing data.

## 3. Compared methods

- **M1 Metadata-only:** comparability fields plus most-recent selection.
- **M2 Semantic-only:** patient/time filter plus cosine similarity.
- **M3 Proposed hybrid:** comparability eligibility followed by fixed weighted
  semantic, recency, and context ranking.

All methods receive identical current records, query text, and candidate corpus.

## 4. Primary metrics

```text
Baseline Selection Accuracy = correct rank-1 baselines / evaluable queries
Valid Pair Rate = comparable rank-1 pairs / queries returning a result
Top-3 Hit Rate = queries with expected baseline in top three / evaluable queries
MRR = mean(1 / rank of expected baseline)
Delta Exact Match = correct delta outputs / valid selected pairs
Evidence Completeness = manifests with all required fields / returned manifests
```

Record median, p95, minimum, and maximum warm-query latency. Report cold model
loading separately so it does not distort interactive retrieval latency.

## 5. Correctness tolerances

- timestamps and record IDs: exact match;
- normalized numeric values: absolute tolerance `1e-6`;
- displayed percentage and velocity: tolerance based on unrounded values, then
  round only for presentation;
- retrieval tie breaking: deterministic by timestamp then record ID.

## 6. Ablation study

If time permits, evaluate hybrid retrieval after removing one component at a
time: eligibility gate, semantic score, recency score, and context score. The
eligibility-gate ablation is the most valuable because it directly tests the
paper's central proposition.

## 7. Statistical reporting

Report counts and proportions, not only percentages. Use paired bootstrap 95%
confidence intervals for the difference in Baseline Selection Accuracy between
M3 and each baseline. With a small synthetic benchmark, describe statistical
results as exploratory and avoid broad generalization.

## 8. Error analysis

Manually classify every M3 test error into:

- ambiguous ground truth;
- normalization failure;
- eligibility-rule failure;
- semantic-ranking failure;
- recency/context-weight failure; or
- malformed synthetic record.

Include 2-3 representative failures in the paper. Negative results and boundary
cases strengthen the credibility of a prototype study.

## 9. Optional usability study

Only run this if the automated study is finished. Ask 3-5 non-clinical
participants to answer fixed record-comparison tasks using a raw timeline and
the dashboard in counterbalanced order. Measure time, correctness, and perceived
traceability. Label it a formative study, not clinical validation.

## 10. Required paper artifacts

- Table I: corpus and benchmark statistics
- Table II: M1/M2/M3 retrieval metrics
- Table III: delta correctness, evidence completeness, and latency
- Figure 1: pipeline architecture
- Figure 2: evidence-linked dashboard example
- Figure 3: error categories or metric comparison
- Appendix/repository artifact: exact configuration and run manifest

## 11. Claim rules

- Do not write “improves” unless M3 exceeds the named baseline in final results.
- Do not write “real time” unless latency is measured and the threshold defined.
- Do not write “clinically accurate,” “safe,” or “effective.”
- Do not imply synthetic evaluation represents hospital deployment.
- Report failed hypotheses and limitations without changing the benchmark.

## 12. Evaluation completion checklist

- Corpus and split frozen before final test run
- All methods run against identical query IDs
- Tests pass before collecting metrics
- Run manifest and corpus hash recorded
- Raw per-query predictions retained
- Tables generated from result files
- Paper values cross-checked against machine-readable output
