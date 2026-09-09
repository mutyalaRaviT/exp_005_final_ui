"""Global macro registry: a YAML dictionary of every macro definition seen,
keyed by (sasfilename, macroname).

Reads happen directly (load_registry). WRITES go through
scripts/update_macro_registry.sh, which implements the optimistic lock:
hash the file, wait GAP_SECONDS, hash again, write only if unchanged.
"""
import hashlib
import subprocess
import tempfile
from datetime import date
from pathlib import Path

import yaml

from sas_lineage.macros import MacroDef

_PKG_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REGISTRY = _PKG_ROOT / "registry" / "macro_registry.yaml"
UPDATE_SCRIPT = _PKG_ROOT / "scripts" / "update_macro_registry.sh"


def file_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def load_registry(path: Path = DEFAULT_REGISTRY) -> dict:
    path = Path(path)
    if not path.exists():
        return {"macros": []}
    return yaml.safe_load(path.read_text()) or {"macros": []}


def load_macros(path: Path = DEFAULT_REGISTRY) -> dict[str, MacroDef]:
    """Registry entries as MacroDefs, ready for macros.expand(extra_macros=...)."""
    return {
        entry["macroname"].lower(): MacroDef(
            name=entry["macroname"],
            params=list(entry.get("params", [])),
            body=entry.get("definition", ""),
        )
        for entry in load_registry(path)["macros"]
    }


def entries_for_file(sasfilename: str, source: str, macros: dict[str, MacroDef]):
    """Registry rows for every macro defined in one SAS file."""
    code = file_hash(source)
    return [
        {
            "sasfilename": sasfilename,
            "sashashcode": code,
            "macroname": m.name,
            "params": list(m.params),
            "definition": m.body,
            "updated": date.today().isoformat(),
        }
        for m in macros.values()
    ]


def update_registry(entries: list[dict], registry_path: Path = DEFAULT_REGISTRY,
                    gap_seconds: int | None = None) -> subprocess.CompletedProcess:
    """Write entries through the bash script (optimistic-lock protocol)."""
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as tmp:
        yaml.safe_dump({"macros": entries}, tmp, sort_keys=False)
        tmp_path = tmp.name
    env = {"GAP_SECONDS": str(gap_seconds)} if gap_seconds is not None else None
    import os
    full_env = {**os.environ, **(env or {})}
    return subprocess.run(
        ["bash", str(UPDATE_SCRIPT), str(registry_path), tmp_path],
        capture_output=True, text=True, env=full_env,
    )
