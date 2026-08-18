# Plan: Bucket 3 — plan_verify disk-stat for path-only claims + REUSE name-normalize
_Last updated: 2026-08-18_
_Status: [ ] pending_

Spec: `docs/AI_artifacts/4_specs/2026-08-18-bkt3-plan-verify.md` (components 1–7). FCV: `docs/AI_artifacts/5_factual-code-verification/2026-08-18-bkt3-plan-verify.md` (A1–A19 ✅; no `## Invalidated Assumptions`). Design: `docs/AI_artifacts/3_design/2026-08-18-bkt3-plan-verify.md`. Grill locked. TD-01 OUT.

## Analysis

This phase extends `plan-verifier/plan_verify.py` only (spec Constraint 16 / one surface). The index lookup stays in frozen `_shared/resolve.py`; the lie is in `verdict_claim`’s two `UNRESOLVED` arms, which today always emit `MISSING` / `no existing match`. Option A: private `_path_only` + `_on_disk` + `ON_DISK_EVIDENCE`, fallback **after** `resolve`, `repo_root_for(db)` of the **opened** db threaded in. `new:` of a path-only on-disk file is `COLLISION` (P1 carve-out). REUSE normalizes the spec needle before the existing substring test. Spec owns WHAT; this plan owns TDD order, exact helper bodies, and every user-visible error/evidence string per branch (Bucket 4 lesson: wrapping one write around two intents prints the wrong label).

**HOW lock A:** `_on_disk` / `_path_only` / `_reuse_ident` / `ON_DISK_EVIDENCE` (new) are unexported in `plan_verify.py`. Do not add them to `_shared/`.

**HOW lock B:** `verdict_claim(..., repo_root: Path | None = None)`. Production `verify` **must** pass `repo_root_for(db)`. Do not `PRAGMA database_list` (FCV A16: it works; still forbidden).

**HOW lock C:** Disk join is exact `<repo_root>/<claim.path>`. Do not copy `_resolve_file`’s `LIKE %/token` suffix onto disk (FCV A19).

**HOW lock D:** Do not widen `looks_pathish` for `Makefile` / `.env` (FCV A15).

## Pre-dispatch audit

### 1. Consumer list per changed identifier

Changed identifiers live in `plan-verifier/plan_verify.py` only. `diff_verify` shares the parser, not verdicts.

| Identifier | Consumers | Affected? |
|---|---|---|
| `verdict_claim` | `verify` (one call site); tests via `pv.verify` | YES — `repo_root` param; two `UNRESOLVED` arms gain disk fallback |
| `verify` | CLI `main()`, `hook_main` | YES — `root = repo_root_for(db)` once, threaded |
| `check_spec_reuse` | `verify` when `--spec` | YES — match/report `_reuse_ident(name)` |
| `STRICT_FAILS` | `verify` → CLI `--strict` | NO member added. Mix of fewer false `MISSING` **and** new `COLLISION` strict-fails. **MUST NOT claim net-fewer CLI failures.** |
| `ON_DISK_EVIDENCE` (new) | `--json` evidence; `render`; hook `problems_only` | YES — new string value; no field rename |
| `parse_entry` / `looks_pathish` / `resolve` | unchanged | NO |
| Manifest hook `plan-verifier` | PostToolUse Write\|Edit, advisory, exit 0 | YES — inherits via `verify`; still cannot block a Write |

### 2. Recorded command + output per scope claim (design probe, carried)

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

After this phase the same probe’s `new:` becomes `COLLISION` ∈ `STRICT_FAILS`, so combined `--strict` exit stays 1. Do not claim net-fewer CLI failures.

Python this FCV session: 3.12.13 (`Path.is_relative_to` present; two-node symlink loop → `RuntimeError`).

### 3. One contradiction looked for and not found

No existing test asserts a path-only on-disk file is `MISSING`. `test_touch_missing` is `src/auth.py::ghost_func`. `test_new_collision` is `src/auth.py::validate_token` (symbol-shaped, verdict-only). Tests are additive.

## Facts (live-certified — do NOT re-derive)

- Sole `verdict_claim` call — (`plan-verifier/plan_verify.py:286`) — quote: "`verdict_claim(con, claim, text, dynamic)`"
- Signature has no `repo_root` — (`plan-verifier/plan_verify.py:208-209`) — quote: "`def verdict_claim(con: sqlite3.Connection, claim: Claim, plan_text: str,`" / "`dynamic_names: set[str]) -> None:`"
- `new:` UNRESOLVED is unconditional OK — (`plan-verifier/plan_verify.py:220`) — quote: "`no existing match`"
- Indexed `new:` COLLISION evidence prefix — (`plan-verifier/plan_verify.py:223`) — quote: "`exists: `"
- Dynamic-names note after the whole if/else, before `return` — (`plan-verifier/plan_verify.py:224-228`) — quote: "`if claim.symbol and claim.symbol in dynamic_names:`" / "`return`"
- touch/remove/swept UNRESOLVED is unconditional MISSING — (`plan-verifier/plan_verify.py:233`) — quote: "`no node or file matches {token!r}`"
- `STRICT_FAILS` frozen — (`plan-verifier/plan_verify.py:80`) — quote: "`STRICT_FAILS = {MISSING, COLLISION, BLOCKED}   # manifest claims only (Block 3b)`"
- `--strict` reads manifest only — (`plan-verifier/plan_verify.py:289`) — quote: "`strict_fail = [c for c in manifest.claims if c.verdict in STRICT_FAILS]`"
- `verify` opens `db_path or find_db(plan)` — (`plan-verifier/plan_verify.py:267`) — quote: "`db = db_path or find_db(plan_path.resolve().parent)`"
- `repo_root_for` imported unused — (`plan-verifier/plan_verify.py:63`) — quote: "`from _shared.db import SchemaError, find_db, open_db, repo_root_for  # noqa: E402`"
- Repo root is DB grandparent — (`_shared/db.py:36`) — quote: "`return db.parent.parent`"
- `open_db` URI RO — (`_shared/db.py:45`) — quote: "`mode=ro&immutable=1`"
- SchemaError text — (`_shared/db.py:59`) — quote: "`schema not recognized (codegraph version drift?); refusing to guess.`"
- CLI missing plan — (`plan-verifier/plan_verify.py:417`) — quote: "`error: no such plan file:`"
- CLI missing spec — (`plan-verifier/plan_verify.py:421`) — quote: "`error: no such spec file:`"
- CLI wraps only FileNotFoundError/SchemaError — (`plan-verifier/plan_verify.py:425`) — quote: "`except (FileNotFoundError, SchemaError) as e:`"
- CLI walk-miss prints the dict error — (`plan-verifier/plan_verify.py:429`) — quote: "`error: {result['error']}`"
- argparse missing plan — (`plan-verifier/plan_verify.py:414`) — quote: "`plan path required (or --hook)`"
- `--strict` exit — (`plan-verifier/plan_verify.py:433`) — quote: "`args.strict and result`"
- Abs `external:` short-circuit — (`plan-verifier/plan_verify.py:213`) — quote: "`declared outside the indexed repo (external:)`"
- REUSE substring — (`plan-verifier/plan_verify.py:180`) — quote: "`if name and name in plan_text:`"
- REUSE-DROPPED evidence template — (`plan-verifier/plan_verify.py:188`) — quote: "`is never referenced by the plan`"
- Swept OK suppressed — (`plan-verifier/plan_verify.py:324-325`) — quote: "`if c.verdict == OK and not c.notes:`" / "`continue                      # swept OKs are noise even in full mode`"
- `_NONCODE_EXT` includes `.json` — (`plan-verifier/plan_verify.py:108`) — quote: "`_NONCODE_EXT = (`"
- Indexed touch evidence — (`plan-verifier/plan_verify.py:261`) — quote: "`({len(callers)} callers)`"
- File-node callers use stem — (`plan-verifier/plan_verify.py:242-243`) — quote: "`callers = (callers_of(con, node.node_id) if node.node_id`" / "`else callers_of_name(con, Path(node.file_path).stem))`"
- `hook_main` calls `verify(plan, None)` — (`plan-verifier/plan_verify.py:381`) — quote: "`result = verify(plan, None)`"
- Hook always exit 0 — (`plan-verifier/plan_verify.py:390`) — quote: "`return 0`"
- `run_fail_open` swallows BaseException, no context — (`_shared/hookio.py:41-42`) — quote: "`except BaseException:`" / "`sys.exit(0)`"
- Parser slash rule — (`_shared/manifest.py:108`) — quote: "`_PATHISH_HINT.match(token)`"
- `::` split maps empty symbol to None — (`_shared/manifest.py:131`) — quote: "`s.strip() or None`"
- Path-only Claim — (`_shared/manifest.py:132-133`) — quote: "`if looks_pathish(raw):`" / "`return Claim(intent, raw, raw, None)`"
- Abs `external:` flag — (`_shared/manifest.py:121`) — quote: "`rest.startswith`"
- Relative `external:` meta — (`_shared/manifest.py:158`) — quote: "`external: value must be an absolute path`"
- Resolve slash rule — (`_shared/resolve.py:58`) — quote: "`_PATHISH.match(token)`"
- File resolve exact then LIKE suffix (index only) — (`_shared/resolve.py:73`) — quote: "`SELECT path FROM files WHERE path = ?`"
- `make_db` writes under `root/.codegraph/` — (`plan-verifier/test_plan_verify.py:23`) — quote: "`dbdir = root /`"
- Fixture `repo` is `tmp_path` — (`plan-verifier/test_plan_verify.py:76-78`) — quote: "`def repo(tmp_path: Path) -> Path:`" / "`make_db(tmp_path)`"
- `write_plan` is in-tree — (`plan-verifier/test_plan_verify.py:82`) — quote: "`def write_plan(repo: Path, body: str, name: str =`"
- `test_new_collision` is verdict-only — (`plan-verifier/test_plan_verify.py:167`) — quote: "`verdict == pv.COLLISION`"
- Relative external already MISSING + meta — (`plan-verifier/test_plan_verify.py:226`) — quote: "`absolute path`"
- CLI no-db exit 2 — (`plan-verifier/test_plan_verify.py:265-270`) — quote: "`def test_no_db_is_error_for_cli(self, tmp_path):`" / "`assert r.returncode == 2`"
- REUSE warn-only never strict-fails — (`plan-verifier/test_plan_verify.py:311-320`) — quote: "`def test_cli_spec_warn_only_never_strict_fails(self, repo):`" / "`assert r.returncode == 0          # warn-only: strict gate unaffected`"
- Verdict-table header is DB-only — (`plan-verifier/design.md:111`) — quote: "`| Claim | Check against DB | Verdict when wrong |`"
- Hook manifest entry — (`manifest.json:51`) — quote: "`--hook`"
- TD-01 stays OPEN and OUT — (`docs/TECH_DEBT.md:5`) — quote: "`TD-01 · No post-`"
- FCV: symlink loop is RuntimeError; `/tmp`→`/private/tmp`; `Makefile`/`.env` not path-only — (`docs/AI_artifacts/5_factual-code-verification/2026-08-18-bkt3-plan-verify.md:7`) — quote: "`Python **3.12.13**`"
- `plan-verifier/adrs/` is absent (create it). Naming precedent: `ssot-diagram/adrs/0001-reuse-p1-recipe-by-sibling-import-defer-shared-to-phase-b.md`.

## Files

- `plan-verifier/plan_verify.py` — add `ON_DISK_EVIDENCE` (new), `_path_only` (new), `_on_disk` (new), `_reuse_ident` (new); extend `verdict_claim` / `verify` / `check_spec_reuse`
- `plan-verifier/test_plan_verify.py` — additive tests 1–18; do not rewrite existing MISSING/COLLISION/REUSE-strict tests
- `plan-verifier/adrs/0001-on-disk-path-only-is-not-missing.md` — create (spec component 6)
- `plan-verifier/design.md` — amend verdict-table header + `touch:` / `new:` / `remove:` rows (component 7)

## Delegation Authority

- **Allowed set** = the union of every step's "Files to modify" (= ## Files). Nothing outside it.
- A file in ## Files assigned to ANOTHER step = a dependency (run per ## Implementation Order), not a deviation.
- A file NOT in ## Files → STOP, don't silently edit. Record in an `### Out-of-scope touches` block of the end-of-implementation report (file, why the step needed it, the change, whether it signals a plan/spec gap).
- **Hard off-limits (escalate before touching):** `_shared/resolve.py`, `_shared/manifest.py`, `_shared/db.py`, `_shared/hookio.py`, `_shared/queries.py`, `diff-verifier/**`, `manifest.json`, Claude/Cursor `settings.json` / `hooks.json`, `codegraph/**`, `CLAUDE.md`, `STATE.md`, `docs/TECH_DEBT.md` (TD-01 stays OPEN), verdict enum / `STRICT_FAILS` membership, `looks_pathish` bodies.
- **Escalate, don't improvise (verbatim — copy into the plan):** *If a test cannot pass without violating this plan's design, STOP and report it. Do not improvise a fix and do not revert anything.*

## Rules Applied

No matching rules (no WRIT `PROJ-*` / `--- WRIT RULES ---` block in this dispatch). Binding MUSTs are spec Constraints 1–17 + OQ-RT-M1 + OQ-RT-M2.

## Capabilities

- [ ] C1. `_on_disk` (new) / `_path_only` (new) / `ON_DISK_EVIDENCE` (new): symlink loop → False no raise; `../outside.json` and `/etc/passwd` False; regular file under root True; directory False; evidence string exactly `on disk, not in index`
- [ ] C2. Path-only on-disk `touch:` / `remove:` → `OK` + exact evidence; `new:` → `COLLISION` + same evidence; `::Symbol` / `foo.py::` / relative `external:` / directory / ghost / abs / `../` stay `MISSING` with `no node or file matches {token!r}`
- [ ] C3. Indexed `touch: src/db.py` evidence is `node.loc` + caller count, never `on disk, not in index`
- [ ] C4. Out-of-tree plan + `--db` fixture db + file at fixture root → `OK` + `on disk, not in index` (OQ-RT-M2)
- [ ] C5. CLI `--strict` passing-only path-only on-disk `touch:` exits 0; combined probe with `new:` still exits 1 (no net-fewer-failures claim)
- [ ] C6. Spec `runFalQueue(...)` / `claim_one(stage=…)` / `emitFrame...` match plan idents; `test_cli_spec_warn_only_never_strict_fails` still exit 0; dropped evidence uses the **normalized** ident
- [ ] C7. ADR exists with (a)–(d) in those words; `design.md` header is not “Check against DB” alone; `touch:` / `new:` / `remove:` rows record the fallback
- [ ] C8. `python3 -m pytest plan-verifier/ -q` green including tests 1–18; `_shared/*` / `manifest.json` byte-unchanged

## Implementation Order

Call-graph facts (do not re-derive):

- Only `verdict_claim` caller is `verify` — (`plan-verifier/plan_verify.py:286`) — quote: "`verdict_claim(con, claim, text, dynamic)`"
- Hook inherits via `verify(plan, None)` — (`plan-verifier/plan_verify.py:381`) — quote: "`result = verify(plan, None)`"
- CLI calls `verify` — (`plan-verifier/plan_verify.py:424`) — quote: "`result = verify(plan, Path(args.db) if args.db else None, spec_path=spec)`"
- REUSE loop is independent of verdicts — (`plan-verifier/plan_verify.py:180`) — quote: "`if name and name in plan_text:`"
- `write_plan` cannot host OQ-RT-M2 — (`plan-verifier/test_plan_verify.py:82`) — quote: "`def write_plan(repo: Path, body: str, name: str =`"

**Dependency table:**

| Step | Produces | Depends on | Why (cite) |
|---|---|---|---|
| 1 | `ON_DISK_EVIDENCE` (new), `_path_only` (new), `_on_disk` (new) + helper tests | none | spec C1; used by C2 |
| 2 | `verdict_claim` fallback + `verify` threads `repo_root_for(db)` + tests 1–7, 12–17 | 1 | fallback sits in UNRESOLVED arms after `resolve` (`:216`) |
| 3 | CLI tests 8 + 18 (`TestCli`) | 2 | CLI is `main` → `verify` (`:424`); OQ-RT-M2 needs threaded root |
| 4 | `_reuse_ident` (new) + tests 9–11 | none (same files as 1–3 → after 3) | independent of disk (`:180`) but same `plan_verify.py` |
| 5 | ADR + `design.md` table | none | spec C6–C7; disjoint files vs 1–4 |

**Parallel waves** (disjoint files): **Wave A:** Step 1 ∥ Step 5. **Wave B:** Step 2 (after 1). **Wave C:** Step 3 (after 2). **Wave D:** Step 4 (after 3; same py files).
**Critical path:** 1 → 2 → 3 → 4. Solo linear: 1, 2, 3, 4, 5.

## Steps

### Step 1 — `ON_DISK_EVIDENCE` (new) + `_path_only` (new) + `_on_disk` (new)
**Goal**: Private helpers that never raise; exact evidence constant (spec component 1).
**Design** (imperative — decision already made, no design freedom): In `plan-verifier/plan_verify.py` after `STRICT_FAILS`, add `ON_DISK_EVIDENCE` (new) `= "on disk, not in index"` (exactly those six words; tests assert `==`, not substring). Add:

```
def _path_only(claim: Claim) -> bool:
    return bool(
        claim.path
        and not claim.symbol
        and not claim.external
        and "::" not in claim.raw
        and not claim.raw.lstrip().startswith("external:")
    )
```

Both the `::` check and the raw `external:` prefix are load-bearing (FCV A5/A6). Add:

```
def _on_disk(repo_root: Path | None, rel: str | None) -> bool:
    if repo_root is None or not rel:
        return False
    if Path(rel).is_absolute() or rel.startswith("~"):
        return False
    try:
        root = repo_root.resolve()
        cand = (root / Path(rel)).resolve()
        return cand.is_relative_to(root) and cand.is_file()
    except (OSError, RuntimeError):
        return False
```

`is_file()`, never `exists()`. Both `.resolve()` calls mandatory (escape + macOS `/tmp` → `/private/tmp`). Catch **both** `OSError` and `RuntimeError` (OQ-RT-M1). Do not call `_on_disk` from `verdict_claim` yet. Do not edit `_shared/`. TDD: add `class TestOnDiskHelpers` in `plan-verifier/test_plan_verify.py` **first** (RED): (a) write a regular file at `repo/hooks.json`, `_on_disk(repo, "hooks.json") is True`; (b) `repo/subdir/` directory, `_on_disk(repo, "subdir/") is False`; (c) `_on_disk(repo, "/etc/passwd") is False`; (d) file one level above `repo`, `_on_disk(repo, "../outside.json") is False`; (e) `_on_disk(None, "hooks.json") is False`; (f) two-node symlink `repo/loop/a` ↔ `repo/loop/b`, `_on_disk(repo, "loop/a") is False` and the call **does not raise**; (g) `_path_only(parse_entry("touch", "hooks.json")) is True`; `_path_only(parse_entry("touch", "foo.py::")) is False`; `_path_only(parse_entry("touch", "external: src/local.py")) is False`; `_path_only(parse_entry("touch", "prisma/schema.prisma::Asset")) is False`. `Makefile` is not path-only: `parse_entry("touch", "Makefile").path is None` (do not change the parser).
**Actions**: 1. Add RED `plan-verifier/test_plan_verify.py::TestOnDiskHelpers` covering `_on_disk` / `_path_only` as in Design. 2. Add `plan-verifier/plan_verify.py::ON_DISK_EVIDENCE` exactly `"on disk, not in index"`. 3. Add `plan-verifier/plan_verify.py::_path_only`. 4. Add `plan-verifier/plan_verify.py::_on_disk` with `except (OSError, RuntimeError)` and `is_file()`. 5. GREEN: `python3 -m pytest plan-verifier/test_plan_verify.py::TestOnDiskHelpers -q`. 6. Do not edit `verdict_claim` / `verify` / `check_spec_reuse` in this step.
**Files to modify**: - `plan-verifier/plan_verify.py` — add three helpers - `plan-verifier/test_plan_verify.py` — add `TestOnDiskHelpers`

<!-- plan-verify
new:   plan-verifier/plan_verify.py::ON_DISK_EVIDENCE, plan-verifier/plan_verify.py::_path_only, plan-verifier/plan_verify.py::_on_disk, plan-verifier/test_plan_verify.py::TestOnDiskHelpers
tier: B
qualifiers: grep-present "on disk, not in index" plan-verifier/plan_verify.py ; grep-present "except (OSError, RuntimeError)" plan-verifier/plan_verify.py ; grep-present "is_file()" plan-verifier/plan_verify.py ; grep-absent "PRAGMA database_list" plan-verifier/plan_verify.py ; byte-unchanged _shared/resolve.py ; byte-unchanged _shared/manifest.py ; byte-unchanged _shared/db.py ; byte-unchanged manifest.json
-->

**Test criteria**: - [ ] `python3 -m pytest plan-verifier/test_plan_verify.py::TestOnDiskHelpers -q` passes - [ ] C1 helper subset - [ ] existing `python3 -m pytest plan-verifier/ -q` still green
**Do not regress**: `TestVerdicts` / `TestCli` / `TestSpecReuse` / `TestExternal` / `TestHook` unchanged this step; `STRICT_FAILS` membership untouched.
**Report contract**: on done, report the literal test command run (copy-paste exact, e.g. `python3 -m pytest plan-verifier/test_plan_verify.py::TestOnDiskHelpers -q`), its pass/fail tail, files touched, any `### Out-of-scope touches`; end with the sentinel line `END`. The orchestrator greps every claim against the diff — an unverifiable/truncated claim fails the step. Don't paraphrase the command; paste it.
*If a test cannot pass without violating this plan's design, STOP and report it. Do not improvise a fix and do not revert anything.*
**Status**: [ ] pending

### Step 2 — `verdict_claim` disk fallback + `verify` threads root
**Goal**: Path-only on-disk files stop being false `MISSING`; `new:` of those files becomes `COLLISION`; `::Symbol` never launders; indexed files keep caller evidence (spec components 2–3; tests 1–7, 12–17).
**Design** (imperative — decision already made, no design freedom): Change `verdict_claim` to `def verdict_claim(con, claim, plan_text, dynamic_names, repo_root: Path | None = None) -> None`. **Do not** place the fallback above `res = _rs.resolve(...)`. Keep the `claim.external` short-circuit first (abs form never stats).

**`new:` UNRESOLVED arm — name both labels (Bucket 4):** replace the single `OK, "no existing match"` write with:

| Condition | `claim.verdict` | `claim.evidence` (exact) |
|---|---|---|
| `_path_only(claim)` and `_on_disk(repo_root, claim.path)` | `COLLISION` | `ON_DISK_EVIDENCE` (new) i.e. `on disk, not in index` |
| else (ghost `new:`, or not path-only) | `OK` | `no existing match` |

Indexed `new:` (not UNRESOLVED) **keeps** `COLLISION` + `"exists: " + ", ".join(...)`. Do **not** overwrite that evidence with `ON_DISK_EVIDENCE`. Dynamic-names note stays **after** the whole if/else and **before** `return`.

**touch / remove / swept UNRESOLVED arm — name both labels:**

| Condition | `claim.verdict` | `claim.evidence` (exact) |
|---|---|---|
| `_path_only(claim)` and `_on_disk(repo_root, claim.path)` | `OK` | `on disk, not in index` |
| else | `MISSING` | `no node or file matches {token!r}` (keep the f-string) |

Then `return` so unindexed `remove:` never reaches caller-count `BLOCKED`.

Do **not** invent a third evidence string. Do **not** add a verdict enum member. Do **not** wrap CLI `error:` lines around these table cells — they are stdout evidence, not stderr.

In `verify`, after `con = open_db(db)`: `root = repo_root_for(db)` then `verdict_claim(con, claim, text, dynamic, root)` (or `repo_root=root`). Do **not** derive root from `find_db(plan_path)` when `db` is already known. Keep `db = db_path or find_db(...)` for **opening**. Hook `verify(plan, None)` inherits.

TDD: add methods on `TestVerdicts` (use `self.run` / `write_plan` except where noted). Create real files next to the fixture db (`make_db(tmp_path)` root). Assert `== pv.ON_DISK_EVIDENCE` or `== "on disk, not in index"`, not substring. Do **not** rewrite `test_new_collision`, `test_touch_missing`, `test_external_relative_no_short_circuit`.

| # | Method | Setup / claim | Expect |
|---|---|---|---|
| 1 | `test_touch_path_only_on_disk_ok` | write `repo/hooks.json`; `touch: hooks.json` | `OK`, evidence `==` `on disk, not in index` |
| 2 | `test_touch_symbol_on_disk_still_missing` | write `repo/prisma/schema.prisma`; `touch: prisma/schema.prisma::Asset` | `MISSING`, evidence `no node or file matches 'Asset'` (token is the symbol) |
| 3 | `test_new_path_only_on_disk_collision` | write `hooks.json`; `new: hooks.json` | `COLLISION`, evidence `==` `on disk, not in index` (not `exists: `, not `no existing match`) |
| 4 | `test_remove_path_only_on_disk_ok` | write `hooks.json`; `remove: hooks.json` | `OK`, same evidence, **not** `BLOCKED` |
| 5 | `test_touch_directory_missing` | `mkdir repo/subdir`; `touch: subdir/` | `MISSING`, evidence `no node or file matches 'subdir/'` |
| 6 | `test_touch_absent_path_missing` | `touch: nope/ghost.json` | `MISSING`, evidence `no node or file matches 'nope/ghost.json'` |
| 7 | `test_touch_absolute_missing` | `touch: /etc/passwd` | `MISSING`, evidence `no node or file matches '/etc/passwd'` |
| 12 | `test_touch_parent_escape_missing` | write file one level **above** `repo`; `touch: ../outside.json` | `MISSING`, evidence `no node or file matches '../outside.json'` |
| 13 | `test_swept_prisma_on_disk_ok_suppressed` | write `repo/probes/schema.prisma` (not in DB); prose `` `probes/schema.prisma` ``; **not** `hooks.json` | swept `OK` + exact evidence; row **absent** from `pv.render(r)`; `r["strict_fail"] == []` |
| 14 | `test_touch_empty_symbol_suffix_missing` | write `repo/foo.py`; `touch: foo.py::` | `MISSING` (not OK). Evidence uses token `foo.py` or raw — **keep today’s** `no node or file matches {token!r}` where `token = claim.symbol or claim.path or claim.raw` (here path `foo.py` because symbol is None) → `no node or file matches 'foo.py'` |
| 15 | `test_touch_indexed_file_keeps_caller_evidence` | `touch: src/db.py` **and** write `repo/src/db.py` on disk (file already in fixture `files`) | evidence contains `src/db.py` + callers; evidence `!=` `on disk, not in index` |
| 16 | `test_touch_relative_external_on_disk_missing` | write `repo/src/local.py`; `touch: external: src/local.py` | `MISSING` + existing abs-path meta (`external: value must be an absolute path`) |
| 17 | `test_symlink_loop_missing_no_raise` | two-node loop `repo/loop/a` ↔ `repo/loop/b`; `touch: loop/a` | `MISSING`; `verify` **does not raise**; evidence `no node or file matches 'loop/a'` |

**Error-path stderr (do not change, do not wrap onto the other branch):**

| Branch | stderr (exact) | exit |
|---|---|---|
| plan path missing | `error: no such plan file: {plan}` | 2 |
| `--spec` path missing | `error: no such spec file: {spec}` | 2 |
| `--db` set, file absent | `error: codegraph index not found: {path} (run `codegraph init` first)` | 2 |
| `--db`/found db, bad schema | `error: {path} schema not recognized (codegraph version drift?); refusing to guess.` | 2 |
| `--db` omitted, walk finds nothing | `error: no .codegraph/codegraph.db found walking up from the plan` | 2 |
| argparse no plan and no `--hook` | `plan path required (or --hook)` (argparse prefix) | 2 |
| symlink loop / `_on_disk` False | **no** new stderr; stdout row `MISSING` + `no node or file matches {token!r}` | `--strict` → 1 if that row is manifest |
| hook any raise | **no** context (keep `run_fail_open`); process exit 0 | 0 |

Do **not** unify the two “no db” strings (Bucket 4: walk-miss vs `--db` missing file).
**Actions**: 1. Add RED `TestVerdicts` methods `test_touch_path_only_on_disk_ok`, `test_touch_symbol_on_disk_still_missing`, `test_new_path_only_on_disk_collision`, `test_remove_path_only_on_disk_ok`, `test_touch_directory_missing`, `test_touch_absent_path_missing`, `test_touch_absolute_missing`, `test_touch_parent_escape_missing`, `test_swept_prisma_on_disk_ok_suppressed`, `test_touch_empty_symbol_suffix_missing`, `test_touch_indexed_file_keeps_caller_evidence`, `test_touch_relative_external_on_disk_missing`, `test_symlink_loop_missing_no_raise`. 2. Extend `plan-verifier/plan_verify.py::verdict_claim` with `repo_root` and the two UNRESOLVED tables above, calling existing `ON_DISK_EVIDENCE` (new) / `_path_only` / `_on_disk`; keep `plan-verifier/plan_verify.py::STRICT_FAILS` membership. 3. In `plan-verifier/plan_verify.py::verify`, set `root = repo_root_for(db)` after `open_db` and pass it into `verdict_claim`. 4. Keep `plan-verifier/plan_verify.py::hook_main` as `verify(plan, None)` / `return 0`. 5. GREEN: `python3 -m pytest plan-verifier/test_plan_verify.py::TestVerdicts plan-verifier/test_plan_verify.py::TestOnDiskHelpers plan-verifier/test_plan_verify.py::TestExternal plan-verifier/test_plan_verify.py::TestHook -q`.
**Files to modify**: - `plan-verifier/plan_verify.py` — `verdict_claim` + `verify` - `plan-verifier/test_plan_verify.py` — add the 13 methods

<!-- plan-verify
new:   plan-verifier/test_plan_verify.py::test_touch_path_only_on_disk_ok, plan-verifier/test_plan_verify.py::test_touch_symbol_on_disk_still_missing, plan-verifier/test_plan_verify.py::test_new_path_only_on_disk_collision, plan-verifier/test_plan_verify.py::test_remove_path_only_on_disk_ok, plan-verifier/test_plan_verify.py::test_touch_directory_missing, plan-verifier/test_plan_verify.py::test_touch_absent_path_missing, plan-verifier/test_plan_verify.py::test_touch_absolute_missing, plan-verifier/test_plan_verify.py::test_touch_parent_escape_missing, plan-verifier/test_plan_verify.py::test_swept_prisma_on_disk_ok_suppressed, plan-verifier/test_plan_verify.py::test_touch_empty_symbol_suffix_missing, plan-verifier/test_plan_verify.py::test_touch_indexed_file_keeps_caller_evidence, plan-verifier/test_plan_verify.py::test_touch_relative_external_on_disk_missing, plan-verifier/test_plan_verify.py::test_symlink_loop_missing_no_raise
touch: plan-verifier/plan_verify.py::verdict_claim, plan-verifier/plan_verify.py::verify
tier: A
qualifiers: grep-present "root = repo_root_for(db)" plan-verifier/plan_verify.py ; grep-absent "repo_root_for(find_db" plan-verifier/plan_verify.py ; grep-absent "UNINDEXED" plan-verifier/plan_verify.py ; grep-absent "PRAGMA database_list" plan-verifier/plan_verify.py ; grep-present "no existing match" plan-verifier/plan_verify.py ; grep-present "no node or file matches" plan-verifier/plan_verify.py ; grep-present "exists: " plan-verifier/plan_verify.py ; byte-unchanged _shared/resolve.py ; byte-unchanged _shared/manifest.py ; byte-unchanged _shared/db.py ; byte-unchanged _shared/hookio.py ; byte-unchanged manifest.json
-->

**Test criteria**: - [ ] `python3 -m pytest plan-verifier/test_plan_verify.py::TestVerdicts plan-verifier/test_plan_verify.py::TestExternal plan-verifier/test_plan_verify.py::TestHook -q` passes - [ ] C2 C3 - [ ] `test_new_collision` still green (indexed symbol COLLISION + `exists: `)
**Do not regress**: `test_new_collision` verdict-only; `test_touch_missing` ghost symbol; `TestHook` always exit 0; `test_external_abs_verdicts_ok` evidence `declared outside the indexed repo (external:)`; `STRICT_FAILS` set; `_shared/resolve.py` / `_shared/manifest.py` byte-unchanged.
**Report contract**: on done, report the literal test command run (copy-paste exact, e.g. `python3 -m pytest plan-verifier/test_plan_verify.py::TestVerdicts -q`), its pass/fail tail, files touched, any `### Out-of-scope touches`; end with the sentinel line `END`. The orchestrator greps every claim against the diff — an unverifiable/truncated claim fails the step. Don't paraphrase the command; paste it.
*If a test cannot pass without violating this plan's design, STOP and report it. Do not improvise a fix and do not revert anything.*
**Status**: [ ] pending

### Step 3 — CLI `--strict` passing-only + OQ-RT-M2 `--db`
**Goal**: Constraint 3 is an automated test; passing-only path-only `touch:` does not fail `--strict` (spec tests 8 + 18).
**Design** (imperative — decision already made, no design freedom): Add two methods on `TestCli` (`plan-verifier/test_plan_verify.py`). **#8** `test_strict_path_only_on_disk_exit0`: write `repo/hooks.json`; `write_plan` with **only** `touch: hooks.json` (no `new:`, no directory); `self.cli(plan, "--strict").returncode == 0`. Stdout may show `OK` + `on disk, not in index`. Do **not** use the five-claim design probe here (that probe’s `new:` is still `COLLISION` / exit 1). **#18** `test_cli_db_flag_stats_fixture_root_not_plan_dir`: plan file **outside** the fixture tree via `tmp_path_factory.mktemp("away")` — **do not** call `write_plan(repo, ...)`. Write `hooks.json` at the **fixture** `repo` root. CLI: `[sys.executable, str(CLI), str(plan), "--db", str(repo / ".codegraph/codegraph.db"), "--json"]` (add `--strict` too). Expect returncode 0, JSON manifest[0] verdict `OK`, evidence exactly `on disk, not in index`. A worker who stats from the plan directory must fail this. Keep `test_no_db_is_error_for_cli`: still exit 2; stderr still `error: no .codegraph/codegraph.db found walking up from the plan` when `--db` is omitted and walk fails. Do not change `test_cli_missing_spec_file_exit2` stderr `error: no such spec file: {spec}`.
**Actions**: 1. Add RED `plan-verifier/test_plan_verify.py::test_strict_path_only_on_disk_exit0`. 2. Add RED `plan-verifier/test_plan_verify.py::test_cli_db_flag_stats_fixture_root_not_plan_dir` using `tmp_path_factory`, not `write_plan`. 3. Do not edit CLI `main` error strings. 4. GREEN: `python3 -m pytest plan-verifier/test_plan_verify.py::TestCli -q`.
**Files to modify**: - `plan-verifier/test_plan_verify.py` — two `TestCli` methods

<!-- plan-verify
new:   plan-verifier/test_plan_verify.py::test_strict_path_only_on_disk_exit0, plan-verifier/test_plan_verify.py::test_cli_db_flag_stats_fixture_root_not_plan_dir
tier: A
qualifiers: grep-present "--db" plan-verifier/test_plan_verify.py ; grep-present "tmp_path_factory" plan-verifier/test_plan_verify.py ; grep-present "on disk, not in index" plan-verifier/test_plan_verify.py ; byte-unchanged _shared/db.py
-->

**Test criteria**: - [ ] `python3 -m pytest plan-verifier/test_plan_verify.py::TestCli -q` passes - [ ] C4 C5 - [ ] `test_no_db_is_error_for_cli` still exit 2
**Do not regress**: `test_strict_fails_on_missing` still exit 1 on `src/auth.py::ghost`; `test_advisory_always_exit0`; `test_strict_passes_ambiguous_and_blast`.
**Report contract**: on done, report the literal test command run (copy-paste exact, e.g. `python3 -m pytest plan-verifier/test_plan_verify.py::TestCli -q`), its pass/fail tail, files touched, any `### Out-of-scope touches`; end with the sentinel line `END`. The orchestrator greps every claim against the diff — an unverifiable/truncated claim fails the step. Don't paraphrase the command; paste it.
*If a test cannot pass without violating this plan's design, STOP and report it. Do not improvise a fix and do not revert anything.*
**Status**: [ ] pending

### Step 4 — `_reuse_ident` in `check_spec_reuse`
**Goal**: Decorated spec names match plan identifiers; `REUSE-DROPPED` stays warn-only and names the searched ident (spec component 4; tests 9–11).
**Design** (imperative — decision already made, no design freedom): Add unexported

```
def _reuse_ident(name: str) -> str:
    original = name.strip()
    s = original
    if "(" in s:
        s = s.split("(", 1)[0]
    s = s.rstrip("…")
    if s.endswith("..."):
        s = s[:-3]
    s = s.strip()
    return s if s else original
```

Unicode `…` first, then ASCII `...` (three dots), **not** `rstrip(".")`. Empty after strip → original. In `check_spec_reuse`, once per row **before** the substring tests: `ident = _reuse_ident(name)`; match `ident in plan_text` (and keep the existing `path` / `Path(path).name` branches). Finding `"name"` and the evidence backticks use `ident`, not the decorated cell. Template stays `spec reuse row `{name}` ({path or 'no path'}) depth=deep is never referenced by the plan — the step that needs it may reinvent it (P9-w2b failure shape)` with `name` bound to `ident`. `spec_reuse_rows` **unchanged**. Do **not** add `reuse_dropped` to `strict_fail`. Do **not** rewrite the matcher into regex. Tests on `TestSpecReuse`: **#9** spec row Function cell `` `runFalQueue(...)` `` vs plan text containing `runFalQueue` → not dropped. **#10** rows `` `claim_one(stage=…)` `` and `` `emitFrame...` `` not dropped when those bare idents appear. **#11** leave `test_cli_spec_warn_only_never_strict_fails` untouched (still exit 0, still prints `REUSE-DROPPED` for `AcpTransport`).
**Actions**: 1. Add RED `plan-verifier/test_plan_verify.py::test_reuse_paren_suffix_matches_ident` and `plan-verifier/test_plan_verify.py::test_reuse_ellipsis_forms_match_ident`. 2. Add `plan-verifier/plan_verify.py::_reuse_ident`. 3. Apply it inside `plan-verifier/plan_verify.py::check_spec_reuse` for match + finding name/evidence. 4. Do not edit `plan-verifier/plan_verify.py::spec_reuse_rows`. 5. GREEN: `python3 -m pytest plan-verifier/test_plan_verify.py::TestSpecReuse -q`.
**Files to modify**: - `plan-verifier/plan_verify.py` — `_reuse_ident` + `check_spec_reuse` - `plan-verifier/test_plan_verify.py` — two methods

<!-- plan-verify
new:   plan-verifier/plan_verify.py::_reuse_ident, plan-verifier/test_plan_verify.py::test_reuse_paren_suffix_matches_ident, plan-verifier/test_plan_verify.py::test_reuse_ellipsis_forms_match_ident
touch: plan-verifier/plan_verify.py::check_spec_reuse
tier: B
qualifiers: grep-present "_reuse_ident" plan-verifier/plan_verify.py ; grep-present "runFalQueue" plan-verifier/test_plan_verify.py ; byte-unchanged _shared/manifest.py
-->

**Test criteria**: - [ ] `python3 -m pytest plan-verifier/test_plan_verify.py::TestSpecReuse -q` passes - [ ] C6 - [ ] `test_cli_spec_warn_only_never_strict_fails` returncode 0
**Do not regress**: REUSE never in `STRICT_FAILS`; `test_dropped_row_flagged` still flags `AcpTransport`; `test_basename_mention_satisfies`.
**Report contract**: on done, report the literal test command run (copy-paste exact, e.g. `python3 -m pytest plan-verifier/test_plan_verify.py::TestSpecReuse -q`), its pass/fail tail, files touched, any `### Out-of-scope touches`; end with the sentinel line `END`. The orchestrator greps every claim against the diff — an unverifiable/truncated claim fails the step. Don't paraphrase the command; paste it.
*If a test cannot pass without violating this plan's design, STOP and report it. Do not improvise a fix and do not revert anything.*
**Status**: [ ] pending

### Step 5 — ADR + `design.md` verdict-table amend
**Goal**: Next reader does not re-litigate; Block 3a table matches shipped behaviour (spec components 6–7).
**Design** (imperative — decision already made, no design freedom): Create `plan-verifier/adrs/` and write `plan-verifier/adrs/0001-on-disk-path-only-is-not-missing.md`. The file **must** contain these words (a)–(d): (a) path-only regular file under indexed root is **not** MISSING — `OK` + `on disk, not in index`; (b) `path::Symbol` excluded, including `foo.py::`; (c) `new:` path-only on-disk is **COLLISION**; (d) directories do not count — `is_file()`. Also state: blast-radius skip (R1); working-tree-dependent verdicts (R2); symlink-out refused (R4); symlink-**loop** returns False via `RuntimeError` catch (OQ-RT-M1); stat root is the DB’s repo not the plan’s (Constraint 3 / OQ-RT-M2). Consumer copy **MUST NOT** claim net-fewer CLI failures.

In `plan-verifier/design.md` at the verdict table: change header `Check against DB` so it is not DB-only (e.g. `Check against the index (path-only on-disk fallback)`). Amend:

- `touch: X` MISSING clause: unless path-only and a regular file under the repo root → `OK` with evidence `on disk, not in index`.
- `remove: Z` same MISSING carve-out.
- **`new: Y` row:** path-only file that already exists on disk under the repo root is `COLLISION` with evidence `on disk, not in index` (not `OK` / `no existing match`). Indexed existence keeps `exists: …` COLLISION.

Do not change blast / AMBIGUOUS rows. Do not edit `manifest.json`.
**Actions**: 1. Create `plan-verifier/adrs/0001-on-disk-path-only-is-not-missing.md` with (a)–(d) plus R1/R2/R4/OQ-RT-M1/Constraint 3. 2. Amend `plan-verifier/design.md` header and `touch:` / `new:` / `remove:` rows. 3. Confirm `python3 -m pytest plan-verifier/ -q` still green.
**Files to modify**: - `plan-verifier/adrs/0001-on-disk-path-only-is-not-missing.md` — create - `plan-verifier/design.md` — verdict table

<!-- plan-verify
new:   plan-verifier/adrs/0001-on-disk-path-only-is-not-missing.md
tier: C
qualifiers: grep-present "on disk, not in index" plan-verifier/adrs/0001-on-disk-path-only-is-not-missing.md ; grep-present "foo.py::" plan-verifier/adrs/0001-on-disk-path-only-is-not-missing.md ; grep-present "COLLISION" plan-verifier/adrs/0001-on-disk-path-only-is-not-missing.md ; grep-present "is_file()" plan-verifier/adrs/0001-on-disk-path-only-is-not-missing.md ; grep-present "on disk, not in index" plan-verifier/design.md ; grep-absent "UNINDEXED" plan-verifier/design.md ; diff-only-within plan-verifier
-->

**Test criteria**: - [ ] ADR file exists and contains (a)–(d) in those words - [ ] `design.md` header is not the bare `Check against DB` - [ ] `python3 -m pytest plan-verifier/ -q` passes (C8)
**Do not regress**: blast / AMBIGUOUS table rows; `manifest.json` hook entry; TD-01.
**Report contract**: on done, report the literal test command run (copy-paste exact, e.g. `python3 -m pytest plan-verifier/ -q`), its pass/fail tail, files touched, any `### Out-of-scope touches`; end with the sentinel line `END`. The orchestrator greps every claim against the diff — an unverifiable/truncated claim fails the step. Don't paraphrase the command; paste it.
*If a test cannot pass without violating this plan's design, STOP and report it. Do not improvise a fix and do not revert anything.*
**Status**: [ ] pending

## E2E Done Criteria

**Prerequisites:** Python 3.12.x; this checkout; a fixture db via `make_db` **or** a live `--db` path; `plan-verifier/plan_verify.py` CLI.

**Walkthrough** (action → observe → expected; map to ## Capabilities):

1. Recreate the design probe (path-only `touch`/`new`/`remove` of an on-disk unindexed file + `touch: docs/` + indexed `plan_verify.py`) against a fixture `--db` → observe stdout evidence `on disk, not in index` on touch/remove, `COLLISION` on `new:`, `MISSING` + `no node or file matches 'docs/'` on the directory, indexed row still loc+callers → `--strict` exit **1** because of `new:` COLLISION (C2, C5). Not a net-fewer-failures win.
2. Same tree, **passing-only** plan (`touch:` of the on-disk file only) `--strict` → exit **0** (C5).
3. Plan file in a **different** temp dir, `--db` = fixture db, file at fixture root → JSON evidence `on disk, not in index`, exit 0 (C4). Omit `--db` → stderr `error: no .codegraph/codegraph.db found walking up from the plan`, exit 2.
4. `--spec` with `` `runFalQueue(...)` `` deep row + plan mentioning `runFalQueue` → no `REUSE-DROPPED` for that row (C6). Unreferenced `AcpTransport` still `REUSE-DROPPED` and `--strict` exit 0.
5. Two-node symlink loop under fixture, `touch: loop/a`, `--strict` → stdout `MISSING` / `no node or file matches 'loop/a'`; **no** traceback (C1, C2).
6. `python3 -m pytest plan-verifier/ -q` → all green including tests 1–18 (C8).

**Done gate:** every line observed + matching; pytest green; ADR + design.md amend present. Live observation diverging from a passing unit test → live wins.

## Open Questions

None that unblock this phase. OQ-1 CLOSED (tool-local ADR). OQ-2 deferred OUT. TD-01 stays OPEN and OUT.

## Out of Scope

- Prisma / markdown extractors in codegraph
- REUSE relocation via the DB
- New verdict enum / new `STRICT_FAILS` member (`UNINDEXED`)
- Treating `path::Symbol` as OK because the file exists
- Widening `looks_pathish` so `Makefile` / `.env` become path-only
- Fallback inside `_shared/resolve.py`
- All-fallback summary note in `render` (Bucket 5/6)
- `settings.json` / `hooks.json` / `manifest.json` edits
- TD-01 native init hook
- Blast-radius for unindexed files (accepted gap; ADR states it)
- Disk suffix-match (`touch: TECH_DEBT.md` vs `docs/TECH_DEBT.md`)

## Claim sweep

Swept this session: every `path:line` + quote in ## Facts, Implementation Order, and per-step Design/Actions. Line numbers re-read from disk (FCV + this plan). First write — no prior-plan C1-STALE.

## Gate co-satisfiability

One honest implementation makes every gate green at once:

| Gate | Honest impl | Pass? |
|---|---|---|
| Step1 `grep-present "on disk, not in index"` | `ON_DISK_EVIDENCE = "on disk, not in index"` | yes |
| Step1 `grep-present "except (OSError, RuntimeError)"` | `_on_disk` except clause | yes |
| Step1 `grep-absent "PRAGMA database_list"` | never added | yes |
| Step1 `byte-unchanged _shared/*` + `manifest.json` | helpers stay in `plan_verify.py` | yes |
| Step2 `grep-present "root = repo_root_for(db)"` | `verify` after `open_db` | yes |
| Step2 `grep-absent "repo_root_for(find_db"` | stat root from opened `db` | yes |
| Step2 `grep-absent "UNINDEXED"` | reuse OK/COLLISION | yes |
| Step2 `grep-present "no existing match"` | else-branch of `new:` UNRESOLVED | yes — no fight with on-disk COLLISION |
| Step2 `grep-present "no node or file matches"` | else-branch of touch UNRESOLVED | yes |
| Step2 `grep-present "exists: "` | indexed `new:` COLLISION kept | yes |
| Step2 `touch:` omits `_shared/db.py::repo_root_for` | call only; `byte-unchanged _shared/db.py` | yes |
| Step3 `grep-present "tmp_path_factory"` + `"--db"` | test 18 | yes |
| Step4 `grep-present "_reuse_ident"` | new helper | yes |
| Step4 no `grep-absent "reuse_dropped"` | result key already at `plan_verify.py:301` | yes |
| Step5 ADR `grep-present` (a)–(d) words | docs | yes |
| Step5 `grep-present "on disk, not in index"` in `design.md` | table amend | yes |
| Step5 `new:` ADR `.md` | file absent today → current `no existing match` | yes |
| Path-only `touch: design.md` omitted | qualifier `grep-present` on `design.md` instead | yes |
