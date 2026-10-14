# IEEE Paper Outline

## 1. Recommended title

**MedDelta-RAG: Comparability-First Retrieval for Evidence-Linked Temporal
Change Detection in Longitudinal Clinical Records**

## 2. Abstract structure

Write 180-220 words after experiments are complete:

1. problem: locating a valid historical baseline in long records;
2. limitation: topical relevance does not guarantee comparability;
3. method: eligibility gate, hybrid ranking, deterministic delta, evidence link;
4. evaluation: synthetic corpus, query count, and three compared methods;
5. results: measured values copied from generated tables;
6. limitation: synthetic prototype, no clinical validation;
7. contribution: transparent longitudinal comparison rather than diagnosis.

Never insert predicted or invented numerical results.

## 3. Section plan

### I. Introduction

Explain longitudinal information overload, invalid-baseline risk, and why a
traceable comparison is narrower and safer than generated diagnosis. End with
three contributions: comparability contract, evidence manifest, and benchmarked
prototype.

### II. Related Work

Organize by clinical information retrieval/RAG, temporal EHR representation,
clinical timeline visualization, and trustworthy/explainable decision support.
For each group, identify the exact difference from this paper. Use verified
scholarly sources; do not cite generated references.

### III. Methodology

Define data schema, normalization, eligibility predicate, three retrieval
methods, score equation, delta formulas, and evidence manifest. Include the
pipeline figure and enough detail for reproduction.

### IV. Experimental Design

Describe synthetic generation, distractors, train/development/test separation,
baselines, metrics, machine configuration, model identifier, fixed seed, and
statistical procedure.

### V. Results

Present corpus statistics, retrieval results, delta correctness, evidence
completeness, and latency. Separate cold initialization from warm-query latency.
Report confidence intervals and counts where available.

### VI. Discussion

Answer each research question, explain why errors occurred, and discuss the
trade-off between strict eligibility and recall. State that transparency does
not imply clinical safety.

### VII. Limitations and Future Work

State synthetic-data, scale, embedding-model, benchmark-construction, and
non-clinical usability limitations. Future work may cover real de-identified
EHRs, clinician studies, FHIR/DICOM, imaging, privacy/security, adaptive ranking,
and only then biologically inspired temporal encoding.

### VIII. Conclusion

Restate measured findings and the narrow contribution. Do not introduce new
claims or promise clinical deployment.

## 4. Contribution paragraph template

> This work makes three contributions. First, it defines a comparability-first
> retrieval contract that separates candidate eligibility from semantic ranking
> in longitudinal record search. Second, it introduces an evidence manifest that
> makes each temporal delta reproducible from two dated source records. Third, it
> evaluates metadata-only, semantic-only, and hybrid retrieval using a seeded
> synthetic benchmark containing controlled non-comparable distractors.

Revise this paragraph only if all three contributions are implemented.

## 5. Novelty boundary

Do not claim novelty for using embeddings, RAG, vector search, a dashboard,
clinical timelines, or arithmetic trends. Claim the operational definition and
evaluation of comparability, the order of eligibility-before-ranking, and the
source-linked output contract.

## 6. Pre-submission checklist

- Conference scope and current portal deadline independently verified
- Current IEEE template and page limit used
- Author/anonymity instructions followed
- Every citation exists and supports its sentence
- All result numbers trace to exported experiment artifacts
- Figures readable at final column width
- No patient data or identifying information included
- Limitations and synthetic-data disclaimer visible
- PDF fonts embedded and portal validation passed
- Source code availability statement matches actual repository access

