"""Term scan over *.sas files: rg (fast path) with a Python fallback.

scan_term() picks whichever scanner is available; both share the same
signature and semantics: case-insensitive, literal (non-regex) substring
match over *.sas files under the given roots.
"""
import shutil
import subprocess
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path


def active_scanner(store_ready: bool = False) -> str:
    """rg (fast disk scan) -> duckdb (synced store, no rg in production)
    -> python (last resort)."""
    if shutil.which("rg"):
        return "rg"
    return "duckdb" if store_ready else "python"


def scan_term(term, roots):
    return (_scan_rg if active_scanner() == "rg" else _scan_python)(term, roots)


def _scan_rg(term, roots):
    cmd = ["rg", "-l", "-i", "--fixed-strings", "-g", "*.sas", term,
           *[str(r) for r in roots]]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return {Path(line) for line in proc.stdout.splitlines() if line}


def _file_has(args):
    path, needle = args
    try:
        return needle in path.read_text(errors="ignore").lower()
    except OSError:
        return False


def _scan_python(term, roots):
    needle = term.lower()
    files = sorted(p for r in roots for p in Path(r).rglob("*.sas"))
    with ProcessPoolExecutor() as ex:
        flags = ex.map(_file_has, [(p, needle) for p in files], chunksize=64)
    return {p for p, hit in zip(files, flags) if hit}
