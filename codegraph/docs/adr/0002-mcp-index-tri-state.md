# ADR 0002 — MCP serves a 3-arm index tri-state, not the CLI's 5-arm health

## Status

Accepted (2026-08-20).

## Context

The CLI and the MCP server read the same index but serve different truths.
`probeIndexHealth` (ADR 0001) classifies an index into five statuses —
`usable`, `empty`, `busy`, `unreadable`, `unclassified`. The MCP handshake,
however, only ever asked "does a `.codegraph/` root exist" and acted on that
binary answer. Worse, the proxy door answered `tools/list` with the full
static tool list unconditionally, so an unindexed workspace was handed tools
that would all fail — and early `isError` failures teach an agent to abandon
codegraph entirely.

The MCP surface is frozen as a tri-state: `index_missing`, `index_empty`,
`usable`, with `busy` carried as a boolean flag rather than a fourth
MCP-visible name. This ADR records how the CLI's five-arm health union maps
onto that tri-state and why.

## Decision

Adopt **Option A** from the bucket-5 design: one mcp-internal helper
(`src/mcp/index-state.ts`) owns walk → probe → throw-guard → 5→3 map and
feeds both MCP doors — the direct `MCPSession` and the local-handshake
proxy — so they answer identically by construction.

### Mapping table (CLI 5-arm → MCP 3-arm)

| `probeIndexHealth` status | MCP state | busy | Handshake instructions | `tools/list` |
|---|---|---|---|---|
| `usable` | `usable` | false | full playbook (`SERVER_INSTRUCTIONS`) | `getStaticTools()` |
| `empty` | `index_empty` | false | "index is empty" (`SERVER_INSTRUCTIONS_INDEX_EMPTY`) | `getStaticTools()` |
| `busy` | `index_empty` | **true** | "index is busy" (`SERVER_INSTRUCTIONS_INDEX_BUSY`) | `getStaticTools()` |
| `unreadable` | `index_missing` | false | inactive note (`SERVER_INSTRUCTIONS_UNINDEXED`) | `[]` |
| `unclassified` | `index_missing` | false | inactive note (`SERVER_INSTRUCTIONS_UNINDEXED`) | `[]` |

`busy` maps to the empty-style arm (tools stay listed): the index exists and
an index build in flight will fill it, so the agent keeps its tools but gets
a short "busy, retry later" copy. The busy discriminant rides a
`{ state, busy }` flag on the helper's return value, not a fourth
MCP-visible name.

### Probe throw → existence, never missing

`probeIndexHealth` opens the db with raw `node:sqlite`, which does not exist
on the supported Node 20–22.4 floor. When the probe throws, the helper
degrades to today's existence gate: a root the walk already found ⇒
usable-enough serving (full playbook + static tools — the engine path never
touches `node:sqlite`); no root ⇒ `index_missing`. A working index must not
silently become "missing" because the probe was unavailable.

### One nonempty `tools/list` source on both doors

`tools/list` returns `[]` only for `index_missing`. Every nonempty list comes
from `getStaticTools()` on BOTH doors, decided by the state alone — never
from `engine.getToolHandler().getTools()`, which byte-diverges via its
per-repo budget suffix once the engine loads and whose availability depends
on a successful engine open. A served list is a state decision, not an
engine decision.

### Carve-out from ADR 0001

ADR 0001 (`:76-77`) reserved the MCP empty-warning threshold and any future
ready-stamp or daemon-visible health signal to Buckets 5 and 6
independently. This ADR is that carve-out: MCP imports `probeIndexHealth`
directly (the `src/index.ts` barrel stays untouched) and owns the 3-arm
mapping. ADR 0001's repair decision table is not amended.

## Why Option A over inlining the map

Two doors (session + proxy) both answer `initialize` and `tools/list`.
Inlining the walk + probe + throw-guard + map in each door re-creates the
two-doors-drift hazard the frozen contract exists to kill: a future edit
updates one door, and the two doors answer differently for the same db. One
helper makes "same payloads on both doors" structural, not conventional.

## Consequences

Positive:

- An unindexed workspace gets an empty `tools/list` and a short inactive
  note instead of a full tool list that would all fail — the one signal an
  agent can't misread.
- Missing vs empty vs usable are told apart in the handshake, so the empty
  state keeps its tools and the empty→usable transition is picked up on the
  next `tools/list`.
- One codebase-owned 5→3 mapping — Bucket 6's writ probe reads the same table.

Negative:

- One extra read-only SQLite open + COUNT per `initialize` / `tools/list`
  (sub-ms warm; ≤500ms worst busy case via `busy_timeout`).
- A new mcp→directory import edge — recorded in `UPDATING.md` so upstream
  merges surface it (fork-survival discipline).

## Open

- TD-01 stays OPEN: no plugin bus, no `.codegraph/ready`. This ADR adds no
  consumer-facing lifecycle event.

## References

- Design: `docs/AI_artifacts/3_design/2026-08-19-bkt5-codegraph-mcp.md` —
  Option A (~:151), mapping table (~:60), probe-throw fallback (~:62).
- Plan: `docs/AI_artifacts/6_plans/2026-08-19-bkt5-codegraph-mcp.md` — Step 8.
- ADR 0001: `codegraph/docs/adr/0001-init-repairs-unusable-index.md` — the
  5-arm vocabulary this ADR maps from; carve-out at `:76-77`.
