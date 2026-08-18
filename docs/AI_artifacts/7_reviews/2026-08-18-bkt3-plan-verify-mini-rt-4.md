# Mini-RT re-run 4 — Bucket 3 design (post F-5/F-6 patch)

_Date:_ 2026-08-18 · _Target:_ `docs/AI_artifacts/3_design/2026-08-18-bkt3-plan-verify.md` (patched)
_Prior:_ `docs/AI_artifacts/7_reviews/2026-08-18-bkt3-plan-verify-mini-rt-3.md` (F-5, F-6)
_Mode:_ mini-RT re-run 4 (three questions; prior report not reused as truth)
_Read-set:_ design full; `plan-verifier/plan_verify.py` (constants, sweep, spec-reuse, verdict_claim,
verify, render/to_json, hook_main, main); `_shared/manifest.py:107-176`; `_shared/resolve.py` full;
`_shared/db.py` full; `_shared/queries.py` full; `plan-verifier/test_plan_verify.py` full.
All design quotes checked against on-disk code, not taken on trust.

**Verdict: GREEN — zero findings in all three sections.**

---

## Section 1 — Done-cell proxy audit

| Done | Verdict | Note |
|---|---|---|
| 1 (pytest plan-verifier, 16 cases) | **STRONG — no proxy** | All 16 §A5 cases are direct behavior pins, re-verified against code. High-risk pins: **#15** (hoist guard) works with the existing fixture — `src/db.py` IS in the fixture `files` table (`test_plan_verify.py:65`), `resolve("src/db.py")` → `_resolve_file` → UNIQUE → `callers_of_name(con,"db")` → 0 callers → evidence `src/db.py (0 callers)`, never `on disk, not in index`; a top-hoist fires `_on_disk` and emits the on-disk evidence → test fails. **#13** (`probes/schema.prisma`) is real: `.prisma` ∉ `_NONCODE_EXT` (`plan_verify.py:108-109`), token survives the sweep filter at `:120`, verdict via `:285-286` loop, row suppressed at `:324`, `strict_fail` empty at `:289`. **#14** (`foo.py::`) pins the raw-`::` guard — `parse_entry` maps empty RHS to `symbol=None` (`manifest.py:129-131`), so `_path_only`'s `"::" not in claim.raw` is the load-bearing check. **#16** relative-`external:` meta_problem exists (`manifest.py:156-158`) and `_path_only`'s raw-prefix check excludes the claim. |
| 2 (whole-repo no NEW) | WEAK-but-pinned (inherent) | Baseline quoted ("exactly those 3 `TestGoldenLive`…"), "NEW" computable. Eyeball-only; no test can pin a whole-suite run. Not a finding (residual docs-are-eyeball). |
| 3 (audit probe) | PASS | Four expected rows are direct E2E checks of the fallback (touch→OK, new→COLLISION, remove→OK, dir→MISSING) and the combined exit-1 is arithmetically forced (`COLLISION`,`MISSING` ∈ `STRICT_FAILS` at `:80`; `strict_fail` reads manifest only at `:289`; exit at `:433`). The probe's fifth row (`touch: plan-verifier/plan_verify.py` → OK (1 callers)) remains absent from the Done-cell expected list — but the hoist is now pinned by test 15, so this is not load-bearing. Not a finding. |
| 4 (ADR four rules) | WEAK (exempt) | Rules a/b/c/d quoted verbatim in the Done cell; honest reviewer eye-checks. Not a finding. |
| 5 (design.md table) | WEAK (exempt) | Target row text quoted verbatim; eye-checkable. Not a finding. |

## Section 2 — Gaming sim (honest-but-lazy, one path per cell)

- **Done 1 — no path.** Every case is discrimination-based; the laziest correct implementation is the design itself. A top-hoist fails **#15**. `_on_disk` returning `exists()` (not `is_file()`) fails **#5**. Returning `True` unconditionally fails **#5/#6/#7/#12**. A lexical (unresolved) containment check fails **#12** (`root/../outside.json` is lexically `is_relative_to(root)` until `.resolve()`). Swept-OK-everywhere fails the existing `test_swept_tokens_get_verdicts_but_never_strict_fail` (`ghost_helper` → MISSING, `test_plan_verify.py:195`). REUSE normalization is forced by **#9/#10**. The shared `verdict_claim` path means the hook surface inherits the fallback structurally (Option A), with no separate buildable split.
- **Done 2 — no honest path.** Running the whole suite and reporting the 3 recorded failures truthfully is the honest-lazy minimum; the only "shortcut" (skip the run) is dishonest.
- **Done 3 — no path.** The four expected rows require the fallback; without it they print MISSING and the probe visibly fails.
- **Done 4 — stub-file path exists but exempt:** write a 5-line ADR restating the four rules → passes all automated checks; the Done cell quotes the rules so a reviewer can eye-check. Per the mini-RT exemption, not a finding.
- **Done 5 — one-line-table-note path exists but exempt:** add the quoted verdict-cell text → passes; eye-checkable target quoted in the cell. Not a finding.

## Section 3 — Chain contradictions (capability matrix)

**No contradiction.**
- **No hop-that-must-BLOCK on a *no* row.** The only *no*-enforcement surface (PostToolUse hook) is advisory: `hook_main` returns 0 on every path (`plan_verify.py:371-390`) and is wrapped in `run_fail_open` (`:410`). The design makes no blocking claim for it; the only *yes* surface (CLI `--strict`) is where blocking lives (`:433`) and is consistent with Done 3's exit-1.
- **Output types match.** `repo_root_for(db) -> Path` (`db.py:34-36`) fits `verdict_claim(..., repo_root: Path | None = None)`; `_path_only` guarantees a non-empty `str` `claim.path` before `_on_disk(root, claim.path)`; `ON_DISK_EVIDENCE` is a str assigned to `claim.evidence` (str). `resolve` states (UNIQUE/AMBIGUOUS/UNRESOLVED) match the branch predicates.
- **Payload kinds fit the surfaces.** The new evidence *value* flows through `render` (str row), `to_json` (`evidence` str field, `:345-359`), and `emit_context` (`additionalContext` str, `hookio.py:24-31`). The two COLLISION evidence shapes (`exists: …` vs `on disk, not in index`) are safe: `test_new_collision` asserts the verdict only (`test_plan_verify.py:167`), and `diff_verify` shares only the parser, never verdict evidence.
- **F-6 resolved.** Relative `external: src/local.py` falls through `parse_entry` with `external=False` (`manifest.py:127-128`); `_path_only`'s `not claim.raw.lstrip().startswith("external:")` excludes it, so `_on_disk` can never fire for that claim class; test 16 pins it. Constraint 9 / AV-6 now hold.

---

## Prior-finding disposition

| Prior | Status | Evidence |
|---|---|---|
| F-5 (placement guard false) | **FIXED** | Test 15 pins the index-wins property for an indexed path-only claim; verified the fixture's `files` table already carries `src/db.py`, so the test is realistic as specified. A top-hoist emits on-disk evidence and fails #15. |
| F-6 (relative external reaches fallback) | **FIXED** | `_path_only` raw-prefix check; test 16 pins MISSING + the `external: value must be an absolute path` meta_problem (emitted at `manifest.py:156-158`). |

**Residual nit (carried from RT-3, not a finding):** the pre-dispatch consumer row "fewer false `MISSING`, so fewer false exit-1" understates the CLI surface's change — `new:` path-only on-disk flips `OK → COLLISION`, a new strict failure. The design is explicit about this elsewhere (Constraint 7, P4, A5 #3, Done 3's forced exit-1), so it is an under-characterization, not a contradiction.
