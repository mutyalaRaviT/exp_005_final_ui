"""Cron entry: sync the DuckDB store with the SAS tree.

Run from the `server` directory (same env vars as `app.py`):

    SAS_ROOTS=../inputs SAS_DB=../output/explorer.duckdb \
        PYTHONPATH=../exp_2:. ../.venv/bin/python scripts/sync_store.py

Walks the roots, hashes every `*.sas` file, reconverts only what changed,
removes files gone from disk, and stamps the sync (`sync_meta`) so the
store-backed search becomes authoritative without ripgrep.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from indexer import Indexer                  # noqa: E402
from sas_lineage.store import LineageStore   # noqa: E402
from service import Service                  # noqa: E402


def main() -> None:
    roots = [Path(p.strip())
             for p in os.environ.get("SAS_ROOTS", "inputs").split(",")
             if p.strip()]
    db_path = os.environ.get("SAS_DB", "output/explorer.duckdb")
    store = LineageStore(db_path)
    indexer = Indexer(store, roots)
    service = Service(store, indexer, roots)
    indexer.build()
    print(json.dumps(service.sync_sources(), indent=2))
    store.close()


if __name__ == "__main__":
    main()
