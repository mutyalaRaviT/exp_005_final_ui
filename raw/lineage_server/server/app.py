"""FastAPI wiring for the live SAS dependency explorer.

Thin HTTP layer over `Indexer`/`Service`: every route is a direct call into
already-tested Python (`orderer`, `scanners`, `indexer`, `service`) — no
analysis logic lives here beyond parsing query params and shaping the JSON
response. Data-flow notation (`x -> y`) in every user-facing string comes
from the layers underneath.

`create_app(roots, db_path)` is the app factory: each call wires a fresh
`Indexer`/`Service` pair against the given roots/db, so tests can inject a
tmp repo and a tmp DuckDB file without touching the real dataset. The
module-level `app` only exists when this file is run directly (`python
app.py` / `uvicorn app:app`) — importing the module (as tests do) never
builds an index or touches `SAS_ROOTS`/`SAS_DB`.
"""
import os
import threading
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from history import EstateHistory
from indexer import Indexer
from orderer import Flow, compute_order
from sas_lineage.store import LineageStore
from sas_lineage.ui_export import project_edges
from scanners import active_scanner
from service import ACTIONS, Service, order_payload

#: the only dev origin the local Vite frontend runs on
ALLOWED_ORIGIN = "http://localhost:5173"

EXCEL_MEDIA_TYPE = ("application/vnd.openxmlformats-officedocument"
                     ".spreadsheetml.sheet")

#: the columnar payload the browser's grid loads whole (Arrow IPC stream)
ARROW_MEDIA_TYPE = "application/vnd.apache.arrow.stream"


class EditIn(BaseModel):
    """Body of `POST /api/edits` — a customer's assertion about one flow.

    `block_id` pins a block-level edit to the block it was made against, so
    the final view can apply it to exactly that block (and so a later re-parse
    can flag it for re-checking when that block's text moves). A project-level
    edit has no single block behind it and leaves it unset.

    `fileid` names the file that block lives in — a block id is only unique
    WITHIN a file, so a block-level edit sends both. File- and project-level
    edits may leave it unset.
    """
    action: str
    src: str
    dst: str
    table_name: str
    level: str
    editor: str
    comment: str = ""
    block_id: str | None = None
    fileid: str | None = None


class SaveIn(BaseModel):
    """Body of `POST /api/file/{fileid}/save` — edited SAS code plus the
    audit trail git keeps: who saved (`editor`, the commit author) and why
    (`reason`, the commit message). When is stamped server-side."""
    code: str
    editor: str
    reason: str


def create_app(roots: list[str | Path], db_path: str | Path) -> FastAPI:
    """Wire one Indexer + Service against `roots`/`db_path` and return the
    FastAPI app. Indexing starts in a background thread on startup so the
    server answers `/api/status` immediately instead of blocking on it."""
    roots = [Path(r) for r in roots]
    store = LineageStore(db_path)
    indexer = Indexer(store, roots)
    # the shadow git repo (pure-python dulwich) lives beside the database
    history = EstateHistory(Path(db_path).parent / "estate_history")
    service = Service(store, indexer, roots, history=history)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        threading.Thread(target=indexer.build, daemon=True).start()
        yield

    app = FastAPI(title="SAS Dependency Explorer", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[ALLOWED_ORIGIN],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Arrow edge payloads are text-heavy (file/table names) and compress
    # several-fold; the browser's fetch decompresses transparently, so the
    # wire cost — what the payload budget measures — is the gzipped size.
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    @app.get("/api/status")
    def get_status():
        return {
            "state": indexer.progress["state"],
            "done": indexer.progress["done"],
            "total": indexer.progress["total"],
            "scanner": active_scanner(service.sources_ready()),
            "tables_known": indexer._tables_known(),
            **service.sync_status(),
        }

    @app.get("/api/files")
    def list_files():
        # through the service, so this read takes the same lock every other
        # store-touching call does — the explorer asks for it while the
        # grid's Arrow load is already on that one connection
        return {"files": service.list_files()}

    @app.get("/api/search")
    def search(q: str = ""):
        return {"hits": indexer.suggest(q)}

    @app.get("/api/neighborhood")
    def neighborhood(table: str | None = None, file: str | None = None,
                      depth: int = 1, up: int | None = None,
                      down: int | None = None):
        try:
            return service.neighborhood(table=table, file=file, depth=depth,
                                        up=up, down=down)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.get("/api/blocklinks")
    def blocklinks(files: str = ""):
        """Cross-file block->block links for the given files (CSV of
        fileids) — the block-level counterpart to `project_edges`."""
        return {"links": service.block_links(_split_files(files))}

    # NOTE: these two register BEFORE the generic /api/file/{fileid:path}
    # route — its `:path` parameter is greedy and would swallow the
    # `/history` and `/at/...` suffixes otherwise.
    @app.get("/api/file/{fileid:path}/history")
    def file_history(fileid: str):
        """The file's save timeline: one entry per shadow-repo commit —
        when, who (editor), why (reason), and the flow delta of that save."""
        return {"history": service.history.history(fileid)}

    @app.get("/api/file/{fileid:path}/at/{commit}")
    def file_at(fileid: str, commit: str):
        """The file's code and engine flows as of one timeline commit."""
        try:
            return service.history.at(fileid, commit)
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    @app.post("/api/file/{fileid:path}/save")
    def save_code(fileid: str, body: SaveIn):
        try:
            return service.save_code(fileid, body.code, body.editor,
                                     body.reason)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    @app.get("/api/file/{fileid:path}")
    def file_detail(fileid: str):
        try:
            return service.file_detail(fileid)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    @app.get("/api/order")
    def order(files: str = ""):
        fileids = _split_files(files) or _all_indexed_fileids(service)
        return _order_for(service, fileids)

    @app.get("/api/excel")
    def excel(files: str = ""):
        payload = service.excel_bytes(_split_files(files))
        stamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        return Response(
            content=payload,
            media_type=EXCEL_MEDIA_TYPE,
            headers={"Content-Disposition":
                     f"attachment; filename=lineage_{stamp}.xlsx"})

    @app.get("/api/edges")
    def edges(files: str = "", filter: str = "", level: str = "",
              offset: int = 0, limit: int = 200):
        fileids = _split_files(files) or _all_indexed_fileids(service)
        return service.final_edges(
            fileids, filter_text=filter or None, level=level or None,
            offset=offset, limit=limit)

    @app.get("/api/edges/arrow")
    def edges_arrow(files: str = "", view: str = "final"):
        """One whole edge view as an Apache Arrow IPC stream — the grid loads
        everything once and filters locally, instead of paging."""
        fileids = _split_files(files) or _all_indexed_fileids(service)
        try:
            payload = service.edges_arrow(fileids, view=view)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        return Response(content=payload, media_type=ARROW_MEDIA_TYPE)

    @app.get("/api/edits/pending")
    def pending_edits():
        """Human edits whose pinned block vanished in a re-parse — the
        review queue. Each row still carries the flow (src -> dst) so the
        strip can re-confirm or discard it in one click."""
        return {"pending": service.pending_checks()}

    @app.post("/api/edits")
    def add_edit(edit: EditIn):
        if edit.action not in ACTIONS:
            raise HTTPException(status_code=422, detail=(
                f"unknown action {edit.action!r}; expected one of "
                f"{', '.join(ACTIONS)}"))
        edit_id = service.add_edit(edit.action, edit.src, edit.dst,
                                    edit.table_name, edit.level, edit.editor,
                                    edit.comment, block_id=edit.block_id,
                                    fileid=edit.fileid)
        return {"edit_id": edit_id}

    @app.post("/api/sync")
    def sync():
        """Tree-wide hash-gated refresh — same walk the cron CLI runs
        (`scripts/sync_store.py`)."""
        return service.sync_sources()

    return app


def _split_files(files: str) -> list[str]:
    """`"a,b,c"` -> `["a", "b", "c"]`; blank/whitespace-only -> `[]`."""
    return [f.strip() for f in files.split(",") if f.strip()]


def _all_indexed_fileids(service: Service) -> list[str]:
    """Every indexed fileid, read through the service so it takes the same
    lock every other store-touching call does (see `Service.list_files`)."""
    return [row["id"] for row in service.list_files()]


def _order_for(service: Service, fileids: list[str]) -> dict:
    """Run-order scores for exactly these files' project-level flows among
    each other — the same computation `Service.neighborhood` does per
    neighborhood, minus the hop expansion: the given fileids are the whole
    graph asked about."""
    entries = service._entries_for(fileids)
    edges = project_edges(entries)
    order = compute_order(
        [Flow(e["src_file"], e["dst_file"], tuple(e["tables"]))
         for e in edges],
        nodes=[e["fileid"] for e in entries])
    labels = Service._labels(entries)
    return order_payload(order, labels)


def _env_roots() -> list[Path]:
    raw = os.environ.get("SAS_ROOTS", "inputs")
    return [Path(p.strip()) for p in raw.split(",") if p.strip()]


if __name__ == "__main__":
    import uvicorn

    app = create_app(_env_roots(),
                      os.environ.get("SAS_DB", "output/explorer.duckdb"))
    uvicorn.run(app, host="0.0.0.0", port=8000)
