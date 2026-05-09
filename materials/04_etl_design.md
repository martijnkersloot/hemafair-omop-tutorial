# Session 4: Designing an ETL Workflow
**Duration:** 30 minutes | **Format:** Lecture (with discussion)

---

## Slide 1 — What Is ETL?

**ETL = Extract, Transform, Load**

| Step | What happens |
|------|-------------|
| **Extract** | Read source data (CSV, database, API) |
| **Transform** | Clean, reshape, map to standard concepts |
| **Load** | Write into the target database (OMOP) |

**ETL vs. ELT:** In ETL you transform before loading. In ELT (common in cloud warehouses) you load raw data first, then transform in-place. Today we do ETL via a staging layer.

---

## Slide 2 — The Staging Layer Pattern

**Don't go directly from source to OMOP.**

```
CSV files
    ↓  (load as-is)
import schema       ← staging layer: raw, no transformations yet
    ↓  (SQL transforms)
omop schema         ← standardised, concept-mapped
```

**Why a staging layer?**
- Easy to re-run: truncate OMOP tables, re-apply transforms
- Source data preserved for debugging
- Can inspect intermediate state with SELECT queries
- No data loss if a transform breaks halfway

---

## Slide 3 — Table Dependency Order

OMOP tables reference each other via foreign keys. You _must_ load them in order:

```
1. PERSON                    ← no dependencies
2. OBSERVATION_PERIOD        ← needs person_id
3. VISIT_OCCURRENCE          ← needs person_id + observation_period
4. CONDITION_OCCURRENCE  ┐
   MEASUREMENT           ├── all need person_id + visit_occurrence_id
   OBSERVATION           │
   PROCEDURE_OCCURRENCE  ┘
```

If you try to insert a CONDITION_OCCURRENCE before the PERSON row exists → foreign key violation.

---

## Slide 4 — Surrogate Keys

OMOP requires integer primary keys (person_id, condition_occurrence_id, etc.).  
Your source system uses its own IDs (Record ID: 9047185) — these are **not** OMOP keys.

**Two approaches:**

```sql
-- 1. row_number() for a single INSERT
INSERT INTO omop.person (person_id, ...)
SELECT row_number() OVER () AS person_id, ...
FROM import.labels;

-- 2. Sequence for multiple INSERT statements into the same table
CREATE SEQUENCE condition_id_seq START 1;

INSERT INTO omop.condition_occurrence (condition_occurrence_id, ...)
SELECT nextval('condition_id_seq'), ...
WHERE diagnosis = 'Beta-thalassaemia';

INSERT INTO omop.condition_occurrence (condition_occurrence_id, ...)
SELECT nextval('condition_id_seq'), ...
WHERE hypopituitarism = 'Yes';
```

Use `row_number()` when you load a table in a single INSERT, and sequences when you need multiple batches.

---

## Slide 5 — CASE Statements for Concept Mapping

The most common transform pattern: map a source value to a concept_id.

```sql
CASE source_column
    WHEN 'Male'             THEN 8507
    WHEN 'Female'           THEN 8532
    ELSE 0   -- unknown or unmapped
END AS gender_concept_id
```

**Rules:**
- Always include an `ELSE 0` — never let an unmapped value cause a NULL in a NOT NULL column
- Keep the source value in `gender_source_value` for traceability
- If you have more than ~5 mappings, consider a lookup table instead

---

## Slide 6 — Conditional Loading (WHERE Clauses)

Many registry fields are boolean flags — only insert a row when the flag is true.

```sql
-- Only insert if patient has hypopituitarism
INSERT INTO omop.condition_occurrence ( ... )
SELECT nextval('condition_id_seq'), ...
FROM import.labels l
JOIN omop.person p ON l."Record ID" = p.person_source_value
WHERE l."Hypopituitarism" = 'Yes';
```

**Why conditional?**
- A patient without osteoporosis should have _no_ osteoporosis row in CONDITION_OCCURRENCE
- Inserting a row with concept_id = 0 for every "No" answer is noise, not data

---

## Slide 7 — Handling Missing Data

Real clinical data has gaps. Plan for them explicitly.

| Situation | Pattern |
|-----------|---------|
| Numeric measurement is NULL | `WHERE field IS NOT NULL` — skip the row |
| Categorical value is unmapped | `ELSE 0` in CASE + source_value preserved |
| No standard concept exists | `concept_id = 0` + `value_as_string` or `value_source_value` |
| Date not available | Use a proxy date (e.g. observation date); document the decision |

**Never silently drop data.** A missing measurement is different from a measurement that was never taken — both are valid, but record them consistently.

---

## Slide 8 — The JOIN Pattern

Events in OMOP need person_id and visit_occurrence_id, which live in other tables. Standard join chain:

```sql
FROM import.labels l
JOIN omop.person p
    ON l."Record ID" = p.person_source_value
JOIN omop.visit_occurrence vo
    ON p.person_id = vo.person_id
```

**Why join back through OMOP tables?**
- `import.labels` has source IDs; OMOP tables have the surrogate keys you need
- Joining on `person_source_value` bridges the two worlds
- Every event table needs at minimum the `person_id` join

---

## Slide 9 — Sequences for Multi-Batch Inserts

When you insert into the same table multiple times (e.g. many different conditions), use a sequence to keep IDs unique across batches:

```sql
CREATE SEQUENCE condition_id_seq START 1;

-- Batch 1: primary diagnosis
INSERT INTO omop.condition_occurrence (condition_occurrence_id, ...)
SELECT nextval('condition_id_seq'), ...

-- Batch 2: Vitamin D deficiency
INSERT INTO omop.condition_occurrence (condition_occurrence_id, ...)
SELECT nextval('condition_id_seq'), ...

-- And so on for each condition
```

If you use `row_number()` across multiple INSERTs, IDs will collide and the second batch will fail.

---

## Slide 10 — Data Quality Checks

After each INSERT, verify your work:

```sql
-- How many rows did we insert?
SELECT COUNT(*) FROM omop.condition_occurrence;

-- Are there concept_id = 0 that we need to investigate?
SELECT condition_source_value, COUNT(*)
FROM omop.condition_occurrence
WHERE condition_concept_id = 0
GROUP BY condition_source_value;

-- Are all persons represented?
SELECT COUNT(DISTINCT person_id) FROM omop.condition_occurrence;
```

**Build verification into the workflow** — don't just run inserts and hope for the best.

---

## Slide 11 — Common Pitfalls

| Pitfall | What happens | Prevention |
|---------|-------------|-----------|
| Inserting into public instead of omop schema | Tables exist but are wrong | Always specify `schema.table` |
| Re-running without truncating | Duplicate rows, duplicate IDs | Truncate or drop+recreate before re-running |
| Using ICD-10 as concept_id | Queries miss patients in network | Always map to Standard (S) concepts |
| NULL in NOT NULL column | Insert fails with constraint violation | ELSE 0 in CASE, IS NOT NULL filters |
| Wrong date format | Dates silently become NULL or wrong year | Test with EXTRACT() on a few rows first |
| Loading events before PERSON | Foreign key violation | Follow the dependency order |

---

## Slide 12 — Today's Exercise: What's Given vs. What You Fill In

**Pre-filled (given to you):**
- Database connection and helpers
- Import schema with source CSVs loaded
- PERSON table — complete, with annotations explaining every pattern
- OBSERVATION_PERIOD — complete, as a second example

**You fill in:**
- VISIT_OCCURRENCE: 2 concept IDs
- CONDITION_OCCURRENCE: CASE mapping for 3 diagnoses, concept IDs for 3 comorbidities
- OBSERVATION: 4 country concept IDs, HGNC gene identifiers
- MEASUREMENT: 2 concept IDs + 1 unit concept ID
- PROCEDURE_OCCURRENCE: 2 procedure concept IDs

Use the concept IDs you found in Session 3 as a starting point. ATHENA is still open.

---

_Let's open the notebook._
