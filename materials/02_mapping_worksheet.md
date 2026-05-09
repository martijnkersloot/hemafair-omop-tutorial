# Session 2: Mapping HemaFAIR Registry Data to OMOP
**Duration:** 60 minutes | **Format:** Group exercise (paper / post-its)

---

## Background

You have registry data from the HemaFAIR project, covering patients with rare haematological conditions (thalassaemia, sickle cell disease). The data was collected in REDCap and exported as a CSV. Before you can load it into an OMOP database, you need to decide:

1. **Which OMOP table** does each source field belong to?
2. **What kind of concept** will represent it — a condition, a measurement, an observation, a procedure?

You do _not_ need to find the exact concept ID yet — that's Session 3.

---

## OMOP Table Reference Card

| OMOP Table | What belongs here |
|------------|------------------|
| **PERSON** | Demographics: date of birth, sex, race |
| **CONDITION_OCCURRENCE** | Diagnoses, diseases, symptoms |
| **MEASUREMENT** | Numeric lab results, vital signs, imaging values with a unit |
| **OBSERVATION** | Categorical or textual clinical findings; country of birth; genetic variants; survey answers |
| **PROCEDURE_OCCURRENCE** | Surgical procedures, therapeutic interventions |
| **DRUG_EXPOSURE** | Medications (note: we won't use this table today) |

**Rule of thumb:**
- Has a numeric value + unit? → MEASUREMENT
- Is a yes/no disease or diagnosis? → CONDITION_OCCURRENCE
- Is a treatment or surgery? → PROCEDURE_OCCURRENCE
- Everything else that is clinically relevant? → OBSERVATION
- Is it about the patient themselves? → PERSON

---

## Part A — Domain Identification (groups, ~30 min)

For each source field below, fill in the table:

1. Which **OMOP domain** does it belong to? _(Person / Condition / Measurement / Observation / Procedure)_
2. Which **OMOP table** would you insert it into?
3. Brief **reasoning** — why did you choose that table?

Use the table reference card above. Discuss within your group — there may be fields where reasonable people disagree.

---

### Worksheet

| # | Source field | OMOP domain | OMOP table | Reasoning |
|---|-------------|-------------|-----------|-----------|
| 1 | Patient's date of birth | | | |
| 2 | Patient's sex at birth | | | |
| 3 | Diagnosis retained by the specialised centre _(e.g. Beta-thalassaemia, Sickle cell disease)_ | | | |
| 4 | Hypopituitarism _(Yes / No)_ | | | |
| 5 | Ferritin serum _(ng/mL)_ | | | |
| 6 | Cardiac iron T2\* _(milliseconds)_ | | | |
| 7 | Cirrhosis _(Yes confirmed / Unknown / No)_ | | | |
| 8 | Patient's country of birth | | | |
| 9 | Does the patient require regular or occasional transfusions? | | | |
| 10 | HBB Allele 1 _(b+, b0, b++)_ | | | |
| 11 | Is the patient on chelation treatment? _(Yes / No)_ | | | |
| 12 | Has the spleen been removed? _(Yes totally / Yes partially / No)_ | | | |
| 13 | Drug compliance _(Poor / Good / Excellent)_ | | | |
| 14 | Vitamin D deficiency _(Yes confirmed / No)_ | | | |
| 15 | Serum iron _(μg/dL)_ | | | |

---

## Bonus question

Look at field **#10** (HBB Allele 1). You decided on a domain — but do you think a standard concept exists in SNOMED or LOINC for a specific HBB allele variant like "b+"? What would you do if there is no standard concept?

_Write your answer here:_

---

## Part B — Debrief (full group, ~20 min)

Your trainer will collect answers on the shared OMOP table diagram on the board.

Discussion points:
- Did your group agree or disagree on any fields? Which ones?
- **Field #7** (Cirrhosis): could this be both a Condition and a Measurement? Why?
- **Field #10** (HBB Allele 1): what do you do when no standard concept exists?
- Why does OMOP store both `condition_concept_id` and `condition_source_value`?

---

## Answer Key _(for trainer only — do not distribute)_

| # | Source field | Domain | Table | Notes |
|---|-------------|--------|-------|-------|
| 1 | Date of birth | Person | PERSON | year/month/day split into separate columns |
| 2 | Sex at birth | Person | PERSON | gender_concept_id: Male=8507, Female=8532 |
| 3 | Diagnosis | Condition | CONDITION_OCCURRENCE | SNOMED concepts for each diagnosis |
| 4 | Hypopituitarism | Condition | CONDITION_OCCURRENCE | Inserted only where value = 'Yes' |
| 5 | Ferritin serum | Measurement | MEASUREMENT | concept 37208753, unit ng/mL = 8842 |
| 6 | Cardiac T2* | Measurement | MEASUREMENT | concept_id = 0 (no OMOP concept); unit ms = 9593 |
| 7 | Cirrhosis | Condition | CONDITION_OCCURRENCE | Also defensible as MEASUREMENT — discuss |
| 8 | Country of birth | Observation | OBSERVATION | SNOMED country concepts exist |
| 9 | Transfusion status | Observation | OBSERVATION | Categorical answer, no numeric value |
| 10 | HBB Allele 1 | Observation | OBSERVATION | concept_id = 0; value stored in value_as_string |
| 11 | Chelation treatment | Procedure | PROCEDURE_OCCURRENCE | concept 4068544 |
| 12 | Splenectomy | Procedure | PROCEDURE_OCCURRENCE | Only where 'Yes, totally' |
| 13 | Drug compliance | Observation | OBSERVATION | Two separate observations: poor vs. good/excellent |
| 14 | Vitamin D deficiency | Condition | CONDITION_OCCURRENCE | concept 436070 |
| 15 | Serum iron | Measurement | MEASUREMENT | concept 4097596, unit ug/dL = 8837 |

---

_In Session 3 you will use ATHENA to find the concept IDs for selected fields._
_In Session 5 you will write the SQL to load all of this into your OMOP database._
