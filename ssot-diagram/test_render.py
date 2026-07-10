"""Tests for render — ssot-diagram P5 HTML renderer (Step 10 / Wave G).

Test categories (mirror test_graph_model.py sections):
1.  Three pinned-sha goldens (GOLDEN_NO_NARR, GOLDEN_WITH_NARR, GOLDEN_TRUSTMATRIX).
2.  Structural asserts (the safety load: 407 tree positions, exactly one </script>,
    zero '<' in the payload region, byte-deterministic render).
3.  Injection test (F3 invariant against the curated injection fixture).
4.  Exit-code tests (every L7 failure mode + --help).
5.  Template hygiene (no `innerHTML`, each sentinel once, no <link>/@import).
6.  Scoped view (--component cmp-lib + stub_nav differs full vs scoped).
7.  Regression guard (golden model sha 56df3d86... untouched after a full render run).

Helpers reused verbatim from test_graph_model.py (GOLDEN, TESTDATA, _synthetic_db,
_mini_model, _run_narrate) — do NOT invent. Re-implementation is prohibited.

Pinned golden shas were captured by rendering once to /tmp then sha256:
    python3 ssot-diagram/render.py render \\
        --model ssot-diagram/testdata/mkt_engine.model.json \\
        --config ssot-diagram/ssot-diagram.config.json \\
        --narratives /nonexistent/narratives.json \\
        --out /tmp/g1.html
    shasum -a 256 /tmp/g1.html

The shas are a determinism tripwire, not the only oracle. A failure here means
the renderer went non-deterministic (template drift, asset reordering, etc.); the
structural and exit-code tests below carry the safety load. Re-pin via:
    python3 ssot-diagram/render.py render --model ... --out /tmp/x.html \\
        && shasum -a 256 /tmp/x.html
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# Sibling import seam (mirror graph_model.py:26-28 + add `import render as r`).
sys.path.insert(0, str(Path(__file__).resolve().parent))
import graph_model as gm  # noqa: E402
import render as r        # noqa: E402
import decision_index as di  # noqa: E402

# ── Reused helpers from test_graph_model.py (do NOT re-define) ───────────────────

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
TESTDATA = HERE / "testdata"
GOLDEN = TESTDATA / "mkt_engine.model.json"
SHIPPED_CONFIG = HERE / "ssot-diagram.config.json"
TEMPLATE = HERE / "render_template.html"

# Real committed golden sha prefix — the regression guard. NEVER the stale 5a1e2156.
GOLDEN_MODEL_SHA_PREFIX = "56df3d86"

# ── Step 10 pinned golden shas (post-render hex) ────────────────────────────────

# GOLDEN #1 — real golden model, no narratives (note present, every node
# prose.source == "fallback").
GOLDEN_NO_NARR_SHA = "b64e2136b6362a0d79d432c0094e0961894f71ef6e910b55c8e6784540901e27"

# GOLDEN #2 — real golden + mkt_engine.narratives.fixture.json (every expected
# trust chip present; subtitle "10 components · 8 decisions"; no note).
GOLDEN_WITH_NARR_SHA = "1f6dadf1be98128d320a986d1300a7dcff60cfea1e6a372ab1cfe1f09a9816d1"

# GOLDEN #3 — trustmatrix.model.json + trustmatrix.narratives.json (per-row
# structural asserts covering BOTH matrix halves).
GOLDEN_TRUSTMATRIX_SHA = "2e2e2d98093e9b8574e8bed2529945797632dbaeb9586b39d87c5cb935192dc1"

# Tree-position count (A8/A15): 10 comps + 150 micros + 245 visible nanos +
# 2 collapsed placeholders = 407.
EXPECTED_TREE_POSITIONS = 407


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _run_render(args: list[str]) -> subprocess.CompletedProcess:
    """Run `render.py …` as a subprocess (mirrors test_graph_model._run_narrate).

    Hard timeout=60s so a hung render fails the test instead of hanging the
    suite forever (tests are L7 exit-code cases — all should return in <2s).
    """
    try:
        return subprocess.run(
            [sys.executable, str(HERE / "render.py"), *args],
            capture_output=True, text=True, timeout=60,
        )
    except subprocess.TimeoutExpired as e:
        pytest.fail(f"render {args} hung past 60s: {e}")


def _extract_model_payload(html: str) -> str:
    """Return the spliced MODEL object literal (between `const MODEL = {` and its
    matching `}`). Used to assert the F3 invariant 'zero < in the payload region'."""
    m = re.search(r"const MODEL = ", html)
    assert m, "template must contain `const MODEL = `"
    j = m.end()
    while j < len(html) and html[j].isspace():
        j += 1
    assert html[j] == "{", f"expected `{{` at pos {j}, got {html[j]!r}"
    depth, k = 0, j
    while k < len(html):
        c = html[k]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                k += 1
                break
        k += 1
    return html[j:k]


def _walk_tree(node: dict) -> list:
    """Walk a viewmodel component, emit one entry per tree position (incl. collapsed)."""
    out = [node]
    if node.get("kind") == "collapsed":
        return out
    for c in node.get("children", []) or []:
        out.extend(_walk_tree(c))
    return out


# ── 1. Three pinned-sha goldens ─────────────────────────────────────────────────

class TestGoldenShas:
    """Step 10 §1-§2 — render the three committed golden fixtures; assert the
    pinned sha256. Also assert the expected structural fingerprint for each."""

    def test_golden_no_narr_sha_pinned(self, tmp_path):
        out = tmp_path / "g1.html"
        r = _run_render(["render",
                         "--model", str(GOLDEN),
                         "--config", str(SHIPPED_CONFIG),
                         "--narratives", "/nonexistent/narratives.json",
                         "--out", str(out)])
        assert r.returncode == 0, r.stderr
        assert _sha256(out) == GOLDEN_NO_NARR_SHA, (
            f"GOLDEN_NO_NARR_SHA drift: {_sha256(out)}")
        # Every node prose.source == "fallback" (no narratives applied).
        html = out.read_text()
        payload = _extract_model_payload(html)
        assert payload.count('"source":"fallback"') >= 400, \
            "expected most nodes to have fallback prose.source (no narratives)"
        # Note present in the viewmodel (L7 note is set when narratives absent).
        assert "no narratives yet" in payload

    def test_golden_with_narr_sha_pinned(self, tmp_path):
        out = tmp_path / "g2.html"
        r = _run_render(["render",
                         "--model", str(GOLDEN),
                         "--config", str(SHIPPED_CONFIG),
                         "--narratives", str(TESTDATA / "mkt_engine.narratives.fixture.json"),
                         "--out", str(out)])
        assert r.returncode == 0, r.stderr
        assert _sha256(out) == GOLDEN_WITH_NARR_SHA, (
            f"GOLDEN_WITH_NARR_SHA drift: {_sha256(out)}")
        html = out.read_text()
        payload = _extract_model_payload(html)
        # Subtitle must be the committed "10 components · 8 decisions". The
        # middle-dot U+00B7 is escaped to \\u00b7 by ensure_ascii=True, so assert
        # the two fragments (encoding-invariant) rather than the raw char.
        assert "10 components" in payload and "8 decisions" in payload, \
            "subtitle must read '10 components · 8 decisions'"
        # Note absent (curated narratives supplied).
        assert "no narratives yet" not in payload, \
            "curated-narratives render must NOT carry the absent-narratives note"
        # Every expected trust chip present at least once (the curated fixture
        # exercises: PROPOSED, NEEDS REVIEW, UNNARRATABLE; plus FRESH decisions).
        # Assert the chip's distinctive text fragments WITHOUT the em-dash: the
        # payload is ensure_ascii=True-escaped (json.dumps), so a raw U+2014 in
        # chip text becomes the literal bytes — — assert on the text that
        # is invariant to that escaping.
        for chip in ("PROPOSED", "UNREVIEWED", "NEEDS REVIEW", "CODE CHANGED",
                     "UNNARRATABLE"):
            assert chip in payload, f"expected chip {chip!r} missing from payload"

    def test_golden_trustmatrix_sha_pinned(self, tmp_path):
        out = tmp_path / "g3.html"
        r = _run_render(["render",
                         "--model", str(TESTDATA / "trustmatrix.model.json"),
                         "--config", str(SHIPPED_CONFIG),
                         "--narratives", str(TESTDATA / "trustmatrix.narratives.json"),
                         "--out", str(out)])
        assert r.returncode == 0, r.stderr
        assert _sha256(out) == GOLDEN_TRUSTMATRIX_SHA, (
            f"GOLDEN_TRUSTMATRIX_SHA drift: {_sha256(out)}")
        # Per-row structural asserts — both matrix halves must surface.
        payload = _extract_model_payload(out.read_text())
        # Half 1: every decision status (FRESH/STALE/ORPHANED/AMBIGUOUS/superseded).
        for status in ("FRESH", "STALE", "ORPHANED", "AMBIGUOUS", "superseded"):
            assert f'"status":"{status}"' in payload, \
                f"decision status {status!r} missing from trustmatrix payload"
        # The literal "AMBIGUOUS — anchor unclear" chip must be present. Assert
        # on "anchor unclear" (survives the ensure_ascii=True em-dash escaping;
        # the raw U+2014 becomes literal bytes — in the payload).
        assert "anchor unclear" in payload, \
            "AMBIGUOUS chip text must appear (Decision chip addendum §2)"
        # Half 2: every prose narrative status (approved/proposed/stale/
        # unnarratable/none). 'stale' is a derived prose status; the curated
        # fixture seeds alphaTwo with a stale-by-design signature mismatch.
        for prose_status in ("approved", "proposed", "stale",
                             "unnarratable", "none"):
            assert f'"status":"{prose_status}"' in payload, \
                f"prose status {prose_status!r} missing from trustmatrix payload"
        # 'disabled' badge is the visual key for superseded (paint cue).
        assert '"badge":"disabled"' in payload, \
            "superseded decisions must paint with the 'disabled' badge"
        # Orphan entry (fake:nano-ghost@tm/ghost.ts) must NEVER enter the payload
        # (build_viewmodel drops orphans — only counted to stderr).
        assert "fake:nano-ghost" not in payload, \
            "orphan narrative entries must NOT enter the payload (A1 branch)"


# ── 2. Structural asserts (carry the safety load) ──────────────────────────────

class TestStructural:
    """Step 10 §3 — 407 tree positions, exactly one </script>, zero '<' in the
    MODEL literal, byte-deterministic render twice."""

    def test_golden_has_407_tree_positions(self):
        model = json.loads(GOLDEN.read_text())
        total = 0
        for comp in model.get("components", []):
            total += len(_walk_tree(comp))
        assert total == EXPECTED_TREE_POSITIONS, (
            f"golden has {total} tree positions, expected {EXPECTED_TREE_POSITIONS} "
            "(10 comps + 150 micros + 245 visible nanos + 2 collapsed placeholders)")

    def test_rendered_has_exactly_one_script_close_tag(self, tmp_path):
        out = tmp_path / "x.html"
        r = _run_render(["render",
                         "--model", str(GOLDEN),
                         "--config", str(SHIPPED_CONFIG),
                         "--narratives", "/nonexistent/narratives.json",
                         "--out", str(out)])
        assert r.returncode == 0, r.stderr
        html = out.read_text()
        assert html.count("</script>") == 1, \
            f"expected exactly one </script>, found {html.count('</script>')}"

    def test_payload_region_has_zero_lt_char(self, tmp_path):
        out = tmp_path / "x.html"
        r = _run_render(["render",
                         "--model", str(GOLDEN),
                         "--config", str(SHIPPED_CONFIG),
                         "--narratives", str(TESTDATA / "mkt_engine.narratives.fixture.json"),
                         "--out", str(out)])
        assert r.returncode == 0, r.stderr
        html = out.read_text()
        payload = _extract_model_payload(html)
        # F3 invariant — _escape_viewmodel_json replaces '<' with <.
        assert "<" not in payload, (
            "F3 violated: literal '<' inside the spliced MODEL literal — the "
            "escape replace('<', '\\u003c') is missing or broken")

    def test_render_twice_is_byte_identical(self, tmp_path):
        """Same render inputs twice ⇒ byte-identical (no timestamp / no random)."""
        a = tmp_path / "a.html"
        b = tmp_path / "b.html"
        for out in (a, b):
            r = _run_render(["render",
                             "--model", str(GOLDEN),
                             "--config", str(SHIPPED_CONFIG),
                             "--narratives", str(TESTDATA / "mkt_engine.narratives.fixture.json"),
                             "--out", str(out)])
            assert r.returncode == 0, r.stderr
        assert _sha256(a) == _sha256(b), (
            f"two renders diverged: {_sha256(a)} vs {_sha256(b)}")


# ── 3. Injection test (F3 invariant against the curated injection fixture) ─────

class TestInjection:
    """Step 10 §4 — injection.narratives.json carries every F3 escape hazard:
    literal </script><script>, <!--, U+2028, the sentinel token. After splice:
    exactly one </script>, zero '<' in payload, both sentinels appear in the
    raw template exactly once."""

    def test_injection_render_is_safe(self, tmp_path):
        out = tmp_path / "inj.html"
        r = _run_render(["render",
                         "--model", str(GOLDEN),
                         "--config", str(SHIPPED_CONFIG),
                         "--narratives", str(TESTDATA / "injection.narratives.json"),
                         "--out", str(out)])
        assert r.returncode == 0, r.stderr
        html = out.read_text()
        assert html.count("</script>") == 1, \
            f"injection render must have exactly one </script>, got {html.count('</script>')}"
        payload = _extract_model_payload(html)
        assert "<" not in payload, \
            "injection render leaked '<' into the MODEL literal (F3 broken)"
        # The escape text must round-trip — the hazard text survives as
        # escaped JSON (< / U+2028), so the literals </script>, <!--, and
        # the raw sentinel string never reappear in the spliced payload.
        assert "<script>" not in payload
        assert "</script>" not in payload
        assert "<!--" not in payload

    def test_each_sentinel_appears_once_in_raw_template(self):
        """SENTINEL_VM and SENTINEL_FONT each appear EXACTLY once in the raw
        template (pre-splice). This is the loader-boundary contract the splicer
        asserts on; if the count drifts, _render_html dies at the assert."""
        text = TEMPLATE.read_text()
        assert text.count(r.SENTINEL_VM) == 1, \
            f"SENTINEL_VM count {text.count(r.SENTINEL_VM)} (must be 1)"
        assert text.count(r.SENTINEL_FONT) == 1, \
            f"SENTINEL_FONT count {text.count(r.SENTINEL_FONT)} (must be 1)"


# ── 4. Exit-code tests (every L7 failure via subprocess) ──────────────────────

class TestExitCodes:
    """Step 10 §5 — every L7 failure mode lands exactly where P4 pinned it."""

    def test_no_verb_exits_2(self):
        r = _run_render([])
        assert r.returncode == 2, f"bare `render.py` must exit 2, got {r.returncode}"

    def test_help_exits_0(self):
        r = _run_render(["--help"])
        assert r.returncode == 0, f"--help must exit 0, got {r.returncode}"
        assert "render" in r.stdout

    def test_missing_model_exits_2(self):
        r = _run_render(["render",
                         "--model", "/nonexistent.json",
                         "--config", str(SHIPPED_CONFIG),
                         "--out", "/tmp/x.html"])
        assert r.returncode == 2, f"missing model must exit 2, got {r.returncode}"
        assert "extract" in r.stderr

    def test_missing_narratives_path_exits_0_with_note(self):
        """L7: absent narratives is a NOTE + exit 0; never a fail."""
        out = tempfile.NamedTemporaryFile(suffix=".html", delete=False).name
        try:
            r = _run_render(["render",
                             "--model", str(GOLDEN),
                             "--config", str(SHIPPED_CONFIG),
                             "--narratives", "/nonexistent/narratives.json",
                             "--out", out])
            assert r.returncode == 0, f"absent narratives must exit 0, got {r.returncode}"
            assert "no narratives yet" in r.stderr, \
                "absent narratives must surface the L7 note on stderr"
            payload = _extract_model_payload(Path(out).read_text())
            assert "no narratives yet" in payload, \
                "absent narratives must surface the L7 note inside the viewmodel"
        finally:
            os.unlink(out)

    def test_malformed_narratives_exits_2(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{ broken json")
        r = _run_render(["render",
                         "--model", str(GOLDEN),
                         "--config", str(SHIPPED_CONFIG),
                         "--narratives", str(bad),
                         "--out", str(tmp_path / "x.html")])
        assert r.returncode == 2, f"malformed narratives must exit 2, got {r.returncode}"

    def test_empty_narratives_no_note_exits_0(self, tmp_path):
        """Curated empty {} is NOT the absent case — no note, exit 0."""
        narr = tmp_path / "empty.json"
        narr.write_text('{"narratives": {}}')
        out = tmp_path / "x.html"
        r = _run_render(["render",
                         "--model", str(GOLDEN),
                         "--config", str(SHIPPED_CONFIG),
                         "--narratives", str(narr),
                         "--out", str(out)])
        assert r.returncode == 0, f"empty narratives must exit 0, got {r.returncode}"
        assert "no narratives yet" not in r.stderr, \
            "curated empty narratives must NOT carry the absent-narratives note"
        assert "no narratives yet" not in out.read_text(), \
            "curated empty narratives must NOT carry the absent-narratives note"

    def test_missing_template_exits_2(self):
        """Copy render.py + assets into a tmp dir (no template), run via
        PYTHONPATH so the sibling imports resolve. Expect exit 2 from the
        missing-template die."""
        tmp = Path(tempfile.mkdtemp())
        try:
            shutil.copy(HERE / "render.py", tmp / "render.py")
            shutil.copytree(HERE / "assets", tmp / "assets")
            env = {**os.environ, "PYTHONPATH": f"{HERE}:{tmp}"}
            r = subprocess.run(
                [sys.executable, str(tmp / "render.py"), "render",
                 "--model", str(GOLDEN),
                 "--config", str(SHIPPED_CONFIG),
                 "--narratives", str(TESTDATA / "injection.narratives.json"),
                 "--out", str(tmp / "x.html")],
                capture_output=True, text=True, env=env, timeout=60,
            )
            assert r.returncode == 2, f"missing template must exit 2, got {r.returncode}"
            assert "render_template.html not found" in r.stderr
        finally:
            shutil.rmtree(tmp)


# ── 5. Template hygiene (no `innerHTML`, sentinels, no <link>/@import) ────────

class TestTemplateHygiene:
    """Step 10 §6 — Step 8 used no `innerHTML`; sentinels each appear once in the
    raw template; no <link rel=stylesheet> or @import."""

    def test_no_innerHTML_in_template(self):
        """The literal word `innerHTML` is forbidden (paint uses textContent)."""
        text = TEMPLATE.read_text()
        assert "innerHTML" not in text, \
            f"`innerHTML` must not appear in the template (paint is textContent)"

    def test_no_link_or_at_import_in_template(self):
        """Zero-network rule: no external <link rel=stylesheet> and no @import."""
        text = TEMPLATE.read_text()
        # Allow <link> only as other attrs; reject rel=stylesheet explicitly.
        assert not re.search(r'<link[^>]*rel=["\']stylesheet["\']', text, re.IGNORECASE), \
            "template must not use <link rel=stylesheet> (zero-network rule)"
        assert "@import" not in text, \
            "template must not use @import (zero-network rule)"


# ── 6. Scoped view (--component cmp-lib + stub_nav) ────────────────────────────

class TestScopedView:
    """Step 10 §7 — --component cmp-lib produces scope=cmp-lib + inert stubs;
    full scope has navigable stubs (stub_nav=True)."""

    def test_scoped_viewmodel_has_scope_cmp_lib(self):
        """build_viewmodel(..., component='cmp-lib') returns scope='cmp-lib'."""
        model = json.loads(GOLDEN.read_text())
        narr = json.loads((TESTDATA / "injection.narratives.json").read_text())
        vm = r.build_viewmodel(model, narr["narratives"], component="cmp-lib")
        assert vm.get("scope") == "cmp-lib"
        # Components list shrinks to one entry (the focused component).
        assert len(vm.get("components", [])) == 1
        # Subtitle in the scoped shape: "<N> files · <M> decisions".
        sub = vm.get("subtitle", "")
        assert "files" in sub and "decisions" in sub, \
            f"scoped subtitle must read 'N files · M decisions', got: {sub!r}"

    def test_full_viewmodel_has_scope_full(self):
        model = json.loads(GOLDEN.read_text())
        narr = json.loads((TESTDATA / "injection.narratives.json").read_text())
        vm = r.build_viewmodel(model, narr["narratives"])
        assert vm.get("scope") == "full"
        assert "10 components" in vm.get("subtitle", "")

    def test_stub_nav_differs_full_vs_scoped(self, tmp_path):
        """Build a synthetic model with cross-component edges so stubs exist in
        BOTH the full and scoped views; assert stub_nav flips True/False."""
        comp_a = {
            "id": "cmp-a", "kind": "component", "name": "A", "path": "a",
            "signature": "sa",
            "children": [{
                "id": "micro:a/a.ts", "kind": "micro", "name": "a/a.ts",
                "path": "a/a.ts", "signature": "ma",
                "edges": [{"target_id": "nano:bx@b/b.ts", "kind": "calls", "count": 1}],
                "decisions": [], "children": [],
            }],
        }
        comp_b = {
            "id": "cmp-b", "kind": "component", "name": "B", "path": "b",
            "signature": "sb",
            "children": [{
                "id": "micro:b/b.ts", "kind": "micro", "name": "b/b.ts",
                "path": "b/b.ts", "signature": "mb",
                "edges": [], "decisions": [], "children": [
                    {"id": "nano:bx@b/b.ts", "kind": "function", "name": "bx",
                     "qualified_name": "bx", "path": "b/b.ts", "signature": "nx",
                     "caller_count": 1, "is_exported": True, "docstring": "",
                     "edges": [], "decisions": []},
                ],
            }],
        }
        model = {"version": 1, "nano_cap": 8, "generated_at": None,
                 "decisions": [], "components": [comp_a, comp_b]}
        vm_full = r.build_viewmodel(model, {})
        vm_scoped = r.build_viewmodel(model, {}, component="cmp-a")

        full_stubs = vm_full["components"][0].get("stubs", []) or vm_full["components"][1].get("stubs", [])
        scoped_stubs = vm_scoped["components"][0].get("stubs", [])
        assert full_stubs, "synthetic model must produce at least one stub in full view"
        assert scoped_stubs, "synthetic model must produce at least one stub in scoped view"
        assert all(s["stub_nav"] is True for s in full_stubs), \
            f"full view stubs must all be stub_nav=True; got {full_stubs}"
        assert all(s["stub_nav"] is False for s in scoped_stubs), \
            f"scoped view stubs must all be stub_nav=False; got {scoped_stubs}"

    def test_unknown_component_exits_2(self):
        """An unknown --component cid dies 2 (addendum §4)."""
        r = _run_render(["render",
                         "--model", str(GOLDEN),
                         "--config", str(SHIPPED_CONFIG),
                         "--narratives", str(TESTDATA / "injection.narratives.json"),
                         "--out", "/tmp/x.html",
                         "--component", "cmp-does-not-exist"])
        assert r.returncode == 2, f"unknown --component must exit 2, got {r.returncode}"


# ── 7. Regression guard (golden sha untouched + zero new fails) ────────────────

class TestRegression:
    """Step 10 §8 — A19 regression guard: golden model sha 56df3d86... untouched
    after a full render run (re-hash the model file post-render)."""

    def test_golden_model_sha_unchanged_after_render(self, tmp_path):
        sha_before = _sha256(GOLDEN)
        assert sha_before.startswith(GOLDEN_MODEL_SHA_PREFIX), (
            f"golden model sha {sha_before} does not start with "
            f"{GOLDEN_MODEL_SHA_PREFIX} — NEVER the stale 5a1e2156")
        # Run a render that doesn't touch the golden file.
        r = _run_render(["render",
                         "--model", str(GOLDEN),
                         "--config", str(SHIPPED_CONFIG),
                         "--narratives", str(TESTDATA / "injection.narratives.json"),
                         "--out", str(tmp_path / "x.html")])
        assert r.returncode == 0, r.stderr
        sha_after = _sha256(GOLDEN)
        assert sha_after == sha_before, \
            f"golden model sha mutated by render: {sha_before} → {sha_after}"

    def test_full_suite_baseline_no_new_fails(self):
        """Run the full ssot-diagram/ suite; the 3 pre-existing TestGoldenLive
        fails must be the ONLY fails (new tests ADD to the 105 pass; the
        3 pre-existing TestGoldenLive stays).

        The nested run DESELECTS this test itself (pytest -k) so a single
        `pytest ssot-diagram/` does not recurse into running the suite N times.
        Hard timeout=120s + on the subprocess — a hung nested run fails the test
        instead of hanging the outer suite.
        """
        try:
            r = subprocess.run(
                [sys.executable, "-m", "pytest", str(HERE), "-q",
                 "--no-header", "--tb=no",
                 "-k", "not test_full_suite_baseline_no_new_fails"],
                capture_output=True, text=True, cwd=str(PROJECT_ROOT),
                timeout=180,
            )
        except subprocess.TimeoutExpired as e:
            pytest.fail(f"nested full-suite run hung past 180s: {e}")
        # Parse "X failed, Y passed in Z" from the tail.
        m = re.search(r"(\d+) failed,\s+(\d+) passed", r.stdout)
        assert m, f"unexpected pytest output: {r.stdout[-500:]}"
        failed, passed = int(m.group(1)), int(m.group(2))
        # 3 pre-existing TestGoldenLive failures; 105 pre-existing passes;
        # the new tests in this file must land in the passed bucket.
        assert failed == 3, (
            f"baseline drift: expected exactly 3 pre-existing TestGoldenLive fails, "
            f"got {failed}. New tests must NOT introduce new failures.")
        assert passed > 105, (
            f"new tests did not land: only {passed} passes (expected > 105).")