# SSOT Diagram — Roadmap

## Goal

A **single source of truth** a non-coder can read to see the real state of what is
being built with an AI: the code structure, the decisions behind it, and whether
those decisions are still valid — in one place, kept honest by a deterministic
foundation rather than by trusting an AI to update docs.

The end artifact is an **interactive diagram** (a single self-contained HTML file,
per `visualizer_guide/design-system/spec.md`): macro components explain the overall
system; each macro expands on click to the micro level inside it; micro expands one
more level to nano (individual functions). Everything labeled in plain language.
Decision (ADR) status is painted onto the same picture.

Core principle: **determinism flows up, inference flows down through a human gate.**
- Lower layers (code structure, anchored decisions, staleness) are machine-checkable
  and never depend on an LLM for their verdicts.
- An LLM may *explain* and *propose*, but never silently rewrites a lower layer.
- Every LLM-written sentence in the final diagram is **pinned to a signature** of the
  code it describes — when the code drifts, the sentence is visibly marked stale, the
  same way a decision goes stale. No silent rot, which is exactly how the old
  hand-maintained docs died.

## The layered model

```
L5  Interactive HTML diagram   ← non-coder opens this; macro → micro → nano
L4  Narrative sidecar          ← plain-language text; LLM proposes, human approves,
                                  every entry signature-pinned (goes stale like a decision)
L3  Diagram model extractor    ← deterministic: DB + decision index → one JSON model
L2  Staleness engine           ← deterministic: anchor drift → FRESH/STALE/ORPHANED   (SHIPPED)
L1  Anchored decision records  ← decisions reference code by stable anchor            (SHIPPED)
L0  Codegraph foundation       ← deterministic: symbols, edges, content signatures    (external)
```

L3 is pure computation (testable, no judgment). L4 is the only inference layer and it
is fully gated + pinned. L5 is a dumb renderer of L3+L4 — it invents nothing.

## Phases

### P0 — Codegraph foundation · DONE (external)
Codegraph indexes the repo into `.codegraph/codegraph.db` (nodes, edges, files,
content hashes). Owned by codegraph itself; we only read it, always read-only.

### P1 — decision-index: anchored records + deterministic staleness · DONE
Engine CLI `ssot-diagram/decision_index.py` (`bootstrap`/`status`/`check`/`refresh`),
read-hook `decision_hook.py`, packaged into `piggyback init`. Anchors carry signature
snapshots from the codegraph DB; verdicts are `FRESH/STALE/ORPHANED/AMBIGUOUS`, no LLM.
45 tests passing; verified against the real mkt_engine index (8 ADRs, 25 anchors).

### P2 — Curate the real index · IN PROGRESS (user-owned)
The seed index is only trustworthy after a human pass. In mkt_engine:
- [ ] Drop wrong anchors (prose mentions that aren't real dependencies).
- [ ] Disambiguate `name@path` anchors bootstrap skipped (e.g. `push`).
- [ ] Re-anchor field/property mentions to their owning type or file.
- [ ] Set `supersedes` chains; mark superseded ADRs.
- [ ] `decision_index refresh <id>` each curated decision → `verified:true`.

**Exit criteria:** `decision_index status` exits 0 (all FRESH) with every anchor
`verified:true`. This curated index is an *input* to P3 — the diagram shows decision
nodes only for verified anchors, so P3 can start in parallel but ships after P2.

### P3 — Diagram model extractor · TODO (the deterministic heart)
One script, `ssot-diagram/graph_model.py`, that turns the codegraph DB + the decision
index into a single `diagram-model.json` — the only input the renderer ever sees.
Deterministic: same DB + same index + same config ⇒ byte-identical model.

**Three-level hierarchy, derived not invented:**
- **Macro** = components. Default: top-level directories that contain indexed files.
  Overridable by `ssot-diagram.config.json` (glob → component name), because good
  macro grouping is a human call, not a heuristic — same seed-then-curate pattern
  as the decision index.
- **Micro** = files (or classes, when a file holds one dominant class) inside a macro.
- **Nano** = functions/methods inside a micro, from `nodes` (`kind IN
  ('function','method','class')`), capped per micro (top N by caller count, rest
  collapsed into a "+K more" node) to avoid the hairball.

**Edges, rolled up:** symbol-level `calls`/`imports` edges aggregate to file level,
then to component level, with counts (`label: "calls ×14"`). Cross-component edges
appear at macro level; within-component edges appear only when expanded.

**Decision nodes:** each verified decision from the index becomes a node attached to
the macro/micro that owns its anchors; badge color = live status from the staleness
engine (fresh → positive, stale → danger, orphaned → danger, superseded → disabled).

**Signatures everywhere:** every model node carries a deterministic signature
(file → `files.content_hash`; symbol → source-slice sha256, same recipe as P1;
component → sha256 over its members' hashes). This is what P4 pins narratives to.

Deliverables:
- [ ] `graph_model.py extract` → `diagram-model.json` (schema documented in-file).
- [ ] `ssot-diagram.config.json` seed + curate flow (`graph_model.py bootstrap-config`).
- [ ] Roll-up edge aggregation with counts; per-micro nano cap.
- [ ] Decision-node merge from `docs/decision-index.json` (verified anchors only).
- [ ] Tests: fixture repo → golden model JSON; determinism test (two runs, identical).

**Exit criteria:** running twice on mkt_engine yields identical JSON; model validates
against its schema; every decision in the curated index appears exactly once.

### P4 — Narrative sidecar: gated plain language · TODO
Non-coders read sentences, not symbol names. `narratives.json` holds one entry per
model node: `{node_id, signature, text, status: proposed|approved|stale}`.

- `graph_model.py narrate` emits a **worklist**: nodes lacking an approved narrative,
  or whose pinned signature no longer matches (→ marked `stale`). An LLM (any agent
  session) fills `text` as `proposed`, using the node's real source/docstrings.
- A human approves (`narrate --approve <node_id>` re-pins the signature). Nothing
  unapproved or stale ever renders as trusted prose.
- Deterministic fallback so the diagram is never empty: kind + name + docstring first
  sentence + counts ("12 functions, called by 3 components") — machine-derived, safe.

Deliverables:
- [ ] `narratives.json` format + staleness check (reuses P1 signature logic).
- [ ] `narrate` worklist / `--approve` / `--reject` commands.
- [ ] Deterministic fallback text builder.
- [ ] Tests: drift a file → its narrative flips to stale; approval re-pins.

**Exit criteria:** tamper with a narrated file → next `extract` marks that narrative
stale and the renderer shows it visually; no path writes narrative text without the
approve step.

### P5 — Interactive HTML renderer · TODO (the end artifact)
`ssot-diagram/render.py`: injects `diagram-model.json` (+ narratives) into a template
built to `design-system/spec.md`. Evolves the existing sketch
(`visualizer_guide/diagrams/example-system-architecture.html`) from 2 levels to 3.

- [ ] Template honors the spec: DM Sans, warm palette, light/dark, badges, rounded
      orthogonal edges, legend, breadcrumb, pan/zoom, tooltips.
- [ ] Three-level expansion macro → micro → nano (spec §3.5, max depth 3); breadcrumb
      shows the path (spec §8.2).
- [ ] Decision nodes color-coded by status; stale narrative = visible "needs review"
      treatment (muted text + danger badge), never silently rendered as current.
- [ ] Plain-language first: approved narrative → fallback text → never raw dumps.
- [ ] Scoped views: `render --component <name>` emits a per-component file to avoid
      the whole-repo hairball on big repos.
- [ ] Output is one self-contained HTML file, zero external deps (spec header rule);
      data embedded as a single `const MODEL = {...}`.
- [ ] Tests: golden-model render smoke test (valid HTML, node count matches model).

**Exit criteria:** a non-coder can open `ssot-diagram.html` for mkt_engine, click from
system view down to a function, and see which decisions are attached and whether they
(and their explanations) are still current — without reading code.

### P6 — Regeneration plumbing · TODO
Staleness detection is only honest if regeneration is cheap and habitual.
- [ ] `piggyback` entry: `ssot-diagram` script — `extract` + `render` in one command.
- [ ] Hook wiring (reuse piggyback plumbing): after codegraph re-index / on session
      end, regenerate model + HTML; narratives are *never* touched by the hook
      (they only go stale, per P4).
- [ ] `status` roll-up: one command prints decisions not FRESH + narratives stale +
      model drift since last render — the "is my SSOT current?" check, exit 1 if not.

**Exit criteria:** edit code → re-index → regenerated diagram shows the change and
flips affected narratives/decisions to stale, with zero manual steps beyond the edit.

### P7 — LLM advisory layer for stale decisions · TODO
When an anchor goes STALE, an LLM reads the drift + the decision and **proposes** a
resolution (amend / supersede / refresh) with reasoning — strictly advisory, human
picks. Surface: `decision_index explain <id>` + extend the read-hook output. Must
never write to L1/L2 without confirmation. (Deliberately after P5/P6: the diagram
makes staleness *visible*; this phase only makes resolving it cheaper.)

### P8 — Decision coverage beyond ADRs · BACKLOG
Genuine decisions scattered in `docs/AI_artifacts/**` get promoted to ADRs (per
DOC-ARCH-001); working-memory drafts stay out of scope. Optionally extend bootstrap
to a wider doc glob once ADR promotion is done.

## Status summary

| Phase | What | Status |
|---|---|---|
| P0 | Codegraph foundation | done (external) |
| P1 | decision-index (records + staleness + hook + packaging) | **done** |
| P2 | Curate real index | in progress (user) |
| P3 | Diagram model extractor (`diagram-model.json`) | todo — next up |
| P4 | Narrative sidecar (gated plain language) | todo |
| P5 | Interactive HTML renderer (macro/micro/nano) | todo |
| P6 | Regeneration plumbing | todo |
| P7 | LLM advisory for stale decisions | todo |
| P8 | Decision coverage beyond ADRs | backlog |

Related: sibling tools that reuse these layers (plan verification, plan visualization,
context briefs) are specced in the repo-root [`BLUEPRINT.md`](../BLUEPRINT.md) — the
renderer built in P5 is deliberately reusable by the plan-visualizer there.
