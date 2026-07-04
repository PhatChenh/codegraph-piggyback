# Run report — 2026-07-04 P3 diagram-model extractor

## Summary (plain-language)

Built the diagram-model extractor (P3) — a script that turns the codegraph index
into a deterministic `diagram-model.json` the future renderer and plan-visualizer
will read. Merged to main (commit `ba02a56`), NOT pushed to origin. It's pure
computation, no AI in any verdict; same inputs always produce the same output file.
The implementation (deepseek-v4-flash) wrote the first draft; Claude ran three
review rounds and fixed every finding. Two findings were serious and missed by the
first two rounds — the phase-end red-team caught them: ~660 real call/reference
edges were silently dropped, and the decision signature didn't actually pin to
content (would let stale docs render as trusted). Worth your double-check: run
`python3 ssot-diagram/graph_model.py extract` against mkt_engine and confirm the
output sha256 is `5a1e2156…`, and that `decision_index status` still exits 0.

## Dispatches

| # | Model | Role | Task (one line) | Outcome |
|---|---|---|---|---|
| 1 | deepseek-v4-flash | implement | P3 graph_model.py + tests + golden + config + manifest entry per plan (14 steps) | needed-fixes |
| 2 | writ:writ-plan-reviewer | review | Stage 1 plan-compliance on impl diff | findings-confirmed |
| 3 | writ:writ-code-quality-reviewer | review | Stage 2 code-quality on impl diff (after Stage 1 fixes) | findings-confirmed |
| 4 | writ:writ-red-team | red-team | Phase-end adversarial on full phase diff (after Stage 1+2 fixes) | findings-confirmed |

Outcome key: `needed-fixes` = pass after Claude-applied corrections; `findings-confirmed` = real issues verified against live DB/code, all fixed.

## Decisions made for you (autonomous)

- **Stage 1 fixes applied directly by Claude** (not re-dispatched to deepseek — dsk turns wedge-prone + classifier blocks `dsk say` under auto mode): default `--config`/`--out` paths moved into `ssot-diagram/` subdir (plan Step 2); removed unauthorized `--force` flag from `extract`; `--update-golden` suppressed via `argparse.SUPPRESS`; nano `name` field added (Block 4b FROZEN + Step 7 action 6); pre-extract guard `[:1]` bug fixed to scan ALL decisions (Step 10 action 4); micro id class-dominant `#qname` (Step 6 action 5); collapsed id `nano:+collapsed@micro:<mid>` (Step 7 action 8). Evidence: commit `c6d9d00` → `526227b` (amended).
- **Stage 2 fixes applied directly by Claude**: supersedes → literal `"superseded"` only when it points at a known ADR (Step 9 action 7 — deepseek's `final_status = ss if ss else worst` emitted the superseding ADR's id as the status); per-node `decisions[]` sorted (Block 1 determinism — index-key-order was leaking); `SystemExit` swallow removed (corrupt index now fail-loud via `di.die`, contract C2); dead `not_fresh`→`_`; simplified `target_file` lookup. Evidence: commit `526227b`.
- **Phase-end red-team Criticals fixed directly by Claude** after user escalation chose "fix all 3": (a) edge data-loss — non-function-target nano-level edges now resolve to the target symbol's owning micro (plan Step 8 action 8), recovering ~660 dropped edges incl. all 17 class-instantiates; A16 test rewritten to use a CLASS target (the real pilot shape); (b) decision signature content-pinned via `_sorted_sha256(verified anchors' live sigs)`; (c) `--nano-cap` CLI overrides config (was dead code). Evidence: commit `526227b` (red-team fixes), golden sha256 `5a1e2156…`.
- **Mutation-tested** the fixes: min↔max badge inversion, supersedes revert, decision-sig drift, nano-cap override each FAIL a guard test when the fix is reverted — confirming the tests actually guard the contracts.
- **Model layout NESTED, not flat** — plan Step 11 said "flat lists with pointers" but Block 4a FROZEN says "no flat mode"; the contract wins, deepseek's nested output was correct, the plan text was wrong. (No code change — just a documented deviation.)
- **Config = SEED (not curated)** shipped as the pilot config; curation deferred as owner product-decision (resolves a plan-internal ambiguity: Files list said "create (curated)" but E2E said curation is human/OUTSIDE).
- Tier classification: **B** (stdlib extractor, no auth/money/secrets/data-loss) — full review stack applied.

## Escalations (AskUserQuestion — user decisions)

1. **dsk execution mode** — auto HARD-blocks `dsk start`/`dsk say` as Data Exfiltration (BUG-017, verified 2026-07-04). User chose "notify before each dsk call" + manual-mode approval each turn.
2. **External DeepSeek API** — code (P3 plan + graph_model.py content) leaves the machine to DeepSeek servers. User approved real-code-context.
3. **pytest interpreter** — not in default `python3`; user chose the writ venv (`/Users/phatchenh/.cache/writ/.venv/bin/python -m pytest`).
4. **Worktree hygiene** — repo had dirty tracked + untracked files; user committed+pushed first, then chose the full skill worktree flow (integration worktree `dsk/p3-diagram-model` + per-wave implementer worktree).
5. **Phase-end red-team 3 Critical/Major findings** — user chose fix-all-3: resolve non-fn targets → owning micro; hash anchor sigs (plan recipe); CLI overrides config.
6. **Merge to main** — user chose "merge to main now" (no push, no CLAUDE.md build-progress edit).

## Cost

~119k tokens across 4 dispatches (source: `dsk say` output reported 119049 tokens for the single deepseek-flash implementation turn; the 3 Claude subagent reviews don't surface token counts in their task results).
Band check: 4 dispatches = medium (3–6) → expected 100k–400k. The deepseek turn alone is 119k, Claude reviews add an unmeasured but substantial amount. Within band; no over-band flag. (Agent Village Block E cost-guard not yet running — per-session exact figures will land with that; this is best-effort.)

## Incidents (for retro)

- **glm-5.2 classifier flapping** — the auto-mode safety model was repeatedly unavailable, blocking Bash/Write/dsk-say with "glm-5.2 is temporarily unavailable". Worked around by waiting + retrying; a Monitor probe was needed once to wait for recovery. This is infrastructure instability, not a tooling bug.
- **`dsk say` HARD-blocked under auto mode** as [Data Exfiltration] (repo code → DeepSeek API). Each `dsk say` required the user to switch to manual mode + approve. This is by-design safety, not a bug — but it materially shaped the run: Claude subagent review (no external API) became the reliable path; re-dispatching fix turns to deepseek was not worth the classifier/stall friction.
- **dsk approval=ask path wedged** — `dsk approve` → `dsk wait` → exit 4 (BUG-008 STALL, zero token growth 240s) after the first tool-approval. Recovered with `dsk cancel` (session kept). Switched to `--approval auto` after; subsequent turn ran clean.
- **dsk `DSK_MAX_PAYLOAD` 4096 cap** (BUG-005) — kickoff prompt trimmed to fit; raised `DSK_MAX_PAYLOAD=20000` for the real turn.
- **Fix turn timed out at 10min** (DSK_TURN_TIMEOUT) with no output — the heredoc input may have garbled; Claude applied those fixes directly instead of re-dispatching.

## Deferred (non-blocking)

- Config curation (seed config shipped as-is; owner product-decision).
- `_shared/` extraction stays Phase B per ADR-0001.
- OQ-FOLDER-001 (legacy `0_scout/1_design/…` artifact folder scheme vs the new integer-only `0_draft/1_scout/…`) — deferred post-pipeline.
- OQ-A18 (Windows backslash-path generalization) — unverifiable from one DB; non-blocking under contract C1 (pilot = mkt_engine, Unix).
- OQ-A24 (CI pilot DB possession) — `extract` skip-if-absent posture keeps it non-blocking.

## Next

P4 (narrative sidecar) per `ssot-diagram/roadmap.md`. The P3 golden (`testdata/mkt_engine.model.json`, sha256 `5a1e2156…`) + Block 4 contract are the substrate P4 pins prose to. The content-pinned decision signature (red-team Critical 2 fix) is what makes P4's staleness trust-gate actually work — without that fix, P4 would have rendered stale prose as trusted.
