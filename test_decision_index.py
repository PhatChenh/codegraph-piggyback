#!/usr/bin/env python3
"""Smoke test for decision_index.py + decision_hook.py.

Builds a throwaway repo with a hand-made codegraph SQLite (the same nodes/files
schema decision_index reads), an ADR doc, and exercises the CLI end-to-end:
bootstrap → status (FRESH) → mutate → status (STALE/ORPHANED) → refresh (FRESH),
plus the Read-hook and error paths. No network, no real codegraph.

Each scenario builds its own tmp repo — no cross-test shared state, order-free.

Run:  python3 test_decision_index.py     (exit 0 = all pass)
"""

import json
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = ROOT / "ssot-diagram" / "decision_index.py"
HOOK = ROOT / "ssot-diagram" / "decision_hook.py"
PASS = FAIL = 0

FOO_SRC = "def foo_func():\n    return 1\n"          # 2 lines; node spans 1..2
ADR = """# ADR-0001 — A Thing

**Status:** Accepted

We depend on `src/foo.py` and the `foo_func()` symbol.
Also mentions `op.type="resize"` (skipped) and `ghost_sym` (unresolvable).
"""


def make_repo(tmp: Path, content_hash="hash_v1", node=True, span=(1, 2)) -> Path:
    """Create root/{.codegraph/codegraph.db, src/foo.py, docs/adrs/ADR-0001.md}."""
    root = tmp / "repo"
    (root / ".codegraph").mkdir(parents=True)
    (root / "src").mkdir()
    (root / "docs" / "adrs").mkdir(parents=True)
    (root / "src" / "foo.py").write_text(FOO_SRC)
    (root / "docs" / "adrs" / "ADR-0001-thing.md").write_text(ADR)
    write_db(root / ".codegraph" / "codegraph.db", content_hash, node, span)
    return root


def write_db(dbpath: Path, content_hash, node, span):
    con = sqlite3.connect(dbpath)
    con.executescript("""
        CREATE TABLE nodes (
            id TEXT PRIMARY KEY, kind TEXT NOT NULL, name TEXT NOT NULL,
            qualified_name TEXT NOT NULL, file_path TEXT NOT NULL, language TEXT NOT NULL,
            start_line INTEGER NOT NULL, end_line INTEGER NOT NULL,
            start_column INTEGER NOT NULL, end_column INTEGER NOT NULL,
            signature TEXT, updated_at INTEGER NOT NULL);
        CREATE TABLE files (
            path TEXT PRIMARY KEY, content_hash TEXT NOT NULL, language TEXT NOT NULL,
            size INTEGER NOT NULL, modified_at INTEGER NOT NULL, indexed_at INTEGER NOT NULL);
    """)
    con.execute("INSERT INTO files VALUES (?,?,?,?,?,?)",
                ("src/foo.py", content_hash, "python", 42, 0, 0))
    if node:
        con.execute(
            "INSERT INTO nodes (id,kind,name,qualified_name,file_path,language,"
            "start_line,end_line,start_column,end_column,signature,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            ("function:abc", "function", "foo_func", "foo_func", "src/foo.py",
             "python", span[0], span[1], 0, 0, "() -> int", 0))
    con.commit()
    con.close()


def set_file_hash(root: Path, h: str):
    db = root / ".codegraph" / "codegraph.db"
    con = sqlite3.connect(db)
    con.execute("UPDATE files SET content_hash = ? WHERE path = 'src/foo.py'", (h,))
    con.commit(); con.close()


def drop_node(root: Path):
    db = root / ".codegraph" / "codegraph.db"
    con = sqlite3.connect(db)
    con.execute("DELETE FROM nodes WHERE name = 'foo_func'")
    con.commit(); con.close()


def set_wal_mode(root: Path):
    """Switch the fixture db to WAL journal mode (what real codegraph now emits)."""
    db = root / ".codegraph" / "codegraph.db"
    con = sqlite3.connect(db)
    con.execute("PRAGMA journal_mode=WAL")
    con.commit(); con.close()


def cli(args, cwd):
    return subprocess.run([sys.executable, str(CLI), *args],
                          cwd=str(cwd), capture_output=True, text=True)


def hook(payload, cwd):
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                          cwd=str(cwd), capture_output=True, text=True)


def index_of(root):
    return json.loads((root / "docs" / "decision-index.json").read_text())


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1; print(f"  PASS {name}")
    else:
        FAIL += 1; print(f"  FAIL {name}")


def scenario(fn):
    with tempfile.TemporaryDirectory() as td:
        fn(Path(td))


def t_bootstrap(td):
    root = make_repo(td)
    r = cli(["bootstrap"], root)
    idx = index_of(root)
    dec = idx["decisions"].get("ADR-0001", {})
    refs = {a["ref"] for a in dec.get("anchors", [])}
    check("bootstrap creates index", (root / "docs" / "decision-index.json").exists())
    check("bootstrap finds ADR-0001", "ADR-0001" in idx["decisions"])
    check("bootstrap resolves file anchor", "file:src/foo.py" in refs)
    check("bootstrap resolves symbol anchor", "foo_func@src/foo.py" in refs)
    check("bootstrap anchors are unverified", all(not a["verified"] for a in dec["anchors"]))
    check("bootstrap status parsed", dec.get("status") == "accepted")
    check("bootstrap reports unresolved ghost_sym", "ghost_sym" in r.stderr)
    check("bootstrap refuses overwrite without --force", cli(["bootstrap"], root).returncode == 2)


def t_status_fresh(td):
    root = make_repo(td)
    cli(["bootstrap"], root)
    r = cli(["status"], root)
    check("status fresh exits 0", r.returncode == 0)
    check("status fresh all FRESH", "STALE" not in r.stdout and "ORPHANED" not in r.stdout)


def t_file_stale(td):
    root = make_repo(td)
    cli(["bootstrap"], root)
    set_file_hash(root, "hash_v2")
    r = cli(["status"], root)
    check("file edit → exit 1", r.returncode == 1)
    check("file edit → file anchor STALE",
          "STALE" in r.stdout and "file:src/foo.py" in r.stdout)
    check("file edit → symbol still FRESH", "foo_func@src/foo.py" in
          [ln.split()[-1] for ln in r.stdout.splitlines() if "FRESH" in ln][0])


def t_symbol_stale(td):
    root = make_repo(td)
    cli(["bootstrap"], root)
    (root / "src" / "foo.py").write_text("def foo_func():\n    return 999\n")
    r = cli(["status"], root)
    check("symbol body edit → exit 1", r.returncode == 1)
    check("symbol body edit → symbol STALE",
          any("STALE" in ln and "foo_func@src/foo.py" in ln for ln in r.stdout.splitlines()))


def t_orphaned(td):
    root = make_repo(td)
    cli(["bootstrap"], root)
    drop_node(root)
    set_file_hash(root, "gone")  # change file too, but real orphan = dropped node
    r = cli(["status"], root)
    check("dropped node → ORPHANED", any("ORPHANED" in ln and "foo_func" in ln
                                         for ln in r.stdout.splitlines()))


def t_refresh(td):
    root = make_repo(td)
    cli(["bootstrap"], root)
    set_file_hash(root, "hash_v2")
    check("pre-refresh stale", cli(["status"], root).returncode == 1)
    cli(["refresh", "ADR-0001"], root)
    r = cli(["status"], root)
    check("refresh → FRESH again", r.returncode == 0)
    dec = index_of(root)["decisions"]["ADR-0001"]
    check("refresh marks verified", all(a["verified"] for a in dec["anchors"]))


def t_check_cmd(td):
    root = make_repo(td)
    cli(["bootstrap"], root)
    adr = root / "docs" / "adrs" / "ADR-0001-thing.md"
    check("check fresh exits 0", cli(["check", str(adr)], root).returncode == 0)
    set_file_hash(root, "hash_v2")
    r = cli(["check", str(adr)], root)
    check("check stale exits 1", r.returncode == 1)
    check("check stale names anchor", "file:src/foo.py" in r.stdout)


def t_hook(td):
    root = make_repo(td)
    cli(["bootstrap"], root)
    adr = str(root / "docs" / "adrs" / "ADR-0001-thing.md")

    fresh = hook({"tool_name": "Read", "tool_input": {"file_path": adr}, "cwd": str(root)}, root)
    check("hook fresh emits nothing", fresh.stdout.strip() == "" and fresh.returncode == 0)

    set_file_hash(root, "hash_v2")
    stale = hook({"tool_name": "Read", "tool_input": {"file_path": adr}, "cwd": str(root)}, root)
    payload = json.loads(stale.stdout) if stale.stdout.strip() else {}
    ctx = payload.get("hookSpecificOutput", {}).get("additionalContext", "")
    check("hook stale emits additionalContext", "DECISION STALENESS" in ctx and "STALE" in ctx)
    check("hook stale tells agent to propose not rewrite", "do NOT silently rewrite" in ctx)

    other = hook({"tool_name": "Read", "tool_input": {"file_path": str(root / "src" / "foo.py")},
                  "cwd": str(root)}, root)
    check("hook ignores non-decision file", other.stdout.strip() == "")


def t_errors(td):
    root = make_repo(td)
    # bad index json
    cli(["bootstrap"], root)
    (root / "docs" / "decision-index.json").write_text("{ not json ]")
    check("bad index json → exit 2", cli(["status"], root).returncode == 2)
    # no db at all
    bare = td / "bare"
    bare.mkdir()
    check("no codegraph db → exit 2", cli(["status"], bare).returncode == 2)


def t_wal_db(td):
    # Regression: codegraph switched to WAL journal mode; a WAL db cannot be opened
    # pure mode=ro (needs to create a -shm file). open_db uses immutable=1 to read it.
    root = make_repo(td)
    set_wal_mode(root)
    r = cli(["bootstrap"], root)
    check("WAL db → bootstrap exits 0", r.returncode == 0)
    check("WAL db → no 'unable to open' error", "unable to open database file" not in r.stderr)
    check("WAL db → status FRESH", cli(["status"], root).returncode == 0)
    cg = root / ".codegraph"
    check("WAL db → read created no -shm/-wal in source repo",
          not (cg / "codegraph.db-shm").exists() and not (cg / "codegraph.db-wal").exists())


def main():
    for fn in (t_bootstrap, t_status_fresh, t_file_stale, t_symbol_stale,
               t_orphaned, t_refresh, t_check_cmd, t_hook, t_errors, t_wal_db):
        print(f"\n# {fn.__name__}")
        scenario(fn)
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
