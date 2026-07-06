"""_shared.resolve — the lookup core (frozen seam, skeleton-contracts Block 1a).

    resolve(con, token, file_hint=None) -> Resolution

Resolution.state is exactly one of UNIQUE / AMBIGUOUS / UNRESOLVED. Never
guesses: >1 match -> AMBIGUOUS with candidate list; 0 -> UNRESOLVED.

Notation parsing (`qname@path` anchors, `path::symbol` manifests, backticked
prose tokens) stays PER-TOOL — each tool converts its notation into a resolve()
call. This module only answers "what code does this token name?".

A token resolves as a FILE when it looks path-like (contains a dot-extension or
a slash), else as a SYMBOL (matched on nodes.name OR nodes.qualified_name,
optionally scoped to file_hint).
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field

UNIQUE, AMBIGUOUS, UNRESOLVED = "UNIQUE", "AMBIGUOUS", "UNRESOLVED"

_PATHISH = re.compile(r"^[\w./-]+\.[A-Za-z0-9]+$")   # foo/bar.ts, worker.ts
_IDENT = re.compile(r"^[A-Za-z_][\w.]*$")            # ModelEntry, Class.method


@dataclass
class Candidate:
    """One match. For files: kind='file', path set, others None."""
    kind: str
    name: str | None
    qualified_name: str | None
    file_path: str
    start_line: int | None = None
    end_line: int | None = None
    node_id: str | None = None

    @property
    def loc(self) -> str:
        if self.start_line is not None:
            return f"{self.file_path}:{self.start_line}"
        return self.file_path


@dataclass
class Resolution:
    state: str                       # UNIQUE | AMBIGUOUS | UNRESOLVED
    candidates: list[Candidate] = field(default_factory=list)

    @property
    def node(self) -> Candidate | None:
        return self.candidates[0] if self.state == UNIQUE else None


def looks_pathish(token: str) -> bool:
    return bool(_PATHISH.match(token)) or "/" in token


def resolve(con: sqlite3.Connection, token: str, file_hint: str | None = None) -> Resolution:
    token = token.strip()
    if not token:
        return Resolution(UNRESOLVED)
    if file_hint is None and looks_pathish(token):
        return _resolve_file(con, token)
    if not _IDENT.match(token):
        return Resolution(UNRESOLVED)
    return _resolve_symbol(con, token, file_hint)


def _resolve_file(con: sqlite3.Connection, token: str) -> Resolution:
    rows = con.execute("SELECT path FROM files WHERE path = ?", (token,)).fetchall()
    if not rows:
        rows = con.execute(
            "SELECT path FROM files WHERE path LIKE ?", ("%/" + token,)
        ).fetchall()
    cands = [Candidate(kind="file", name=None, qualified_name=None, file_path=r[0])
             for r in rows]
    return _verdict(cands)


def _resolve_symbol(con: sqlite3.Connection, token: str,
                    file_hint: str | None) -> Resolution:
    sql = ("SELECT id, kind, name, qualified_name, file_path, start_line, end_line "
           "FROM nodes WHERE (name = ? OR qualified_name = ?)")
    params: list = [token, token]
    if file_hint:
        # scope to the hinted file; accept exact path or suffix match so hints
        # written repo-relative and hints written basename-only both work
        sql += " AND (file_path = ? OR file_path LIKE ?)"
        params += [file_hint, "%/" + file_hint.lstrip("/")]
    rows = con.execute(sql, params).fetchall()
    cands = [Candidate(node_id=r[0], kind=r[1], name=r[2], qualified_name=r[3],
                       file_path=r[4], start_line=int(r[5]), end_line=int(r[6]))
             for r in rows]
    # containers duplicate leaf names (a file node named like its function, a
    # class + its __init__); if exactly one NON-container candidate remains,
    # prefer it — this mirrors "same code" rather than guessing between code.
    if len(cands) > 1:
        leaves = [c for c in cands if c.kind not in ("file", "import")]
        if len(leaves) == 1:
            cands = leaves
    return _verdict(cands)


def _verdict(cands: list[Candidate]) -> Resolution:
    if not cands:
        return Resolution(UNRESOLVED)
    if len(cands) == 1:
        return Resolution(UNIQUE, cands)
    return Resolution(AMBIGUOUS, cands)
