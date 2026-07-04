# CLAUDE.md — ssot-diagram

> ssot-diagram rules. Repo-wide rules: `../CLAUDE.md`.

## What this tool is

The flagship G3 tool: a **single source of truth** a non-coder can read to see the
real state of what's being built — code structure + the decisions behind it + whether
those decisions are still valid — in one place, kept honest by a deterministic
foundation rather than by trusting an AI to update docs.

End artifact: an **interactive diagram** (self-contained HTML) — macro components →
micros → nanos, everything labeled in plain language, decision (ADR) status painted on.

Core principle: **determinism flows up, inference flows down through a human gate.**
Lower layers (code structure, anchored decisions, staleness) are machine-checkable —
never depend on an LLM for verdicts. An LLM may *explain* and *propose*, but never
silently rewrites a lower layer. Every LLM-written sentence is **pinned to a
signature** of the code it describes — when code drifts, the sentence is visibly marked
stale, the same way a decision goes stale.

## Layered model

```
L5  Interactive HTML diagram   ← non-coder opens this; macro → micro → nano
L4  Narrative sidecar          ← plain-language text; LLM proposes, human approves,
                                  every entry signature-pinned (goes stale like a decision)
L3  Diagram model extractor    ← deterministic: DB + decision index → one JSON model   (SHIPPED)
L2  Staleness engine           ← deterministic: anchor drift → FRESH/STALE/ORPHANED     (SHIPPED)
L1  Anchored decision records  ← decisions reference code by stable anchor              (SHIPPED)
L0  Codegraph foundation       ← deterministic: symbols, edges, content signatures       (external)
```

L3 is pure computation (testable, no judgment). L4 is the only inference layer and it
is fully gated + pinned. L5 is a dumb renderer of L3+L4 — it invents nothing.

## Phases + status

- **P1** decision-index engine (`decision_index.py` + `decision_hook.py`) — SHIPPED
- **P2** decision-index curation (mkt_engine: 8 ADRs/33 anchors/all verified/all FRESH) — DONE 2026-07-04
- **P3** diagram-model extractor (`graph_model.py` → `diagram-model.json`) — DONE 2026-07-04 (merged main `ba02a56`); 32/32 pytest, byte-deterministic (golden sha256 `5a1e2156…`)
- **P4** narrative sidecar — NEXT
- **P5** interactive HTML renderer
- **P6** PostToolUse re-extract hook

Pick-up point: `STATE.md`. Roadmap detail: `roadmap.md`. Run report:
`ai-artifacts/9_runs/2026-07-04-p3-diagram-model-extractor.md`.

## Tool-specific rules (inherit repo rules from `../CLAUDE.md`)

- **3-level NESTED** model (Block 4a FROZEN contract in
  `../docs/roadmap/skeleton-contracts.md`): components → micros → nanos. No fourth
  level, **no flat mode**. P3 originally specced flat; the contract won, code is nested.
- **Content signatures pin every persisted node**, including decisions: decision
  signature = `_sorted_sha256(verified anchors' live sigs)`, NOT `sha256(id)` — so P4
  narratives can detect staleness via signature mismatch (Block 5b trust gate).
- Edge kinds ⊆ `{calls, imports, references}` (contract 6 FROZEN). `instantiates`
  folds to `calls`; `implements` is dropped; non-function-target nano-level edges
  resolve to the target symbol's owning micro (no silent data loss).
- Read-only DB (`mode=ro&immutable=1`); reuses P1's recipe via sibling-import
  (`import decision_index as di`); `_shared/` extraction deferred to Phase B per
  `adrs/0001-reuse-p1-recipe-by-sibling-import-defer-shared-to-phase-b.md`.
- Byte-deterministic writer: `sort_keys=True`, `generated_at: null`, atomic
  temp+`os.replace` (inherits P1's `save_index` pattern).
