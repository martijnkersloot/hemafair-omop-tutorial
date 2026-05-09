# Session 1: Introduction to the OMOP Common Data Model
**Duration:** 30 minutes | **Format:** Lecture

---

## Slide 1 — The Problem: Clinical Data in Silos

- Every hospital, registry, and study stores data differently
  - Different column names, different coding systems, different date formats
- Result: you can't combine datasets without months of manual harmonisation
- Research questions that need 10,000 patients can't be answered from a single centre

**Speaker note:** Ask: "How many of you have tried to combine data from two sources and spent most of the time just aligning column names?" This is the everyday reality that OMOP solves.

---

## Slide 2 — The Vision: One Model, Many Sources

- What if every database looked the same structure-wise?
- You write a query once → run it on data from Amsterdam, Paris, Toronto — same result
- This is the promise of a **Common Data Model**

> "The OMOP CDM is a person-centric data model that represents clinical observations using a standardised structure and standardised vocabularies."

---

## Slide 3 — What is OMOP CDM?

- **OMOP** = Observational Medical Outcomes Partnership
- Developed by the **OHDSI** community (Observational Health Data Sciences and Informatics)
- Open standard: freely available, actively maintained
- Adopted by 300+ databases across 30+ countries
- Current version: **CDM 5.4**
- DDL, documentation, tools: [ohdsi.org](https://ohdsi.org) / [github.com/OHDSI](https://github.com/OHDSI)

---

## Slide 4 — The CDM at a Glance

_[Diagram: core table layout]_

```
                         ┌──────────────┐
                         │    PERSON    │
                         └──────┬───────┘
                                │
                   ┌────────────▼──────────────┐
                   │     OBSERVATION_PERIOD     │
                   └────────────┬──────────────┘
                                │
                   ┌────────────▼──────────────┐
                   │      VISIT_OCCURRENCE      │
                   └──┬─────┬──────┬───────┬───┘
                      │     │      │       │
          ┌───────────▼─┐ ┌─▼──┐ ┌─▼──┐ ┌─▼──────────────┐
          │  CONDITION  │ │MEAS│ │ OBS│ │   PROCEDURE    │
          │  OCCURRENCE │ │MENT│ │ERVA│ │   OCCURRENCE   │
          └─────────────┘ └────┘ │TION│ └────────────────┘
                                 └────┘
```

**Key idea:** Everything traces back to a person and a visit.

---

## Slide 5 — Core Tables Overview

| Table | What it stores |
|-------|---------------|
| PERSON | Demographics: DOB, sex, race, ethnicity |
| OBSERVATION_PERIOD | The time window a person is observed |
| VISIT_OCCURRENCE | Encounters: outpatient, inpatient, home visit |
| CONDITION_OCCURRENCE | Diagnoses and conditions |
| MEASUREMENT | Lab results, vital signs, imaging values |
| OBSERVATION | Other clinical findings that don't fit above |
| PROCEDURE_OCCURRENCE | Surgical procedures, treatments |
| DRUG_EXPOSURE | Prescriptions and administrations |

---

## Slide 6 — Standard Concepts: The Currency of OMOP

- Every clinical value gets a **concept_id** — a single integer
- Example: `8532` always means **Female**, regardless of source system
- Concept IDs come from standard terminologies (SNOMED CT, LOINC, RxNorm…)
- Stored in the `CONCEPT` vocabulary table in your database

**Two values always stored together:**
```
gender_concept_id  = 8532       ← standard, for queries
gender_source_value = "Female"  ← original, for audit
```

---

## Slide 7 — Standard Vocabularies

| Vocabulary | Used for | Example |
|-----------|---------|---------|
| SNOMED CT | Conditions, procedures, observations | Beta-thalassemia → 65959000 |
| LOINC | Lab tests, measurements | Ferritin serum → 2276-4 |
| RxNorm | Drugs | Hydroxyurea → 202462 |
| MedDRA | Adverse events | |
| ICD-10 | Source coding (non-standard in OMOP) | |

**Important:** ICD-10 codes are _source_ codes — they get mapped to SNOMED standard concepts.

**Speaker note:** This distinction — source code vs. standard concept — is the single most confusing thing for newcomers. Spend a moment on this.

---

## Slide 8 — Source vs. Standard: Why Both?

```
Source data (REDCap):           OMOP database:
"Beta-thalassemia"         →    condition_source_value = "Beta-thalassemia"
                           →    condition_concept_id   = 65959000  (SNOMED)
```

- **Source value**: what was in the original record → preserved for traceability
- **Standard concept**: what it means universally → used for analysis and network queries
- **concept_id = 0**: "we have no standard mapping" — valid, must be documented

---

## Slide 9 — The PERSON Table (Worked Example)

```sql
SELECT person_id, gender_concept_id, year_of_birth,
       person_source_value, gender_source_value
FROM omop.person
LIMIT 3;
```

| person_id | gender_concept_id | year_of_birth | person_source_value | gender_source_value |
|-----------|------------------|--------------|--------------------|--------------------|
| 1 | 8532 | 1957 | 9047185 | Female |
| 2 | 8507 | 2000 | 11639873 | Male |
| 3 | 8532 | 1985 | 7062535 | Female |

**Each patient appears exactly once.** Visits, conditions, measurements all link to `person_id`.

---

## Slide 10 — Event Tables: Same Pattern, Different Domain

All event tables share the same structure:
- `[table]_id` — surrogate primary key
- `person_id` — links to PERSON
- `[table]_concept_id` — the standard concept for what happened
- `[table]_date` — when it happened
- `visit_occurrence_id` — links to VISIT (optional but recommended)
- `[table]_source_value` — the original value from the source

```sql
SELECT condition_concept_id, condition_source_value, person_id
FROM omop.condition_occurrence LIMIT 3;
```

---

## Slide 11 — The Visit Backbone

- Every clinical event needs context: _when and where did this happen?_
- `VISIT_OCCURRENCE` provides that context
- All event tables have a `visit_occurrence_id` column
- Without visits, events float free — valid but less useful for analysis

**In the HemaFAIR registry:** no actual visit dates → we assign a single synthetic visit per person using the observation date. This is a common real-world pragmatic decision.

---

## Slide 12 — Real-World OMOP Use Cases

- **Network studies**: same phenotype definition run simultaneously on 20 databases across 10 countries
- **ATLAS**: drag-and-drop cohort builder on top of OMOP data
- **ACHILLES**: automated data quality and characterisation reports
- **Drug safety**: post-marketing surveillance across insurance claims + EHR data
- **COVID-19**: OHDSI ran one of the largest international observational studies in weeks, not years

---

## Slide 13 — OHDSI Ecosystem

| Tool | Purpose |
|------|---------|
| [ATHENA](https://athena.ohdsi.org) | Browse and download vocabularies |
| ATLAS | Cohort definition, incidence rates, patient-level prediction |
| ACHILLES | Database characterisation and data quality |
| WhiteRabbit | Scan source data structure |
| RabbitInAHat | Design source→OMOP field mappings |
| HADES (R) | Statistical analysis packages |

All open-source, all free.

---

## Slide 14 — What We'll Do Today

1. **Now (Session 2):** Look at the HemaFAIR registry data — decide which OMOP table each field belongs to
2. **Session 3:** Use ATHENA to find the right standard concept IDs
3. **Session 4:** Plan the ETL execution order and patterns
4. **Session 5:** Write and run the actual SQL to populate your OMOP database

By the end of today you will have a working OMOP database with real (synthetic) patient data.

---

## Slide 15 — Key Terms to Remember

| Term | Meaning |
|------|---------|
| CDM | Common Data Model — shared table structure |
| concept_id | Integer ID for a standard clinical concept |
| OHDSI | Community maintaining OMOP |
| ETL | Extract, Transform, Load — the process of converting source data to OMOP |
| source_value | Original value from the source system |
| Standard concept | A concept with domain and vocabulary approved for use in OMOP queries |
| concept_id = 0 | No standard mapping exists |

---

_End of Session 1. Questions before we look at the registry data?_
