#!/usr/bin/env python3
"""
Build a completed OMOP database (answer key ETL) and clone it per trainee.

Strategy:
  1. Clone omop_vocab_template → omop_answers_template
  2. Run the full HemaFAIR ETL against that template
  3. Clone omop_answers_template → trainee_XX_answers for each trainee

Usage:
    python3 scripts/create_answer_dbs.py 30
    python3 scripts/create_answer_dbs.py 30 --start 1 --container hemafair_postgres
"""

import argparse
import os
import subprocess
import sys

VOCAB_TEMPLATE   = "omop_vocab_template"
ANSWERS_TEMPLATE = "omop_answers_template"

# ---------------------------------------------------------------------------
# ETL SQL — extracted from hemafair_omop_etl.ipynb (answer key)
# ---------------------------------------------------------------------------

CDM_SOURCE_SQL = """
INSERT INTO omop.cdm_source (
    cdm_source_name, cdm_source_abbreviation, cdm_holder,
    source_release_date, cdm_release_date,
    cdm_version_concept_id, vocabulary_version
)
VALUES (
    'HemaFAIR', 'HemaFAIR', 'HemaFAIR',
    '2026-05-06', '2026-05-06',
    756265,
    'v5.0 27-FEB-25'
);
"""

PERSON_SQL = """
INSERT INTO omop.person (
    person_id, gender_concept_id,
    year_of_birth, month_of_birth, day_of_birth,
    race_concept_id, ethnicity_concept_id,
    person_source_value, gender_source_value
)
SELECT
    row_number() OVER () AS person_id,
    CASE "Patient's sex at birth"
        WHEN 'Male'   THEN 8507
        WHEN 'Female' THEN 8532
        ELSE 0
    END,
    EXTRACT(YEAR  FROM TO_DATE("Patient's date of birth", 'DD/MM/YYYY'))::integer,
    EXTRACT(MONTH FROM TO_DATE("Patient's date of birth", 'DD/MM/YYYY'))::integer,
    EXTRACT(DAY   FROM TO_DATE("Patient's date of birth", 'DD/MM/YYYY'))::integer,
    0, 0,
    "Record ID"::text,
    "Patient's sex at birth"
FROM import.labels;
"""

OBSERVATION_PERIOD_SQL = """
INSERT INTO omop.observation_period (
    observation_period_id, person_id,
    observation_period_start_date, observation_period_end_date,
    period_type_concept_id
)
SELECT row_number() OVER (), person_id,
    '2026-05-12', '2026-05-12', 32809
FROM omop.person;
"""

VISIT_OCCURRENCE_SQL = """
INSERT INTO omop.visit_occurrence (
    visit_occurrence_id, person_id, visit_concept_id,
    visit_start_date, visit_start_datetime,
    visit_end_date, visit_end_datetime,
    visit_type_concept_id
)
SELECT row_number() OVER (), p.person_id,
    581476,
    op.observation_period_start_date, op.observation_period_start_date,
    op.observation_period_end_date,   op.observation_period_end_date,
    32809
FROM omop.person p
JOIN omop.observation_period op ON op.person_id = p.person_id;
"""

CONDITION_OCCURRENCE_SQL = [
    "CREATE SEQUENCE IF NOT EXISTS condition_id_seq START 1;",
    # Primary diagnosis
    """
INSERT INTO omop.condition_occurrence (
    condition_occurrence_id, person_id, condition_concept_id,
    condition_start_date, condition_start_datetime,
    condition_end_date, condition_end_datetime,
    condition_type_concept_id, visit_occurrence_id, condition_source_value
)
SELECT nextval('condition_id_seq'), p.person_id,
    CASE l."Diagnosis retained by the specialised centre"
        WHEN 'Alpha-thalassemia'   THEN 4287844
        WHEN 'Beta-thalassemia'    THEN 4278669
        WHEN 'Sickle cell disease' THEN 25518
        ELSE 0
    END,
    vo.visit_start_date, vo.visit_start_date,
    vo.visit_start_date, vo.visit_start_date,
    32865, vo.visit_occurrence_id,
    l."Diagnosis retained by the specialised centre"
FROM import.labels l
JOIN omop.person p ON l."Record ID"::text = p.person_source_value
JOIN omop.visit_occurrence vo ON p.person_id = vo.person_id;
""",
    # Hypopituitarism
    """
INSERT INTO omop.condition_occurrence (
    condition_occurrence_id, person_id, condition_concept_id,
    condition_start_date, condition_start_datetime,
    condition_end_date, condition_end_datetime,
    condition_type_concept_id, visit_occurrence_id, condition_source_value
)
SELECT nextval('condition_id_seq'), p.person_id, 4254542,
    vo.visit_start_date, vo.visit_start_date,
    vo.visit_start_date, vo.visit_start_date,
    32865, vo.visit_occurrence_id, l."Hypopituitarism"
FROM import.labels l
JOIN omop.person p ON l."Record ID"::text = p.person_source_value
JOIN omop.visit_occurrence vo ON p.person_id = vo.person_id
WHERE l."Hypopituitarism" = 'Yes';
""",
    # Infertile
    """
INSERT INTO omop.condition_occurrence (
    condition_occurrence_id, person_id, condition_concept_id,
    condition_start_date, condition_start_datetime,
    condition_end_date, condition_end_datetime,
    condition_type_concept_id, visit_occurrence_id, condition_source_value
)
SELECT nextval('condition_id_seq'), p.person_id, 4311387,
    vo.visit_start_date, vo.visit_start_date,
    vo.visit_start_date, vo.visit_start_date,
    32865, vo.visit_occurrence_id, l."Is the patient infertile?"
FROM import.labels l
JOIN omop.person p ON l."Record ID"::text = p.person_source_value
JOIN omop.visit_occurrence vo ON p.person_id = vo.person_id
WHERE l."Is the patient infertile?" = 'Yes';
""",
    # Acute viral hepatitis
    """
INSERT INTO omop.condition_occurrence (
    condition_occurrence_id, person_id, condition_concept_id,
    condition_start_date, condition_start_datetime,
    condition_end_date, condition_end_datetime,
    condition_type_concept_id, visit_occurrence_id, condition_source_value
)
SELECT nextval('condition_id_seq'), p.person_id, 4211974,
    vo.visit_start_date, vo.visit_start_date,
    vo.visit_start_date, vo.visit_start_date,
    32865, vo.visit_occurrence_id, l."Acute viral hepatitis"
FROM import.labels l
JOIN omop.person p ON l."Record ID"::text = p.person_source_value
JOIN omop.visit_occurrence vo ON p.person_id = vo.person_id
WHERE l."Acute viral hepatitis" = 'Yes';
""",
    # Vitamin D deficiency
    """
INSERT INTO omop.condition_occurrence (
    condition_occurrence_id, person_id, condition_concept_id,
    condition_start_date, condition_start_datetime,
    condition_end_date, condition_end_datetime,
    condition_type_concept_id, visit_occurrence_id, condition_source_value
)
SELECT nextval('condition_id_seq'), p.person_id, 436070,
    vo.visit_start_date, vo.visit_start_date,
    vo.visit_start_date, vo.visit_start_date,
    32865, vo.visit_occurrence_id, l."Vitamin D deficiency"
FROM import.labels l
JOIN omop.person p ON l."Record ID"::text = p.person_source_value
JOIN omop.visit_occurrence vo ON p.person_id = vo.person_id
WHERE l."Vitamin D deficiency" = 'Yes, confirmed';
""",
    # Osteoporosis
    """
INSERT INTO omop.condition_occurrence (
    condition_occurrence_id, person_id, condition_concept_id,
    condition_start_date, condition_start_datetime,
    condition_end_date, condition_end_datetime,
    condition_type_concept_id, visit_occurrence_id, condition_source_value
)
SELECT nextval('condition_id_seq'), p.person_id, 80502,
    vo.visit_start_date, vo.visit_start_date,
    vo.visit_start_date, vo.visit_start_date,
    32865, vo.visit_occurrence_id, l."Osteoporosis"
FROM import.labels l
JOIN omop.person p ON l."Record ID"::text = p.person_source_value
JOIN omop.visit_occurrence vo ON p.person_id = vo.person_id
WHERE l."Osteoporosis" = 'Yes, confirmed';
""",
    # Osteopenia
    """
INSERT INTO omop.condition_occurrence (
    condition_occurrence_id, person_id, condition_concept_id,
    condition_start_date, condition_start_datetime,
    condition_end_date, condition_end_datetime,
    condition_type_concept_id, visit_occurrence_id, condition_source_value
)
SELECT nextval('condition_id_seq'), p.person_id, 4195039,
    vo.visit_start_date, vo.visit_start_date,
    vo.visit_start_date, vo.visit_start_date,
    32865, vo.visit_occurrence_id, l."Osteopenia"
FROM import.labels l
JOIN omop.person p ON l."Record ID"::text = p.person_source_value
JOIN omop.visit_occurrence vo ON p.person_id = vo.person_id
WHERE l."Osteopenia" = 'Yes, confirmed';
""",
    # Acute chest syndrome
    """
INSERT INTO omop.condition_occurrence (
    condition_occurrence_id, person_id, condition_concept_id,
    condition_start_date, condition_start_datetime,
    condition_end_date, condition_end_datetime,
    condition_type_concept_id, visit_occurrence_id, condition_source_value
)
SELECT nextval('condition_id_seq'), p.person_id, 254062,
    vo.visit_start_date, vo.visit_start_date,
    vo.visit_start_date, vo.visit_start_date,
    32865, vo.visit_occurrence_id, l."Acute chest syndrome"
FROM import.labels l
JOIN omop.person p ON l."Record ID"::text = p.person_source_value
JOIN omop.visit_occurrence vo ON p.person_id = vo.person_id
WHERE l."Acute chest syndrome" = 'Yes, confirmed';
""",
]

OBSERVATION_SQL = [
    "CREATE SEQUENCE IF NOT EXISTS observation_id_seq START 1;",
    # Country of birth
    """
INSERT INTO omop.observation (
    observation_id, person_id, observation_concept_id,
    observation_date, observation_datetime,
    observation_type_concept_id, visit_occurrence_id, value_source_value
)
SELECT nextval('observation_id_seq'), p.person_id,
    CASE l."Patient's country of birth"
        WHEN 'Australia'      THEN 4199969
        WHEN 'Canada'         THEN 4200105
        WHEN 'Congo'          THEN 4202085
        WHEN 'Cyprus'         THEN 4152209
        WHEN 'Greece'         THEN 4151604
        WHEN 'Iraq'           THEN 4152215
        WHEN 'Syria'          THEN 4153306
        WHEN 'United Kingdom' THEN 4202086
        ELSE 40482029
    END,
    vo.visit_start_date, vo.visit_start_date, 32865,
    vo.visit_occurrence_id, l."Patient's country of birth"
FROM import.labels l
JOIN omop.person p ON l."Record ID"::text = p.person_source_value
JOIN omop.visit_occurrence vo ON p.person_id = vo.person_id;
""",
    # Transfusion status
    """
INSERT INTO omop.observation (
    observation_id, person_id, observation_concept_id,
    observation_date, observation_datetime,
    observation_type_concept_id, visit_occurrence_id, value_source_value
)
SELECT nextval('observation_id_seq'), p.person_id,
    40758326,
    vo.visit_start_date, vo.visit_start_date, 32865, vo.visit_occurrence_id,
    l." Does the patient require regular or occasional transfusions in the present (in the last 12 months) ?"
FROM import.labels l
JOIN omop.person p ON l."Record ID"::text = p.person_source_value
JOIN omop.visit_occurrence vo ON p.person_id = vo.person_id;
""",
    # HBB Allele 1
    """
INSERT INTO omop.observation (
    observation_id, person_id, observation_concept_id,
    observation_date, observation_datetime,
    observation_type_concept_id, value_as_string,
    visit_occurrence_id, value_source_value
)
SELECT nextval('observation_id_seq'), p.person_id, 0,
    vo.visit_start_date, vo.visit_start_date, 32865,
    l."HBB Allele 1", vo.visit_occurrence_id, 'HGNC:4827'
FROM import.labels l
JOIN omop.person p ON l."Record ID"::text = p.person_source_value
JOIN omop.visit_occurrence vo ON p.person_id = vo.person_id;
""",
    # HBB Allele 2
    """
INSERT INTO omop.observation (
    observation_id, person_id, observation_concept_id,
    observation_date, observation_datetime,
    observation_type_concept_id, value_as_string,
    visit_occurrence_id, value_source_value
)
SELECT nextval('observation_id_seq'), p.person_id, 0,
    vo.visit_start_date, vo.visit_start_date, 32865,
    l."HBB Allele 2", vo.visit_occurrence_id, 'HGNC:4827'
FROM import.labels l
JOIN omop.person p ON l."Record ID"::text = p.person_source_value
JOIN omop.visit_occurrence vo ON p.person_id = vo.person_id;
""",
    # HBA Allele 1
    """
INSERT INTO omop.observation (
    observation_id, person_id, observation_concept_id,
    observation_date, observation_datetime,
    observation_type_concept_id, value_as_string,
    visit_occurrence_id, value_source_value
)
SELECT nextval('observation_id_seq'), p.person_id, 0,
    vo.visit_start_date, vo.visit_start_date, 32865,
    l."HBA Allele 1", vo.visit_occurrence_id, 'HGNC:4823;HGNC:4824'
FROM import.labels l
JOIN omop.person p ON l."Record ID"::text = p.person_source_value
JOIN omop.visit_occurrence vo ON p.person_id = vo.person_id;
""",
    # HBA Allele 2
    """
INSERT INTO omop.observation (
    observation_id, person_id, observation_concept_id,
    observation_date, observation_datetime,
    observation_type_concept_id, value_as_string,
    visit_occurrence_id, value_source_value
)
SELECT nextval('observation_id_seq'), p.person_id, 0,
    vo.visit_start_date, vo.visit_start_date, 32865,
    l."HBA Allele 2", vo.visit_occurrence_id, 'HGNC:4823;HGNC:4824'
FROM import.labels l
JOIN omop.person p ON l."Record ID"::text = p.person_source_value
JOIN omop.visit_occurrence vo ON p.person_id = vo.person_id;
""",
    # Drug compliance — poor
    """
INSERT INTO omop.observation (
    observation_id, person_id, observation_concept_id,
    observation_date, observation_datetime,
    observation_type_concept_id, visit_occurrence_id, value_source_value
)
SELECT nextval('observation_id_seq'), p.person_id, 4292063,
    vo.visit_start_date, vo.visit_start_date, 32865,
    vo.visit_occurrence_id, l."Drug compliance"
FROM import.labels l
JOIN omop.person p ON l."Record ID"::text = p.person_source_value
JOIN omop.visit_occurrence vo ON p.person_id = vo.person_id
WHERE l."Drug compliance" = 'Poor (< 60% of recommended dose)';
""",
    # Drug compliance — good / excellent
    """
INSERT INTO omop.observation (
    observation_id, person_id, observation_concept_id,
    observation_date, observation_datetime,
    observation_type_concept_id, visit_occurrence_id, value_source_value
)
SELECT nextval('observation_id_seq'), p.person_id, 4056965,
    vo.visit_start_date, vo.visit_start_date, 32865,
    vo.visit_occurrence_id, l."Drug compliance"
FROM import.labels l
JOIN omop.person p ON l."Record ID"::text = p.person_source_value
JOIN omop.visit_occurrence vo ON p.person_id = vo.person_id
WHERE l."Drug compliance" = 'Good (80-60 % of recommended dose)'
   OR l."Drug compliance" = 'Excellent (>80% of recommended dose)';
""",
]

MEASUREMENT_SQL = [
    "CREATE SEQUENCE IF NOT EXISTS measurement_id_seq START 1;",
    # Cardiac iron T2* — note: column name contains a non-breaking space (U+00A0)
    """
INSERT INTO omop.measurement (
    measurement_id, person_id, measurement_concept_id,
    measurement_date, measurement_datetime,
    measurement_type_concept_id, value_as_number,
    unit_concept_id, visit_occurrence_id, value_source_value
)
SELECT nextval('measurement_id_seq'), p.person_id, 0,
    vo.visit_start_date, vo.visit_start_date, 32809,
    l."Cardiac iron T2*\xa0 (milisec)",
    9593, vo.visit_occurrence_id, 'Cardiac iron T2'
FROM import.labels l
JOIN omop.person p ON l."Record ID"::text = p.person_source_value
JOIN omop.visit_occurrence vo ON p.person_id = vo.person_id
WHERE l."Cardiac iron T2*\xa0 (milisec)" IS NOT NULL;
""",
    # Liver MRI T2*
    """
INSERT INTO omop.measurement (
    measurement_id, person_id, measurement_concept_id,
    measurement_date, measurement_datetime,
    measurement_type_concept_id, value_as_number,
    unit_concept_id, visit_occurrence_id, value_source_value
)
SELECT nextval('measurement_id_seq'), p.person_id, 0,
    vo.visit_start_date, vo.visit_start_date, 32809,
    l."Liver MRI T2* (milisec)",
    9593, vo.visit_occurrence_id, 'Liver MRI T2'
FROM import.labels l
JOIN omop.person p ON l."Record ID"::text = p.person_source_value
JOIN omop.visit_occurrence vo ON p.person_id = vo.person_id
WHERE l."Liver MRI T2* (milisec)" IS NOT NULL;
""",
    # Cirrhosis
    """
INSERT INTO omop.measurement (
    measurement_id, person_id, measurement_concept_id,
    measurement_date, measurement_datetime,
    measurement_type_concept_id, unit_concept_id,
    visit_occurrence_id, value_source_value
)
SELECT nextval('measurement_id_seq'), p.person_id, 36770062,
    vo.visit_start_date, vo.visit_start_date, 32809,
    9593, vo.visit_occurrence_id, l."Cirrhosis"
FROM import.labels l
JOIN omop.person p ON l."Record ID"::text = p.person_source_value
JOIN omop.visit_occurrence vo ON p.person_id = vo.person_id
WHERE l."Cirrhosis" = 'Yes, confirmed';
""",
    # Ferritin serum
    """
INSERT INTO omop.measurement (
    measurement_id, person_id, measurement_concept_id,
    measurement_date, measurement_datetime,
    measurement_type_concept_id, value_as_number,
    unit_concept_id, visit_occurrence_id
)
SELECT nextval('measurement_id_seq'), p.person_id, 37208753,
    vo.visit_start_date, vo.visit_start_date, 32809,
    l."Ferritin serum (ng/mL / µg/L)",
    8842, vo.visit_occurrence_id
FROM import.labels l
JOIN omop.person p ON l."Record ID"::text = p.person_source_value
JOIN omop.visit_occurrence vo ON p.person_id = vo.person_id
WHERE l."Ferritin serum (ng/mL / µg/L)" IS NOT NULL;
""",
    # Serum iron
    """
INSERT INTO omop.measurement (
    measurement_id, person_id, measurement_concept_id,
    measurement_date, measurement_datetime,
    measurement_type_concept_id, value_as_number,
    unit_concept_id, visit_occurrence_id
)
SELECT nextval('measurement_id_seq'), p.person_id, 4097596,
    vo.visit_start_date, vo.visit_start_date, 32809,
    l."Serum iron (μg/dL)",
    8837, vo.visit_occurrence_id
FROM import.labels l
JOIN omop.person p ON l."Record ID"::text = p.person_source_value
JOIN omop.visit_occurrence vo ON p.person_id = vo.person_id
WHERE l."Serum iron (μg/dL)" IS NOT NULL;
""",
]

PROCEDURE_SQL = [
    "CREATE SEQUENCE IF NOT EXISTS procedure_id_seq START 1;",
    # Chelation
    """
INSERT INTO omop.procedure_occurrence (
    procedure_occurrence_id, person_id, procedure_concept_id,
    procedure_date, procedure_datetime,
    procedure_end_date, procedure_end_datetime,
    procedure_type_concept_id, visit_occurrence_id, procedure_source_value
)
SELECT nextval('procedure_id_seq'), p.person_id, 4068544,
    vo.visit_start_date, vo.visit_start_date,
    vo.visit_start_date, vo.visit_start_date,
    32865, vo.visit_occurrence_id,
    l."Is the patient on chelation treatment ?"
FROM import.labels l
JOIN omop.person p ON l."Record ID"::text = p.person_source_value
JOIN omop.visit_occurrence vo ON p.person_id = vo.person_id
WHERE l."Is the patient on chelation treatment ?" = 'Yes';
""",
    # Hydroxyurea
    """
INSERT INTO omop.procedure_occurrence (
    procedure_occurrence_id, person_id, procedure_concept_id,
    procedure_date, procedure_datetime,
    procedure_end_date, procedure_end_datetime,
    procedure_type_concept_id, visit_occurrence_id, procedure_source_value
)
SELECT nextval('procedure_id_seq'), p.person_id, 3169902,
    vo.visit_start_date, vo.visit_start_date,
    vo.visit_start_date, vo.visit_start_date,
    32865, vo.visit_occurrence_id,
    l."Is the patient on hydroxyurea treatment (present time) ?"
FROM import.labels l
JOIN omop.person p ON l."Record ID"::text = p.person_source_value
JOIN omop.visit_occurrence vo ON p.person_id = vo.person_id
WHERE l."Is the patient on hydroxyurea treatment (present time) ?" = 'Yes';
""",
    # Splenectomy
    """
INSERT INTO omop.procedure_occurrence (
    procedure_occurrence_id, person_id, procedure_concept_id,
    procedure_date, procedure_datetime,
    procedure_end_date, procedure_end_datetime,
    procedure_type_concept_id, visit_occurrence_id, procedure_source_value
)
SELECT nextval('procedure_id_seq'), p.person_id, 2834904,
    vo.visit_start_date, vo.visit_start_date,
    vo.visit_start_date, vo.visit_start_date,
    32865, vo.visit_occurrence_id,
    l."Has the spleen been removed ?"
FROM import.labels l
JOIN omop.person p ON l."Record ID"::text = p.person_source_value
JOIN omop.visit_occurrence vo ON p.person_id = vo.person_id
WHERE l."Has the spleen been removed ?" = 'Yes, totally';
""",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def psql(sql: str, container: str, superuser: str, db: str = "postgres") -> bool:
    result = subprocess.run(
        ["docker", "exec", container, "psql", "-U", superuser, "-d", db, "-c", sql],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  ERROR: {result.stderr.strip()}", file=sys.stderr)
        return False
    print(f"  OK: {result.stdout.strip()}")
    return True


def psql_many(statements: list, container: str, superuser: str, db: str) -> None:
    for sql in statements:
        psql(sql.strip(), container, superuser, db=db)


def terminate_connections(container: str, superuser: str, dbname: str) -> None:
    psql(
        f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        f"WHERE datname = '{dbname}' AND pid <> pg_backend_pid();",
        container, superuser,
    )


def load_env(env_path: str) -> dict:
    env = {}
    if not os.path.exists(env_path):
        return env
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip()
    return env


# ---------------------------------------------------------------------------
# Build the answers template DB
# ---------------------------------------------------------------------------

def answers_template_exists(container: str, superuser: str) -> bool:
    result = subprocess.run(
        ["docker", "exec", container, "psql", "-U", superuser, "-d", "postgres",
         "-tAc", f"SELECT 1 FROM pg_database WHERE datname='{ANSWERS_TEMPLATE}'"],
        capture_output=True, text=True,
    )
    return result.stdout.strip() == "1"


def build_answers_template(container: str, superuser: str) -> None:
    print(f"\nBuilding answers template '{ANSWERS_TEMPLATE}'...")

    terminate_connections(container, superuser, ANSWERS_TEMPLATE)
    psql(f"DROP DATABASE IF EXISTS {ANSWERS_TEMPLATE};", container, superuser)

    terminate_connections(container, superuser, VOCAB_TEMPLATE)
    psql(
        f"CREATE DATABASE {ANSWERS_TEMPLATE} TEMPLATE {VOCAB_TEMPLATE};",
        container, superuser,
    )

    db = ANSWERS_TEMPLATE
    print("  Running ETL...")
    psql(CDM_SOURCE_SQL.strip(), container, superuser, db=db)
    psql(PERSON_SQL.strip(), container, superuser, db=db)
    psql(OBSERVATION_PERIOD_SQL.strip(), container, superuser, db=db)
    psql(VISIT_OCCURRENCE_SQL.strip(), container, superuser, db=db)
    psql_many(CONDITION_OCCURRENCE_SQL, container, superuser, db=db)
    psql_many(OBSERVATION_SQL, container, superuser, db=db)
    psql_many(MEASUREMENT_SQL, container, superuser, db=db)
    psql_many(PROCEDURE_SQL, container, superuser, db=db)

    print(f"  Answers template ready.")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    env_file = os.path.join(os.path.dirname(__file__), "..", ".env")
    env = load_env(env_file)

    parser = argparse.ArgumentParser(description="Create completed OMOP answer databases per trainee")
    parser.add_argument("count", type=int, help="Number of trainees")
    parser.add_argument("--start", type=int, default=1, help="Starting trainee number (default: 1)")
    parser.add_argument("--container", default="hemafair_postgres", help="Postgres container name")
    parser.add_argument("--pg-user", default=env.get("POSTGRES_USER", "postgres"))
    parser.add_argument("--rebuild-template", action="store_true",
                        help="Force rebuild of the answers template even if it already exists")
    args = parser.parse_args()

    if not args.rebuild_template and answers_template_exists(args.container, args.pg_user):
        print(f"Answers template '{ANSWERS_TEMPLATE}' already exists — skipping build.")
        print("  Run with --rebuild-template to force a full rebuild.")
    else:
        build_answers_template(args.container, args.pg_user)

    for i in range(args.start, args.start + args.count):
        db_name = f"trainee_{i:02d}_answers"
        owner   = f"trainee_{i:02d}"
        print(f"\n[{db_name}]")

        terminate_connections(args.container, args.pg_user, db_name)
        psql(f"DROP DATABASE IF EXISTS {db_name};", args.container, args.pg_user)

        terminate_connections(args.container, args.pg_user, ANSWERS_TEMPLATE)
        psql(
            f"CREATE DATABASE {db_name} TEMPLATE {ANSWERS_TEMPLATE} OWNER {owner};",
            args.container, args.pg_user,
        )
        psql(f"GRANT ALL PRIVILEGES ON DATABASE {db_name} TO {owner};", args.container, args.pg_user)
        psql(f"ALTER SCHEMA omop OWNER TO {owner};",   args.container, args.pg_user, db=db_name)
        psql(f"ALTER SCHEMA results OWNER TO {owner};", args.container, args.pg_user, db=db_name)
        psql(f"GRANT USAGE ON SCHEMA import TO {owner};", args.container, args.pg_user, db=db_name)
        psql(f"GRANT SELECT ON ALL TABLES IN SCHEMA import TO {owner};", args.container, args.pg_user, db=db_name)
        psql(
            f"DO $$ DECLARE r RECORD; BEGIN "
            f"FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'omop' LOOP "
            f"EXECUTE 'ALTER TABLE omop.' || quote_ident(r.tablename) || ' OWNER TO {owner}'; "
            f"END LOOP; END $$;",
            args.container, args.pg_user, db=db_name,
        )

    print(f"\nDone. Created {args.count} answer database(s) (trainee_XX_answers).")


if __name__ == "__main__":
    main()
