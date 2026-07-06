"""_shared.db — codegraph DB discovery + read-only access.

The ONLY sanctioned way to open `.codegraph/codegraph.db`. Extracted verbatim
from `ssot-diagram/decision_index.py` (Phase B, per skeleton-contracts Block 1).

Invariants (frozen, Block 1e):
- read-only connect: `mode=ro&immutable=1` (codegraph uses WAL; a pure mode=ro
  open would need a -shm file; immutable keeps the zero-write coupling)
- schema guard fails loudly on unrecognized schema — never guesses
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


class SchemaError(RuntimeError):
    """Raised when the codegraph DB schema is not recognized."""


def find_db(start: Path) -> Path | None:
    """Walk up from `start` for a .codegraph/codegraph.db."""
    start = Path(start)
    if start.is_file():
        start = start.parent
    for d in [start, *start.parents]:
        cand = d / ".codegraph" / "codegraph.db"
        if cand.is_file():
            return cand
    return None


def repo_root_for(db: Path) -> Path:
    """The indexed repo root is the parent of the .codegraph/ dir."""
    return db.parent.parent


def open_db(path: Path) -> sqlite3.Connection:
    """Read-only connection with schema guard. Raises SchemaError/FileNotFoundError
    instead of exiting — callers decide whether to die (CLI) or fail open (hook)."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"codegraph index not found: {path} (run `codegraph init` first)")
    con = sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True)
    verify_schema(con, path)
    return con


def verify_schema(con: sqlite3.Connection, path: Path) -> None:
    """Guard against an unexpected codegraph schema — read-only coupling to its
    internals, so fail loudly rather than emit wrong answers."""
    node_cols = {r[1] for r in con.execute("PRAGMA table_info(nodes)")}
    file_cols = {r[1] for r in con.execute("PRAGMA table_info(files)")}
    need_nodes = {"name", "qualified_name", "file_path", "start_line", "end_line"}
    need_files = {"path", "content_hash"}
    if not need_nodes <= node_cols or not need_files <= file_cols:
        raise SchemaError(
            f"{path} schema not recognized (codegraph version drift?); refusing to guess."
        )
