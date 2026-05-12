#!/usr/bin/env python3
"""
Drop all trainee_XX and trainee_XX_answers databases and their users.

Usage:
    python3 scripts/drop_trainee_dbs.py 30
    python3 scripts/drop_trainee_dbs.py 30 --start 1 --container hemafair_postgres
"""

import argparse
import os
import subprocess
import sys


def psql(sql: str, container: str, superuser: str, db: str = "postgres") -> bool:
    result = subprocess.run(
        ["docker", "exec", container, "psql", "-U", superuser, "-d", db, "-c", sql],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  WARN: {result.stderr.strip()}", file=sys.stderr)
        return False
    print(f"  OK: {result.stdout.strip()}")
    return True


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


def terminate_connections(container: str, superuser: str, dbname: str) -> None:
    psql(
        f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        f"WHERE datname = '{dbname}' AND pid <> pg_backend_pid();",
        container, superuser,
    )


def main():
    env_file = os.path.join(os.path.dirname(__file__), "..", ".env")
    env = load_env(env_file)

    parser = argparse.ArgumentParser(description="Drop trainee databases and users")
    parser.add_argument("count", type=int, help="Number of trainees to drop")
    parser.add_argument("--start", type=int, default=1, help="Starting number (default: 1)")
    parser.add_argument("--container", default="hemafair_postgres")
    parser.add_argument("--pg-user", default=env.get("POSTGRES_USER", "postgres"))
    args = parser.parse_args()

    print(f"Dropping trainee_{args.start:02d} through trainee_{args.start + args.count - 1:02d}...")
    print("This will also drop their _answers databases and PostgreSQL users.")
    confirm = input("Type 'yes' to continue: ").strip().lower()
    if confirm != "yes":
        print("Aborted.")
        sys.exit(0)

    for i in range(args.start, args.start + args.count):
        username = f"trainee_{i:02d}"
        answers_db = f"{username}_answers"
        print(f"\n[{username}]")

        # Drop answers database
        terminate_connections(args.container, args.pg_user, answers_db)
        psql(f"DROP DATABASE IF EXISTS {answers_db};", args.container, args.pg_user)

        # Drop main database
        terminate_connections(args.container, args.pg_user, username)
        psql(f"DROP DATABASE IF EXISTS {username};", args.container, args.pg_user)

        # Drop user
        psql(f"DROP USER IF EXISTS {username};", args.container, args.pg_user)

    print(f"\nDone. Dropped {args.count} trainee database(s) and user(s).")
    print(f"Run create_trainees.py to recreate with a different count.")


if __name__ == "__main__":
    main()
