# STATE.md — ssot-diagram

> ssot-diagram pick-up point. Repo-wide state: `../STATE.md`.

## What is happening right now

**ssot P3 diagram-model extractor: DONE (2026-07-04), merged to main.**
Commit `ba02a56` (merge) + `b0b82b4` (run-report). NOT pushed to origin. Built via
`deepseek-orchestrate` (deepseek-v4-flash implemented; Claude reviewed each wave) with
three review rounds (plan-compliance → code-quality → phase-end adversarial red-team)
— all findings fixed. Run report: `ai-artifacts/9_runs/2026-07-04-p3-diagram-model-extractor.md`;
scoreboard: `../docs/model-scoreboard.csv`. `../CLAUDE.md` "Build Progress" updated
(P3 DONE / P4 next). Pushed to origin `99a4c11` (2026-07-06).

## IN PROGRESS: P4 (narrative sidecar) — implementation DONE 2026-07-06; pending owner review/merge

**Started 2026-07-06.** Stage 1-3 done (roadmap read; grill locked 2 decisions:
command-per-id approval, scope = components+micros+important nanos). **Design step
DONE + hardened:** `ai-artifacts/1_design/p4-narrative-sidecar.md` (826 lines) +
red-team `…-redteam.md` (verdict REVISE: 4 MAJOR + 5 MINOR, all folded). Owner
ratified 3 forks: (1) **Block 5a AMENDED 2026-07-06** — store `proposed|approved`,
derive `stale` live (`../docs/roadmap/skeleton-contracts.md` Block 5a/5b now carry
the amendment + consumer obligation); (2) keep separate `narrate_threshold` (default
4, reconciled with nano_cap); (3) decisions EXCLUDED from narration. Key design fix:
signature pins at INGEST, approve refuses a drifted entry (no laundering). **Spec
step DONE (2026-07-06):** `ai-artifacts/2_specs/p4-narrative-sidecar.md` (700 lines,
12 components, 15 assumptions A1–A15 — design's A1–A10 folded + A11–A15 from red-team
fixes; author pre-verified A7/A10/A3 against live code, but factual-code-verification
re-confirms independently). OQ-MANIFEST-1 RESOLVED 2026-07-06: separate
`narrative-sidecar` manifest key. **factual-code-verification step DONE
(2026-07-06):** `ai-artifacts/3_factual-code-verification/p4-narrative-sidecar.md`
(174 lines) — 13 validated / 0 invalidated / 2 unverifiable (A14/A15, functions
not built yet). No invalidated assumption ⇒ no design loop-back; pipeline proceeds.
FCV corrected a load-bearing doc-drift: golden sha256 is `56df3d86…`, NOT the
`5a1e2156…` previously repeated in STATE/CLAUDE/spec (now fixed in those 3 docs;
`ai-artifacts/9_runs/2026-07-04-p3-…md` still carries the stale value as a historical
record). **Plan step DONE (2026-07-06):** `ai-artifacts/4_plans/p4-narrative-sidecar.md`
(837 lines, 12 Steps ≈ spec components 1–12, 5 waves, 16 capabilities; `plan_verify.py
--strict` PASS 19/19; hardened 2026-07-06 with an `## Implementer Notes
(weak-model)` section — 15 signatures, `_derive_status`/`_first_sentence`/argparse
skeletons, `_save_model` serialization params, verified node field names, test-fixture
template — for handoff to a weaker implementer model, gate still PASS). **build-pipeline
COMPLETE** (design→spec→FCV→plan).

## IMPLEMENTATION DONE (2026-07-06) — deepseek-orchestrate protocol, Claude subagents (no dsk)

Built via the `deepseek-orchestrate` protocol adapted to Claude leaf subagents
(`writ-implementer`/`writ-test-writer`/`writ-plan-reviewer`/`writ-code-quality-reviewer`/
`writ-red-team`, all opus/sonnet, max 2 parallel). Plan was the implementer source of
truth (exact signatures + skeletons; weak-model-hardened). Waves A+B (Steps 1-4 helpers)
→ Wave C (Steps 5-9 subcommands + Step 11 config/manifest inline) → Wave D (Step 10 CLI)
→ Wave E (Step 12 tests). Implementation is ADDITIVE: `graph_model.py` +475 lines, 0
modified/removed lines (P3 `_save_model`/`load_config`/`cmd_extract`/`build_parser`
existing subparsers byte-identical); `test_graph_model.py` +874 lines (11 `TestNarrate*`
classes, 66 tests); config +2 keys; manifest +1 `narrative-sidecar` entry.

**Plan/substrate contradictions found + adjudicated during build (NOT deviations, both
contract-faithful):**
- **Sig-index count 402 ≠ plan C4's "405".** 3 nano ids (canRedo, canUndo, resetStore)
  appear under 2 micros each and dedupe in the pinned `dict[str,str]` return type. 402
  is correct-per-signature; C4's 405 was a visit-count. Tests assert 402.
- **`_first_sentence` bar-stripping.** Plan note §4 verbatim regex stripped only
  pure-separator lines, but the named T2 fixtures (`validatePixelSize`/`EditTopBar`/
  `ResizeTool`) carry LABELED headers (`── X ──`, prose mixed with bars on one line) —
  26 nanos leaked `──`/`----`. Extended `_first_sentence` with a `_BAR_RUN` scrubber
  (`[-─=]{2,}`→space) post-join. Contract (no-bars, T2/C6/C7/E2E §2) preserved.

**Review rounds DONE:** R1 plan-compliance (`writ-plan-reviewer`) = COMPLIANT-WITH-NOTES
(all capabilities C1-C16 + load-bearing invariants live-verified; both adjudicated
contradictions confirmed contract-faithful; the 3 "notes" are pre-existing/authorized —
skeleton-contracts.md Block 5a/5b amendment was owner-ratified at DESIGN step, the 5
doc/state files are prior pipeline steps, C16 "green" wording vs 3 pre-existing
TestGoldenLive pilot-drift fails). R2 code-quality (`writ-code-quality-reviewer`) =
FIX-FIRST → 1 IMPORTANT fixed + verified (`cmd_narrate_status` was wrongly widening
unnarrated scope via `--include-nanos`; spec §component 8 says that flag is worklist-only;
hardcoded `include_nanos=False`; F9 stored-entry-watching unaffected). Phase-end red-team
(`writ-red-team`) = REVISE: 2 MAJOR + 4 MINOR. **MAJOR 1 (dead `--include-nanos` on
status subparser)** FIXED — removed the flag so argparse honestly rejects it (vs silently
ignoring); 66 tests green. **MAJOR 2 (empty-signature laundering hole) DEFERRED** — see
Open Questions below. 4 MINORs deferred to doc.

**Verify (done-criteria):** `python3 -m pytest ssot-diagram/` = 95 passed / 3 pre-fail
(the SAME `TestGoldenLive` pilot-drift set, 0 NEW P4 failures; committed golden sha
`56df3d86…` intact, live extract `ca28dd56…` differs only because pilot repo drifted
since 2026-07-04). E2E walkthrough (plan §E2E, 10 steps) observed + matching: F6
laundering-hole close verified (approve refuses exit 2, sig/text NOT laundered), 1-step
refresh verified (drifted→ingest fresh→approve succeeds), byte-determinism (sha-equal
across two ingests), 0 `stale` in narratives.json, `piggyback status` lists
`narrative-sidecar` + `diagram-model`.

## Open Questions / tracked tech-debt (deferred — not blocking merge)
- **TD-P4-1 [MAJOR, KNOWN-LIMIT]: empty-signature laundering hole.** The F6 close is NOT
  airtight for nodes that share an empty-body content signature: `cmp-dist` +
  `cmp-invoice-cost` both = sha256 of empty source (`e3b0c442…`), and 3 empty test-body
  nanos collide too. If an id is REUSED for new code with the same empty hash, old
  approved text about old code renders approved-and-fresh for new code. Narrow (needs both
  id-reuse AND identical empty hash), solo-builder low-probability. **Owner decision
  2026-07-06: ACCEPTED as documented known-limit** — ship P4; revisit only if laundering
  becomes a real risk. Fillet fix (compound `node_id` into the pinned signature) would
  change Block 5a entry semantics → touches FROZEN contract + spec central claim + may
  still not close the empty-body-reuse sub-case; deferred. Logged here as TD-P4-1.
- **MINOR (4 doc/edge-gaps, DEFERRED to P6 — no data-loss/security):** (a)
  `cmd_narrate_reject` dies if no codegraph DB (uses DB only for root discovery; spec says
  reject needs no model). (b) P4 reads non-frozen P3 fields (`caller_count`/
  `is_exported`/`docstring`) via `.get(...,default)` — silent scoping degradation if P3
  renames them, no startup die (only `signature` guarded). (c) Re-extracting with a
  different `nano_cap` silently orphans previously-approved nano narratives
  (correct-orphaned behavior, undocumented alongside rename/delete). (d)
  `narrate_threshold=4` ↔ `nano_cap=8` interaction undocumented (raising nano_cap
  collapses fewer → widens worklist). All lumped into P6 GC + hook work (touches narrate
  internals there).

Artifacts under `ai-artifacts/` — NOTE case-collision debt (`AI-artifacts` vs
`ai-artifacts` in git, + `roadmap.md` moved into the folder) still unresolved,
deferred to post-P4 cleanup.

## P4 substrate (P3 as shipped)

P3 substrate is live: golden `testdata/mkt_engine.model.json` (sha256
`56df3d86…`) + Block 4 contract (in `../docs/roadmap/skeleton-contracts.md`). The
content-pinned decision signature (red-team Critical 2 fix) is what makes P4's
staleness trust-gate actually work — P4 narratives pin to `decision.signature`; if it
doesn't change on drift, stale prose renders as trusted. Pre-P4 housekeeping DONE
(2026-07-06): main pushed to origin `99a4c11`, `../CLAUDE.md` build-progress current.

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
| **implement** | `graph_model.py` (+ tests + golden + config + manifest) | ✅ merged main `ba02a56` — 32/32 pytest, deterministic (golden sha256 `56df3d86…`), P1 regression clean |
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
(sha256 `56df3d86…`); 11 decision nodes all FRESH; 2 collapsed `+K more` nodes;
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
