"""Tests for diff_verify.py. Run: python3 -m pytest diff-verifier/ -q"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
CLI = HERE / "diff_verify.py"
sys.path.insert(0, str(HERE))
import diff_verify as dv  # noqa: E402


PLAN = """# Step 3 plan

<!-- plan-verify
touch: src/db.py::get_conn, tests/test_db.py
new:   src/db.py::get_pool
remove: src/db.py::legacy_conn
tier: B
qualifiers: byte-unchanged src/auth.py ; diff-only-within src/ tests/
-->
"""


def make_db(root: Path, *, delivered: bool, removed: bool) -> None:
    dbdir = root / ".codegraph"
    dbdir.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(dbdir / "codegraph.db")
    con.executescript("""
        CREATE TABLE nodes (id TEXT PRIMARY KEY, kind TEXT, name TEXT,
            qualified_name TEXT, file_path TEXT, start_line INT, end_line INT);
        CREATE TABLE edges (id INTEGER PRIMARY KEY, source TEXT, target TEXT,
            kind TEXT, line INT);
        CREATE TABLE files (path TEXT PRIMARY KEY, content_hash TEXT);
    """)
    rows = [("n1", "function", "get_conn", "db.get_conn", "src/db.py", 10, 20)]
    if delivered:
        rows.append(("n2", "function", "get_pool", "db.get_pool", "src/db.py", 30, 40))
    if not removed:
        rows.append(("n3", "function", "legacy_conn", "db.legacy_conn", "src/db.py", 50, 60))
    con.executemany("INSERT INTO nodes VALUES (?,?,?,?,?,?,?)", rows)
    con.execute("INSERT INTO files VALUES ('src/db.py','h1')")
    con.commit()
    con.close()


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src/db.py").write_text("def get_conn(): pass\n")
    (tmp_path / "src/auth.py").write_text("def ok(): pass\n")
    plan = tmp_path / "plan.md"
    plan.write_text(PLAN)
    return tmp_path


GOOD_DIFF = ["src/db.py", "tests/test_db.py"]


def run(repo: Path, files: list[str], *flags: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CLI), str(repo / "plan.md"), "--files", *files,
         "--repo-root", str(repo), *flags],
        capture_output=True, text=True)


class TestScope:
    def test_clean_diff_passes(self, repo):
        make_db(repo, delivered=True, removed=True)
        r = run(repo, GOOD_DIFF, "--strict")
        assert r.returncode == 0, r.stdout + r.stderr
        assert "PASS" in r.stdout

    def test_out_of_scope_touch(self, repo):
        make_db(repo, delivered=True, removed=True)
        r = run(repo, [*GOOD_DIFF, "src/sneaky.py"], "--strict")
        assert r.returncode == 1
        assert "OUT-OF-SCOPE-TOUCH" in r.stdout and "src/sneaky.py" in r.stdout

    def test_allow_glob_admits_run_docs(self, repo):
        make_db(repo, delivered=True, removed=True)
        r = run(repo, [*GOOD_DIFF, "docs/AI_artifacts/9_runs/report.md"],
                "--strict", "--allow", "docs/AI_artifacts/*")
        assert r.returncode == 0


class TestQualifiers:
    def test_byte_unchanged_fails_when_touched(self, repo):
        make_db(repo, delivered=True, removed=True)
        r = run(repo, [*GOOD_DIFF, "src/auth.py"], "--strict")
        assert "QUALIFIER-FAIL" in r.stdout and "src/auth.py" in r.stdout

    def test_diff_only_within_fails_outside(self, repo):
        make_db(repo, delivered=True, removed=True)
        r = run(repo, [*GOOD_DIFF, "infra/deploy.sh"], "--strict")
        assert "diff-only-within" in r.stdout or "OUT-OF-SCOPE" in r.stdout
        assert r.returncode == 1

    def test_grep_absent(self, tmp_path):
        (tmp_path / "src").mkdir()
        (tmp_path / "src/sink.py").write_text("import lib.db\n")
        fail = dv.run_qualifier('grep-absent "lib.db" src/*.py', tmp_path, [])
        assert fail and "sink.py" in fail
        ok = dv.run_qualifier('grep-absent "nonexistent" src/*.py', tmp_path, [])
        assert ok is None

    def test_unknown_verb_fails_closed(self, tmp_path):
        assert "unknown verb" in dv.run_qualifier("rm -rf /", tmp_path, [])


class TestDbChecks:
    def test_not_delivered(self, repo):
        make_db(repo, delivered=False, removed=True)
        r = run(repo, GOOD_DIFF, "--strict")
        assert r.returncode == 1 and "NOT-DELIVERED" in r.stdout

    def test_not_removed(self, repo):
        make_db(repo, delivered=True, removed=False)
        r = run(repo, GOOD_DIFF, "--strict")
        assert r.returncode == 1 and "NOT-REMOVED" in r.stdout

    def test_skip_db_reports_skip(self, repo):
        r = run(repo, GOOD_DIFF, "--strict", "--skip-db")
        assert "SKIPPED" in r.stdout and r.returncode == 0


class TestTests:
    def test_tests_missing(self, repo):
        make_db(repo, delivered=True, removed=True)
        r = run(repo, ["src/db.py"], "--strict")
        assert r.returncode == 1 and "TESTS-MISSING" in r.stdout

    def test_na_when_no_tests_declared(self, tmp_path):
        (tmp_path / "plan.md").write_text(
            "<!-- plan-verify\ntouch: src/db.py::get_conn\n-->")
        make_db(tmp_path, delivered=True, removed=True)
        r = subprocess.run(
            [sys.executable, str(CLI), str(tmp_path / "plan.md"),
             "--files", "src/db.py", "--repo-root", str(tmp_path), "--strict"],
            capture_output=True, text=True)
        assert "n/a" in r.stdout


class TestGitMode:
    def test_git_diff_range(self, repo):
        make_db(repo, delivered=True, removed=True)
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                        "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                        "commit", "-qm", "base"], cwd=repo, check=True)
        (repo / "src/db.py").write_text("def get_conn(): pass\ndef get_pool(): pass\n")
        (repo / "tests").mkdir()
        (repo / "tests/test_db.py").write_text("def test_x(): pass\n")
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                        "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                        "commit", "-qm", "impl"], cwd=repo, check=True)
        r = subprocess.run(
            [sys.executable, str(CLI), str(repo / "plan.md"),
             "--diff", "HEAD~1..HEAD", "--repo-root", str(repo), "--strict"],
            capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        assert "PASS" in r.stdout

    def test_json_output(self, repo):
        make_db(repo, delivered=True, removed=True)
        r = run(repo, GOOD_DIFF, "--json")
        doc = json.loads(r.stdout)
        assert doc["findings"] == [] and doc["tiers"] == ["B"]


# ── per-step listing mode (P8 ADR-0011 seam) ────────────────────────────────

PER_STEP_PLAN = """# P8 plan

### Step 1 — first

<!-- plan-verify
touch: src/foo.py, src/bar.py
tier: A
gates: human:merge-signoff
-->

### Step 2 — second

<!-- plan-verify
touch: src/baz.py
-->

### Step 3 — third

<!-- plan-verify
touch: src/qux.py
tier: Z
-->
"""


def run_per_step(plan_path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CLI), str(plan_path), "--per-step"],
        capture_output=True, text=True)


class TestPerStep:
    def test_help_advertises_per_step(self):
        """done-signal #1: --help must print --per-step (P8 ADR-0011)."""
        r = subprocess.run([sys.executable, str(CLI), "--help"],
                           capture_output=True, text=True)
        assert "--per-step" in r.stdout, r.stdout

    def test_emits_one_record_per_block(self, tmp_path):
        plan = tmp_path / "plan.md"
        plan.write_text(PER_STEP_PLAN)
        r = run_per_step(plan)
        assert r.returncode == 0, r.stdout + r.stderr
        records = json.loads(r.stdout)
        assert isinstance(records, list)
        assert len(records) == 3, records

    def test_record_carries_step_id_from_heading(self, tmp_path):
        plan = tmp_path / "plan.md"
        plan.write_text(PER_STEP_PLAN)
        records = json.loads(run_per_step(plan).stdout)
        # Step IDs are the heading text (stripped of leading hashes).
        assert records[0]["stepId"] == "Step 1 — first"
        assert records[1]["stepId"] == "Step 2 — second"
        assert records[2]["stepId"] == "Step 3 — third"
        assert all(rec["stepIdSource"] == "heading" for rec in records)

    def test_record_carries_files(self, tmp_path):
        plan = tmp_path / "plan.md"
        plan.write_text(PER_STEP_PLAN)
        records = json.loads(run_per_step(plan).stdout)
        assert records[0]["files"] == ["src/foo.py", "src/bar.py"]
        assert records[1]["files"] == ["src/baz.py"]
        assert records[2]["files"] == ["src/qux.py"]

    def test_tier_present_vs_absent_marker(self, tmp_path):
        plan = tmp_path / "plan.md"
        plan.write_text(PER_STEP_PLAN)
        records = json.loads(run_per_step(plan).stdout)
        # Step 1: tier A, present.
        assert records[0]["tier"] == "A"
        assert records[0]["tierAbsent"] is False
        # Step 2: tier missing → explicit marker for the consumer.
        assert records[1]["tier"] is None
        assert records[1]["tierAbsent"] is True
        # Step 3: tier Z (out of vocabulary) → value preserved + problem reported.
        assert records[2]["tier"] == "Z"
        assert records[2]["tierAbsent"] is False
        assert any("tier: 'Z'" in p for p in records[2]["tierProblems"])

    def test_record_carries_gates(self, tmp_path):
        plan = tmp_path / "plan.md"
        plan.write_text(PER_STEP_PLAN)
        records = json.loads(run_per_step(plan).stdout)
        assert records[0]["gates"] == ["human:merge-signoff"]
        assert records[1]["gates"] == []
        assert records[2]["gates"] == []


# ── BUG-024: --step scopes the diff verdict to ONE wave's block ──────────────

# A 2-step plan: Step 1's symbol is delivered; Step 2's is NOT (later wave, not
# built yet). The whole-plan verdict fails on Step 2's NOT-DELIVERED; a --step
# "Step 1" verdict must PASS (that is the toll-gate BUG-024 restores).
TWO_WAVE_PLAN = """# multi-wave plan

### Step 1 — build the pool

<!-- plan-verify
touch: src/db.py::get_conn, tests/test_db.py
new:   src/db.py::get_pool
tier: B
-->

### Step 2 — build the cache (NOT YET IMPLEMENTED)

<!-- plan-verify
new:   src/cache.py::get_cache
tests/test_cache.py
tier: B
-->
"""


class TestStepScope:
    """BUG-024 regression: --step must scope the whole verdict to one block."""

    def _repo(self, tmp_path: Path) -> Path:
        (tmp_path / "src").mkdir()
        (tmp_path / "src/db.py").write_text("def get_conn(): pass\n")
        (tmp_path / "plan.md").write_text(TWO_WAVE_PLAN)
        # DB has Step 1's symbols delivered; Step 2's get_cache is ABSENT.
        make_db(tmp_path, delivered=True, removed=True)
        return tmp_path

    def test_whole_plan_fails_midwave(self, tmp_path):
        """Without --step, wave-1's diff is verdicted against the WHOLE plan →
        NOT-DELIVERED for Step 2's not-yet-built get_cache. This is the bug."""
        repo = self._repo(tmp_path)
        r = run(repo, GOOD_DIFF, "--strict")
        assert r.returncode == 1, r.stdout + r.stderr
        assert "NOT-DELIVERED" in r.stdout
        assert "get_cache" in r.stdout

    def test_step_scopes_verdict_and_passes(self, tmp_path):
        """WITH --step 'Step 1 — build the pool', only Step 1's claims are
        verdicted → PASS even though Step 2's symbols don't exist yet."""
        repo = self._repo(tmp_path)
        r = run(repo, GOOD_DIFF, "--strict", "--step", "Step 1 — build the pool")
        assert r.returncode == 0, r.stdout + r.stderr
        assert "PASS" in r.stdout
        # get_cache belongs to Step 2 — it must NOT be verdicted here.
        assert "get_cache" not in r.stdout

    def test_step_scopes_out_of_scope_touch(self, tmp_path):
        """A file declared only in Step 2 is OUT-OF-SCOPE for a Step-1 verdict."""
        repo = self._repo(tmp_path)
        r = run(repo, [*GOOD_DIFF, "src/cache.py"], "--strict",
                "--step", "Step 1 — build the pool")
        assert r.returncode == 1
        assert "OUT-OF-SCOPE-TOUCH" in r.stdout and "src/cache.py" in r.stdout

    def test_unknown_step_errors_loudly(self, tmp_path):
        """A mis-typed step id must fail (exit 2), NOT silently verdict an empty
        manifest (which would pass any diff)."""
        repo = self._repo(tmp_path)
        r = run(repo, GOOD_DIFF, "--strict", "--step", "Step 99 — nope")
        assert r.returncode == 2, r.stdout + r.stderr
        assert "matched no plan-verify block" in r.stderr

    def test_step_note_records_scoping(self, tmp_path):
        repo = self._repo(tmp_path)
        r = run(repo, GOOD_DIFF, "--json", "--step", "Step 1 — build the pool")
        doc = json.loads(r.stdout)
        assert any("scoped to step" in n for n in doc["notes"])

    def test_synthetic_step_id_when_no_heading(self, tmp_path):
        plan = tmp_path / "plan.md"
        plan.write_text(
            "<!-- plan-verify\ntouch: src/a.py\ntier: C\n-->\n"
            "<!-- plan-verify\ntouch: src/b.py\ntier: B\n-->\n"
        )
        records = json.loads(run_per_step(plan).stdout)
        assert records[0]["stepId"] == "block-1"
        assert records[0]["stepIdSource"] == "synthetic"
        assert records[1]["stepId"] == "block-2"

    def test_no_diff_required(self, tmp_path):
        """--per-step must work WITHOUT --diff or --files."""
        plan = tmp_path / "plan.md"
        plan.write_text("<!-- plan-verify\ntouch: src/x.py\ntier: B\n-->")
        r = run_per_step(plan)
        assert r.returncode == 0, r.stdout + r.stderr
        records = json.loads(r.stdout)
        assert len(records) == 1

    def test_diff_required_when_per_step_absent(self, tmp_path):
        """Regression: diff mode still requires --diff|--files when no --per-step."""
        plan = tmp_path / "plan.md"
        plan.write_text("<!-- plan-verify\ntouch: src/x.py\ntier: B\n-->")
        r = subprocess.run(
            [sys.executable, str(CLI), str(plan), "--strict"],
            capture_output=True, text=True)
        assert r.returncode == 2, r.stdout + r.stderr
        assert "--per-step" in r.stderr or "--diff" in r.stderr
