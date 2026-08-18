# Mini-RT — 2026-08-18-bkt3-plan-verify design

_Date:_ 2026-08-18 · _Target:_ `docs/AI_artifacts/3_design/2026-08-18-bkt3-plan-verify.md`
_Mode:_ mini-RT (three passes: Done-cell proxy audit, gaming sim, matrix chain-contradiction)
_Read-set:_ design §Done + §Surface-capability matrix + §Chosen Approach + the actual code it quotes
(`plan-verifier/plan_verify.py:60-340,395-437`, `_shared/manifest.py:107-134`, `_shared/db.py:34-47`,
`plan-verifier/test_plan_verify.py:140-219`)

**Verdict: NOT green — 2 findings must be fixed before dispatch, 3 more should be.**

---

## F1 — CRITICAL — Done item 3's "exit code 0 under `--strict`" is arithmetically impossible

Done item 3 asserts the audit probe (design §pre-dispatch audit, line 55) rerun after the change
prints the four on-disk rows AND `exit code 0 under --strict`. It cannot.

The probe plan claims:
- `new: docs/TECH_DEBT.md` → on disk → **COLLISION** (A2 new: branch: path-only + `_on_disk` → COLLISION)
- `touch: docs/` → directory → **MISSING** (`is_file()` false)
- `touch: docs/TECH_DEBT.md` → OK, `remove: docs/TECH_DEBT.md` → OK, `plan_verify.py` → OK

`STRICT_FAILS = {MISSING, COLLISION, BLOCKED}` (constraint 1, `plan_verify.py:80`); COLLISION is in it.
`strict_fail = [c for c in manifest.claims if c.verdict in STRICT_FAILS]` (constraint 2,
`plan_verify.py:289`). CLI: `sys.exit(1 if (args.strict and result["strict_fail"]) else 0)`
(`plan_verify.py:433`). The probe's COLLISION + MISSING are both manifest claims → `strict_fail`
non-empty → **exit 1, never 0**.

Verified against the code, not just the doc. The rows listed in Done item 3 are all correct
descriptions of the new behaviour; only the exit-code tail is wrong.

### Chain (matrix row 2 ⟂ Done 3)
Surface-capability matrix row 2 (CLI exit code, **enforcing**) + constraint 1 (`COLLISION ∈ STRICT_FAILS`)
+ constraint 2 (strict reads manifest claims) + A2 (`new:` on-disk → COLLISION; directory → MISSING)
+ the probe plan (contains a `new:` of an existing file and a `touch: docs/`) ⟹ Done item 3's
"exit code 0" is unreachable. The matrix is internally consistent — the contradiction is between
matrix row 2's enforcement semantics and the Done cell that claims exit 0 on a plan that strict-fails.

### Gaming sim: probe surgery
A worker facing an impossible Done cell has two exits: (a) fail the check honestly, or (b) silently
edit the probe plan to the two passing rows (`touch:` + `remove:` of `docs/TECH_DEBT.md`) → exit 0,
declare Done. Option (b) never exercises the two most important new behaviours (`new:` → COLLISION,
directory → MISSING) — the exact behaviours the probe was meant to pin. The Done cell does not quote
the probe plan verbatim, so nothing stops the surgery.

### Fix (pick one)
- **Rewrite Done item 3** to assert exit **1** with the full probe, OR
- **Trim the probe** to the passing claims (`touch:`/`remove:` of `docs/TECH_DEBT.md` + the indexed
  py) and assert exit 0, moving `new:`→COLLISION and `touch: docs/`→MISSING into §A5 tests only
  (they already are — A5 #3 and #5). The former keeps the probe honest about both directions;
  the latter is fine because A5 #3/#5 pin those verdicts. Either way the Done cell must name which.

---

## F2 — HIGH — `../` containment is untested; the load-bearing `.resolve()` can be dropped without failing a single A5 test

R3 claims traversal (`../../etc/passwd`) is handled by `.resolve()` + `is_relative_to(root)`. The
§A5 test table pins only the **absolute** case (test 7, `touch: /etc/passwd` → MISSING). No test
covers `../` or `~/`.

Empirically verified (Python 3.12):

```
root = Path('/a/b'); cand = root / '../secrets.json'
cand.is_relative_to(root)          → True   (lexical; '..' is just a part)
cand.resolve().is_relative_to(root) → False  (the guard that actually works)
```

Without `.resolve()`, `(root / '../secrets.json')` passes `is_relative_to` lexically, and the
subsequent `is_file()` resolves `..` at the OS level → a real out-of-repo file answers True →
verdict OK. The absolute-refusal check (`p.is_absolute()` / `rel.startswith("~")`) does not catch
`../`, so a worker who implements `_on_disk` without `.resolve()` passes **all 11 A5 tests** and
opens a containment hole. `.resolve()` is the single line R3 depends on and nothing verifies it.

### Fix
Add to §A5: `touch: ../outside.json` where the file exists one level above the fixture root →
`MISSING` (and optionally a `touch: ~/secrets.json` case). Without this, the containment claim is
faith, not a test.

---

## F3 — MEDIUM — swept-on-disk fallback is claimed but untested

Design asserts "Swept claims inherit the fallback, harmlessly" (§Implications) — a backticked
pathish token existing on disk renders OK and is suppressed (`plan_verify.py:324`). §A5 has no swept
case. The only sweep test (`test_swept_tokens_get_verdicts_but_never_strict_fail`) uses `ghost_helper`
(a bare identifier → symbol path, untouched by the fallback) and `validate_token` (symbol). Neither
exercises a swept **path-only** token.

Consequence: a worker wiring the fallback for swept tokens wrong (or not at all — e.g. sweeping
through a separate code path that never calls `_on_disk`) passes every test while the design's
claimed noise-reduction silently doesn't happen. Low stakes (swept never gates, constraint 2), but
the design sells it as a benefit with no pin. Add one case: prose containing `` `hooks.json` `` with
the file on disk → zero rows rendered, `strict_fail` empty.

---

## F4 — LOW–MED — A2 `new:` snippet omits the dynamic-names note block; verbatim implementation drops it

Current `plan_verify.py:224-227` — the `if claim.symbol and claim.symbol in dynamic_names` note — sits
inside `if claim.intent == "new":`, after the resolved/UNRESOLVED arms, before the `return`. A2's
replacement snippet shows only the restructured if/else and marks the resolved arm `...unchanged...`;
the note block appears nowhere. A worker implementing the shown block verbatim deletes the note.

Backstop exists: `test_new_ok_and_dynamic_note` (`new: src/auth.py::refresh_token` → asserts the
`unresolved_refs` note) fails if the block drops, so Done item 1 catches it. But this is exactly the
BUG-024 failure shape the repo records ("wrap the surrounding lines or the worker follows the snippet
literally"). Pin it: state that `:224-227` survives unchanged, or show it in the snippet.

---

## F5 — LOW — Done item 4 resolves OQ-1 unilaterally

OQ-1 leaves the ADR location open (tool-local vs repo-level `docs/architecture/`) with a
recommendation. Done item 4 hard-codes `plan-verifier/adrs/0001-…`, silently foreclosing the
repo-level option without a recorded owner decision. If tool-local is the call, that's fine — but the
design presents OQ-1 as open, so Done 4 and OQ-1 contradict on whether a decision is pending. Either
close OQ-1 in the design, or drop the path from Done 4.

---

## Done-cell proxy audit (per cell)

| Done | Verdict | Note |
|---|---|---|
| 1 | PASS | 11 §A5 cases pin touch-OK, symbol-laundering-guard (#2), new-COLUSION (#3), remove-OK (#4), directory-MISSING (#5), ghost (#6), absolute-refused (#7), CLI exit-0 (#8), REUSE normalize (#9/10), warn-only (#11). Missing `../` (F2) and swept-on-disk (F3). |
| 2 | WEAK | "No NEW failures vs pre-change baseline" — baseline not recorded in the design; a worker eyeballing post-change output can't distinguish pre-existing `TestGoldenLive` drift (3 known) from new. Recommend a recorded baseline or explicit exception list. |
| 3 | **FAIL** | Exit-0 unreachable (F1). |
| 4 | WEAK | Content-presence proxy; a vacuous ADR passes. Also forecloses OQ-1 (F5). |
| 5 | PASS | Contract-of-record table update is the right place; grep-able. |

## Gaming sim — what survives

- **Not gameable:** ON_DISK_EVIDENCE exact string (equality-asserted in A5 #1/#3/#4); `new:`→COLLISION
  verdict (#3); `path::Symbol` laundering guard (#2) — `parse_entry` puts bare identifiers in `symbol`
  (`manifest.py:134`) and `::` sets both parts, so `_path_only` (`path && !symbol && !external`) cannot
  fire for either; directory→MISSING (#5). The predicate is sound against the real parser.
- **Gameable:** exit-0 via probe surgery (F1); `.resolve()` drop via untested `../` (F2); dynamic-note
  drop (F4, backstopped); swept-on-disk silent no-op (F3).

## Open-question cross-check

- OQ-1: contradicted by Done 4 (F5).
- OQ-2: "no" recommendation is consistent — per-row evidence already carries the truth.
- OQ-3: normalized identifier in REUSE-DROPPED — consistent with A4; the design already flags it as an
  unlocked user-visible string change.

---

_F1 must be resolved before dispatch (the Done cell is impossible as written and invites probe surgery).
F2 before implementation (containment hole is untestable-away). F3/F4/F5 are cheap design-text pins._
