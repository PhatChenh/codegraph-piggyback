# Archive

Stale or superseded handoff docs. Kept for history, not for action.

## ssot-graph-p4-iteration.md (archived 2026-07-04)

**Why archived:** phase-mismapped + stale data.

- Labeled "P4" but content is roadmap **P5 (renderer) + P6 (regen)** work —
  SVG widget, codegraph edges, generator script. Skipped real P3 (extractor)
  + P4 (narrative sidecar).
- Data facts stale: written Jun 28 against pre-curation index
  ("all verified:false"). P2 landed Jul 4 — 33 anchors now all `verified:true`,
  all FRESH. ADR-0003 anchor count + supersedes state may have changed.
- "Standalone HTML vs widget undecided" — superseded: roadmap P5 locks
  one self-contained HTML file.
- No code artifact saved (widget was inline-only, see doc line 52).

Salvageable: widget prototype + codegraph-edge-layer concept = useful P5
pre-exploration. Real P4 (narrative sidecar) is gated behind P3 extractor,
itself paused at factual-code-verification (see `p3-pipeline-state.md`).
