# ADR 0001 — Reuse P1's recipe by sibling import; defer `_shared/` to Phase B

## Status

Accepted (2026-07-04).

> **UPDATE 2026-07-09 (doc-sweep):** the `_shared/` extraction this ADR
> *deferred* to Phase B has since SHIPPED — commit `82287f9` ("plan-verifier +
> diff-verifier + _shared extraction") landed `_shared/db.py`, `sig.py`,
> `resolve.py`, `queries.py`, `budget.py`, `hookio.py`, `manifest.py` at the repo
> root, and `decision_index.py:44-57` now imports `_shared.db`/`resolve`/`sig`.
> The "defer to Phase B" portion of the 2026-07-04 decision is therefore
> SUPERSEDED in effect (phase B cutover happened, via the second-consumer rule,
> when plan-verifier needed the resolver+signature code). The sibling-import
> seam this ADR primarily establishes (`import decision_index as di`) remains
> the live pattern for P3/P4/P5 tools. This note records the divergence per
> DOC-SYNC-001; the original decision text below is left unchanged as a
> historical record.

## Context

The ssot-diagram pipeline has three phases of shared plumbing. Phase 1 (P1)
shipped `decision_index.py` — the engine that opens the codegraph SQLite DB
read-only, guards its schema, and computes the content-signature recipe (file
hash, symbol slice hash, component hash) plus the decision-anchor staleness
helpers (`current_sig`, `anchor_status`, `_evaluate`). Phase 3 (P3) is the
diagram-model extractor (`graph_model.py`) and needs exactly that same DB /
signature / resolve recipe to build `diagram-model.json`.

The clean place for shared plumbing is a `_shared/` library (Block 1 of
`../docs/roadmap/skeleton-contracts.md`). But right now only the design exists on
disk — there is no `_shared/db.py`, no `_shared/sig.py`. The contract explicitly
schedules the lift-and-cutover as a separate "Phase B" task: "decision_index.py
refactors to import `_shared/` via clean cutover — no back-compat aliases; its
existing tests must pass unchanged (Phase B)." A second caller (P3) now needs the
recipe before Phase B has happened.

So the situation is: P3 must get the recipe from somewhere before the shared
library exists. Three sources were on the table — import P1 as a sibling, copy
the recipe inline, or do the Phase B extraction now.

There is already repo precedent for the sibling-import move:
`ssot-diagram/decision_hook.py` (lines 22-23) does exactly
`sys.path.insert(0, str(Path(__file__).resolve().parent)); import decision_index as di`
to reuse P1's helpers from the same directory. P3 sits in the same directory and
can mirror that pattern verbatim.

## Decision

P3's `ssot-diagram/graph_model.py` imports `decision_index` as a sibling module
and reuses P1's DB / signature / resolve / staleness recipe verbatim, rather
than copying the recipe inline or extracting `_shared/` in this phase.

The import mirrors the established `decision_hook.py` precedent:

```
sys.path.insert(0, str(Path(__file__).resolve().parent))
import decision_index as di
```

The recipe P3 reuses from P1 (the load-bearing set, all in
`ssot-diagram/decision_index.py`):

- `find_db` — walk up to locate `.codegraph/codegraph.db`
- `open_db` — read-only connect (`mode=ro&immutable=1`)
- `verify_schema` — fail-loud guard against codegraph schema drift
- `file_content_hash` — file signature from `files.content_hash`
- `symbol_spans` — source-slice extent for a `(qualified_name, file_path)` lookup
- `slice_hash` — sha256 of a symbol's source lines (content, not line numbers)
- `parse_ref` — split an anchor ref into `('file', path)` or `('sym', name, path)`
- `current_sig` — live signature + state (`OK`/`ORPHANED`/`AMBIGUOUS`)
- `anchor_status` — `FRESH`/`STALE`/`ORPHANED`/`AMBIGUOUS` per anchor
- `load_index` — fail-loud loader for the curated decision index
- `_evaluate` — walk every anchor, return rows + a not-fresh count (the
  pre-extract guard calls this; reaching the leading-underscore symbol is
  acceptable because P3 imports P1 as a sibling, the same move the hook makes)

P3's own code is limited to what is genuinely new: component grouping (reads
`ssot-diagram.config.json`), micro selection (file vs dominant class), the nano
cap + collapse, edge roll-up with stable sample selection, decision-node merge,
model id synthesis, and byte-deterministic JSON serialization.

## Alternatives Considered

### Option B — Copy the recipe inline into `graph_model.py`

Carry a private duplicate of `find_db`, `open_db`, `verify_schema`,
`file_content_hash`, `symbol_spans`, `slice_hash`, `parse_ref`, `current_sig`,
`anchor_status`. Zero cross-file coupling; P1 can change without touching P3.

Rejected: a future edit to `slice_hash` in P1 (e.g. normalizing line endings)
that is not mirrored in P3 produces different signatures for the same symbol,
silently breaking the Block 5b trust rule (a P4 narrative pinned to P3's
signature would not match P1's staleness check). A shared test asserting P3 and
P1 produce the same signature for the same anchor would catch the drift — but
that test is itself a coupling, which defeats the isolation Option B buys.

### Option C — Extract `_shared/` now, P1 + P3 both import it

Do the Block 1 "Phase B" clean cutover inside P3: lift the recipe into
`_shared/db.py` + `_shared/sig.py`, rewire `decision_index.py` and
`decision_hook.py` to import from there, then P3 imports the same. One copy of
the recipe machine-wide.

Rejected: CLAUDE.md §3 (Scope Discipline — "Touch only what the request
requires") forbids folding a refactor of shipped code into P3's delivery. The
contract itself scopes the clean cutover to "Phase B" as a separate task, and a
clean cutover with no back-compat aliases can break P1's tests in subtle ways
(import path, `sys.path` derivation). Doing it here couples P3's delivery to P1's
test suite passing unchanged — a coupling neither P3 nor P1 asked for.

## Consequences

Positive:

- One copy of the signature recipe — no silent drift between P1 and P3 on the
  Block 5b trust rule (P4 narratives pin to the same hash P1's staleness check
  compares against).
- Lowest blast radius — P3 ships without editing shipped P1 (`decision_index.py`
  is a read dependency, no edit; `manifest.json` grows one entry and nothing
  else).
- P3's risk concentrates where it should — in component grouping, edge roll-up,
  and stable ordering, not in re-implementing DB plumbing.

Negative:

- Second-caller coupling: P3 is now a second caller of P1 internals
  (`di.current_sig` / `di.anchor_status` / `di._evaluate`). Any signature change
  in P1's recipe must update two callers until Phase B lands. Mitigation: P1's
  tests and P3's tests both guard the recipe, and the contract schedules the
  `_shared/` cutover as a clean, single-shot update.
- `sys.path` mutation is fragile if the file is moved. Mitigation:
  `decision_hook.py:22` established this exact pattern and it is now the repo
  convention; P3 mirrors it verbatim.
- The Phase B cutover now has a known consolidation target set (enumerated
  below) — Phase B must update three callers (P1, the hook, P3), not two.

### Phase B consolidation targets

When Phase B lands, the `_shared/` cutover must lift exactly these symbols out of
`decision_index.py` (the set P3 reuses by sibling import today). This list is the
ADR's bonus value: Phase B has a checklist.

| Symbol | `decision_index.py` line |
|---|---|
| `find_db` | 53 |
| `open_db` | 73 |
| `verify_schema` | 85 |
| `file_content_hash` | 96 |
| `symbol_spans` | 101 |
| `slice_hash` | 115 |
| `parse_ref` | 125 |
| `current_sig` | 136 |
| `anchor_status` | 154 |
| `load_index` | 163 |
| `_evaluate` | 290 |

Phase B then rewires `decision_index.py`, `decision_hook.py`, and
`graph_model.py` to import from `_shared/` (clean cutover per Block 1 note — no
back-compat aliases).

## References

- Design doc: `ai-artifacts/1_design/p3-diagram-model-extractor.md`
  (Option A chosen; Option B/C rejected; OQ-ADR-1 resolved "write the ADR")
- Contract: `../docs/roadmap/skeleton-contracts.md` Block 1 (the `_shared/`
  extraction scheduled as "Phase B" clean cutover) and Block 5b (the trust rule
  that signatures must match — the reason Option B's drift is fatal)
- Sibling-import precedent: `ssot-diagram/decision_hook.py` lines 22-23
  (`sys.path.insert(0, str(Path(__file__).resolve().parent)); import decision_index as di`)
- Recipe source: `ssot-diagram/decision_index.py`
