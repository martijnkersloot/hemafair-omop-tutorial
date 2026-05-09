---
marp: true
theme: default
paginate: true
style: |
  section {
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 28px;
    background: #ffffff;
  }
  h1 {
    color: #1a5276;
    font-size: 44px;
    border-bottom: 3px solid #2e86c1;
    padding-bottom: 10px;
  }
  h2 { color: #1a5276; font-size: 36px; }
  h3 { color: #2e86c1; }
  section.title {
    background: #1a5276;
    color: white;
    text-align: center;
    justify-content: center;
  }
  section.title h1 { color: white; border-bottom: 3px solid #7fb3d3; font-size: 52px; }
  section.title h2 { color: #aed6f1; border: none; }
  section.warning {
    background: #fef9e7;
    border-left: 8px solid #f39c12;
  }
  table { width: 100%; font-size: 22px; }
  th { background: #1a5276; color: white; padding: 8px; }
  td { padding: 6px 8px; border-bottom: 1px solid #d5d8dc; }
  tr:nth-child(even) td { background: #eaf2ff; }
  code { background: #eaf2ff; padding: 2px 6px; border-radius: 4px; font-size: 22px; color: #1a5276; }
  pre { background: #f4f6f9; border-left: 4px solid #2e86c1; padding: 12px; font-size: 20px; }
  blockquote {
    border-left: 4px solid #2e86c1;
    background: #eaf2ff;
    padding: 12px 16px;
    margin: 12px 0;
  }
  footer { font-size: 18px; color: #888; }
---

<!-- _class: title -->

# Designing an ETL Workflow

## HemaFAIR Training School
### Session 4 · 30 minutes

---

<!-- footer: Session 4 — Designing an ETL Workflow -->

# What is ETL?

**Extract · Transform · Load**

| Step | What happens |
|------|-------------|
| **Extract** | Read source data — CSV, database, API |
| **Transform** | Clean, reshape, map to standard concepts |
| **Load** | Write into the target database (OMOP) |

**ETL vs. ELT:** In ETL you transform before loading. In ELT (common in cloud warehouses) you load raw data first, then transform in-place. Today we use ETL via a staging layer.

---

# The Staging Layer Pattern

> Don't go directly from source to OMOP.

```
CSV files
    ↓  (load as-is, no transformations)
import schema     ← staging layer
    ↓  (SQL: map, filter, reshape)
omop schema       ← standardised, concept-mapped
```

**Why?**
- Easy to re-run — truncate OMOP, re-apply transforms
- Source data preserved for debugging
- Can inspect intermediate state with `SELECT`
- No data loss if a transform fails halfway

---

# Table Dependency Order

OMOP tables reference each other via foreign keys.
**You must load them in order:**

```
1.  PERSON                    ← no dependencies
        ↓
2.  OBSERVATION_PERIOD        ← needs person_id
        ↓
3.  VISIT_OCCURRENCE          ← needs person_id
        ↓
4.  CONDITION_OCCURRENCE  ┐
    MEASUREMENT           ├── all need person_id
    OBSERVATION           │   + visit_occurrence_id
    PROCEDURE_OCCURRENCE  ┘
```

Inserting a CONDITION_OCCURRENCE before PERSON exists → **foreign key violation**.

---

# Surrogate Keys

OMOP requires integer primary keys. Your source IDs are not OMOP keys.

**Single INSERT — use `row_number()`:**
```sql
INSERT INTO omop.person (person_id, ...)
SELECT row_number() OVER () AS person_id, ...
FROM import.labels;
```

**Multiple INSERTs into the same table — use a sequence:**
```sql
CREATE SEQUENCE condition_id_seq START 1;

INSERT INTO omop.condition_occurrence (condition_occurrence_id, ...)
SELECT nextval('condition_id_seq'), ...
WHERE diagnosis = 'Beta-thalassemia';

INSERT INTO omop.condition_occurrence (condition_occurrence_id, ...)
SELECT nextval('condition_id_seq'), ...
WHERE hypopituitarism = 'Yes';
```

---

# CASE Statements for Concept Mapping

The most common transform pattern:

```sql
CASE source_column
    WHEN 'Male'   THEN 8507   -- SNOMED: Male
    WHEN 'Female' THEN 8532   -- SNOMED: Female
    ELSE 0                    -- unknown or unmapped
END AS gender_concept_id
```

**Rules:**
- Always include `ELSE 0` — never let an unmapped value cause NULL in a NOT NULL column
- Keep the source value in `gender_source_value` for traceability
- If you have many mappings, a lookup table is cleaner than a long CASE

---

# Conditional Loading — WHERE Clauses

Many registry fields are boolean flags — **only insert a row when the flag is true**.

```sql
-- Only insert if patient has hypopituitarism
INSERT INTO omop.condition_occurrence ( ... )
SELECT nextval('condition_id_seq'), ...
FROM import.labels l
JOIN omop.person p ON l."Record ID" = p.person_source_value
JOIN omop.visit_occurrence vo ON p.person_id = vo.person_id
WHERE l."Hypopituitarism" = 'Yes';
```

**Why?** A patient *without* osteoporosis should have **no** osteoporosis row in CONDITION_OCCURRENCE. Inserting a `concept_id = 0` row for every "No" answer is noise, not data.

---

# Handling Missing Data

Real clinical data has gaps. Plan for them **explicitly**.

| Situation | Pattern |
|-----------|---------|
| Numeric measurement is NULL | `WHERE field IS NOT NULL` — skip the row |
| Categorical value is unmapped | `ELSE 0` in CASE + source_value preserved |
| No standard concept exists | `concept_id = 0` + `value_as_string` or `value_source_value` |
| Date not available | Use a proxy date; document the decision |

> **Never silently drop data.** A missing measurement is different from a measurement that was never taken.

---

# The Standard JOIN Chain

Events need `person_id` and `visit_occurrence_id` from other tables.

```sql
FROM import.labels l
JOIN omop.person p
    ON l."Record ID" = p.person_source_value
JOIN omop.visit_occurrence vo
    ON p.person_id = vo.person_id
```

**Why join back through OMOP tables?**
- `import.labels` has source IDs
- OMOP tables have the surrogate keys you need
- `person_source_value` bridges the two worlds

---

# Data Quality Checks

After each INSERT, **verify your work**:

```sql
-- How many rows did we insert?
SELECT COUNT(*) FROM omop.condition_occurrence;

-- Any unmapped values still set to concept_id = 0?
SELECT condition_source_value, COUNT(*)
FROM omop.condition_occurrence
WHERE condition_concept_id = 0
GROUP BY 1;

-- Are all persons represented?
SELECT COUNT(DISTINCT person_id)
FROM omop.condition_occurrence;
```

Build verification into the workflow — don't just run INSERTs and hope.

---

<!-- _class: warning -->

# Common Pitfalls

| Pitfall | What happens | Fix |
|---------|-------------|-----|
| Wrong schema (`public` vs `omop`) | Data lands in wrong place | Always prefix: `omop.person` |
| Re-running without truncating | Duplicate rows, duplicate IDs | `TRUNCATE` or drop+recreate before re-run |
| Using ICD-10 as concept_id | Network queries miss patients | Map to Standard (S) SNOMED concept |
| NULL in NOT NULL column | Insert fails | `ELSE 0` in CASE, IS NOT NULL filters |
| Wrong date format | Dates become NULL or wrong year | Test `EXTRACT()` on a few rows first |
| Loading events before PERSON | Foreign key violation | Follow the dependency order |

---

# Today's Exercise: What's Given vs. What You Fill In

**Pre-filled (given to you):**
- Database connection + helper functions
- Registry data pre-loaded in `import` schema
- PERSON table — **complete with annotations** explaining every pattern
- OBSERVATION_PERIOD — complete as a second example

**You fill in (marked `-- TODO`):**
- VISIT_OCCURRENCE: 2 concept IDs
- CONDITION_OCCURRENCE: CASE mapping for 3 diagnoses, concept IDs for 3 comorbidities
- OBSERVATION: 4 country concept IDs, HGNC gene identifiers
- MEASUREMENT: 2 concept IDs + 1 unit concept ID
- PROCEDURE_OCCURRENCE: 2 procedure concept IDs

---

<!-- _class: title -->

# Any questions?

## Next: Session 5 — ETL Exercise
### 💻 Let's open the notebook

---
