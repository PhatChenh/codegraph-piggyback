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
from _shared.manifest import iter_blocks, parse_manifest  # noqa: E402

OUT_OF_SCOPE = "OUT-OF-SCOPE-TOUCH"
QUALIFIER_FAIL = "QUALIFIER-FAIL"
NOT_DELIVERED = "NOT-DELIVERED"
NOT_REMOVED = "NOT-REMOVED"
TESTS_MISSING = "TESTS-MISSING"

TEST_GLOBS = ("test_*", "*_test.*", "*.test.*")


def is_test_path(p: str) -> bool:
    parts = Path(p).parts
    name = Path(p).name
    return "tests" in parts or any(fnmatch.fnmatch(name, g) for g in TEST_GLOBS)


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
        for f in sorted(repo_root.glob(glob)):
            if f.is_file() and literal in f.read_text(errors="replace"):
                hits.append(str(f.relative_to(repo_root)))
        return (f"{literal!r} found in: {', '.join(hits[:5])}" if hits else None)

    return f"unknown verb {verb!r} (allowed: grep-absent, byte-unchanged, diff-only-within)"


# ── core ─────────────────────────────────────────────────────────────────────

def verify(plan_path: Path, changed: list[str], repo_root: Path,
           allow: list[str], skip_db: bool, db_path: Path | None) -> dict:
    manifest = parse_manifest(plan_path.read_text(errors="replace"))
    findings: list[dict] = []
    notes: list[str] = []

    # 1 — scope: every changed file ∈ declared paths ∪ allow globs
    declared = manifest.declared_paths()
    allowed = [f for f in changed if any(fnmatch.fnmatch(f, g) for g in allow)]
    for f in changed:
        if f in declared or f in allowed:
            continue
        findings.append({"verdict": OUT_OF_SCOPE, "evidence": f})

    # 2 — qualifiers (scope-class verbs exempt --allow-admitted files;
    #     safety-class verbs never do)
    scoped = [f for f in changed if f not in allowed]
    for q in manifest.qualifiers:
        fail = run_qualifier(q, repo_root, changed, scoped)
        if fail:
            findings.append({"verdict": QUALIFIER_FAIL, "evidence": f"{q} → {fail}"})

    # 3 — new delivered / remove gone (DB re-query)
    if skip_db:
        notes.append("DB checks SKIPPED (--skip-db): NOT-DELIVERED / NOT-REMOVED not verified")
    else:
        db = db_path or find_db(plan_path.resolve().parent)
        if db is None:
            notes.append("no codegraph DB found — NOT-DELIVERED / NOT-REMOVED not verified")
        else:
            con = open_db(db)
            for c in manifest.claims:
                token = c.symbol or c.path or c.raw
                res = _rs.resolve(con, token,
                                  file_hint=c.path if c.symbol else None)
                if c.intent == "new" and res.state == _rs.UNRESOLVED:
                    findings.append({"verdict": NOT_DELIVERED, "evidence": c.raw})
                if c.intent == "remove" and res.state != _rs.UNRESOLVED:
                    locs = ", ".join(x.loc for x in res.candidates[:3])
                    findings.append({"verdict": NOT_REMOVED,
                                     "evidence": f"{c.raw} still at {locs}"})

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
            "stepIdSource": "heading" if not r.step_id.startswith("block-")
                            else "synthetic",
        })
    return records


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
                        args.skip_db, Path(args.db) if args.db else None)
    except (FileNotFoundError, SchemaError, subprocess.CalledProcessError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(2)

    print(json.dumps(result, indent=2) if args.json else render(result))
    sys.exit(1 if (args.strict and result["findings"]) else 0)


if __name__ == "__main__":
    main()
