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
QUALIFIER_VERBS = ("grep-absent", "byte-unchanged", "diff-only-within")

_BLOCK_RE = re.compile(r"^<!--\s*plan-verify\s*$(.*?)^-->\s*$",
                       re.MULTILINE | re.DOTALL)
_LINE_RE = re.compile(r"^\s*(touch|new|remove|tier|gates|qualifiers)\s*:\s*(.*)$")
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


def looks_pathish(token: str) -> bool:
    return bool(_PATHISH_HINT.match(token)) or "/" in token


def parse_entry(intent: str, raw: str) -> Claim:
    raw = raw.strip()
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
                continue
            key, val = lm.group(1), lm.group(2).strip()
            if key in ("touch", "new", "remove"):
                for raw in filter(None, (e.strip() for e in val.split(","))):
                    m.claims.append(parse_entry(key, raw))
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


def _parse_block_body(block_text: str) -> tuple[list[Claim], str | None,
                                                  list[str], list[str], list[str]]:
    """Parse one plan-verify block's lines. Returns
    (claims, last_tier, tier_problems, gates, qualifiers).

    Mirrors `parse_manifest`'s per-block behavior — claims accumulate; `tier:`
    collapses to the last value (None if absent); `gates:` and `qualifiers:`
    are per-block lists. Tier-problems are scoped to this block.
    """
    claims: list[Claim] = []
    last_tier: str | None = None
    tier_problems: list[str] = []
    gates: list[str] = []
    qualifiers: list[str] = []
    for line in block_text.splitlines():
        lm = _LINE_RE.match(line)
        if not lm:
            continue
        key, val = lm.group(1), lm.group(2).strip()
        if key in ("touch", "new", "remove"):
            for raw in filter(None, (e.strip() for e in val.split(","))):
                claims.append(parse_entry(key, raw))
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
    return claims, last_tier, tier_problems, gates, qualifiers


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
        claims, tier, tier_problems, gates, qualifiers = _parse_block_body(body)
        # Preserve document order of the FIRST occurrence of each path; dedup
        # later duplicates (a path that appears under both `touch:` and
        # `new:` should not appear twice in the consumer's per-step record).
        seen: set[str] = set()
        files: list[str] = []
        for c in claims:
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
        ))
    return out
