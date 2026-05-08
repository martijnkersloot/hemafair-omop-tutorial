#!/usr/bin/env python3
"""
Create numbered trainee PostgreSQL users, each with their own OMOP CDM 5.4 database
pre-loaded with OHDSI vocabulary from Google Drive.

Strategy: build one vocabulary template database, then clone it per trainee.
This imports the vocabulary only once instead of N times.

Usage:
    python3 scripts/create_trainees.py 30
    python3 scripts/create_trainees.py 30 --start 1 --container hemafair_postgres --out credentials.csv
"""

import argparse
import csv
import os
import secrets
import string
import subprocess
import sys
import tempfile
import urllib.request

OMOP_DDL_URL = (
    "https://raw.githubusercontent.com/OHDSI/CommonDataModel/main/"
    "inst/ddl/5.4/postgresql/OMOPCDM_postgresql_5.4_ddl.sql"
)
GDRIVE_FOLDER_ID = "1-TtQuH6sq3yjHdGf2SEEEPbet0nUi_dY"
TEMPLATE_DB = "omop_vocab_template"

VOCAB_TABLES = [
    ("concept",              "CONCEPT.csv"),
    ("concept_relationship", "CONCEPT_RELATIONSHIP.csv"),
    ("concept_ancestor",     "CONCEPT_ANCESTOR.csv"),
    ("concept_synonym",      "CONCEPT_SYNONYM.csv"),
    ("concept_class",        "CONCEPT_CLASS.csv"),
    ("domain",               "DOMAIN.csv"),
    ("drug_strength",        "DRUG_STRENGTH.csv"),
    ("relationship",         "RELATIONSHIP.csv"),
    ("vocabulary",           "VOCABULARY.csv"),
]


def ensure_deps():
    needed = []
    for pkg, name in [("gdown", "gdown"), ("psycopg2-binary", "psycopg2"),
                      ("pandas", "pandas"), ("sqlalchemy", "sqlalchemy")]:
        try:
            __import__(name)
        except ImportError:
            needed.append(pkg)
    if needed:
        print(f"Installing missing packages: {', '.join(needed)}")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--break-system-packages"] + needed,
            check=True,
        )


def random_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(c.isupper() for c in pw)
            and any(c.islower() for c in pw)
            and any(c.isdigit() for c in pw)
            and any(c in "!@#$%^&*" for c in pw)
        ):
            return pw


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


def psql_file(sql_path: str, container: str, superuser: str, db: str, schema: str = "public") -> bool:
    """Replace @cdmDatabaseSchema placeholder, copy into container, and execute."""
    with open(sql_path) as f:
        ddl = f.read()
    ddl = ddl.replace("@cdmDatabaseSchema", schema)
    patched_path = sql_path + ".patched.sql"
    with open(patched_path, "w") as f:
        f.write(ddl)
    dest = "/tmp/omop_cdm_patched.sql"
    cp = subprocess.run(
        ["docker", "cp", patched_path, f"{container}:{dest}"],
        capture_output=True, text=True,
    )
    if cp.returncode != 0:
        print(f"  ERROR copying DDL: {cp.stderr.strip()}", file=sys.stderr)
        return False
    result = subprocess.run(
        ["docker", "exec", container, "psql", "-U", superuser, "-d", db, "-f", dest],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  ERROR applying DDL: {result.stderr.strip()}", file=sys.stderr)
        return False
    print(f"  OK: OMOP CDM tables created in schema '{schema}'")
    return True


def fetch_omop_ddl() -> str:
    print("Fetching OMOP CDM 5.4 DDL...")
    path = os.path.join(tempfile.gettempdir(), "omop_cdm_5.4_ddl.sql")
    if os.path.exists(path):
        print(f"  Using cached DDL at {path}")
        return path
    urllib.request.urlretrieve(OMOP_DDL_URL, path)
    print(f"  Downloaded to {path}")
    return path


def download_vocab() -> str:
    import gdown
    vocab_dir = os.path.join(tempfile.gettempdir(), "omop_vocab")
    all_present = os.path.exists(vocab_dir) and all(
        os.path.exists(os.path.join(vocab_dir, fname)) for _, fname in VOCAB_TABLES
    )
    if all_present:
        print(f"  Using cached vocabulary at {vocab_dir}")
        return vocab_dir
    os.makedirs(vocab_dir, exist_ok=True)
    print("Downloading vocabulary from Google Drive...")
    gdown.download_folder(
        f"https://drive.google.com/drive/folders/{GDRIVE_FOLDER_ID}",
        output=vocab_dir, quiet=False, use_cookies=False,
    )
    return vocab_dir


def parse_omop_dates(df):
    import pandas as pd
    for col in ("valid_start_date", "valid_end_date"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col].astype(str), format="%Y%m%d", errors="coerce").dt.date
    return df


def import_vocab(vocab_dir: str, superuser: str, password: str, db: str, port: int):
    import pandas as pd
    from sqlalchemy import create_engine
    from urllib.parse import quote_plus

    engine = create_engine(
        f"postgresql+psycopg2://{superuser}:{quote_plus(password)}@localhost:{port}/{db}"
    )
    for table, filename in VOCAB_TABLES:
        filepath = os.path.join(vocab_dir, filename)
        if not os.path.exists(filepath):
            print(f"  WARNING: {filename} not found, skipping", file=sys.stderr)
            continue
        print(f"  Importing {filename} → omop.{table}...")
        for chunk in pd.read_csv(filepath, sep="\t", low_memory=False, chunksize=50_000):
            chunk = parse_omop_dates(chunk)
            chunk.columns = [c.lower() for c in chunk.columns]
            chunk.to_sql(table, engine, schema="omop", if_exists="append", index=False)
    print("  Vocabulary import complete.")


def build_template(container: str, superuser: str, password: str, port: int, ddl_path: str, vocab_dir: str):
    print(f"\nBuilding template database '{TEMPLATE_DB}'...")
    psql(f"DROP DATABASE IF EXISTS {TEMPLATE_DB};", container, superuser)
    psql(f"CREATE DATABASE {TEMPLATE_DB};", container, superuser)
    psql("CREATE SCHEMA omop;", container, superuser, db=TEMPLATE_DB)
    psql("CREATE SCHEMA results;", container, superuser, db=TEMPLATE_DB)
    psql_file(ddl_path, container, superuser, db=TEMPLATE_DB, schema="omop")
    import_vocab(vocab_dir, superuser, password, db=TEMPLATE_DB, port=port)


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


def main():
    ensure_deps()

    env_file = os.path.join(os.path.dirname(__file__), "..", ".env")
    env = load_env(env_file)

    parser = argparse.ArgumentParser(description="Create trainee OMOP databases")
    parser.add_argument("count", type=int, help="Number of trainees to create")
    parser.add_argument("--start", type=int, default=1, help="Starting number (default: 1)")
    parser.add_argument("--container", default="hemafair_postgres", help="Postgres container name")
    parser.add_argument("--pg-user", default=env.get("POSTGRES_USER", "postgres"), help="PostgreSQL superuser")
    parser.add_argument("--pg-password", default=env.get("POSTGRES_PASSWORD", ""), help="PostgreSQL superuser password")
    parser.add_argument("--pg-port", type=int, default=int(env.get("POSTGRES_PORT", 5432)), help="PostgreSQL port")
    parser.add_argument("--out", default="credentials.csv", help="Output CSV file")
    args = parser.parse_args()

    if args.count < 1:
        sys.exit("Count must be at least 1.")

    print(f"Using superuser: {args.pg_user}")

    ddl_path = fetch_omop_ddl()
    vocab_dir = download_vocab()
    build_template(args.container, args.pg_user, args.pg_password, args.pg_port, ddl_path, vocab_dir)

    rows = []
    for i in range(args.start, args.start + args.count):
        username = f"trainee_{i:02d}"
        password = random_password()
        print(f"\n[{username}]")

        psql(f"CREATE USER {username} WITH PASSWORD '{password}';", args.container, args.pg_user)
        psql(f"CREATE DATABASE {username} TEMPLATE {TEMPLATE_DB} OWNER {username};", args.container, args.pg_user)
        psql(f"GRANT ALL PRIVILEGES ON DATABASE {username} TO {username};", args.container, args.pg_user)
        psql(f"ALTER SCHEMA omop OWNER TO {username};", args.container, args.pg_user, db=username)
        psql(f"ALTER SCHEMA results OWNER TO {username};", args.container, args.pg_user, db=username)
        psql(
            f"DO $$ DECLARE r RECORD; BEGIN "
            f"FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'omop' LOOP "
            f"EXECUTE 'ALTER TABLE omop.' || quote_ident(r.tablename) || ' OWNER TO {username}'; "
            f"END LOOP; END $$;",
            args.container, args.pg_user, db=username,
        )

        rows.append({"username": username, "password": password, "database": username})

    with open(args.out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["username", "password", "database"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nDone. Credentials written to {args.out}")
    print("Keep this file secure — delete it after distributing credentials.")


if __name__ == "__main__":
    main()
