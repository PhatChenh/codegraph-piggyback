# Frozen cross-phase contracts — codegraph-piggyback

> Output of /architecture-grill (2026-07-03). These are the seams later phases
> import; do not silently redesign. Everything NOT here stays WHAT-level and is
> decided per-phase by /build-pipeline. Each block states what is FROZEN vs
> PENDING (safe to fill later without breaking importers).

## Block 1 — `_shared/` library + delivery rail

**Imported by:** every phase from B onward (plan-verifier, plan-visualizer,
changeset-context, drift-digest, biography, repo-map, hygiene tools).

### Decisions

**1a. Resolver seam (FROZEN).** `_shared/resolve.py` exposes the lookup core
ONLY:

```
resolve(name, file_hint=None) -> UniqueNode | AMBIGUOUS(candidates) | UNRESOLVED
```

- Never guesses: >1 match → AMBIGUOUS with candidate list; 0 → UNRESOLVED.
- Notation parsing (`qname@path` decision anchors, `path::symbol` plan manifests,
  backticked prose tokens) stays PER-TOOL — each tool converts its notation into
  a `resolve()` call. A new tool's notation can never change what shipped tools
  resolve.
- Rationale: verdict honesty is the shared currency and lives in the core;
  notation is surface syntax that legitimately differs per document type.

**1b. Distribution model (FROZEN).**
- Scripts run **in place** from this checkout; hooks in consumer repos point at
  absolute ($HOME-portable) paths (existing `piggyback.py` behavior, verified
  2026-07-03 — no copying exists and none is added).
- Tools import `_shared/` by **file-relative path from their own location**
  (repo root on `sys.path` derived from `__file__`), never from cwd.
- Consequence: one copy of every module, machine-wide; `piggyback update`
  (git pull) rolls out everywhere at once.

**1c. Wiring policy (FROZEN).**
- `piggyback init` and `update` are **picker-curated per repo**: new tools are
  OFFERED, never silently wired. Picker choices are recorded per repo so
  `update` can distinguish "declined" from "never seen".
- PENDING: storage location/shape of the per-repo choice record (rail-upgrade
  phase decides; likely `.claude/piggyback.json`).

**1d. Rail architecture (FROZEN as-is + upgrade phase).** Keep
checkout-in-place + `manifest.json` + reconciler. No packaging, no versioning,
no symlinks — single publisher = single consumer. Three upgrades scheduled as a
small roadmap phase (roadmap Phase I): durable per-repo picker record ·
`status` shows wired/available/new per repo · post-pull sanity check (manifest
+ optional per-script `--selfcheck`), warn-only.

**1e. Module invariants (FROZEN — restated from `_shared/design.md`).**
- `db.py`: read-only connect (`mode=ro&immutable=1`), schema guard fails loudly.
- `sig.py`: file = `files.content_hash`; symbol = sha256 of source slice;
  component = sha256 over member hashes. Content-based, never ids/line numbers.
- `queries.py`: pure functions of the DB.
- `budget.py`: output never exceeds budget; overflow collapses to counts.
- `hookio.py`: silent on no-signal; never raises into the session.

**Decision-log note (not contract):** `decision_index.py` refactors to import
`_shared/` via clean cutover — no back-compat aliases; its existing tests must
pass unchanged (Phase B).

## Block 2 — plan-verify manifest syntax

**Produced by:** planner agents/templates (Phase B onward). **Imported by:**
plan-verifier (Phase B), plan-visualizer (Phase D), workflow-guardrails
run-reports (cross-project).

### Decisions

**2a. Syntax (FROZEN, verbatim from `plan-verifier/design.md`):**

```markdown
<!-- plan-verify
touch: src/auth.py::validate_token, src/db.py::get_conn
new:   src/auth.py::refresh_token
remove: src/auth.py::legacy_check
-->
```

- Opens with `<!-- plan-verify` on its own line, closes with `-->`.
- Three line kinds: `touch:` / `new:` / `remove:`, comma-separated lists.
- Entry forms: `path::symbol` · bare `path` · bare `symbol` (repo-wide,
  AMBIGUOUS-prone). Multiple blocks per document allowed; lists concatenate.

**2b. Change control (FROZEN):** syntax changes require checking both
downstream consumers (plan-visualizer chips, workflow-guardrails ledger
parsing) — it is a public contract shared across repos.

**2c. Authoring duty (FROZEN):** plan templates used by /build-pipeline and
writ/reasonix planners must emit this block; a plan without it gets only the
lower-confidence heuristic sweep.

## Block 3 — plan-verifier verdict contract

**Imported by:** plan-visualizer (Phase D warning chips), /build-pipeline
strict gate, workflow-guardrails run-report ledgers (cross-project).

### Decisions

**3a. Verdict vocabulary (FROZEN):** `OK · MISSING · AMBIGUOUS · COLLISION ·
BLOCKED · UNACKNOWLEDGED-BLAST` — exactly these, per the design.md verdict
table. Swept (prose-heuristic) claims are touch-class only: they may produce
MISSING / AMBIGUOUS / UNACKNOWLEDGED-BLAST, never COLLISION or BLOCKED.

**3b. Gate semantics (FROZEN, decided 2026-07-03):**
- Default: advisory, exit 0 always.
- `--strict`: exit 1 on any MISSING / COLLISION / BLOCKED.
- AMBIGUOUS: **warn-only even in strict** — repos legitimately reuse names;
  the ghost case already hard-fails as MISSING. Tightening later is cheap;
  loosening a distrusted gate is not.
- UNACKNOWLEDGED-BLAST: warn-only, triggers at **≥ 6 callers** (impact-analyzer
  HIGH tier) with zero callers named anywhere in the plan text. Threshold is
  config, not contract — may be raised if real plans prove noisy.

**3c. Evidence duty (FROZEN):** every row carries evidence — resolved
`file:line` for existence verdicts, caller count + top caller locations for
blast verdicts. A verdict without evidence is a bug, not a style choice.

## Block 4 — `diagram-model.json` public surface

**Produced by:** ssot P3 extractor (Phase A). **Imported by:** ssot P5 renderer
(Phase C), plan-visualizer (Phase D), narratives worklist (Phase C/P4).

### Decisions

**4a. Hierarchy (FROZEN):** exactly three levels — component → file (or
dominant class) → function/method. No fourth level, no flat mode.

**4b. Node fields importers may rely on (FROZEN):** deterministic `id` derived
from path/qualified name (same code ⇒ same id across runs — narratives and
plan-visualizer key on it), `kind`, `name`, `path`, content `signature` (Block
1e recipes; what P4 pins prose to).

**4c. Edges (FROZEN):** rolled up per level, directional, carry counts.
Plan-visualizer reads one-hop callers from these rolled-up edges — it never
opens the DB.

**4d. Decision nodes (FROZEN):** each verified decision attaches to the
component/file owning its anchors and carries live status
(FRESH/STALE/ORPHANED/superseded).

**4e. Resolvability (FROZEN):** a `path::symbol` manifest entry (Block 2) must
resolve to a model node via the Block 1a resolver discipline (honest
AMBIGUOUS/UNRESOLVED).

**PENDING (P3 build decides):** full field list, layout hints, nano-cap
("+K more") encoding, `ssot-diagram.config.json` schema, unknown-path
component placement.

## Block 5 — `narratives.json` entry shape

**Produced by:** ssot P4 (Phase C). **Imported by:** P5 renderer (Phase C),
biography (Phase F).

### Decisions

**5a. Entry (FROZEN, verbatim from ssot roadmap):**
`{node_id, signature, text, status: proposed|approved|stale}`.

**5b. Trust rule (FROZEN):** nothing renders/quotes as trusted prose unless
`approved` AND signature matches current model; stale is shown as visibly
stale, never silently as current. Biography obeys the same rule when quoting
narratives.

**PENDING:** worklist format, approval CLI flags (P4 build decides).
