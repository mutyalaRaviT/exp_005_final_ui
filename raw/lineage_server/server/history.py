"""The estate's shadow git repo — code + edge timeline, pure python.

Every code save is one git commit in a tool-owned repo (default:
`output/estate_history/`). git's own fields carry the audit trail:
author = the editor, message = the reason, author_time = when. Two paths
per fileid: the SAS code at `<fileid>`, and the file's engine edges at
`<fileid>.edges.jsonl` (one sorted-JSON line per edge), so the edge
timeline of a save is a plain line-diff against the parent commit.

Implemented with dulwich (pure python) — production hosts need no git
binary. The service serializes writes, so no locking is needed here.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from dulwich import porcelain
from dulwich.object_store import tree_lookup_path
from dulwich.repo import Repo

EDGES_SUFFIX = ".edges.jsonl"


def _edge_lines(edges: list[dict]) -> str:
    lines = sorted(json.dumps(e, sort_keys=True) for e in edges)
    return "\n".join(lines) + ("\n" if lines else "")


def _parse_lines(blob: bytes) -> list[dict]:
    return [json.loads(line) for line in blob.decode().splitlines() if line]


class EstateHistory:
    def __init__(self, repo_dir: str | Path):
        # resolve up front: dulwich's add() rejects paths that do not
        # resolve inside the repo, and the server derives this dir from a
        # possibly-relative $SAS_DB
        self.repo_dir = Path(repo_dir).resolve()
        self._repo: Repo | None = None

    # ---- repo plumbing -----------------------------------------------------

    def _open(self) -> Repo:
        if self._repo is None:
            self.repo_dir.mkdir(parents=True, exist_ok=True)
            if not (self.repo_dir / ".git").exists():
                porcelain.init(str(self.repo_dir))
            self._repo = Repo(str(self.repo_dir))
        return self._repo

    def _head_tree(self, repo: Repo):
        try:
            return repo[repo.head()].tree
        except KeyError:
            return None

    def _blob_at(self, repo: Repo, tree, relpath: str) -> bytes | None:
        if tree is None:
            return None
        try:
            _mode, sha = tree_lookup_path(
                repo.get_object, tree, relpath.encode())
        except KeyError:
            return None
        return repo[sha].data

    # ---- public ------------------------------------------------------------

    def has_file(self, fileid: str) -> bool:
        repo = self._open()
        return self._blob_at(repo, self._head_tree(repo), fileid) is not None

    def record(self, fileid: str, code: str, edges: list[dict],
               editor: str, reason: str) -> str:
        """One save -> one commit. Returns the commit hash (hex)."""
        repo = self._open()
        code_path = self.repo_dir / fileid
        code_path.parent.mkdir(parents=True, exist_ok=True)
        code_path.write_text(code)
        edges_path = self.repo_dir / (fileid + EDGES_SUFFIX)
        edges_path.write_text(_edge_lines(edges))
        porcelain.add(repo, [str(code_path), str(edges_path)])
        ident = f"{editor} <{editor}@local>".encode()
        commit = porcelain.commit(
            repo, message=reason.encode(), author=ident, committer=ident)
        return commit.decode()

    def history(self, fileid: str) -> list[dict]:
        """Newest-first commits touching this fileid, each with its edge
        delta vs the parent commit (`added` / `removed` lists of edge
        dicts)."""
        repo = self._open()
        if self._head_tree(repo) is None:
            return []
        paths = [fileid.encode(), (fileid + EDGES_SUFFIX).encode()]
        entries = []
        for walk in repo.get_walker(paths=paths):
            commit = walk.commit
            edges_now = _parse_lines(
                self._blob_at(repo, commit.tree, fileid + EDGES_SUFFIX)
                or b"")
            parent_tree = (repo[commit.parents[0]].tree
                           if commit.parents else None)
            edges_before = _parse_lines(
                self._blob_at(repo, parent_tree, fileid + EDGES_SUFFIX)
                or b"")
            now = {json.dumps(e, sort_keys=True) for e in edges_now}
            before = {json.dumps(e, sort_keys=True) for e in edges_before}
            author = commit.author.decode()
            saved_at = datetime.fromtimestamp(
                commit.author_time, tz=timezone.utc).isoformat()
            entries.append({
                "commit": commit.id.decode(),
                "saved_at": saved_at,
                "editor": author.split(" <")[0],
                "reason": commit.message.decode().strip(),
                "added": [json.loads(s) for s in sorted(now - before)],
                "removed": [json.loads(s) for s in sorted(before - now)],
            })
        return entries

    def at(self, fileid: str, commit: str) -> dict:
        """The file's code and edges as of one commit."""
        repo = self._open()
        tree = repo[commit.encode()].tree
        code = self._blob_at(repo, tree, fileid)
        if code is None:
            raise ValueError(f"{fileid} not present at {commit}")
        edges = self._blob_at(repo, tree, fileid + EDGES_SUFFIX) or b""
        return {"code": code.decode(), "edges": _parse_lines(edges)}
