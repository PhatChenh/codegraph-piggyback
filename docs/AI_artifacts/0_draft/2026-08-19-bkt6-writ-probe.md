# Design — Bucket 6: writ index probe honesty + `writ codegraph-init` honest exit

_Date:_ 2026-08-19 · _Tier:_ FULL (`code-read: full-pipe`) · _Code home:_ `falkor-writ` · _Artifact home:_ `codegraph-piggyback`
_Locked requirements:_ `docs/AI_artifacts/_handoff/2026-08-19-bkt6-writ-probe-grill.md` (LOCKED 2026-08-19)
_Scope:_ `docs/AI_artifacts/_scope/2026-08-16-feedback-bugs-scope.md` Bucket 6 (ITEM-1-writ)
_Run state:_ `docs/AI_artifacts/9_runs/2026-08-19-bkt6-writ-probe.state.md`

## Summary

`codegraph_index.probe()` in falkor-writ collapses two different sqlite failures onto two
wrong names: a db it cannot open reads as `"missing"` (i.e. "never indexed"), and a db whose
`schema_versions` table cannot be read reads as `("unrecognized", frozenset(), {1,5})` — which
every consumer renders as "unknown schema version, found none". Both were reproduced live in
this session (Pre-dispatch audit below). This design adds a fourth honest state,
`"unreadable"`, threads it through the four contract consumers (`freshness()`, the blast-gate
deny copy, the pre-dispatch audit seat, the `writ codegraph-init` wrapper), and makes the wrapper
**fail loudly right after `codegraph init`** when the probe is still not usable, instead of
exiting 0 on a dead index. The index file is never deleted by writ (lock C1); the greenfield
marker is still consumed only on `usable`.

**Owner amendment C1-a (2026-08-19, big-RT), applied throughout:** every bad-state message names
**`writ codegraph-init`**, never `codegraph index`; and there is **no post-init `codegraph index`
retry** — `codegraph init` (Bucket 4) is the repair. Verified live on a junk db:
`codegraph index` → `✗ Failed to index: file is not a database` (exit 1, repairs nothing);
`codegraph init` → unlink + rebuild + `Indexed 1 files` (exit 0). OQ-1 is closed as absorbed.

Chosen: **Option A — plain-string `"unreadable"` return, no retry hop.** It keeps every existing
`probe != "usable"` consumer fail-closed by construction, and it points every operator at the one
command that actually repairs an index.

**OQ-4 decided — option A (ORCH away-craft A2.1, 2026-08-19; owner not re-asked).** A *healthy*
freshly-built index used to probe as not-usable: `codegraph init` leaves a WAL-mode db with no
`-wal`/`-shm` sidecars, `sqlite3.connect(mode=ro)` **succeeds**, and the first **execute** raises
`OperationalError: unable to open database file`. The fix lives in `_connect`, not in `probe()`
(§1.0): plain `mode=ro` first, one `SELECT 1` ping, and only on that specific error a single retry
with `?mode=ro&immutable=1`. After it, the happy path following `codegraph init` probes `usable`,
so nothing in §5 is gated on this any more.

## Pre-dispatch audit

**Consumer list — every call site of `codegraph_index.probe` and of `blast_radius.freshness`
(enumerated by grep over `bin`, `writ`, `.claude`, `hooks`, `tests` in falkor-writ):**

| # | Call site | Predicate today | Touched by this design |
|---|---|---|---|
| 1 | `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/blast_radius.py:285-289` `freshness()` | `state != "usable"` → `"unrecognized"` | **yes** — new pass-through verdict |
| 2 | `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/.claude/hooks/writ-blast-gate.sh:169-202` deny copy | `verdict == 'missing' / 'unrecognized' / else stale` | **yes** — new `unreadable` branch |
| 3 | `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py:975-1005` `check_predispatch` | `probe == "missing"` / tuple `"unrecognized"` | **yes** — new `PRE-UNREADABLE` deny |
| 4 | `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py:1031` marker consume | `probe == "usable"` | no — fail-closed already |
| 5 | `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/writ-codegraph-init.sh:165-175` guard 2 | `"$PROBE" != "usable"` | **yes** — honest exit 1, no retry (C1-a) |
| 6 | `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py:2198` `check_c11` | `probe != "usable"` → `return []` | no — silent by design (M5) |
| 7 | `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py:2278` `check_c12` | `probe != "usable"` → `return []` | no — silent by design (M5) |
| 8 | `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py:2358` `check_c16` | `probe != "usable"` → `return []` | no — silent by design (M5) |
| 9 | `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/writ-doctor.sh:367` | prints `freshness()` verbatim | no — prints the new word for free |
| 10 | `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/blast_radius.py:133-137` `_connect` (duplicate opener behind `:145`, `:169`, `:194`) | its own `mode=ro` URI, not `probe()` | **yes** (OQ-4 A) — delegate to `codegraph_index._connect` |

The scout digest named four consumers; the sweep found **nine `probe`/`freshness` call sites across
six files** (C11/C12/C16 and `writ-doctor.sh` were not in the digest), plus a tenth site that is not
a probe caller at all — `blast_radius`'s duplicate read-only opener, which OQ-4 A folds into the
same `_connect`. All five untouched sites are
untouched *because* they compare against `"usable"`, not against a bad-state name — a new
member of the enum cannot read as usable at any of them.

**Recorded command + output per scope claim.**

Claim 1 — "a db file that sqlite cannot open reads as `missing`":

```
$ mkdir -p $T/r/.codegraph && printf 'junk' > $T/r/.codegraph/codegraph.db && chmod 000 …
$ python - $T/r  # imports falkor-writ bin/lib/codegraph_index
probe(unreadable-perms) = missing
```

Claim 2 — "a readable db with no `schema_versions` table, and a junk-bytes db, both read as
`unrecognized` with an empty found-set":

```
probe(junk-db)   = ('unrecognized', frozenset(), frozenset({1, 5}))
freshness(junk)  = unrecognized
probe(no-schema_versions) = ('unrecognized', frozenset(), frozenset({1, 5}))
freshness(no-schema_versions) = unrecognized
```

Claim 3 — "`codegraph index` refuses when the db file does not exist":

```
$ cd $T && git init -q . && codegraph index $T
✗ CodeGraph not initialized in /var/folders/…/tmp.S2y323rRxQ
ℹ Run "codegraph init" first
exit=1
```

Claim 4 — "the live `codegraph` binary already carries the Bucket 4 init repair":

```
$ readlink -f $(which codegraph) → ~/.codegraph/versions/v1.0.1/bin/codegraph
$ grep -o "Cannot repair index (errcode [^)]*)" ~/.codegraph/versions/v1.0.1/lib/dist/bin/codegraph.js
Cannot repair index (errcode ${health.errcode})
$ ls -la … /lib/dist/bin/codegraph.js → Aug 18 11:38
```

**One contradiction looked for and not found.** Hypothesis: some consumer already special-cases
the empty found-set (`frozenset()`) and prints something honest, which would make the lie
cosmetic. It does not. `writ-blast-gate.sh:189` renders an empty set as the literal word `none`
(`external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/.claude/hooks/writ-blast-gate.sh:189`
— `found_s = ", ".join(str(v) for v in sorted(found)) or "none"`), and
`artifact_claims.py:1002-1004` formats `sorted(found)` unguarded into "found [] but this reader
knows [1, 5]". No consumer distinguishes empty-found from a real foreign version.

## Constraints (Guardrail Checklist)

No `CONSTRAINTS.md` / `docs/rules/` exists in falkor-writ (dispatch: "constraints: (none authored
in falkor-writ)"; verified — `docs/` holds `TECH_DEBT.md`, `OPEN_QUESTIONS.md`, `BUGS.md`, no
constraints file, no `docs/rules/`). The binding checklist is therefore the grill's frozen locks
plus the repo's own critical rules:

- **C-01** Probe enum is exactly `{missing, unreadable, unrecognized, usable}` (grill freeze).
- **C-02** Connect/select failure or absent `schema_versions` → `unreadable`, never
  `unrecognized` with an empty found-set (grill freeze).
- **C-03** `unrecognized` stays for a real integer version outside `{1, 5}` (grill freeze).
- **C-04** Fail-closed: `unreadable` is never treated as usable; edits stay denied (grill freeze).
  Harness scope: "denied" is the Claude Write/Edit path plus the Cursor Write copy wired at
  `~/.cursor/hooks.json`; the Cursor deny envelope is unverified (matrix note (b)). No consumer
  anywhere treats the state as usable — that half of C-04 is harness-independent.
- **C-05** Greenfield marker deleted only on `usable` (grill freeze; today
  `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py:1031` and `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/writ-codegraph-init.sh:172`).
- **C-06** **Never** delete `.codegraph/codegraph.db` from writ (grill lock C1).
- **C-07** **No** post-init `codegraph index` retry (lock 1-a **superseded by C1-a**): after
  `codegraph init`, probe ≠ usable → exit nonzero, marker left, db not deleted, no loop.
- **C-08** Three split deny/audit messages, all naming **`writ codegraph-init`** (C1-a): missing →
  build it; unreadable → rebuild it, then inspect/fix permissions yourself; unrecognized → both
  version sets + the wrapper. `codegraph index` appears in none of them.
- **C-09** piggyback TD-01 stays OPEN; note that the wrapper does **not** add an `index` retry —
  Bucket 4's `codegraph init` is the repair (lock 3-a as amended by C1-a).
- **C-10** ADR ships in falkor-writ with the impl (lock 4-a).
- **C-11** OUT: Write-gate auto-index; changing `KNOWN_SCHEMA_VERSIONS`; a piggyback probe clone;
  MCP `tools/list` (Bucket 5); plugin/event bus; `.codegraph/ready` (grill freeze).
  gate-waive: C6-FICTION — `KNOWN_SCHEMA_VERSIONS` is falkor-writ code, cited by abs `external:` path in the Read-set; it is not a piggyback symbol and not new.
- **C-12** falkor-writ house rule: the index is read-only ground truth — this module "never
  writes to it" (`external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/codegraph_index.py:5-6`).

## Implications

- **`probe()` has two collapse sites, not one.** `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/codegraph_index.py:63-79`
  — `if not _index_path(repo).is_file(): return "missing"` (line 63-64), then
  `except sqlite3.Error: return "missing"` (line 67-68) is collapse #1, and
  `except sqlite3.Error: return "unrecognized", frozenset(), KNOWN_SCHEMA_VERSIONS` (line 71-72)
  is collapse #2. Only the *first* `return "missing"` is honest; the file-absent test already
  ran, so anything reaching line 68 is a file that exists and cannot be opened.
- **The two collapses have different triggers.** Live: a `chmod 000` db hits line 68 (connect
  raises) → `missing`. Junk bytes and a schema-less db do **not** fail at connect (sqlite opens
  lazily) — they hit line 72 → `unrecognized` with an empty found-set. Both were reproduced
  above; a design that only fixes one branch fixes the rarer one.
- **`freshness()` is the only place the enum narrows.** `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/blast_radius.py:288-289`
  — `if state != "usable": return "unrecognized"`. This is the pre-mortem cause #1 the scope doc
  already predicted; without a pass-through line, the honest probe state dies one function later
  and the deny copy still says "unknown schema".
- **The freshness cache cannot go sticky on the new state.** Only a `fresh` verdict is written
  (`external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/blast_radius.py:300-309`,
  `"verdict": "fresh"`), and the read path requires `data.get("verdict") == "fresh"`
  (`:273-274`). `unreadable` therefore inherits the existing never-cached policy with no code
  change — but it needs a test, because that is a policy claim, not a structural guarantee.
- **The audit seat has a second, independent collapse.** `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py:979-980`
  — `except Exception:` / `probe = "missing"  # unreadable index == missing`. That comment is
  the exact belief this bucket retires. After the change the `except` still exists (it also
  covers a failed *import* of the sibling module) but its comment and meaning must be rewritten
  to "module unavailable → fall back to the greenfield path", not "unreadable == missing".
- **`check_predispatch`'s marker branch is where the lie is most expensive.** On `missing` with a
  *matching* greenfield marker the audit proceeds with no finding
  (`external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py:997` — `# else marker-match -> proceed (no finding)`). A
  corrupt index that reads as `missing` can therefore ride a stale greenfield marker straight
  through the pre-dispatch gate. Naming `unreadable` separately closes that path because the
  marker branch is only reachable under `missing`.
- **The wrapper today exits 0 on a dead index.** `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/writ-codegraph-init.sh:172-175`
  — `if [ "$PROBE" != "usable" ]; then … exit 0`. An operator (or an agent following the deny
  copy) sees a zero exit and retries the write, which the blast-gate denies again — the loop the
  grill's lock 6 exists to break.
- **The wrapper reads probe through a `print()`**, so the shell sees the tuple's Python repr for
  `unrecognized` (`external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/writ-codegraph-init.sh:169` — `print(codegraph_index.probe(sys.argv[1]))`).
  Three distinct messages (C-08) need the state and its detail as separate fields, so the inline
  python must print a kind line and a detail line rather than one repr.
- **`codegraph index` repairs nothing this bucket cares about.** Verified live twice: with no db
  file it exits 1 with `CodeGraph not initialized in <path>` (`codegraph/src/bin/codegraph.ts:749-751`).
  quote: "CodeGraph not initialized in"
  On a junk db it exits 1 with `✗ Failed to index: file is not a database`. This is the evidence
  behind C1-a: a retry hop spends a subprocess to fail at exactly the two states it was meant to
  rescue, and prints "Run codegraph init first" right after init ran.
- **Bucket 4's `init` IS the repair (C1-a).** `codegraph init` now probes health
  and unlinks an unreadable db before a fresh init (`codegraph/src/bin/codegraph.ts:629-632`).
  quote: "unlinkUnreadableIndex(projectPath);"
  Verified live on a junk db: `init` unlinks, rebuilds and reports `Indexed 1 files` at exit 0.
  It still refuses `busy`/`unclassified` and touches nothing there
  (`codegraph/src/bin/codegraph.ts:615` quote: "Index database is locked") — those states now exit
  1 from the wrapper with no second attempt, which is the accepted cost of dropping the hop.
- **codegraph's own health vocabulary is five-wide, writ's is four-wide.**
  `codegraph/src/directory.ts:134-146` classifies `usable | empty | unreadable | busy | unclassified`.
  quote: "return { status: row.n === 0 ? 'empty' : 'usable' };"
  writ's `busy` (SQLITE_BUSY on a live daemon) lands in writ's `unreadable`, and writ has no
  `empty` at all (a 0-node db with a known schema version is `usable` to writ). Both are accepted
  by the freeze (`empty` is Bucket 5's problem); the ADR must say so, or the next session reads
  the two enums as a bug.
- **Module depth.** `codegraph_index.py` is a deep module: 4 public functions over a private
  connect/row-map core, one interface used by six files. This change deepens it further (the
  callers get a better-named state without new API surface). Deletion test: removing it would
  scatter sqlite-open + schema-version logic into the blast gate, the audit seat, and the shell
  wrapper — it earns its keep. `freshness()` is the shallow one (a 4-line map over `probe` plus a
  cache); this design does not add to it beyond one pass-through line, and deleting it would
  push the stale-window + cache policy into two callers, so it stays.

## Surface-capability matrix

| Surface / hop | Vendor-enforced? | Payload / contract | Operator surface |
|---|---|---|---|
| `writ codegraph-init` → `codegraph init <path>` (subprocess) | **yes** — exit code is honored today (`external: …/writ-codegraph-init.sh:128-132`) | argv forwarded verbatim; stdout/stderr are clack UI | wrapper stderr line + passthrough exit |
| ~~`writ codegraph-init` → `codegraph index <path>`~~ | **hop removed (C1-a)** — verified live to repair nothing: exit 1 `CodeGraph not initialized` when the db is absent, exit 1 `Failed to index: file is not a database` on a junk db | — | — |
| `writ codegraph-init` → `probe()` (in-process python) | n/a — pure function | returns kind + optional detail | — |
| Blast-gate `PreToolUse` Write/Edit → **Claude Code** | **yes** — honors `hookSpecificOutput.permissionDecision: "deny"` (`external: …/writ-blast-gate.sh:204-211`) | deny reason string | the deny text in the transcript |
| Blast-gate `PreToolUse` Read → **Claude Code** | **no** — WARN only, `additionalContext`, never denies (`external: …/writ-blast-gate.sh:148-149`) | `<writ-blast-gate event="warn">` | injected context |
| Blast-gate Write → **Cursor** (`preToolUse`) | **wired and live** — `~/.cursor/hooks.json` runs `bash /Users/phatchenh/.cursor/hooks/writ-blast-gate.sh` with `"matcher": "Write"`, `"failClosed": true` (verified on this machine 2026-08-19) | that file is a **byte-identical copy** of `.claude/hooks/writ-blast-gate.sh` (verified: `diff` reports no difference), so it carries the same three deny strings | Cursor Write path |
| Blast-gate Read → **Cursor** | **no** — no `preToolUse`/`beforeReadFile` entry for this script on the Read side | — | none (declared loss) |

Corrected fact (this supersedes an earlier "Claude-only, no Cursor copy" reading): the Write gate
**is** wired on Cursor through a **user-level copy** of the script, not through the falkor-writ
source. Two consequences the plan must carry. **(a) Drift:** editing
`.claude/hooks/writ-blast-gate.sh` does **not** update `~/.cursor/hooks/writ-blast-gate.sh`; after
the deny-copy edit the plan must refresh the Cursor copy (`writ-doctor` / the install path) or the
twin silently keeps the old three-branch copy and denies with the pre-fix wording. **(b) Envelope:**
the copy emits Claude's `hookSpecificOutput.permissionDecision` shape, while Cursor's documented
deny field is `permission`; the hook fires on Cursor and its `failClosed` wiring is live, but
whether Cursor honors *this envelope* as a deny is **not verified here** — do not write "the deny
blocks on Cursor" into the spec without a live check. Read WARN stays Claude-only either way
(declared loss, consistent with grill R15 and the "Cursor Read WARN stays Claude-only" risk row).

## Chosen Approach

**Option A.** Six edits in falkor-writ, one new ADR, tests, one live fixture run.

### 1. `bin/lib/codegraph_index.py` — the enum

- Module docstring surface line becomes
  `probe(repo) -> "usable" | "missing" | "unreadable" | ("unrecognized", found, known)`.
- `probe()` body:
  - file absent → `"missing"` (unchanged).
  - `_connect` raises `sqlite3.Error` → `"unreadable"` (was `"missing"`).
  - `SELECT version FROM schema_versions` raises `sqlite3.Error` → `"unreadable"` (was the
    empty-found `unrecognized` tuple). The existing `finally: con.close()` stays.
  - rows read and `found <= KNOWN_SCHEMA_VERSIONS` → `"usable"` (unchanged).
  - otherwise → `("unrecognized", found, KNOWN_SCHEMA_VERSIONS)` (unchanged).
- Docstring states the enum, and states that `unreadable` covers corrupt/truncated/permission-denied
  **and a locked db** (SQLITE_BUSY), because writ has no separate `busy` name.

**§1.0 — `_connect` gains the WAL fallback (OQ-4 A). Do this before the enum change; the enum is
only honest once `_connect` is.** `sqlite3.connect(f"file:{path}?mode=ro", uri=True)` does not
touch the file, so the current `_connect` cannot fail on a WAL-without-`-shm` db — the *first
query* does. New shape:

1. open `file:{path}?mode=ro` as today;
2. ping it with `SELECT 1`;
3. on `sqlite3.OperationalError` whose message is `unable to open database file`: close that
   connection and retry **once** with `file:{path}?mode=ro&immutable=1`, ping again, return it;
4. any other `sqlite3.Error` (and a failing immutable ping) propagates unchanged — callers still
   map it to `unreadable`.

**Plain `ro` leads; `immutable=1` is never the first attempt.** `immutable=1` tells SQLite the file
cannot change, which is a lie while an indexer is writing: leading with it would read a live db
without its WAL and would silently launder the `busy` case that must stay honest. The retry is
reached only after the plain open has already failed with the one error that means "no `-shm` and I
may not create one".

Verified live on a fresh-`init` fixture (no daemon): header `write_version = 2` (WAL), directory
holds only `codegraph.db`; plain `ro` → `OperationalError: unable to open database file`;
`ro&immutable=1` → `schema_versions = [(1,), (5,)]` with **no** sidecar created. Junk bytes raise
`DatabaseError: file is not a database` on **both** URIs and `chmod 000` raises
`unable to open database file` on **both** — so `unreadable` keeps meaning exactly what the grill
froze. No write to the index (C-12 intact), no new enum member (C-01 intact).


### 2. `bin/lib/blast_radius.py` — `freshness()`

Insert one pass-through before the narrowing line:

```python
if state == "missing":
    return "missing"
if state == "unreadable":
    return "unreadable"
if state != "usable":
    return "unrecognized"
```

Docstring return line becomes `"missing" | "unreadable" | "unrecognized" | "stale" | "fresh"`, and
gate-waive: C7-ARMDRIFT — two genuinely different unions: codegraph's `probeIndexHealth` status (TS) vs writ's `freshness()` verdict (Python). They share the word `unreadable` by intent; the matrix and OQ-2 state the fold.
the cache paragraph names `unreadable` in the never-cached list (the code already only writes
`fresh`).

**Second `_connect` — delete the duplicate open, don't copy the fix (OQ-4 A, item 3).**
`blast_radius` carries its own byte-identical read-only opener
(`external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/blast_radius.py:133-137`
— `con = sqlite3.connect(f"file:{_index_path(repo)}?mode=ro", uri=True)`), used by the three index
readers at `:145`, `:169`, `:194`. A probe that says `usable` while these opens still fail is worse
than the original bug: verified live on a fresh-`init` fixture, `report_for_file` returns
`symbols = []`, `blast = set()` — a silent empty blast radius on a healthy index, because each
reader catches `sqlite3.Error` and returns `[]`.

Fix: point `blast_radius._connect` at `codegraph_index._connect` (the module is **already**
imported — `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/blast_radius.py:36`
— `import codegraph_index  # noqa: E402  sibling`). One opener, one fallback. Do **not** copy the
retry into a second place, and do **not** extract a new `_shared` module for it — the sibling
import is the existing pattern in this repo.

**M1 craft — the cache must not skip `probe()` (fail-closed).** Today a `fresh` cache hit returns
`"fresh"` after comparing only the db mtime (`external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/blast_radius.py:279-281`
— `db_mtime = data.get("db_mtime", 0)` / `if db_mtime == _db_mtime(repo):`). An index that becomes
unreadable **without an mtime change** — `chmod 000`, a lock, a sidecar loss — therefore keeps
gating as fresh for up to `FRESH_CACHE_TTL` (300 s, falkor-writ constant at
gate-waive: C6-FICTION — `FRESH_CACHE_TTL` is falkor-writ code, cited by the abs `external:` path on the next line; not a piggyback symbol, not new.
`external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/blast_radius.py:69`)
and the Write proceeds. The docstring's "never masks a state change" claim is false for exactly
this state.

Change: the cache hit becomes a *stale-check* skip, not a *probe* skip. Probe first; only if the
probe says `usable` may a cache hit short-circuit the mtime/staleness arithmetic:

```python
state = codegraph_index.probe(repo)          # ALWAYS, before any cache read
if state == "missing":
    return "missing"
if state == "unreadable":
    return "unreadable"
if state != "usable":
    return "unrecognized"
# usable -> cache may skip only the stale arithmetic below
```

Cost: one sqlite open per gated Write instead of a cached skip — the same open the uncached path
already pays, and the probe is a single-row SELECT. Named test below pins it.

### 3. `.claude/hooks/writ-blast-gate.sh` — deny copy (three messages, C-08)

New branch between `missing` and `unrecognized`:

- `missing` (unchanged): "This repo has no codegraph index … Run `writ codegraph-init` to build
  the index, then retry the write."
- `unreadable` (new, **C1-a wording**): "This repo's codegraph index file exists but cannot be read
  (corrupt, truncated, or locked by another indexer), so Writ cannot verify what this write may
  affect. Run `writ codegraph-init` to rebuild it, then retry the write. If it still fails, the
  file is junk or unreadable by this user — inspect or fix permissions on
  `.codegraph/codegraph.db` yourself; Writ never deletes it."
  The command is **`writ codegraph-init`, not `codegraph index`** (C1-a): `index` is verified to
  repair nothing on a junk db (`✗ Failed to index: file is not a database`, exit 1), while `init`
  unlinks and rebuilds (exit 0).
- `unrecognized` (unchanged): both version sets, plumbed from the probe tuple, plus
  `writ codegraph-init`.

The Read-path WARN needs no branch — it interpolates the verdict
(`external: …/writ-blast-gate.sh:158` — `"This repo's codegraph index is " + verdict`), which now
reads "…is unreadable", and the sentence that follows it already names `writ codegraph-init`
(`external: …/writ-blast-gate.sh:159-160`), which is the C1-a command for every bad state. The
header comment (line 6) gains `unreadable` in its state list.

**Same step, second file — the Cursor twin.** `~/.cursor/hooks/writ-blast-gate.sh` is a
byte-identical copy wired on Cursor `preToolUse` / `Write`; editing only the falkor-writ source
leaves Cursor running the pre-fix three-branch copy. The step is not done until the copy is
refreshed through the supported path (`writ-doctor` / the install script that placed it) and a
`diff` between the two files is silent. Do **not** hand-patch the copy as a separate edit — two
diverging hand-edits is the drift this note exists to prevent.

### 4. `bin/lib/artifact_claims.py` — audit seat

- New id beside the others: `PRE_UNREADABLE = "PRE-UNREADABLE"  # index file present but unreadable`.
- New branch, placed **before** the `missing` branch so the marker path is unreachable for it:

```python
if probe == "unreadable":
    findings.append(Finding(
        PRE_UNREADABLE, "DENY", 1,
        "Codegraph index file exists but cannot be read (corrupt, truncated, or "
        "locked). Run `writ codegraph-init` to rebuild it before dispatch; if that "
        "fails, inspect or fix permissions on the file yourself."))
elif probe == "missing":
    …unchanged marker logic…
```

- The `except Exception: probe = "missing"` fallback keeps its value (a failed *import* of the
  sibling module must not become a bogus unreadable deny) but its comment changes to name what it
  now covers: module import failure, not an unreadable index.
- `check_predispatch`'s docstring branch list grows the sixth branch.
- The marker consume (`probe == "usable"`) and C11/C12/C16 (`probe != "usable"`) are **not**
  edited — they are already correct for a wider enum.

### 5. `bin/writ-codegraph-init.sh` — no retry, honest exit (C1-a)

**There is no second command.** `codegraph init` already ran (unchanged, argv forwarded verbatim);
Bucket 4 made it the repair (unlink-and-rebuild on unreadable, clear-and-reindex on empty). After
guard 4 (unchanged), replace the single guard-2 block with:

1. Read the probe as two lines from the inline python (`kind` on line 1, `detail` on line 2, where
   detail is `found=…;known=…` for `unrecognized` and empty otherwise). One probe, no re-probe.
2. `kind == usable` → consume marker, exit 0 (unchanged behavior and messages).
3. `kind == missing` → print
   `writ-codegraph-init: codegraph init exited 0 but no index database exists at <db>; check the init output above. Marker left for audit-time consume.`
   → exit 1.
4. `kind == unreadable` → print
   `writ-codegraph-init: codegraph init exited 0 but the index at <db> is still unreadable; the file was NOT deleted. Inspect it or fix its permissions yourself, then re-run 'writ codegraph-init'. Marker left for audit-time consume.`
   → exit 1.
5. `kind == unrecognized` → print
   `writ-codegraph-init: index at <db> is at an unrecognized schema version (found {…}; this reader knows {1, 5}). Marker left for audit-time consume.`
   → exit 1.

No branch runs `codegraph index`, and no branch removes any file. Rationale, verified live rather
than assumed: on a junk db `codegraph index` prints `✗ Failed to index: file is not a database`
and exits 1 — it cannot repair what `init` did not; and with the db absent it exits 1 with
`CodeGraph not initialized`. A retry hop would therefore have added a guaranteed-failing subprocess
and a misleading "Run codegraph init first" to the two states it was meant to rescue. The marker is
left on every non-`usable` path, and every message still names audit-time consume as the retiring
path (existing wrapper contract). The `chmod 000` / cannot-open case is explicitly *not* repairable
by either CLI — its message tells the operator to fix permissions themselves.

### 6. ADR — `docs/adr/0001-unreadable-is-not-unrecognized.md` (new directory in falkor-writ)

falkor-writ has **no** `docs/adr/` today (verified: no `adr`/`decisions` directory under the
repo). The ADR ships with the impl (C-10) and records: why `unreadable` ≠ `unrecognized` (an empty
found-set is not a version claim); why writ never deletes the db (C1 — codegraph's `init` owns
unlink, writ owns diagnosis); why writ's four names differ from codegraph's five
(`busy` folds into `unreadable`; `empty` is Bucket 5's); and why the wrapper runs **no**
`codegraph index` retry (C1-a — `init` is the repair; `index` is verified to fail on exactly the
states a retry would target).

### 7. Tests (R4-a) + docs

- `tests/test_codegraph_index.py`: junk-bytes db → `"unreadable"`; valid sqlite without
  `schema_versions` → `"unreadable"`; `chmod 000` db → `"unreadable"` (was `"missing"`);
  existing four probe tests unchanged.
- `tests/test_blast_radius.py`: `freshness()` on a schema-less db is `"unreadable"` (the scope
  doc's pre-mortem cause #1, written as a test); `unreadable` is never cached; **and the M1
  cache-mask test** — warm a `fresh` verdict into the cache, make the db unreadable *without*
  touching its mtime (`chmod 000`, then restore the mtime with `os.utime` to the recorded value),
  call `freshness()` inside the TTL, assert it returns `"unreadable"` and **not** `"fresh"`. This
  is the named test for the fail-closed cache change in §2; without it the cache silently keeps
  gating Writes on a dead index for up to 300 s.
- `tests/test_artifact_claims.py`: `PRE-UNREADABLE` denies on an unreadable index; an unreadable
  index **plus a matching greenfield marker** still denies (the ride-through the enum closes); a
  red audit still preserves the marker.
- `tests/test_blast_gate_hook.py` (**existing** harness — runs the real script against real fixture
  indexes; it already pins the missing / unrecognized / stale deny reasons): add the unreadable
  fixture on a **code** Write → the deny reason **contains** `writ codegraph-init`, **does not
  contain** `codegraph index`, and **does not contain** `stale` (C1-a item 7). This is pre-mortem
  #1's promised test; without this file the `unreadable` branch can be skipped or misordered into
  the final `else` and every other named test still passes green.
- `tests/test_writ_codegraph_init.py`: fake `codegraph` that leaves a junk db → wrapper exits 1,
  marker survives, **db file still exists**, and the fake records that **`codegraph index` was
  never invoked** (the no-retry contract, C1-a item 3 — assert the invocation log holds exactly one
  `init` call); missing-db case → exit 1 with the init-output message; unrecognized case → exit 1
  naming both version sets; usable case → unchanged consume. The existing
  `test_unusable_index_leaves_marker` asserts exit 0 on an unusable index — the new exit-1 contract
  flips it, so that test is **updated, not added**.
- **OQ-4 A tests** (WAL-no-sidecar fixture — build it by running a real `codegraph init` in a temp
  repo, or by copying such a `codegraph.db` alone, without `-wal`/`-shm`):
  (a) `tests/test_codegraph_index.py`: that fixture → `probe() == "usable"`, and the directory still
  holds **no** `-shm`/`-wal` after the call (the fallback must not write);
  (b) `tests/test_blast_radius.py`: an index read on the same fixture (`report_for_file` on a file
  with known symbols) returns **rows, not `[]`** — this is the check that `blast_radius._connect`
  really delegates rather than keeping its own opener;
  (c) junk bytes and `chmod 000` still → `"unreadable"` on both URIs (already listed above; assert
  they did not become usable via the fallback).
- One live `writ codegraph-init` on a fixture repo (not a huge-tree rebuild). With OQ-4 A applied
  this is the **happy path** — expect probe `usable`, marker consumed, exit 0 — not a reproduction
  of anything.
- `docs/TECH_DEBT.md` in piggyback: TD-01 stays OPEN, note that the wrapper deliberately does **not**
  add an `index` retry and that Bucket 4's `init` is the repair (C-09 / C1-a).

### Dual-predicate check (Step 3b)

Load-bearing must/never/only claims and their single honest path:

| Pair | Fight? | Honest path |
|---|---|---|
| "wrapper must repair a dead index" vs "must never delete `codegraph.db`" | no | repair is delegated to Bucket-4 `codegraph init`, which owns the only sanctioned unlink; writ only diagnoses |
| ~~"one `index` try when probe ≠ usable" (lock 5)~~ | **resolved by C1-a** | the retry hop is gone; `init` is the repair, so the predicate pair no longer exists. OQ-1 closed as absorbed |
| "every bad state names `writ codegraph-init`" (C1-a) vs "the state may be unrepairable by any CLI" (`chmod 000`) | no | one command named first, then the honest fallback sentence: inspect / fix permissions yourself; writ never deletes |
| "exit nonzero when still unusable" (lock 6) vs "marker left for audit-time consume" (existing contract) | no | both hold: nonzero exit and marker preserved are independent |
| "unreadable is never usable" vs "C11/C12/C16 stay silent when not usable" | no | silence is not usability; the audit seat denies in the same run |
| "three split messages" vs "same strings on Claude and Cursor" | no | one source script; Cursor runs a byte-identical **copy** wired on Write — same strings, provided the plan refreshes the copy after the edit (matrix note (a)) |

## Alternatives Considered

### Option A — plain-string `"unreadable"`, no retry hop (Recommended; C1-a form)

**Approach:** as specified above.
**Files touched:** `bin/lib/codegraph_index.py` (`_connect` WAL fallback + enum),
`bin/lib/blast_radius.py` (`_connect` delegation + pass-through + cache fail-closed),
`.claude/hooks/writ-blast-gate.sh` (deny branch) **and its `~/.cursor/hooks/` copy**,
`bin/lib/artifact_claims.py` (PRE-UNREADABLE + comment), `bin/writ-codegraph-init.sh` (exit-1
branches), `docs/adr/0001-…md` (new), four test files.
**Cost:** dev low-med (~50–60 lines + ~14 tests) · runtime: one probe per gated Write (the cache
no longer skips it, §2) · maintenance: one more enum member in one docstring-documented contract.
**Risk:** *classification* — a locked (SQLITE_BUSY) db is named `unreadable` and the copy says
"rebuild it", which is the wrong advice while a daemon holds the file. Mitigated by naming
"or locked by another indexer" in the message text.
**Module depth:** no new boundary, no new interface; deepens `codegraph_index` (same API, better
answer). `freshness()` stays a 5-line map.
**What it defers:** writ has no `empty`/`busy` names (Bucket 5 and a later re-grill own those);
the `schema_versions`-empty-table hole (OQ-3).
**Constraints check:** C-01 ✅ · C-02 ✅ · C-03 ✅ (untouched branch) · C-04 ✅ (all consumers
compare to `"usable"`) · C-05 ✅ (consume predicate untouched) · C-06 ✅ (no unlink anywhere) ·
C-07 ✅ (no retry hop at all) · C-08 ✅ · C-09 ✅ · C-10 ✅ · C-11 ✅ (no MCP, no ready-file, no bus,
`KNOWN_SCHEMA_VERSIONS` untouched) · C-12 ✅ (read-only; `mode=ro` connect unchanged).
gate-waive: C6-FICTION — falkor-writ constant, cited by abs `external:` path in the Read-set; not a piggyback symbol, not new.

### Option B — structured return: `("unreadable", reason)` tuple

**Approach:** probe returns a tuple carrying the sqlite message so consumers can print the raw
error ("database disk image is malformed", "no such table: schema_versions").
**Files touched:** same five, plus every consumer that compares `probe == "…"` must switch to a
`state[0]`-style unwrap; the wrapper's two-line print becomes three.
**Cost:** dev med · runtime none · maintenance higher — two return shapes for bad states means
every future consumer must remember which states are tuples.
**Risk:** *contract* — `check_predispatch` already does `isinstance(probe, tuple) and probe[0] == "unrecognized"`
(`external: …/artifact_claims.py:998`); a second tuple state makes that line silently ambiguous
to a careless edit.
**Module depth:** same boundary; the interface widens without the callers needing it — 4 of 9 call
sites only ever ask "usable or not".
**What it defers:** nothing extra.
**Constraints check:** C-01 ⚠️ (the enum's members stop being four plain names) · everything else
as Option A.
**Not selected:** the raw sqlite message is a diagnosis the operator gets from `codegraph init`
itself; buying it costs the enum's flatness, which is exactly what four consumers rely on.

### Option C — enum/dataclass for all four states (deepen the module properly)

**Approach:** `probe()` returns a small frozen dataclass (`state`, `found`, `known`) or a
`StrEnum`; all nine call sites migrate.
**Files touched:** all of Option A plus every consumer body and their existing tests.
**Cost:** dev high · runtime none · maintenance lowest long-term (one shape, no isinstance).
**Risk:** *blast radius* — this rewrites the `unrecognized` deny copy and the marker-consume
predicate, i.e. code the grill explicitly froze as unchanged (C-03/C-05); a regression there is a
false deny on every write in every repo.
**Module depth:** genuinely deeper; real seam only if a second probe implementation appears —
today there is one, so the seam is speculative.
**What it defers:** nothing; it pulls future work forward.
**Constraints check:** C-03 ⚠️ / C-05 ⚠️ (both frozen surfaces get rewritten) · rest as Option A.
**Not selected:** correct shape, wrong bucket. It is a refactor whose risk lands on the exact
predicates this bucket must not disturb; it stays available once `busy`/`empty` force a fifth and
sixth member.

### Rejected alternatives (one line each)

- **Fix the message at each consumer, leave `probe()` alone** — four copies of the same
  correction, and the next consumer inherits the lie (the scout's landmine).
- **Any post-init `codegraph index` retry (gated or not)** — rejected by owner amendment C1-a and
  by live evidence: `index` exits 1 with `Failed to index: file is not a database` on a junk db and
  with `CodeGraph not initialized` when the db is absent. It repairs neither state, so the hop only
  adds a failing subprocess and a misleading instruction.
- **Loop `codegraph index` until usable** — can hang on a large tree; grill rejected, and C1-a
  removed even the single try.
- **Wrapper deletes the db and re-inits** — violates C1/C-06; codegraph's own `init` already owns
  the only sanctioned unlink, gated on its `unreadable` classification.
- **Exit 0 after a failed retry** — the current behavior; it is the reason the operator loops.
- **Add `busy` and `empty` to writ's enum to mirror codegraph** — outside the frozen four; `empty`
  is Bucket 5's contract and would change what `usable` means.
- **`.codegraph/ready` marker** — NEVER IN ORIGINAL SCOPE (grill Q5-a); ADR-0001 in codegraph
  already argues the row-count is the single source of truth.

> Recommended: **Option A** — it buys the honest fourth name and the loud failure at the cost of
> leaving `busy`/`empty` unnamed, which is the tradeoff the frozen enum already chose.

## Risks

| Risk | Mitigation |
|---|---|
| A locked db (live `codegraph daemon`) is named `unreadable` and the copy says "rebuild", which is wrong advice mid-index | Message names "or locked by another indexer" so the reader can judge; the wrapper exits 1 and deletes nothing, so waiting for the indexer to finish and re-running is lossless |
| A healthy fresh index (WAL, no `-shm`) reads as unreadable | **Closed by OQ-4 A** (§1.0): `_connect` retries once with `immutable=1` after the plain `ro` ping fails, and `blast_radius` shares that opener. Pinned by three named tests |
| `immutable=1` reads a db that IS being written (torn/stale read) | The retry is unreachable while a writer holds the db: a live indexer's `-shm` exists, so the plain `ro` ping succeeds and returns first. `busy` therefore still surfaces as `unreadable`, not as a laundered read |
| With the retry dropped (C1-a), a `busy`/`unclassified` db gets no second attempt — `init` refuses and touches nothing, so the wrapper exits 1 on a db that may be perfectly fine once the daemon releases it | Accepted by C1-a: the message names the lock as a possible cause, and re-running `writ codegraph-init` after stopping the indexer is one command. Writ never deletes, so nothing is lost by waiting |
| `freshness()` gains a fifth verdict that some caller string-matches | Only two callers exist (blast-gate, `writ-doctor.sh`); doctor prints it verbatim, blast-gate gets an explicit branch; both are in the read-set |
| Wrapper exit-code change (0 → 1 on bad states) breaks a caller that treats nonzero as fatal | Callers: `writ/cli.py` `codegraph_init` passes the code through to the operator (`external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/writ/cli.py:990-992`); no hook consumes it. That passthrough is the intended loud failure |
| `PRE-UNREADABLE` is a new DENY id that could fire on repos mid-index and block dispatch | It fires only where the old code already denied or lied; and the audit seat's waiver machinery (`gate-waive: PRE-UNREADABLE — …`) applies unchanged |
| The two-line probe print in bash mis-parses when a path contains newlines | Detail line is a fixed `found=…;known=…` shape built from ints, never a path |

## Pre-mortem

Three months on, this failed because:

1. **`freshness()` was updated but the blast-gate's `else` still swallowed it** — the deny copy
   said "stale" for an unreadable index because `unreadable` fell into the final `else`.
   *Design change:* the branch order is specified explicitly (missing / unreadable / unrecognized /
   else stale) and a test asserts the deny reason for an unreadable index contains
   `writ codegraph-init`, not `codegraph index`, and not the word "stale" (C1-a item 7).
2. **The wrapper told everyone to run a command that cannot repair the state it names.** The
   retry hop would have run `codegraph index` on exactly the two states where it is verified to
   exit 1 without repairing anything. *Design change:* C1-a removed the hop entirely; `init` is
   the repair, every message names `writ codegraph-init`, and the unrepairable case
   (`chmod 000`) says so instead of pretending a command fixes it.
3. **`PRE-UNREADABLE` denied dispatch on repos whose index was merely locked by a running daemon,
   and the team learned to waive it by reflex.** *Accepted risk, noted:* writ cannot distinguish
   busy from corrupt without adopting codegraph's errcode map (out of scope). The message names
   "locked" as a cause so the reader can judge, and the waiver is a one-liner with a required
   reason.

## Open Questions

**OQ-1 — CLOSED (absorbed by C1-a, 2026-08-19).** The question was whether the wrapper's
`codegraph index` retry should skip the `missing` state. The owner removed the retry entirely, so
there is no hop left to gate: after `codegraph init`, a non-usable probe exits nonzero with the
state's own message. No residual decision; recorded here rather than deleted so the plan does not
re-derive it.

**OQ-2 — Is `busy` worth its own fifth name later?** — not a blocker. writ folds SQLITE_BUSY into
`unreadable`; codegraph names it separately and refuses to touch the db there
(`codegraph/src/directory.ts:141-142`). **If we keep four:** the copy must keep saying "or locked",
and an operator mid-index is told to rebuild. **If we add `busy` later:** a fifth enum member and a
fifth consumer branch, i.e. a repeat of this bucket. Recommendation: keep four now (frozen), record
in the ADR that `busy` is a deliberate fold so a later re-grill starts from the reason, not the
symptom.

**OQ-3 — A `schema_versions` table that exists but is empty still reads as `usable`.** Today
`found = frozenset()` and `frozenset() <= KNOWN_SCHEMA_VERSIONS` is true, so an index that records
no version at all passes as usable. **If left:** one more silent-usable hole, narrower than the two
this bucket closes (it needs a table present but unpopulated). **If fixed here:** it changes the
meaning of `usable`, which the grill froze as unchanged. Recommendation: leave it, note it in the
ADR's Consequences, and let a later bucket decide — flagged now so it is not re-discovered as a
surprise.

**OQ-4 — CLOSED as option A (ORCH away-craft A2.1, 2026-08-19; Tier-A, owner not re-asked).**
The question was whether `"unreadable"` should also name a *healthy* fresh index — `codegraph init`
leaves a WAL db with no `-wal`/`-shm`, `connect(mode=ro)` succeeds, and the first execute raises
`unable to open database file`. **Decision: A.** `_connect` keeps plain `mode=ro` as the first
attempt, pings `SELECT 1`, and retries once with `?mode=ro&immutable=1` only on that exact error
(§1.0); `blast_radius._connect` delegates to the same opener (§2). Rejected B (ship as-is): every
fresh init in a repo with no running daemon would deny Writes and fail the wrapper, re-creating the
bucket's headline symptom through a new door. Residual, accepted: `immutable=1` would be a stale
read of a db under active write — unreachable in practice because a live writer's `-shm` makes the
plain `ro` ping succeed first, so `busy` still surfaces as `unreadable`.

## ADR references

- **New (ships with the impl, falkor-writ):** `docs/adr/0001-unreadable-is-not-unrecognized.md`.
- **Related (codegraph fork):** `codegraph/docs/adr/0001-init-repairs-unusable-index.md` — Bucket
  4's decision that `init` repairs an existence-true but unusable index, including the health
  vocabulary this design deliberately does not copy.
  quote: "Buckets 5 and 6 own their own health/ready unions"
- **Tech debt:** piggyback `docs/TECH_DEBT.md` TD-01 stays OPEN; add a dated note that the wrapper
  deliberately does **not** run a `codegraph index` retry and that Bucket 4's `codegraph init` is
  the repair (C-09 / C1-a). No plugin/event bus, no `.codegraph/ready`.

## Options explored

- **Option B (tuple with sqlite reason)** — viable, not chosen: richer diagnosis, but a second
  tuple-shaped state makes the existing `isinstance(probe, tuple)` unwrap ambiguous.
- **Option C (dataclass/StrEnum for all states)** — viable, not chosen: the right long-term shape,
  but it rewrites the two predicates the grill froze (`unrecognized` copy, marker consume).
- **Per-consumer message fix** — rejected: four copies, lie survives in `probe()`.
- **Any `codegraph index` retry (single, gated, or looped) / wrapper-side delete / exit 0 after
  failure** — rejected per owner amendment C1-a, lock C1, and the live evidence that `index` fails
  on both target states.

## Read-set

gate-waive: C6-FICTION — every symbol below lives in falkor-writ and is cited by abs `external:` path; none is a piggyback symbol and none is new.

- `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/codegraph_index.py:1-140` (probe, `_connect`, `_index_path`, `KNOWN_SCHEMA_VERSIONS`, node readers)
- `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/blast_radius.py:36,63-72,129-200,242-313` (sibling import, `stale_index_days`, `FRESH_CACHE_TTL` (falkor-writ constant), `_index_path`/`_connect` duplicate + its three readers, `_db_mtime`, `_verdict_cache_path`, `freshness`)
  gate-waive: C6-FICTION — `FRESH_CACHE_TTL` is a falkor-writ constant on the cited abs `external:` path; not a piggyback symbol, not new.
- `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py:856-1039` (`PRE_*` ids, `_read_marker`, `_current_tree_sha`, `check_predispatch`)
- `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py:2186-2200,2270-2280,2350-2360` (`check_c11`, `check_c12`, `check_c16` probe guards)
- `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py:255-400` (CITE_RE / EXTERNAL_RE / C3 machinery — cite discipline for this artifact)
- `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/writ-codegraph-init.sh:1-186` (whole wrapper: argv derivation, guards 1–4, marker consume)
- `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/.claude/hooks/writ-blast-gate.sh:1-239` (front door, exemptions, Read WARN, Write deny copy, fail-open envelope)
- `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/writ/cli.py:962-993` (`writ codegraph-init` CLI passthrough)
- `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/tests/test_codegraph_index.py:85-125` · `tests/test_blast_radius.py:300-410` · `tests/test_writ_codegraph_init.py:1-120` · `tests/test_artifact_claims.py:1639-1740`
- `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/writ-doctor.sh:367` (freshness display)
- `codegraph/src/bin/codegraph.ts:560-760` (init dispatch + index refusal) · `codegraph/src/directory.ts:93-161` (`isInitialized`, `probeIndexHealth`) · `codegraph/docs/adr/0001-init-repairs-unusable-index.md`
- `docs/AI_artifacts/_handoff/2026-08-19-bkt6-writ-probe-grill.md` · `docs/AI_artifacts/_scope/2026-08-16-feedback-bugs-scope.md` · `docs/TECH_DEBT.md` · `.village/runs/2026-08-16-feedback-scope-scout/channel/SCOUT_DIGEST.md`

## Assumptions to verify

1. **`_connect` failure is reachable only for an existing file.** `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/codegraph_index.py:63-68` —
   `if not _index_path(repo).is_file(): return "missing"` precedes the connect. Verified live: a
   `chmod 000` db returns `missing` today. Matters: renaming that branch to `unreadable` is only
   honest if the file-absent case cannot reach it.
2. **A junk/schema-less db reaches the SELECT branch, not the connect branch.** Verified live
   (both fixtures returned the `('unrecognized', frozenset(), …)` tuple). Matters: the fix must
   change *both* branches or the common case stays mislabeled.
3. **Every non-listed consumer compares against `"usable"`.** `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py:2198` —
   `if probe != "usable":` (same at :2278, :2358) and `:1031` `if probe == "usable" and not any(...)`.
   Matters: this is what makes the new state fail-closed with zero edits there.
4. **`freshness()` narrows every non-usable, non-missing state to one word.** `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/blast_radius.py:288-289` —
   `if state != "usable":` / `return "unrecognized"`. Matters: without the pass-through the probe
   fix is invisible to the gate.
5. **The freshness cache only ever writes `fresh`.** `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/blast_radius.py:303-308` —
   `"verdict": "fresh"`. Matters: `unreadable` inherits never-cached with no code change; still test it.
6. **The wrapper's guard-2 predicate is a string compare on a printed probe.** `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/writ-codegraph-init.sh:169-172` —
   `print(codegraph_index.probe(sys.argv[1]))` then `if [ "$PROBE" != "usable" ]`. Matters: three
   distinct messages need kind and detail as separate fields.
7. **`codegraph index` fails on both states a retry would target; `codegraph init` repairs one of
   them.** `codegraph/src/bin/codegraph.ts:749-751`.
   quote: "CodeGraph not initialized in"
   Verified live: no db → exit 1 (`Run "codegraph init" first`); junk db → exit 1
   (`✗ Failed to index: file is not a database`); the same junk db under `codegraph init` → exit 0,
   `Indexed 1 files`. Matters: this is the whole evidential basis for C1-a's no-retry rule.
8. **Bucket 4's repair is live in the installed binary**, so the retry is a belt-and-braces path,
   not the primary repair: `codegraph/src/bin/codegraph.ts:623`
   quote: "Cannot repair index (errcode" — and the same string is present in
   `~/.codegraph/versions/v1.0.1/lib/dist/bin/codegraph.js` (built 2026-08-18).
9. **The blast-gate deny is Claude-shaped, and it runs on BOTH harnesses through two files.**
   Envelope: `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/.claude/hooks/writ-blast-gate.sh:204-207` —
   `"permissionDecision": "deny"`. Claude wiring:
   `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/hooks/hooks.json:245,258` and
   `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/templates/settings.json:255`.
   Cursor wiring (verified on this machine 2026-08-19, supersedes any "no Cursor copy" reading):
   `external: /Users/phatchenh/.cursor/hooks.json:84` runs
   `external: /Users/phatchenh/.cursor/hooks/writ-blast-gate.sh` on `preToolUse` matcher `Write`
   with `failClosed: true`, and that copy is byte-identical to the source (`diff` silent, copy
   dated 2026-08-19 11:23). Matters twice: the copy must be refreshed after the deny-copy edit or
   the twin drifts, and the Cursor-side deny envelope is still the Claude shape — verify before any
   downstream doc claims Cursor blocks.
10. **falkor-writ has no ADR directory yet.** No `docs/adr/` or `docs/decisions/` exists (find over
    the repo). Matters: the impl step creates the directory, it does not append to an index.

11. **A freshly built index is WAL-mode with no sidecars, and a read-only probe cannot read it.**
    Verified on a fresh `codegraph init` fixture: header `write_version = 2` (WAL), directory holds
    only `.gitignore` + `codegraph.db`; `file:…?mode=ro` → `OperationalError: unable to open
    database file`; `file:…?mode=ro&immutable=1` → `[(1,), (5,)]` with **no** sidecar created; after
    any read-write open the plain read-only path works and `probe()` returns `usable`. Junk bytes
    stay `DatabaseError: file is not a database` and `chmod 000` stays unreadable under
    `immutable=1`. Matters: this is the evidence behind OQ-4 A — the plain-`ro`-then-`immutable`
    order in `_connect` is what keeps `"unreadable"` meaning a dead index rather than every healthy
    fresh one, and what keeps a live writer on the honest path.
