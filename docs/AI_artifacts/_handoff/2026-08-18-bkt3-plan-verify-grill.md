# Solution map — Bucket 3 plan_verify disk-stat + REUSE (design grill)
_Date:_ 2026-08-18  
_Posture:_ design (in-pipeline; split forbidden)  
_Parent:_ `docs/AI_artifacts/_scope/2026-08-16-feedback-bugs-scope.md`  
_Status:_ **LOCKED** 2026-08-18 (owner compact reply)

## Shape (plain)

When this bucket ships:

1. A plan claim that names **only a file** (`touch: hooks.json`, `touch: prisma/schema.prisma`) is **not MISSING** if that path is a **regular file** on disk under the indexed repo root, even when the code index never listed it. Evidence string: **`on disk, not in index`**. `--strict` does not fail that row.
2. The same file, named **with a symbol** (`touch: prisma/schema.prisma::Asset`), stays **MISSING** if the index has no `Asset`. File-on-disk does not launder a ghost function.
3. `new:` of a path-only file that already exists on disk is **COLLISION** (the index being empty is not “create me”).
4. `remove:` of a path-only file that exists on disk is **OK** with the same honest evidence. No fake BLOCKED (index has no callers for unparsed files). Genuinely absent path stays MISSING / `--strict` fail.
5. Folders are not “exists.” `touch: prisma/` stays MISSING unless a regular file is named.
6. Spec reuse names: strip `(...)`, unicode `…`, ASCII `...`, take the identifier before `(`. Plan `runFalQueue` matches spec `runFalQueue(...)`. REUSE-DROPPED stays warn-only (`--strict` never fails it).
7. Write a short ADR with the implementation: why on-disk path-only is OK, not a ghost.

Home: this repo. One surface: `plan-verifier/plan_verify.py`. Stat root = parent of `.codegraph/` (same as the index). R15: one CLI; both harnesses consume it. No settings/hooks edit.

## Owner locks this grill

| ID | Lock |
|---|---|
| 0-a | Adopt inherited IN/OUT/freezes |
| 1-a | Path-only `new:` + file on disk → COLLISION |
| 2-a | Regular files only (`is_file`); directories stay MISSING |
| 3-a | Path-only `remove:` + file on disk → OK + `on disk, not in index` |
| 4-a | Also strip ASCII `...` |
| 5-a | Write MISSING-freeze ADR with the impl |
| C1 | Evidence text exactly `on disk, not in index` |

## Frozen from scope (not reopened)

- Path-only on-disk → not MISSING; `::Symbol` still needs the index.
- REUSE identifier-normalize only; never `--strict` fail.
- No new verdict enum / no new STRICT_FAILS member.
- OUT: Prisma/markdown extractors; REUSE relocation via DB; swept-prose flood; treating `path::Symbol` as OK because the file exists.

## Alternatives dropped

- Leave `new:` index-only — silent “create what already exists.”
- Count directories as present — freeze said file; accidental folder claims would pass.
- Leave `remove:` index-only — delete-a-docs-file plans still fail `--strict`.
- Unicode `…` only — US-keyboard `...` is the same decoration.
- Skip the ADR — next session re-litigates the honesty rule.
- New verdict name (`UNINDEXED`) — freeze forbids a new STRICT_FAILS member.

## Risks accepted

- Path-only OK skips blast-radius for files the index never parsed (scope pre-mortem).
- A plan that means “recreate this file” must say `touch:`, not `new:`.
- Swept claims unchanged (still never fail `--strict`).

## Open questions remaining

None for this grill. How to `stat` (relative path join, missing repo root) is craft for design.

## Parked vs cut

| Item | Tag |
|---|---|
| Prisma/markdown extractors | **NEVER IN ORIGINAL SCOPE** (Q4-a) |
| REUSE CodeGraph relocation | **NEVER IN ORIGINAL SCOPE** (Q6-a rejected c) |
| Swept-prose flood | **NEVER IN ORIGINAL SCOPE** |
| New STRICT_FAILS member | **NEVER IN ORIGINAL SCOPE** |
| MCP missing/empty | **PLANNED** in Bucket 5 |
| writ `probe()` + init wrapper | **PLANNED** in Bucket 6 |
| TD-01 native init hook | **THIS FEATURE, later re-grill** |
| grep-absent 0 files | **DONE** in Bucket 2 |
| CLI refuse `${…}` + init repair | **DONE** in Bucket 4 |

Nothing was **CUT**.

## Expert still doesn’t like

LIGHT for a checker that other pipelines consume is still right: one file, obvious contract, failure mode is loud (`--strict`), not silent. Do not fold Bucket 6 into this run.

## ADR / CONTEXT / object-map

- ADR: **write** (5-a) with impl. Path is craft (tool-local vs `docs/architecture/`).
- CONTEXT.md: no write (tooling terms, not a product glossary).
- Object-map: no hit.

## Away + seats (same compact reply)

- Away defaults **D1–D8 ACCEPTED** 2026-08-18. No deltas.
- R1-a: new labeled daemon `orch-bkt3-plan-verify` (never `:8877`; do not steal `p19-lite-part3-orch` `:19641`).
- R2: design `claude-opus`/`av`; RT/spec/plan/FCV grok 4.6 harness Task (`cursor-grok-4.6-high`); other `clx-deepseek-v4-flash`/`av`; judge `syn-kimi-k3`/`av` persistent. I9 this run: harness grok = RT+spec+plan+FCV, not review-only.
- R3: band-2 design fallback **`syn-kimi-k3`** (owner override vs opus-4-6). Same model as judge; **separate SID**; warn recorded.
- R4-a: no spend cap.
