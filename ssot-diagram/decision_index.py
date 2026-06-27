#!/usr/bin/env python3
"""decision_index — deterministic decision-staleness tracking over codegraph.

A decision (an ADR, a design doc) depends on code. When that code changes, the
decision MIGHT be stale. This tool detects that deterministically: each decision
declares ANCHORS (a file or a symbol); each anchor carries a SIGNATURE snapshot
taken when the decision was last confirmed. On demand, the current signature is
recomputed from codegraph's index and compared:

    FRESH      signature unchanged           — decision still rests on the same code
    STALE      signature changed             — code drifted; a human must review
    ORPHANED   anchor's file/symbol is gone  — anchor points at nothing
    AMBIGUOUS  symbol name+path matches >1    — anchor under-specified

No LLM is in that verdict — it is a pure compare. The tool NEVER edits a
decision document; the only write paths are `bootstrap` (seed a fresh index)
and `refresh` (re-snapshot after a human confirms a decision still holds).

Signature source is codegraph's SQLite index (`.codegraph/codegraph.db`), read
strictly read-only:
  - file anchor   `file:<relpath>`        sig = files.content_hash (sha256 of file)
  - symbol anchor `<qualified_name>@<relpath>`
                  sig = sha256 of the symbol's source slice [start_line,end_line]

Commands:
  bootstrap   scan decision docs, extract+validate candidate anchors against the
              codegraph index, write a SEED index (every anchor verified:false —
              a human curates). This is what produces a project's index file.
  status      compare every anchor's snapshot vs current; exit 1 if any not FRESH.
  check DOC   one document's anchor statuses (the Read-hook calls this).
  refresh ID  re-snapshot a decision's anchors (human-gated "still valid").
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

DEFAULT_DOCS_GLOB = "docs/adrs/*.md"
DEFAULT_INDEX_REL = "docs/decision-index.json"

FRESH, STALE, ORPHANED, AMBIGUOUS = "FRESH", "STALE", "ORPHANED", "AMBIGUOUS"


# ── discovery ──────────────────────────────────────────────────────────────────

def find_db(start: Path) -> Path | None:
    """Walk up from `start` for a .codegraph/codegraph.db."""
    for d in [start, *start.parents]:
        cand = d / ".codegraph" / "codegraph.db"
        if cand.is_file():
            return cand
    return None


def repo_root_for(db: Path) -> Path:
    """The indexed repo root is the parent of the .codegraph/ dir."""
    return db.parent.parent


def default_index_path(root: Path) -> Path:
    return root / DEFAULT_INDEX_REL


# ── codegraph db (read-only) ────────────────────────────────────────────────────

def open_db(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        die(f"codegraph index not found: {path} (run `codegraph init` first)")
    # immutable=1: codegraph now uses WAL journal mode; a WAL db cannot be opened
    # pure mode=ro (SQLite must create a -shm file → "unable to open database file").
    # immutable promises the file is not being written, so reads skip wal/shm and
    # touch nothing in the source repo — preserving the zero-write coupling.
    con = sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True)
    verify_schema(con, path)
    return con


def verify_schema(con: sqlite3.Connection, path: Path) -> None:
    """Guard against an unexpected codegraph schema — read-only coupling to its
    internals, so fail loudly rather than emit wrong signatures."""
    node_cols = {r[1] for r in con.execute("PRAGMA table_info(nodes)")}
    file_cols = {r[1] for r in con.execute("PRAGMA table_info(files)")}
    need_nodes = {"name", "qualified_name", "file_path", "start_line", "end_line"}
    need_files = {"path", "content_hash"}
    if not need_nodes <= node_cols or not need_files <= file_cols:
        die(f"{path} schema not recognized (codegraph version drift?); refusing to guess.")


def file_content_hash(con: sqlite3.Connection, relpath: str) -> str | None:
    row = con.execute("SELECT content_hash FROM files WHERE path = ?", (relpath,)).fetchone()
    return row[0] if row else None


def symbol_spans(con: sqlite3.Connection, qname: str, relpath: str) -> list[tuple[int, int]]:
    rows = con.execute(
        "SELECT start_line, end_line FROM nodes WHERE qualified_name = ? AND file_path = ?",
        (qname, relpath),
    ).fetchall()
    return [(int(a), int(b)) for a, b in rows]


# ── signatures ──────────────────────────────────────────────────────────────────

def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


def slice_hash(root: Path, relpath: str, start: int, end: int) -> str | None:
    """sha256 of a symbol's source lines [start,end] (1-based inclusive). Hashes
    CONTENT, not line numbers, so edits elsewhere in the file don't trip it."""
    p = root / relpath
    if not p.is_file():
        return None
    lines = p.read_text(errors="replace").splitlines()
    return _sha256("\n".join(lines[start - 1:end]))


def parse_ref(ref: str) -> tuple:
    """`file:<path>` → ('file', path);  `<qualified_name>@<path>` → ('sym', name, path)."""
    if ref.startswith("file:"):
        return ("file", ref[len("file:"):])
    if "@" in ref:
        name, path = ref.rsplit("@", 1)
        if name and path:
            return ("sym", name, path)
    die(f"bad anchor ref {ref!r} (want 'file:<path>' or '<qualified_name>@<path>')")


def current_sig(con: sqlite3.Connection, root: Path, ref: str) -> tuple[str, str | None]:
    """Return (state, sig). state == 'OK' means sig is the live signature to
    compare; otherwise sig is None and state is ORPHANED/AMBIGUOUS."""
    parsed = parse_ref(ref)
    if parsed[0] == "file":
        h = file_content_hash(con, parsed[1])
        return ("OK", h) if h is not None else (ORPHANED, None)
    _, qname, relpath = parsed
    spans = symbol_spans(con, qname, relpath)
    if not spans:
        return (ORPHANED, None)
    if len(spans) > 1:
        return (AMBIGUOUS, None)
    start, end = spans[0]
    sh = slice_hash(root, relpath, start, end)
    return ("OK", sh) if sh is not None else (ORPHANED, None)


def anchor_status(con: sqlite3.Connection, root: Path, anchor: dict) -> str:
    state, sig = current_sig(con, root, anchor["ref"])
    if state != "OK":
        return state
    return FRESH if sig == anchor.get("sig") else STALE


# ── index io ────────────────────────────────────────────────────────────────────

def load_index(path: Path) -> dict:
    if not path.is_file():
        die(f"decision index not found: {path} (run `decision_index bootstrap` to seed it)")
    try:
        doc = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        die(f"{path} is not valid JSON: {e}")
    if not isinstance(doc.get("decisions"), dict):
        die(f"{path} missing top-level 'decisions' object")
    return doc


def save_index(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=2) + "\n")
    os.replace(tmp, path)


# ── bootstrap (seed an index from decision docs) ────────────────────────────────

_TOKEN_RE = re.compile(r"`([^`]+)`")
_PATHISH = re.compile(r"^[\w./-]+\.[A-Za-z0-9]+$")     # foo/bar.ts, worker.ts
_IDENT = re.compile(r"^[A-Za-z_]\w*$")                  # ModelEntry, push
_ADR_ID = re.compile(r"(ADR-\d+)", re.IGNORECASE)
_STATUS = re.compile(r"\*\*Status:\*\*\s*([A-Za-z]+)")


def extract_candidates(text: str) -> list[str]:
    """Backtick tokens that look like a file path or a bare identifier. Tokens
    with spaces/operators/quotes (e.g. `op.type="resize"`) are skipped."""
    out, seen = [], set()
    for raw in _TOKEN_RE.findall(text):
        tok = raw.strip().rstrip("()")              # push() → push
        if tok in seen:
            continue
        if _PATHISH.match(tok) or _IDENT.match(tok):
            seen.add(tok)
            out.append(tok)
    return out


def resolve_token(con: sqlite3.Connection, token: str) -> str | None:
    """Map a doc token to a unique anchor ref, or None if it doesn't resolve to
    exactly one file/symbol. Conservative: ambiguous tokens are dropped (and
    reported), never guessed."""
    if _PATHISH.match(token):
        rows = con.execute("SELECT path FROM files WHERE path = ?", (token,)).fetchall()
        if not rows:
            rows = con.execute("SELECT path FROM files WHERE path LIKE ?",
                               ("%/" + token,)).fetchall()
        if len(rows) == 1:
            return "file:" + rows[0][0]
        return None
    rows = con.execute(
        "SELECT qualified_name, file_path FROM nodes WHERE name = ?", (token,)
    ).fetchall()
    if len(rows) == 1:
        return f"{rows[0][0]}@{rows[0][1]}"
    return None


def decision_id_for(doc_path: Path) -> str:
    m = _ADR_ID.search(doc_path.name)
    return m.group(1).upper() if m else doc_path.stem


def cmd_bootstrap(args) -> None:
    db = Path(args.db) if args.db else find_db(Path.cwd())
    if not db:
        die("no .codegraph/codegraph.db found (run `codegraph init` first)")
    root = repo_root_for(db)
    out = Path(args.out) if args.out else default_index_path(root)
    if out.exists() and not args.force:
        die(f"{out} exists — refusing to overwrite a curated index. Pass --force to reseed.")

    con = open_db(db)
    docs = sorted(root.glob(args.docs))
    if not docs:
        die(f"no decision docs matched {args.docs!r} under {root}")

    decisions, total_anchors, unresolved = {}, 0, []
    for doc in docs:
        text = doc.read_text(errors="replace")
        did = decision_id_for(doc)
        status_m = _STATUS.search(text)
        anchors, seen_refs = [], set()
        for tok in extract_candidates(text):
            ref = resolve_token(con, tok)
            if ref is None:
                unresolved.append(f"{did}: `{tok}`")
                continue
            if ref in seen_refs:
                continue
            seen_refs.add(ref)
            state, sig = current_sig(con, root, ref)
            anchors.append({"ref": ref, "sig": sig, "verified": False})
            total_anchors += 1
        decisions[did] = {
            "doc": str(doc.relative_to(root)),
            "status": (status_m.group(1).lower() if status_m else "unknown"),
            "supersedes": None,
            "anchors": anchors,
        }

    save_index(out, {"decisions": decisions})
    ok(f"seeded {out}: {len(decisions)} decision(s), {total_anchors} anchor(s)")
    info("every anchor is verified:false — curate it: drop wrong anchors, add missed ones, set supersedes.")
    if unresolved:
        warn(f"{len(unresolved)} doc token(s) did not resolve to a unique file/symbol (skipped):")
        for u in unresolved[:40]:
            info(f"    {u}")
        if len(unresolved) > 40:
            info(f"    … and {len(unresolved) - 40} more")


# ── status / check / refresh ────────────────────────────────────────────────────

def _resolve_db_root_index(args) -> tuple[sqlite3.Connection, Path, Path]:
    db = Path(args.db) if args.db else find_db(Path.cwd())
    if not db:
        die("no .codegraph/codegraph.db found (run `codegraph init` first)")
    root = repo_root_for(db)
    index_path = Path(args.index) if args.index else default_index_path(root)
    return open_db(db), root, index_path


def _evaluate(con, root, decisions: dict) -> tuple[list, int]:
    """Return (rows, n_not_fresh). rows = (did, ref, state)."""
    rows, not_fresh = [], 0
    for did, dec in decisions.items():
        for a in dec.get("anchors", []):
            state = anchor_status(con, root, a)
            if state != FRESH:
                not_fresh += 1
            rows.append((did, a["ref"], state))
    return rows, not_fresh


def cmd_status(args) -> None:
    con, root, index_path = _resolve_db_root_index(args)
    doc = load_index(index_path)
    rows, not_fresh = _evaluate(con, root, doc["decisions"])
    if args.json:
        print(json.dumps([{"decision": d, "ref": r, "state": s} for d, r, s in rows], indent=2))
    else:
        for did, ref, state in rows:
            mark = " " if state == FRESH else "!"
            print(f"[{mark}] {state:<9} {did}  {ref}")
        n = len(rows)
        print(f"\n{n - not_fresh}/{n} anchors FRESH; {not_fresh} need review", file=sys.stderr)
    sys.exit(1 if not_fresh else 0)


def cmd_check(args) -> None:
    """One document's status — used by the Read-hook. Quiet when all FRESH."""
    con, root, index_path = _resolve_db_root_index(args)
    doc = load_index(index_path)
    target = Path(args.doc).resolve()
    hits = {did: dec for did, dec in doc["decisions"].items()
            if (root / dec["doc"]).resolve() == target or dec["doc"] == args.doc
            or Path(dec["doc"]).name == Path(args.doc).name}
    if not hits:
        sys.exit(0)
    rows, not_fresh = _evaluate(con, root, hits)
    for did, ref, state in rows:
        if state != FRESH:
            print(f"{state}: {did} anchor {ref}")
    sys.exit(1 if not_fresh else 0)


def cmd_refresh(args) -> None:
    """Re-snapshot a decision's anchors — the human-gated 'still valid' path.
    Reads the live index (not read-only), recomputes sigs, writes back."""
    con, root, index_path = _resolve_db_root_index(args)
    doc = load_index(index_path)
    dec = doc["decisions"].get(args.id)
    if dec is None:
        die(f"no decision '{args.id}' in {index_path}")
    changed = 0
    for a in dec.get("anchors", []):
        if args.anchor and a["ref"] != args.anchor:
            continue
        state, sig = current_sig(con, root, a["ref"])
        if state != "OK":
            warn(f"{a['ref']}: {state} — not refreshing (fix the anchor first)")
            continue
        if a.get("sig") != sig:
            a["sig"] = sig
            changed += 1
        a["verified"] = True
    save_index(index_path, doc)
    ok(f"refreshed {args.id}: {changed} signature(s) updated, anchors marked verified")


# ── helpers ─────────────────────────────────────────────────────────────────────

def info(msg: str) -> None:
    print(msg, file=sys.stderr)


def ok(msg: str) -> None:
    print(f"✓ {msg}", file=sys.stderr)


def warn(msg: str) -> None:
    print(f"! {msg}", file=sys.stderr)


def die(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(2)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="decision_index", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--db", help="path to .codegraph/codegraph.db (default: search upward)")
        sp.add_argument("--index", help=f"path to the index json (default: <root>/{DEFAULT_INDEX_REL})")

    pb = sub.add_parser("bootstrap", help="seed an index from decision docs")
    pb.add_argument("--docs", default=DEFAULT_DOCS_GLOB,
                    help=f"glob (relative to repo root) of decision docs (default: {DEFAULT_DOCS_GLOB})")
    pb.add_argument("--db", help="path to .codegraph/codegraph.db (default: search upward)")
    pb.add_argument("--out", help=f"output index path (default: <root>/{DEFAULT_INDEX_REL})")
    pb.add_argument("--force", action="store_true", help="overwrite an existing index")
    pb.set_defaults(fn=cmd_bootstrap)

    ps = sub.add_parser("status", help="compare every anchor; exit 1 if any not FRESH")
    common(ps)
    ps.add_argument("--json", action="store_true", help="machine-readable output")
    ps.set_defaults(fn=cmd_status)

    pc = sub.add_parser("check", help="one document's status (used by the Read-hook)")
    pc.add_argument("doc", help="path to a decision document")
    common(pc)
    pc.set_defaults(fn=cmd_check)

    pr = sub.add_parser("refresh", help="re-snapshot a decision's anchors (human-gated)")
    pr.add_argument("id", help="decision id, e.g. ADR-0007")
    pr.add_argument("--anchor", help="refresh only this anchor ref")
    common(pr)
    pr.set_defaults(fn=cmd_refresh)
    return p


def main() -> None:
    args = build_parser().parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
