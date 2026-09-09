import subprocess
import threading
import time
from pathlib import Path

import yaml

from sas_lineage.macros import extract_macros
from sas_lineage.registry import (
    UPDATE_SCRIPT,
    entries_for_file,
    load_macros,
    load_registry,
    update_registry,
)

SRC = """%macro stage(t);
data work.&t.;
    set raw.&t.;
run;
%mend;
"""


def make_entries():
    _, macros = extract_macros(SRC)
    return entries_for_file("jobs/stage.sas", SRC, macros)


def test_entry_fields():
    entry = make_entries()[0]
    assert entry["sasfilename"] == "jobs/stage.sas"
    assert entry["macroname"] == "stage"
    assert entry["params"] == ["t"]
    assert len(entry["sashashcode"]) == 16
    assert "set raw.&t.;" in entry["definition"]
    assert entry["updated"]


def test_script_creates_and_merges(tmp_path):
    registry = tmp_path / "macro_registry.yaml"
    result = update_registry(make_entries(), registry_path=registry, gap_seconds=0)
    assert result.returncode == 0, result.stderr
    data = load_registry(registry)
    assert len(data["macros"]) == 1

    # same (sasfilename, macroname) again -> replaced, not duplicated
    result = update_registry(make_entries(), registry_path=registry, gap_seconds=0)
    assert result.returncode == 0
    assert len(load_registry(registry)["macros"]) == 1
    assert "1 replaced" in result.stdout


def test_script_detects_concurrent_writer(tmp_path):
    registry = tmp_path / "macro_registry.yaml"
    registry.write_text("macros: []\n")

    def interfere():
        time.sleep(1)
        registry.write_text("macros: [{sasfilename: other.sas, macroname: x}]\n")

    t = threading.Thread(target=interfere)
    t.start()
    result = update_registry(make_entries(), registry_path=registry, gap_seconds=3)
    t.join()
    assert result.returncode == 1
    assert "CONFLICT" in result.stderr
    # the other writer's content survived untouched
    assert load_registry(registry)["macros"][0]["sasfilename"] == "other.sas"


def test_loaded_registry_macros_expand(tmp_path):
    registry = tmp_path / "macro_registry.yaml"
    update_registry(make_entries(), registry_path=registry, gap_seconds=0)
    macros = load_macros(registry)
    assert "stage" in macros
    assert macros["stage"].params == ["t"]


def test_script_is_executable():
    assert Path(UPDATE_SCRIPT).exists()
    result = subprocess.run(["bash", str(UPDATE_SCRIPT)], capture_output=True, text=True)
    assert result.returncode != 0  # usage error, but the script runs


# ---- lock-file behavior -----------------------------------------------------

def run_script(registry, entries_file, **env_overrides):
    import os
    env = {**os.environ, "GAP_SECONDS": "0", **{k: str(v) for k, v in env_overrides.items()}}
    return subprocess.run(
        ["bash", str(UPDATE_SCRIPT), str(registry), str(entries_file)],
        capture_output=True, text=True, env=env,
    )


def write_entries_file(tmp_path):
    entries_file = tmp_path / "entries.yaml"
    entries_file.write_text(yaml.safe_dump({"macros": make_entries()}))
    return entries_file


def test_lock_released_after_success(tmp_path):
    registry = tmp_path / "reg.yaml"
    result = run_script(registry, write_entries_file(tmp_path))
    assert result.returncode == 0, result.stderr
    assert "lock acquired" in result.stdout
    assert not (tmp_path / "reg.yaml.lock").exists()


def test_lock_released_even_on_failure(tmp_path):
    registry = tmp_path / "reg.yaml"
    registry.write_text("macros: []\n")
    bad_entries = tmp_path / "bad.yaml"
    bad_entries.write_text("not: {valid: [entries")  # merge step will blow up
    result = run_script(registry, bad_entries)
    assert result.returncode != 0
    assert not (tmp_path / "reg.yaml.lock").exists()  # trap cleaned it up


def test_lock_released_after_hash_conflict(tmp_path):
    registry = tmp_path / "reg.yaml"
    registry.write_text("macros: []\n")

    def interfere():
        time.sleep(1)
        registry.write_text("macros: [{sasfilename: other.sas, macroname: x}]\n")

    t = threading.Thread(target=interfere)
    t.start()
    result = run_script(registry, write_entries_file(tmp_path), GAP_SECONDS=3)
    t.join()
    assert result.returncode == 1
    assert "CONFLICT" in result.stderr
    assert not (tmp_path / "reg.yaml.lock").exists()


def test_second_writer_waits_then_gives_up(tmp_path):
    registry = tmp_path / "reg.yaml"
    lock = tmp_path / "reg.yaml.lock"
    lock.mkdir()  # another writer holds the lock right now
    (lock / "owner").write_text("pid: 99999\n")
    result = run_script(registry, write_entries_file(tmp_path),
                        LOCK_TIMEOUT_SECONDS=2, LOCK_STALE_SECONDS=9999)
    assert result.returncode == 2
    assert "LOCKED" in result.stderr
    assert lock.exists()  # we never delete a live lock we don't own


def test_stale_lock_is_stolen(tmp_path):
    import os
    registry = tmp_path / "reg.yaml"
    lock = tmp_path / "reg.yaml.lock"
    lock.mkdir()
    old = time.time() - 3600  # a writer that died an hour ago
    os.utime(lock, (old, old))
    result = run_script(registry, write_entries_file(tmp_path), LOCK_STALE_SECONDS=60)
    assert result.returncode == 0, result.stderr
    assert "stealing" in result.stderr
    assert len(load_registry(registry)["macros"]) == 1
    assert not lock.exists()
