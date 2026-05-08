#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="$(dirname "$0")/../docker-compose.yml"
ENV_FILE="$(dirname "$0")/../.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "No .env file found. Copy .env.example to .env and set your passwords first."
  exit 1
fi

cmd="${1:-help}"

case "$cmd" in
  up)
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d
    echo "postgres  -> localhost:5432"
    echo "pgadmin   -> http://localhost:5050"
    ;;
  down)
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down
    ;;
  logs)
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" logs -f
    ;;
  psql)
    docker exec -it hemafair_postgres psql -U "$(grep POSTGRES_USER "$ENV_FILE" | cut -d= -f2)"
    ;;
  reset)
    echo "WARNING: this destroys all data. Press Ctrl-C to abort, or Enter to continue."
    read -r
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down -v
    ;;
  *)
    echo "Usage: $0 {up|down|logs|psql|reset}"
    ;;
esac
