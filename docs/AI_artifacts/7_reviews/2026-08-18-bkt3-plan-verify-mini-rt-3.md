# Mini-RT re-run 3 — Bucket 3 design (post F-1..F-4 patch)

_Date:_ 2026-08-18 · _Target:_ `docs/AI_artifacts/3_design/2026-08-18-bkt3-plan-verify.md` (patched)
_Prior:_ `docs/AI_artifacts/7_reviews/2026-08-18-bkt3-plan-verify-mini-rt-2.md` (F-1..F-4)
_Mode:_ mini-RT re-run 3 (three passes, independent — prior report not reused as truth)
_Read-set:_ design §A1–A6 + §Done + §matrix + §Constraints/AV; actual code
(`plan-verifier/plan_verify.py:76-110,112-125,137-190,208-303,314-359,371-433`,
`_shared/manifest.py:107-134`, `_shared/db.py:34-47`, `plan-verifier/test_plan_verify.py` full).
All design quotes in §A5/#13 and §A2 verified against on-disk code, not taken on trust.

**Verdict: NOT green — 1 finding must be fixed before dispatch, 1 more should be.**

Prior F-1..F-4 are all resolved (verified against code, not on trust). Two new findings:

- **F-5 (must fix)** — the placement guard the design claims ("test 2 fails loudly if a worker
  hoists it") is false; no test distinguishes a correctly-placed fallback from a hoisted one.
- **F-6 (should fix)** — `_path_only` does not exclude `external:`-prefixed raw entries; AV-6 /
  Constraint 9's "external: claims never reach the fallback" is false for the relative form.

---

## Section 1 — Done-cell proxy audit

| Done | Verdict | Note |
|---|---|---|
| 1 (pytest plan-verifier, 14 cases) | **WEAK** | 13/14 are direct behavior pins (evidence equality #1/#3/#4, laundering #2, dir→MISSING #5, absent→MISSING #6, absolute-refused #7, CLI exit-0 #8, REUSE normalize #9/#10, warn-only #11, `../`-escape #12, swept-on-disk #13, empty-`::` guard #14). **#13 is now real**: `.prisma` is NOT in `_NONCODE_EXT` (`plan_verify.py:108-109` = md/json/yaml/yml/lock/log/txt/csv/html/svg/png), so the token survives the sweep filter and reaches `_on_disk` — F-1 fixed. **#14 pins the empty-`::` guard** — F-2 fixed. **Blind spot:** no case exercises an *indexed* path-only claim (path-only + file present in the DB's `files` table + on disk). A hoisted implementation (fallback before the resolve) passes all 14 → F-5. |
| 2 (whole-repo no NEW) | WEAK-but-pinned | Baseline now recorded in the Done cell ("the 3 existing `TestGoldenLive` pilot-drift failures… exactly those 3 and nothing else"), so "NEW" is computable. Still eyeball-verified, not machine-pinned — F-3 fixed, residual proxy is inherent. |
| 3 (audit probe) | PASS | Probe outputs are direct behavior checks; combined exit-1 is arithmetically forced (`new:`→COLLISION ∈ `STRICT_FAILS` at `:80`, `touch: docs/`→MISSING, `strict_fail` reads manifest only at `:289`, CLI exits at `:433`). **Gap:** Done 3's expected-output list covers only the four `docs/TECH_DEBT.md`/`docs/` rows; the probe's fifth row (`touch: plan-verifier/plan_verify.py` → `OK … (1 callers)`, the one row that WOULD catch a hoist) is absent from the Done-cell expectations. |
| 4 (ADR states four rules) | WEAK | File-existence proxy for content. The four rules a/b/c/d are now quoted verbatim in the Done cell so an honest reviewer can eye-check; still no assertion — F-4 persists (inherent to docs). |
| 5 (design.md verdict table) | WEAK | Grep-able cell proxy; the exact row text the amendment must produce is now specified. F-4 persists. |

## Section 2 — Gaming sim (honest-but-lazy executor, one path per cell)

1. **Hoist the fallback (Done 1 / blast preservation) — real path.** Implement `_on_disk` +
   `_path_only` at the TOP of `verdict_claim` (before the resolve at `plan_verify.py:215-216`),
   same two branches. Every one of the 14 §A5 cases passes: #2/#14 are `::`-claims, excluded by
   `_path_only` regardless of placement; #1/#3/#4/#5/#6/#7/#12/#13 produce identical verdicts hoisted
   vs in-UNRESOLVED. What the hoist silently breaks: a path-only claim on an **indexed** file
   (`touch: src/db.py`, 12 callers in the fixture) short-circuits to `OK  on disk, not in index` and
   never reaches the caller-count / `UNACKNOWLEDGED-BLAST` computation — blast masking for every
   path-only claim on a parsed file. The design's stated defense — "§A2 pins the exact insertion
   points … and test 2 fails loudly if a worker hoists it" — is **false**: test 2 is
   `prisma/schema.prisma::Asset`, excluded by the `_path_only` predicate before placement matters.
   Done 3's probe could catch it via the `plan_verify.py (1 callers)` row, but that row is not in
   Done 3's expected-output list. **Green without delivering the design's placement guarantee.**
2. **ADR (Done 4)** — write a stub `plan-verifier/adrs/0001-*.md` → passes.
3. **design.md table (Done 5)** — add a one-line table note → passes.
4. **"no NEW" (Done 2)** — run whole suite, see exactly the 3 recorded `TestGoldenLive` failures,
   report "no NEW". Harder than pre-patch (baseline is recorded) but still eyeball-only.

Not gameable: core manifest fallback verdicts + exact evidence string (#1/#3/#4), laundering
guard (#2, non-empty symbol), containment (#7 absolute, #12 `../`), empty-`::` guard (#14),
REUSE normalization (#9/#10), swept-on-disk wiring (#13 — fails if the swept loop path is skipped).

## Section 3 — Chain contradictions (capability matrix)

**Matrix rows: no contradiction.** Hook row enforcement *no* + the design makes no blocking claim
+ `hook_main` returns 0 unconditionally (`:390`) → no hop-that-must-BLOCK sits on a *no* row. CLI
row *yes* consistent with Done 3's exit-1. Output types match: `repo_root_for(db) -> Path`
(`_shared/db.py:36`) fits `verdict_claim(..., repo_root: Path | None = None)`; `_on_disk` is only
reached under `_path_only`, which guarantees non-empty `str` `claim.path`. Payload kinds match:
`emit_context` receives the joined string → `additionalContext`; `--json` gains only a new evidence
*value*, no field renamed.

**One internal contradiction, off the matrix — F-6.** Constraint 9 and AV-6 claim "`external:`
claims already short-circuit before any resolution, so the disk fallback must not fire for them."
True only for the **absolute** form (`external:` flag set at `manifest.py:121-126`). The **relative**
form (`external: src/local.py`) falls through parse_entry (`manifest.py:127-128`) with `external =
False`, so `_path_only`'s `not claim.external` is True, `"::" not in claim.raw` is True → the
fallback fires when `src/local.py` exists on disk → `MISSING` silently flips to `OK` (touch/remove)
or `OK`→`COLLISION` (new) for a claim class the design says can never reach the fallback. The
existing pin (`test_external_relative_no_short_circuit`) survives only because the fixture root
contains no `src/local.py` on disk. Fix: `_path_only` must also reject `raw.startswith("external:")`.

**Nit (not a contradiction):** the pre-dispatch consumer row "fewer false `MISSING`, so fewer false
exit-1" is partial — `new:` path-only on-disk flips `OK → COLLISION`, a *new* strict failure for a
claim shape that previously passed. Deliberate (grill C-07, Done 3 exit-1 forced), but the "fewer"
phrasing understates the CLI surface's change.

---

## Prior-finding disposition

| Prior | Status | Evidence |
|---|---|---|
| F-1 swept token vacuous | **FIXED** | A5 #13 now uses `probes/schema.prisma`; verified `.prisma` ∉ `_NONCODE_EXT` (`plan_verify.py:108-109`). Token survives sweep, reaches `_on_disk`; a worker skipping the swept wiring fails the test. |
| F-2 empty-`::` laundering | **FIXED** | `_path_only` now carries `"::" not in claim.raw`; AV-5 rewritten correctly; #14 pins `touch: foo.py::` → MISSING. Verified `parse_entry` maps empty RHS to `symbol=None` (`manifest.py:129-131`), so the raw-string check is the load-bearing guard. |
| F-3 unpinned baseline | **FIXED** | Done 2 records the exact pre-change known-fail set (3 `TestGoldenLive`) and defines "NEW". |
| F-4 doc-proxy cells | **PARTIAL** | Done 4 quotes the four rules verbatim; Done 5 quotes the target table row. Content still unpinned by any test (inherent to docs); listed as residual WEAK proxies. |

---

_F-5 must be fixed before dispatch — a claimed placement guarantee is unpinned and the stated
defense (test 2) does not hold, so a worker can hoist the fallback, pass every test, and silently
mask `UNACKNOWLEDGED-BLAST` for indexed path-only claims. Cheap fix: one test — create
`repo/src/db.py` on disk (it is already in the fixture's `files` table), plan `touch: src/db.py`,
assert `BLAST` (not `OK  on disk, not in index`). F-6 is a one-line predicate tightening +
one test; ships silently today if unpatched._
