# Design — Bucket 3: plan_verify disk-stat for path-only claims + REUSE name-normalize

_Date:_ 2026-08-18 · _Tier:_ LIGHT PLAN · _Surface:_ `plan-verifier/plan_verify.py`
_Locked requirements:_ `docs/AI_artifacts/_handoff/2026-08-18-bkt3-plan-verify-grill.md` (LOCKED)
_Scope parent:_ `docs/AI_artifacts/_scope/2026-08-16-feedback-bugs-scope.md` (Bucket 3, ITEM-4+6)

---

## Summary

`plan_verify` resolves every claim through the codegraph index only. A manifest claim that
names a file codegraph never parsed (`touch: hooks.json`, `touch: prisma/schema.prisma`,
`touch: docs/TECH_DEBT.md`) therefore verdicts `MISSING` and fails `--strict`, even though the
file is sitting on disk. Orchestrators hand-patch those plans every run.

This bucket adds a **disk fallback that fires only where the index came back empty**, for
**path-only** claims (no `::Symbol`), rooted at the indexed repo root:

- `touch:` / `remove:` / swept path-only + regular file on disk → **OK**, evidence exactly
  `on disk, not in index`.
- `new:` path-only + regular file on disk → **COLLISION** (index-blindness is not "create me").
- `path::Symbol` → **unchanged**: still `MISSING` when the index has no symbol. A file on disk
  never launders a ghost function.
- Directories are not "exists" (`is_file()`, not `exists()`).

Plus REUSE identifier-normalization: spec reuse-row names are reduced to the identifier before
`(`, with trailing `…` / `...` stripped, so spec `runFalQueue(...)` matches plan `runFalQueue`.
`REUSE-DROPPED` stays warn-only.

No new verdict enum, no new `STRICT_FAILS` member, one file changed, no settings/hooks edit.

---

## Pre-dispatch audit

**Consumer list for the surface** (`plan-verifier/plan_verify.py`):

| Consumer | How it consumes | Affected by this change? |
|---|---|---|
| CLI `python3 plan-verifier/plan_verify.py <plan> --strict` | exit code 0/1 + rendered table | YES — fewer false `MISSING`, so fewer false exit-1 |
| Manifest hook entry `plan-verifier` (PostToolUse Write\|Edit) | injects `render(..., problems_only=True)` context | YES — fewer advisory rows |
| `--json` consumers (orchestrators) | `manifest[].verdict/evidence`, `strict_fail` bool | YES — new evidence string value |
| `diff-verifier/diff_verify.py` | shares only the manifest **parser**, not verdicts | NO |
| `plan-verifier/test_plan_verify.py` | direct `pv.verify` + subprocess | YES — new tests, no existing rewrite expected |

`diff_verify` coupling is parser-only:

> `diff-verifier/diff_verify.py:4` — "Reads the SAME `<!-- plan-verify -->` manifest as plan_verify (parser:"

**Recorded command + output per scope claim.**

1. Scope claim: *"path-only `touch:` of a real on-disk file verdicts MISSING and fails `--strict` today"*.

```
$ printf '# probe\n\n<!-- plan-verify\ntouch: docs/TECH_DEBT.md\nnew: docs/TECH_DEBT.md\nremove: docs/TECH_DEBT.md\ntouch: docs/\ntouch: plan-verifier/plan_verify.py\n-->\n' > /tmp/bkt3probe/probe-plan.md
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

That single run confirms all four behaviours this bucket changes: `touch` MISSING, `new` wrongly
OK, `remove` MISSING, and (already correct) a directory MISSING. `docs/TECH_DEBT.md` exists on
disk — it is the file quoted in the Constraints section below.

2. Scope claim: *"the manifest ships this as a PostToolUse hook"*.

```
$ sed -n '48,55p' manifest.json
    "plan-verifier": {
      "script": "plan-verifier/plan_verify.py",
      "args": "--hook",
      "scope": "repo",
      "desc": "verify plan code-claims vs codegraph on Write|Edit of *plan*.md (advisory; strict gate = CLI in build-pipeline)",
      "hooks": [
        { "event": "PostToolUse", "matcher": "Write|Edit" }
```

3. Scope claim: *"the repo runs a Python new enough for `Path.is_relative_to`"* (3.9+).

```
$ python3 -V
Python 3.12.13
```

**One contradiction looked for and NOT found.** Hypothesis: an existing test asserts that a
path-only claim whose file exists on disk is `MISSING` — which would make the fix a test
rewrite, not an addition. Probe:

```
$ grep -rn "pv.MISSING\|MISSING" plan-verifier/test_plan_verify.py
plan-verifier/test_plan_verify.py:152:        assert r["manifest_claims"][0].verdict == pv.MISSING
plan-verifier/test_plan_verify.py:195:        assert sw["ghost_helper"] == pv.MISSING
plan-verifier/test_plan_verify.py:225:        assert c.verdict == pv.MISSING
plan-verifier/test_plan_verify.py:246:        assert r.returncode == 0 and "MISSING" in r.stdout and "FAIL" in r.stdout
```

All four are symbol-shaped or non-existent-path-shaped, so none contradicts: `:152` is
`src/auth.py::ghost_func`, `:195` is the bare identifier `ghost_helper`, `:246` is
`src/auth.py::ghost`, and `:225` is the relative-`external:` case whose claim path is the literal
string `external: src/local.py` (never a real file). Contradiction not found — the change is
additive to the test file.

---

## Guardrail Checklist

No `CONSTRAINTS.md` / `docs/rules/` exists in this repo (`ls docs/rules` → no such directory), so
the checklist is derived from `CLAUDE.md` **Critical Rules** + the scope's frozen contracts.

| ID | Rule | This change |
|---|---|---|
| C-01 | Never write to `.codegraph/codegraph.db`; connect `mode=ro` | satisfied — no DB access added; the fallback is a `stat` |
| C-02 | Every tool registers in `manifest.json` | satisfied — `plan-verifier` entry already exists, unchanged |
| C-03 | CLIs must also run standalone | satisfied — change is in the shared verdict path used by CLI and hook |
| C-04 | Hooks inject ≤ ~30 lines, stay silent when nothing to say, never block on their own errors (fail-open) | satisfied — `_on_disk` swallows `OSError`; hook budget untouched |
| C-05 | `_shared/` extraction happens when the second consumer appears, not speculatively | satisfied — the helper stays private to `plan_verify.py`; `diff_verify` has no such need |
| C-06 (scope freeze) | Path-only on-disk → not MISSING; `::Symbol` still needs the index | this is the change |
| C-07 (scope freeze) | No new verdict enum / no new `STRICT_FAILS` member | satisfied — reuses `OK` / `COLLISION` |
| C-08 (scope freeze) | REUSE identifier-normalize only; never `--strict` fail | satisfied — `reuse_dropped` is a separate list, not a claim |
| C-09 (grill C1) | Evidence text exactly `on disk, not in index` | satisfied — one module constant, used by all three branches |
| C-10 (grill 2-a) | Regular files only; directories stay MISSING | satisfied — `is_file()` |

Nothing here touches auth/payments/migrations/secrets/infra/CI, so no `human-authority` domain is
engaged beyond what the grill already locked.

---

## Constraints

1. **`STRICT_FAILS` is frozen and may not gain a member.**
   `plan-verifier/plan_verify.py:80`
> STRICT_FAILS = {MISSING, COLLISION, BLOCKED}   # manifest claims only (Block 3b)
   The fix must land inside the existing enum — hence `OK` for touch/remove and `COLLISION` for
   `new:`, not a new `UNINDEXED` verdict.

2. **`--strict` reads manifest claims only**, so swept claims can change verdict freely without
   touching the gate. `plan-verifier/plan_verify.py:289`
> strict_fail = [c for c in manifest.claims if c.verdict in STRICT_FAILS]

3. **The stat root must be the indexed repo root, and that root is derived from the DB, not from
   the plan file.** `_shared/db.py:36`
> return db.parent.parent
   This matters because the plan file may live outside the repo (the probe above ran a plan from
   `/tmp` against this repo's DB via `--db`).

4. **`verdict_claim` currently has no access to the DB path or repo root** — it receives only a
   connection, the claim, plan text, and dynamic names. `plan-verifier/plan_verify.py:208`
> def verdict_claim(con: sqlite3.Connection, claim: Claim, plan_text: str,
   So the root has to be threaded in; it cannot be recovered from `con`.

5. **`verdict_claim` has exactly one caller**, inside `verify`, so threading a parameter is a
   one-line ripple. `plan-verifier/plan_verify.py:286`:
> verdict_claim(con, claim, text, dynamic)

6. **The path/symbol split is decided by the parser, not by the verdict layer.** A claim with no
   `::` that looks path-like carries `path` set and `symbol` None. `_shared/manifest.py:132-133`:
> return Claim(intent, raw, raw, None)
   That is exactly the "path-only" predicate this design keys on.

7. **"Path-like" requires a dot-extension or a slash**, which is why `touch: prisma/` (slash) is a
   path claim and correctly stays MISSING as a directory. `_shared/manifest.py:56`:
> _PATHISH_HINT = re.compile(r"^[\w./-]+\.[A-Za-z0-9]+$")

8. **File resolution against the index is exact-path-then-suffix**, i.e. the index answers about
   `files.path` rows only — nothing on disk. `_shared/resolve.py:73`:
> rows = con.execute("SELECT path FROM files WHERE path = ?", (token,)).fetchall()

9. **`external:` claims must never take the disk fallback** (they declare a target outside the
   indexed root by definition) — but the existing short-circuit covers only the **absolute** form.
   `plan-verifier/plan_verify.py:213`:
> claim.verdict, claim.evidence = OK, "declared outside the indexed repo (external:)"
   `parse_entry` sets `external=True` only when the remainder starts `/` or `~/`; the **relative**
   form (`external: src/local.py`) falls through with `external=False` and `path` = the whole raw
   string. So `not claim.external` alone does not satisfy this constraint — `_path_only` also
   rejects any raw entry whose text starts with `external:` (§A1, A5 #16).

10. **REUSE matching is a plain substring test on the spec's row name**, which is why a decorated
    spec name never matches an undecorated plan mention. `plan-verifier/plan_verify.py:180-181`:
> if name and name in plan_text:

---

## Surface-capability matrix

One row per boundary hop this change's behaviour crosses.

| Event / surface | Vendor-enforced? | Payload fields | Operator surface |
|---|---|---|---|
| Claude Code `PostToolUse` (matcher `Write\|Edit`), `--hook` mode | **no** — advisory only; this tool emits context and always returns 0 (`plan-verifier/plan_verify.py:389-390`: `    emit_context(...)` / `    return 0`) | `hookSpecificOutput.additionalContext` = budgeted `render(problems_only=True)` rows | transcript context lines only; cannot block a Write |
| CLI exit code (`--strict`) consumed by build-pipeline / av verify-wave | **yes** — the caller gates on the process exit status (`plan-verifier/plan_verify.py:433`: `    sys.exit(1 if (args.strict and result["strict_fail"]) else 0)`) | exit 0/1 + stdout table | the only place this tool can actually stop anything |
| `--json` payload consumed by orchestrators | **yes** — machine-read fields | `manifest[].verdict`, `manifest[].evidence`, `strict_fail` | a new `evidence` string value appears; no field added or renamed |
| Filesystem `stat` of `<repo_root>/<claim path>` | n/a — in-process, same-machine, read-only | — | — |

No claim of "blocks" / "fails closed" is made for the hook surface anywhere in this design: the
hook row's enforcement column is **no**, and the only enforcing surface is the CLI exit code.

---

## Implications

- **The bug is a category error, not a lookup bug.** `verdict_claim` asks the index one question
  ("what code does this token name?") and treats `UNRESOLVED` as "does not exist". For a claim that
  names a *file* rather than a *symbol*, the index is only authoritative for languages codegraph
  parses; `prisma/schema.prisma`, `hooks.json`, and `docs/*.md` are not in `files` at all. The
  verdict path today (`plan-verifier/plan_verify.py:231-233`):
> claim.verdict = MISSING

- **Three call sites, one predicate.** All three verdicts this bucket changes flow through the two
  `UNRESOLVED` branches — the `new:` one at `plan-verifier/plan_verify.py:219-220`:
> claim.verdict, claim.evidence = OK, "no existing match"
  and the shared touch/remove/swept one at `:231`. Nothing else needs editing, because `remove:`
  and `touch:` both fall through the same early `UNRESOLVED` return before callers are computed.

- **`remove:` gets its honest verdict for free.** Once the path-only branch returns early with
  `OK`, the caller-based `BLOCKED` computation is never reached for an unindexed file — which is
  correct, because the index has no callers for a file it never parsed. Today's `remove:` path is
  at `plan-verifier/plan_verify.py:246-247`:
> if claim.intent == "remove":

- **The laundering hole closes by predicate, not by ordering.** `path::Symbol` claims set both
  `path` and `symbol` — `_shared/manifest.py:129`
> if "::" in raw:
  and the resolve token for them is the symbol — `plan-verifier/plan_verify.py:215`
> token = claim.symbol or claim.path or claim.raw
  Gating the fallback on `claim.symbol is None` is therefore sufficient: no `::Symbol` claim can
  ever reach it.

- **Swept claims inherit the fallback, harmlessly.** Sweep tokens go through the same
  `verdict_claim`, so a backticked path-ish prose token that exists on disk will now render `OK`
  and be suppressed from output — `plan-verifier/plan_verify.py:324`
> if c.verdict == OK and not c.notes:
  Swept claims never enter `strict_fail` (Constraint 2), so the gate is untouched. Net effect: slightly
  quieter output, no verdict semantics change.

- **Doc-ish extensions are already excluded from the sweep**, so this does not flood the sweep with
  markdown noise — `_NONCODE_EXT` filters them before resolution
  (`plan-verifier/plan_verify.py:120-121`):
> if "://" in tok or tok.lower().endswith(_NONCODE_EXT):

- **Containment is a real concern, not a hypothetical.** A bare `touch: /etc/passwd` parses as a
  path claim (it matches `looks_pathish` via the slash — `_shared/resolve.py:57-58`):
> return bool(_PATHISH.match(token)) or "/" in token
  and `Path(root) / "/etc/passwd"` evaluates to `/etc/passwd` under pathlib's absolute-override
  rule. Without an explicit guard the fallback would mark any absolute path on the machine as
  present. The sanctioned form for out-of-repo targets is `external:` (Constraint 9), so absolute
  path-only claims must be refused and stay `MISSING`.

- **Module depth.** `verdict_claim` is a deep function (small signature, all verdict policy inside)
  and this change deepens it further rather than adding a boundary. The one new symbol is a private
  `_on_disk(repo_root, rel) -> bool`. Deletion test: delete it and its containment + `is_file` +
  `OSError` handling reappears inline at three call sites — it earns its keep. It is **not** a seam:
  one adapter, no second implementation, so it stays private and is not promoted to `_shared/`
  (C-05).

- **`check_spec_reuse` is shallow in the depth sense** (thin loop over `spec_reuse_rows`), and this
  change deepens it by moving decoration-stripping inside it rather than asking callers to
  pre-clean names.

- **Runtime dependency added: the filesystem.** Previously a verdict was a pure function of
  (DB, plan text). Now it is a function of (DB, plan text, working tree). Two consequences: verdicts
  become time-dependent (a claim flips when the file is created), and a plan verified against a DB
  from another checkout via `--db` will stat *that* checkout's root, not the plan's neighbourhood.
  That is the frozen behaviour (Constraint 3), and the probe run above exercises exactly that shape.

---

## Chosen Approach

**Option A — disk fallback inside `verdict_claim`, repo root threaded from `verify`.**

### A1. Constant + predicates (module level, `plan-verifier/plan_verify.py`)

```python
ON_DISK_EVIDENCE = "on disk, not in index"      # grill C1 — exact string, do not reword


def _path_only(claim: Claim) -> bool:
    """A claim naming a FILE and no symbol — the only shape the disk fallback serves.

    `"::" not in claim.raw` is load-bearing, NOT redundant with `not claim.symbol`:
    `parse_entry` maps the empty form `foo.py::` to path='foo.py', symbol=None
    (`s.strip() or None`), so a symbol-falsy check alone would let `touch: foo.py::`
    take the disk fallback. The grill freeze is that ANY `::` claim stays index-bound.

    The `external:` raw-prefix check is likewise not redundant with `not claim.external`:
    the FLAG is set only for the absolute form (remainder starts `/` or `~/`). A relative
    `external: src/local.py` falls through with external=False and path = the whole raw
    string, so the flag alone does not exclude it (Constraint 9).
    """
    return (bool(claim.path) and not claim.symbol and not claim.external
            and "::" not in claim.raw
            and not claim.raw.lstrip().startswith("external:"))


def _on_disk(repo_root: Path | None, rel: str) -> bool:
    """True when `rel` names a regular file INSIDE the indexed repo root.

    Directories are not 'exists' (grill 2-a). Absolute paths are refused: `external:`
    is the sanctioned form for out-of-repo targets, and `root / '/abs'` == '/abs'.
    Never raises — a hook must not die on a permission error (CLAUDE.md fail-open).
    """
    if repo_root is None or not rel:
        return False
    p = Path(rel)
    if p.is_absolute() or rel.startswith("~"):
        return False
    try:
        root = repo_root.resolve()
        cand = (root / p).resolve()
        return cand.is_relative_to(root) and cand.is_file()
    except OSError:
        return False
```

`.resolve()` on **both** sides is mandatory, not stylistic. It does two jobs: it collapses `..`
segments so `../outside.json` cannot escape the root, and it keeps the macOS `/tmp` →
`/private/tmp` symlink from producing a false containment failure in tests. A lexical
`is_relative_to` on the unresolved join is **not** sufficient — `root / '../outside.json'` is
lexically "under" `root` until it is resolved, so dropping either `.resolve()` reopens the escape.
A5 #12 pins this. `is_relative_to` requires Python ≥ 3.9; the repo runs 3.12 (audit probe 3).

### A2. `verdict_claim` gains the root

```python
def verdict_claim(con: sqlite3.Connection, claim: Claim, plan_text: str,
                  dynamic_names: set[str], repo_root: Path | None = None) -> None:
```

Default `None` keeps the function callable without a root (fallback simply never fires), so no
existing direct caller can break.

**`new:` branch** — replaces the current unconditional OK at `:219-220`:

```python
    if claim.intent == "new":
        if res.state == _rs.UNRESOLVED:
            if _path_only(claim) and _on_disk(repo_root, claim.path):
                claim.verdict, claim.evidence = COLLISION, ON_DISK_EVIDENCE
            else:
                claim.verdict, claim.evidence = OK, "no existing match"
        else:
            ...unchanged (the `exists: ` + candidate locs form)...
        # UNCHANGED — the dynamic-names note at plan_verify.py:224-227 stays exactly where it is,
        # AFTER the whole if/else and BEFORE the return. Restructuring the branch above must not
        # move it inside a branch, or a `new:` claim whose symbol is in unresolved_refs silently
        # loses its note.
        if claim.symbol and claim.symbol in dynamic_names:
            claim.notes.append(
                f"`{claim.symbol}` already appears in unresolved_refs — something "
                "references this name dynamically")
        return
```

**touch / remove / swept branch** — replaces the current unconditional MISSING at `:231-234`:

```python
    if res.state == _rs.UNRESOLVED:
        if _path_only(claim) and _on_disk(repo_root, claim.path):
            claim.verdict, claim.evidence = OK, ON_DISK_EVIDENCE
        else:
            claim.verdict = MISSING
            claim.evidence = f"no node or file matches {token!r}"
        return
```

The early `return` is what makes `remove:` honest: an unindexed file never reaches the
caller-count code, so it can never produce a fake `BLOCKED`.

### A3. `verify` computes the root once

```python
    con = open_db(db)
    root = repo_root_for(db)
    ...
    for claim in [*manifest.claims, *swept]:
        verdict_claim(con, claim, text, dynamic, root)
```

`repo_root_for` is already imported (`plan-verifier/plan_verify.py:63`):
> `from _shared.db import SchemaError, find_db, open_db, repo_root_for  # noqa: E402`

### A4. REUSE identifier normalization (`check_spec_reuse`)

```python
def _reuse_ident(name: str) -> str:
    """Spec reuse-row name → the identifier a plan would actually write.

    `runFalQueue(...)` → `runFalQueue` · `claim_one(stage=…)` → `claim_one`
    `emitFrame…` → `emitFrame` · `emitFrame...` → `emitFrame`
    Falls back to the original text when stripping would leave nothing.
    """
    n = name.split("(", 1)[0].strip()
    for suffix in ("…", "..."):
        if n.endswith(suffix):
            n = n[: -len(suffix)].strip()
    return n or name.strip()
```

Applied once per row inside the existing loop, before the substring tests at `:180-183`; the
normalized identifier is what gets matched **and** what gets reported in the `REUSE-DROPPED`
finding, so the evidence line names the thing that was searched for. `spec_reuse_rows` itself is
untouched (its parsing of the depth column and `:line` suffixes already works), and
`reuse_dropped` never enters `strict_fail` (Constraint 2), so warn-only survives by construction.

### A5. Tests (`plan-verifier/test_plan_verify.py`)

The existing fixture builds a synthetic DB under `tmp_path` and returns `tmp_path` as the repo
root, so real files can be created next to it and the fallback exercises for free:

> `plan-verifier/test_plan_verify.py:77-78`:
> `def repo(tmp_path: Path) -> Path:`
> `    make_db(tmp_path)`

New cases (all in `TestVerdicts` unless noted):

| # | Case | Expect |
|---|---|---|
| 1 | `touch: hooks.json`, file written to `repo/hooks.json` | `OK`, evidence == `on disk, not in index` |
| 2 | `touch: prisma/schema.prisma::Asset` with the file on disk | `MISSING` (laundering guard) |
| 3 | `new: hooks.json` with the file on disk | `COLLISION`, same evidence |
| 4 | `remove: hooks.json` with the file on disk | `OK`, same evidence, no `BLOCKED` |
| 5 | `touch: subdir/` (a real directory) | `MISSING` |
| 6 | `touch: nope/ghost.json` (nothing on disk) | `MISSING` |
| 7 | `touch: /etc/passwd` | `MISSING` (absolute refused) |
| 8 | CLI `--strict` on a **passing-only** plan: one path-only `touch:` of an on-disk file, no `new:`, no directory claim (`TestCli`) | exit 0 |
| 9 | reuse row `runFalQueue(...)` vs plan text `runFalQueue` (`TestSpecReuse`) | not dropped |
| 10 | reuse rows `claim_one(stage=…)` and `emitFrame...` | not dropped when the bare identifier appears |
| 11 | existing `test_cli_spec_warn_only_never_strict_fails` | unchanged — still exit 0 |
| 12 | `touch: ../outside.json` with `outside.json` created one level ABOVE the fixture root | `MISSING` (escape refused) |
| 13 | plan prose with a backticked `probes/schema.prisma` (file at `repo/probes/schema.prisma`, absent from the DB), no manifest block. The token must NOT be `hooks.json`: `.json` is in `_NONCODE_EXT` (`plan_verify.py:108-109`, filtered at `:120`), so the sweep never creates a row for it and the test would be vacuous. `.prisma` is not filtered and the `/` makes it pathish. | swept verdict `OK`, evidence == `on disk, not in index`, row absent from `render(...)` output; `strict_fail` empty |
| 14 | `touch: foo.py::` (empty symbol form) with `repo/foo.py` on disk and absent from the DB | `MISSING` — `"::" in raw` blocks the fallback even though `parse_entry` set `symbol=None` |
| 15 | `touch: src/db.py` with `repo/src/db.py` written on disk AND present in the fixture `files` table (hoist guard) | evidence is the resolved `node.loc` + caller count, **never** `on disk, not in index` — the index wins whenever it resolves |
| 16 | `touch: external: src/local.py` (relative external form) with `repo/src/local.py` on disk | `MISSING`, plus the existing `external: value must be an absolute path` meta_problem — the raw-prefix check keeps the relative form off the fallback |

### A6. ADR (grill lock 5-a)

Write `plan-verifier/adrs/0001-on-disk-path-only-is-not-missing.md` alongside the implementation,
mirroring the existing per-tool ADR convention (`ssot-diagram/adrs/0001-…md`, `0002-…`, `0003-…`).
Content: why an unindexed-but-present file is OK rather than MISSING, why `::Symbol` is excluded,
why `new:` inverts to COLLISION, and why directories do not count.

### Why A over the alternatives

Option A puts the fallback at the one layer that already owns verdict policy, keeps the frozen
resolver seam untouched, and needs a single threaded parameter with one caller to update.

### Dual-predicate co-satisfiability check (Step 3b)

Load-bearing must/never/only claims and the honest path that satisfies all of them:

| # | Predicate | Pair risk | Resolution |
|---|---|---|---|
| P1 | path-only + on disk **must** be OK | vs P2 | different predicate branches; `_path_only` is the discriminator |
| P2 | `path::Symbol` **must never** become OK because the file exists | vs P1 | `_path_only` requires `claim.symbol` falsy **and** `"::" not in claim.raw` — symbol-falsy alone is NOT sufficient, because `foo.py::` parses to symbol None (§A1). With both conditions the two cannot fire together |
| P3 | **no new** verdict enum / `STRICT_FAILS` member | vs P1, P4 | reuses `OK`/`COLLISION`, both already in the enum |
| P4 | `new:` + on disk **must** be COLLISION | vs P1 | branch is `intent == "new"`, disjoint from the touch/remove path |
| P5 | directories **must never** count as exists | vs P1 | `is_file()` is strictly narrower than `exists()` |
| P6 | evidence text **must** be exactly `on disk, not in index` | vs the existing `"exists: " + locs` COLLISION evidence | the on-disk COLLISION is a *different* branch and emits only the constant; the indexed COLLISION keeps its `exists: …` form. No test asserts a single COLLISION evidence shape (`test_new_collision` asserts the verdict only) |
| P7 | REUSE **must never** fail `--strict` | vs A4 | `reuse_dropped` is not a `Claim` and never enters `strict_fail` |
| P8 | hook **must never** block or die | vs the new filesystem access | `_on_disk` returns False on `OSError`; hook mode already wraps in `run_fail_open` |

No pair requires two mutually exclusive behaviours on one path. Nothing promoted to an Open
Question from this step.

---

## Alternatives Considered

### Option A — disk fallback inside `verdict_claim`, root threaded from `verify` (Recommended)

**Approach:** as specified above.
**Files touched:** `plan-verifier/plan_verify.py` (constant + 2 helpers + 2 branches + 1 call site
+ `check_spec_reuse`); `plan-verifier/test_plan_verify.py` (new cases); `plan-verifier/adrs/0001-*.md` (new).
**Cost:** dev low (~30 lines prod). Runtime: one `stat` per unresolved path-only claim — no LLM, no
scan, no migration. Maintenance: one private helper.
**Risk:** *correctness* — a wrong containment rule would let out-of-repo paths pass as present;
mitigated by the absolute-path refusal + `is_relative_to` + test 7.
**Module depth:** no new module boundary. One private helper `_on_disk` (deletion test: removing it
scatters containment/`is_file`/`OSError` handling across three call sites → earns keep). No new
interface (single adapter → not a seam, stays private). `verdict_claim` is deep and gets deeper;
`check_spec_reuse` is shallow and is deepened rather than wrapped.
**What it defers:** blast-radius for unindexed files (there is none to compute); any language
extractor work (explicitly OUT).
**Constraints check:** C-01 satisfies (no DB write) · C-02 satisfies (entry unchanged) · C-03
satisfies · C-04 satisfies (`OSError` swallowed) · C-05 satisfies (stays private) · C-06 satisfies
(is the change) · C-07 satisfies (no new enum) · C-08 satisfies (warn-only preserved) · C-09
satisfies (one constant) · C-10 satisfies (`is_file`).

### Option B — disk fallback inside `_shared/resolve.py` (Not recommended)

**Approach:** teach `resolve()` (or `_resolve_file`) to return a synthetic `Candidate(kind="file")`
when the index misses but the file is on disk, so every consumer inherits the behaviour.
**Files touched:** `_shared/resolve.py` (+ a root parameter through its signature), and by
implication `diff-verifier/diff_verify.py`, `impact-analyzer/`, and any other resolver consumer.
**Cost:** dev medium; maintenance high — the resolver's contract ("what code does this token
name?") becomes "what code or file exists", which every consumer must re-reason about.
**Risk:** *contract* — `resolve()` is a frozen seam:
> `_shared/resolve.py:1` — `"""_shared.resolve — the lookup core (frozen seam, skeleton-contracts Block 1a)."""`
Changing it silently alters tools outside this bucket's one-surface ceiling.
**Module depth:** no new boundary, but it widens a frozen interface — the opposite of seam
discipline (one requested adapter, N unconsulted ones).
**What it defers:** nothing; it *pulls in* work from other tools' buckets.
**Constraints check:** C-06 satisfies · C-07 satisfies · **C-05 violates** (a shared change with one
real consumer) · scope "one surface" ⚠️ violates (`plan_verify.py` is the declared surface).

### Option C — advisory note only, verdicts unchanged (Not recommended — conservative arm)

**Approach:** keep `MISSING`, append a note ("exists on disk; codegraph has not indexed this file")
to the claim's `notes` list, which `render` already prints under the row.
**Files touched:** `plan-verifier/plan_verify.py` (one branch), tests.
**Cost:** dev very low. Runtime identical. Maintenance minimal.
**Risk:** *does not solve the problem* — `--strict` still exits 1 (Constraint 2 is unaffected by
notes), so orchestrators still hand-patch every Prisma/docs plan. The bucket's stated promise is
that those plans stop failing.
**Module depth:** no change.
**What it defers:** the entire fix.
**Constraints check:** C-06 **violates** (the freeze says not MISSING) · everything else n/a.

### Option D — post-pass in `verify` that rewrites verdicts after `verdict_claim` (Not recommended)

**Approach:** leave `verdict_claim` untouched; after the loop, walk claims whose verdict is
`MISSING` (or `new:`+`OK`) and flip them based on a disk stat.
**Files touched:** `plan-verifier/plan_verify.py` (`verify` only), tests.
**Cost:** dev low; maintenance medium.
**Risk:** *drift* — verdict policy now lives in two places, and any future caller of
`verdict_claim` (the function is public and importable) gets the old, wrong answer. The hook and CLI
both route through `verify` today, so this works — until something calls the verdict function
directly, which is exactly what the test file does (`pv.verify` today, but `verdict_claim` is
exported).
**Module depth:** makes `verify` shallower-by-accretion (orchestration + policy) and leaves
`verdict_claim` lying about its own contract.
**What it defers:** the same cleanup, later.
**Constraints check:** C-06 satisfies · C-07 satisfies · C-09 satisfies · **design-integrity ⚠️**:
two sources of truth for one verdict.

### Rejected alternatives (one line each)

- **New `UNINDEXED` verdict** — freeze forbids a new enum member; also forces every downstream
  `--json` consumer to learn a value.
- **Demote all unindexed `MISSING` to warn** — rejected in the scope (`Q4-a` rejected column); it
  would also stop real ghosts from failing `--strict`.
- **Index Prisma/markdown in codegraph** — explicitly OUT of this program (scope §5 OUT-hard).
- **REUSE relocation lookup via the DB** — OUT (`Q6-a` rejected c); normalization is the cheap fix.
- **Stat root = the plan file's directory** — would give a different answer than the index for a
  plan stored outside the repo (the audit probe's exact shape); the freeze pins the index root.
- **`exists()` instead of `is_file()`** — would make `touch: prisma/` pass, which grill lock 2-a
  forbids.

**Recommended: Option A.** It buys the fix at one file and ~30 lines while leaving the frozen
resolver seam and the verdict enum untouched — the cost is that `verdict_claim` grows a parameter
that only one caller supplies.

**ADR offer:** the chosen option is (1) hard to reverse once plans depend on it, (2) surprising
without context ("why is an unindexed file OK but an unindexed symbol MISSING?"), and (3) the result
of a real trade-off (honesty about the index's coverage vs blast-radius blindness). All three gates
pass — and the grill already locked it as 5-a, so the ADR ships with the implementation (§A6).

**Object-map amendment:** no object map exists in `docs/AI_artifacts/2_ux/` — **no object-map delta.**

---

## Risks

| # | Risk | Mitigation |
|---|---|---|
| R1 | **Blast-radius blindness.** A path-only `touch:` of an unindexed file now passes with no caller analysis, so a plan touching a widely-imported unparsed file gets no `UNACKNOWLEDGED-BLAST`. | Accepted in the scope pre-mortem ("path-only OK skips blast-radius for files the index never parsed"). The ADR states it explicitly so the next reader does not mistake OK for "checked". The index genuinely has no callers to report — the alternative is a fake verdict. |
| R2 | **Verdicts become working-tree-dependent.** The same plan + same DB can verdict differently before and after a file is created, and a plan re-verified in CI on a fresh checkout may differ from the author's machine. | Evidence string `on disk, not in index` makes the reason visible in every row and in `--json`; reviewers can see which rows came from disk rather than the index. |
| R3 | **Containment bypass.** A crafted path (`../../etc/passwd`, an absolute path, a `~`-prefixed path) could mark an out-of-repo file present. | Absolute and `~` refused outright; `.resolve()` on BOTH sides + `is_relative_to(root)` rejects `..` escapes (a lexical check would not — see §A1); test 7 pins the absolute case and **test 12 pins the `../` escape**. Out-of-repo targets have a sanctioned form (`external:`). |
| R4 | **Symlink to an out-of-repo file.** A repo-internal symlink pointing outside resolves outside the root and will be refused, which may surprise someone who legitimately symlinks a file into the repo. | Deliberate: refusing is the fail-closed direction, and the row stays `MISSING` (loud), not silently OK. Recorded in the ADR. |
| R5 | **A plan verified against another checkout's DB (`--db`) stats that checkout.** | Frozen behaviour (Constraint 3, grill: "Stat root = parent of `.codegraph/` (same as the index)"). Documented in the ADR; the audit probe demonstrates the shape. |
| R6 | **Evidence-string drift.** A later edit rewording `on disk, not in index` would break consumers grepping for it. | Single module constant `ON_DISK_EVIDENCE` (new) introduced by this design in §A1; tests assert equality, not substring, so any reword fails loudly. |
| R7 | **REUSE over-normalization.** Stripping at the first `(` could shorten a row whose name legitimately contains parentheses, producing a needle that matches too much. | Fallback to the original text when stripping empties the name; matching is unchanged (substring), and the failure direction is a *missed* REUSE-DROPPED warning, which never gates `--strict`. |
| R8 | **Hook cost.** The hook now stats the filesystem on every plan Write/Edit. | One `stat` per unresolved path-only claim (typically < 10 per plan), bounded and local; the hook's line budget is untouched. |

### Pre-mortem — it is three months later and this shipped badly

1. **"`--strict` stopped catching typo'd paths."** Someone wrote `touch: docs/READ.ME` — a file
   that happens to exist — and the gate passed a plan whose real target was `docs/README.md`.
   *Cause:* disk presence is a weaker check than index presence, and typos that land on a real file
   are now invisible. *Design response:* accepted risk, stated here and in the ADR — the same hole
   already exists for indexed files (a typo landing on a different real file always passed). No
   design change; the evidence string makes the weaker basis visible in the row.
2. **"Every plan row says `on disk, not in index`, so nobody reads the evidence column."** The
   fallback fired far more often than expected because the repo's index was stale/empty, and real
   ghosts hid in the noise. *Design response:* the fallback fires only on `UNRESOLVED` **path-only**
   claims — symbol claims are untouched — so a stale index still fails loudly on every `::Symbol`
   row. Flagged as OQ-2 (whether an all-fallback run deserves a summary note).
3. **"A worker hoisted the fallback above the `resolve` call, and indexed files silently lost their
   caller evidence."** *Cause:* the branch was placed at the top of `verdict_claim` rather than
   inside the two `UNRESOLVED` arms, so a path-only claim that the index CAN resolve short-circuits
   to `on disk, not in index` and never reaches the caller count, the `node.loc` evidence, or the
   `UNACKNOWLEDGED-BLAST` check. Note test 2 does NOT catch this: `prisma/schema.prisma::Asset`
   carries `::`, so `_path_only` excludes it at either placement — it pins the laundering hole, not
   the hoist. *Design response:* §A2 pins the exact insertion points with the surrounding verbatim
   lines, and **test 15** (`touch: src/db.py`, present in the fixture `files` table AND on disk →
   evidence must be the resolved `node.loc` + caller count, never `on disk, not in index`) is the
   test that fails loudly if a worker hoists it.

---

## Open Questions

**OQ-1 — ADR location: tool-local vs repo-wide. — CLOSED 2026-08-18 (ORCH, away Tier A): tool-local.**
Decision: the ADR is written at `plan-verifier/adrs/0001-on-disk-path-only-is-not-missing.md`. No
repo-level ADR folder is created. Recorded below as the reasoning that produced it; not open.
Current state: ADRs exist only under `ssot-diagram/adrs/` (three files, `0001-`…`0003-`); there is
no `docs/adr/` or `docs/architecture/` in this repo. The grill left the path as craft ("ADR: write
(5-a) with impl. Path is craft (tool-local vs `docs/architecture/`)"). The question: does the
MISSING-freeze ADR belong beside the tool that implements it, or in a repo-level ADR folder that
does not yet exist?
**If tool-local (`plan-verifier/adrs/0001-…`):** matches the only existing convention, the ADR sits
next to the code it constrains, and nothing new is invented; the cost is that a reader looking for
repo-wide decisions must know to look inside tool folders.
**If repo-level (`docs/architecture/`):** cross-tool decisions get one home; the cost is creating a
second, competing ADR convention with exactly one occupant while `ssot-diagram/adrs/` keeps three.
Chosen: **tool-local** — one convention beats two, and this decision constrains exactly one
tool's verdict contract.

**OQ-2 — should an all-fallback run emit a summary note?**
Current state: each fallback row carries its own evidence, but the render has no aggregate line.
The question: when every path-only claim in a plan resolved by disk rather than by the index (a
strong smell that the index is stale or empty), should `render` add one note line?
**If yes:** the stale-index case becomes visible at a glance, and pre-mortem cause 2 is defanged;
the cost is a new output line that consumers (av verify-wave parsers) have not seen, plus a
threshold to argue about.
**If no:** output stays byte-stable for existing consumers and the per-row evidence still carries
the truth; the cost is that a wholly-stale index reads as a clean plan for path claims.
Recommendation: **no** for this bucket — it is output-contract surface area beyond the locked
promise, and Bucket 5/6 (`index_empty` / probe states) is where "the index is empty" belongs.

**OQ-3 — REUSE-DROPPED reporting: normalized identifier or the spec's raw cell text?**
Current state: the finding reports `name` as parsed from the spec cell, and the evidence embeds it
in backticks. Under A4 the searched needle is the normalized identifier. The question: which string
should the operator see?
**If normalized (`runFalQueue`):** the message names exactly what was searched, so a false
REUSE-DROPPED is debuggable without opening the spec; the cost is that the row no longer quotes the
spec verbatim.
**If raw (`runFalQueue(...)`):** the message is traceable back to the spec table cell character for
character; the cost is that it shows a string the matcher never used, which is the current confusing
behaviour one layer removed.
Recommendation: **normalized** — the design chose it in §A4; flagged here because it is a
user-visible string change that no lock covers.

---

## Read-set

| `file:line` | What it pinned |
|---|---|
| `plan-verifier/plan_verify.py:76-81` | verdict constants, `STRICT_FAILS`, blast threshold |
| `plan-verifier/plan_verify.py:112-125` | `sweep_tokens` — stopwords + `_NONCODE_EXT` filtering |
| `plan-verifier/plan_verify.py:137-168` | `spec_reuse_rows` — deep-row parsing, `:line` suffix strip |
| `plan-verifier/plan_verify.py:171-190` | `check_spec_reuse` — substring matching, warn-only shape |
| `plan-verifier/plan_verify.py:208-261` | `verdict_claim` — every branch this design edits |
| `plan-verifier/plan_verify.py:264-303` | `verify` — DB resolution, claim loop, `strict_fail` |
| `plan-verifier/plan_verify.py:308-359` | `render` / `to_json` — output surfaces affected |
| `plan-verifier/plan_verify.py:371-390` | `hook_main` — advisory, always returns 0 |
| `plan-verifier/plan_verify.py:395-437` | CLI flags + `--strict` exit contract |
| `_shared/db.py:22-47` | `find_db`, `repo_root_for`, read-only `open_db` |
| `_shared/resolve.py:1-113` | frozen seam: states, `looks_pathish`, `_resolve_file`, `_resolve_symbol` |
| `_shared/manifest.py:48-84` | `Claim` dataclass, key regexes, `_PATHISH_HINT` |
| `_shared/manifest.py:107-134` | `parse_entry` — `external:` / `::` / pathish / bare-ident split |
| `plan-verifier/test_plan_verify.py:22-105` | synthetic DB fixture + `write_plan` helper |
| `plan-verifier/test_plan_verify.py:140-200` | `TestVerdicts` — the class new cases join |
| `plan-verifier/test_plan_verify.py:201-234` | `TestExternal` — the relative-`external:` MISSING case |
| `plan-verifier/test_plan_verify.py:272-330` | `SPEC_REUSE` fixture + `TestSpecReuse` |
| `plan-verifier/design.md:109-160` | verdict table + exit-code contract to amend |
| `manifest.json:48-56` | `plan-verifier` hook registration |

## Assumptions to verify

**AV-1** — `verdict_claim` has exactly one call site, so threading `repo_root` is a one-line ripple. `plan-verifier/plan_verify.py:286`
> verdict_claim(con, claim, text, dynamic)
Why it matters: If a second caller exists (hook path, another tool), it must pass the root or silently keep the old behaviour

**AV-2** — `--strict` is computed from manifest claims only, so swept-claim changes cannot move the gate. `plan-verifier/plan_verify.py:289`
> strict_fail = [c for c in manifest.claims if c.verdict in STRICT_FAILS]
Why it matters: The whole "swept inherits the fallback harmlessly" argument rests on this

**AV-3** — The repo root is the DB's grandparent, not the plan's directory. `_shared/db.py:36`
> return db.parent.parent
Why it matters: Wrong root ⇒ every stat answers about the wrong tree

**AV-4** — A no-`::` path-like entry produces `path` set, `symbol` None. `_shared/manifest.py:133`
> return Claim(intent, raw, raw, None)
Why it matters: `_path_only` is built on this shape

**AV-5** — A `::` in `raw` excludes the disk fallback **even when the symbol part is empty**:
`parse_entry` splits on `::` and maps an empty right-hand side to `symbol=None`, so `foo.py::`
yields path set / symbol None. `_shared/manifest.py:129`
> if "::" in raw:
Why it matters: The laundering guard keys on `"::" not in claim.raw`, not on `claim.symbol` alone;
checking only the symbol would let `touch: foo.py::` reach the fallback (A5 #14 pins this)

**AV-6** — The `claim.external` short-circuit covers the **absolute** form only. `parse_entry` sets
the flag when the remainder starts with `/` or `~/`; a **relative** `external: src/local.py` falls
through with `external=False` and `path` = the whole raw string, so the flag alone does not exclude
it — the `raw`-prefix check in `_path_only` (§A1) is what covers the relative form.
`plan-verifier/plan_verify.py:213`
> claim.verdict, claim.evidence = OK, "declared outside the indexed repo (external:)"
Why it matters: Absolute `external:` paths must not be stat'd against the repo root, and the
relative form must not reach the fallback either (Constraint 9; A5 #16 pins it)

**AV-7** — File resolution consults `files.path` only — nothing on disk. `_shared/resolve.py:73`
> rows = con.execute("SELECT path FROM files WHERE path = ?", (token,)).fetchall()
Why it matters: Confirms the gap being closed is real, not a resolver bug

**AV-8** — `looks_pathish` treats any token containing `/` as a path, including absolute ones. `_shared/resolve.py:58`
> return bool(_PATHISH.match(token)) or "/" in token
Why it matters: Justifies the explicit absolute-path refusal in `_on_disk`

**AV-9** — REUSE matching is a bare substring test on the spec's name. `plan-verifier/plan_verify.py:180`
> if name and name in plan_text:
Why it matters: Normalizing the needle is sufficient; no matcher rewrite needed

**AV-10** — The test fixture's repo root is `tmp_path`, so test files can be created next to the DB. `plan-verifier/test_plan_verify.py:78`
> make_db(tmp_path)
Why it matters: The new tests need a writable root that equals the stat root

**AV-11** — `test_new_collision` asserts the verdict only, not the evidence shape. `plan-verifier/test_plan_verify.py:167`
> assert r["manifest_claims"][0].verdict == pv.COLLISION
Why it matters: A second COLLISION evidence form (P6) is safe only if this holds

**AV-12** — Swept OK rows are already suppressed from output. `plan-verifier/plan_verify.py:324`
> if c.verdict == OK and not c.notes:
Why it matters: Explains why swept fallback hits reduce, not increase, noise
---

## Done (inline, replaces retired success-criteria)

1. `python3 -m pytest plan-verifier/ -q` passes, including the 16 cases in §A5.
2. `python3 -m pytest -q` (whole repo) shows no NEW failures. **The pre-change known-fail set is
   the 3 existing `TestGoldenLive` pilot-drift failures** (recorded in `CLAUDE.md` Build Progress:
   "129 pytest pass / 3 pre-existing `TestGoldenLive` pilot-drift (0 NEW)"). "NEW" means any
   failure that is not one of those 3 — a run that still shows exactly those 3 and nothing else
   satisfies this item; a run showing 2 of them plus a different one does not.
3. The audit probe rerun after the change prints, for a plan claiming `docs/TECH_DEBT.md`:
   `touch` → `OK  on disk, not in index`; `new` → `COLLISION  on disk, not in index`;
   `remove` → `OK  on disk, not in index`; `touch: docs/` → `MISSING`.
   **Combined `--strict` exit is 1, not 0** — that probe deliberately carries two STRICT_FAILS rows
   (`new:` → COLLISION and `touch: docs/` → MISSING), so exit 1 is the only honest result for it.
   Do NOT trim the probe to manufacture exit 0. The exit-0 case is A5 #8, which uses a
   passing-only plan: a path-only `touch:` of an on-disk file, no `new:`, no directory claim.
   (If a later worker trims the probe anyway, A5 #3 and #5 still pin COLLISION and directory-MISSING
   independently of the probe.)
4. `plan-verifier/adrs/0001-on-disk-path-only-is-not-missing.md` exists and states these four rules
   in these words:
   (a) a path-only claim whose file is a regular file under the indexed repo root is **not**
   MISSING — verdict OK with evidence `on disk, not in index`;
   (b) `path::Symbol` is **excluded** from the fallback and stays MISSING when the index has no
   symbol — a file on disk never launders a ghost function (any `::` in the raw entry excludes it,
   including the empty form `foo.py::`);
   (c) `new:` of a path-only file that already exists on disk is **COLLISION**, not OK — an empty
   index is not permission to create;
   (d) **directories do not count** as exists — `is_file()`, never `exists()`.
5. `plan-verifier/design.md` verdict table records the disk fallback. The row of record is
   `plan-verifier/design.md:113`
> | `touch: X` | X exists and resolves to exactly one node/file | `MISSING` (zero matches) / `AMBIGUOUS` (more than one match) |
   The implementation must amend that row's verdict cell to read: `MISSING` (zero matches — unless
   the claim is path-only and the file is a regular file under the repo root, which is `OK` with
   evidence `on disk, not in index`) / `AMBIGUOUS` (more than one match). The `remove: Z` row at
   `:115` gets the same path-only carve-out on its `MISSING` clause.

## Options explored

- **Option B — fallback in `_shared/resolve.py`:** viable but rejected; it widens a frozen seam
  (skeleton-contracts Block 1a) and drags consumers outside this bucket's one-surface ceiling.
- **Option C — advisory note only:** viable but rejected; `--strict` still exits 1, so the bucket's
  promise is unmet.
- **Option D — post-pass in `verify`:** viable but rejected; splits verdict policy across two
  functions and leaves `verdict_claim` returning the wrong answer to direct callers.
- **New `UNINDEXED` verdict / demote-all-to-warn / Prisma extractor / REUSE DB relocation /
  plan-dir stat root / `exists()` instead of `is_file()`:** rejected outright — see Rejected
  alternatives.

## ADR references

- To be written with the implementation: `plan-verifier/adrs/0001-on-disk-path-only-is-not-missing.md`
  (grill lock 5-a; location locked tool-local, OQ-1 CLOSED 2026-08-18).
- Related existing: `ssot-diagram/adrs/0001-reuse-p1-recipe-by-sibling-import-defer-shared-to-phase-b.md`
  (the `_shared/` deferral it records is noted as SUPERSEDED in `CLAUDE.md`; this bucket adds no
  `_shared/` member, so no further amendment).

**Next step:** Design doc written. Run `/writing-detailed-specs` to structure the chosen option into
build steps.
