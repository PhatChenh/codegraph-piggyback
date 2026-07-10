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
5b amendment owner-ratified). **P5 HTML renderer IMPLEMENTATION COMPLETE 2026-07-10**
(branch `dsk/p5-html-renderer`, 12 commits, NOT merged). 11 steps shipped via
av-orchestrate (minimax worker seats on Steps 5/8/9/10 — glm orchestrator
inline-reviewing tier-A + authoring the verbatim steps): `render.py` +
`render_template.html` + `test_render.py` (24 tests) + 3 font binaries + OFL +
4 fixtures + `ssot-render` manifest entry + OTHER-FILE addendum note.
**129 pytest pass / 3 pre-existing `TestGoldenLive` pilot-drift (0 NEW)**; golden
model sha `56df3d86…` intact; render E2E = 339KB self-contained,
byte-deterministic, zero network. **NEXT: live painter E2E browser check
(deferred — click/hover/pan/zoom not headlessly assertable) + merge to main.**
av-orchestrate gaps logged: BUG-023 (staged-cwd unreachable → sequential-only),
BUG-024 (verify-wave category-21 phase-scoped → per-wave gate can't pass mid-phase).
`_shared/` extraction SHIPPED (commit `82287f9`, alongside plan-verifier)
— `_shared/db.py`/`sig.py`/`resolve.py`/`queries.py`/`budget.py`/`hookio.py`/
`manifest.py` live at repo root; ADR-0001's "defer to Phase B" decision is
SUPERSEDED (dated note added to the ADR). See `ssot-diagram/STATE.md`** for the
P5 pick-up point. Everything else: specced in `<tool>/design.md`, build order
in `docs/roadmap/roadmap.md`.

## What AI Gets Wrong

- README's "Planned scripts per tool" section is legacy; BLUEPRINT + per-tool
  `design.md` supersede it (e.g. commit-time impact checking is `impact-precommit/`,
  not `impact-analyzer/`).
- `arch-visualizer/` looks like an active stub — it isn't; ssot-diagram +
  plan-visualizer replaced it.
