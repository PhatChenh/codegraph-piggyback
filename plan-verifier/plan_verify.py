#!/usr/bin/env python3
"""plan_verify — mechanically fact-check a plan's code claims against codegraph.

Before a plan is approved, every claim that names a piece of code is looked up
in `.codegraph/codegraph.db` and verdicted. No LLM anywhere in the pipeline —
the result is evidence, not another opinion.

Claim sources (design.md, skeleton-contracts Block 2):
  Tier 1 — declared manifest block(s) inside the plan markdown:

      <!-- plan-verify
      touch: src/auth.py::validate_token, src/db.py::get_conn
      new:   src/auth.py::refresh_token
      remove: src/auth.py::legacy_check
      tier: A
      gates: research:bullmq-remove-api, human:merge-signoff
      qualifiers: grep-absent "lib/db" lib/analytics/sinks/*.py ; byte-unchanged lib/canvas/store.ts
      -->

    touch/new/remove: comma-separated entries — `path::symbol` | bare path |
    bare symbol. Multiple blocks allowed (one per plan Step); lists concatenate.
    tier/gates/qualifiers (extension, BLUEPRINT §2.2 / M3-fleet 2026-07-04):
    per-block metadata. plan_verify VALIDATES their shape and reports them;
    qualifiers are EXECUTED later by diff-verifier at wave-end, never here.

  Tier 2 — heuristic sweep: backticked identifiers/paths in prose, resolved the
    same conservative way. Swept claims are touch-class only and lower
    confidence; they warn but never fail --strict (measured noise rate on real
    plans in this workspace: see design.md "Measured sweep noise").

Verdicts (frozen, Block 3a): OK · MISSING · AMBIGUOUS · COLLISION · BLOCKED ·
UNACKNOWLEDGED-BLAST. Gate semantics (frozen, Block 3b): default advisory
exit 0; --strict exit 1 on any manifest MISSING / COLLISION / BLOCKED.
AMBIGUOUS + UNACKNOWLEDGED-BLAST warn-only even in strict.

  Tier 3 — spec-reuse cross-check (`--spec <spec.md>`, added 2026-07-19 after
    the P9-w2b Step 5 probe defect): every row of the spec's "Already built
    (reuse, do not rebuild)" table whose Depth column says `deep` must be
    referenced somewhere in the plan (symbol name, path, or path basename).
    A dropped row is exactly how the w2b plan lost the canonical ACP client
    and the implementer invented a protocol. Verdict REUSE-DROPPED is
    warn-only (never fails --strict) — the reuse table's shape varies across
    specs, so this is a loud flag, not a gate.

Usage:
  plan_verify.py <plan.md> [--spec <spec.md>] [--strict] [--json] [--db PATH]
  plan_verify.py --hook          # Claude Code PostToolUse:Write|Edit hook mode
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _shared import resolve as _rs                                  # noqa: E402
from _shared.budget import emit_budgeted                            # noqa: E402
from _shared.db import SchemaError, find_db, open_db, repo_root_for  # noqa: E402
from _shared.hookio import emit_context, read_hook_input, run_fail_open  # noqa: E402
from _shared.manifest import (                                       # noqa: E402
    Claim,
    Manifest,
    parse_entry,
    parse_manifest,
    strip_blocks,
)
from _shared.queries import callers_of, callers_of_name, unresolved_ref_names  # noqa: E402

# ── contract constants ───────────────────────────────────────────────────────

OK, MISSING, AMBIG, COLLISION, BLOCKED, BLAST = (
    "OK", "MISSING", "AMBIGUOUS", "COLLISION", "BLOCKED", "UNACKNOWLEDGED-BLAST")

BLAST_THRESHOLD = 6          # impact-analyzer HIGH tier; config, not contract (Block 3b)
STRICT_FAILS = {MISSING, COLLISION, BLOCKED}   # manifest claims only (Block 3b)
ON_DISK_EVIDENCE = "on disk, not in index"     # path-only claim, file on disk (bkt3)
HOOK_BUDGET_LINES = 28

# plan-file globs for hook mode (integer scheme + legacy fallbacks)
PLAN_GLOBS = ("*plan*.md", "docs/plans/*", "*/6_plans/*", "*/4_plans/*")


# ── heuristic sweep (tier 2) ─────────────────────────────────────────────────

_TOKEN_RE = re.compile(r"`([^`\n]+)`")
_IDENT = re.compile(r"^[A-Za-z_]\w*$")
_LINE_SUFFIX = re.compile(r":\d+(-\d+)?$")           # worker.ts:165-180 → worker.ts
_STOPWORDS = {
    # py + ts/js keywords + doc-prose noise that resolves to nothing useful
    # (measured on 3 real mkt_engine plans, 2026-07-05 — see design.md)
    "if", "for", "while", "with", "print", "return", "raise", "import", "from",
    "class", "def", "assert", "yield", "lambda", "not", "and", "or", "in", "is",
    "else", "elif", "try", "except", "finally", "pass", "break", "continue",
    "del", "global", "nonlocal", "True", "False", "None", "null", "true",
    "false", "self", "str", "int", "bool", "float", "dict", "list",
    "set", "tuple", "main", "TODO", "OK", "FAIL", "PASS",
    "never", "void", "string", "number", "boolean", "any", "unknown", "async",
    "await", "type", "interface", "enum", "const", "let", "var", "new", "this",
    "super", "extends", "implements", "export", "default", "function",
    "undefined", "NaN", "Promise", "Record", "Partial", "Pick", "Omit",
    "Readonly", "keyof", "typeof", "readonly", "static", "public", "private",
}
# doc-ish / non-code extensions the sweep should never treat as code claims
_NONCODE_EXT = (".md", ".json", ".yaml", ".yml", ".lock", ".log", ".txt",
                ".csv", ".html", ".svg", ".png")


def sweep_tokens(text: str, already: set[str]) -> list[str]:
    out, seen = [], set()
    text_wo_manifest = strip_blocks(text)
    for raw in _TOKEN_RE.findall(text_wo_manifest):
        tok = raw.strip().rstrip("()")
        tok = _LINE_SUFFIX.sub("", tok)              # file.ts:165-180 → file.ts
        if (tok in seen or tok in already or tok in _STOPWORDS or len(tok) < 3):
            continue
        if "://" in tok or tok.lower().endswith(_NONCODE_EXT):
            continue
        if _rs.looks_pathish(tok) or _IDENT.match(tok):
            seen.add(tok)
            out.append(tok)
    return out


# ── spec-reuse cross-check (tier 3) ──────────────────────────────────────────

_REUSE_HEADING_RE = re.compile(r"^#{1,6}\s+.*already built.*$",
                               re.IGNORECASE | re.MULTILINE)
_ANY_HEADING_RE = re.compile(r"^#{1,6}\s+", re.MULTILINE)
_BACKTICKED_RE = re.compile(r"`([^`]+)`")
_LOC_LINE_SUFFIX = re.compile(r":[\dL+#-]+\+?$")     # acp.ts:406+ → acp.ts


def spec_reuse_rows(spec_text: str) -> list[tuple[str, str]]:
    """Parse the spec's 'Already built (reuse, do not rebuild)' table.

    Returns (name, path) per row whose LAST cell contains 'deep' (the depth
    column). name = first backticked token of cell 1 (else its plain text);
    path = first backticked token of cell 2 with any :line suffix stripped.
    Empty list when the heading or table is absent — the caller notes that.
    """
    hm = _REUSE_HEADING_RE.search(spec_text)
    if not hm:
        return []
    section = spec_text[hm.end():]
    nm = _ANY_HEADING_RE.search(section)
    if nm:
        section = section[:nm.start()]
    rows: list[tuple[str, str]] = []
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2 or all(set(c) <= {"-", ":", " "} for c in cells):
            continue                                   # separator row
        if "deep" not in cells[-1].lower():
            continue                                   # header row / shallow row
        name_m = _BACKTICKED_RE.search(cells[0])
        name = (name_m.group(1) if name_m else cells[0]).strip()
        path_m = _BACKTICKED_RE.search(cells[1])
        path = _LOC_LINE_SUFFIX.sub("", path_m.group(1).strip()) if path_m else ""
        if name or path:
            rows.append((name, path))
    return rows


def _reuse_ident(name: str) -> str:
    """Strip decoration off a spec row's function name so the reuse cross-check
    matches the bare identifier in the plan.

    Paren suffix first (``runFalQueue(...)`` -> ``runFalQueue``), then the
    unicode ellipsis ``…``, then ASCII ``...``. Never ``rstrip(".")`` — a
    trailing dot is a legitimate identifier character."""
    original = name.strip()
    s = original
    if "(" in s:
        s = s.split("(", 1)[0]
    s = s.rstrip("…")
    if s.endswith("..."):
        s = s[:-3]
    s = s.strip()
    return s if s else original


def check_spec_reuse(spec_text: str, plan_text: str) -> tuple[list[dict], list[str]]:
    """REUSE-DROPPED findings + notes. A row passes when its symbol name, its
    path, or its path basename appears anywhere in the plan text."""
    rows = spec_reuse_rows(spec_text)
    if not rows:
        return [], ["spec-reuse: no 'Already built' table with deep rows found "
                    "in the spec — cross-check skipped"]
    dropped = []
    for name, path in rows:
        ident = _reuse_ident(name)
        if ident and ident in plan_text:
            continue
        if path and (path in plan_text or Path(path).name in plan_text):
            continue
        dropped.append({
            "verdict": "REUSE-DROPPED",
            "name": ident, "path": path,
            "evidence": f"spec reuse row `{ident}` ({path or 'no path'}) depth=deep "
                        "is never referenced by the plan — the step that needs it "
                        "may reinvent it (P9-w2b failure shape)"})
    return dropped, []


# ── verdict computation ──────────────────────────────────────────────────────

def _path_only(claim: Claim) -> bool:
    return bool(
        claim.path
        and not claim.symbol
        and not claim.external
        and "::" not in claim.raw
        and not claim.raw.lstrip().startswith("external:")
    )


def _on_disk(repo_root: Path | None, rel: str | None) -> bool:
    if repo_root is None or not rel:
        return False
    if Path(rel).is_absolute() or rel.startswith("~"):
        return False
    try:
        root = repo_root.resolve()
        cand = (root / Path(rel)).resolve()
        return cand.is_relative_to(root) and cand.is_file()
    except (OSError, RuntimeError):
        return False


def _mentions(plan_text: str, caller: dict) -> bool:
    """Deterministic 'does the plan acknowledge this caller': its symbol name or
    its file basename appears anywhere in the plan text."""
    base = Path(caller["file_path"]).name
    return caller["name"] in plan_text or base in plan_text


def _caller_evidence(callers: list[dict], unmentioned: list[dict]) -> str:
    tops = ", ".join(f"{c['file_path']}:{c['line']}" for c in unmentioned[:3])
    return f"{len(callers)} callers; unmentioned: {tops}" + (
        f" (+{len(unmentioned) - 3} more)" if len(unmentioned) > 3 else "")


def verdict_claim(con: sqlite3.Connection, claim: Claim, plan_text: str,
                  dynamic_names: set[str],
                  repo_root: Path | None = None) -> None:
    if claim.external:
        # `external: <abs-path>` declares a target outside the indexed repo —
        # no node/file to resolve, so verdict OK with honest evidence (21.4).
        claim.verdict, claim.evidence = OK, "declared outside the indexed repo (external:)"
        return
    token = claim.symbol or claim.path or claim.raw
    res = _rs.resolve(con, token, file_hint=claim.path if claim.symbol else None)

    if claim.intent == "new":
        if res.state == _rs.UNRESOLVED:
            if _path_only(claim) and _on_disk(repo_root, claim.path):
                claim.verdict, claim.evidence = COLLISION, ON_DISK_EVIDENCE
            else:
                claim.verdict, claim.evidence = OK, "no existing match"
        else:
            claim.verdict = COLLISION
            claim.evidence = "exists: " + ", ".join(c.loc for c in res.candidates[:3])
        if claim.symbol and claim.symbol in dynamic_names:
            claim.notes.append(
                f"`{claim.symbol}` already appears in unresolved_refs — something "
                "references this name dynamically")
        return

    # touch / remove / swept need the target to exist
    if res.state == _rs.UNRESOLVED:
        if _path_only(claim) and _on_disk(repo_root, claim.path):
            claim.verdict, claim.evidence = OK, ON_DISK_EVIDENCE
        else:
            claim.verdict = MISSING
            claim.evidence = f"no node or file matches {token!r}"
        return
    if res.state == _rs.AMBIGUOUS:
        claim.verdict = AMBIG
        claim.evidence = f"{len(res.candidates)} matches: " + ", ".join(
            c.loc for c in res.candidates[:4])
        return

    node = res.node
    callers = (callers_of(con, node.node_id) if node.node_id
               else callers_of_name(con, Path(node.file_path).stem))
    unmentioned = [c for c in callers if not _mentions(plan_text, c)]

    if claim.intent == "remove":
        if unmentioned:
            claim.verdict = BLOCKED
            claim.evidence = _caller_evidence(callers, unmentioned)
        else:
            claim.verdict = OK
            claim.evidence = f"{node.loc} ({len(callers)} callers, all acknowledged)"
        return

    # touch / swept
    if len(callers) >= BLAST_THRESHOLD and len(unmentioned) == len(callers):
        claim.verdict = BLAST
        claim.evidence = f"{node.loc} — " + _caller_evidence(callers, unmentioned)
    else:
        claim.verdict = OK
        claim.evidence = f"{node.loc} ({len(callers)} callers)"


def verify(plan_path: Path, db_path: Path | None,
           spec_path: Path | None = None) -> dict:
    text = plan_path.read_text(errors="replace")
    db = db_path or find_db(plan_path.resolve().parent)
    if db is None:
        return {"error": "no .codegraph/codegraph.db found walking up from the plan"}
    con = open_db(db)
    root = repo_root_for(db)

    reuse_dropped: list[dict] = []
    reuse_notes: list[str] = []
    if spec_path is not None:
        reuse_dropped, reuse_notes = check_spec_reuse(
            spec_path.read_text(errors="replace"), text)

    manifest = parse_manifest(text)
    already = {c.raw for c in manifest.claims} | {
        c.symbol for c in manifest.claims if c.symbol} | {
        c.path for c in manifest.claims if c.path}
    swept = [parse_entry("swept", t) for t in sweep_tokens(text, already)]

    dynamic = unresolved_ref_names(con)
    for claim in [*manifest.claims, *swept]:
        verdict_claim(con, claim, text, dynamic, root)

    n_manifest = len(manifest.claims)
    strict_fail = [c for c in manifest.claims if c.verdict in STRICT_FAILS]
    return {
        "plan": str(plan_path),
        "db": str(db),
        "manifest_claims": manifest.claims,
        "swept_claims": swept,
        "tiers": manifest.tiers,
        "gates": manifest.gates,
        "qualifiers": manifest.qualifiers,
        "meta_problems": manifest.meta_problems,
        "counts": {"manifest": n_manifest, "swept": len(swept)},
        "strict_fail": strict_fail,
        "reuse_dropped": reuse_dropped,
        "reuse_notes": reuse_notes,
    }


# ── output ───────────────────────────────────────────────────────────────────

def _row(prefix: str, claim: Claim) -> str:
    lines = [f"  {prefix:<6} {claim.raw:<42} {claim.verdict:<22} {claim.evidence}"]
    lines += [f"         note: {n}" for n in claim.notes]
    return "\n".join(lines)


def render(result: dict, problems_only: bool = False) -> str:
    mc, sc = result["manifest_claims"], result["swept_claims"]
    head = (f"── PLAN-VERIFY: {result['plan']} ── "
            f"{len(mc) + len(sc)} claims ({len(mc)} manifest, {len(sc)} swept)")
    rows = []
    for c in mc:
        if problems_only and c.verdict == OK and not c.notes:
            continue
        rows.append(_row(c.intent, c))
    for c in sc:
        if c.verdict == OK and not c.notes:
            continue                      # swept OKs are noise even in full mode
        rows.append(_row("swept", c))
    for p in result["meta_problems"]:
        rows.append(f"  meta   {p}")
    for d in result.get("reuse_dropped", []):
        rows.append(f"  reuse  {d['name']:<42} {'REUSE-DROPPED':<22} {d['evidence']}")
    for n in result.get("reuse_notes", []):
        rows.append(f"  note   {n}")
    if result["gates"]:
        rows.append(f"  gates  {', '.join(result['gates'])} (orchestrator may not "
                    "cross without recorded sign-off)")
    fails = result["strict_fail"]
    tail = ("── verdict: FAIL (" + ", ".join(
        f"{sum(1 for c in fails if c.verdict == v)} {v}"
        for v in (MISSING, COLLISION, BLOCKED)
        if any(c.verdict == v for c in fails)) + ") ──") if fails else \
        "── verdict: PASS (no manifest MISSING/COLLISION/BLOCKED) ──"
    return "\n".join([head, *rows, tail])


def to_json(result: dict) -> str:
    def claim_dict(c: Claim) -> dict:
        return {"intent": c.intent, "raw": c.raw, "verdict": c.verdict,
                "evidence": c.evidence, "notes": c.notes, "external": c.external}
    return json.dumps({
        "plan": result["plan"],
        "manifest": [claim_dict(c) for c in result["manifest_claims"]],
        "swept": [claim_dict(c) for c in result["swept_claims"]],
        "tiers": result["tiers"], "gates": result["gates"],
        "qualifiers": result["qualifiers"],
        "meta_problems": result["meta_problems"],
        "reuse_dropped": result.get("reuse_dropped", []),
        "reuse_notes": result.get("reuse_notes", []),
        "strict_fail": bool(result["strict_fail"]),
    }, indent=2)


# ── hook mode ────────────────────────────────────────────────────────────────

def is_plan_path(path: str) -> bool:
    p = path.replace("\\", "/")
    name = Path(p).name.lower()
    return any(fnmatch.fnmatch(name, g) if "/" not in g else fnmatch.fnmatch(p, "*" + g)
               for g in PLAN_GLOBS)


def hook_main() -> int:
    data = read_hook_input()
    if not data or data.get("tool_name") not in ("Write", "Edit"):
        return 0
    fp = (data.get("tool_input") or {}).get("file_path", "")
    if not fp or not fp.endswith(".md") or not is_plan_path(fp):
        return 0
    plan = Path(fp)
    if not plan.is_file():
        return 0
    result = verify(plan, None)
    if "error" in result:
        return 0                                    # no DB → silent no-op
    bad_manifest = [c for c in result["manifest_claims"] if c.verdict != OK]
    bad_swept = [c for c in result["swept_claims"] if c.verdict != OK]
    if not bad_manifest and not bad_swept and not result["meta_problems"]:
        return 0                                    # all OK → silent
    lines = render(result, problems_only=True).splitlines()
    emit_context("\n".join(emit_budgeted(lines, HOOK_BUDGET_LINES, "rows")))
    return 0


# ── entrypoint ───────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(prog="plan_verify", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan", nargs="?", help="path to the plan markdown")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 on any manifest MISSING/COLLISION/BLOCKED")
    ap.add_argument("--spec", help="spec markdown to cross-check: every deep row "
                    "of its 'Already built (reuse)' table must be referenced by "
                    "the plan (REUSE-DROPPED warn otherwise; never fails --strict)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--db", help="path to .codegraph/codegraph.db (default: walk up)")
    ap.add_argument("--hook", action="store_true", help="hook mode (stdin JSON)")
    args = ap.parse_args()

    if args.hook:
        run_fail_open(hook_main)
        return

    if not args.plan:
        ap.error("plan path required (or --hook)")
    plan = Path(args.plan)
    if not plan.is_file():
        print(f"error: no such plan file: {plan}", file=sys.stderr)
        sys.exit(2)
    spec = Path(args.spec) if args.spec else None
    if spec is not None and not spec.is_file():
        print(f"error: no such spec file: {spec}", file=sys.stderr)
        sys.exit(2)
    try:
        result = verify(plan, Path(args.db) if args.db else None, spec_path=spec)
    except (FileNotFoundError, SchemaError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(2)
    if "error" in result:
        print(f"error: {result['error']}", file=sys.stderr)
        sys.exit(2)

    print(to_json(result) if args.json else render(result))
    sys.exit(1 if (args.strict and result["strict_fail"]) else 0)


if __name__ == "__main__":
    main()
