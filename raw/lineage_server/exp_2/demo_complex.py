"""Run every example in examples/ through the full pipeline and print the
blocks, statuses, and edges. Also registers ex8's macros into the global
YAML registry via the hash-guarded bash script.

DEV-ONLY: production spreadsheets come solely from the UI's /api/excel
verified merge — never from this script.
"""
import sys
from pathlib import Path

from sas_lineage.pipeline import analyze_file, register_file
from sas_lineage.registry import DEFAULT_REGISTRY

EXAMPLES = sorted((Path(__file__).parent / "examples").glob("ex*.sas"))


def main():
    for path in EXAMPLES:
        print(f"\n=== {path.name} ===")
        analysis = analyze_file(path, registry_path=None)
        if analysis.macros:
            print(f"  macros: {sorted(analysis.macros)}  let vars: {analysis.let_vars}")
        for b in analysis.blocks:
            note = f"  unresolved={b.unresolved}" if b.unresolved else ""
            print(f"  {b.block_id}: {b.status}{note}")
        for e in analysis.edges:
            print(f"    [{e.edge_type}] {e.display}")

    if "--register" in sys.argv:
        print(f"\n=== registering ex8 macros into {DEFAULT_REGISTRY} ===")
        result = register_file(EXAMPLES[-1], gap_seconds=None)  # default 5s gap
        print(result.stdout.strip())
        if result.returncode != 0:
            print(result.stderr.strip())


if __name__ == "__main__":
    main()
