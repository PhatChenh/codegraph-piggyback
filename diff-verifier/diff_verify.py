#!/usr/bin/env python3
"""diff_verify — wave-end mechanical compliance: diff vs plan manifest.

Reads the SAME `<!-- plan-verify -->` manifest as plan_verify (parser:
_shared/manifest.py) and verdicts an implementation diff against it:

  OUT-OF-SCOPE-TOUCH   changed file not in the declared file list / --allow
  QUALIFIER-FAIL       a qualifiers: entry ran dirty (named)
  NOT-DELIVERED        declared new: symbol still absent from the DB
  NOT-REMOVED          declared remove: symbol still present in the DB
  TESTS-MISSING        declared test files absent from the diff

Zero LLM. Exit 0 advisory; --strict exits 1 on any verdict. See design.md for
what this deliberately does NOT catch (phase-end strong-model review keeps
wrong-but-green logic, quality, security).

Usage:
  diff_verify.py <plan.md> --diff <base>..<head> [--strict] [--json]
  diff_verify.py <plan.md> --files f1 f2 ...     [--strict] [--skip-db]
  diff_verify.py <plan.md> --per-step [--json]   # 2026-07-07 P8 listing mode

`--per-step` (added 2026-07-07 for agent_village P8 `av verify-wave --preflight`,
ADR-0011 pinned seam) emits one record per `<!-- plan-verify -->` block —
step id, declared file paths, `tier:` value (or explicit absent marker),
`gates:` list, plus any per-block tier problems — as JSON. Works WITHOUT a
git diff: it is a pure manifest listing, used for tier-law + tier-floor lint
BEFORE the wave runs.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _shared import resolve as _rs                      # noqa: E402
from _shared.db import SchemaError, find_db, open_db    # noqa: E402
from _shared.manifest import (                            # noqa: E402
    iter_blocks,
    parse_manifest,
    parse_manifest_for_step,
)

OUT_OF_SCOPE = "OUT-OF-SCOPE-TOUCH"
QUALIFIER_FAIL = "QUALIFIER-FAIL"
NOT_DELIVERED = "NOT-DELIVERED"
NOT_REMOVED = "NOT-REMOVED"
TESTS_MISSING = "TESTS-MISSING"
MANIFEST_EMPTY = "MANIFEST-EMPTY"
PLAN_MALFORMED_MARKER = "PLAN-MALFORMED:"

TEST_GLOBS = ("test_*", "*_test.*", "*.test.*")

# Code the codegraph index parses. A path claim outside this set is a document
# (or data) deliverable: the index holds no rows for it, so asking it whether
# the file exists can only ever answer UNRESOLVED. Those claims are verified on
# disk instead. Measured 2026-10-23: the index held 169 files and zero .md rows,
# so every markdown `new:` claim failed NOT-DELIVERED with the file present.
CODE_EXTENSIONS = frozenset({
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".py", ".go", ".rs", ".java", ".rb", ".php", ".cs", ".kt", ".swift",
    ".c", ".h", ".cc", ".cpp", ".hpp", ".m", ".mm", ".scala", ".sh",
})


def is_test_path(p: str) -> bool:
    parts = Path(p).parts
    name = Path(p).name
    return "tests" in parts or any(fnmatch.fnmatch(name, g) for g in TEST_GLOBS)


def is_document_claim(claim) -> bool:
    """True for a path-bearing claim the code index cannot resolve.

    Only path claims qualify. A bare-symbol claim (`touch: av`) keeps the
    symbol lookup — it is code by definition. An extensionless path is treated
    as a document only when its extension is not indexable code.
    """
    path = claim.path
    if not path:
        return False
    return Path(path).suffix.lower() not in CODE_EXTENSIONS


def index_cannot_hold(con, claim) -> bool:
    """True for a path-only claim whose extension has no row in the index.

    `.sh` is in CODE_EXTENSIONS but an index may hold zero shell files, so a
    lookup could only answer UNRESOLVED (agent_village av-improve B3). Such a
    claim is checked on disk. Limit: one indexed file of that extension sends
    every other claim of it back to the index lookup.
    """
    if not claim.path or claim.symbol:
        return False
    suffix = Path(claim.path).suffix.lower()
    if not suffix:
        return False
    row = con.execute("SELECT 1 FROM files WHERE lower(path) LIKE ? LIMIT 1",
                      ("%" + suffix,)).fetchone()
    return row is None


def document_verdict(repo_root: Path, claim) -> tuple[str, str] | None:
    """On-disk verdict for a document claim: (reason, detail) or None if fine.

    `new`/`touch` require the file to exist; `remove` requires it to be gone.
    Same existence contract the index lookup enforces for code — content
    quality is the contract check's job, not this tool's.
    """
    path = claim.path
    if path is None:
        return None
    target = Path(path) if Path(path).is_absolute() else (repo_root / path)
    exists = target.exists()
    if claim.intent == "remove" and exists:
        return ("still-present", path)
    if claim.intent in ("new", "touch") and not exists:
        return ("missing", path)
    return None


# ── diff acquisition ─────────────────────────────────────────────────────────

def diff_files(repo_root: Path, diff_range: str) -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--name-only", diff_range],
        cwd=repo_root, capture_output=True, text=True, check=True)
    return [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]


# ── qualifier execution (restricted verbs only — design.md) ─────────────────

def run_qualifier(q: str, repo_root: Path, changed: list[str],
                  scoped: list[str] | None = None) -> str | None:
    """None = clean; else the failure evidence string. `scoped` = changed files
    minus --allow-admitted ones (used by scope-class verbs only)."""
    if scoped is None:
        scoped = changed
    try:
        parts = shlex.split(q)
    except ValueError as e:
        return f"unparseable: {e}"
    if not parts:
        return "empty qualifier"
    verb, args = parts[0], parts[1:]

    if verb == "byte-unchanged":
        if len(args) != 1:
            return "byte-unchanged wants exactly one path"
        return f"{args[0]} was changed" if args[0] in changed else None

    if verb == "diff-only-within":
        # scope-class constraint: --allow-admitted files are exempt (same class
        # as OUT-OF-SCOPE-TOUCH). byte-unchanged/grep-absent are safety-class —
        # --allow never bypasses those.
        if not args:
            return "diff-only-within wants at least one dir"
        dirs = [a.rstrip("/") + "/" for a in args]
        outside = [f for f in scoped if not any(f.startswith(d) for d in dirs)]
        return (f"outside {args}: {', '.join(outside[:5])}" if outside else None)

    if verb == "grep-absent":
        if len(args) != 2:
            return 'grep-absent wants: "<literal>" <glob>'
        literal, glob = args
        hits = []
        matched_any = False
        for f in sorted(repo_root.glob(glob)):
            if f.is_file():
                matched_any = True
                if literal in f.read_text(errors="replace"):
                    hits.append(str(f.relative_to(repo_root)))
        if not matched_any:
            return f"no file matches {glob!r}"
        return (f"{literal!r} found in: {', '.join(hits[:5])}" if hits else None)

    if verb == "grep-present":
        # Safety-class like grep-absent (--allow never bypasses it). Added
        # 2026-07-19 (P9-w2b stub-drift guard): a plan can demand that the
        # delivered code references a required artifact — e.g. the real
        # protocol's schema validator in a probe — so green-against-own-stub
        # can't clear wave-end.
        if len(args) != 2:
            return 'grep-present wants: "<literal>" <glob>'
        literal, glob = args
        matched_any = False
        for f in sorted(repo_root.glob(glob)):
            if f.is_file():
                matched_any = True
                if literal in f.read_text(errors="replace"):
                    return None
        return (f"{literal!r} not found in any file matching {glob!r}"
                if matched_any else f"no file matches {glob!r}")

    return (f"unknown verb {verb!r} (allowed: grep-absent, grep-present, "
            "byte-unchanged, diff-only-within)")


# ── core ─────────────────────────────────────────────────────────────────────

def _manifest_empty_unknown_keys(meta_problems: list[str]) -> list[str]:
    """Extract unknown-key names from a `parse_manifest` meta_problems list.
    Added 2026-07-27 (Bucket B Step 3) so `verify()` can name them in a
    MANIFEST-EMPTY finding (Step 3 / D1 / RT M-5: a finding, not a note, so
    wave-end fails closed rather than merely narrating)."""
    out: list[str] = []
    for p in meta_problems:
        prefix = "unknown manifest key: '"
        if p.startswith(prefix) and p.endswith("'"):
            out.append(p[len(prefix):-1])
        elif p.startswith("unknown manifest key: "):
            # fall back: strip the static prefix and any surrounding quotes
            rest = p[len("unknown manifest key: "):].strip()
            if len(rest) >= 2 and rest[0] in "\"'" and rest[-1] == rest[0]:
                rest = rest[1:-1]
            out.append(rest)
    return out


def verify(plan_path: Path, changed: list[str], repo_root: Path,
           allow: list[str], skip_db: bool, db_path: Path | None,
           step: str | None = None) -> dict:
    text = plan_path.read_text(errors="replace")
    # BUG-024: `--step` scopes the whole verdict to ONE plan-verify block, so a
    # multi-wave plan can pass mid-phase (before later steps' symbols exist).
    # Without it, `verify()` verdicts a single wave's diff against the ENTIRE
    # plan's manifest → NOT-DELIVERED for every not-yet-built later-step symbol.
    if step is not None:
        manifest, matched = parse_manifest_for_step(text, step)
        if not matched:
            raise SchemaError(
                f"--step {step!r} matched no plan-verify block in {plan_path} "
                "(step id is the block's nearest preceding heading, or "
                "'block-N'); run --per-step to list the available step ids")
    else:
        manifest = parse_manifest(text)
    findings: list[dict] = []
    notes: list[str] = []
    if step is not None:
        notes.append(f"scoped to step {step!r} (BUG-024 per-wave verdict)")

    # 1 — scope: every changed file ∈ declared paths ∪ allow globs
    declared = manifest.declared_paths()
    allowed = [f for f in changed if any(fnmatch.fnmatch(f, g) for g in allow)]
    for f in changed:
        if f in declared or f in allowed:
            continue
        findings.append({"verdict": OUT_OF_SCOPE, "evidence": f})

    # 1b — MANIFEST-EMPTY: unknown-key manifest with NO declared paths —
    # OUT-OF-SCOPE will silently check every changed file (the §0.3 trap that
    # teaches an ORCH to widen --allow until it stops). Step 3 / D1 / RT M-5:
    # emit a FINDING (not a note) naming the unknown keys. Appended OUTSIDE
    # the --allow admission path so widening globs cannot clear it
    # (capability C-06b). Gate-only empty with no unknown keys stays untouched
    # (legitimate `tier:` + `gates: human:…` step — §0.7's PASS class).
    unknown_keys = _manifest_empty_unknown_keys(manifest.meta_problems)
    if not declared and unknown_keys:
        findings.append({
            "verdict": MANIFEST_EMPTY,
            "evidence": f"unknown manifest keys: {', '.join(unknown_keys)}",
        })

    # 2 — qualifiers (scope-class verbs exempt --allow-admitted files;
    #     safety-class verbs never do)
    scoped = [f for f in changed if f not in allowed]
    for q in manifest.qualifiers:
        fail = run_qualifier(q, repo_root, changed, scoped)
        if fail:
            findings.append({"verdict": QUALIFIER_FAIL, "evidence": f"{q} → {fail}"})

    # 3 — new delivered / remove gone
    #     Code claims: DB re-query (the index is the authority for code).
    #     Document claims: on-disk existence (the index holds no rows for them,
    #     so a DB lookup could only ever answer UNRESOLVED — see CODE_EXTENSIONS).
    if skip_db:
        notes.append("DB checks SKIPPED (--skip-db): NOT-DELIVERED / NOT-REMOVED not verified")
    else:
        db = db_path or find_db(plan_path.resolve().parent)
        if db is None:
            notes.append("no codegraph DB found — NOT-DELIVERED / NOT-REMOVED not verified")
        else:
            con = open_db(db)
            document_claims = 0
            for c in manifest.claims:
                if is_document_claim(c) or index_cannot_hold(con, c):
                    document_claims += 1
                    bad = document_verdict(repo_root, c)
                    if bad is None:
                        continue
                    reason, path = bad
                    if reason == "still-present":
                        findings.append({"verdict": NOT_REMOVED,
                                         "evidence": f"{c.raw} still present at {path}"})
                    else:
                        findings.append({"verdict": NOT_DELIVERED,
                                         "evidence": f"{c.raw} absent from {path}"})
                    continue
                token = c.symbol or c.path or c.raw
                res = _rs.resolve(con, token,
                                  file_hint=c.path if c.symbol else None)
                if c.intent == "new" and res.state == _rs.UNRESOLVED:
                    findings.append({"verdict": NOT_DELIVERED, "evidence": c.raw})
                if c.intent == "remove" and res.state != _rs.UNRESOLVED:
                    locs = ", ".join(x.loc for x in res.candidates[:3])
                    findings.append({"verdict": NOT_REMOVED,
                                     "evidence": f"{c.raw} still at {locs}"})
            if document_claims:
                notes.append(
                    f"{document_claims} document claim(s) verified on disk "
                    "(the code index holds no rows for non-code paths)")

    # 4 — declared test files present in diff
    declared_tests = [p for p in declared if is_test_path(p)]
    if not declared_tests:
        notes.append("TESTS-MISSING n/a (no test files declared in manifest)")
    else:
        absent = [t for t in declared_tests if t not in changed]
        if absent:
            findings.append({"verdict": TESTS_MISSING, "evidence": ", ".join(absent)})

    if manifest.meta_problems:
        notes += [f"manifest: {p}" for p in manifest.meta_problems]

    return {"plan": str(plan_path), "changed": changed, "findings": findings,
            "notes": notes, "gates": manifest.gates, "tiers": manifest.tiers}


def render(result: dict) -> str:
    lines = [f"── DIFF-VERIFY: {result['plan']} ── {len(result['changed'])} changed files"]
    for f in result["findings"]:
        lines.append(f"  {f['verdict']:<20} {f['evidence']}")
    for n in result["notes"]:
        lines.append(f"  note: {n}")
    lines.append("── verdict: " + ("FAIL ({} finding{})".format(
        len(result["findings"]), "s" if len(result["findings"]) != 1 else "")
        if result["findings"] else "PASS") + " ──")
    return "\n".join(lines)


# ── per-step listing mode (P8 ADR-0011 seam) ─────────────────────────────────

def per_step_records(plan_path: Path) -> list[dict]:
    """Return one record per `<!-- plan-verify -->` block in the plan.

    Each record is the consumer-side JSON shape:
      {stepId, blockIndex, files[], tier (or null), tierAbsent, tierProblems[],
       gates[], qualifiers[], stepIdSource: "heading"|"synthetic"}

    `tierAbsent` is the explicit absent marker — true when `tier:` was missing
    or empty in the block. The consumer's tier-law check (P8 preflight)
    needs both `tier` AND `tierAbsent` to distinguish "tagged tier X" from
    "tag omitted". `tierProblems` carries the per-block meta_problems
    (e.g. an out-of-vocabulary tier like `D`) so the consumer can surface
    them without re-parsing the plan.
    """
    text = plan_path.read_text(errors="replace")
    records: list[dict] = []
    for r in iter_blocks(text):
        records.append({
            "stepId": r.step_id,
            "blockIndex": r.block_index,
            "files": r.files,
            "tier": r.tier,
            "tierAbsent": r.tier is None or r.tier == "",
            "tierProblems": r.tier_problems,
            "gates": r.gates,
            "qualifiers": r.qualifiers,
            "unknownKeys": r.unknown_keys,
            "stepIdSource": "heading" if not r.step_id.startswith("block-")
                            else "synthetic",
        })
    return records


def _block_body(text: str, block_index: int) -> str:
    """Return the body (lines between the `<!-- plan-verify` opener and the
    `-->` closer) of the Nth plan-verify block in `text`. Internal helper.
    """
    from _shared.manifest import _BLOCK_RE  # type: ignore
    for i, m in enumerate(_BLOCK_RE.finditer(text), start=1):
        if i == block_index:
            return m.group(1)
    return ""


def _per_block_claim_counts(plan_path: Path) -> list[int]:
    """Re-parse each plan-verify block's body and return the count of
    touch/new/remove claim entries (path- OR symbol-bearing). Used to
    distinguish D1's case 2 (claims present, no path) from case 3
    (gate-only, no claims at all). Cheap: a parse per block, no DB.
    """
    text = plan_path.read_text(errors="replace")
    counts: list[int] = []
    for b in iter_blocks(text):
        body = _block_body(text, b.block_index)
        snippet = f"<!-- plan-verify\n{body}\n-->\n"
        counts.append(len(parse_manifest(snippet).claims))
    return counts


def apply_d1_three_way_rule(plan_path: Path, records: list[dict]
                            ) -> list[dict]:
    """Apply D1's three-way rule (plan §1 / §0.7) to the per-step records.
    Returns the offending-step descriptors (empty when the plan is fine or
    has only warn / silent-pass zero-file steps). Each descriptor shape::

        {"stepId": str, "unknownKeys": list[str]}

    Three cases (matches the partition inventORied under §0.7's corpus probe):

    1. `files == []` AND unknown keys present → collect for refusal.
    2. `files == []`, no unknown keys, ≥1 claim (any intent) → warn on stderr.
       Bare-symbol claims (`touch: av`) are a documented form; warn because
       `touch: av` is also the §0.1 trap — refusing would break a documented
       shape.
    3. `files == []`, no unknown keys, no claims → gate-only step, silent pass.
       These are correct `tier:` + `gates: human:…` blocks (§0.7's PASS class).

    The caller prints the `PLAN-MALFORMED:` marker and exits 2 (CLI side
    effects — kept out of this pure function).
    """
    claim_counts = _per_block_claim_counts(plan_path)
    warnings_to_emit: list[str] = []
    offenders: list[dict] = []
    for rec, n in zip(records, claim_counts):
        if rec["files"]:  # non-empty → not a zero-file case
            continue
        unknown = list(rec.get("unknownKeys", []))
        if unknown:
            offenders.append({"stepId": rec["stepId"],
                               "unknownKeys": unknown})
        elif n > 0:
            warnings_to_emit.append(
                f"step {rec['stepId']!r} declares only symbols; "
                "if you meant a path, write path::symbol"
            )
        # else: gate-only, silent pass
    for w in warnings_to_emit:
        print(f"warning: {w}", file=sys.stderr)
    return offenders


def print_plan_malformed_block(plan_path: Path,
                                offenders: list[dict]) -> None:
    """Emit the stable `PLAN-MALFORMED:` block to stderr (one line per
    offending step + the fix). Step 3b consumes this marker at the `av`
    layer to rephrase the ORCH-facing headline.
    """
    print(f"{PLAN_MALFORMED_MARKER} {plan_path}", file=sys.stderr)
    for off in offenders:
        keys = ", ".join(repr(k) for k in off["unknownKeys"])
        print(
            f"  step {off['stepId']!r} has unknown manifest key(s) {keys}; "
            "use touch:/new:, and path::symbol for extensionless paths",
            file=sys.stderr,
        )


def main() -> None:
    ap = argparse.ArgumentParser(prog="diff_verify", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan", help="path to the plan markdown (with plan-verify manifest)")
    # `--per-step` is a listing-only mode; mutually exclusive with the diff/
    # files src group because it does not consume a diff. `--diff|--files`
    # remain required EXCEPT when `--per-step` is set.
    src = ap.add_mutually_exclusive_group(required=False)
    src.add_argument("--diff", help="git range, e.g. main..HEAD")
    src.add_argument("--files", nargs="+", help="explicit changed-file list")
    ap.add_argument("--per-step", action="store_true",
                    help="list one record per plan-verify block as JSON "
                         "(P8 preflight; no diff required)")
    ap.add_argument("--step",
                    help="scope the diff verdict to ONE plan-verify block "
                         "(its nearest-heading step id, or 'block-N'); a "
                         "multi-wave plan uses this so a mid-phase wave passes "
                         "without demanding later steps' symbols (BUG-024)")
    ap.add_argument("--allow", action="append", default=[],
                    help="glob of additionally-allowed changed files (repeatable); "
                         "run docs / STATE.md updates typically ride here")
    ap.add_argument("--repo-root", help="repo root (default: walk up from plan)")
    ap.add_argument("--db", help="path to codegraph.db (default: walk up)")
    ap.add_argument("--skip-db", action="store_true",
                    help="skip NOT-DELIVERED/NOT-REMOVED (no fresh index available)")
    ap.add_argument("--strict", action="store_true", help="exit 1 on any finding")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    plan = Path(args.plan)
    if not plan.is_file():
        print(f"error: no such plan file: {plan}", file=sys.stderr)
        sys.exit(2)

    # `--per-step` short-circuits the diff-verification path. Listing only.
    if args.per_step:
        try:
            records = per_step_records(plan)
        except (FileNotFoundError, SchemaError) as e:
            print(f"error: {e}", file=sys.stderr)
            sys.exit(2)
        # D1 three-way rule (plan §1 / §0.7). Refusals block the wave at
        # preflight with the stable PLAN-MALFORMED marker (consumed by
        # Step 3b at the `av` layer). Exit 2 — the existing setup/usage
        # failure code (lines :290, :298, :306, :323), NOT a new code
        # (capability C-15: the `av` exit-code table is byte-unchanged).
        try:
            offenders = apply_d1_three_way_rule(plan, records)
        except (FileNotFoundError, SchemaError) as e:
            print(f"error: {e}", file=sys.stderr)
            sys.exit(2)
        if offenders:
            print_plan_malformed_block(plan, offenders)
            sys.exit(2)
        print(json.dumps(records, indent=2))
        sys.exit(0)

    # Diff mode — enforce the (originally mutually exclusive + required) src group.
    if not (args.diff or args.files):
        print("error: one of --diff, --files, or --per-step is required",
              file=sys.stderr)
        sys.exit(2)

    if args.repo_root:
        repo_root = Path(args.repo_root)
    else:
        db_guess = find_db(plan.resolve().parent)
        repo_root = (db_guess.parent.parent if db_guess
                     else plan.resolve().parent)

    try:
        changed = (diff_files(repo_root, args.diff) if args.diff
                   else list(args.files))
        result = verify(plan, changed, repo_root, args.allow,
                        args.skip_db, Path(args.db) if args.db else None,
                        step=args.step)
    except (FileNotFoundError, SchemaError, subprocess.CalledProcessError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(2)

    print(json.dumps(result, indent=2) if args.json else render(result))
    sys.exit(1 if (args.strict and result["findings"]) else 0)


if __name__ == "__main__":
    main()
