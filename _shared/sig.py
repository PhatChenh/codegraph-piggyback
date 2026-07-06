"""_shared.sig — content-signature recipes (the single mint).

Extracted from `ssot-diagram/decision_index.py` (Phase B). Frozen recipes
(skeleton-contracts Block 1e):
- file      = files.content_hash (codegraph's own sha256 of the file)
- symbol    = sha256 of its source slice [start_line, end_line] — CONTENT,
              never ids or line numbers
- component = sha256 over sorted member hashes
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


def file_content_hash(con: sqlite3.Connection, relpath: str) -> str | None:
    row = con.execute("SELECT content_hash FROM files WHERE path = ?", (relpath,)).fetchone()
    return row[0] if row else None


def symbol_spans(con: sqlite3.Connection, qname: str, relpath: str) -> list[tuple[int, int]]:
    rows = con.execute(
        "SELECT start_line, end_line FROM nodes WHERE qualified_name = ? AND file_path = ?",
        (qname, relpath),
    ).fetchall()
    return [(int(a), int(b)) for a, b in rows]


def slice_hash(root: Path, relpath: str, start: int, end: int) -> str | None:
    """sha256 of a symbol's source lines [start,end] (1-based inclusive). Hashes
    CONTENT, not line numbers, so edits elsewhere in the file don't trip it."""
    p = root / relpath
    if not p.is_file():
        return None
    lines = p.read_text(errors="replace").splitlines()
    return sha256_text("\n".join(lines[start - 1:end]))


def component_sig(member_hashes: list[str]) -> str:
    """Component signature = sha256 over the SORTED member hashes (order-stable)."""
    return sha256_text("\n".join(sorted(member_hashes)))
