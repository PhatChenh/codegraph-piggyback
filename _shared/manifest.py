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
