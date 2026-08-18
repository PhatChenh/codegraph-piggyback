# Phase Bucket 3 — plan_verify disk-stat for path-only claims + REUSE name-normalize

_Date:_ 2026-08-18
_Design:_ `docs/AI_artifacts/3_design/2026-08-18-bkt3-plan-verify.md` (Option A)
_Grill:_ `docs/AI_artifacts/_handoff/2026-08-18-bkt3-plan-verify-grill.md` (LOCKED 2026-08-18)
_RT:_ `docs/AI_artifacts/7_reviews/2026-08-18-bkt3-plan-verify-design-redteam.md` (0 CRITICAL; M1–M2 + N1–N6 absorbed here as MUSTs)
_Scope:_ `docs/AI_artifacts/_scope/2026-08-16-feedback-bugs-scope.md` Bucket 3 = ITEM-4+6
_Surface:_ `plan-verifier/plan_verify.py`. One phase (grill: split forbidden).
_TD-01:_ OUT of this bucket (`docs/TECH_DEBT.md`).

## Purpose

`plan_verify` currently treats every unresolved claim as absent. Path-only `touch:` / `remove:` of a regular file that sits on disk but was never parsed into the index (hooks.json, prisma/schema.prisma, docs/*.md) therefore verdicts `MISSING` and fails `--strict`. This phase adds a disk fallback that fires only on `UNRESOLVED` **path-only** claims, rooted at the indexed repo root: touch/remove → `OK` with evidence exactly `on disk, not in index`; `new:` → `COLLISION` with the same evidence; `::Symbol` and directories stay index-bound. Spec reuse-row names are reduced to the identifier before `(`, with trailing `…` / `...` stripped, so spec `runFalQueue(...)` matches plan `runFalQueue`. After this phase, orchestrators stop hand-patching those path-only rows, and `new:` of a file that already exists on disk is an honest collision.

## Pre-dispatch audit

### 1. Consumer list per changed identifier

Changed identifiers live in `plan-verifier/plan_verify.py` only (one surface). `diff_verify` shares the **parser**, not verdicts.

| Identifier | Consumers | Affected? |
|---|---|---|
| `verdict_claim` | `verify` (one call site); tests via `pv.verify` | YES — new `repo_root` param; two `UNRESOLVED` arms gain disk fallback |
| `verify` | CLI `main()`, `hook_main` | YES — computes `repo_root_for(db)` once and threads it |
| `check_spec_reuse` | `verify` when `--spec` | YES — matches/reports the normalized identifier |
| `STRICT_FAILS` | `verify` → CLI `--strict` exit | NO member added. Mix of fewer false `MISSING` (touch/remove path-only on-disk) **and** new `COLLISION` strict-fails (`new:` path-only on-disk). **MUST NOT claim net-fewer CLI failures.** |
| `ON_DISK_EVIDENCE` (new) | `--json` `manifest[].evidence`; rendered table; hook `render(..., problems_only=True)` | YES — new evidence string value; no field added or renamed |
| `parse_entry` / `looks_pathish` / `resolve` | unchanged | NO — fallback is verdict-layer only |
| Manifest hook `plan-verifier` | PostToolUse Write\|Edit, advisory, always exit 0 | YES — fewer advisory `MISSING` rows on touch/remove; new `COLLISION` rows on `new:` of on-disk files. Hook still cannot block a Write. |

### 2. Recorded command + output per scope claim

Scope: path-only `touch:` of a real on-disk file verdicts `MISSING` and fails `--strict` today. Design audit probe (carried; not re-derived):

```
$ python3 plan-verifier/plan_verify.py /tmp/bkt3probe/probe-plan.md --db .codegraph/codegraph.db --strict
── PLAN-VERIFY: /tmp/bkt3probe/probe-plan.md ── 5 claims (5 manifest, 0 swept)
  touch  docs/TECH_DEBT.md                          MISSING                no node or file matches 'docs/TECH_DEBT.md'
  new    docs/TECH_DEBT.md                          OK                     no existing match
  remove docs/TECH_DEBT.md                          MISSING                no node or file matches 'docs/TECH_DEBT.md'
  touch  docs/                                      MISSING                no node or file matches 'docs/'
  touch  plan-verifier/plan_verify.py               OK                     plan-verifier/plan_verify.py (1 callers)
── verdict: FAIL (3 MISSING) ──
EXIT=1
```

That run also shows why CLI failure count is not monotonically down: after this phase the same probe’s `new:` becomes `COLLISION` ∈ `STRICT_FAILS` (grill 1-a), so combined `--strict` exit stays 1.

Python on this machine: 3.12.13 (`Path.is_relative_to` present; `Path.resolve()` on a two-node symlink loop raises `RuntimeError`, verified this session).

### 3. One contradiction looked for and not found

Looked for an existing test that asserts a path-only claim whose file exists on disk is `MISSING` (which would make the fix a rewrite). `plan-verifier/test_plan_verify.py` MISSING asserts are symbol-shaped or non-existent-path-shaped (`src/auth.py::ghost_func`, `ghost_helper`, `src/auth.py::ghost`, relative `external: src/local.py`). Contradiction not found — tests are additive.

Looked for `--db` / out-of-tree-plan coverage of Constraint 3: **absent** (RT M2). That absence is why OQ-RT-M2 is a MUST test, not a probe-only Done cell.

## Already built (reuse, do not rebuild)

| Function/Module | Location | What it does | How this spec uses it | Depth |
|---|---|---|---|---|
| Verdict constants + `STRICT_FAILS` | `plan-verifier/plan_verify.py:76-81` | `OK/MISSING/AMBIGUOUS/COLLISION/BLOCKED/UNACKNOWLEDGED-BLAST`; strict set `{MISSING, COLLISION, BLOCKED}` | reuse as-is; **no new member** | deep |
| `verdict_claim` | `plan-verifier/plan_verify.py:208-261` | all verdict policy | extend the two `UNRESOLVED` arms only; do not hoist above `resolve` | deep |
| `verify` | `plan-verifier/plan_verify.py:264-303` | open db, loop claims, `strict_fail` from **manifest** only | one new line: `root = repo_root_for(db)` passed into `verdict_claim` | deep |
| `check_spec_reuse` / `spec_reuse_rows` | `plan-verifier/plan_verify.py:137-190` | substring match; warn-only `REUSE-DROPPED` | normalize the needle inside the existing loop; parser of the spec table stays | shallow (thin loop) |
| `sweep_tokens` / `_NONCODE_EXT` | `plan-verifier/plan_verify.py:112-125` / `:108-109` | backticked tokens; drops `.json`/`.md`/… | swept inherits fallback; test 13 must use `.prisma` not `.json` | deep |
| `render` / `to_json` | `plan-verifier/plan_verify.py:314-359` | table + json; swept OK suppressed | new evidence string appears; no schema change | deep |
| `hook_main` | `plan-verifier/plan_verify.py:371-390` | advisory; always `return 0` | inherits via `verify`; do not wrap a second fail-open inside `_on_disk`’s callers | deep |
| `run_fail_open` | `_shared/hookio.py:34-42` | catches `BaseException`, `sys.exit(0)`, **no context** | why `_on_disk` must not raise: a raise here drops the rest of the plan | deep |
| CLI `main` | `plan-verifier/plan_verify.py:395-433` | `--strict` / `--json` / `--db` / `--hook` | `--db` is the Constraint 3 door; CLI has **no** `run_fail_open` — a raise is a traceback | deep |
| `repo_root_for` / `open_db` / `find_db` | `_shared/db.py:22-47` | root = `db.parent.parent`; RO URI connect | **reuse** `repo_root_for(db)` of the **opened** db (not `find_db(plan)`) | deep |
| `resolve` / `_resolve_file` / `looks_pathish` | `_shared/resolve.py:1-80` | frozen seam; files table only; `or "/" in token` | **do not edit**; fallback is verdict-layer | deep (frozen 1a) |
| `parse_entry` / `Claim` / `looks_pathish` | `_shared/manifest.py:107-134` | path/symbol/external split | `_path_only` is built on this shape; do not widen the parser | deep |
| Test fixture `repo` / `write_plan` / `make_db` | `plan-verifier/test_plan_verify.py:22-86` | synthetic db under `tmp_path` (= stat root) | new on-disk files sit next to the db; OQ-RT-M2 must **not** use in-tree `write_plan` for the plan file | deep |
| `TestVerdicts` / `TestCli` / `TestSpecReuse` / `TestExternal` | `plan-verifier/test_plan_verify.py:140-330` | existing verdict / CLI / reuse / relative-external | new cases join these classes; do not rewrite `test_new_collision` (verdict-only) or `test_cli_spec_warn_only_never_strict_fails` | deep |
| `plan-verifier` manifest entry | `manifest.json:48-55` | PostToolUse Write\|Edit, `--hook` | **unchanged** | n/a |
| Verdict table (contract) | `plan-verifier/design.md:109-116` | Block 3a SSOT | amend header + `touch:` / `new:` / `remove:` rows (Done 5) | n/a |

### Partially built (extend)

| What exists | What must change | Why |
|---|---|---|
| `verdict_claim` `new:` UNRESOLVED → unconditional `OK, "no existing match"` (`:219-220`) | path-only + on-disk → `COLLISION, ON_DISK_EVIDENCE`; else keep today’s OK | grill 1-a |
| `verdict_claim` touch/remove/swept UNRESOLVED → unconditional `MISSING` (`:231-234`) | path-only + on-disk → `OK, ON_DISK_EVIDENCE`; else keep today’s MISSING | scope Q4-a |
| `verdict_claim` signature (no `repo_root`) | add `repo_root: Path \| None = None` | Constraint 5; one caller |
| `verify` claim loop (`:286`) | pass `repo_root_for(db)` | Constraint 3; OQ-RT-M2 |
| `check_spec_reuse` loop (`:180`) | match + report `_reuse_ident(name)` | Q6-a |
| `plan-verifier/design.md` verdict table | header + three rows (Done 5) | Block 3a |
| `plan-verifier/test_plan_verify.py` | add cases; do not rewrite existing MISSING/COLLISION asserts | additive |

### Not built (create)

- `ON_DISK_EVIDENCE = "on disk, not in index"`
- `_path_only(claim) -> bool`
- `_on_disk(repo_root, rel) -> bool` (catches `OSError` **and** `RuntimeError`)
- `_reuse_ident(name) -> str`
- `plan-verifier/adrs/0001-on-disk-path-only-is-not-missing.md`
- New tests: design A5 #1–#16 plus **#17 OQ-RT-M1** (symlink loop) and **#18 OQ-RT-M2** (out-of-tree plan + `--db`)

## Feature overview

Happy path: a path-only `touch:` / `remove:` names a regular file under the indexed repo root that is absent from `files.path`. `resolve` returns `UNRESOLVED`. Fallback stats `<repo_root>/<claim.path>` with both sides `.resolve()`d, `is_relative_to(root)`, `is_file()`. Verdict `OK`, evidence exactly `on disk, not in index`. `--strict` does not fail that row. Indexed files never take this branch (hoist guard: test 15).

`new:` of the same shape is `COLLISION` with the same evidence — an empty index is not a create-license (P1 carve-out: path-only + on disk is **not** OK when intent is `new:`).

`path::Symbol` (including empty `foo.py::`) stays index-bound: file-on-disk never launders a ghost. Relative `external: src/local.py` stays off the fallback (`raw` prefix). Absolute / `~` / `../` escapes stay `MISSING`. Directories stay `MISSING` (`is_file()`, not `exists()`).

REUSE: spec cell `runFalQueue(...)` / `claim_one(stage=…)` / `emitFrame...` matches plan `runFalQueue` / `claim_one` / `emitFrame`. Finding reports the **normalized** identifier. `REUSE-DROPPED` never enters `strict_fail`.

Edge: symlink loop under the repo → `_on_disk` returns False (no raise) → row `MISSING`; other claims in the same plan still verdict. Plan file in `/tmp` with `--db` pointing at the fixture → stats the **fixture** root, not `/tmp`.

## Out of scope

- **Prisma / markdown extractors in codegraph** — scope Q4-a rejected; deferred — no phase in this program.
- **REUSE relocation via the DB** — Q6-a rejected c; deferred — no phase yet.
- **New verdict enum / new `STRICT_FAILS` member** (`UNINDEXED`) — freeze; never.
- **Treating `path::Symbol` as OK because the file exists** — freeze; never.
- **Widening `looks_pathish` so `Makefile` / `.env` become path-only** — RT N6; parser-shaped freeze. Motivating files all have extensions. Document, don’t expand.
- **Fallback inside `_shared/resolve.py`** — Option B rejected; frozen seam 1a; one-surface ceiling.
- **All-fallback summary note in `render`** — design OQ-2 recommended no; Bucket 5/6 (`index_empty`).
- **settings.json / hooks.json / `manifest.json` edits** — grill: no settings/hooks edit.
- **TD-01 native init hook** — OUT of this bucket.
- **Blast-radius for unindexed files** — accepted gap (R1); ADR states it.
- **Disk suffix-match** (`touch: TECH_DEBT.md` vs `docs/TECH_DEBT.md`) — index suffix is files-table only; disk join is exact. Accepted gap (RT audit 6).

## Constraints

**Binding MUSTs (dispatch / RT / mini-RT — do not drop):**

- **OQ-RT-M1.** `_on_disk` MUST catch `OSError` **and** `RuntimeError` (symlink loops: `Path.resolve()` raises `RuntimeError` on Python 3.12, not `OSError` — `except OSError` does not see it). Return `False`. CLI must not traceback (`main` only catches `FileNotFoundError`/`SchemaError`). Hook must not lose the rest of the plan (`run_fail_open` swallows the *whole* `verify` with no context). Pin with a test: two-node symlink loop **under the fixture** → `MISSING` / `_on_disk` False, **no raise**.
- **OQ-RT-M2.** Constraint 3 MUST be an automated test, not only the /tmp probe: plan file **outside** the fixture tree, `--db` = fixture db, on-disk file at the **fixture** root → `OK` + evidence `on disk, not in index`. A worker who stats from the plan path must fail this test.
- Evidence text exactly `on disk, not in index` (one module constant; tests assert equality, not substring).
- P1 carve-out: path-only + on disk **must** be `OK` **except** `new:` (P4: that shape is `COLLISION`). Do not write P1 without the intent carve-out.
- `Makefile` / `.env` are **not** path-only under current `looks_pathish` (no `/`, no dot-extension of the hint regex). Disk fallback never fires. Do not expand the parser.
- Consumer copy MUST NOT claim net-fewer CLI failures (path-only `new:` on-disk becomes a new `STRICT_FAILS` hit).
- Constraint 4 MUST NOT claim “cannot recover root from `con`” (`PRAGMA database_list` works on the URI connection). Threading `repo_root_for(db)` is still the required API; do not add a PRAGMA lookup inside `verdict_claim`.
- Constraint 7 cites `looks_pathish` (`or "/" in token`), not only `_PATHISH_HINT`. `_PATHISH_HINT` does not match `prisma/`.
- Done 5 also amends the `new:` verdict-table row **and** the “Check against DB” header, not only `touch:` / `remove:` MISSING clauses.
- Dynamic-names note on `new:` stays **after** the whole if/else and **before** the `return`. `plan-verifier/plan_verify.py:224-227`
>         if claim.symbol and claim.symbol in dynamic_names:

From CLAUDE.md / grill / design / skeleton-contracts:

1. **`STRICT_FAILS` is frozen.** `plan-verifier/plan_verify.py:80`
> STRICT_FAILS = {MISSING, COLLISION, BLOCKED}   # manifest claims only (Block 3b)
   Reuse `OK` / `COLLISION`. No new enum member. — source: skeleton Block 3b; grill freeze.

2. **`--strict` reads manifest claims only.** `plan-verifier/plan_verify.py:289`
> strict_fail = [c for c in manifest.claims if c.verdict in STRICT_FAILS]
   Swept can change freely. REUSE-DROPPED is not a `Claim`. — source: design Constraint 2.

3. **Stat root = indexed repo root from the opened DB, not the plan file.** `_shared/db.py:36`
> return db.parent.parent
   `verify` already has `db` (CLI `--db` or `find_db(plan)`). Pass `repo_root_for(db)`. A plan in `/tmp` against this repo’s `--db` must stat **this** tree. OQ-RT-M2 pins it. — source: grill “Stat root = parent of `.codegraph/`”.

4. **`verdict_claim` today has no `repo_root` parameter** — thread one in. `plan-verifier/plan_verify.py:208-209`
> def verdict_claim(con: sqlite3.Connection, claim: Claim, plan_text: str,
>                   dynamic_names: set[str]) -> None:
   Do **not** claim the root cannot be recovered from `con` (`open_db` is a URI connection; `PRAGMA database_list` returns the file path). Do **not** recover it that way. — source: RT N1; design A2.

5. **Exactly one caller.** `plan-verifier/plan_verify.py:286`
> verdict_claim(con, claim, text, dynamic)
   Default `None` keeps a missing pass from throwing; production **must** pass the root. — source: design Constraint 5.

6. **Path/symbol split is parser-owned.** `_shared/manifest.py:132-133`
> if looks_pathish(raw):
>         return Claim(intent, raw, raw, None)
   Path-only predicate: `path` set, `symbol` None, no `::` in `raw`, not `external:`. — source: design Constraint 6.

7. **Path-like includes slash, not only a dot-extension.** `_shared/manifest.py:107-108`
> def looks_pathish(token: str) -> bool:
>     return bool(_PATHISH_HINT.match(token)) or "/" in token
   Same slash rule in `_shared/resolve.py:57-58`
> return bool(_PATHISH.match(token)) or "/" in token
   This is why `touch: prisma/` is a path claim (directory → still MISSING via `is_file()`). `_PATHISH_HINT` alone does **not** match `prisma/`. — source: RT N2.

8. **Index file lookup is `files.path` only.** `_shared/resolve.py:73`
> rows = con.execute("SELECT path FROM files WHERE path = ?", (token,)).fetchall()
   Do not teach `resolve()` about disk. — source: skeleton 1a.

9. **`external:` never takes the disk fallback.** Absolute form short-circuits. `plan-verifier/plan_verify.py:213`
> claim.verdict, claim.evidence = OK, "declared outside the indexed repo (external:)"
   Relative form does **not** set `claim.external`; `_path_only` must also reject `raw.lstrip().startswith("external:")`. — source: design Constraint 9.

10. **REUSE is a substring test.** `plan-verifier/plan_verify.py:180`
> if name and name in plan_text:
    Normalize the needle; do not rewrite the matcher. — source: Q6-a.

11. **Never write the codegraph db.** `_shared/db.py:45`
> con = sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True)
    Fallback is `stat` only. — source: CLAUDE.md C-01.

12. **Hooks fail-open and do not block.** `plan-verifier/plan_verify.py:390`
>     return 0
    `_shared/hookio.py:41-42`
>     except BaseException:
>         sys.exit(0)
    `_on_disk` must return False rather than raise, or the hook drops every other claim. CLI `plan-verifier/plan_verify.py:425` only catches schema/missing-file:
>     except (FileNotFoundError, SchemaError) as e:
    — source: CLAUDE.md C-04; OQ-RT-M1.

13. **No `_shared/` extraction for a one-consumer helper.** `_on_disk` stays private. — source: CLAUDE.md C-05.

14. **Regular files only.** `is_file()`, never `exists()`. — source: grill 2-a.

15. **Containment.** Refuse absolute and `~`. `.resolve()` on **both** sides + `is_relative_to(root)`. Lexical `is_relative_to` on an unresolved join is not sufficient. — source: design §A1.

16. **One surface.** Only `plan-verifier/plan_verify.py`, `plan-verifier/test_plan_verify.py`, `plan-verifier/adrs/0001-on-disk-path-only-is-not-missing.md`, `plan-verifier/design.md` (verdict-table amend). No `manifest.json` / settings / hooks / `_shared/` / `diff-verifier/` edits. — source: grill; R15 (one CLI; both harnesses consume it).

17. **Block 3a table is the contract** at `plan-verifier/design.md:111`
> | Claim | Check against DB | Verdict when wrong |
    Amend that header (it is no longer DB-only) and the `touch:` / `new:` / `remove:` rows. — source: RT N4; Done 5.

## Assumptions

FLOOR from design `## Assumptions to verify` (verbatim claims). FCV checks each.

| ID | Assumption | Source implication | What would prove it wrong |
|---|---|---|---|
| A1 | `verdict_claim` has exactly one call site, so threading `repo_root` is a one-line ripple. `plan-verifier/plan_verify.py:286` quote: `verdict_claim(con, claim, text, dynamic)` | implication “three call sites, one predicate”; Constraint 5 | a second caller exists (hook path, another tool) that must pass the root or silently keep the old behaviour |
| A2 | `--strict` is computed from manifest claims only, so swept-claim changes cannot move the gate. `plan-verifier/plan_verify.py:289` quote: `strict_fail = [c for c in manifest.claims if c.verdict in STRICT_FAILS]` | implication “swept inherits the fallback harmlessly” | `strict_fail` includes swept claims |
| A3 | The repo root is the DB’s grandparent, not the plan’s directory. `_shared/db.py:36` quote: `return db.parent.parent` | Constraint 3 | `repo_root_for` walks from the plan, or is not `db.parent.parent` |
| A4 | A no-`::` path-like entry produces `path` set, `symbol` None. `_shared/manifest.py:133` quote: `return Claim(intent, raw, raw, None)` | implication “path/symbol split is parser-owned” | path-like entries set `symbol` or leave `path` None |
| A5 | A `::` in `raw` excludes the disk fallback **even when the symbol part is empty**: `parse_entry` splits on `::` and maps an empty right-hand side to `symbol=None`, so `foo.py::` yields path set / symbol None. `_shared/manifest.py:129` quote: `if "::" in raw:` | implication “laundering hole closes by predicate”; A5 #14 | `foo.py::` parses with `symbol` non-None, or `"::" not in claim.raw` is true for that shape |
| A6 | The `claim.external` short-circuit covers the **absolute** form only. `parse_entry` sets the flag when the remainder starts with `/` or `~/`; a **relative** `external: src/local.py` falls through with `external=False` and `path` = the whole raw string, so the flag alone does not exclude it — the `raw`-prefix check in `_path_only` is what covers the relative form. `plan-verifier/plan_verify.py:213` quote: `claim.verdict, claim.evidence = OK, "declared outside the indexed repo (external:)"` | Constraint 9; A5 #16 | relative `external:` sets `external=True`, or `_path_only` would stat it |
| A7 | File resolution consults `files.path` only — nothing on disk. `_shared/resolve.py:73` quote: `rows = con.execute("SELECT path FROM files WHERE path = ?", (token,)).fetchall()` | implication “the bug is a category error” | `_resolve_file` already stats the working tree |
| A8 | `looks_pathish` treats any token containing `/` as a path, including absolute ones. `_shared/resolve.py:58` quote: `return bool(_PATHISH.match(token)) or "/" in token` | implication “containment is a real concern”; justifies absolute-path refusal | `looks_pathish` requires a dot-extension and ignores `/` |
| A9 | REUSE matching is a bare substring test on the spec’s name. `plan-verifier/plan_verify.py:180` quote: `if name and name in plan_text:` | implication “decorated spec name never matches”; A4 | matcher is tokenized / regex, not substring |
| A10 | The test fixture’s repo root is `tmp_path`, so test files can be created next to the DB. `plan-verifier/test_plan_verify.py:78` quote: `make_db(tmp_path)` | A5 tests 1–16 | fixture db lives somewhere other than `tmp_path` |
| A11 | `test_new_collision` asserts the verdict only, not the evidence shape. `plan-verifier/test_plan_verify.py:167` quote: `assert r["manifest_claims"][0].verdict == pv.COLLISION` | dual-predicate P6 (second COLLISION evidence form) | that test (or a sibling) asserts `exists: ` evidence for every COLLISION |
| A12 | Swept OK rows are already suppressed from output. `plan-verifier/plan_verify.py:324` quote: `if c.verdict == OK and not c.notes:` | implication “swept fallback hits reduce, not increase, noise” | swept OK rows are printed in full `render` |

Additional (decomposition + RT; FCV should still check):

| ID | Assumption | Source implication | What would prove it wrong |
|---|---|---|---|
| A13 | `Path.resolve()` on a two-node symlink loop raises `RuntimeError`, not `OSError` (verified 3.12.13 this session: `RuntimeError: Symlink loop from '…'`). CLI `main` does not catch `RuntimeError`. `plan-verifier/plan_verify.py:425` quote: `except (FileNotFoundError, SchemaError) as e:` | OQ-RT-M1; RT M1 | resolve raises `OSError`/`OSError` subclass that `except OSError` would see, or CLI already wraps `BaseException` |
| A14 | Parser `looks_pathish` is the same slash rule as resolve, in `_shared/manifest.py:108` quote: `return bool(_PATHISH_HINT.match(token)) or "/" in token` | RT N2 (Constraint 7 cite) | `parse_entry` uses `_PATHISH_HINT` alone |
| A15 | `Makefile` and `.env` are **not** path-only (`looks_pathish` False this session on both parsers). Fallback never fires for them. | RT N6 | `looks_pathish("Makefile")` or `looks_pathish(".env")` is True |
| A16 | `open_db` uses a URI connection. `_shared/db.py:45` quote: `con = sqlite3.connect(f"file:{path}?mode=ro&immutable=1", uri=True)` | RT N1 (PRAGMA `database_list` can name the file) | connect is not URI, or `database_list` is empty |
| A17 | `_NONCODE_EXT` includes `.json`. `plan-verifier/plan_verify.py:108-109` quote: `_NONCODE_EXT = (".md", ".json", ".yaml", ".yml", ".lock", ".log", ".txt",` | A5 #13 (do not use `hooks.json` as a sweep token) | `.json` is not filtered from the sweep |
| A18 | `repo_root_for` is already imported and unused as a call. `plan-verifier/plan_verify.py:63` quote: `from _shared.db import SchemaError, find_db, open_db, repo_root_for  # noqa: E402` | design A3 | import already gone, or already called in `verify` |

## Component dependency order

What must EXIST before each component works — not the code-writing order.

### 1. `ON_DISK_EVIDENCE` (new) + `_path_only` + `_on_disk`
**Goal.** One exact evidence string; one path-only predicate; one contained regular-file stat that never raises.
**Build.** Module-level in `plan-verifier/plan_verify.py` (private helpers, not `_shared/`):

- `ON_DISK_EVIDENCE = "on disk, not in index"` — grill C1; do not reword.
- `_path_only(claim)` true iff `claim.path` and not `claim.symbol` and not `claim.external` and `"::" not in claim.raw` and not `claim.raw.lstrip().startswith("external:")`. Both the `::` check and the raw `external:` prefix are load-bearing (A5, A6).
- `_on_disk(repo_root, rel)`: False if `repo_root is None` or `rel` empty; False if `Path(rel).is_absolute()` or `rel.startswith("~")`; else `root = repo_root.resolve()`, `cand = (root / Path(rel)).resolve()`, return `cand.is_relative_to(root) and cand.is_file()`. **MUST** `except (OSError, RuntimeError): return False` (OQ-RT-M1). Both `.resolve()` calls are mandatory (escape + macOS `/tmp` → `/private/tmp`). `is_file()`, never `exists()`.
**Depends on.** None.
**Assumes.** A3, A4, A5, A6, A8, A13, A14, A15.
**Interface shape.** Unexported. One adapter, stays private (C-05).
**Done when.** A two-node symlink loop under a fixture root does not raise out of `_on_disk` (returns False). `../outside.json` and `/etc/passwd` return False. A regular file under root returns True. A directory returns False. `Makefile` is not path-only (parser), so `_path_only` is never asked to serve it.

### 2. `verdict_claim` disk fallback inside the two `UNRESOLVED` arms
**Goal.** Path-only on-disk files stop being false `MISSING`; `new:` of those files becomes `COLLISION`; `::Symbol` never launders; indexed files keep caller evidence.
**Build.** Add `repo_root: Path | None = None`. **Do not** place the fallback above `resolve`.

`new:` branch when `res.state == UNRESOLVED`: if `_path_only` and `_on_disk(repo_root, claim.path)` → `COLLISION, ON_DISK_EVIDENCE`; else keep `OK, "no existing match"`. Indexed collision keeps `"exists: " + locs`. Dynamic-names note stays after the whole if/else, before `return`.

Touch / remove / swept when `res.state == UNRESOLVED`: if `_path_only` and `_on_disk` → `OK, ON_DISK_EVIDENCE`; else keep `MISSING` + `no node or file matches {token!r}`. Early `return` so unindexed `remove:` never reaches caller-count `BLOCKED`.

P1 carve-out is this split: path-only + on disk is OK **unless** intent is `new:` (COLLISION).
**Depends on.** 1.
**Assumes.** A1, A5, A6, A7, A11.
**Done when.** Behaviour of tests 1–7, 12–16 (component 5). Indexed `touch: src/db.py` evidence is `node.loc` + caller count, **never** `on disk, not in index`.

### 3. `verify` threads `repo_root_for(db)`
**Goal.** Stat root is the opened index’s repo, including when the plan lives somewhere else and `--db` is passed.
**Build.** After `con = open_db(db)`, `root = repo_root_for(db)`; pass `root` into every `verdict_claim(...)`. Do **not** derive root from `find_db(plan_path)` when `db` is already known. Do **not** PRAGMA-from-`con`.
**Depends on.** 2 (signature exists).
**Assumes.** A1, A3, A18.
**Done when.** OQ-RT-M2 test greens: out-of-tree plan + `--db` fixture db + file at fixture root → `OK` + `on disk, not in index`. The same plan with no `--db` (no db walking up from `/tmp`) stays the existing CLI exit-2 “no db” path.

### 4. REUSE identifier normalization
**Goal.** Spec `runFalQueue(...)` / `claim_one(stage=…)` / `emitFrame...` match plan `runFalQueue` / `claim_one` / `emitFrame`; `REUSE-DROPPED` stays warn-only and names the searched identifier.
**Build.** `_reuse_ident(name)`: take text before first `(`, strip trailing `…` then `...`; if empty, fall back to original stripped name. Apply once per row **before** the substring tests; use the normalized string for both the match **and** the finding’s `name` / evidence backticks. `spec_reuse_rows` unchanged. Do not add `reuse_dropped` to `strict_fail`.
**Depends on.** None.
**Assumes.** A2, A9.
**Done when.** Tests 9–11. `test_cli_spec_warn_only_never_strict_fails` still exit 0. A dropped row’s evidence names the identifier that was searched, not the decorated spec cell.

### 5. Tests
**Goal.** Every MUST above has a case that fails the lazy misread.
**Build.** Add to `plan-verifier/test_plan_verify.py` (`TestVerdicts` unless noted). Create real files next to the fixture db (A10). Do not rewrite existing MISSING/COLLISION tests.

| # | Case | Expect |
|---|---|---|
| 1 | `touch: hooks.json`, file at `repo/hooks.json` | `OK`, evidence == `on disk, not in index` |
| 2 | `touch: prisma/schema.prisma::Asset` with the file on disk | `MISSING` |
| 3 | `new: hooks.json` with the file on disk | `COLLISION`, same evidence |
| 4 | `remove: hooks.json` with the file on disk | `OK`, same evidence, no `BLOCKED` |
| 5 | `touch: subdir/` (real directory) | `MISSING` |
| 6 | `touch: nope/ghost.json` | `MISSING` |
| 7 | `touch: /etc/passwd` | `MISSING` |
| 8 | CLI `--strict`, **passing-only** plan: one path-only `touch:` of an on-disk file, no `new:`, no directory (`TestCli`) | exit 0 |
| 9 | reuse row `runFalQueue(...)` vs plan `runFalQueue` (`TestSpecReuse`) | not dropped |
| 10 | reuse rows `claim_one(stage=…)` and `emitFrame...` | not dropped when bare ident appears |
| 11 | existing `test_cli_spec_warn_only_never_strict_fails` | unchanged, exit 0 |
| 12 | `touch: ../outside.json` with file one level above fixture root | `MISSING` |
| 13 | prose `` `probes/schema.prisma` `` (file on disk, not in DB); **not** `hooks.json` (`.json` ∈ `_NONCODE_EXT`) | swept `OK` + exact evidence; row absent from `render`; `strict_fail` empty |
| 14 | `touch: foo.py::` with `repo/foo.py` on disk, absent from DB | `MISSING` |
| 15 | `touch: src/db.py` on disk **and** in fixture `files` | evidence is resolved `node.loc` + caller count, **never** `on disk, not in index` |
| 16 | `touch: external: src/local.py` with `repo/src/local.py` on disk | `MISSING` + existing abs-path meta_problem |
| **17 (OQ-RT-M1)** | two-node symlink loop under the fixture (`loop/a` ↔ `loop/b`); `touch: loop/a` | `MISSING`; `_on_disk` / `verify` / CLI **do not raise** |
| **18 (OQ-RT-M2)** | plan file **outside** the fixture tree; CLI `--db` = fixture db; `hooks.json` (or equivalent) written at the **fixture** root; path-only `touch:` of that file (`TestCli`) | `OK` + evidence `on disk, not in index`. Must fail a worker who `find_db(plan.parent)` |

**Depends on.** 1–4.
**Assumes.** A10, A11, A12, A13, A17.
**Done when.** `python3 -m pytest plan-verifier/ -q` includes all 18; existing tests still green.

### 6. ADR
**Goal.** Next reader does not re-litigate why unindexed-but-present is OK and unindexed-symbol is not.
**Build.** `plan-verifier/adrs/0001-on-disk-path-only-is-not-missing.md` (tool-local; OQ-1 CLOSED). Must state in these words: (a) path-only regular file under indexed root is **not** MISSING — `OK` + `on disk, not in index`; (b) `path::Symbol` excluded, including `foo.py::`; (c) `new:` path-only on-disk is **COLLISION**; (d) directories do not count — `is_file()`. Also: blast-radius skip (R1); working-tree-dependent verdicts (R2); symlink-out refused (R4); symlink-**loop** returns False via `RuntimeError` catch (OQ-RT-M1); stat root is the DB’s repo not the plan’s (Constraint 3 / OQ-RT-M2).
**Depends on.** Behaviour of 2–3 specified (can be written in parallel).
**Assumes.** None.
**Done when.** File exists at that path and contains (a)–(d) in those words.

### 7. `plan-verifier/design.md` verdict-table amend (Done 5)
**Goal.** Block 3a contract matches shipped behaviour, including `new:` and the table header.
**Build.** At `plan-verifier/design.md:111` change header `Check against DB` so it is not DB-only (e.g. check against the index, with a path-only on-disk fallback). Amend:

- `touch: X` MISSING clause: unless path-only and a regular file under the repo root → `OK` with evidence `on disk, not in index`.
- `remove: Z` same MISSING carve-out.
- **`new: Y` row:** path-only file that already exists on disk under the repo root is `COLLISION` with evidence `on disk, not in index` (not `OK` / “no existing match”). Indexed existence keeps today’s `exists: …` COLLISION.

Do not change blast / AMBIGUOUS rows.
**Depends on.** None (docs).
**Assumes.** None.
**Done when.** Header is not “Check against DB” alone; `touch:` / `remove:` / `new:` rows all record the fallback.

## Handoff notes

- **Contract with later buckets:** this phase promises path-only on-disk `touch:`/`remove:` no longer false-`MISSING` under `--strict`, and path-only `new:` of an on-disk file is `COLLISION`. It does **not** promise net-fewer CLI failures. It does **not** promise `Makefile` / `.env` coverage. It does **not** export a disk-aware `resolve()`.
- **Contract with Bucket 5/6:** no `index_empty` / probe work. OQ-2 (all-fallback summary note) stays **no** for this bucket.
- **OQ-3 CLOSED for implementers:** REUSE-DROPPED reports the **normalized** identifier (design A4).
- **OQ-RT-M1 and OQ-RT-M2 are MUSTs**, not open questions. FCV/planner must keep them.
- **Open uncertainty:** none that unblock this phase. OQ-1 CLOSED (tool-local ADR). OQ-2 deferred (no). TD-01 stays OPEN and out of this bucket.
- **Suggested research before planning:** FCV of A1–A18. If FCV finds a second `verdict_claim` caller, every caller must pass the root. If `Path.resolve` on this runtime does not raise `RuntimeError` for ELOOP, keep both exception types anyway (cheap, required by OQ-RT-M1).
- **Planner traps:** (1) hoist fallback above `resolve` — fails #15; (2) `except OSError` only — fails #17 / traceback on CLI; (3) `find_db(plan)` as stat root — fails #18; (4) `exists()` not `is_file()` — fails #5; (5) lexical containment without both `.resolve()` — fails #12; (6) `_path_only` on `not claim.symbol` without `"::" not in raw` — fails #14; (7) `not claim.external` without raw `external:` prefix — fails #16; (8) sweep test on `hooks.json` — vacuous (#13); (9) passing-only CLI test that still includes `new:` or a directory — probe exit-1 ≠ A5 #8; (10) claim net-fewer CLI failures in copy; (11) skip `new:` row / header in design.md; (12) widen `looks_pathish` for `Makefile`/`.env`; (13) recover root from `con` via PRAGMA instead of threading `repo_root_for(db)`.
- **Next stage:** `/factual-code-verification` on A1–A18, then `/plan`.
