"""_shared.queries — pure DB lookups every tool shares.

Only functions with a live consumer exist (extraction rule: nothing
speculative). Current consumers: plan-verifier, diff-verifier.
All results are pure functions of the DB — same DB file, same answer.
"""

from __future__ import annotations

import sqlite3

# Who breaks if the target changes/disappears. `instantiates` included: the
# pilot DBs emit it for class construction and deleting a class with live
# instantiators breaks them exactly like deleting a called function.
BLAST_KINDS = ("calls", "references", "imports", "instantiates")


def callers_of(con: sqlite3.Connection, node_id: str) -> list[dict]:
    """Incoming blast-radius edges for one node: who calls/references/imports it."""
    rows = con.execute(
        f"""SELECT src.name, src.file_path, e.line, e.kind
            FROM edges e
            JOIN nodes src ON e.source = src.id
            WHERE e.target = ? AND e.kind IN ({",".join("?" * len(BLAST_KINDS))})""",
        (node_id, *BLAST_KINDS),
    ).fetchall()
    return [{"name": r[0], "file_path": r[1], "line": r[2], "kind": r[3]} for r in rows]


def callers_of_name(con: sqlite3.Connection, name: str) -> list[dict]:
    """Blast radius by target NAME (any node with that name). Coarser than
    callers_of — use only when no unique node id is available."""
    rows = con.execute(
        f"""SELECT src.name, src.file_path, e.line, e.kind
            FROM edges e
            JOIN nodes src ON e.source = src.id
            JOIN nodes tgt ON e.target = tgt.id
            WHERE tgt.name = ? AND e.kind IN ({",".join("?" * len(BLAST_KINDS))})""",
        (name, *BLAST_KINDS),
    ).fetchall()
    return [{"name": r[0], "file_path": r[1], "line": r[2], "kind": r[3]} for r in rows]


def nodes_for_file(con: sqlite3.Connection, relpath: str) -> list[dict]:
    rows = con.execute(
        "SELECT id, kind, name, qualified_name, start_line, end_line "
        "FROM nodes WHERE file_path = ? ORDER BY start_line",
        (relpath,),
    ).fetchall()
    return [{"id": r[0], "kind": r[1], "name": r[2], "qualified_name": r[3],
             "start_line": r[4], "end_line": r[5]} for r in rows]


def unresolved_ref_names(con: sqlite3.Connection) -> set[str]:
    """Names codegraph could not statically resolve (dynamic dispatch signal).
    Returns empty set when the table is absent (older codegraph versions)."""
    try:
        return {r[0] for r in con.execute(
            "SELECT DISTINCT reference_name FROM unresolved_refs")}
    except sqlite3.OperationalError:
        return set()
