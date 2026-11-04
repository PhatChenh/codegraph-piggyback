"""Tests for _shared/manifest.py — the `<!-- plan-verify -->` parser.

Real-substrate tests (TEST-SUBSTRATE-001): exercise the live parser with no
mocks and no fixtures that re-implement the grammar. Added in Bucket B
Step 2 (2026-07-27) to cover the parser's new `unknown_keys` channel
(Step 1) and the two silent traps called out in the plan: the §0.1
extensionless-path trap (`touch: av` is a *symbol*, not a file path) and
the §0.7 three-way partition that the consumer must be able to read.

Run: python3 -m pytest _shared/test_manifest.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import manifest as mf  # noqa: E402


# A heading is needed for `iter_blocks`'s `step_id` resolution; bare
# blocks fall back to "block-N" which is also fine — both are tested
# where it matters.


def block(text: str, heading: str = "# Step") -> str:
    """Wrap `text` in a `<!-- plan-verify -->` block under `heading`."""
    return f"{heading}\n\n<!-- plan-verify\n{text}\n-->\n"


class TestUnknownKeyChannel:
    """Cases 1, 4, 5, 6 from the plan — the new `unknown_keys` channel
    and its boundaries."""

    def test_files_key_inside_block_is_unknown(self):
        """Case 1: `files:` inside a block → unknown_keys == ['files'],
        parse_manifest.meta_problems names the key, files == [] (no
        path claims under the wrong key)."""
        text = block("files: src/auth.py")
        [rec] = mf.iter_blocks(text)
        assert rec.unknown_keys == ["files"]
        assert rec.files == []              # no path claims from that key
        # parse_manifest must surface the same fact in meta_problems:
        m = mf.parse_manifest(text)
        assert any("unknown manifest key: 'files'" in p for p in m.meta_problems)

    def test_correct_touch_no_unknown_keys(self):
        """Case 4: a correct `touch: daemon/index.ts` produces no
        unknown-key noise and yields the path as expected."""
        text = block("touch: daemon/index.ts")
        [rec] = mf.iter_blocks(text)
        assert rec.unknown_keys == []
        assert rec.files == ["daemon/index.ts"]
        assert mf.parse_manifest(text).meta_problems == []

    def test_unknown_key_does_not_suppress_valid_touch(self):
        """Case 5: an unknown key in the same block must NOT mask a
        valid `touch:` entry — the path still surfaces in `files`."""
        text = block("files: src/other.py\ntouch: src/auth.py")
        [rec] = mf.iter_blocks(text)
        assert rec.unknown_keys == ["files"]
        assert rec.files == ["src/auth.py"]   # valid claim preserved

    def test_prose_and_blank_lines_produce_no_unknown_key_noise(self):
        """Case 6: prose lines and blanks inside a block must not be
        classified as unknown keys. Regression guard on `_ANY_KEY_RE`
        over-matching — a line like `Note: something` (a typical prose
        sentence) is NOT a manifest key. If this test fails, narrow
        `_ANY_KEY_RE` (a Step-1 fix-round), do not weaken this test."""
        text = block(
            "touch: src/auth.py\n"
            "\n"
            "Note: this is prose\n"
            "We just need to update: the auth module\n"
            "TODO: follow up later\n"
            "Some words here without any colon at all\n"
            "  indented prose: with leading whitespace\n"
        )
        [rec] = mf.iter_blocks(text)
        assert rec.unknown_keys == [], (
            f"_ANY_KEY_RE over-matched on prose; got {rec.unknown_keys!r} "
            "— narrow the regex (do not weaken this test)"
        )
        # The valid touch in the same block must still be intact.
        assert rec.files == ["src/auth.py"]


class TestEntryClassification:
    """Cases 2, 3 — the §0.1 extensionless-path trap and its inverse
    `path::symbol` form. The parser's `looks_pathish` heuristic
    determines which is which."""

    def test_touch_bare_av_is_symbol_not_path(self):
        """Case 2: `touch: av` is a BARE SYMBOL — `av` is not pathish
        (no extension, no slash) so it does NOT reach `files`. This is
        the §0.1 trap that produced the B1 defect when written as
        `files: av::doctor` instead of `touch: av::doctor`."""
        text = block("touch: av")
        [rec] = mf.iter_blocks(text)
        assert rec.files == []
        m = mf.parse_manifest(text)
        assert len(m.claims) == 1
        assert m.claims[0].path is None
        assert m.claims[0].symbol == "av"

    def test_touch_path_symbol_form_yields_path(self):
        """Case 3: `touch: av::doctor` IS path-bearing — the `path::symbol`
        form makes the path part explicit, so `files` captures `av`."""
        text = block("touch: av::doctor")
        [rec] = mf.iter_blocks(text)
        assert rec.files == ["av"]
        m = mf.parse_manifest(text)
        assert len(m.claims) == 1
        assert m.claims[0].path == "av"
        assert m.claims[0].symbol == "doctor"


class TestBlockLineSpans:
    """Writ item 21.3 Step 1 (2026-08-09) — the new `block_line_spans`
    export: one 1-indexed `(start_line, end_line)` span per
    `<!-- plan-verify -->` block, in document order. Gives consumers
    (falkor-writ C5 rescope, C10 BODYSYNC) a way to address block lines
    without re-deriving a block-detection grammar."""

    def test_two_blocks_return_two_spans_covering_comment_lines(self):
        """Case (a): a doc with two blocks returns two spans covering
        exactly the comment lines — from the `<!-- plan-verify` opening
        line through the `-->` closing line, inclusive."""
        text = block("tier: A", "# Step 1") + "\n" + block("tier: B", "# Step 2")
        assert mf.block_line_spans(text) == [(3, 5), (9, 11)]

    def test_no_blocks_returns_empty(self):
        """Case (b): a doc with no plan-verify blocks returns []."""
        text = "# Step 1\n\ntouch: src/auth.py\n\n# Step 2\n"
        assert mf.block_line_spans(text) == []

    def test_spans_agree_with_iter_blocks_order(self):
        """Case (c): spans correspond 1:1 with `iter_blocks` records in
        document order — same block count, same first-line ordering, and
        each span covers exactly its block's comment lines."""
        text = (block("tier: A", "# Step 1") + "\n"
                + block("tier: B", "# Step 2") + "\n"
                + block("tier: C", "# Step 3"))
        spans = mf.block_line_spans(text)
        recs = mf.iter_blocks(text)
        assert len(spans) == len(recs) == 3
        for (start, end), rec in zip(spans, recs):
            assert start < end
            # the span covers exactly this block's comment lines
            lines = text.splitlines()[start - 1 : end]
            assert lines[0].strip() == "<!-- plan-verify"
            assert lines[-1].strip() == "-->"
            assert rec.block_index > 0
        # document order: spans start in strictly ascending line order
        assert [s[0] for s in spans] == sorted(s[0] for s in spans)


class TestExternalEntries:
    """Writ item 21.4 Step 7 (2026-08-09) — the `external:` value form.

    `external: <abs-path>` declares a touch outside the indexed repo: the
    parser flags it `external=True` and `iter_blocks` keeps its abs path out
    of `BlockRecord.files` (diff_verify scoping stays repo-local). A
    RELATIVE remainder (`external: src/local.py`) is not abs-shaped — it
    parses unflagged and each caller records a meta_problem. Owner lock 12b:
    quote-wrapped abs paths (`external: "/abs/path with spaces/f.py"`) are
    accepted so an author can carry spaces; unquoted spaced paths still
    truncate at the first space.
    """

    def test_abs_path_no_symbol(self):
        """Case (i): `external: /abs/x.py` → path, symbol None, external."""
        c = mf.parse_entry("touch", "external: /abs/x.py")
        assert c.path == "/abs/x.py"
        assert c.symbol is None
        assert c.external is True

    def test_abs_path_with_symbol(self):
        """Case (ii): `external: /abs/x.py::sym` → path + symbol, external.
        The external branch must run BEFORE the `::` split (FCV probe 6) or
        this parses to bogus path='external: /abs/x.py'."""
        c = mf.parse_entry("touch", "external: /abs/x.py::sym")
        assert c.path == "/abs/x.py"
        assert c.symbol == "sym"
        assert c.external is True

    def test_relative_falls_through_with_meta_problem(self):
        """Case (iii): `external: src/local.py` is NOT external and the
        caller records the abs-shape meta_problem (MAJOR-1 — a relative
        external must never become a silent OK)."""
        text = block("touch: external: src/local.py")
        m = mf.parse_manifest(text)
        assert len(m.claims) == 1
        assert m.claims[0].external is False
        assert any("external: value must be an absolute path" in p
                   for p in m.meta_problems)

    def test_tilde_home_path_is_external(self):
        """Case (iv): `external: ~/x.py` is abs-shaped (home expansion)."""
        c = mf.parse_entry("touch", "external: ~/x.py")
        assert c.external is True
        assert c.path == "~/x.py"

    def test_iter_blocks_files_excludes_external_claims(self):
        """Case (v): `iter_blocks` keeps an external abs path OUT of
        `files` (diff scoping stays repo-local) but the claim still parses
        into `parse_manifest`. A relative path in the same block stays in
        `files`."""
        text = block("touch: external: /abs/x.py, src/local.py", "# Step 1")
        [rec] = mf.iter_blocks(text)
        assert "/abs/x.py" not in rec.files
        assert "src/local.py" in rec.files
        m = mf.parse_manifest(text)
        assert {c.path for c in m.claims} == {"/abs/x.py", "src/local.py"}

    def test_ordinary_touch_byte_identical(self):
        """Case (vi): ordinary `touch:` entries behave byte-identically —
        no external flag, no meta_problem, files untouched."""
        text = block("touch: src/auth.py::validate_token")
        [rec] = mf.iter_blocks(text)
        assert rec.files == ["src/auth.py"]
        assert mf.parse_manifest(text).meta_problems == []

    def test_quote_wrapped_spaced_abs_path(self):
        """Owner lock 12b: `external: "/abs/path with spaces/f.py"` — the
        quote-wrapped form lets an author carry spaces that the unquoted
        form truncates at the first space."""
        c = mf.parse_entry("touch", 'external: "/abs/path with spaces/f.py"')
        assert c.external is True
        assert c.path == "/abs/path with spaces/f.py"
        assert c.symbol is None

    def test_quote_wrapped_abs_path_with_symbol(self):
        """Owner lock 12b: `external: '/abs/x.py::sym'` — quote wraps the
        whole value, symbol part still split after the quotes are stripped."""
        c = mf.parse_entry("touch", "external: '/abs/x.py::sym'")
        assert c.external is True
        assert c.path == "/abs/x.py"
        assert c.symbol == "sym"

class TestParentHeadingStep:
    """agent_village S8 (2026-11-04): a task covering two steps names the heading over them."""

    PLAN = (
        "## Steps\n\n"
        "### Step 1 — test\n\n<!-- plan-verify\nnew: tests/test_a.py::test_x\n-->\n\n"
        "### Step 2 — fix\n\n<!-- plan-verify\ntouch: a.py::f\n-->\n\n"
        "## Out of Scope\n\n<!-- plan-verify\ntouch: b.py::g\n-->\n"
    )

    def test_a_parent_heading_selects_every_block_under_it_and_none_after(self):
        for step in ("## Steps", "Steps"):
            m, matched = mf.parse_manifest_for_step(self.PLAN, step)
            assert matched
            assert sorted(c.raw for c in m.claims) == ["a.py::f", "tests/test_a.py::test_x"]

    def test_an_exact_step_heading_still_selects_only_its_own_block(self):
        m, matched = mf.parse_manifest_for_step(self.PLAN, "Step 2 — fix")
        assert matched
        assert [c.raw for c in m.claims] == ["a.py::f"]

    def test_an_unknown_heading_still_matches_nothing(self):
        assert mf.parse_manifest_for_step(self.PLAN, "## Nope")[1] is False
