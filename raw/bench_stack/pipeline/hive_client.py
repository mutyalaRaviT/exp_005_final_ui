"""pipeline.hive_client -- lazy-start client for the real-Hive lane.

Why this file exists: the containerised Hive (docker/hive/compose.yaml)
takes 40-90 seconds to become query-ready, which is far too slow to pay
per query. This module is the "start it if it isn't already, then talk to
it" layer, so callers can simply issue a query and let the first one bear
the startup cost.

`ensure_up()` shells out to install/hive_up.sh rather than driving the
container runtime itself. That keeps one definition of how the stack
starts, shared with the shell entry points, instead of a second copy here
that could drift.

Typical use:

    from pipeline.hive_client import HiveClient
    hive = HiveClient()                  # nothing started yet
    rows = hive.sql("SELECT 1")          # starts the stack if needed

Environment:
    HIVE_API_URL        default http://localhost:10099
    HIVE_IDLE_MINUTES   passed through to hive_up.sh (0 disables the reaper)
    HIVE_AUTOSTART      set to "0" to fail instead of starting the stack,
                        which is what CI wants: a test that silently boots
                        a 6 GiB container is a test that hides its cost.
"""
import json
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_API_URL = os.environ.get("HIVE_API_URL", "http://localhost:10099")


class HiveError(RuntimeError):
    """A query reached Hive and Hive rejected it, or the stack is down.

    Carries the engine's own message rather than a summary: when a
    reference lane disagrees with the pipeline, the exact Hive error is
    the evidence.
    """


class HiveClient:
    def __init__(self, api_url=None, autostart=None, timeout=900):
        self.api_url = (api_url or DEFAULT_API_URL).rstrip("/")
        if autostart is None:
            autostart = os.environ.get("HIVE_AUTOSTART", "1") != "0"
        self.autostart = autostart
        self.timeout = timeout
        self._known_up = False

    # -- lifecycle --------------------------------------------------
    def is_ready(self, timeout=5):
        try:
            with urllib.request.urlopen(f"{self.api_url}/health", timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8")).get("ok") is True
        except (urllib.error.URLError, OSError, ValueError):
            return False

    def ensure_up(self, verbose=True):
        """Start the stack if it is not already answering queries.

        Cached in `_known_up` so a corpus run does not re-probe before
        every statement; a stack that dies mid-run still surfaces, as
        the next query itself fails with the connection error.
        """
        if self._known_up or self.is_ready():
            self._known_up = True
            return
        if not self.autostart:
            raise HiveError(
                f"Hive is not running at {self.api_url} and HIVE_AUTOSTART=0. "
                f"Start it with: bash install/hive_up.sh"
            )
        script = REPO_ROOT / "install" / "hive_up.sh"
        env = dict(os.environ)
        if not verbose:
            env["HIVE_QUIET"] = "1"
        proc = subprocess.run(
            ["bash", str(script)], env=env, capture_output=not verbose, text=True,
        )
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip() if not verbose else ""
            raise HiveError(f"install/hive_up.sh failed (exit {proc.returncode}). {detail}")
        self._known_up = True

    # -- requests ---------------------------------------------------
    def _post(self, route, payload):
        self.ensure_up()
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.api_url}{route}", data=body,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            # A 400 from the API carries Hive's own error text in the
            # body, which is the useful part -- so read it rather than
            # letting urllib turn it into a bare "HTTP Error 400".
            try:
                detail = json.loads(e.read().decode("utf-8")).get("error", "")
            except Exception:
                detail = str(e)
            raise HiveError(detail) from None
        except (urllib.error.URLError, OSError) as e:
            raise HiveError(f"cannot reach the Hive API at {self.api_url}: {e}") from None

    def sql(self, sql, database=None):
        """Run SQL, return a list of row-lists. Raises HiveError on failure."""
        r = self._post("/sql", {"sql": sql, "database": database, "format": "json"})
        return r.get("rows", [])

    def sql_full(self, sql, database=None):
        """Like `sql`, but returns the whole payload including `columns`."""
        return self._post("/sql", {"sql": sql, "database": database, "format": "json"})

    def script(self, hql, database=None):
        """Run a whole .hql for side effects. Returns the per-statement report."""
        return self._post("/script", {"hql": hql, "database": database})

    def export_csv(self, table, container_path, database=None, order_by=None):
        """Write SELECT * FROM table to a headerless CSV inside /results."""
        return self._post("/export", {
            "table": table, "path": container_path,
            "database": database, "order_by": order_by,
        })

    def health(self):
        with urllib.request.urlopen(f"{self.api_url}/health", timeout=90) as r:
            return json.loads(r.read().decode("utf-8"))
