# Solution map — Bucket 5 codegraph MCP missing vs empty (design grill)
_Date:_ 2026-08-19  
_Posture:_ design (in-pipeline; split forbidden)  
_Parent:_ `docs/AI_artifacts/_scope/2026-08-16-feedback-bugs-scope.md`  
_Status:_ **LOCKED** 2026-08-19 (owner compact reply)

## Shape (plain)

When this bucket ships:

1. The coding agent’s first look at CodeGraph tells the truth: **missing** (no db) vs **empty** (db exists, 0 symbols) vs **usable** (has symbols).
2. **Missing** → empty tool list + short “inactive” note. Absence is the signal. Agent uses Read/Grep. Does **not** run `codegraph init` itself.
3. **Empty** → tools may stay listed (freeze: empty list is missing-only) but **not** the full playbook. Short text: user runs `codegraph init` (Bucket 4 already indexes; do **not** say stale `init -i`).
4. **Junk / unclassified** (file exists, sqlite cannot name a healthy index) → **missing** behavior. Bucket 4 `init` is the repair.
5. **Busy** (index locked, errcode 5) → **empty-style**: tools stay, short “busy, retry later.” Not a fourth MCP name.
6. Handshake still answers fast (`#172`): cheap COUNT via existing `probeIndexHealth` **before** the initialize reply; heavy engine/WASM stays in the background.
7. MCP **imports** `probeIndexHealth` and **maps** CLI 5-arm → MCP 3-arm. `isInitialized` stays “files exist.” No third public enum on the library barrel.
8. **Both doors:** in-process `session.ts` **and** daemon `proxy.ts`. Same payloads. Proxy today always sends the full playbook + full tools — that is the live lie.
9. Recoverable states stay SUCCESS-shaped (`isError` still only for real stop-trying).
10. piggyback **TD-01 stays OPEN**. No plugin bus. No `.codegraph/ready`. Writ probe is Bucket 6.

Code home: **`codegraph/` fork**. Pipeline artifacts: **piggyback** `docs/AI_artifacts/`. One contract surface: MCP `initialize` instructions + `tools/list` (+ matching `NotIndexedError` / late emptyWarn copy). R15: shared MCP binary; no per-harness settings.json / hooks.json edit.

## Owner locks this grill

| ID | Lock |
|---|---|
| 0-a | Adopt inherited IN/OUT/freezes |
| 1-a | Junk/unclassified → missing; busy → empty-style; no fourth MCP name |
| 2-a | Cheap COUNT before handshake reply; heavy init stays background |
| 3-a | Import `probeIndexHealth`, map 5→3; do not change `isInitialized` |
| 4-a | Same contract on `session.ts` **and** `proxy.ts` |
| 5-a | Missing and empty: short copy; user runs `codegraph init`; agent does not self-init |
| C1-a | Stay one pipeline. A-split only if FCV proves `engine.ts` + idle-kill are a **different** contract (not Q4-a) |
| C2-a | TD-01 stays OPEN |

## Away / run locks

| ID | Lock |
|---|---|
| Away | D1–D8 ACCEPTED 2026-08-19 |
| R1-a | New labeled daemon `orch-bkt5-codegraph-mcp` `:19851`. Do not hijack `:19841` / `:19831` / `:19391`. Never `:8877`. Do not stop `:19641`. |
| R2 | **Band-2 design** = harness Task `cursor-grok-4.6-high` (owner override; expands the harness exception). Same-model warn vs RT at that band. Until band-2, design stays `syn-3-kimi-k3` via av. |
| R3-a | opus judge usage-limit → `syn-kimi-k3` via av immediately; fresh SID ≠ design SID. Do not wait/retry that Claude-login seat. Same-family warn vs design Kimi. |
| R4-a | Tests: missing, 0-node, junk (+ busy copy). **Live = vitest spawn of `serve --mcp`** (extend `mcp-initialize` / add proxy spawn) — implementer-run. ORCH does **not** personally drive a second village-style live cert. |
| R5-a | Design/spec/plan/FCV artifacts in piggyback `docs/AI_artifacts/`. Code edits later in `codegraph/`. |

## Frozen from scope (not reopened)

- MCP tri-state `index_missing` / `index_empty` / usable.
- Recoverable ≠ `isError`.
- Empty `tools/list` only for missing, not for empty-db.
- Empty-db must not look like a full indexed project.
- OUT: CLI init (Bucket 4); writ probe (Bucket 6); empty → `isError`; plugin bus; `.codegraph/ready`; npm upgrade; installer `cursor.ts`.

## ORCH-burden recheck (owner ask 2026-08-19)

Two different “ORCH”s:

1. **This pipeline conductor** (this Cursor thread + village). Cost is design→RT→FCV covering two doors and a mapper.
2. **Future coding-agent sessions** (the daily pain). Empty-db that looks indexed wastes retries then abandonment.

| Pick | This-run conductor | Future agent sessions | Cheaper alternative that still fixes the live lie? |
|---|---|---|---|
| 0-a adopt box | none | none | Re-scope would add a grill, not remove one |
| 1-a junk→missing, busy→retry | mapper tests | busy = one retry (tiny). Junk no longer looks indexed | Fold busy into missing: **less** future retry, **worse** during a real `index` (agent abandons for a lock). Keep 1-a |
| 2-a COUNT at handshake | keep `#172` speed test | first paragraph honest | Existence-only handshake: **less** this-run risk, **does not** fix initialize text. Keep 2-a |
| 3-a import+map | mapping table in FCV | one thermometer | Duplicate COUNT: two probes drift. Global `isInitialized` change: CLI blast. Keep 3-a |
| **4-a session+proxy** | **the extra this-run work** (FCV both doors) | **the actual live fix** (daemon proxy is what Cursor/Claude hit) | Session-only: cheaper this run, **live daemon still lies**. `CODEGRAPH_NO_DAEMON=1` in every MCP config: owner ops forever, still need session.ts. **No fix without touching proxy.** Keep 4-a; gatherer reads proxy, ORCH does not survey it in this thread |
| 5-a user runs `init` | none | agent stays off self-init (already the rule) | Agent self-init: surprise minutes. Keep 5-a |
| R4-a tests+live | was a second ORCH-driven spawn | proof | **Narrowed (craft, still R4-a):** live = vitest spawn already in `mcp-initialize.test.ts` + proxy spawn. No extra conductor-operated cert |
| R2 harness grok band-2 | only if band-2 fires | n/a | av `cursor-grok-46` would be a second grok path; owner kept harness-only exception |

**Verdict:** nothing selected adds a new **owner** chore (still one `codegraph init` when they want the map). Nothing selected adds a new **future-agent** chore except busy-retry, which is cheaper than abandonment. The only this-run extra is Q4-a, and **no other solution fixes the daemon waiters without that door.** Skipping this FULL pipeline (QUICK session.ts only) would leave the lie you actually see.

## Alternatives dropped

- Session-only (Q4-b) — daemon proxy still lies.
- Handshake existence-only (Q2-b) — full playbook on hollow db.
- Fourth MCP name — freeze break.
- Health-aware `isInitialized` — CLI `uninit`/`init` blast; Bucket 4 rejected.
- Duplicate MCP COUNT — two sqlite probes.
- Agent runs `init` — scope rejected; operating surprise.
- Close TD-01 / plugin bus / `.codegraph/ready` — OUT.
- Force all hosts to `CODEGRAPH_NO_DAEMON` — owner config tax; does not replace the payload fix.

## Risks accepted

- Cheap COUNT on slow FS still sits inside `#172`’s ~30s budget (500ms busy cap already on the probe).
- Busy looking a bit like empty (tools listed, short copy).
- Band-2 design = same grok family as RT (owner harness exception).
- Judge fallback `syn-kimi-k3` vs design `syn-3-kimi-k3` = same-family warn.
- Proxy COUNT must not wait for daemon engine open (same `#172` spirit).

## Open questions remaining

None for this grill. Exact instruction strings, mapper table, and whether proxy can `existsSync`+COUNT without importing the CLI module are **craft for design**.

## Parked vs cut

| Item | Tag |
|---|---|
| CLI `init` repair / `${…}` refuse | **DONE** Bucket 4 |
| Writ probe `unreadable` | **PLANNED** in Bucket 6 |
| Native plugin/event bus | **THIS FEATURE, later re-grill** (TD-01) |
| `.codegraph/ready` | **NEVER IN ORIGINAL SCOPE** (Q5-a) |
| Empty → `isError` | **NEVER IN ORIGINAL SCOPE** |
| npm upgrade of upstream | **NEVER IN ORIGINAL SCOPE** |
| Installer `cursor.ts` | **NEVER IN ORIGINAL SCOPE** this bucket |
| `engine.ts` + daemon idle-kill as a **second product** | **A-split only if FCV proves it** (C1-a) |

Nothing else was **CUT**.

## Expert still doesn’t like

FULL PIPE for ~20 lines + a proxy twin is heavy, but empty-db looking indexed is the silently-wrong case the FULL rule exists for. Do not demote. Do not drop proxy to “save the conductor” — that saves this afternoon and leaves the daily lie.

## ADR / CONTEXT / object-map

- ADR: **offer with the impl** in `codegraph/docs/adr/` (all three gates true: mapper 5→3 is surprising; reversing it re-breaks agents; real trade-off vs duplicating the probe).
- CONTEXT.md: **no write** (MCP payload names are not a product-domain glossary; they live in freeze + server-instructions).
- Object-map: no hit.
