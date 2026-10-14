# AI Implementation Prompt

Use this document as the initial prompt for an AI coding model operating at the
repository root. Give the model access to the repository and a terminal. Do not
ask it to write the manuscript before it has generated verified results.

## Master prompt

```text
You are implementing MedDelta-RAG, a four-day research prototype and experiment.
Read AGENTS.md, README.md, and every file under docs/ before editing. Treat those
documents as the requirements. Inspect the repository and preserve existing work.

Objective
Build a local, deterministic pipeline that retrieves a clinically comparable
historical observation for a synthetic current observation, calculates temporal
change without generative arithmetic, and exposes exact source evidence. Then run
a controlled comparison of metadata-only, semantic-only, and comparability-first
hybrid retrieval. This is research software, not a medical device.

Non-negotiable scope
- Use only seeded synthetic records. Never use or request identifiable data.
- Do not provide diagnosis, treatment, prognosis, alerts, or clinical advice.
- Do not add imaging, FHIR/DICOM, hosted services, authentication, an LLM, an SNN,
  or cloud deployment.
- Keep dependencies and the interface small enough to finish by 30 July 2026.
- Do not invent experiment results, citations, tests, or completed work.

Preferred stack
- Python 3.11 with a pyproject.toml
- Streamlit, pandas, Plotly, NumPy, sentence-transformers, and pytest
- Persist embeddings as a NumPy matrix with a record-ID manifest
- Use a deterministic TF-IDF fallback only if the transformer model cannot be
  installed; record the actual encoder in all result manifests and the paper

Required structure
Create the structure in docs/02_PROJECT_SPECIFICATION.md. Keep domain code under
src/meddelta and scripts as thin command-line entry points. Do not put research
logic inside Streamlit callbacks.

Implementation order
1. Create pyproject.toml, package structure, configuration, and typed data models.
2. Implement seeded synthetic observations and benchmark queries with controlled
   distractors and development/test splits.
3. Implement schema validation, aliases, canonical units, and the small verified
   conversion map in docs/05_DATA_AND_API_SPECIFICATION.md.
4. Implement the comparability predicate as a pure function returning a decision
   and explicit reason code. Test every rule and boundary case.
5. Implement cached embeddings and cosine similarity with deterministic ranking.
6. Implement the metadata-only, semantic-only, and hybrid retrieval methods.
7. Implement deterministic delta formulas and evidence manifests. Test zero,
   negative, missing, future-date, same-date, incompatible-unit, and no-baseline
   cases.
8. Implement an experiment runner that evaluates every method on identical test
   queries and writes raw predictions, metrics, latency, and a run manifest.
9. Build one restrained Streamlit screen with patient/current-record selection,
   method control, summary delta, timeline, evidence table, score details, and the
   permanent text: "Research prototype - synthetic data - not for clinical use."
10. Document exact setup, generation, test, experiment, and dashboard commands.

Retrieval contract
- An eligible baseline has the same patient, is earlier than the current record,
  has the same normalized concept, uses a compatible canonical unit, has a
  parseable value, and matches anatomical site when site is required.
- Eligibility must run before hybrid ranking. Semantic similarity cannot override
  an eligibility failure.
- Use the fixed score and tie-breaking rules in
  docs/03_ARCHITECTURE_AND_WORKFLOW.md. Do not tune on held-out test queries.

Evaluation contract
- Generate at least 60 patients and 120 benchmark queries.
- Freeze and record the seed before the final test run.
- Compare all three methods using Baseline Selection Accuracy, Valid Pair Rate,
  Top-3 Hit Rate, MRR, Delta Exact Match, Evidence Completeness, median latency,
  p95 latency.
- Keep per-query predictions and rejected-candidate reasons for error analysis.
- Generate machine-readable CSV/JSON artifacts and Markdown or LaTeX-ready result
  tables from those artifacts.
- If the proposed method does not outperform a baseline, report that accurately
  and preserve the result.

Verification
- Run formatting/static checks if configured and run the full pytest suite.
- Run data generation twice with the same seed and verify matching corpus hashes.
- Run the final experiment from a clean generated-data directory.
- Smoke-test the Streamlit app and inspect it at desktop and narrow viewport sizes.
- Confirm all displayed deltas identify two source record IDs and no UI text
  presents a clinical interpretation.

Working behavior
- Work phase by phase and update a short implementation checklist.
- Before each phase, inspect relevant existing files.
- Make focused changes and do not overwrite unrelated user work.
- When blocked, diagnose the cause and choose the smallest in-scope fallback.
- After each phase, run the narrowest relevant tests; run all tests at the end.
- Continue through implementation, experiments, and documentation unless an
  action requires user credentials, real data, or external publication access.

Final report
Report implemented features, exact verification commands and outcomes, measured
experiment results, generated artifact locations, unresolved limitations, and
the command that starts the dashboard. Clearly separate measured facts from
future work.
```

## Follow-up prompt for paper generation

Use this only after the experiment artifacts exist:

```text
Read the repository documentation, source code, tests, run manifest, raw
predictions, and generated result tables. Draft an IEEE-style paper following
docs/07_PAPER_OUTLINE.md.

Rules:
- Use only measured values from data/results; never estimate or invent results.
- Verify every numerical claim against an artifact and identify its source file.
- Do not invent references. Mark missing citations as [CITATION NEEDED: topic].
- Describe all records as synthetic and the system as a research prototype.
- Do not claim clinical accuracy, patient benefit, safety, diagnosis, or hospital
  readiness.
- Explain that embeddings, RAG, and temporal dashboards are established; locate
  novelty in comparability-first eligibility, valid-pair evaluation, and the
  evidence manifest.
- Include methods detailed enough to reproduce the corpus, retrieval methods,
  scoring, metrics, and statistical analysis.
- Include negative findings and limitations.
- Produce the manuscript in the conference's current official IEEE template only
  after its page limit, anonymity policy, and submission requirements are given
  or independently verified.

Before writing the abstract and conclusion, prepare a claim-to-evidence table
mapping every proposed claim to a measured result or implementation artifact.
Remove any claim that lacks evidence.
```

## Minimal intervention prompts

Use these only when the model stops before completion:

```text
Continue with the next incomplete P0 item in docs/04_PROJECT_LIFECYCLE.md. Inspect
current repository state, preserve existing work, implement it, and run focused
tests. Do not expand scope.
```

```text
Run the reproducibility audit now: cleanly regenerate synthetic artifacts using
the recorded seed, run all tests and experiments, compare corpus hashes, and list
any paper claim that is not supported by a generated artifact.
```

## Information the human must supply

An AI model should not guess the following:

- official conference name and track;
- submission portal URL and exact deadline/time zone;
- IEEE template, page limit, and anonymity policy;
- author names, affiliations, ORCID identifiers, and acknowledgements;
- whether a public code URL can be included in an anonymous submission.
