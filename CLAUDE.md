# CLAUDE.md — codegraph-piggyback

Hook scripts and CLIs that read `.codegraph/codegraph.db` to make AI coding agents
safer and cheaper. Owner is a non-SWE solo builder — explain options in plain English,
present tradeoffs before acting. This repo is the **delivery rail**: every tool ships
as a `manifest.json` entry so `piggyback install/init/update` distributes it.

---

## Project Context

Codegraph indexes a repo into a SQLite knowledge graph (`nodes`, `edges`, `files`,
FTS, `unresolved_refs`). This repo builds derivative tools on top: hooks that push
structural context to agents at the right moment (G1), deterministic verifiers that
check plans and commits against real code (G2), and non-coder visibility tools
(G3, flagship: `ssot-diagram/`). Full rationale + specs:
`~/all-projects/vibe-coding-setup/BLUEPRINT.md`.

## Reference Docs

Read before changing architecture:
- `docs/roadmap/skeleton-contracts.md` — the 5 FROZEN cross-phase contracts +
  build-order handoff (architecture-grill 2026-07-03; do not silently redesign)
- `~/all-projects/vibe-coding-setup/BLUEPRINT.md` — master spec: four principles, ground rules (§0),
  per-tool specs (G1–G3), build order (§6)
- `docs/roadmap/roadmap.md` — this repo's build order + per-tool design doc index
- `<tool>/design.md` — the standalone spec for each tool (write/read these, not the
  README's legacy "Planned scripts per tool" section, which BLUEPRINT supersedes)
- `ssot-diagram/CLAUDE.md` — flagship G3 tool's rules + layered model (P0–P6),
  cross-references `ssot-diagram/roadmap.md`. Read when working ssot-diagram phases.

## Tech Stack

| Layer | Choice |
|---|---|
| Tools | Python 3, stdlib only (sqlite3, hashlib, json) |
| Data source | `.codegraph/codegraph.db` — **read-only, always** |
| Derived state | Tool-owned files (`docs/decision-index.json`, `diagram-model.json`, snapshots) |
| Delivery | `manifest.json` entry + `piggyback add/register`; hooks into Claude Code `settings.json` |
| Tests | pytest (`test_*.py` beside the code) |

## Repo Structure

```
piggyback.py        # installer/reconciler CLI — wires manifest hooks into settings.json
manifest.json       # SSOT: script + hook events + scope (global|repo) per tool
_shared/            # extracted common code (db, sig, resolve, queries, budget, hookio) — see _shared/design.md
impact-analyzer/    # SHIPPED — PostToolUse:Read blast-radius hook (+ design-extensions.md)
codegraph-gate/     # SHIPPED — codegraph-first exploration ordering gate
ssot-diagram/       # SHIPPED P1–P5 (decision-index, P2 curation, P3 diagram-model, P4 narrative sidecar, P5 HTML renderer — impl DONE 2026-07-10 on branch dsk/p5-html-renderer, merge pending); P6 (regen hook) pending — per ssot-diagram/CLAUDE.md
plan-verifier/      # G2 star — verify plan claims against DB (design.md)
plan-visualizer/    # G3 star — render a plan as a picture over the code map (design.md)
changeset-context/  # branch brief: touched symbols + one-hop neighborhood (design.md)
repo-map/           # token-budgeted orientation map (design.md)
impact-precommit/   # commit-time blast-radius gate (design.md)
drift-digest/       # "what changed since I last looked" (design.md)
sot-enrichment/     # symbol biography (design.md)
dead-code-finder/   # hygiene: unreferenced nodes (design.md)
doc-coverage/       # hygiene: missing docstrings, CI mode (design.md)
arch-visualizer/    # legacy stub — superseded by ssot-diagram + plan-visualizer
docs/               # roadmap + install notes
```

## Commands

```sh
python3 piggyback.py install        # per-machine: wire global-scope hooks
piggyback init --all                # per-repo: wire repo-scope hooks (idempotent)
piggyback update                    # pull + reconcile
piggyback add <name> --script <path> --scope repo --hook 'Event:Matcher'
piggyback status                    # what's registered
python3 -m pytest                   # run all tests
```

## Coding Patterns

- One tool = one folder = one `design.md` + script(s) + `test_*.py` in the same folder.
- Verdicts are pure computations over the DB — an LLM may explain on top, never decide.
- Hooks: parse hook JSON on stdin, inject ≤ ~30 lines, stay silent when nothing to say,
  never block the session on their own errors (fail-open). `impact-analyzer` is the
  reference implementation.
- Signatures: file = `files.content_hash`; symbol = sha256 of source slice; component =
  sha256 over member hashes. Reuse `_shared/sig.py` (extracted from `decision_index.py`)
  — never reimplement.
- `_shared/` extraction happens when the **second consumer** appears, not speculatively.

## Critical Rules

- **Never write to `.codegraph/codegraph.db`.** Connect `mode=ro`. Derived state lives
  in tool-owned files.
- **Every tool registers in `manifest.json`** — a script not in the manifest doesn't ship.
- **CLIs must also run standalone** (CI + manual use), not only as hooks.
- **Anything LLM-written that persists is pinned to a content signature** so drift is
  visible, never silent.
- **Don't gut the README's consumer runbook** — machines depend on it verbatim.

## Build Progress

Shipped: impact-analyzer, codegraph-gate, decision-index (ssot P1), ssot P2
curation DONE (2026-07-04), **ssot P3 diagram-model extractor DONE (merged main
`ba02a56`, 2026-07-04; 32/32 pytest, byte-deterministic), P4 narrative sidecar
DONE 2026-07-06 (merged main `65f3982`; design→spec→FCV→plan→implement→review
complete, plan-verify 19/19; 105/108 pytest, 0 P4 regressions, byte-deterministic,
F6 laundering-hole close E2E-verified; TD-P4-1 empty-sig quarantine CLOSED, Block
5b amendment owner-ratified). **P5 HTML renderer MERGED to main `a51384e` (2026-07-10)** + pushed via `bf1570a`.
11 steps shipped via av-orchestrate (minimax worker seats on Steps 5/8/9/10 —
glm orchestrator inline-reviewing tier-A + authoring the verbatim steps):
`render.py` + `render_template.html` + `test_render.py` (24 tests) + 3 font
binaries + OFL + 4 fixtures + `ssot-render` manifest entry + OTHER-FILE
addendum note. **129 pytest pass / 3 pre-existing `TestGoldenLive` pilot-drift (0 NEW)**; golden
model sha `56df3d86…` intact; render E2E = 339KB self-contained,
byte-deterministic, zero network. **ssot NEXT (deferred vs FEEDBACK-scope):**
live painter E2E + ssot P6 PostToolUse re-extract hook — `ssot-diagram/STATE.md`.
plan-verifier + diff-verifier SHIPPED + MERGED to main (`82287f9` + BUG-024
`57c0961`). **FEEDBACK-scope 2026-08-16:** Buckets 1+2 done in source (village
ACP `--path` live-certified; `grep-absent` 0-files fails). **Bucket 4 codegraph
CLI MERGED to main `908667a` (2026-08-18):** refuse unexpanded `${…}`; `init`
repairs empty/unreadable, refuses busy; FIX 1 fresh-init error label. Plan
`docs/AI_artifacts/6_plans/2026-08-17-bkt4-codegraph-cli.md`. Report
`docs/AI_artifacts/9_runs/2026-08-17-bkt4-codegraph-cli.md`. **Bucket 3 pipeline
DONE 2026-08-18** (design/RT/spec/FCV/plan pinned; impl not started). Plan
`docs/AI_artifacts/6_plans/2026-08-18-bkt3-plan-verify.md`. Report
`docs/AI_artifacts/9_runs/2026-08-18-bkt3-plan-verify.md`. Remaining ROI:
3 impl → 6 → 5. Scope: `docs/AI_artifacts/_scope/2026-08-16-feedback-bugs-scope.md`.
av-orchestrate: BUG-023 staged-cwd FIXED (`1e48ad2`, do not re-open);
BUG-024 per-wave `--step` shipped (`57c0961`).
`_shared/` extraction SHIPPED (commit `82287f9`, alongside plan-verifier)
— `_shared/db.py`/`sig.py`/`resolve.py`/`queries.py`/`budget.py`/`hookio.py`/
`manifest.py` live at repo root; ADR-0001's "defer to Phase B" decision is
SUPERSEDED (dated note added to the ADR). See `ssot-diagram/STATE.md`** for the
P5 pick-up point. Everything else: specced in `<tool>/design.md`, build order
in `docs/roadmap/roadmap.md`.

## What AI Gets Wrong

- **`codegraph/` is a LOCAL FORK of the CodeGraph engine (base v1.0.1, binary
  reports 999.0.0 on purpose). NEVER `npm install/update -g @colbymchenry/codegraph`
  or `codegraph upgrade` — both silently revert the local patches. All update
  work follows `codegraph/UPDATING.md`.**
- README's "Planned scripts per tool" section is legacy; BLUEPRINT + per-tool
  `design.md` supersede it (e.g. commit-time impact checking is `impact-precommit/`,
  not `impact-analyzer/`).
- `arch-visualizer/` looks like an active stub — it isn't; ssot-diagram +
  plan-visualizer replaced it.
- **minimax (M3) test code doesn't account for `ensure_ascii=True`** (P5, 2026-07-10):
  it asserts chip/subtitle text with raw non-ASCII chars (em-dash `—` U+2014,
  middle-dot `·` U+00B7), but `json.dumps(ensure_ascii=True)` escapes them to
  `—`/`·` in the payload → impossible literal match. Verdict: assert
  encoding-invariant fragments, never raw non-ASCII against an escaped payload.
- **minimax (M3) stalls before writing its turn report** on long steps (P5 Step 10:
  `turn_end{stall}`, file written but report absent). Its test code shipped 4 real
  bugs (the escape one above + a self-recursive regression test + missing
  subprocess timeout + a Step-9 fixture sig bug) caught ONLY because the
  orchestrator ran the tests itself rather than trusting the (absent) report.
- **`grep-absent` with a glob that matches zero files is a fail** (`no file
  matches`), same as `grep-present` (Bucket 2, 2026-08-16). A vacuous glob is
  not “the string is absent.”
- **Plan error-path lines must name the exact user-visible string for every
  branch** (Bucket 4 whole-diff, 2026-08-17): wrapping repair writes also
  wrapped fresh `init`, so a new project printed `Cannot repair index (errcode
  undefined)`. Write both labels in the plan, or the worker will follow the
  wrap instruction literally.
- **`=== END REPORT ===` must be an unfenced last line** of the ACP reply and
  of WT-root `IMPLEMENTATION_REPORT.md`. A fenced sentinel, or a report under
  `codegraph/`, fails verify-wave check 4. Judge artifacts go in **this
  worktree’s** `.village/runs/<id>/channel/`, not the parent checkout’s
  `.village/` tree.
- **Done-cell `--strict` exit 0 on a probe that includes `new:` (COLLISION) and
  a directory (MISSING) is impossible** (Bucket 3 mini-RT F1). Write exit **1**
  for the combined probe; put exit 0 on a passing-only plan.
- **A5 swept tokens in `_NONCODE_EXT` (`.json`) never reach the sweep**
  (Bucket 3 mini-RT-2). Use a code-extension pathish token (e.g. `.prisma`).
