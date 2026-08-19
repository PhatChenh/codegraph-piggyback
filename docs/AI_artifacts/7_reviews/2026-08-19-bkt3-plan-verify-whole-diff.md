# Whole-diff review — Bucket 3 plan_verify (solo, I7)

Range: `b90f1ec` → `687a247` · Plan: `docs/AI_artifacts/6_plans/2026-08-18-bkt3-plan-verify.md`
Product (locked): disk-stat for path-only claims + REUSE name-normalize, `plan-verifier/plan_verify.py` only. M1: `_on_disk` catches `(OSError, RuntimeError)`. M2: stat root = DB repo (`--db`), not plan folder.

## Verification performed

- Read plan, `PHASE_DIFF.patch`, and live sources under this worktree (`plan_verify.py` helpers + both `UNRESOLVED` arms + `verify` threading; test file; ADR; `design.md` table).
- `git diff --stat b90f1ec..687a247` = exactly the 4 declared files (+326/−12); working tree clean for `plan-verifier/`. `_shared/*`, `manifest.json`, `docs/TECH_DEBT.md` not in diff (constraints hold).
- `python3 -m pytest plan-verifier/ -q` → **59 passed**.
- Live CLI (live counterpart reachable): plan in `/tmp/bkt3wd`, `--db` worktree DB, claims `touch`/`new`/`touch docs/` of real-but-unindexed paths →
  `touch docs/TECH_DEBT.md OK on disk, not in index`; `new: … COLLISION on disk, not in index`; `touch docs/ MISSING no node or file matches 'docs/'`; `--strict` EXIT=1. Matches plan E2E walkthrough #1 exactly, M2 (stat root = DB repo, not plan cwd) live-verified.

## Plan-conformance sweep (no findings)

- M1: `except (OSError, RuntimeError)` present in `_on_disk`; symlink loop → False, no raise (test 17 + `TestOnDiskHelpers`).
- M2: `verify` does `root = repo_root_for(db)` after `open_db`, threads positionally to the sole `verdict_claim` call; no `PRAGMA database_list`, no `repo_root_for(find_db`. OQ-RT-M2 CLI test uses `tmp_path_factory` + `--db`.
- HOW lock A: `_path_only`/`_on_disk`/`_reuse_ident`/`ON_DISK_EVIDENCE` all private to `plan_verify.py`; `_shared/` untouched.
- HOW lock C/D: disk join is exact `root / rel` with `resolve()` both sides + containment; `looks_pathish` never widened (`Makefile` test asserts `.path is None`).
- Both `UNRESOLVED` arms keep exact else-branch strings (`no existing match`, `no node or file matches {token!r}`); indexed `new:` keeps `exists: `; dynamic-names note stays after the if/else, before `return`; `STRICT_FAILS` membership untouched.
- `_reuse_ident` matches plan body verbatim (paren split → unicode `…` rstrip → ASCII `...` suffix → empty→original); finding `name` + evidence template bind `ident`.
- ADR carries (a)–(d) verbatim + R1/R2/R4/OQ-RT-M1/Constraint 3 and the explicit *no net-fewer-failures* non-claim; `design.md` header + three rows amended, blast/AMBIGUOUS rows unchanged.
- Tests 1–18 all present (13 `TestVerdicts` + `TestOnDiskHelpers` + 2 `TestCli` + 2 `TestSpecReuse`); evidence asserted with equality, not substring; pre-existing MISSING/COLLISION/warn-only tests unrewritten.

## Findings

### NIT

1. **Test parent-dir pollution** — `test_touch_parent_escape_missing` and `test_on_disk_parent_escape_false` write `outside.json` into `repo.parent` (pytest's shared basetemp), leaving a stray file visible to other tmp users in the same session. Harmless (fixed name, `{}` content, never read by another test); a `try/finally` unlink would be tidier. Not worth a re-roll on its own.

No CRITICAL, MAJOR, or MINOR findings. Contract strings, verdict routing, strict gating, and locked M1/M2 semantics all match the plan in code, in tests, and live.

VERDICT: APPROVE
