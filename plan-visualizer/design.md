# Plan Visualizer — Design

**Status:** not built · **Effort:** S once ssot-diagram P5 (the renderer) ships; M if built standalone · **Build order:** #8 in the BLUEPRINT §6 sequence — deliberately after plan-verifier (#3) and the ssot renderer (#7), because it is nearly free once both exist.

---

## What it is

When an AI proposes a plan, that plan is a wall of engineering prose. This tool turns
the plan into a picture drawn on top of the map of the code as it exists today: the
pieces the plan will change glow amber, brand-new pieces appear with dashed outlines,
pieces being removed are crossed out, and everything that currently depends on the
changed pieces is highlighted so nothing breaks silently. A short header sentence in
plain language summarizes the whole plan. You approve or reject plans by looking at a
picture instead of trusting prose.

## Why it exists

- **Principle 1 — trust artifacts, not claims.** The picture is computed from the
  real code database, not from what the plan's author says. If the plan claims to
  touch something that doesn't exist, the picture shows a ghost.
- **Principle 3 — determinism before inference.** No LLM draws anything. Same plan +
  same code = byte-identical picture, every time.
- **Principle 4 — route attention to one-way doors.** The human plan-approval gate is
  the single most valuable review moment. This tool makes that moment cheap and
  reliable for a non-coder, whose strongest judgment channel is visual.

**Failure it prevents:** approving a plan whose true blast radius you never saw —
e.g., a "small change" that 12 existing places depend on, or a removal the plan never
acknowledged had callers.

Together with plan-verifier this is the pair that changes `/build-pipeline`: verify
the plan's facts mechanically, then look at the plan as a picture.

## Inputs

1. **The plan-verify manifest** — the small declared block plan-verifier
   (BLUEPRINT §2.2) already standardizes inside every plan file: a `touch:` list
   (existing things the plan will modify), a `new:` list (things it will create,
   each with a declared file path), and a `remove:` list (things it will delete).
   Plan-verifier's verdicts on those claims (MISSING / AMBIGUOUS / COLLISION /
   BLOCKED / UNACKNOWLEDGED-BLAST) are also consumed.
2. **`diagram-model.json`** — the current repo's diagram model produced by
   ssot-diagram P3 (`graph_model.py extract`): the three-level component → file →
   function hierarchy, rolled-up edges with counts, and attached decision nodes.

No other inputs. In particular: no re-reading of source files, no LLM output.

## Core computation (zero LLM, fully deterministic)

1. **Resolve `touch` and `remove` entries to model nodes.** Each manifest entry names
   a path and symbol; look it up in the diagram model (same resolution outcome
   discipline as `_shared/resolve.py` — honest AMBIGUOUS/UNRESOLVED, never a guess).
   Mark resolved nodes as *touched* or *removed*.
2. **Synthesize proposed nodes for `new` entries.** These don't exist in the model
   yet, so create dashed placeholder nodes and place each one inside the component
   its declared file path belongs to (the model's component grouping decides this —
   the tool invents no grouping of its own).
3. **Compute the collateral set.** For every touched or removed node, pull its
   one-hop callers from the model's edges. These are the existing pieces that depend
   on the changed code.
4. **Fade everything else.** All remaining nodes stay in the picture for orientation
   but are visually de-emphasized. The eye lands only on what the plan affects.

## Output contract (rendering)

Reuses the ssot-diagram P5 renderer and the design-system tokens — the renderer is
data-blind; this tool only prepares a decorated model for it.

| Plan role | Visual treatment |
|---|---|
| touched | amber badge |
| new | positive badge + dashed border |
| removed | danger badge + strikethrough label |
| collateral caller | neutral badge, highlighted edge with dependency count |
| everything else | faded |

- **Header panel** — plain language, deterministic (assembled from counts, never an
  LLM sentence). Example, reproduced exactly from the blueprint:
  *"This plan changes 3 things inside Payments, adds 1 new piece, removes 1.
  12 existing places depend on the changed code. 2 decisions (ADR-0007, ADR-0012)
  are anchored to affected code."*
- **Verdict chips** — plan-verifier verdicts render as warning chips on the affected
  nodes. A `MISSING` claim literally renders as a ghost node: the plan says it will
  touch something the code database says does not exist, and you can see that.
- Output is one self-contained HTML file (same rule as the P5 renderer — zero
  external dependencies, opens in any browser).

## Delivery

- **CLI:** `plan_visualize.py <plan.md> -o plan-preview.html` — point it at a plan
  file, get a preview file to open.
- **Pipeline:** wired as an optional `/build-pipeline` step immediately after the
  plan-verify step, so the human gate always has both the fact-check table and the
  picture.
- **Piggyback:** ships as a `manifest.json` entry so `piggyback install/init/update`
  distributes it like every other tool.

## Ground rules inherited

- **Read-only DB.** Never touches `.codegraph/codegraph.db` directly at all — it
  reads `diagram-model.json`, itself a read-only derivation. Writes only its own
  output HTML.
- **Determinism up, inference gated.** The entire picture is pure computation. There
  is no LLM anywhere in this tool; nothing to gate.
- **Signatures are the currency.** Node identity and placement come from the diagram
  model, whose nodes already carry content signatures; this tool adds no new
  signature scheme.
- **Budgeted, fail-open.** It is a CLI/pipeline step, not a context-injecting hook,
  so the 30-line hook budget doesn't apply — but it must fail open in the pipeline:
  if the model file or manifest is missing, print one plain-language line saying why
  no preview was produced and exit without blocking the run (except under an explicit
  strict flag).
- **Piggyback delivery rail.** Distributed via `manifest.json`; also runs standalone
  for CI and manual use.

## Dependencies

- **plan-verifier (BLUEPRINT §2.2)** — defines the manifest convention and produces
  the verdicts this tool renders. Hard dependency: no manifest, no picture.
- **ssot-diagram P3** — `diagram-model.json`, the map the plan is drawn onto.
- **ssot-diagram P5** — the interactive HTML renderer and its template.
- **design-system tokens** — `visualizer_guide/design-system/spec.md` colors/badges
  (amber, positive, danger, neutral, disabled).
- **`_shared/` modules:** `resolve.py` (manifest entry → model node with honest
  AMBIGUOUS/UNRESOLVED), `budget.py` only if header text is ever size-capped.
  `db.py`/`queries.py` are *not* needed if one-hop callers come from the model's
  rolled-up edges — preferred, so this tool never opens the DB itself.

## Non-goals

- **No plan authoring or editing.** It renders a plan; it never changes one.
- **No heuristic claim extraction.** If a plan lacks the declared manifest block,
  this tool does not scrape prose — that fallback belongs to plan-verifier; this
  tool visualizes only what was declared and verified.
- **No diffing of two plans**, no before/after simulation of the codebase, no
  execution-order animation. One plan, one current map, one picture.
- **No LLM commentary** in the output, ever.

## Open questions

- **[Human-judgment]** When plan-verifier reports AMBIGUOUS (a name matching several
  symbols), should the picture mark all candidates or refuse to render that entry
  with a visible "unresolved" chip? Refusing is more honest; marking all is more
  informative but can mislead.
- **[Human-judgment]** Should the optional `/build-pipeline` step be on by default
  once shipped, or opt-in per repo until you've trusted a few previews?
- **[Technical research]** Whether the P5 renderer's node/edge decoration hooks are
  general enough to express dashed borders and strikethrough without forking the
  template — confirm when P5's template lands, before sizing this at S.
- **[Technical research]** For a `new:` entry whose declared path sits in a directory
  the model has no component for (a genuinely new area), where does the dashed node
  go — a synthesized "proposed component," or a top-level orphan? Needs a look at how
  P3's component config handles unknown paths.
