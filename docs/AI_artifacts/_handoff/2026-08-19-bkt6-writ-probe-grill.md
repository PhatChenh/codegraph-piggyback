# Solution map — Bucket 6 writ probe + init wrapper (design grill)
_Date:_ 2026-08-19  
_Posture:_ design (in-pipeline; split forbidden)  
_Parent:_ `docs/AI_artifacts/_scope/2026-08-16-feedback-bugs-scope.md`  
_Status:_ **LOCKED** 2026-08-19 (owner compact reply) · **C1-a amendment** 2026-08-19 (big-RT)

## Shape (plain)

When this bucket ships:

1. Writ’s index health-check has four honest names: **missing** (no db file), **unreadable** (file exists but sqlite connect/select fails, or the version table is absent), **unrecognized** (a real integer version outside `{1, 5}`), **usable** (unchanged).
2. A smashed or locked file is **not** reported as “unknown schema, found none.” That lie is what this session saw on falkor-writ Reads.
3. `freshness()` keeps `unreadable` as `unreadable`. It does not fold it into `unrecognized`.
4. Unreadable is never treated as usable (edits stay blocked until the map is actually readable).
5. `writ codegraph-init` runs `codegraph init` (Bucket 4 already unlinks+rebuilds junk). **No post-init `codegraph index` retry** (C1-a: that command cannot repair junk/schema-less; live index exit 1, init exit 0).
6. If probe still not usable after init: **exit nonzero**, leave the greenfield marker, tell the operator the file is junk. **Never delete** `.codegraph/codegraph.db`. `chmod`/cannot-open: neither CLI repairs; operator fixes permissions by hand.
7. Block-messages split: no file **and** unreadable → `writ codegraph-init`; real unknown version → both version sets + wrapper. Same strings on Claude and Cursor (one script). **Not** `codegraph index` for unreadable (C1-a).
8. Marker still deleted only when probe is usable.
9. Short ADR in falkor-writ next to the probe: why unreadable ≠ unrecognized, and why we still don’t auto-delete.
10. piggyback **TD-01 stays OPEN** (native init-finished signal still missing). Wrapper does **not** add an `index` retry; Bucket 4 `init` is the repair. Native plugin bus stays parked.

Code home: **falkor-writ**. Pipeline artifacts: **piggyback** `docs/AI_artifacts/`. One contract surface: `probe()` + its four consumers. No settings/hooks.json edit. R15: same wrapper + same `probe()`; deny copy is command text, not a Claude-only event.

## Owner locks this grill

| ID | Lock |
|---|---|
| 0-a | Adopt inherited IN/OUT/freezes |
| 1-a | **SUPERSEDED C1-a:** no post-init `index` retry. Init is the repair. Still-bad → fail honest, marker left, no loop |
| 2-a | Three deny/audit messages. **C1-a:** unreadable names `writ codegraph-init`, not `codegraph index` |
| C1-a | 2026-08-19 big-RT: keep fourth name; unreadable → `writ codegraph-init`; drop index retry |
| 3-a | TD-01 stays OPEN; wrapper does **not** add an `index` retry (C1-a). Bucket 4 `init` is the repair |
| 4-a | ADR in falkor-writ with the impl |
| C1 | Never auto-delete `.codegraph/codegraph.db` |

## Away / run locks

| ID | Lock |
|---|---|
| Away | D1–D8 ACCEPTED 2026-08-19 |
| R1-a | New labeled daemon `orch-bkt6-writ-probe`. Do not hijack `:19831` / `:19391`. Never `:8877`. Do not stop `:19641`. |
| R2 | Design `claude-opus` via av. **RT / spec / plan / FCV** = harness Task `cursor-grok-4.6-high` (supersedes earlier “FCV-only harness”). Gather `clx-deepseek-v4-flash` via av. Judge `syn-kimi-k3` via av. ORCH this Cursor grok 4.6 session. Spec = fresh Task; FCV+plan share one Task; big RT = fresh Task each round. Band-2 design = `syn-3-kimi-k3` ≠ judge SID. |
| R3-a | opus usage-limit → design `syn-3-kimi-k3` immediately; do not wait/retry that Claude-login seat |
| R4-a | Tests in falkor-writ + one live `writ codegraph-init` on a fixture (not a full huge-repo rebuild in this design→plan run) |
| R5-a | Design/spec/plan/FCV artifacts in piggyback `docs/AI_artifacts/`. Code edits later in falkor-writ. |

## Frozen from scope (not reopened)

- Probe enum `{missing, unreadable, unrecognized, usable}`.
- Connect/select failure or missing `schema_versions` → `unreadable`, never `unrecognized` with `found=frozenset()`.
- `unrecognized` stays for a real integer version outside `{1, 5}`.
- `missing` = db file absent. `usable` unchanged.
- Fail-closed: unreadable is never usable.
- Marker deleted only on `usable`.
- OUT: Write-gate auto-index; change `KNOWN_SCHEMA_VERSIONS`; piggyback probe clone; MCP `tools/list` (Bucket 5); plugin bus; `.codegraph/ready`.

## Alternatives dropped

- Exit 0 when still unusable after index — looks like success; next edit still dies.
- Wrapper deletes the db — one-way; C1 forbids.
- Loop `index` until usable — can hang.
- Every bad state names `codegraph index` — wrong first step when the file is missing.
- Close TD-01 — would hide the still-missing native hook.
- Skip the ADR — next session re-litigates the names.

## Risks accepted

- One `index` can take minutes on a large tree (fixture live-check, not a huge-repo rebuild, in this pipeline run).
- Path-only OK from Bucket 3 is unrelated and stays.
- Cursor Read WARN stays Claude-only (declared loss); this bucket does not add it.

## Open questions remaining

None for this grill. Return-shape of `probe()` (`str` vs tuple), exact deny strings, and how `freshness()` grows the fifth member are **craft for design**.

## Parked vs cut

| Item | Tag |
|---|---|
| Write-gate auto-index | **NEVER IN ORIGINAL SCOPE** (Q1-a rejected) |
| MCP missing/empty | **PLANNED** in Bucket 5 |
| Native plugin/event bus | **THIS FEATURE, later re-grill** (TD-01) |
| `.codegraph/ready` | **NEVER IN ORIGINAL SCOPE** (Q5-a) |
| piggyback probe clone | **NEVER IN ORIGINAL SCOPE** |
| Change `KNOWN_SCHEMA_VERSIONS` | **NEVER IN ORIGINAL SCOPE** |
| Bucket 4 CLI init repair | **DONE** |
| Auto-delete smashed db | **CUT** (C1) |

Nothing else was **CUT**.

## Expert still doesn’t like

FULL PIPE for a small probe change is heavy process, but today’s failure is silently the wrong diagnosis — that is why the tier exists. Do not demote at pickup.

## ADR / CONTEXT / object-map

- ADR: **write with the impl** in falkor-writ (all three gates true).
- CONTEXT.md: **no write** (scope: writ CONTEXT is FalkorDB terms; enum lives in freeze + `probe()` docstring).
- Object-map: no hit.
