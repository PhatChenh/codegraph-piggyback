"""_shared.manifest — the `<!-- plan-verify -->` manifest parser.

The manifest is a PUBLIC CONTRACT (skeleton-contracts Block 2): produced by
planner agents, consumed by plan-verifier (claim checks), diff-verifier
(wave-end compliance), plan-visualizer (rendering). One parser here so the
three consumers can never drift on syntax. Extracted from plan_verify.py the
moment diff-verifier became the second consumer (the extraction rule).

Syntax (Block 2a, + tier/gates/qualifiers extension of 2026-07-04):

    <!-- plan-verify
    touch: src/auth.py::validate_token, src/db.py::get_conn
    new:   src/auth.py::refresh_token
    remove: src/auth.py::legacy_check
    tier: A
    gates: research:bullmq-remove-api, human:merge-signoff
    qualifiers: grep-absent "lib/db" src/api/*.py ; byte-unchanged lib/store.ts
    -->

Entry forms: `path::symbol` | bare path | bare symbol. Multiple blocks per
document allowed (one per plan Step); lists concatenate. Qualifiers use the
restricted verb grammar ONLY (no raw shell — decided 2026-07-05):
    grep-absent "<literal>" <glob>   pattern absent from files matching glob
    grep-present "<literal>" <glob>  pattern PRESENT in ≥1 file matching glob
                                     (added 2026-07-19: lets a plan demand e.g.
                                     a real-protocol schema import in a probe —
                                     the P9-w2b stub-drift guard)
    byte-unchanged <path>            path untouched by the diff
    diff-only-within <dir>[ <dir>…]  all diff files under the listed dirs

`iter_blocks(text)` (added 2026-07-07 for P8 diff-verifier `--per-step`
listing mode) walks the same blocks but preserves per-block attribution:
each yielded record carries its step heading text, its declared file paths,
the `tier:` value (or `None` if absent — explicit marker for the tier-law
check), the `gates:` list, and any per-block meta problems.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

VALID_TIERS = {"A", "B", "C"}
GATE_PREFIXES = ("research:", "human:")
QUALIFIER_VERBS = ("grep-absent", "grep-present", "byte-unchanged", "diff-only-within")

_BLOCK_RE = re.compile(r"^<!--\s*plan-verify\s*$(.*?)^-->\s*$",
                       re.MULTILINE | re.DOTALL)
_LINE_RE = re.compile(r"^\s*(touch|new|remove|tier|gates|qualifiers)\s*:\s*(.*)$")
_ANY_KEY_RE = re.compile(r"^\s*([a-z][a-z0-9_-]*)\s*:\s*(.*)$")
_PATHISH_HINT = re.compile(r"^[\w./-]+\.[A-Za-z0-9]+$")
# Heading form used by the build-pipeline plans: `### Step N — title`.
# Falls back to any `#`/`##`/`###` heading if the canonical form is absent.
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


@dataclass
class Claim:
    intent: str          # touch | new | remove | swept
    raw: str             # entry as written
    path: str | None     # file part, if any
    symbol: str | None   # symbol part, if any
    verdict: str = ""
    evidence: str = ""
    notes: list[str] = field(default_factory=list)
    external: bool = False   # `external: <abs-path>` value form (item 21.4)


@dataclass
class Manifest:
    claims: list[Claim] = field(default_factory=list)
    tiers: list[str] = field(default_factory=list)
    gates: list[str] = field(default_factory=list)
    qualifiers: list[str] = field(default_factory=list)
    meta_problems: list[str] = field(default_factory=list)

    def declared_paths(self) -> set[str]:
        return {c.path for c in self.claims if c.path}


@dataclass
class BlockRecord:
    """Per-block record (added 2026-07-07 for `--per-step` listing mode).

    Carries the step's heading text (the `stepId` consumer-side), its declared
    file paths (the `touch`+`new`+`remove` entries' path parts — none/symbol-
    only entries excluded), the `tier:` value (or `None` if absent — explicit
    marker so the consumer's tier-law check can detect a MISSING tag), the
    `gates:` list, and any per-block meta problems. Multiple `tier:` lines in
    one block collapse to the last one (matches `parse_manifest` semantics).
    """
    step_id: str            # heading text, or "block-N" if no preceding heading
    block_index: int        # 1-based ordinal among the document's plan-verify blocks
    files: list[str]        # declared paths (touch + new + remove entries with a path)
    tier: str | None        # last tier: value, or None if absent
    tier_problems: list[str] = field(default_factory=list)
    gates: list[str] = field(default_factory=list)
    qualifiers: list[str] = field(default_factory=list)
    unknown_keys: list[str] = field(default_factory=list)


def looks_pathish(token: str) -> bool:
    return bool(_PATHISH_HINT.match(token)) or "/" in token


def parse_entry(intent: str, raw: str) -> Claim:
    raw = raw.strip()
    if raw.startswith("external:"):
        rest = raw[len("external:"):].strip()
        # Owner lock 12b (2026-08-09): quote-wrapped abs paths carry spaces
        # (`external: "/abs/path with spaces/f.py"`, `external: '/abs/x.py::sym'`).
        # Unquoted spaced paths still truncate at the first space; the quoted
        # form is the fix.
        if len(rest) >= 2 and rest[0] == rest[-1] and rest[0] in "\"'":
            rest = rest[1:-1].strip()
        if rest.startswith("/") or rest.startswith("~/"):
            if "::" in rest:
                p, s = rest.split("::", 1)
                return Claim(intent, raw, p.strip() or None, s.strip() or None,
                             external=True)
            return Claim(intent, raw, rest, None, external=True)
        # relative remainder: no flag — falls through to the normal branches
        # unchanged; the caller records the abs-shape meta_problem.
    if "::" in raw:
        p, s = raw.split("::", 1)
        return Claim(intent, raw, p.strip() or None, s.strip() or None)
    if looks_pathish(raw):
        return Claim(intent, raw, raw, None)
    return Claim(intent, raw, None, raw)


def strip_blocks(text: str) -> str:
    return _BLOCK_RE.sub("", text)


def parse_manifest(text: str) -> Manifest:
    m = Manifest()
    for block in _BLOCK_RE.findall(text):
        for line in block.splitlines():
            lm = _LINE_RE.match(line)
            if not lm:
                ak = _ANY_KEY_RE.match(line)
                if ak:
                    m.meta_problems.append(f"unknown manifest key: {ak.group(1)!r}")
                continue
            key, val = lm.group(1), lm.group(2).strip()
            if key in ("touch", "new", "remove"):
                for raw in filter(None, (e.strip() for e in val.split(","))):
                    c = parse_entry(key, raw)
                    m.claims.append(c)
                    if raw.startswith("external:") and not c.external:
                        m.meta_problems.append(
                            "external: value must be an absolute path")
            elif key == "tier":
                m.tiers.append(val)
                if val not in VALID_TIERS:
                    m.meta_problems.append(f"tier: {val!r} not in {sorted(VALID_TIERS)}")
            elif key == "gates":
                for g in filter(None, (e.strip() for e in val.split(","))):
                    m.gates.append(g)
                    if not g.startswith(GATE_PREFIXES):
                        m.meta_problems.append(
                            f"gate {g!r} lacks a {'/'.join(GATE_PREFIXES)} prefix")
            elif key == "qualifiers":
                for q in filter(None, (e.strip() for e in val.split(";"))):
                    m.qualifiers.append(q)
                    if not q.startswith(QUALIFIER_VERBS):
                        m.meta_problems.append(
                            f"qualifier {q!r} not one of {list(QUALIFIER_VERBS)} "
                            "(raw shell is not allowed)")
    return m


def parse_manifest_for_step(text: str, step_id: str) -> tuple[Manifest, bool]:
    """Build a Manifest from ONLY the plan-verify block(s) whose nearest-heading
    step id matches `step_id` (added 2026-07-10 for BUG-024 per-wave scoping).

    Returns `(manifest, matched)`. `matched` is False when no block in the plan
    resolves to `step_id` — the caller (diff_verify `--step`) treats that as a
    hard error rather than silently verdicting an EMPTY manifest (which would
    pass any diff and mask a mis-typed step id).

    Step-id resolution mirrors `iter_blocks`: the nearest preceding `#`-heading
    text, or `block-N` (1-based) when no heading precedes the block. A plan may
    (rarely) carry two blocks under the same heading — both are merged, matching
    how `parse_manifest` accumulates claims across a step's blocks.

    `step_id` may be given as (a) the exact heading text, (b) the `block-N`
    fallback id, or (c) a bare 1-based ordinal (`"1"`, `"2"`, …) — the last form
    matches the `.av-verify.json` contract's "text or numeric index". The
    numeric form matches by block ordinal regardless of heading text.
    """
    m = Manifest()
    matched = False
    want_ordinal: int | None = None
    if step_id.isdigit():
        want_ordinal = int(step_id)
    for idx, mo in enumerate(_BLOCK_RE.finditer(text), start=1):
        heading = _nearest_heading(text, mo.start())
        this_step = heading or f"block-{idx}"
        if not (this_step == step_id or (want_ordinal is not None and idx == want_ordinal)):
            continue
        matched = True
        claims, tier, tier_problems, gates, qualifiers, unknown_keys = _parse_block_body(mo.group(1))
        m.claims.extend(claims)
        if tier is not None:
            m.tiers.append(tier)
        m.meta_problems.extend(tier_problems)
        m.gates.extend(gates)
        for g in gates:
            if not g.startswith(GATE_PREFIXES):
                m.meta_problems.append(
                    f"gate {g!r} lacks a {'/'.join(GATE_PREFIXES)} prefix")
        m.qualifiers.extend(qualifiers)
        for q in qualifiers:
            if not q.startswith(QUALIFIER_VERBS):
                m.meta_problems.append(
                    f"qualifier {q!r} not one of {list(QUALIFIER_VERBS)} "
                    "(raw shell is not allowed)")
        for uk in unknown_keys:
            m.meta_problems.append(f"unknown manifest key: {uk!r}")
    return m, matched


def _parse_block_body(block_text: str) -> tuple[list[Claim], str | None,
                                                  list[str], list[str], list[str],
                                                  list[str]]:
    """Parse one plan-verify block's lines. Returns
    (claims, last_tier, tier_problems, gates, qualifiers, unknown_keys).

    Mirrors `parse_manifest`'s per-block behavior — claims accumulate; `tier:`
    collapses to the last value (None if absent); `gates:` and `qualifiers:`
    are per-block lists. Tier-problems are scoped to this block. Unknown keys
    (lines that look like `<key>:` but fail `_LINE_RE`) are captured in order
    for callers that surface them to the user.
    """
    claims: list[Claim] = []
    last_tier: str | None = None
    tier_problems: list[str] = []
    gates: list[str] = []
    qualifiers: list[str] = []
    unknown_keys: list[str] = []
    for line in block_text.splitlines():
        lm = _LINE_RE.match(line)
        if not lm:
            ak = _ANY_KEY_RE.match(line)
            if ak:
                unknown_keys.append(ak.group(1))
            continue
        key, val = lm.group(1), lm.group(2).strip()
        if key in ("touch", "new", "remove"):
            for raw in filter(None, (e.strip() for e in val.split(","))):
                c = parse_entry(key, raw)
                claims.append(c)
                # Relative-external detection lives here (not in parse_entry,
                # which stays pure). tier_problems is the per-block problems
                # channel (BlockRecord docstring: "any per-block meta problems").
                if raw.startswith("external:") and not c.external:
                    tier_problems.append(
                        "external: value must be an absolute path")
        elif key == "tier":
            last_tier = val
            if val not in VALID_TIERS:
                tier_problems.append(f"tier: {val!r} not in {sorted(VALID_TIERS)}")
        elif key == "gates":
            for g in filter(None, (e.strip() for e in val.split(","))):
                gates.append(g)
        elif key == "qualifiers":
            for q in filter(None, (e.strip() for e in val.split(";"))):
                qualifiers.append(q)
    return claims, last_tier, tier_problems, gates, qualifiers, unknown_keys


def _nearest_heading(text: str, block_start: int) -> str:
    """Walk backward from `block_start` to find the most recent `#`-prefixed
    heading line. Returns the heading text (with leading hashes + spaces
    stripped). Falls back to '' when no heading precedes the block.
    """
    prefix = text[:block_start]
    best: str | None = None
    for hm in _HEADING_RE.finditer(prefix):
        best = hm.group(2).strip()
    return best or ""


def iter_blocks(text: str) -> list[BlockRecord]:
    """Parse every `<!-- plan-verify -->` block in `text` and return one
    `BlockRecord` per block (in document order).

    The record's `step_id` is the nearest preceding heading text; if no
    heading precedes the block, the record uses `block-N` (1-based).
    The record's `files` list is the union of path-bearing claim entries
    (`touch`/`new`/`remove` with a `path`); symbol-only and bare-symbol
    entries are excluded (the consumer re-queries them via the codegraph
    DB if it needs symbol attribution).
    """
    out: list[BlockRecord] = []
    for idx, m in enumerate(_BLOCK_RE.finditer(text), start=1):
        body = m.group(1)
        claims, tier, tier_problems, gates, qualifiers, unknown_keys = _parse_block_body(body)
        # Preserve document order of the FIRST occurrence of each path; dedup
        # later duplicates (a path that appears under both `touch:` and
        # `new:` should not appear twice in the consumer's per-step record).
        seen: set[str] = set()
        files: list[str] = []
        for c in claims:
            # external claims stay in `claims` but their abs paths are
            # excluded from `files` — diff_verify per-step diff scoping is
            # repo-local; an abs path outside the tree has no meaning there.
            if c.external:
                continue
            if c.path and c.path not in seen:
                seen.add(c.path)
                files.append(c.path)
        heading = _nearest_heading(text, m.start())
        step_id = heading or f"block-{idx}"
        out.append(BlockRecord(
            step_id=step_id,
            block_index=idx,
            files=files,
            tier=tier,
            tier_problems=list(tier_problems),
            gates=list(gates),
            qualifiers=list(qualifiers),
            unknown_keys=list(unknown_keys),
        ))
    return out


def block_line_spans(text: str) -> list[tuple[int, int]]:
    """Return one 1-indexed `(start_line, end_line)` span per
    `<!-- plan-verify -->` block, in document order (added 2026-08-09
    for the falkor-writ checks that address block lines — C5 rescope,
    C10 BODYSYNC).

    A span runs from the block comment's opening line through its
    closing `-->` line, inclusive. The start line is the 1-indexed line
    of `m.start()`; the end line is the newline count up to `m.end()`
    — `_BLOCK_RE`'s trailing `\\s*$` consumes the newline terminating
    the `-->` line, so counting newlines before `m.end()` lands on the
    closing line. Spans pair 1:1 with `iter_blocks` records.
    """
    return [(text.count("\n", 0, m.start()) + 1,
             text.count("\n", 0, m.end()))
            for m in _BLOCK_RE.finditer(text)]
