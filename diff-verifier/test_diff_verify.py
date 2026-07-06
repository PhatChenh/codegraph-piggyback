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
