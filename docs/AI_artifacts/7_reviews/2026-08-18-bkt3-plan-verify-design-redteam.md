# Red-team — Bucket 3 design (`2026-08-18-bkt3-plan-verify.md`)

_Date:_ 2026-08-18  
_Mode:_ **cross-model** (artifact authored by claude-opus; this review is cursor-grok-46, fresh session, artifact + repo + contracts only). Certifies craft + some shared-judgment misses this lineage can see. **Cannot certify** same-lineage blind spots the author and a same-model reviewer would both miss.  
_Fix:_ nothing. Report-only.

## Steelman

The bug is real and the layer is the right one. `verdict_claim` already owns “what does this claim mean,” `_shared/resolve.py` is a frozen “what code does this token name?” seam, and `STRICT_FAILS` is frozen — so the only honest move is a disk `stat` *inside* the two existing `UNRESOLVED` arms, keyed on a parser-shaped path-only predicate, with `new:` inverted to `COLLISION` so an empty index is not a create-license. Containment (`absolute`/`~` refused, `.resolve()` on both sides, `is_relative_to`, `is_file` not `exists`) matches the grill locks; the `::` and `external:` raw-prefix checks are load-bearing against real parser shapes (`foo.py::` → `symbol=None`; relative `external:` → `external=False`). Putting the helper in `plan_verify.py` rather than `resolve.py` respects the one-surface ceiling. The approach is the cheapest thing that actually stops `--strict` from failing a `touch:` of a file the index never parsed.

## Executive summary

Zero CRITICAL. Two MAJOR (exception contract of `_on_disk`; Constraint 3 unpinned by the automated suite). Option A stays the right shape — revise the helper’s “never raises” story and add one `--db`/out-of-tree plan test before spec. Several MINOR fact/wording nits; none of them overturn the chosen approach.

**Verdict: revise.**

---

## Findings

### M1 — `_on_disk` “Never raises” / P8 is false: `Path.resolve()` raises `RuntimeError` on symlink loops

```
Where: artifact §A1 `_on_disk` (except OSError only) + Risks P8 + CLAUDE.md hook fail-open
Severity: MAJOR
Confidence: VERIFIED
```

**Impact (plain language):** A plan that names a looping symlink under the repo (or a tree that has one) does not get a quiet `MISSING` row. The CLI dies with a traceback instead of exit 0/1/2. The hook does not “return False and continue”; `run_fail_open` swallows the *whole* verify, so every other claim in that plan also vanishes from the transcript — like one bad address on a mailing list causing the whole list to be thrown away.

**Evidence:**

Design §A1:

> Never raises — a hook must not die on a permission error (CLAUDE.md fail-open).
>
> ```python
>     try:
>         root = repo_root.resolve()
>         cand = (root / p).resolve()
>         return cand.is_relative_to(root) and cand.is_file()
>     except OSError:
>         return False
> ```

P8: “`_on_disk` returns False on `OSError`”.

This machine, Python 3.12.13, a two-node symlink loop:

```
symlink loop RuntimeError Symlink loop from '/private/tmp/bkt3-rel-probe/loop/a'
```

`pathlib.Path.resolve` source (same interpreter) explicitly re-raises `RuntimeError` after catching `OSError` with `ELOOP` — so `except OSError` in `_on_disk` **does not see it**.

CLI `main()` (`plan_verify.py:423-433`) has no `run_fail_open` wrapper. Hook `run_fail_open` (`_shared/hookio.py:34-42`) catches `BaseException` and `sys.exit(0)` with **no context** — P8’s “return False on OSError” never runs. R4 discusses out-of-repo symlinks and fail-closed `MISSING`; it does not mention loops or `RuntimeError`.

**Check:**

```sh
python3 - <<'PY'
from pathlib import Path
d = Path('/tmp/bkt3-eloop'); d.mkdir(exist_ok=True)
a, b = d/'a', d/'b'
a.unlink(missing_ok=True); b.unlink(missing_ok=True)
a.symlink_to(b); b.symlink_to(a)
try:
    a.resolve(); print('no raise')
except Exception as e:
    print(type(e).__name__, e)
PY
```

---

### M2 — Constraint 3 (stat the DB’s repo, not the plan’s tree) is load-bearing and A5 never pins it

```
Where: artifact Constraint 3 + A3 + A5 tests 1–16 + Done item 1 vs Done item 3
Severity: MAJOR
Confidence: VERIFIED
```

**Impact (plain language):** The distinctive real use — a plan sitting in `/tmp` checked with `--db` against this repo — is exactly how orchestrators already run the tool (the design’s own probe). Every automated test puts the plan *inside* the fixture repo and never passes `--db`. A worker who derives the stat root by walking up from the **plan file** (the rejected alternative) still greens Done 1. Only the manual `/tmp` probe (Done 3) would catch it; pytest-green workers skip that.

**Evidence:**

Constraint 3:

> The stat root must be the indexed repo root, and that root is derived from the DB, not from the plan file.
> This matters because the plan file may live outside the repo (the probe above ran a plan from `/tmp` against this repo’s DB via `--db`).

Rejected alternative: “Stat root = the plan file’s directory”.

A5 #1–#16: every case uses the in-tree `write_plan(repo, …)` helper (`test_plan_verify.py:82-86`, `TestVerdicts.run` at `:141-143`). A5 #8 (`TestCli`) does not pass `--db`. Live test file today: **zero** `--db` / `repo_root_for` references (`rg --db plan-verifier/test_plan_verify.py` → no matches). The design adds 16 cases and still none of them are “plan outside fixture + `--db` points at fixture + file at fixture root.”

Live probe (this review) confirms the shape is real:

```
$ python3 plan-verifier/plan_verify.py /tmp/bkt3probe/probe-plan.md --db .codegraph/codegraph.db --strict
  touch  docs/TECH_DEBT.md   MISSING   no node or file matches 'docs/TECH_DEBT.md'
EXIT=1
```

`docs/TECH_DEBT.md` exists on disk and is absent from `files.path` (exact and suffix both empty).

**Simulation transcript (audit 3 — lazy executor):**

```
# Honest-lazy verify() misread of “stat root = parent of .codegraph”:
found = find_db(plan_path.resolve().parent)
root = repo_root_for(found) if found else None   # ignores opened --db

# Done 1 / A5: plan is repo/docs/plans/p1-plan.md; find_db hits fixture .codegraph
# → root == fixture root. Tests 1–16 PASS (including #8 CLI, no --db).

# Constraint 3 case (Done 3 probe): plan=/tmp/bkt3probe/probe-plan.md, --db=repo db
# find_db(/tmp/bkt3probe) → None → root None → _on_disk always False
# → touch: docs/TECH_DEBT.md stays MISSING. Intent of Constraint 3 betrayed.
# Pytest-green; only the manual probe fails — and Done 1 does not require it.
```

**Check:** After implementation, a test that must fail the plan-walk root and pass `repo_root_for(db)`:

```sh
# plan in a second tmp dir, --db = fixture db, hooks.json written at fixture root
python3 -m pytest plan-verifier/test_plan_verify.py -k 'out_of_tree or db_flag' -q
```

(No such test is specified in §A5. That absence *is* the finding.)

---

## MINOR (not in the return summary; recorded so they are not lost)

**N1 — Constraint 4 is false.** “Root cannot be recovered from `con`.” `open_db` URI connections still answer `PRAGMA database_list` with the file path (verified this session: `[(0, 'main', '…/codegraph.db')]`). Threading a parameter is still the cleaner API; the “cannot” claim is not.

**N2 — Constraint 7 cites the wrong predicate.** `_PATHISH_HINT` at `_shared/manifest.py:56` is `^[\w./-]+\.[A-Za-z0-9]+$` and does **not** match `prisma/` (`match=False`). `touch: prisma/` is a path claim because `looks_pathish` (`manifest.py:107-108`) adds `or "/" in token`. Behaviour claim is true; citation is wrong. An implementer who only reads the quoted regex could drop directory handling as “not path-only.”

**N3 — P1 vs P4 wording.** Dual-predicate table P1 says “path-only + on disk **must** be OK” with no intent carve-out; P4 says `new:` + on disk **must** be COLLISION. A2’s `intent == "new"` branch is unambiguous and A5 #3 pins it — table P1 is sloppy, not unsatisfiable in code.

**N4 — Done 5 under-amends the frozen verdict table.** Block 3a says the contract is `plan-verifier/design.md`’s verdict table. Done 5 rewrites the `touch:` / `remove:` MISSING clauses only. The table header is still “Check against DB,” and the `new:` row is left as DB-only existence. After A2, both are stale.

**N5 — Consumer row overstates CLI effect.** “fewer false `MISSING`, so fewer false exit-1.” Live probe: `new: docs/TECH_DEBT.md` is today `OK` / would not strict-fail; after A2 it is `COLLISION` ∈ `STRICT_FAILS`. Grill 1-a wants that. The consumer sentence is still wrong as a net claim.

**N6 — `Makefile` / `.env` are not path-only.** `looks_pathish` false (verified); disk fallback never fires. Motivating files all have extensions; freeze is parser-shaped. Document, don’t expand.

---

## Six audits (compressed)

1. **Fact & arithmetic.** Probe output in the artifact matches a live rerun (3 MISSING, `new:` OK, EXIT=1). Python 3.12.13 matches. Line cites for `STRICT_FAILS`, `strict_fail`, `verdict_claim` caller, `repo_root_for`, `parse_entry` `::` / relative-`external:`, `test_new_collision` asserting verdict-only — all hold. Failures: Constraint 4 (PRAGMA), Constraint 7 (regex vs `looks_pathish`), `_on_disk` exception class (M1). Lexical `is_relative_to(root / '../outside.json')` **is** `True` until `.resolve()` — A1’s containment rationale is correct (verified).
2. **Internal consistency.** P1 vs P4 (N3). Option D rejected because `verdict_claim` would lie to direct callers; A2 then adds `repo_root=None` default so a direct caller *still* gets the old answer. One caller exists (`:286`); the default is unnecessary. Not raised as MAJOR — production path is the one caller they will update — but it is the same footgun they used to kill D.
3. **Gaming.** Highest stakes: (a) path-only on-disk → not MISSING — A5 #1/#8 pin; (b) `::` never launders — #14 pins `foo.py::`; (c) containment — #7 and #12 pin absolute and `../` *if written as specified*. Remaining easy betrayal: wrong stat root (M2). Hoist above `resolve` fails #15 only if the worker actually writes `src/db.py` on disk as specified; fixture already has it in `files` (`test_plan_verify.py:64-68`).
4. **Assumption feasibility.** AV-1 one caller: grep = `plan_verify.py:286` only. AV-2 `strict_fail` manifest-only: `:289`. AV-3 `repo_root_for` = `db.parent.parent`: `_shared/db.py:34-36`. AV-5 `foo.py::` → path set / symbol None: verified via `parse_entry`. AV-6 relative `external:` → `external=False`, path = raw: verified. AV-7 index has no `docs/TECH_DEBT.md`: verified. `is_relative_to` exists on 3.12. `ssot-diagram/adrs/0001-…` exists (ADR convention). `docs/rules/` absent as claimed.
5. **Contract compliance.** Grill locks 1-a–5-a and C1 are implemented in A1–A6. Scope Q4-a “not MISSING” is satisfied by `OK` *and* `COLLISION`; the tighter scope sentence “verdict **OK**” is overridden by later grill 1-a — owner-locked, not a defect if 1-a is treated as the amendment. Skeleton Block 1a (don’t widen `resolve`) honored by rejecting B. Block 3b `STRICT_FAILS` honored. Block 3c “file:line for existence verdicts” is bent by grill C1’s exact prose string; no in-repo consumer parses evidence as file:line. R15 / no settings edit: honored. OUT list (Prisma extractor, REUSE relocation, new enum): honored.
6. **Missing-by-construction.** Disk match is exact-join; index file match is exact-then-suffix (`resolve.py:73-77`). `touch: TECH_DEBT.md` with the file at `docs/TECH_DEBT.md` stays MISSING after this bucket; the same basename would suffix-hit if it were indexed. Index-wins (test 15) plus no suffix on disk is a silent capability gap vs “file exists.” Accepted blast-radius skip (R1) is in the scope pre-mortem. No rollback: once plans depend on disk-OK, revert re-breaks `--strict` — the ADR offer names this; not silent. Human-authority: no silent spend/vendor/exposure pick; OQ-2/OQ-3 are at least listed (OQ-3 is also pre-decided in A4 — process nit, not a domain-1–11 value).

---

## Human-authority

No MAJOR silent assumption. Grill already locked the behaviour that creates operating-burden (working-tree-dependent verdicts) and the evidence string. OQ-2/OQ-3 are the remaining user-visible output questions; they are not closed by a hidden default in an unasked domain.

---

## Mode caveat

Cross-model craft review. Mini-RT-4 on this artifact was GREEN on Done-cell gaming; M2 is the disagreement: Done 3 is not an automated pin of Constraint 3. Same-model reviewers who already accepted “the probe is enough” will miss M2.

**Verdict: revise** (two MAJOR). Do not rethink Option A.
