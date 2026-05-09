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
  section.handson {
    background: #eaf2ff;
  }
  section.handson h1 { color: #1a5276; }
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
  footer { font-size: 18px; color: #888; }
---

<!-- _class: title -->

# Identifying and Selecting Ontology Terms

## HemaFAIR Training School
### Session 3 · 30 minutes

---

<!-- footer: Session 3 — Identifying Ontology Terms -->

# Why Standard Terminology?

Two hospitals record the same condition:

| Hospital | How they recorded it |
|----------|---------------------|
| Hospital A | "Beta thal major" |
| Hospital B | "β-thalassaemia, transfusion-dependent" |
| Registry | ORPHA code: 848 |

Without a shared concept, a cross-hospital query finds **zero** overlapping patients.

**Standard terminology solves this:** all three map to SNOMED `65959000` — Beta-thalassemia.

---

# The Vocabulary Landscape

| Vocabulary | Domain | What it covers |
|-----------|--------|---------------|
| **SNOMED CT** | Conditions, procedures, findings | Broad clinical coverage |
| **LOINC** | Lab tests, measurements, surveys | Tests and observations |
| **RxNorm** | Drugs, ingredients, dose forms | Medication naming |
| **MedDRA** | Adverse events | Drug safety / regulatory |
| **ICD-10** | Diagnoses (billing) | Source coding — non-standard in OMOP |
| **HGNC** | Genes | Not in OMOP — use `value_as_string` |

---

# Standard vs. Classification Concepts

Each concept in OMOP has a `standard_concept` flag:

| Flag | Meaning | Use in ETL? |
|------|---------|------------|
| **S** — Standard | The right level of specificity | ✅ Yes — use for `concept_id` |
| **C** — Classification | Parent / grouper concept | ❌ Too broad |
| *(blank)* | Non-standard or source concept | ❌ Use `source_value` only |

> **Rule:** Always pick `standard_concept = 'S'` for the `[table]_concept_id` column.

**Common mistake:** Using an ICD-10 code directly as concept_id. It won't break things, but network queries won't find your patients.

---

# ATHENA: The Vocabulary Browser

## 🌐 athena.ohdsi.org

What ATHENA gives you:
- Search across all OMOP vocabularies at once
- Filter by domain, vocabulary, standard concept flag
- Browse concept hierarchies
- Check validity dates
- Download vocabulary files for your database

---

# Live Demo: Finding Beta-thalassemia

1. Go to **athena.ohdsi.org**
2. Search: `Beta-thalassemia`
3. Filter: **Domain** = Condition · **Standard Concept** = Standard
4. Click the top result
5. Note:
   - `concept_id` = **65959000**
   - Vocabulary = **SNOMED**
   - `standard_concept` = **S**
   - `valid_end_date` = **2099-12-31** ✅

---

# Reading an ATHENA Result

| Column | What to check |
|--------|--------------|
| **Concept ID** | Copy this number into your ETL |
| **Concept Name** | Verify it matches your clinical intent |
| **Domain** | Must match your table choice from Session 2 |
| **Vocabulary** | SNOMED for conditions/procedures, LOINC for labs |
| **Standard Concept** | Must be **S** |
| **Valid End Date** | Should be `2099-12-31` (not expired) |

---

# Concept Hierarchies

OMOP vocabularies include parent–child relationships:

```
Haemoglobin disorder  (broad)
  └── Thalassemia  (medium)
        ├── Alpha-thalassemia  (specific) ← use this
        └── Beta-thalassemia   (specific) ← use this
              ├── Beta-thal major
              └── Beta-thal minor
```

- Queries using `CONCEPT_ANCESTOR` can find **all descendants** of a concept
- This enables "find all patients with any form of thalassaemia" without listing every variant
- **In ETL: always map to the most specific concept your source data supports**

---

# When There Is No Standard Concept

Not every clinical value has a standard concept.

| Situation | What to do |
|-----------|-----------|
| No concept in any vocabulary | `concept_id = 0`, store original in `source_value` |
| ICD-10 code, no SNOMED equivalent | Map to SNOMED if possible; else `concept_id = 0` |
| Gene variant (e.g. HBB b+ allele) | `concept_id = 0`, allele in `value_as_string`, HGNC ID in `value_source_value` |
| MRI parameter not in LOINC | `concept_id = 0`, document clearly |

> **concept_id = 0 is valid — it is not an error.** It means "no standard mapping exists."

---

# Tricky Cases from the HemaFAIR Registry

| Source field | Challenge | Solution |
|-------------|-----------|---------|
| HBB Allele b+ | No OMOP concept for specific allele variants | `concept_id = 0` · `value_as_string = "b+"` · `value_source_value = "HGNC:4827"` |
| Cardiac iron T2* (ms) | MRI parameter, no LOINC concept | `concept_id = 0` · `unit_concept_id = 9593` (millisecond) |
| Country of birth | SNOMED has country concepts | Search ATHENA by country name |
| Drug compliance | Two categories → two concepts | Two separate INSERT statements with WHERE |

---

# Practical Tips

1. **Start with SNOMED** for conditions and procedures — broadest coverage
2. **Use LOINC** for lab tests and measurements
3. **Verify the domain** matches your table: a LOINC concept with domain "Measurement" should go in `MEASUREMENT`, not `OBSERVATION`
4. **Check `valid_end_date`** — avoid concepts that expired before your data collection
5. **Map to the most specific concept** your source data supports
6. **Document `concept_id = 0` decisions** — record what you tried

---

<!-- _class: handson -->

# 🔍 Hands-On: Concept Hunting

**15 minutes · Work in pairs · Open ATHENA: athena.ohdsi.org**

Find the standard concept ID for each field. Record them — you'll use these in Session 5.

| # | Field | What to search | concept_id | Vocabulary |
|---|-------|---------------|-----------|-----------|
| 1 | Sex: Male | "Male" · Domain: Gender | | |
| 2 | Sex: Female | "Female" · Domain: Gender | | |
| 3 | Beta-thalassaemia | "Beta-thalassemia" · Domain: Condition | | |
| 4 | Ferritin serum | "Ferritin serum" · Domain: Measurement | | |
| 5 | Chelation treatment | "Chelation" · Domain: Procedure | | |
| 6 | Splenectomy | "Splenectomy" · Domain: Procedure | | |

---

<!-- _class: handson -->

# 🔍 Bonus Question

Search ATHENA for **"HBB"** or **"hemoglobin beta chain"**.

Can you find a standard concept that covers the specific **b+ allele variant**?

What do you conclude? What would you do in the ETL?

---

# Debrief: Answers

| # | Field | concept_id | Vocabulary |
|---|-------|-----------|-----------|
| 1 | Male | **8507** | Gender |
| 2 | Female | **8532** | Gender |
| 3 | Beta-thalassaemia | **65959000** | SNOMED |
| 4 | Ferritin serum | **37208753** | LOINC |
| 5 | Chelation treatment | **4068544** | SNOMED |
| 6 | Splenectomy | **2834904** | CPT4 |

**Bonus:** No standard concept for b+ allele → `concept_id = 0`, store genotype in `value_as_string`, gene HGNC ID in `value_source_value`.

---

<!-- _class: title -->

# Any questions?

## Next: Session 4 — Designing an ETL Workflow
### 📐 How do we actually load the data?

---
