# Architecture and Workflow

## 1. System pipeline

```text
Seeded synthetic records
        |
        v
Schema validation -> concept/unit normalization -> text embeddings
        |                                              |
        +---------------- persisted corpus ------------+
                                                       |
Current observation/query                              v
        |                                     candidate retrieval
        |                                              |
        +--> temporal + patient constraints -----------+
                                                       v
                                      comparability eligibility gate
                                                       |
                              +------------------------+------------------+
                              |                        |                  |
                         semantic score          recency score      context score
                              +------------------------+------------------+
                                                       v
                                             selected baseline
                                                       |
                                                       v
                                     deterministic delta engine
                                                       |
                                                       v
                                 evidence manifest + dashboard + metrics
```

## 2. Design principle

Eligibility and ranking are separate. Eligibility encodes whether two records
*may be compared*. Ranking chooses the best record among valid candidates. A
high semantic score must never override an incompatible concept, unit, site, or
time direction.

## 3. Components

### Data generator

Produces reproducible patients, observations, notes, distractors, and benchmark
queries. It also writes the known correct baseline ID for each query.

### Normalizer

Converts concept aliases to a canonical concept and supported units to a
canonical value. The initial unit map should stay small and fully tested.

Recommended concepts:

- creatinine: mg/dL and umol/L, canonical mg/dL;
- glucose: mg/dL and mmol/L, canonical mg/dL;
- lesion diameter: mm and cm, canonical mm, with anatomical site required;
- systolic blood pressure: mmHg;
- HbA1c: percent.

### Embedding index

Encodes the short note and normalized context text. Persist record IDs and the
embedding matrix locally. For this corpus, NumPy cosine similarity is sufficient
and makes the experiment transparent; a hosted vector database is unnecessary.

### Retrieval strategies

**Metadata-only:** filter patient, earlier timestamp, and concept; choose the most
recent compatible record.

**Semantic-only:** filter patient and earlier timestamp; rank all remaining notes
by cosine similarity. This intentionally permits semantically relevant but
non-comparable candidates and serves as a baseline.

**Hybrid:** apply all comparability gates, then rank eligible candidates:

```text
hybrid_score = 0.50 * semantic_similarity
             + 0.30 * recency_score
             + 0.20 * context_match
```

Use fixed weights in the main experiment. Do not tune them on the test queries.
Break ties by latest timestamp, then lexicographic record ID.

One transparent recency function is:

```text
recency_score = exp(-elapsed_days / 365)
```

Context match is 1.0 for exact normalized condition/anatomical context, 0.5 for
partially specified context, and 0.0 for mismatch. An anatomical mismatch is an
eligibility failure when site is mandatory.

### Delta engine

For canonical current value `c`, baseline value `b`, and positive elapsed days
`t`:

```text
absolute_change = c - b
percentage_change = ((c - b) / abs(b)) * 100  when b != 0
change_per_day = (c - b) / t
```

Return `undefined` with a reason when percentage change cannot be calculated.
Do not infer whether a change is clinically good, bad, significant, or causal.

### Evidence manifest

The result object includes current and baseline IDs, original and canonical
values, timestamps, elapsed days, formula version, retrieval method, component
scores, rejected-candidate reasons, and warnings.

### Dashboard

Use one work-focused screen:

- sidebar: patient, current record, query, and retrieval method;
- summary band: baseline date and deterministic delta;
- timeline: selected concept over time;
- evidence table: exact source rows and normalized values;
- retrieval details: score components and rejection reasons;
- persistent research-use warning.

## 4. Failure behavior

- No valid earlier record: return `NO_COMPARABLE_BASELINE`.
- Unsupported conversion: return `INCOMPATIBLE_UNIT`.
- Same/future timestamp: reject candidate.
- Zero baseline: omit percentage change but retain absolute change.
- Missing site for site-dependent concept: return `INSUFFICIENT_CONTEXT`.
- Missing embedding: allow metadata-only retrieval and identify degraded mode.

## 5. Reproducibility contract

All generated data, query splits, score weights, model names, and random seeds
must be configuration values. Evaluation output must include a configuration
snapshot and a hash of the generated corpus.

