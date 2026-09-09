#!/usr/bin/env bash
# Thin launcher — all logic lives in Python: sas_lineage/update_registry.py
# (lock file with guaranteed release, 5s hash-gap conflict check, YAML merge).
# Exit codes: 0 written, 1 hash conflict, 2 lock held by a live writer.
# Env: GAP_SECONDS, LOCK_TIMEOUT_SECONDS, LOCK_STALE_SECONDS.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PY="${PYTHON:-$SCRIPT_DIR/../../.venv/bin/python}"
export PYTHONPATH="$SCRIPT_DIR/..${PYTHONPATH:+:$PYTHONPATH}"
exec "$PY" -m sas_lineage.update_registry "$@"
