"""Tests for plan_verify.py — synthetic codegraph DB, every verdict class,
strict gate semantics, hook mode. Run: python3 -m pytest plan-verifier/ -q"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
CLI = HERE / "plan_verify.py"
sys.path.insert(0, str(HERE))
import plan_verify as pv  # noqa: E402


# ── fixture repo + DB ────────────────────────────────────────────────────────

def make_db(root: Path) -> Path:
    dbdir = root / ".codegraph"
    dbdir.mkdir(parents=True)
    db = dbdir / "codegraph.db"
    con = sqlite3.connect(db)
    con.executescript("""
        CREATE TABLE nodes (id TEXT PRIMARY KEY, kind TEXT, name TEXT,
            qualified_name TEXT, file_path TEXT, start_line INT, end_line INT);
        CREATE TABLE edges (id INTEGER PRIMARY KEY, source TEXT, target TEXT,
            kind TEXT, line INT);
        CREATE TABLE files (path TEXT PRIMARY KEY, content_hash TEXT);
        CREATE TABLE unresolved_refs (reference_name TEXT);
    """)
    nodes = [
        ("n1", "function", "validate_token", "auth.validate_token", "src/auth.py", 41, 60),
        ("n2", "function", "get_conn", "db.get_conn", "src/db.py", 12, 30),
        ("n3", "function", "legacy_check", "auth.legacy_check", "src/auth.py", 70, 90),
        ("s1", "class", "Settings", "config.Settings", "src/config.py", 10, 40),
        ("s2", "class", "Settings", "legacy.Settings", "src/legacy/config.py", 7, 30),
    ]
    # callers: 4 for validate_token, 12 for get_conn, 3 for legacy_check
    callers = []
    for i in range(4):
        callers.append((f"cv{i}", "function", f"route_{i}", f"api.route_{i}",
                        "src/api/routes.py", 10 + i, 12 + i))
    for i in range(12):
        callers.append((f"cg{i}", "function", f"worker_{i}", f"jobs.worker_{i}",
                        "src/jobs/worker.py", 100 + i, 102 + i))
    for i, loc in enumerate(["src/api/routes.py", "src/cli.py", "tests/test_auth.py"]):
        callers.append((f"cl{i}", "function", f"legacy_user_{i}",
                        f"x.legacy_user_{i}", loc, 200 + i, 202 + i))
    con.executemany("INSERT INTO nodes VALUES (?,?,?,?,?,?,?)", nodes + callers)

    edges = []
    for i in range(4):
        edges.append((f"cv{i}", "n1", "calls", 88))
    for i in range(12):
        edges.append((f"cg{i}", "n2", "calls", 55))
    for i in range(3):
        edges.append((f"cl{i}", "n3", "calls", 14))
    con.executemany("INSERT INTO edges (source,target,kind,line) VALUES (?,?,?,?)", edges)

    con.executemany("INSERT INTO files VALUES (?,?)", [
        ("src/auth.py", "h1"), ("src/db.py", "h2"), ("src/config.py", "h3"),
        ("src/legacy/config.py", "h4"), ("src/api/routes.py", "h5"),
        ("src/jobs/worker.py", "h6"), ("src/cli.py", "h7"),
        ("tests/test_auth.py", "h8"),
    ])
    con.execute("INSERT INTO unresolved_refs VALUES ('refresh_token')")
    con.commit()
    con.close()
    return db


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    make_db(tmp_path)
    return tmp_path


def write_plan(repo: Path, body: str, name: str = "docs/plans/p1-plan.md") -> Path:
    p = repo / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body)
    return p


MANIFEST_GOOD = """# Plan

<!-- plan-verify
touch: src/auth.py::validate_token
new:   src/auth.py::refresh_token
remove: src/auth.py::legacy_check
tier: A
gates: research:bullmq-remove-api
qualifiers: byte-unchanged src/db.py ; grep-absent "lib/db" src/api/*.py
-->

We change `validate_token` in src/auth.py. Callers in routes.py, cli.py and
test_auth.py are updated in the same change.
"""


# ── manifest parsing ─────────────────────────────────────────────────────────

class TestManifest:
    def test_entries_and_meta(self):
        m = pv.parse_manifest(MANIFEST_GOOD)
        assert [(c.intent, c.raw) for c in m.claims] == [
            ("touch", "src/auth.py::validate_token"),
            ("new", "src/auth.py::refresh_token"),
            ("remove", "src/auth.py::legacy_check"),
        ]
        assert m.tiers == ["A"] and m.gates == ["research:bullmq-remove-api"]
        assert len(m.qualifiers) == 2 and not m.meta_problems

    def test_bad_tier_and_raw_shell_qualifier_flagged(self):
        text = "<!-- plan-verify\ntier: Z\nqualifiers: rm -rf / ; byte-unchanged a.py\n-->"
        m = pv.parse_manifest(text)
        assert any("tier" in p for p in m.meta_problems)
        assert any("raw shell" in p for p in m.meta_problems)

    def test_multiple_blocks_concatenate(self):
        text = ("<!-- plan-verify\ntouch: src/db.py::get_conn\n-->\nprose\n"
                "<!-- plan-verify\ntouch: src/auth.py::validate_token\n-->")
        assert len(pv.parse_manifest(text).claims) == 2

    def test_path_symbol_forms(self):
        c = pv.parse_entry("touch", "src/auth.py::validate_token")
        assert (c.path, c.symbol) == ("src/auth.py", "validate_token")
        c = pv.parse_entry("touch", "src/auth.py")
        assert (c.path, c.symbol) == ("src/auth.py", None)
        c = pv.parse_entry("touch", "validate_token")
        assert (c.path, c.symbol) == (None, "validate_token")


# ── verdicts ────────────────────────────────────────────────────────────────

class TestVerdicts:
    def run(self, repo: Path, body: str) -> dict:
        plan = write_plan(repo, body)
        return pv.verify(plan, None)

    def test_touch_ok_with_evidence(self, repo):
        r = self.run(repo, "<!-- plan-verify\ntouch: src/auth.py::validate_token\n-->")
        c = r["manifest_claims"][0]
        assert c.verdict == pv.OK and "src/auth.py:41" in c.evidence

    def test_touch_missing(self, repo):
        r = self.run(repo, "<!-- plan-verify\ntouch: src/auth.py::ghost_func\n-->")
        assert r["manifest_claims"][0].verdict == pv.MISSING

    def test_touch_ambiguous(self, repo):
        r = self.run(repo, "<!-- plan-verify\ntouch: Settings\n-->")
        c = r["manifest_claims"][0]
        assert c.verdict == pv.AMBIG and "src/config.py:10" in c.evidence

    def test_new_ok_and_dynamic_note(self, repo):
        r = self.run(repo, "<!-- plan-verify\nnew: src/auth.py::refresh_token\n-->")
        c = r["manifest_claims"][0]
        assert c.verdict == pv.OK
        assert any("unresolved_refs" in n for n in c.notes)

    def test_new_collision(self, repo):
        r = self.run(repo, "<!-- plan-verify\nnew: src/auth.py::validate_token\n-->")
        assert r["manifest_claims"][0].verdict == pv.COLLISION

    def test_remove_blocked_lists_unmentioned_callers(self, repo):
        r = self.run(repo, "<!-- plan-verify\nremove: src/auth.py::legacy_check\n-->")
        c = r["manifest_claims"][0]
        assert c.verdict == pv.BLOCKED and "3 callers" in c.evidence

    def test_remove_ok_when_callers_acknowledged(self, repo):
        body = ("<!-- plan-verify\nremove: src/auth.py::legacy_check\n-->\n"
                "We delete legacy_check and update routes.py, cli.py, test_auth.py.")
        r = self.run(repo, body)
        assert r["manifest_claims"][0].verdict == pv.OK

    def test_unacknowledged_blast_at_threshold(self, repo):
        r = self.run(repo, "<!-- plan-verify\ntouch: src/db.py::get_conn\n-->")
        c = r["manifest_claims"][0]
        assert c.verdict == pv.BLAST and "12 callers" in c.evidence

    def test_blast_suppressed_when_mentioned(self, repo):
        body = ("<!-- plan-verify\ntouch: src/db.py::get_conn\n-->\n"
                "12 call sites in worker.py are updated wave by wave.")
        r = self.run(repo, body)
        assert r["manifest_claims"][0].verdict == pv.OK

    def test_swept_tokens_get_verdicts_but_never_strict_fail(self, repo):
        body = "Prose mentions `ghost_helper` and `validate_token` only."
        r = self.run(repo, body)
        sw = {c.raw: c.verdict for c in r["swept_claims"]}
        assert sw["ghost_helper"] == pv.MISSING
        assert r["strict_fail"] == []          # swept never gates

    # ── verdict_claim disk fallback (Step 2, bkt3) ─────────────────────────

    def test_touch_path_only_on_disk_ok(self, repo):
        (repo / "hooks.json").write_text("{}")
        r = self.run(repo, "<!-- plan-verify\ntouch: hooks.json\n-->")
        c = r["manifest_claims"][0]
        assert c.verdict == pv.OK
        assert c.evidence == pv.ON_DISK_EVIDENCE

    def test_touch_symbol_on_disk_still_missing(self, repo):
        (repo / "prisma").mkdir()
        (repo / "prisma" / "schema.prisma").write_text("")
        r = self.run(repo,
                     "<!-- plan-verify\ntouch: prisma/schema.prisma::Asset\n-->")
        c = r["manifest_claims"][0]
        assert c.verdict == pv.MISSING
        assert c.evidence == "no node or file matches 'Asset'"

    def test_new_path_only_on_disk_collision(self, repo):
        (repo / "hooks.json").write_text("{}")
        r = self.run(repo, "<!-- plan-verify\nnew: hooks.json\n-->")
        c = r["manifest_claims"][0]
        assert c.verdict == pv.COLLISION
        assert c.evidence == pv.ON_DISK_EVIDENCE

    def test_remove_path_only_on_disk_ok(self, repo):
        (repo / "hooks.json").write_text("{}")
        r = self.run(repo, "<!-- plan-verify\nremove: hooks.json\n-->")
        c = r["manifest_claims"][0]
        assert c.verdict == pv.OK
        assert c.evidence == pv.ON_DISK_EVIDENCE
        assert c.verdict != pv.BLOCKED

    def test_touch_directory_missing(self, repo):
        (repo / "subdir").mkdir()
        r = self.run(repo, "<!-- plan-verify\ntouch: subdir/\n-->")
        c = r["manifest_claims"][0]
        assert c.verdict == pv.MISSING
        assert c.evidence == "no node or file matches 'subdir/'"

    def test_touch_absent_path_missing(self, repo):
        r = self.run(repo, "<!-- plan-verify\ntouch: nope/ghost.json\n-->")
        c = r["manifest_claims"][0]
        assert c.verdict == pv.MISSING
        assert c.evidence == "no node or file matches 'nope/ghost.json'"

    def test_touch_absolute_missing(self, repo):
        r = self.run(repo, "<!-- plan-verify\ntouch: /etc/passwd\n-->")
        c = r["manifest_claims"][0]
        assert c.verdict == pv.MISSING
        assert c.evidence == "no node or file matches '/etc/passwd'"

    def test_touch_parent_escape_missing(self, repo):
        (repo.parent / "outside.json").write_text("{}")
        r = self.run(repo, "<!-- plan-verify\ntouch: ../outside.json\n-->")
        c = r["manifest_claims"][0]
        assert c.verdict == pv.MISSING
        assert c.evidence == "no node or file matches '../outside.json'"

    def test_swept_prisma_on_disk_ok_suppressed(self, repo):
        (repo / "probes").mkdir()
        (repo / "probes" / "schema.prisma").write_text("")
        r = self.run(repo, "Prose mentions `probes/schema.prisma` only.")
        assert r["swept_claims"][0].verdict == pv.OK
        assert r["swept_claims"][0].evidence == pv.ON_DISK_EVIDENCE
        assert "probes/schema.prisma" not in pv.render(r)
        assert r["strict_fail"] == []

    def test_touch_empty_symbol_suffix_missing(self, repo):
        (repo / "foo.py").write_text("")
        r = self.run(repo, "<!-- plan-verify\ntouch: foo.py::\n-->")
        c = r["manifest_claims"][0]
        assert c.verdict == pv.MISSING
        assert c.evidence == "no node or file matches 'foo.py'"

    def test_touch_indexed_file_keeps_caller_evidence(self, repo):
        (repo / "src").mkdir(parents=True)
        (repo / "src" / "db.py").write_text("")
        r = self.run(repo, "<!-- plan-verify\ntouch: src/db.py\n-->")
        c = r["manifest_claims"][0]
        assert "src/db.py" in c.evidence and "callers" in c.evidence
        assert c.evidence != pv.ON_DISK_EVIDENCE

    def test_touch_relative_external_on_disk_missing(self, repo):
        (repo / "src").mkdir(parents=True)
        (repo / "src" / "local.py").write_text("")
        r = self.run(repo, "<!-- plan-verify\ntouch: external: src/local.py\n-->")
        c = r["manifest_claims"][0]
        assert c.verdict == pv.MISSING
        assert any("absolute path" in p for p in r["meta_problems"])

    def test_symlink_loop_missing_no_raise(self, repo):
        (repo / "loop").mkdir()
        (repo / "loop" / "a").symlink_to("b")
        (repo / "loop" / "b").symlink_to("a")
        r = self.run(repo, "<!-- plan-verify\ntouch: loop/a\n-->")
        c = r["manifest_claims"][0]
        assert c.verdict == pv.MISSING
        assert c.evidence == "no node or file matches 'loop/a'"


# ── on-disk helpers (Step 1, bkt3) ──────────────────────────────────────────

class TestOnDiskHelpers:
    def test_on_disk_regular_file_true(self, repo):
        (repo / "hooks.json").write_text("{}")
        assert pv._on_disk(repo, "hooks.json") is True

    def test_on_disk_directory_false(self, repo):
        (repo / "subdir").mkdir()
        assert pv._on_disk(repo, "subdir/") is False

    def test_on_disk_absolute_false(self, repo):
        assert pv._on_disk(repo, "/etc/passwd") is False

    def test_on_disk_parent_escape_false(self, repo):
        outside = repo.parent / "outside.json"
        outside.write_text("{}")
        assert pv._on_disk(repo, "../outside.json") is False

    def test_on_disk_none_root_false(self, repo):
        assert pv._on_disk(None, "hooks.json") is False

    def test_on_disk_symlink_loop_false_no_raise(self, repo):
        (repo / "loop").mkdir()
        (repo / "loop" / "a").symlink_to("b")
        (repo / "loop" / "b").symlink_to("a")
        assert pv._on_disk(repo, "loop/a") is False

    def test_path_only_forms(self):
        assert pv._path_only(pv.parse_entry("touch", "hooks.json")) is True
        assert pv._path_only(pv.parse_entry("touch", "foo.py::")) is False
        assert pv._path_only(pv.parse_entry("touch", "external: src/local.py")) is False
        assert pv._path_only(
            pv.parse_entry("touch", "prisma/schema.prisma::Asset")) is False

    def test_makefile_not_path_only(self):
        assert pv.parse_entry("touch", "Makefile").path is None


# ── external claims (item 21.4, Step 8) ──────────────────────────────────────

class TestExternal:
    def run(self, repo: Path, body: str) -> dict:
        plan = write_plan(repo, body)
        return pv.verify(plan, None)

    def test_external_abs_verdicts_ok(self, repo):
        r = self.run(repo, "<!-- plan-verify\ntouch: external: /abs/x.py::sym\n-->")
        c = r["manifest_claims"][0]
        assert c.external is True
        assert c.verdict == pv.OK
        assert c.evidence == "declared outside the indexed repo (external:)"

    def test_external_quoted_spaced_verdicts_ok(self, repo):
        r = self.run(repo,
                     '<!-- plan-verify\ntouch: external: "/abs/path with spaces/f.py"\n-->')
        c = r["manifest_claims"][0]
        assert c.external is True
        assert c.path == "/abs/path with spaces/f.py"
        assert c.verdict == pv.OK

    def test_external_relative_no_short_circuit(self, repo):
        r = self.run(repo, "<!-- plan-verify\ntouch: external: src/local.py\n-->")
        c = r["manifest_claims"][0]
        assert c.external is False
        assert c.verdict == pv.MISSING
        assert any("absolute path" in p for p in r["meta_problems"])

    def test_json_surfaces_external_flag(self, repo):
        plan = write_plan(repo, "<!-- plan-verify\ntouch: external: /abs/x.py::sym\n-->")
        r = subprocess.run([sys.executable, str(CLI), str(plan), "--json"],
                           capture_output=True, text=True)
        doc = json.loads(r.stdout)
        assert doc["manifest"][0]["external"] is True


# ── CLI gate semantics ───────────────────────────────────────────────────────

class TestCli:
    def cli(self, plan: Path, *flags: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(CLI), str(plan), *flags],
                              capture_output=True, text=True)

    def test_advisory_always_exit0(self, repo):
        plan = write_plan(repo, "<!-- plan-verify\ntouch: src/auth.py::ghost\n-->")
        r = self.cli(plan)
        assert r.returncode == 0 and "MISSING" in r.stdout and "FAIL" in r.stdout

    def test_strict_fails_on_missing(self, repo):
        plan = write_plan(repo, "<!-- plan-verify\ntouch: src/auth.py::ghost\n-->")
        assert self.cli(plan, "--strict").returncode == 1

    def test_strict_passes_ambiguous_and_blast(self, repo):
        plan = write_plan(repo, "<!-- plan-verify\ntouch: Settings\n"
                                "touch: src/db.py::get_conn\n-->")
        r = self.cli(plan, "--strict")
        assert r.returncode == 0
        assert "AMBIGUOUS" in r.stdout and "UNACKNOWLEDGED-BLAST" in r.stdout

    def test_json_output(self, repo):
        plan = write_plan(repo, MANIFEST_GOOD)
        r = self.cli(plan, "--json")
        doc = json.loads(r.stdout)
        assert doc["tiers"] == ["A"] and len(doc["manifest"]) == 3

    def test_no_db_is_error_for_cli(self, tmp_path):
        plan = tmp_path / "plan.md"
        plan.write_text("x")
        r = subprocess.run([sys.executable, str(CLI), str(plan)],
                           capture_output=True, text=True)
        assert r.returncode == 2

    def test_strict_path_only_on_disk_exit0(self, repo):
        (repo / "hooks.json").write_text("{}")
        plan = write_plan(repo, "<!-- plan-verify\ntouch: hooks.json\n-->")
        r = self.cli(plan, "--strict")
        assert r.returncode == 0

    def test_cli_db_flag_stats_fixture_root_not_plan_dir(self, repo,
                                                         tmp_path_factory):
        plan = tmp_path_factory.mktemp("away") / "plan.md"
        plan.write_text("<!-- plan-verify\ntouch: hooks.json\n-->")
        (repo / "hooks.json").write_text("{}")
        r = subprocess.run([sys.executable, str(CLI), str(plan), "--db",
                            str(repo / ".codegraph" / "codegraph.db"),
                            "--json", "--strict"],
                           capture_output=True, text=True)
        assert r.returncode == 0
        doc = json.loads(r.stdout)
        assert doc["manifest"][0]["verdict"] == pv.OK
        assert doc["manifest"][0]["evidence"] == "on disk, not in index"


# ── spec-reuse cross-check (tier 3, 2026-07-19) ──────────────────────────────

SPEC_REUSE = """# Spec

## Already built (reuse, do not rebuild)

| Function/Module | Location | What it does | How this spec uses it | Depth |
|---|---|---|---|---|
| `AcpTransport` | `daemon/transport/acp.ts:406+` | transport | staging | deep |
| `validateAcpFrame` | `test/probes/lib/acp-schema.mjs` | schema check | probe frames | deep |
| `helperThing` | `src/util/helper.ts` | misc | trivial | shallow |

## Next section
"""


class TestSpecReuse:
    def test_rows_parse_deep_only(self):
        rows = pv.spec_reuse_rows(SPEC_REUSE)
        assert rows == [("AcpTransport", "daemon/transport/acp.ts"),
                        ("validateAcpFrame", "test/probes/lib/acp-schema.mjs")]

    def test_dropped_row_flagged(self):
        plan = "The probe reuses `validateAcpFrame` for every frame."
        dropped, notes = pv.check_spec_reuse(SPEC_REUSE, plan)
        assert notes == []
        assert [d["name"] for d in dropped] == ["AcpTransport"]
        assert dropped[0]["verdict"] == "REUSE-DROPPED"

    def test_basename_mention_satisfies(self):
        plan = "Stage the bundle into acp.ts stateDir; validate via acp-schema.mjs."
        dropped, _ = pv.check_spec_reuse(SPEC_REUSE, plan)
        assert dropped == []

    def test_reuse_paren_suffix_matches_ident(self):
        spec = ("# Spec\n\n## Already built (reuse, do not rebuild)\n\n"
                "| Function/Module | Location | What it does | How this spec uses it | Depth |\n"
                "|---|---|---|---|---|\n"
                "| `runFalQueue(...)` | `src/queue.ts` | staging | reuse | deep |\n\n"
                "## Next section\n")
        dropped, _ = pv.check_spec_reuse(spec, "Call runFalQueue for each batch.")
        assert dropped == []

    def test_reuse_ellipsis_forms_match_ident(self):
        spec = ("# Spec\n\n## Already built (reuse, do not rebuild)\n\n"
                "| Function/Module | Location | What it does | How this spec uses it | Depth |\n"
                "|---|---|---|---|---|\n"
                "| `claim_one(stage=…)` | `src/claims.ts` | staging | reuse | deep |\n"
                "| `emitFrame...` | `src/frames.ts` | staging | reuse | deep |\n\n"
                "## Next section\n")
        dropped, _ = pv.check_spec_reuse(spec, "Use claim_one before emitFrame on every stage.")
        assert dropped == []

    def test_missing_table_noted_not_failed(self):
        dropped, notes = pv.check_spec_reuse("# Spec\nno table here\n", "plan")
        assert dropped == [] and any("skipped" in n for n in notes)

    def test_cli_spec_warn_only_never_strict_fails(self, repo):
        plan = write_plan(repo, "<!-- plan-verify\ntouch: src/auth.py::validate_token\n-->\n"
                                "Callers in routes.py, cli.py, test_auth.py updated.")
        spec = repo / "docs/spec.md"
        spec.write_text(SPEC_REUSE)
        r = subprocess.run([sys.executable, str(CLI), str(plan),
                            "--spec", str(spec), "--strict"],
                           capture_output=True, text=True)
        assert "REUSE-DROPPED" in r.stdout
        assert r.returncode == 0          # warn-only: strict gate unaffected

    def test_cli_missing_spec_file_exit2(self, repo):
        plan = write_plan(repo, MANIFEST_GOOD)
        r = subprocess.run([sys.executable, str(CLI), str(plan),
                            "--spec", str(repo / "nope.md")],
                           capture_output=True, text=True)
        assert r.returncode == 2


# ── hook mode ────────────────────────────────────────────────────────────────

class TestHook:
    def hook(self, payload: dict) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(CLI), "--hook"],
                              input=json.dumps(payload),
                              capture_output=True, text=True)

    def test_problems_injected(self, repo):
        plan = write_plan(repo, "<!-- plan-verify\ntouch: src/auth.py::ghost\n-->")
        r = self.hook({"tool_name": "Write",
                       "tool_input": {"file_path": str(plan)}, "cwd": str(repo)})
        assert r.returncode == 0
        out = json.loads(r.stdout)
        assert "MISSING" in out["hookSpecificOutput"]["additionalContext"]

    def test_silent_when_all_ok(self, repo):
        plan = write_plan(
            repo, "<!-- plan-verify\ntouch: src/auth.py::validate_token\n-->")
        r = self.hook({"tool_name": "Write",
                       "tool_input": {"file_path": str(plan)}, "cwd": str(repo)})
        assert r.returncode == 0 and r.stdout.strip() == ""

    def test_silent_on_non_plan_file(self, repo):
        p = write_plan(repo, "anything `ghost_helper`", name="docs/notes.md")
        r = self.hook({"tool_name": "Write",
                       "tool_input": {"file_path": str(p)}, "cwd": str(repo)})
        assert r.stdout.strip() == ""

    def test_fail_open_on_garbage_stdin(self):
        r = subprocess.run([sys.executable, str(CLI), "--hook"],
                           input="not json", capture_output=True, text=True)
        assert r.returncode == 0 and r.stdout.strip() == ""

    def test_plan_path_globs(self):
        assert pv.is_plan_path("/x/docs/AI_artifacts/6_plans/p3.md")
        assert pv.is_plan_path("/x/docs/AI_artifacts/4_plans/p3.md")
        assert pv.is_plan_path("/x/docs/plans/anything.md")
        assert pv.is_plan_path("/x/my-plan.md")
        assert not pv.is_plan_path("/x/docs/notes.md")
