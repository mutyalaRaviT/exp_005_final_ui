"""Pure-Python registry updater (the bash script is now a thin launcher for this).

Protocol, exit codes, and messages are identical to the original bash version:

  1. LOCK: atomically create <registry>.lock (mkdir). Waiting writers retry
     for LOCK_TIMEOUT_SECONDS then give up (exit 2). Locks older than
     LOCK_STALE_SECONDS are stolen. The lock is ALWAYS released — try/finally
     plus SIGINT/SIGTERM handlers cover success, failure, and interruption.
  2. HASH GAP: hash the registry, wait GAP_SECONDS (default 5), hash again;
     abort with exit 1 on mismatch (an out-of-band edit).
  3. MERGE: keyed on (sasfilename, macroname) — replace or append.

Usage: python -m sas_lineage.update_registry <registry.yaml> <entries.yaml>
Env:   GAP_SECONDS, LOCK_TIMEOUT_SECONDS, LOCK_STALE_SECONDS, e.g. for tests.
"""
import hashlib
import os
import signal
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

EXIT_OK, EXIT_CONFLICT, EXIT_LOCKED = 0, 1, 2


def hash_of(path: Path) -> str:
    if not path.is_file():
        return "ABSENT"
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RegistryLock:
    """mkdir-based lock. Guaranteed release: use as a context manager; the
    __exit__ runs on success, on any exception, and (via the signal handlers
    installed in main) on SIGINT/SIGTERM."""

    def __init__(self, registry: Path, timeout: int, stale: int):
        self.lock_dir = Path(str(registry) + ".lock")
        self.timeout = timeout
        self.stale = stale
        self.held = False

    def _age_seconds(self) -> float:
        try:
            return time.time() - self.lock_dir.stat().st_mtime
        except OSError:
            return 0.0

    def acquire(self):
        self.lock_dir.parent.mkdir(parents=True, exist_ok=True)
        waited = 0
        while True:
            try:
                self.lock_dir.mkdir()
                self.held = True
                owner = (f"pid: {os.getpid()}\nhost: {socket.gethostname()}\n"
                         f"started: {datetime.now(timezone.utc).isoformat()}\n")
                try:
                    (self.lock_dir / "owner").write_text(owner)
                except OSError:
                    pass
                return
            except FileExistsError:
                pass
            if self._age_seconds() > self.stale:
                print(f"stale lock (older than {self.stale}s) — stealing it",
                      file=sys.stderr)
                self._remove()
                continue
            if waited >= self.timeout:
                print(f"LOCKED: {self.lock_dir} held by another writer for "
                      f"{waited}s — giving up", file=sys.stderr)
                try:
                    for line in (self.lock_dir / "owner").read_text().splitlines():
                        print(f"  owner {line}", file=sys.stderr)
                except OSError:
                    pass
                raise SystemExit(EXIT_LOCKED)
            time.sleep(1)
            waited += 1

    def _remove(self):
        for child in self.lock_dir.glob("*"):
            child.unlink(missing_ok=True)
        try:
            self.lock_dir.rmdir()
        except OSError:
            pass

    def release(self):
        if self.held:  # never delete a lock we don't own
            self._remove()
            self.held = False

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *exc):
        self.release()
        return False


def merge_entries(registry_path: Path, entries: list[dict]) -> str:
    registry = ({"macros": []} if not registry_path.exists()
                else yaml.safe_load(registry_path.read_text()) or {"macros": []})
    index = {(m["sasfilename"], m["macroname"]): i
             for i, m in enumerate(registry["macros"])}
    added = replaced = 0
    for entry in entries:
        key = (entry["sasfilename"], entry["macroname"])
        if key in index:
            registry["macros"][index[key]] = entry
            replaced += 1
        else:
            index[key] = len(registry["macros"])
            registry["macros"].append(entry)
            added += 1
    registry_path.write_text(
        yaml.safe_dump(registry, sort_keys=False, allow_unicode=True)
    )
    return f"merged: {added} added, {replaced} replaced, {len(registry['macros'])} total"


def update(registry_path: Path, entries_path: Path,
           gap: int, timeout: int, stale: int) -> int:
    with RegistryLock(registry_path, timeout, stale):
        print(f"lock acquired: {registry_path}.lock")

        before = hash_of(registry_path)
        print(f"registry hash: {before} — waiting {gap}s to detect "
              f"concurrent writers...")
        time.sleep(gap)
        after = hash_of(registry_path)

        if before != after:
            print(f"CONFLICT: registry changed during the {gap}s grace period",
                  file=sys.stderr)
            print(f"  before: {before}\n  after:  {after}", file=sys.stderr)
            print("someone else is updating — re-run to retry on top of their "
                  "version", file=sys.stderr)
            return EXIT_CONFLICT

        entries = yaml.safe_load(entries_path.read_text())["macros"]
        print(merge_entries(registry_path, entries))
        print(f"written: {registry_path} (new hash: {hash_of(registry_path)})")
        return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("usage: python -m sas_lineage.update_registry "
              "<registry.yaml> <entries.yaml>", file=sys.stderr)
        return 64

    # make SIGTERM raise SystemExit so finally/__exit__ blocks run
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))

    return update(
        Path(argv[0]), Path(argv[1]),
        gap=int(os.environ.get("GAP_SECONDS", "5")),
        timeout=int(os.environ.get("LOCK_TIMEOUT_SECONDS", "30")),
        stale=int(os.environ.get("LOCK_STALE_SECONDS", "120")),
    )


if __name__ == "__main__":
    sys.exit(main())
