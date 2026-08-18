# Factual Code Verification: Bucket 3 — plan_verify disk-stat + REUSE name-normalize
_Last updated: 2026-08-18_

Spec: `docs/AI_artifacts/4_specs/2026-08-18-bkt3-plan-verify.md`
Design: `docs/AI_artifacts/3_design/2026-08-18-bkt3-plan-verify.md`
Grill: `docs/AI_artifacts/_handoff/2026-08-18-bkt3-plan-verify-grill.md`
Runtime this session: Python **3.12.13**; `Path.is_relative_to` present; `Path("/tmp").resolve()` → `/private/tmp`; two-node symlink loop → `RuntimeError: Symlink loop from '…'` (not `OSError`); URI `open_db` `PRAGMA database_list` returns the file path.

## Overview

`plan_verify` verdicts claims against the index only. Path-only `touch:`/`remove:` of a regular file that is on disk but absent from `files.path` is `MISSING` (`no node or file matches {token!r}`). Path-only `new:` of that same file is `OK` (`no existing match`). Spec reuse is a bare substring of the spec cell. Spec A1–A18 + extra A19 all match this code. Structural audit S1–S6 pass. No invalidated assumptions. Ready for `/plan`.

Calibration (auto-proceed, NON-INTERACTIVE): deep-trace `plan-verifier/plan_verify.py`, `plan-verifier/test_plan_verify.py`, `_shared/db.py`, `_shared/resolve.py`, `_shared/manifest.py`, `_shared/hookio.py`, `plan-verifier/design.md` verdict table, `_shared/queries.py` callers; surface `manifest.json:48-55`; skip `diff-verifier/` (parser share, not verdicts).

Structural audit: pass.

## Key Components

| Symbol | Site | Role now |
|---|---|---|
| `STRICT_FAILS` | `plan-verifier/plan_verify.py:80` | `{MISSING, COLLISION, BLOCKED}` — frozen, no new member |
| `ON_DISK_EVIDENCE` / `_path_only` / `_on_disk` / `_reuse_ident` | **absent** | spec components 1, 4 |
| `verdict_claim` | `plan-verifier/plan_verify.py:208-261` | all verdict policy; **no** `repo_root`; two UNRESOLVED arms unconditional |
| `verify` | `plan-verifier/plan_verify.py:264-303` | `db = db_path or find_db(...)`; one `verdict_claim` call, no root |
| `check_spec_reuse` | `plan-verifier/plan_verify.py:171-190` | `if name and name in plan_text:` — no normalize |
| `sweep_tokens` / `_NONCODE_EXT` | `plan-verifier/plan_verify.py:112-125` / `:108-109` | drops `.json`/`.md`/… |
| `render` / `to_json` | `plan-verifier/plan_verify.py:314-359` | swept OK suppressed `:324-325`; evidence is a string field |
| `hook_main` | `plan-verifier/plan_verify.py:371-390` | `verify(plan, None)` `:381`; **always** `return 0` `:390` |
| `run_fail_open` | `_shared/hookio.py:34-42` | `except BaseException: sys.exit(0)` — no context |
| `main` | `plan-verifier/plan_verify.py:395-433` | `except (FileNotFoundError, SchemaError)` only `:425` |
| `repo_root_for` | `_shared/db.py:34-36` | `return db.parent.parent`; imported in `plan_verify.py:63`, **never called** |
| `open_db` | `_shared/db.py:39-47` | URI `mode=ro&immutable=1`; FileNotFoundError string `:44` |
| `find_db` | `_shared/db.py:22-31` | walk up for `.codegraph/codegraph.db` |
| `resolve` / `_resolve_file` | `_shared/resolve.py:61-80` | files table exact then `LIKE %/token`; **no** disk |
| `looks_pathish` (resolve) | `_shared/resolve.py:57-58` | `_PATHISH` **or** `"/" in token` |
| `looks_pathish` (parser) | `_shared/manifest.py:107-108` | `_PATHISH_HINT` **or** `"/" in token` — same slash rule |
| `parse_entry` | `_shared/manifest.py:111-134` | `external:` abs flag; `::` split; pathish → path set / symbol None |
| `Claim` | `_shared/manifest.py:62-71` | `path`, `symbol`, `external`, `raw` |
| `make_db` / `repo` / `write_plan` | `plan-verifier/test_plan_verify.py:22-86` | db under `tmp_path/.codegraph/`; plan **inside** repo |
| `test_new_collision` | `plan-verifier/test_plan_verify.py:165-167` | verdict-only, symbol-shaped `new: src/auth.py::validate_token` |
| verdict table | `plan-verifier/design.md:109-116` | header `Check against DB` |
| hook entry | `manifest.json:48-55` | PostToolUse Write\|Edit, `--hook` |

## How It Works

1. CLI `main` (`:395`) requires a plan file or `--hook`. Missing plan → stderr `error: no such plan file: {plan}` exit 2 (`:417-418`). Missing `--spec` file → `error: no such spec file: {spec}` exit 2 (`:421-422`).
2. `verify` (`:264`): `db = db_path or find_db(plan_path.resolve().parent)` (`:267`). Walk miss → `{"error": "no .codegraph/codegraph.db found walking up from the plan"}` (`:269`); CLI prints `error: {result['error']}` exit 2 (`:428-430`). `--db` set but not a file → `open_db` raises FileNotFoundError `codegraph index not found: {path} (run \`codegraph init\` first)` (`_shared/db.py:44`); CLI `error: {e}` exit 2 (`:425-427`). Bad schema → SchemaError `{path} schema not recognized (codegraph version drift?); refusing to guess.` (`_shared/db.py:58-59`); same CLI wrapper.
3. `parse_manifest` → claims. `sweep_tokens` → swept. Loop (`:285-286`): `verdict_claim(con, claim, text, dynamic)` — **only call site**.
4. `verdict_claim`: if `claim.external` → OK + `declared outside the indexed repo (external:)` (`:210-214`). Else `resolve(con, token, file_hint=...)`.
5. `new:` + `UNRESOLVED` → OK + `no existing match` (`:219-220`). Else COLLISION + `exists: ` + locs (`:222-223`). Dynamic-names note **after** the if/else, **before** `return` (`:224-228`).
6. touch/remove/swept + `UNRESOLVED` → MISSING + `no node or file matches {token!r}` then `return` (`:231-234`) — unindexed `remove:` never reaches BLOCKED.
7. `--strict` (`:289`): `strict_fail = [c for c in manifest.claims if c.verdict in STRICT_FAILS]` — swept excluded. Exit 1 iff `--strict` and `strict_fail` (`:433`).
8. `check_spec_reuse`: substring `name in plan_text` (`:180`); dropped evidence uses the **raw** spec name in backticks (`:187`). Not a `Claim`; never in `strict_fail`.
9. Hook: `run_fail_open(hook_main)` (`:410`). Any raise including `RuntimeError` from a future `_on_disk` → `sys.exit(0)` with **empty** context (`hookio.py:41-42`). CLI has **no** `BaseException` wrapper.

## Spec Verification

| Assumption ID | Spec Claim | Verdict | Evidence |
|---|---|---|---|
| A1 | `verdict_claim` has exactly one call site | ✅ Validated | def `:208`; sole call `plan_verify.py:286` `verdict_claim(con, claim, text, dynamic)`. Grep: no other production caller (tests via `pv.verify`) |
| A2 | `--strict` from manifest claims only | ✅ Validated | `:289` `strict_fail = [c for c in manifest.claims if c.verdict in STRICT_FAILS]`. Swept in the loop `:285` but not this list. `test_swept_tokens_get_verdicts_but_never_strict_fail` `:191-196` |
| A3 | Repo root is DB grandparent, not plan dir | ✅ Validated | `_shared/db.py:36` `return db.parent.parent`. `verify` does not call it today |
| A4 | No-`::` path-like → path set, symbol None | ✅ Validated | `manifest.py:132-133` `return Claim(intent, raw, raw, None)`. This session: `hooks.json` → path=`hooks.json` symbol=None |
| A5 | `foo.py::` → path set, symbol None, `"::" in raw` | ✅ Validated | `manifest.py:129-131` `s.strip() or None`. This session: `foo.py::` → path=`foo.py` symbol=None `::in_raw=True`. `_path_only` **must** keep `"::" not in claim.raw` |
| A6 | `claim.external` is abs/`~/` only; relative needs raw prefix | ✅ Validated | `manifest.py:121-128` then fall through. This session: `external: src/local.py` → external=False path=`external: src/local.py`. `test_external_relative_no_short_circuit` `:221-226` |
| A7 | File resolve is `files.path` only, no disk | ✅ Validated | `resolve.py:73` exact SELECT; `:75-76` LIKE suffix also **files table**. No `stat`/`Path`/`os.path` in `_resolve_file` |
| A8 | `looks_pathish` treats `/` as path, incl. abs | ✅ Validated | `resolve.py:57-58` and `manifest.py:107-108`. This session: `prisma/` True; `/etc/passwd` True (`/` in token) |
| A9 | REUSE is bare substring | ✅ Validated | `plan_verify.py:180` `if name and name in plan_text:` |
| A10 | Fixture repo root is `tmp_path` | ✅ Validated | `make_db(root)` `:22-23` writes `root/.codegraph/codegraph.db`; fixture `:77-78` `make_db(tmp_path)`. `repo_root_for(db)` of that db **is** `tmp_path` |
| A11 | `test_new_collision` asserts verdict only | ✅ Validated | `:165-167` `assert r["manifest_claims"][0].verdict == pv.COLLISION`. Symbol-shaped (`::validate_token`); no evidence assert. Sibling tests also verdict-or-`exists:`-free |
| A12 | Swept OK rows suppressed from `render` | ✅ Validated | `:324-325` `if c.verdict == OK and not c.notes: continue` |
| A13 | `Path.resolve()` on two-node loop raises `RuntimeError`; CLI does not catch it | ✅ Validated | This session: `RuntimeError: Symlink loop from '…'`. CLI `:425` `except (FileNotFoundError, SchemaError) as e:` |
| A14 | Parser `looks_pathish` has the same slash rule | ✅ Validated | `manifest.py:108` `return bool(_PATHISH_HINT.match(token)) or "/" in token`. `_PATHISH_HINT` does **not** match `prisma/` (no trailing `.\w+`); slash clause does |
| A15 | `Makefile` / `.env` are not path-only | ✅ Validated | This session both parsers False. `parse_entry("Makefile")` → path=None symbol=`Makefile`. Fallback never asked |
| A16 | `open_db` is URI; `database_list` can name the file | ✅ Validated | `db.py:45` URI connect. This session `PRAGMA database_list` → `(0, 'main', '/private/…/codegraph.db')`. Do **not** recover root that way |
| A17 | `_NONCODE_EXT` includes `.json` | ✅ Validated | `plan_verify.py:108-109`. Sweep `:120` `tok.lower().endswith(_NONCODE_EXT)`. Test 13 must use `.prisma` |
| A18 | `repo_root_for` imported, unused as a call | ✅ Validated | import `:63`; grep: no call in `plan_verify.py`. `ssot-diagram/*` call it elsewhere — out of surface |
| A19 (extra) | `_resolve_file` suffix-matches `LIKE %/token` | ✅ Validated | `resolve.py:75-76`. Index suffix ≠ disk suffix. Disk join must stay exact `<repo_root>/<claim.path>` (spec OUT already) |
| S1 | Assumptions falsifiable | ✅ Validated | each A-row has a disproof condition |
| S2 | Done-when observable | ✅ Validated | C1–C7 name CLI/evidence/file contents, not only “pytest green” |
| S3 | Components independently testable | ✅ Validated | C1 before C2; C4 independent; C5 after 1–4; no later-component required to test an earlier one |
| S4 | No silent HOW deferrals | ✅ Validated | predicate, evidence string, exception pair, `is_file`, both `.resolve()` spelled; OQ-2 explicitly OUT |
| S5 | Data model declared | ✅ Validated | `Claim` fields + `ON_DISK_EVIDENCE` + verdicts + `repo_root: Path \| None` |
| S6 | Dependency order sound | ✅ Validated | 1→2→3; 4 none; 5 after 1–4; 6–7 docs. No cycle. Frozen seam 1a mapped to OUT |

## Edge Cases & Silent Failure Modes

- **`foo.py::` laundering:** parser yields path set + symbol None (`manifest.py:129-131`). Predicate `not claim.symbol` alone is True; disk fallback would OK a ghost. `"::" not in claim.raw` is load-bearing (A5 / test 14).
- **Relative `external:`:** `external=False`, `path` = whole raw `external: src/local.py` (this session). `not claim.external` alone would `_on_disk` that string (usually False → MISSING today). Prefix check still required so a weird filename cannot OK it (A6 / test 16). Abs form short-circuits at `:210-214` and never reaches fallback.
- **`new:` vs touch on the same on-disk file:** today both skip disk; after patch they **diverge** (COLLISION vs OK). Wrapping one UNRESOLVED write around both intents is the Bucket 4 class of bug.
- **Indexed file:** UNIQUE from `files.path` (or LIKE suffix) → never UNRESOLVED → fallback must not run (test 15). Evidence `f"{node.loc} ({len(callers)} callers)"` (`:260-261`) via `callers_of_name(stem)` when `node_id` is None (`:242-243`).
- **Directory `prisma/`:** path-only (`/` in token) but `is_file()` False → stay MISSING + `no node or file matches 'prisma/'` (test 5). `exists()` would wrongly OK.
- **Escape:** `Path(rel).is_absolute()` / `rel.startswith("~")` → False before join. Lexical `is_relative_to` on unresolved `root/../outside.json` is True until both `.resolve()` (RT; test 12). macOS `/tmp`→`/private/tmp` confirmed this session.
- **Symlink loop:** `cand.resolve()` raises `RuntimeError` (this session). `except OSError` does **not** see it. CLI traceback (no `error:` line). Hook: `run_fail_open` drops **all** claims, not one row (OQ-RT-M1).
- **`--db` vs walk:** two **different** user-visible strings (see How It Works). Unifying them is a Bucket 4 wrap. OQ-RT-M2: `write_plan` **cannot** host the plan (`:82-86` writes under `repo`); a worker who `find_db(plan.parent)` still lucks out if the plan sits in-tree.
- **Sweep `hooks.json`:** `.json` ∈ `_NONCODE_EXT` → never a swept token. Vacuous test 13 if used.
- **`Makefile` / `.env`:** not path-only; treated as symbols; stay MISSING if no node. Do not widen `looks_pathish`.
- **REUSE decorated names:** `runFalQueue(...)` is not a substring of plan `runFalQueue`. Normalize needle **and** the finding’s `{name}` so dropped evidence names the searched ident.
- **Hook inherit:** `verify(plan, None)` `:381` — once `verify` threads `repo_root_for(db)`, hook gets it. Do not add a second fail-open inside `_on_disk` callers.

## Dependencies & Coupling

- `verdict_claim` ← `verify` (only). `verify` ← `hook_main:381`, `main:424`.
- `parse_entry` / `looks_pathish` frozen parser (`_shared/manifest.py`) — also consumed by `diff-verifier`. **Do not edit.**
- `resolve` frozen seam 1a — **do not edit.** Fallback is verdict-layer.
- `repo_root_for` already imported. `ssot-diagram` callers exist; out of this surface.
- `STRICT_FAILS` / verdict enum frozen Block 3b.
- `run_fail_open` swallows the whole `verify`; `_on_disk` must return False.
- Tests: `TestVerdicts.run` uses in-tree `write_plan` + `find_db`. CLI `--db` tests must pass an explicit db path.

## Extension Points

- **Extend:** the two `UNRESOLVED` arms inside `verdict_claim` (`:219-220`, `:231-234`). Signature grows `repo_root: Path | None = None`.
- **Closed:** `_shared/resolve.py`, `_shared/manifest.py`, verdict enum, `STRICT_FAILS`, hook `return 0`, `manifest.json`.
- **Private helpers** stay in `plan_verify.py` (C-05; one consumer).

## Open Questions

None that block planning. OQ-1 CLOSED (tool-local ADR). OQ-2 deferred OUT. TD-01 stays OPEN and OUT. OQ-RT-M1 / OQ-RT-M2 are MUSTs (verified: RuntimeError this session; `write_plan` in-tree).

## Technical Debt Spotted

None new. `docs/TECH_DEBT.md` TD-01 remains OUT.

## Invalidated Assumptions

_(omitted — none)_
