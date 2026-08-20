# Phase Bucket 6 — writ probe honesty + `writ codegraph-init` honest exit

_Date:_ 2026-08-20
_Design:_ `docs/AI_artifacts/3_design/2026-08-19-bkt6-writ-probe.md` (Option A; RT r1–r8 patched; r9 C1 **ABSORB** judge `ac4ecea7`, not patched)
_Grill:_ `docs/AI_artifacts/_handoff/2026-08-19-bkt6-writ-probe-grill.md` (LOCKED 2026-08-19 + C1-a)
_RT:_ `docs/AI_artifacts/7_reviews/2026-08-19-bkt6-writ-probe-design-redteam-r9.md` (C1 ABSORB; M2 recorder-reset absorbed here)
_Scope:_ `docs/AI_artifacts/_scope/2026-08-16-feedback-bugs-scope.md` Bucket 6 = ITEM-1-writ
_Code home:_ `/Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ`
_Artifact home:_ this piggyback tree. One phase (grill: split forbidden).
_TD-01:_ piggyback `docs/TECH_DEBT.md` stays **OPEN**. Wrapper does **not** add `codegraph index` retry; Bucket 4 `codegraph init` is the repair (C-09 / C1-a).
_OQ:_ OQ-1 CLOSED (C1-a). OQ-4 CLOSED as A. **OQ-5.2 CLOSED as 2-b** (owner 2026-08-20: operator, not a Done-cell). **OQ-5.1 OPEN** (Cursor deny envelope). **OQ-6 OPEN** (Claude cache refresh operator). OQ-2 / OQ-3 recorded, not this phase.

**Judge locks (do not reopen):** enum `{missing, unreadable, unrecognized, usable}`; connect/select fail or missing `schema_versions` → `unreadable`; never auto-delete db; no post-init `codegraph index`; unreadable deny names `writ codegraph-init`. OQ-4 A: first URI exact `file:{db}?mode=ro` (no extra query keys); retry `?mode=ro&immutable=1` only on `unable to open database file`; production `timeout=0`. 5b: `_connect` observes `'database is locked'` on the held writer; no mutation between 5a and 5b. **C1 ABSORB:** runtime wrap of real `sqlite3.connect`; every `bin/lib/` connect is a `_connect` call whose URI is one of the two pinned URIs; **fresh recorded list per `_connect` drive**. Design §7 AST “fails by construction” is **superseded**. No `hooks.json` edit. No `install.sh --all/--only`. No overwrite of `~/.cursor/hooks/writ-blast-gate.sh`. R15: same `probe()` + wrapper; deny copy harness-agnostic **in source**.

## Purpose

`probe()` stops lying: a file that exists but cannot be opened, and a db whose `schema_versions` table cannot be read, both return the plain string `"unreadable"` instead of `"missing"` or empty-found `"unrecognized"`. `freshness()` passes that word through. The blast-gate and audit seat print a distinct unreadable sentence that names `writ codegraph-init`. After `codegraph init`, the wrapper exits **1** when probe is still not usable, leaves the greenfield marker, and never deletes the db. A healthy WAL-without-`-shm` init probes `usable` via one exact-string `_connect` retry.

## Pre-dispatch audit

Codegraph MCP in this workspace indexes **piggyback**. falkor-writ source was read via `codegraph_explore` with `projectPath=/Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ` plus live `rg` in that tree (this session 2026-08-20).

### 1. Consumer list per changed identifier

| Identifier | Consumers | Affected? |
|---|---|---|
| `codegraph_index.probe` | `freshness()` (`external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/blast_radius.py:285`); `check_predispatch` (`external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py:978`); `check_c11` (`:2198`); `check_c12` (`:2278`); `check_c16` (`:2358`); wrapper inline python (`external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/writ-codegraph-init.sh:169`); blast-gate unrecognized branch (`external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/.claude/hooks/writ-blast-gate.sh:185`); tests | YES — return enum grows `"unreadable"`. C11/C12/C16 **probe-guards** stay `!= "usable"` (no edit). Marker consume (`:1031`) stays `== "usable"` (no edit). |
| `codegraph_index._connect` | `probe`, `enclosing_symbol`, `_nodes_with_ids`, `interface_members`, `_edges` (same file); after this phase also `blast_radius._connect`, `_c16_resolve_node`, `_c12_container` | YES — WAL ping + one `immutable=1` retry; `timeout=0` |
| `blast_radius.freshness` | blast-gate Write deny (`writ-blast-gate.sh:169`); Read WARN (`:151`); `writ-doctor.sh:367` | YES — pass-through `"unreadable"`; probe **before** cache |
| `blast_radius._connect` | `nodes_in_file` (`:169`), `blast_nodes` (`:194`), `_nodes_with_ids` (`:145`) → `report_for_file` (`:412`) | YES — **delete** duplicate open; delegate to `codegraph_index._connect` |
| `_c16_resolve_node` / `_c12_container` | `check_c16` / `check_c12` after usable guard | YES — opener fold only; try/except + return contract unchanged |
| blast-gate deny `reason` | Claude PreToolUse Write/Edit (source); pytest `HOOK` (`external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/tests/test_blast_gate_hook.py:33`); live Cursor copy is **operator**, not a consumer of this impl | YES — new `unreadable` branch **in source**. Envelope shape unchanged (OQ-5.1 OPEN). |
| `PRE_INDEX` / `PRE_SCHEMA` / new `PRE_UNREADABLE` | `check_predispatch` findings | YES — new id + two full-sentence replacements |
| wrapper guard 2 | `writ/cli.py:codegraph_init` passthrough (`external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/writ/cli.py:990-992`) | YES — exit 1 + three messages. CLI **not** edited. |
| `KNOWN_SCHEMA_VERSIONS` (`external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/codegraph_index.py:27`) | probe usable/unrecognized | NO — frozen (C-11). gate-waive: C6-FICTION — falkor-writ constant on that abs `external:` path; not a piggyback symbol, not new. |
| piggyback `manifest.json` / Claude `settings.json` / Cursor `hooks.json` | harness install | NO |

### 2. Recorded command + output per scope claim

This session, cwd `/Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ`:

```
$ rg -n 'sqlite3\.connect' bin/lib/
bin/lib/codegraph_index.py:48:    con = sqlite3.connect(f"file:{_index_path(repo)}?mode=ro", uri=True)
bin/lib/blast_radius.py:135:    con = sqlite3.connect(f"file:{_index_path(repo)}?mode=ro", uri=True)
bin/lib/artifact_claims.py:2166:        con = sqlite3.connect(
bin/lib/artifact_claims.py:2488:        con = sqlite3.connect(

$ python3 -c "import sqlite3; print(sqlite3.sqlite_version)"
3.51.0

$ ls docs/adr
ls: docs/adr: No such file or directory

$ rg -c unreadable tests/test_blast_gate_hook.py
(empty — zero hits)

$ sed -n '172,175p' bin/writ-codegraph-init.sh
if [ "$PROBE" != "usable" ]; then
    echo "writ-codegraph-init: codegraph index not usable (probe='$PROBE'); marker left for audit-time consume" >&2
    exit 0
fi
```

Live probe collapses (carried from design Pre-dispatch audit; not re-derived this seat): `chmod 000` db → `probe = missing`; junk / no-`schema_versions` → `('unrecognized', frozenset(), frozenset({1, 5}))`.

### 3. One contradiction looked for and not found

Looked for a fifth `sqlite3.connect` under `bin/lib/` (would make “fold three, leave one” incomplete). `rg` returns exactly the four sites above. `project_rules._connect` is FalkorDBLite, not sqlite. `writ/origin_context.py` is a different db, outside `bin/lib/`, out of scope.

Looked for an existing consumer that already special-cases empty `found` as honest “cannot read”. blast-gate `:189` renders empty as `"none"`; PRE-SCHEMA formats `sorted(found)` as `[]`. No contradiction — the lie is still the live copy.

Looked for `docs/adr/` to append — absent. Impl **creates** the directory.

## Already built (reuse, do not rebuild)

gate-waive: C6-FICTION — every symbol below lives in falkor-writ and is cited by abs `external:` path; none is a piggyback symbol and none is new.

| Function/Module | Location | What it does | How this spec uses it | Depth |
|---|---|---|---|---|
| `KNOWN_SCHEMA_VERSIONS` | `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/codegraph_index.py:27` | `frozenset({1, 5})` | **do not change** (C-11). Unrecognized still names both sets. gate-waive: C6-FICTION — falkor-writ constant on that abs `external:` path; not a piggyback symbol, not new. | deep |
| `_index_path` | `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/codegraph_index.py:42-43` | `repo/.codegraph/codegraph.db` | `_connect` / `probe` keep using it | deep |
| `_connect` | `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/codegraph_index.py:46-50` | `sqlite3.connect(f"file:{path}?mode=ro", uri=True)` + `Row` factory; **no timeout, no ping, no retry** | **extend** (comp 1). Sole production opener after fold. | deep |
| `probe` | `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/codegraph_index.py:53-79` | absent → `"missing"`; connect `Error` → `"missing"`; SELECT `Error` → empty-found tuple; `found <= known` → `"usable"` | **extend** (comp 2). Callers of `== "usable"` / `!= "usable"` reuse as-is. | deep |
| `enclosing_symbol` / `callers_of` / `interface_members` / `_edges` | `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/codegraph_index.py:86-206` | node readers via `_connect` | inherit WAL fallback; no API change | deep |
| sibling import | `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/blast_radius.py:36` `import codegraph_index` | already on path | blast `_connect` delegates; **no new `_shared` module** | n/a |
| `FRESH_CACHE_TTL` | `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/blast_radius.py:69` = 300 | fresh-only cache window | cache-mask test uses it; value unchanged. gate-waive: C6-FICTION — falkor-writ constant on that abs `external:` path; not a piggyback symbol, not new. | deep |
| `freshness` | `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/blast_radius.py:256-312` | cache-then-probe; `state != "usable"` → `"unrecognized"`; only writes `"fresh"` (`:303-308`) | **extend** (comp 4) | shallow |
| `report_for_file` | `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/blast_radius.py:403-420` | symbols + blast; empty on sqlite error | WAL fixture assert 4: `"symbols"` nonempty | deep |
| `check_predispatch` | `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py:931-1039` | five index branches; `except Exception: probe = "missing"` (`:979-980`); consume only `probe == "usable"` (`:1031`) | **extend** (comp 6). Consume predicate **untouched**. | deep |
| `PRE_INDEX` / `PRE_SCHEMA` / `PRE_MARKER` / `PRE_SECTION` | `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py:858-861` | audit ids | add `PRE_UNREADABLE` (new) beside them | deep |
| `_c16_resolve_node` | `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py:2155-2184` | own `mode=ro` open; `len(rows) != 1` → `None` | opener → `_connect`; rest unchanged | deep |
| `_c12_container` | `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py:2478-2509` | same own open | same fold | deep |
| `check_c11` / `check_c12` / `check_c16` | `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py:2271,2351,2187` | `probe != "usable"` → `[]` | **no probe-guard edit** (M5 silence) | deep |
| blast-gate deny envelope | `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/.claude/hooks/writ-blast-gate.sh:204-211` | `hookSpecificOutput.permissionDecision: "deny"` | **unchanged shape**. New reason branch only. | deep |
| blast-gate missing / unrecognized copy | `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/.claude/hooks/writ-blast-gate.sh:174-195` | already names `writ codegraph-init` | missing unchanged; unrecognized unchanged; insert `unreadable` **before** `else stale` | deep |
| wrapper guards 1, 3, 4 + `codegraph init` hop | `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/writ-codegraph-init.sh:1-186` | argv forward; exit passthrough of init | **keep**. Replace guard-2 block only. | deep |
| `codegraph_init` CLI | `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/writ/cli.py:966-992` | locate script, pass exit | CONSUMER-ONLY | deep |
| pytest HOOK path | `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/tests/test_blast_gate_hook.py:33` | execs falkor-writ source, **not** `~/.cursor/hooks/` | blast-gate tests stay here | deep |
| `make_index` / `_make_usable_index` / `fake_codegraph` | `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/tests/test_codegraph_index.py:65-79`; `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/tests/test_writ_codegraph_init.py:47-54,93-106` | DELETE-journal (`write_version=1`) fixtures; fake init is `exit 0` | **forbidden** as WAL-fixture builders. Keep for enum / consume / existing tests. | deep |
| `test_unusable_index_leaves_marker` | `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/tests/test_writ_codegraph_init.py:143-151` | asserts **exit 0** on unusable | **update** to exit 1 (not add a parallel) | deep |
| Bucket 4 `codegraph init` repair | installed `~/.codegraph/versions/v1.0.1` (design audit) | unlink unreadable, refuse busy | wrapper’s only repair; no `index` hop | n/a |

### Partially built (extend)

| What exists | What must change | Why |
|---|---|---|
| `_connect` one URI, no ping | plain `ro` + `SELECT 1` + exact-string retry `immutable=1`; `timeout=0` both connects | OQ-4 A; WAL-without-`-shm` else looks unreadable |
| `probe` connect-fail → `"missing"`; SELECT-fail → empty tuple | both → `"unreadable"` | C-02 |
| `freshness` cache before probe; non-usable → `"unrecognized"` | probe **first**; pass `"unreadable"`; cache only after usable | M1 cache-mask; pre-mortem 1 |
| `blast_radius._connect` duplicate URI | body = `codegraph_index._connect(repo)` (keep Row if not already set — `_connect` already sets it) | silent empty blast on WAL |
| `_c16_resolve_node` / `_c12_container` private opens | `codegraph_index._connect(repo)` | same silent-empty on WAL |
| blast-gate `else: # stale` | `elif verdict == 'unreadable':` exact sentence; header comment gains the word | else swallows new verdict as stale |
| `check_predispatch` five branches + comment “unreadable == missing” | sixth branch **before** `missing`; comment = import-fail only; PRE-INDEX / PRE-SCHEMA full-sentence replace | marker ride-through; C-08 |
| wrapper `:172-175` exit 0 | two-line probe print; three nonzero messages; no `index`; no unlink | lock 6 / C1-a |
| `test_unusable_index_leaves_marker` exit 0 | exit 1 + db still exists + invocation log = one `init` | C1-a |

### Not built (create)

- `"unreadable"` as a first-class `probe` / `freshness` string
- `PRE_UNREADABLE` (new) = `"PRE-UNREADABLE"`
- `docs/adr/0001-unreadable-is-not-unrecognized.md` (new `docs/adr/` in falkor-writ)
- WAL+lock **one** `def` test (asserts 1–4 + 5a/5b + 6a–6d) with **runtime wrap** one-opener pin (C1 ABSORB)
- unreadable fixtures in `test_codegraph_index.py` / `test_blast_radius.py` / `test_blast_gate_hook.py` / `test_artifact_claims.py`
- live `writ codegraph-init` on a real-`codegraph init` WAL fixture (wrapper happy path)
- piggyback TD-01 dated note (OPEN stays)

## Feature overview

Happy path: `codegraph init` leaves WAL (`header[18:20] == b'\x02\x02'`) with no `-wal`/`-shm`. `_connect` opens `file:{db}?mode=ro` (`timeout=0`), `SELECT 1` raises `unable to open database file`, retries once `file:{db}?mode=ro&immutable=1` (`timeout=0`), ping succeeds. `probe` → `"usable"`. Wrapper consumes marker, exit 0. Blast readers and C12/C16 resolve rows, not `[]`/`None`. No sidecars created (C-12).

Missing: file absent → `"missing"` (unchanged). Blast-gate / PRE-INDEX copy name `writ codegraph-init`. Wrapper after init still-missing → exit 1, marker left, db not deleted.

Unreadable: connect `sqlite3.Error`, or SELECT `schema_versions` `sqlite3.Error` (table absent counts), or SQLITE_BUSY (`'database is locked'`). `probe` / `freshness` → `"unreadable"`. Never cached. Deny / PRE-UNREADABLE / wrapper messages as specified below. **Retry must not fire** on `'database is locked'`.

Unrecognized: real integer version outside `{1, 5}` — still the tuple. PRE-SCHEMA replacement names both sets + wrapper. Empty found-set is **no longer** this state.

Fail-closed: no consumer treats `"unreadable"` as usable (`== "usable"` / `!= "usable"` predicates). Greenfield marker deleted only on `"usable"`.

## Out of scope

- **Cursor live-hook body copy** (`~/.cursor/hooks/writ-blast-gate.sh`) — OQ-5.2 = 2-b; operator follow-up, same class as OQ-6. **Not** a Done-cell. Impl **must not** `install` onto that path.
- **Cursor deny envelope** (flat `permission`) — OQ-5.1 OPEN. Do not emit dual envelope this phase. Do not write “the deny blocks on Cursor.”
- **Claude plugin-cache refresh** — OQ-6 OPEN; `bin/writ-refresh-plugin-cache.sh` is operator, not a Done-cell. C-04 Claude row = **source pytest**, not live session.
- **`busy` / `empty` as writ names** — OQ-2 / Bucket 5. SQLITE_BUSY folds into `unreadable`.
- **Empty `schema_versions` table still `usable`** — OQ-3; grill froze `usable` unchanged.
- **`hooks.json` / `settings.json` / `install.sh --all/--only`** — grill freeze.
- **Write-gate auto-index; change `KNOWN_SCHEMA_VERSIONS`; piggyback probe clone; MCP `tools/list`; plugin bus; `.codegraph/ready`** — C-11. gate-waive: C6-FICTION — `KNOWN_SCHEMA_VERSIONS` is falkor-writ code, cited by abs `external:` path in Already-built; not a piggyback symbol, not new.
- **Delete `.codegraph/codegraph.db` from writ** — C1 / C-06.
- **Post-init `codegraph index`** — C1-a.
- **`writ/cli.py`**, **`writ-doctor.sh`** (prints new word for free), C11/C12/C16 **guards**, marker-consume predicate.
- Design §7 **AST walk** over `bin/lib/*.py` as the one-opener pin — **superseded** (C1 ABSORB). Do not implement that walk.

## Constraints

- **C-01** enum exactly `{missing, unreadable, unrecognized, usable}` — grill.
- **C-02** connect/select fail or absent `schema_versions` → `unreadable`, never empty-found unrecognized — grill.
- **C-03** `unrecognized` stays for a real integer outside `{1, 5}` — grill.
- **C-04** unreadable never usable. Claude deny = source script + pytest. Cursor deny unverified (OQ-5.1). Live Claude = OQ-6.
- **C-05** marker deleted only on `usable` — `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py:1031` and wrapper consume path **untouched** as predicates.
- **C-06** never delete the db from writ — grill C1.
- **C-07** no post-init `codegraph index` — C1-a.
- **C-08** every bad-state / PRE-* message contains `writ codegraph-init`; does **not** contain ``Run `codegraph index` ``; does **not** contain `Run the codegraph index`; PRE-SCHEMA does **not** contain `Rebuild the index`; unreadable blast-gate does **not** contain `stale`. Noun phrase “codegraph index file” is legal. Where this spec gives a full sentence, tests assert **equality**.
- **C-09** piggyback TD-01 OPEN; note: wrapper does not add `index` retry.
- **C-10** ADR ships in falkor-writ with the impl.
- **C-11** OUT list above.
- **C-12** index read-only; `_connect` never creates `-wal`/`-shm` (assert 3 **and** post-assert-4 listing).
- **R15** same `probe()` + wrapper; deny strings harness-agnostic **in source**. Live Cursor copy may lag until operator refresh — accepted.
- **No `hooks.json`.** No Village `install.sh` for this bucket.

## Assumptions

Design `## Assumptions to verify` carried as A1–A11 (floor). A12–A14 added by this decomposition.

| ID | Assumption | Source implication | What would prove it wrong |
|---|---|---|---|
| A1 | `_connect` failure is reachable only for an existing file. `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/codegraph_index.py:63-68` — `if not _index_path(repo).is_file(): return "missing"` precedes the connect. Verified live: a `chmod 000` db returns `missing` today. Matters: renaming that branch to `unreadable` is only honest if the file-absent case cannot reach it. | design assump 1 | Absent-file path reaches the connect `except` (is_file true for a dangling name, or order swapped) |
| A2 | A junk/schema-less db reaches the SELECT branch, not the connect branch. Verified live (both fixtures returned the `('unrecognized', frozenset(), …)` tuple). Matters: the fix must change *both* branches or the common case stays mislabeled. | design assump 2 | Junk db raises at `_connect` after OQ-4 A (would skip SELECT mapping) |
| A3 | Every non-listed consumer compares against `"usable"`. `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py:2198` — `if probe != "usable":` (same at :2278, :2358) and `:1031` `if probe == "usable" and not any(...)`. Matters: this is what makes the new state fail-closed with zero edits there. | design assump 3 | A consumer string-matches `"missing"` / `"unrecognized"` only and treats anything else as usable |
| A4 | `freshness()` narrows every non-usable, non-missing state to one word. `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/blast_radius.py:288-289` — `if state != "usable":` / `return "unrecognized"`. Matters: without the pass-through the probe fix is invisible to the gate. | design assump 4 | A third narrowing site exists outside freshness |
| A5 | The freshness cache only ever writes `fresh`. `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/blast_radius.py:303-308` — `"verdict": "fresh"`. Matters: `unreadable` inherits never-cached with no code change; still test it. | design assump 5 | Cache write path stores other verdicts |
| A6 | The wrapper's guard-2 predicate is a string compare on a printed probe. `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/writ-codegraph-init.sh:169-172` — `print(codegraph_index.probe(sys.argv[1]))` then `if [ "$PROBE" != "usable" ]`. Matters: three distinct messages need kind and detail as separate fields. | design assump 6 | Wrapper already parses a tuple / JSON |
| A7 | `codegraph index` fails on both states a retry would target; `codegraph init` repairs one of them. Verified live: no db → exit 1 (`Run "codegraph init" first`); junk db → exit 1 (`✗ Failed to index: file is not a database`); same junk under `codegraph init` → exit 0, `Indexed 1 files`. | design assump 7 | Live `index` starts repairing junk |
| A8 | Bucket 4's repair is live in the installed binary, so the retry is a belt-and-braces path, not the primary repair: quote `"Cannot repair index (errcode"` in `~/.codegraph/versions/v1.0.1/lib/dist/bin/codegraph.js` (built 2026-08-18). | design assump 8 | Installed binary lacks unlink-unreadable |
| A9 | The blast-gate deny is Claude-shaped, and it runs on BOTH harnesses through two files. Envelope: `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/.claude/hooks/writ-blast-gate.sh:204-207` — `"permissionDecision": "deny"`. Claude wiring: `hooks/hooks.json` + plugin cache (OQ-6). Cursor wiring: `~/.cursor/hooks.json` runs `~/.cursor/hooks/writ-blast-gate.sh` on `preToolUse` matcher `Write` with `failClosed: true`. **Spec overlay (owner 2-b):** impl does **not** refresh that Cursor file; live copy is operator follow-up. Envelope honor on Cursor remains OQ-5.1. No downstream doc may claim Cursor blocks until OQ-5.1 closes. | design assump 9 + owner 2-b | Cursor copy is the pytest HOOK (it is not — `:33` is source) |
| A10 | falkor-writ has no ADR directory yet. No `docs/adr/` or `docs/decisions/` exists (re-verified this session: `ls docs/adr` → No such file). Matters: the impl step creates the directory, it does not append to an index. | design assump 10 | `docs/adr/` already exists with a 0001 |
| A11 | A freshly built index is WAL-mode with no sidecars, and a read-only probe cannot read it — and the repo's own test fixtures are NOT that shape. Real `codegraph init`: `header[18:20] = b'\x02\x02'`; plain `ro` execute → `unable to open database file`; `immutable=1` → schema rows; listing `[.gitignore, codegraph.db]`. `make_index` / `_make_usable_index`: `header[18:20] = b'\x01\x01'`; plain `ro` already usable. Junk stays `file is not a database`; `chmod 000` stays unreadable under both URIs. | design assump 11 | Live `codegraph init` starts leaving DELETE journal / sidecars |
| A12 | Exactly four `sqlite3.connect` call sites exist under `bin/lib/` (this session `rg`, output in Pre-dispatch audit). Folding three of them leaves `_connect` as the only opener. | C1 ABSORB / design §2 inventory | A fifth site appears (or `from sqlite3 import connect` already in `bin/lib/`) |
| A13 | `_c16_resolve_node` / `_c12_container` do `import sqlite3` **inside** the function (`artifact_claims.py:2164,2486`) and look up `sqlite3.connect` at call time. A wrap of stdlib `sqlite3.connect` therefore observes them **until** they are folded. After fold, only `_connect` should appear. | C1 ABSORB | Module-level `from sqlite3 import connect` binds before the test patch |
| A14 | `sqlite3.connect` timeout is the **second positional** (`database, timeout=5.0, …`). A pin that only reads `kwargs["timeout"]` fails an honest `connect(uri, 0, uri=True)`. | r9 measurement (not a new product rule) | Production uses a sqlite wrapper that drops the positional |

## Component dependency order

### 1. `_connect` WAL fallback (OQ-4 A)

**Goal.** A healthy post-`init` WAL db with no sidecars is readable; a locked DELETE db is not laundered to usable.
**Build.** `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/codegraph_index.py:46-50`. (1) `sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=0)` — first URI **exact equality**, no extra query keys (`immutable`, `nolock`, `vfs=…` all forbidden on attempt 1). (2) `SELECT 1`. (3) On `sqlite3.OperationalError` with message **exactly** `unable to open database file`: close, retry once `file:{path}?mode=ro&immutable=1` with `timeout=0`, ping again, return. (4) Any other `sqlite3.Error` (including `'database is locked'`) and a failing immutable ping **propagate**. Keep `row_factory = sqlite3.Row`. Docstring: never lead with `immutable=1`.
**Depends on.** None.
**Assumes.** A11, A14.
**Done when.** Production `_connect` sets `timeout=0` on every connect. First recorded URI on a real-init WAL fixture is exactly `f"file:{db}?mode=ro"`; second contains `immutable=1`. Locked DELETE + `BEGIN EXCLUSIVE` held: `_connect` raises `OperationalError` `'database is locked'`, **one** connect, retry did not fire.

### 2. `probe()` enum

**Goal.** File-exists-but-dead is `"unreadable"`, not `"missing"` or empty-found unrecognized.
**Build.** `codegraph_index.py:53-79`. File absent → `"missing"` (unchanged, **must stay first**). `_connect` raises `sqlite3.Error` → `"unreadable"`. `SELECT version FROM schema_versions` raises `sqlite3.Error` → `"unreadable"` (keep `finally: con.close()`). `found <= KNOWN_SCHEMA_VERSIONS` → `"usable"`. Else tuple unrecognized. Module docstring surface: `probe(repo) -> "usable" \| "missing" \| "unreadable" \| ("unrecognized", found, known)`. `unreadable` covers corrupt / truncated / permission-denied **and locked** (no fifth `busy` name).
**Depends on.** Comp 1 (enum is only honest once `_connect` is).
**Assumes.** A1, A2.
**Done when.** Junk bytes → `"unreadable"`; sqlite without `schema_versions` → `"unreadable"`; `chmod 000` → `"unreadable"`; foreign version `9` still tuple; absent path still `"missing"`.

### 3. One opener — fold duplicates

**Goal.** Every `bin/lib/` index open goes through `codegraph_index._connect`.
**Build.** `blast_radius._connect` (`:133-137`) delegates to `codegraph_index._connect` (sibling already imported `:36`). `_c16_resolve_node` (`:2166-2168`) and `_c12_container` (`:2488-2490`) same; keep each function’s try/except and return contract; **copy the retry nowhere**. Do not extract `_shared`.
**Depends on.** Comp 1.
**Assumes.** A12, A13.
**Interface shape.** Callers still see `_connect(repo) -> Connection`; the retry is hidden.
**Done when.** Runtime wrap pin (comp 9) shows every `bin/lib/` connect is `codegraph_index._connect` with URI ∈ `{f"file:{db}?mode=ro", f"file:{db}?mode=ro&immutable=1"}`. Assert 4: `report_for_file` symbols nonempty; `_c16_resolve_node` not `None`; `_c12_container` not `None` on the **same** WAL fixture; listing after those calls still has no `-wal`/`-shm`.

### 4. `freshness()` pass-through + fail-closed cache

**Goal.** Gate sees `"unreadable"`; a chmod/lock without mtime change cannot stay `"fresh"` inside TTL.
**Build.** `blast_radius.py:256-312`. **Always** `state = codegraph_index.probe(repo)` **before** any cache read. Then:

```python
if state == "missing":
    return "missing"
if state == "unreadable":
    return "unreadable"
if state != "usable":
    return "unrecognized"
# usable -> existing cache / stale arithmetic only
```

Docstring return: `"missing" \| "unreadable" \| "unrecognized" \| "stale" \| "fresh"`. Cache paragraph names `unreadable` in the never-cached list (write path already only `"fresh"` — keep).
**Depends on.** Comp 2.
**Assumes.** A4, A5.
**Done when.** Schema-less db → `freshness() == "unreadable"` (not `"unrecognized"`). Warm `"fresh"` cache, `chmod 000` + restore mtime via `os.utime`, call inside TTL → `"unreadable"` not `"fresh"`. Unreadable never written to cache.

### 5. Blast-gate deny copy (source only)

**Goal.** Unreadable Writes are denied with the specified sentence, not `"stale"` / unrecognized `{none}`.
**Build.** `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/.claude/hooks/writ-blast-gate.sh:169-202`. New branch **between** `missing` and `unrecognized`. Header comment (`:6`) adds `unreadable`. Read WARN interpolates verdict (`:158`) — no new branch.

**`unreadable` reason, verbatim (equality pin):**

```
This repo's codegraph index file exists but cannot be read (corrupt, truncated, or locked by another indexer), so Writ cannot verify what this write may affect. Run `writ codegraph-init` to rebuild it, then retry the write. If it still fails, the file is junk or unreadable by this user — inspect or fix permissions on `.codegraph/codegraph.db` yourself; Writ never deletes it.
```

Missing copy unchanged (`:174-178`). Unrecognized copy unchanged (`:191-194`). Envelope unchanged (`:204-211`).

**Must not:** overwrite `~/.cursor/hooks/writ-blast-gate.sh`; edit any `hooks.json`; invoke `agent_village/scripts/hooks/install.sh`. Same strings live **in source**; Cursor copy refresh is operator (OQ-5.2 = 2-b), same class as OQ-6.
**Depends on.** Comp 4 (verdict word).
**Assumes.** A9.
**Done when.** Pytest against `HOOK = REPO / ".claude" / "hooks" / "writ-blast-gate.sh"`: code Write on unreadable fixture → `permissionDecisionReason` **equals** the sentence above; contains `writ codegraph-init` and `cannot be read`; does not contain `unrecognized`, ``Run `codegraph index` ``, `Run the codegraph index`, or `stale`. **No** `diff -q` against `~/.cursor/hooks/` in CI or the plan Done-cell.

### 6. Audit seat

**Goal.** Unreadable cannot ride a greenfield marker; PRE-INDEX / PRE-SCHEMA no longer instruct `codegraph index`.
**Build.** `artifact_claims.py` `check_predispatch` (`:931-1005`). Add `PRE_UNREADABLE = "PRE-UNREADABLE"  # index file present but unreadable` beside `:858-861`. Branch **before** `missing`:

**PRE-UNREADABLE message, verbatim:**

```
Codegraph index file exists but cannot be read (corrupt, truncated, or locked). Run `writ codegraph-init` to rebuild it before dispatch; if that fails, inspect or fix permissions on the file yourself.
```

**PRE-INDEX replacement, verbatim** (delete `Run the codegraph index`):

```
No codegraph index for this repo. Run `writ codegraph-init` before dispatch, or mark the repo greenfield (`writ predispatch-audit --mark-greenfield <artifact>`).
```

**PRE-SCHEMA replacement, verbatim** (delete sentence-initial `Rebuild the index`):

```
Codegraph index at an unrecognized schema version: found {sorted(found)} but this reader knows {sorted(known)}. Run `writ codegraph-init` to rebuild the index at a known schema version.
```

`except Exception: probe = "missing"` **keeps the value**; comment becomes “module import failure → greenfield path”, **not** “unreadable == missing”. Docstring branch list grows the sixth. Marker consume (`:1031`) and C11/C12/C16 guards **not** edited.
**Depends on.** Comp 2.
**Assumes.** A3.
**Done when.** Unreadable index → `PRE-UNREADABLE` DENY. Unreadable **plus matching marker** still DENY (not proceed). Red audit still preserves marker. PRE-INDEX / PRE-SCHEMA messages **equal** the replacements (PRE-SCHEMA formatted with the fixture’s version sets). Belts: contains `writ codegraph-init`; no ``Run `codegraph index` ``; no `Run the codegraph index`; PRE-SCHEMA no `Rebuild the index`. Existing `:1670` `"index" in msg.lower()` does **not** substitute.

### 7. Wrapper honest exit (C1-a)

**Goal.** After `codegraph init`, still-not-usable is exit 1, marker left, db not deleted, `index` never invoked.
**Build.** `writ-codegraph-init.sh:165-175`. One probe, two printed lines: `kind` then `detail` (`found=…;known=…` for unrecognized, empty otherwise). `usable` → consume marker, exit 0 (unchanged messages). Else **no** `codegraph index`, **no** unlink:

- `missing` → `writ-codegraph-init: codegraph init exited 0 but no index database exists at <db>; check the init output above. Marker left for audit-time consume.` → exit 1
- `unreadable` → `writ-codegraph-init: codegraph init exited 0 but the index at <db> is still unreadable; the file was NOT deleted. Inspect it or fix its permissions yourself, then re-run 'writ codegraph-init'. Marker left for audit-time consume.` → exit 1
- `unrecognized` → `writ-codegraph-init: index at <db> is at an unrecognized schema version (found {…}; this reader knows {1, 5}). Marker left for audit-time consume.` → exit 1

Guards 1/3/4 unchanged. `writ/cli.py` unchanged (already passes exit).
**Depends on.** Comp 2.
**Assumes.** A6, A7, A8.
**Done when.** Fake `codegraph` that leaves junk db: wrapper exit 1, marker survives, **db file still exists**, invocation log holds **exactly one** `init` and **zero** `index`. Missing-db: exit 1 with the init-output sentence. Unrecognized: exit 1 names both version sets. `test_unusable_index_leaves_marker` **updated** from exit 0 → exit 1. Happy path **not** proven with `_make_usable_index` / `fake_codegraph` — that is the live check in comp 9.

### 8. ADR

**Goal.** Next session does not re-litigate the four names or auto-delete.
**Build.** Create `docs/adr/` in falkor-writ. New `docs/adr/0001-unreadable-is-not-unrecognized.md`: why `unreadable` ≠ `unrecognized` (empty found-set is not a version claim); writ never deletes (codegraph `init` owns unlink); writ’s four names vs codegraph’s five (`busy` folds; `empty` is Bucket 5); no `codegraph index` retry (C1-a). Record OQ-3 hole and OQ-2 fold as consequences, not as reopen.
**Depends on.** Comp 2, 7 (decisions it records).
**Assumes.** A10.
**Done when.** File exists in falkor-writ and states those four reasons.

### 9. Tests + live WAL wrapper + C1 ABSORB pin

**Goal.** Pins cannot green a lock-skipping `_connect`, a private `bin/lib/` opener, or a mixed recorder.
**Build.** Tests in falkor-writ only (R4-a).

**9a. Enum / freshness / audit / hook / wrapper** — as Partially-built + comps 2, 4–7 Done-when. `chmod 000` fixtures belong here, **never** as assert 5’s lock stand-in.

**9b. ONE function** `def test_…` holding asserts **1–4 and 5a–5b** (and 6a–6d / 6b runtime) **in that order**. WAL `db`/`repo` from **real `codegraph init`** in a temp git repo. Then, same function, locked DELETE db + `BEGIN EXCLUSIVE` writer **held open** through 5b. **No mutation of any kind between 5a and 5b** (no rebuild, chmod, unlink, rewrite). Forbidden WAL builders: `make_index`, `_make_usable_index`, `_index_usable`, copy-a-db-alone unless step 1 asserts WAL header.

1. `header[18:20] == b'\x02\x02'`.
2. `sqlite3.connect(f"file:{db}?mode=ro", uri=True)` + `SELECT 1` raises `OperationalError` `unable to open database file`.
3. `probe(repo) == "usable"`; listing has no `-wal`/`-shm`.
4. Same repo: `report_for_file(...)["symbols"]` nonempty; `_c16_resolve_node` not `None`; `_c12_container` not `None`. **Re-list after 4:** still no sidecars.
5a. On locked DELETE (`schema_versions={1,5}`, writer held, reader `timeout=0`): plain `ro` execute → `str(e) == 'database is locked'`. Forbidden substitutes: chmod 000, absent, junk.
5b. **Same fixture, writer still open, recorder reset (see 9c):** `codegraph_index._connect(repo)` raises `OperationalError` `'database is locked'` attributed to the **first** recorded connect; recorder length **exactly 1** (retry did not fire); then `probe(repo) == "unreadable"`. If 5b takes ~5 s, production `_connect` is missing `timeout=0`.

6a (static, `_connect` own source only): exactly two `sqlite3.connect(` call sites.
6b (runtime, WAL fixture, **fresh list**): exactly two recorded calls; `recorded[0].uri == f"file:{db}?mode=ro"` (**equality; no extra keys**); `recorded[1].uri` contains `immutable=1`; every call’s **resolved timeout is 0** (kwarg `timeout=0` **or** positional second arg `0` — do not require `timeout` in kwargs). Forbidden: constants-only / `src.index` order.
6c (static): second call-site literal contains `immutable=1`.
6d (static): second connect inside `If` whose test compares against exact `'unable to open database file'`.
7. Separate tests: junk + chmod 000 → `"unreadable"` on **both** URIs.

**9c. C1 ABSORB — runtime wrap replaces design §7 AST one-opener (judge `ac4ecea7`).** Design claim that a private `immutable=1` opener via `import sqlite3 as sq` / `sqlite3.dbapi2.connect` / `getattr` / bound local **“fails by construction”** under the specified AST walk is **false** (r9 C1). **Do not implement that walk.**

Must-write: wrap the **real** `sqlite3.connect` (`unittest.mock.patch("sqlite3.connect", wraps=sqlite3.connect)` or equivalent that still opens) for the WAL+lock test. Recorder captures `(uri, timeout, stack)`. A connect whose first `bin/lib/` frame is not `codegraph_index._connect` **fails**. Every such URI must be one of the two pinned URIs above.

**Fresh recorded list per `_connect` drive** (absorbs r9 M2): 5b (“exactly one”) and 6b (“exactly two”) share one `def` and may share the shim **object**, but **`recorded.clear()` or a new list immediately before each `_connect`/`probe` drive** that asserts a count. Do not accumulate assert-3’s WAL connects into 5b’s “exactly one”.

**9d. Live wrapper happy path.** One real `writ codegraph-init` on a fixture built by real `codegraph init` (not `fake_codegraph` + DELETE). Expect probe `usable`, marker consumed, exit 0. Record observed `write_version`; if it is 1, the check does not count.

**Depends on.** Comps 1–7.
**Assumes.** A11, A12, A13, A14.
**Decisions.** Q: positional vs keyword `timeout=0`? Production: keyword. Test: resolved timeout == 0. Leaning keyword in source because A14’s kwargs-only assert is a trap.
**Done when.** 9a–9d all hold. One-opener is the **runtime wrap**, not an AST file count.

### 10. piggyback TD-01 note

**Goal.** TD-01 stays OPEN with an accurate repair story.
**Build.** `docs/TECH_DEBT.md` TD-01: dated note that the wrapper deliberately does **not** run `codegraph index` and that Bucket 4 `codegraph init` is the repair (C-09 / C1-a). Status remains OPEN. No plugin bus. No `.codegraph/ready`.
**Depends on.** Comp 7 (what the note describes).
**Done when.** Note present; status still OPEN.

## Handoff notes

- **Contract with FCV / plan:** verify A1–A14 against current falkor-writ lines; plan files = the extend/create lists. WAL+lock pins are one `def`. Cursor copy and Claude cache are **operator follow-ups**, not plan steps.
- **C1 ABSORB annotation for FCV:** if FCV still sees design §7 “ast walk … fails by construction”, treat that sentence as **superseded** by spec 9c. Do not “verify” the AST walk into the plan.
- **Open uncertainty:** OQ-5.1 (Cursor envelope), OQ-6 (Claude cache), OQ-2 (`busy` later), OQ-3 (empty version table). Residual MAJOR may exist only as those numbered OQs.
- **Suggested research:** none required before planning. Live Cursor deny check is OQ-5.1, later.
- **R15:** deny copy is command text in **one source file**. Live Cursor twin lag is accepted until the operator copies; do not reopen `hooks.json`.
