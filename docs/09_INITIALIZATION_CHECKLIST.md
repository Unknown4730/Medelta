# Initialization and Delivery Checklist

## Research lock

- [ ] Conference identity, track, deadline, and time zone verified in the portal
- [ ] Paper title and contribution statement frozen
- [ ] RQ1-RQ3 accepted; RQ4 marked optional
- [ ] Synthetic-data-only and no-diagnosis scope accepted
- [ ] P0/P1/P2 priorities accepted

## Repository initialization

- [ ] Python 3.11 environment created
- [ ] `pyproject.toml` and locked dependency versions added
- [ ] Source, script, test, data, and documentation directories created
- [ ] Generated data, model cache, virtual environment, and secrets ignored
- [ ] Exact setup and execution commands documented
- [ ] Embedding model downloaded and cached before experiment day

## Data and logic

- [ ] Schema and status codes implemented
- [ ] Seeded generator creates at least 60 patients and 120 queries
- [ ] Development/test split and distractors validated
- [ ] Unit conversions verified by tests
- [ ] Comparability predicate tests cover every rejection reason
- [ ] Delta tests cover zero and invalid baselines
- [ ] Corpus hash is stable across repeated generation

## Retrieval and evaluation

- [ ] Metadata-only baseline implemented
- [ ] Semantic-only baseline implemented
- [ ] Hybrid method implemented without test-set tuning
- [ ] Raw rankings and rejection reasons retained
- [ ] Primary metrics match the evaluation specification
- [ ] Warm and cold latency measured separately
- [ ] Final run manifest contains configuration and environment metadata
- [ ] Result tables generated directly from artifacts

## Demonstration

- [ ] Permanent synthetic-data/non-clinical warning visible
- [ ] Current and baseline source IDs visible
- [ ] Timeline and evidence table agree with source records
- [ ] Undefined and no-baseline states render clearly
- [ ] No generated diagnosis or clinical interpretation is shown
- [ ] Desktop and narrow-width layouts checked

## Paper

- [ ] Related-work references verified from scholarly sources
- [ ] Contributions match implemented and evaluated components
- [ ] Abstract written after final results
- [ ] Methods reproduce configuration and formulas
- [ ] Counts, confidence intervals, errors, and limitations reported
- [ ] Every result number cross-checked against an artifact
- [ ] No invented citations or clinical claims
- [ ] IEEE format, page limit, anonymity, and PDF checks completed

## Submission package

- [ ] Manuscript PDF
- [ ] Source files and figures
- [ ] Reproducibility README
- [ ] Tests passing from a clean setup
- [ ] Synthetic corpus, benchmark, run manifest, and result tables archived
- [ ] Portal metadata and author information proofread

