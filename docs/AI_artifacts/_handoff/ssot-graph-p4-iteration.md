# Handoff — SSOT Graph P4 Iteration

## Goal

Iterate on the P4 visual SSOT graph for `mkt_engine`. A working P4 preview widget exists (pure-JS force sim + SVG). Next session should extend it toward the real P4 spec: add code-structure edges from codegraph, supersedes chains, and move toward a reusable generator script.

## Read First

- [`ssot-diagram/roadmap.md`](../../../ssot-diagram/roadmap.md) — full layer model + P4 spec
- [`mkt_engine/docs/decision-index.json`](../../../../mkt_engine/docs/decision-index.json) — live data (8 ADRs, 25 anchors)
- [`ssot-diagram/decision_index.py`](../../../ssot-diagram/decision_index.py) — L1/L2 engine (read-only reference)

## State

**Done this session:**
- Read roadmap; confirmed P4 is next after P2 curation
- Pulled live data from `mkt_engine/docs/decision-index.json` + ran `decision_index.py status`
- Built P4 preview widget (inline HTML, pure JS — no CDN): force-directed graph, 8 ADR nodes + 20 code anchor nodes, 25 edges, hover tooltips, pan/zoom, color by module
- Widget renders correctly; shows Envelope as hub (×4 shared), ADR-0003 orange (no anchors), all 25 FRESH

**Key data facts:**
- 8 ADRs, 20 unique anchors, 25 links total
- Shared hubs: `Envelope@lib/canvas/types.ts` (×4), `canvas/types.ts` (×2), `canvas/store.ts` (×2)
- ADR-0003 has 0 anchors — needs curation
- All verified:false — P2 curation not yet done
- No supersedes chains set yet

**Not done:**
- Code-structure edges from codegraph (file imports, call graph between anchor nodes)
- Supersedes chains between ADR nodes
- Plain-language summaries on nodes (needs L3)
- Scoped views (per subsystem filter)
- Generator script (currently just a one-off widget, not a CLI tool)

## Next Steps

1. **Add codegraph edges** — query `.codegraph/codegraph.db` in mkt_engine for import/call edges between the 20 anchor files/symbols; render as thinner gray edges in the graph (separate layer, togglable)
2. **Add supersedes edges** — read `supersedes` field from decision-index.json; render as dashed orange ADR→ADR edges (currently all null, but wire it up)
3. **Scoped view toggle** — add module filter buttons (lib/canvas / lib/ai / components / other) that highlight/dim subgraphs
4. **Extract to generator script** — `ssot-diagram/graph_render.py` that reads decision-index.json + codegraph.db and emits self-contained HTML; can be wired to the piggyback hook later

**Do NOT touch mkt_engine source files.** Read-only access only. If any file write is needed, use an isolated worktree.

## Open Items

- Decide: standalone HTML file output vs embedded widget-only? (user hasn't specified)
- L3 summaries (plain-language per ADR) need P3 to be built first — skip for now, leave placeholder
- `decision_index.py check <doc>` requires a positional `doc` arg — can't batch-check all ADRs in one call; might want to add a `check-all` subcommand eventually

## Files Touched

No files modified this session (read-only + widget rendered inline only):
- Read: `ssot-diagram/roadmap.md`
- Read: `mkt_engine/docs/decision-index.json`
- Read: `mkt_engine/docs/adrs/*.md` (all 8, first 5 lines each)
- Executed read-only: `decision_index.py status` in mkt_engine dir
- Created: `docs/AI_artifacts/_handoff/ssot-graph-p4-iteration.md` (this file)

## Suggested Skills

- `draw-diagram` or `mcp__visualize__show_widget` — to render updated widget iterations
- `writ:writ-work` — if extracting to a generator script (`graph_render.py`)
- `guardrail-check` — before writing any new tool that touches mkt_engine files
