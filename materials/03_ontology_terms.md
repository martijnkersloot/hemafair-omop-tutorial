# Session 3: Identifying and Selecting Ontology Terms
**Duration:** 30 minutes | **Format:** 15 min lecture + 15 min hands-on

---

## Slide 1 — Why Standard Terminology?

Two hospitals record the same condition:
- Hospital A: "Beta thal major"
- Hospital B: "β-thalassaemia, transfusion-dependent"
- ORPHA code: 848

Without a shared concept, a cross-hospital query finds zero overlapping patients.

**Standard terminology solves this:** both map to SNOMED CT concept `65959000` — Beta-thalassemia.

---

## Slide 2 — The Vocabulary Landscape

| Vocabulary | Domain | Scope |
|-----------|--------|-------|
| **SNOMED CT** | Conditions, procedures, findings | Broad clinical coverage |
| **LOINC** | Lab tests, measurements, surveys | Tests and observations |
| **RxNorm** | Drugs, ingredients, dose forms | US-focused drug naming |
| **MedDRA** | Adverse events, regulatory | Drug safety reporting |
| **ICD-10** | Diagnoses (billing) | Source coding, non-standard in OMOP |
| **HGNC** | Genes | Not in OMOP — use value_as_string |

**In OMOP:** ICD-10 codes are _source_ codes. They get mapped to SNOMED when you query.

---

## Slide 3 — Standard vs. Classification Concepts

Each concept in OMOP has a `standard_concept` flag:

| Flag | Meaning | Use in ETL |
|------|---------|-----------|
| **S** (Standard) | Use this for `[table]_concept_id` | ✅ Yes |
| **C** (Classification) | Parent/grouper concept | ❌ No — too broad |
| _(blank)_ | Non-standard / source concept | ❌ No — use source_value |

**Rule:** Always pick concepts with `standard_concept = 'S'` for the concept_id column.

**Speaker note:** A common mistake is picking an ICD-10 code directly. It won't break anything, but network queries won't find your patients.

---

## Slide 4 — ATHENA: The Vocabulary Browser

**URL:** https://athena.ohdsi.org

Live demo — walk through:
1. Search for "Beta-thalassemia"
2. Filter by Domain = Condition, Standard Concept = Standard
3. Click on a result — show concept_id, vocabulary, class, validity dates
4. Show the hierarchy tab — ancestors and descendants

**What to look at:**
- `concept_id` — the number you put in your ETL
- `domain_id` — confirms which OMOP table to use
- `standard_concept` — must be S
- `valid_end_date` — avoid concepts that expired before your data was collected

---

## Slide 5 — Reading ATHENA Results

_[Screenshot placeholder: ATHENA search result for "Beta-thalassemia"]_

Key columns:
| Column | What to check |
|--------|--------------|
| Concept ID | Copy this into your ETL |
| Concept Name | Verify it matches your clinical intent |
| Domain | Should match your table choice from Session 2 |
| Vocabulary | SNOMED for conditions/procedures, LOINC for labs |
| Standard Concept | Must be S |
| Valid Start / End | End date should be 2099-12-31 for current concepts |

---

## Slide 6 — Concept Hierarchies

OMOP vocabulary tables include parent-child relationships:

```
Haemoglobin disorder (broad)
  └── Thalassemia (medium)
        ├── Alpha-thalassemia (specific)
        └── Beta-thalassemia (specific)  ← use this
              ├── Beta-thal major
              └── Beta-thal minor
```

- Queries using `CONCEPT_ANCESTOR` can find all descendants of a concept
- This enables "find all patients with any form of thalassaemia" without listing every variant
- In ETL: **always map to the most specific concept** your source data supports

---

## Slide 7 — When There Is No Standard Concept

Not every clinical value has a standard concept. What to do:

| Situation | What to do |
|-----------|-----------|
| No concept in any vocabulary | `concept_id = 0`, store original in `source_value` |
| ICD-10 code, no SNOMED equivalent | Map to SNOMED if possible; else `concept_id = 0` |
| Gene variant (e.g. HBB b+ allele) | `concept_id = 0`, use `value_as_string` for the allele, `value_source_value` for HGNC gene ID |
| MRI parameter not in LOINC | `concept_id = 0`, document clearly |

**concept_id = 0 is valid — it is not an error.** It means "I know this doesn't have a standard mapping."

---

## Slide 8 — Tricky Cases from the HemaFAIR Registry

| Source field | Challenge | Solution |
|-------------|-----------|---------|
| HBB Allele 1 (b+, b0) | No OMOP concept for specific allele variants | concept_id = 0; value_as_string = "b+"; value_source_value = "HGNC:4827" |
| Cardiac iron T2* (ms) | MRI parameter, limited LOINC coverage | concept_id = 0; unit_concept_id = 9593 (millisecond) |
| Patient's country of birth | SNOMED has country concepts | Search ATHENA: "Country of origin" → find per-country SNOMED concepts |
| Drug compliance (Poor/Good) | Categorical; two different concepts | Map to two separate OMOP concepts: poor compliance = 4292063, good = 4056965 |

---

## Slide 9 — Practical Tips

1. **Start with SNOMED** for conditions and procedures — broadest coverage
2. **Use LOINC** for lab tests and measurements
3. **Verify the domain** matches your table: a LOINC concept with domain "Measurement" should go in MEASUREMENT, not OBSERVATION
4. **Check valid_end_date**: avoid retired concepts (end date in the past)
5. **One concept per insert**: if a field maps to multiple concepts (like drug compliance → poor vs. good), write multiple INSERT statements with WHERE clauses
6. **Document concept_id = 0 decisions** — future you will thank present you

---

## Slide 10 — Hands-On: Concept Hunting

_(15 minutes, work in pairs)_

Using ATHENA (https://athena.ohdsi.org), find the **standard concept ID** for each of the following fields from the HemaFAIR registry. Record your answers in the table — you will use these IDs in the ETL exercise (Session 5).

| # | Field | What to search | concept_id | Vocabulary | Standard? |
|---|-------|---------------|-----------|-----------|----------|
| 1 | Sex: Male | "Male" — Domain: Gender | | | |
| 2 | Sex: Female | "Female" — Domain: Gender | | | |
| 3 | Beta-thalassaemia | "Beta-thalassemia" — Domain: Condition | | | |
| 4 | Ferritin serum | "Ferritin serum" — Domain: Measurement | | | |
| 5 | Chelation treatment | "Chelation" — Domain: Procedure | | | |
| 6 | Splenectomy (total) | "Splenectomy" — Domain: Procedure | | | |

**Bonus:** Search for "HBB" or "hemoglobin beta" — can you find a concept that covers the b+ allele variant? What do you conclude?

---

### Answer Key _(trainer only)_

| # | Field | concept_id | Vocabulary |
|---|-------|-----------|-----------|
| 1 | Male | 8507 | Gender |
| 2 | Female | 8532 | Gender |
| 3 | Beta-thalassaemia | 65959000 | SNOMED |
| 4 | Ferritin serum | 37208753 | LOINC |
| 5 | Chelation treatment | 4068544 | SNOMED |
| 6 | Splenectomy | 2834904 | CPT4 |

Bonus: No standard concept exists for b+ allele variants → concept_id = 0.

---

_In Session 5 you will paste these concept IDs into your ETL notebook._
