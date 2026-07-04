# STATE.md — ssot-diagram

> ssot-diagram pick-up point. Repo-wide state: `../STATE.md`.

## What is happening right now

**ssot P3 diagram-model extractor: DONE (2026-07-04), merged to main.**
Commit `ba02a56` (merge) + `b0b82b4` (run-report). NOT pushed to origin. Built via
`deepseek-orchestrate` (deepseek-v4-flash implemented; Claude reviewed each wave) with
three review rounds (plan-compliance → code-quality → phase-end adversarial red-team)
— all findings fixed. Run report: `ai-artifacts/9_runs/2026-07-04-p3-diagram-model-extractor.md`;
scoreboard: `../docs/model-scoreboard.csv`. **`../CLAUDE.md` "Build Progress" still says
"awaiting code implementation" — update on next touch.**

## NEXT: P4 (narrative sidecar) per `roadmap.md`

P3 substrate is live: golden `testdata/mkt_engine.model.json` (sha256
`5a1e2156…`) + Block 4 contract (in `../docs/roadmap/skeleton-contracts.md`). The
content-pinned decision signature (red-team Critical 2 fix) is what makes P4's
staleness trust-gate actually work — P4 narratives pin to `decision.signature`; if it
doesn't change on drift, stale prose renders as trusted. Before P4: optionally push
main to origin, update `../CLAUDE.md` build-progress.

## One-paragraph orientation (P3 as shipped)

P3 is one deterministic script `graph_model.py` that reads the codegraph DB (read-only)
+ the curated decision index + a config, and emits one `diagram-model.json` (3-level
NESTED per Block 4a: components → micros → nanos, with rolled-up edges
`calls`/`imports`/`references`, decision nodes with FRESH/STALE/ORPHANED/superseded
badges, and a CONTENT signature on every node including decisions — pinned to anchor
sigs so drift is visible). Same inputs ⇒ byte-identical JSON. No LLM in any verdict.
Ships via `../manifest.json` (entry `diagram-model`, repo scope, `hooks: []` —
CLI-first; P6 owns hook wiring). P2 (curated index) LANDED 2026-07-04.

## Pipeline state (all DONE)

| Step | Artifact | Status |
|---|---|---|
| design | `ai-artifacts/1_design/p3-diagram-model-extractor.md` | ✅ written, revised post-red-team |
| red-team | (5 fixes folded into design as A13–A17) | ✅ 5 fixes applied |
| spec | `ai-artifacts/2_specs/p3-diagram-model-extractor.md` | ✅ written (14 components, 25 assumptions A1–A25) |
| factual-code-verification | `ai-artifacts/3_factual-code-verification/p3-diagram-model-extractor.md` | ✅ 23 valid / 0 invalidated / 2 unverifiable-non-blocking; A13–A17 each verified |
| ADR | `adrs/0001-reuse-p1-recipe-by-sibling-import-defer-shared-to-phase-b.md` | ✅ written |
| plan | `ai-artifacts/4_plans/p3-diagram-model-extractor.md` | ✅ written (1484 lines, 14 Steps) |
| **implement** | `graph_model.py` (+ tests + golden + config + manifest) | ✅ merged main `ba02a56` — 32/32 pytest, deterministic (golden sha256 `5a1e2156…`), P1 regression clean |
| **review** | plan-compliance → code-quality → phase-end red-team (3 rounds) | ✅ all findings fixed; mutation-tested |

## What was built + deviations from the plan (post-implementation notes)

The implementer (deepseek-v4-flash via `deepseek-orchestrate`) wrote the initial
extractor; Claude (orchestrator) ran three review rounds and fixed every finding.
**Deviations from the plan that the reviews corrected** (the plan text and the code
disagreed in places; for traceability):

- **Model layout: NESTED, not flat.** Plan Step 11 said "flat lists with pointers";
  Block 4a FROZEN contract says "no flat mode". Code is NESTED (`components[].children`
  = micros, `micros[].children` = nanos) — contract wins, plan text was wrong.
- **Default `--config`/`--out` paths**: in `ssot-diagram/` subdir (plan Step 2), not
  repo-root. deepseek initially placed them at repo-root; fixed.
- **`--force` on `extract`**: removed (not in plan Step 2's flag surface). `bootstrap-config`
  keeps its `--force`. `--update-golden` suppressed via `argparse.SUPPRESS`.
- **Nano `name` field** (Block 4b FROZEN + Step 7 action 6): added (deepseek omitted it).
- **Pre-extract guard `[:1]` bug** (Step 10 action 4): fixed to scan ALL decisions.
- **Micro id class-dominant `#qname`** (Step 6 action 5) + **collapsed id
  `nano:+collapsed@micro:<mid>`** (Step 7 action 8): plan-form applied.
- **Supersedes → literal `"superseded"`** only when it points at a known ADR (Step 9
  action 7); deepseek's `final_status = ss if ss else worst` emitted the superseding
  ADR's id as the status — fixed.
- **Per-node `decisions[]` sorted** (Block 1 determinism): added (deepseek left them in
  index-key-order, which leaked when the index JSON was re-serialized).
- **SystemExit swallow removed**: corrupt index now fail-loud via `di.die` (contract C2);
  absent index warns + 0 decisions.
- **EDGE DATA LOSS (Step 8, red-team Critical)**: nano-level edges whose target was a
  class/interface/type_alias/constant/file were silently dropped (db_id_to_nano covered
  only function/method). At the pilot: 225 calls-to-constants + 425 type-references +
  17 class-instantiates vanished. Fixed: resolve non-function targets to the target
  symbol's FILE's micro (plan Step 8 action 8); the edge attaches on that micro's
  `edges[]`. Golden micro-level gained 239 references + 65 calls. **A16 test rewritten
  to use a CLASS target (the real pilot shape — the original used a function target,
  which masked the bug).**
- **DECISION SIGNATURE (Step 9 action 6, red-team Critical)**: was `sha256(id)` (string,
  never changed on drift) — broke the Block 1e/4b/5b pinning chain (P4 narratives would
  render stale prose as trusted). Fixed: `_sorted_sha256(verified anchors' live sigs via
  di.current_sig)`; falls back to `sha256(id)` only if no anchor produced a live sig.
- **`--nano-cap` CLI override (red-team Major)**: config was always overriding the CLI
  flag (dead code). Fixed: CLI overrides config; config is the fallback.

**Deferred (non-blocking, pilot-n/a):** config curation (seed config shipped as-is;
owner product-decision). `_shared/` extraction stays Phase B per ADR-0001.

## Verify command (P3 done-criteria — run from the mkt_engine checkout OR with explicit
`--db`/`--index` pointing at the pilot; the bare command works once `piggyback install`
wires the tool into the pilot repo)

```sh
python3 ssot-diagram/graph_model.py extract --db ~/all-projects/mkt_engine/.codegraph/codegraph.db \
  --index ~/all-projects/mkt_engine/docs/decision-index.json \
  --config ssot-diagram/ssot-diagram.config.json    # or let it default after install
python3 -m pytest ssot-diagram/                      # use /Users/phatchenh/.cache/writ/.venv/bin/python if default python3 lacks pytest
```
Pass = 32/32 pytest (golden NOT skipped — pilot DB present) AND: byte-identical re-extract
(sha256 `5a1e2156…`); 11 decision nodes all FRESH; 2 collapsed `+K more` nodes;
sample_callers `{file,line}` only (0 malformed of 1476); `generated_at: null`; edge kinds
⊆ {calls,imports,references}; 0 ids leaking `nodes.id` shape; `decision_index status`
still exits 0 (P1 regression).

## Stale artifacts (do NOT trust for current state)

- `ai-artifacts/_handoff/p3-pipeline-state.md` — last updated at the spec step;
  its "next step: factual-code-verification" line is SUPERSEDED (verify + plan both
  done). Kept as a record, not a pick-up point. **Use this STATE.md instead.**
- `ai-artifacts/_handoff/p3-resume-verification.md` — same; superseded.
- `ai-artifacts/_handoff/_archive/ssot-graph-p4-iteration.md` — phase-mismapped
  (labeled P4 but is P5/P6 pre-exploration) + stale P2 data. See its archive README.
- Assistant-private memory file `parallel-phase-ab-split.md` — has stale "0/25
  verified" framing. The live index (33/33 verified+FRESH) is the truth; re-verify
  the live index each session, do not trust that memory file.
