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
  h2 {
    color: #1a5276;
    font-size: 36px;
  }
  h3 { color: #2e86c1; }
  section.title {
    background: #1a5276;
    color: white;
    text-align: center;
    justify-content: center;
  }
  section.title h1 {
    color: white;
    border-bottom: 3px solid #7fb3d3;
    font-size: 52px;
  }
  section.title h2 { color: #aed6f1; border: none; }
  table { width: 100%; font-size: 22px; }
  th { background: #1a5276; color: white; padding: 8px; }
  td { padding: 6px 8px; border-bottom: 1px solid #d5d8dc; }
  tr:nth-child(even) td { background: #eaf2ff; }
  code { background: #eaf2ff; padding: 2px 6px; border-radius: 4px; color: #1a5276; }
  blockquote {
    border-left: 4px solid #2e86c1;
    background: #eaf2ff;
    padding: 12px 16px;
    margin: 12px 0;
    font-style: italic;
  }
  .highlight { color: #c0392b; font-weight: bold; }
  footer { font-size: 18px; color: #888; }
---

<!-- _class: title -->

# Introduction to the OMOP Common Data Model

## HemaFAIR Training School
### Session 1 · 30 minutes

---

<!-- footer: Session 1 — Introduction to OMOP CDM -->

# The Problem: Clinical Data in Silos

Every hospital stores data differently

- Different column names, different coding systems, different date formats
- Combining two datasets often takes months of manual work
- Research questions that need 10 000 patients can't be answered from one centre

> "We had the data. We just couldn't combine it."

---

# A Glimpse of the Chaos

| Source | Field name | Value |
|--------|-----------|-------|
| Hospital A | `sex` | `M` |
| Hospital B | `patient_gender` | `Male` |
| Registry C | `gender_code` | `1` |
| Your study | `Sex at birth` | `Male` |

All mean the same thing. None are compatible out of the box.

---

# The Vision: One Model, Many Sources

What if every database **looked the same structurally**?

- You write a query **once**
- Run it on data from Amsterdam, Paris, Toronto
- Get the same result

This is the promise of a **Common Data Model (CDM)**

---

# What is OMOP CDM?

- **OMOP** = Observational Medical Outcomes Partnership
- Developed and maintained by the **OHDSI community**
  (Observational Health Data Sciences and Informatics)
- Open standard — freely available, actively maintained
- Adopted by **300+ databases** across **30+ countries**
- Current version: **CDM 5.4**

📎 [ohdsi.org](https://ohdsi.org) · [github.com/OHDSI/CommonDataModel](https://github.com/OHDSI/CommonDataModel)

---

# The CDM at a Glance

```
              ┌──────────────┐
              │    PERSON    │
              └──────┬───────┘
                     │
        ┌────────────▼──────────────┐
        │      OBSERVATION_PERIOD   │
        └────────────┬──────────────┘
                     │
        ┌────────────▼──────────────┐
        │      VISIT_OCCURRENCE     │
        └──┬──────┬──────┬──────┬───┘
           │      │      │      │
     CONDITION  MEAS-  OBSER- PROCEDURE
     OCCURRENCE UREMENT VATION OCCURRENCE
```

**Everything traces back to a person and a visit.**

---

# Core Tables Overview

| Table | What it stores |
|-------|---------------|
| PERSON | Demographics: date of birth, sex, race |
| OBSERVATION_PERIOD | The time window a person is observed |
| VISIT_OCCURRENCE | Encounters: outpatient, inpatient, home visit |
| CONDITION_OCCURRENCE | Diagnoses and conditions |
| MEASUREMENT | Lab results, vital signs, imaging values |
| OBSERVATION | Other clinical findings |
| PROCEDURE_OCCURRENCE | Treatments and surgical procedures |
| DRUG_EXPOSURE | Prescriptions and administrations |

---

# Standard Concepts: The Currency of OMOP

Every clinical value gets a **concept_id** — a single integer

> `8532` always means **Female**, regardless of source system

Concept IDs come from standard terminologies stored in your database:

```
CONCEPT table
  concept_id │ concept_name │ domain_id │ vocabulary_id
  ───────────┼──────────────┼───────────┼─────────────
  8532       │ Female       │ Gender    │ Gender
  8507       │ Male         │ Gender    │ Gender
  65959000   │ Beta-thalassemia │ Condition │ SNOMED
```

---

# Source vs. Standard: Two Values, Always Together

```sql
-- In OMOP you always store both:
gender_source_value  = 'Female'  -- original, for audit & traceability
gender_concept_id    = 8532      -- standard, for queries & network studies
```

| | Purpose |
|--|---------|
| **source_value** | What was in the original record |
| **concept_id** | What it means universally |
| **concept_id = 0** | No standard mapping exists — valid, not an error |

---

# Standard Vocabularies

| Vocabulary | Used for | Example |
|-----------|---------|---------|
| **SNOMED CT** | Conditions, procedures, findings | Beta-thalassemia → 65959000 |
| **LOINC** | Lab tests, measurements | Ferritin serum → 2276-4 |
| **RxNorm** | Drugs, ingredients | Hydroxyurea → 202462 |
| **MedDRA** | Adverse events | Drug safety reporting |
| **ICD-10** | Source coding (billing) | Non-standard in OMOP |

⚠️ ICD-10 codes are **source codes** — they get mapped to SNOMED when you query.

---

# The PERSON Table — Worked Example

```sql
SELECT person_id, gender_concept_id, year_of_birth,
       person_source_value, gender_source_value
FROM omop.person LIMIT 3;
```

| person_id | gender_concept_id | year_of_birth | person_source_value | gender_source_value |
|-----------|-----------------|--------------|--------------------|--------------------|
| 1 | 8532 | 1957 | 9047185 | Female |
| 2 | 8507 | 2000 | 11639873 | Male |
| 3 | 8532 | 1985 | 7062535 | Female |

**Each patient appears exactly once.**

---

# Event Tables: The Same Pattern, Different Domain

All event tables share the same structure:

| Column | Purpose |
|--------|---------|
| `[table]_id` | Surrogate primary key |
| `person_id` | Links to PERSON |
| `[table]_concept_id` | The standard concept for what happened |
| `[table]_date` | When it happened |
| `visit_occurrence_id` | Context: links to VISIT |
| `[table]_source_value` | Original value from source |

---

# The Visit Backbone

Every clinical event needs context: **when and where did this happen?**

- `VISIT_OCCURRENCE` provides that context
- All event tables have a `visit_occurrence_id` column
- Without visits, events float free — valid, but less useful

**In the HemaFAIR registry:**
No actual visit dates → we assign a single synthetic visit per person.
This is a common pragmatic decision in registry data.

---

# Real-World OMOP Use Cases

- **Network studies**: same cohort definition run simultaneously on 20 databases across 10 countries
- **ATLAS**: drag-and-drop cohort builder — no SQL required
- **ACHILLES**: automated data quality and characterisation reports
- **Drug safety**: post-marketing surveillance across insurance claims + EHR data
- **COVID-19**: OHDSI ran one of the largest international observational studies in weeks, not years

---

# The OHDSI Ecosystem

| Tool | Purpose |
|------|---------|
| [ATHENA](https://athena.ohdsi.org) | Browse and download vocabularies |
| ATLAS | Cohort definition, incidence, prediction |
| ACHILLES | Database characterisation and data quality |
| WhiteRabbit | Scan source data structure |
| RabbitInAHat | Design source→OMOP field mappings |
| HADES (R) | Statistical analysis packages |

All **open-source**, all **free**.

---

# What We'll Do Today

1. **Session 2 (now):** Look at the HemaFAIR registry data — decide which OMOP table each field belongs to ✏️
2. **Session 3:** Use ATHENA to find the right standard concept IDs 🔍
3. **Session 4:** Plan the ETL execution order and SQL patterns 📐
4. **Session 5:** Write and run the actual SQL to populate your database 💻

**By the end of today you will have a working OMOP database with real (synthetic) patient data.**

---

# Key Terms to Remember

| Term | Meaning |
|------|---------|
| CDM | Common Data Model — shared table structure |
| concept_id | Integer ID for a standard clinical concept |
| OHDSI | Community maintaining OMOP |
| ETL | Extract, Transform, Load |
| source_value | Original value from the source system |
| Standard concept | Approved for use in OMOP queries (flag = S) |
| concept_id = 0 | No standard mapping exists |

---

<!-- _class: title -->

# Any questions?

## Next: Session 2 — Mapping Exercise
### ✏️ Time to look at the data

---
