#!/usr/bin/env python3
"""
Create numbered trainee PostgreSQL users, each with their own blank OMOP CDM 5.4 database.

Usage:
    python3 scripts/create_trainees.py 20
    python3 scripts/create_trainees.py 20 --start 1 --container hemafair_postgres --out credentials.csv

Each trainee gets:
    username : trainee_01, trainee_02, ...
    database : trainee_01, trainee_02, ...  (blank OMOP CDM 5.4 schema inside)
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
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  ERROR: {result.stderr.strip()}", file=sys.stderr)
        return False
    print(f"  OK: {result.stdout.strip()}")
    return True


def psql_file(sql_path: str, container: str, superuser: str, db: str, schema: str = "public") -> bool:
    """Copy a SQL file into the container and execute it inside the given schema."""
    filename = os.path.basename(sql_path)
    dest = f"/tmp/{filename}"
    cp = subprocess.run(
        ["docker", "cp", sql_path, f"{container}:{dest}"],
        capture_output=True, text=True,
    )
    if cp.returncode != 0:
        print(f"  ERROR copying DDL: {cp.stderr.strip()}", file=sys.stderr)
        return False
    result = subprocess.run(
        ["docker", "exec", container, "psql", "-U", superuser, "-d", db,
         "-c", f"SET search_path TO {schema};", "-f", dest],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  ERROR applying DDL: {result.stderr.strip()}", file=sys.stderr)
        return False
    print(f"  OK: OMOP CDM tables created in schema '{schema}'")
    return True


def fetch_omop_ddl() -> str:
    print(f"Fetching OMOP CDM 5.4 DDL from OHDSI GitHub...")
    ddl_path = os.path.join(tempfile.gettempdir(), "omop_cdm_5.4_ddl.sql")
    if os.path.exists(ddl_path):
        print(f"  Using cached DDL at {ddl_path}")
        return ddl_path
    urllib.request.urlretrieve(OMOP_DDL_URL, ddl_path)
    print(f"  Downloaded to {ddl_path}")
    return ddl_path


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
    env_file = os.path.join(os.path.dirname(__file__), "..", ".env")
    env = load_env(env_file)

    parser = argparse.ArgumentParser(description="Create trainee OMOP databases")
    parser.add_argument("count", type=int, help="Number of trainees to create")
    parser.add_argument("--start", type=int, default=1, help="Starting number (default: 1)")
    parser.add_argument("--container", default="hemafair_postgres", help="Postgres container name")
    parser.add_argument("--pg-user", default=env.get("POSTGRES_USER", "postgres"), help="PostgreSQL superuser (reads from .env)")
    parser.add_argument("--out", default="credentials.csv", help="Output CSV file (default: credentials.csv)")
    args = parser.parse_args()

    if args.count < 1:
        sys.exit("Count must be at least 1.")

    print(f"Using superuser: {args.pg_user}")

    ddl_path = fetch_omop_ddl()

    rows = []
    for i in range(args.start, args.start + args.count):
        username = f"trainee_{i:02d}"
        password = random_password()
        print(f"\n[{username}]")

        psql(f"CREATE USER {username} WITH PASSWORD '{password}';", args.container, args.pg_user)
        psql(f"CREATE DATABASE {username} OWNER {username};", args.container, args.pg_user)
        psql(f"GRANT ALL PRIVILEGES ON DATABASE {username} TO {username};", args.container, args.pg_user)

        # Create omop schema, apply DDL into it, hand ownership to the trainee
        psql(f"CREATE SCHEMA omop AUTHORIZATION {username};", args.container, args.pg_user, db=username)
        psql_file(ddl_path, args.container, args.pg_user, db=username, schema="omop")
        psql(
            f"DO $$ DECLARE r RECORD; BEGIN "
            f"FOR r IN SELECT tablename FROM pg_tables WHERE schemaname='omop' LOOP "
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
