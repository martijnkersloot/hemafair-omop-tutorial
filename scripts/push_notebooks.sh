#!/usr/bin/env bash
# Push notebooks to every JupyterHub user's omop_answers folder.
# Must be run as root (sudo) so it can write to home directories.
#
# Usage:
#   sudo bash scripts/push_notebooks.sh
#   sudo bash scripts/push_notebooks.sh --folder omop_answers

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FOLDER="omop_answers"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --folder) FOLDER="$2"; shift 2 ;;
        *) echo "Unknown argument: $1"; exit 1 ;;
    esac
done

NOTEBOOKS=(
    "hemafair_omop_etl_exercise.ipynb"
    "hemafair_omop_etl.ipynb"
    "hemafair_omop_reset.ipynb"
)

echo "Pushing notebooks from: $REPO_DIR"
echo "Target folder:          ~/<user>/$FOLDER"
echo ""

pushed=0

for user_home in /home/jupyter-*/; do
    [[ -d "$user_home" ]] || continue
    jupyter_user=$(basename "$user_home")
    target_dir="${user_home}${FOLDER}"

    mkdir -p "$target_dir"

    for nb in "${NOTEBOOKS[@]}"; do
        src="$REPO_DIR/$nb"
        if [[ ! -f "$src" ]]; then
            echo "  WARNING: $nb not found, skipping"
            continue
        fi
        cp "$src" "$target_dir/$nb"
    done

    chown -R "${jupyter_user}:${jupyter_user}" "$target_dir"
    echo "  ✓ $target_dir"
    pushed=$((pushed + 1))
done

echo ""
echo "Done. Pushed to $pushed user(s)."
