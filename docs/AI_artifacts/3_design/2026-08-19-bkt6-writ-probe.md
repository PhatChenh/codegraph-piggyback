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
| 7 | `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py:2278` `check_c12` | `probe != "usable"` → `return []` | probe-guard **no** (silence by design, M5); **opener yes** — `_c12_container` (`:2488-2490`) folds into `codegraph_index._connect` |
| 8 | `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py:2358` `check_c16` | `probe != "usable"` → `return []` | probe-guard **no** (silence by design, M5); **opener yes** — `_c16_resolve_node` (`:2166-2168`) folds into `codegraph_index._connect` |
| 9 | `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/writ-doctor.sh:367` | prints `freshness()` verbatim | no — prints the new word for free |
| 10 | `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/blast_radius.py:133-137` `_connect` (duplicate opener behind `:145`, `:169`, `:194`) | its own `mode=ro` URI, not `probe()` | **yes** (OQ-4 A) — delegate to `codegraph_index._connect` |

The scout digest named four consumers; the sweep found **nine `probe`/`freshness` call sites across
six files** (C11/C12/C16 and `writ-doctor.sh` were not in the digest), plus a tenth site that is not
a probe caller at all — `blast_radius`'s duplicate read-only opener, which OQ-4 A folds into the
same `_connect`. RT-r2 found **two more** private openers inside `artifact_claims`
(`_c16_resolve_node`, `_c12_container`), folded by the same rule (§2). The untouched *probe-guard*
sites are untouched *because* they compare against `"usable"`, not against a bad-state name — a new
member of the enum cannot read as usable at any of them; rows 7–8 are untouched as guards and
touched as openers, which are different lines in different functions.

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
  Harness scope, split by evidence:
  - **Claude Write/Edit — the SOURCE script emits a deny Claude honors; the LIVE file is the plugin
    cache (RT-r5 M2; the earlier flat "verified deny" is retracted).** The envelope
    `hookSpecificOutput.permissionDecision: "deny"` is honored by Claude Code and is emitted by
    `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/.claude/hooks/writ-blast-gate.sh:204-211`
    — which is also the only file pytest executes
    (`external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/tests/test_blast_gate_hook.py:32-33`).
    A live Claude session does **not** run that file:
    `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/hooks/hooks.json:245,258` invokes
    `bash ${CLAUDE_PLUGIN_ROOT}/.claude/hooks/writ-blast-gate.sh`, and on this machine the `writ@writ`
    `installPath` is `/Users/phatchenh/.claude/plugins/cache/writ/writ/1.6.1` (verified 2026-08-19 from
    `~/.claude/plugins/installed_plugins.json`). So C-04 on Claude claims exactly this much: **the
    source emits the deny, proven by test.** Landing it in a running session is an operator step
    (refresh the cache, restart Claude) — **OQ-6**, deliberately **not** a Done-cell of this bucket.
  - **No consumer treats the state as usable** — harness-independent, structural (every predicate is
    `== "usable"` / `!= "usable"`).
  - **Cursor Write — NOT verified as a deny; OQ-gated (OQ-5.1).** The script is wired
    (`external: /Users/phatchenh/.cursor/hooks.json:84-86`, `failClosed: true`) and is a byte-identical
    copy of the Claude source, so it emits **only** Claude's nested envelope. Cursor's documented deny
    is flat `{"permission":"deny",…}` and "Claude nesting alone did NOT block a Write on this machine"
    LIVE (`external: /Users/phatchenh/all-projects/vibe-coding-setup/agent_village/docs/cursor/CURSOR-KNOWLEDGE.md:246-255`).
    Until OQ-5.1 is decided with a live Cursor check, C-04 holds **on Claude only**; the Cursor row must
    not be written up as a deny anywhere downstream.
- **C-05** Greenfield marker deleted only on `usable` (grill freeze; today
  `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py:1031` and `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/writ-codegraph-init.sh:172`).
- **C-06** **Never** delete `.codegraph/codegraph.db` from writ (grill lock C1).
- **C-07** **No** post-init `codegraph index` retry (lock 1-a **superseded by C1-a**): after
  `codegraph init`, probe ≠ usable → exit nonzero, marker left, db not deleted, no loop.
- **C-08** Three split deny/audit messages, all naming **`writ codegraph-init`** (C1-a): missing →
  build it; unreadable → rebuild it, then inspect/fix permissions yourself; unrecognized → both
  version sets + the wrapper. **The banned thing is the repair *command*, not the noun.** No message
  instructs the operator to run `codegraph index` — i.e. the literal command string
  ``Run `codegraph index` `` (and any other imperative form of it) appears in none of them,
  **including the audit-seat findings** PRE-INDEX and PRE-SCHEMA, which carry the command today (§4).
  The **noun phrase** "codegraph index file" / "no codegraph index for this repo" stays legal and is
  used by the specified missing / unreadable / PRE-INDEX sentences on purpose — a substring ban on
  the bare two words `codegraph index` would fail this design's own copy (RT-r3 M1). Live check on
  the exact specified sentences (this session, `python3`):

  ```
  missing       noun 'codegraph index'=True  cmd 'Run `codegraph index`'=False 'writ codegraph-init'=True  'stale'=False
  unreadable    noun 'codegraph index'=True  cmd 'Run `codegraph index`'=False 'writ codegraph-init'=True  'stale'=False
  unrecognized  noun 'codegraph index'=True  cmd 'Run `codegraph index`'=False 'writ codegraph-init'=True  'stale'=False
  PRE-INDEX     noun 'codegraph index'=True  cmd 'Run `codegraph index`'=False 'writ codegraph-init'=True  'stale'=False
  PRE-SCHEMA    noun 'codegraph index'=False cmd 'Run `codegraph index`'=False 'writ codegraph-init'=True  'stale'=False
  ```
  (`missing` / `unrecognized` are the verbatim strings live in
  `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/.claude/hooks/writ-blast-gate.sh:174-195`;
  the other three are this design's specified replacements, §3 and §4.)

  **The backticked form is not the only imperative — RT-r4 M1.** The live audit-seat sentences carry
  *un-backticked* instructions (`"Run the codegraph index before dispatch"` at
  `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py:987-989`,
  `"Rebuild the index at a known schema version."` at `:1002-1004`), so a ban on
  ``Run `codegraph index` `` alone is green on a copy that **keeps** the old instruction and merely
  appends `writ codegraph-init` beside it. Live proof this session (`python3`, exact strings — LIVE =
  on-disk today, GAMED = old sentence + wrapper token appended, SPECIFIED = §4's replacement):

  ```
  PRE-INDEX LIVE       has-wrapper=False ban`cmd`=False ban'Run the codegraph index'=True  | r3-ban passes=False r4-ban passes=False
  PRE-INDEX GAMED      has-wrapper=True  ban`cmd`=False ban'Run the codegraph index'=True  | r3-ban passes=True  r4-ban passes=False
  PRE-INDEX SPECIFIED  has-wrapper=True  ban`cmd`=False ban'Run the codegraph index'=False | r3-ban passes=True  r4-ban passes=True
  PRE-SCHEMA LIVE      has-wrapper=False ban'Rebuild the index'=True  | r3-ban passes=False r4-ban passes=False
  PRE-SCHEMA GAMED     has-wrapper=True  ban'Rebuild the index'=True  | r3-ban passes=True  r4-ban passes=False
  PRE-SCHEMA SPECIFIED has-wrapper=True  ban'Rebuild the index'=False | r3-ban passes=True  r4-ban passes=True
  ```

  (Note `SPECIFIED` PRE-SCHEMA says "…to rebuild the index at a known schema version", lowercase, so
  the case-sensitive ban on the sentence-initial `Rebuild the index` discriminates the gamed copy
  without forbidding the honest wording.)

  So every test written against C-08 pins **all four**: contains `writ codegraph-init`; does **not**
  contain ``Run `codegraph index` ``; does **not** contain the un-backticked imperative
  `Run the codegraph index`; and, for PRE-SCHEMA, does **not** contain `Rebuild the index`
  (unreadable additionally: does **not** contain `stale`). Where the design specifies a full
  replacement sentence, the test asserts that sentence **exactly** — an equality assert is the only
  pin an append cannot game.
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
| Blast-gate `PreToolUse` Write/Edit → **Claude Code** | **yes, envelope-wise** — honors `hookSpecificOutput.permissionDecision: "deny"` (`external: …/writ-blast-gate.sh:204-211`). **But the file a live session execs is `${CLAUDE_PLUGIN_ROOT}/.claude/hooks/writ-blast-gate.sh` = the plugin cache (`~/.claude/plugins/cache/writ/writ/1.6.1` on this machine), not the clone pytest runs** — cache refresh + Claude restart is operator work, **OQ-6** | deny reason string | the deny text in the transcript, **after** the cache carries the new copy |
| Blast-gate `PreToolUse` Read → **Claude Code** | **no** — WARN only, `additionalContext`, never denies (`external: …/writ-blast-gate.sh:148-149`) | `<writ-blast-gate event="warn">` | injected context |
| Blast-gate Write → **Cursor** (`preToolUse`) | **wired — deny NOT verified (OQ-5.1)**: `~/.cursor/hooks.json:84-86` runs `bash /Users/phatchenh/.cursor/hooks/writ-blast-gate.sh` with `"matcher": "Write"`, `"failClosed": true` (verified on this machine 2026-08-19), but the script emits only Claude's nested envelope and the script always exits 0 | that file is a **byte-identical copy** of `.claude/hooks/writ-blast-gate.sh` (`diff` silent, re-run this session), so it carries the same deny **strings**; whether Cursor treats the envelope as a deny is OQ-5.1 | Cursor Write path — deny unproven |
| Blast-gate Read → **Cursor** | **no** — no `preToolUse`/`beforeReadFile` entry for this script on the Read side | — | none (declared loss) |

Corrected fact (this supersedes an earlier "Claude-only, no Cursor copy" reading): the Write gate
**is** wired on Cursor through a **user-level copy** of the script, not through the falkor-writ
source. Two consequences the plan must carry. **(a) Drift:** editing
`.claude/hooks/writ-blast-gate.sh` does **not** update `~/.cursor/hooks/writ-blast-gate.sh`; after
the deny-copy edit the plan must refresh the Cursor copy or the twin silently keeps the old
three-branch copy and denies with the pre-fix wording. **The refresh is a one-file body copy —
`install -m 0755 <source> ~/.cursor/hooks/writ-blast-gate.sh` — followed by a silent `diff -q`
(§3).** It is **not** `writ-doctor` (never copies this file: no `copy_pair` / `cursor/hooks` /
`writ-blast-gate` match in `bin/writ-doctor.sh`; it only prints `freshness()` at `:367`) and it is
**not** `agent_village/scripts/hooks/install.sh`, whose only argv modes either abort, blast the whole
manifest, or write `~/.cursor/hooks.json` — frozen out by the grill (RT-r4 C1; evidence in §3).
A silent `diff -q` proves the bytes moved; it does **not** prove Cursor treats the envelope as a
deny, which is OQ-5.1. **(b) Envelope:**
the copy emits Claude's `hookSpecificOutput.permissionDecision` shape, while Cursor's documented
deny field is `permission`; the hook fires on Cursor and its `failClosed` wiring is live, but
whether Cursor honors *this envelope* as a deny is **not verified here** — do not write "the deny
blocks on Cursor" into the spec without a live check. Read WARN stays Claude-only either way
(declared loss, consistent with grill R15 and the "Cursor Read WARN stays Claude-only" risk row).
**Status after RT r3:** the dual-envelope question (emit Cursor's flat `permission` shape alongside
Claude's nested one) is **OQ-5.1** in Open Questions, and the copy-refresh path is **OQ-5.2** (OPEN — mechanical path settled, owner authorization
pending, RT-r8 M2; if yes: copy the body, never `hooks.json`) — a real
numbered entry, not prose (RT-r3 M2 filed exactly the missing entry). Deliberately not designed this
round; the spec seat decides both with the live Cursor check in hand.

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

1. open `file:{path}?mode=ro` as today, **with `timeout=0`** on every connect in this function
   (RT-r7 C1 — the default lock wait is measured 5.14–5.34 s this session; a 5-second 5b is the
   exact incentive that made chmod-000 look cheaper, so the fast path must be the production
   path, pinned by assert 6b's recorded-kwargs check);
2. ping it with `SELECT 1`;
3. on `sqlite3.OperationalError` whose message is `unable to open database file`: close that
   connection and retry **once** with `file:{path}?mode=ro&immutable=1` (same `timeout=0`), ping
   again, return it;
4. any other `sqlite3.Error` (and a failing immutable ping) propagates unchanged — callers still
   map it to `unreadable`.

**Plain `ro` leads; `immutable=1` is never the first attempt; the retry predicate is one exact
string.** `immutable=1` tells SQLite the file cannot change, which is a lie while an indexer is
writing: leading with it would read a live db without its WAL and would silently launder the `busy`
case that must stay honest. The retry is reached only after the plain open has already failed with the
one error that means "no `-shm` and I may not create one". **Both halves are load-bearing and both are
pinned by test (§7 asserts 5 and 6), not by prose** — RT-r5 C1 showed the earlier test list green with
either half broken. Live proof of why the predicate must be the exact string
`unable to open database file` and not any `OperationalError` (python sqlite 3.51.0, this session):

```
# DELETE db, writer holding BEGIN EXCLUSIVE:
plain ro  -> OperationalError 'database is locked'      # a DIFFERENT message
immutable -> [(1,)]                                     # would read it anyway -> "usable"
```

A broadened predicate (retry on any `OperationalError`) therefore turns a locked index into `usable`
and the Write gate lets the edit through on a map SQLite refused to serve — C-04 fail-closed, gone.
`immutable=1` "skips all file locking and change detection" (SQLite URI docs), so this is not a
theoretical risk: it is what the retry would do on every locked db.

Verified live on a fresh-`init` fixture (no daemon), band-1 re-run: header bytes
`header[18:20] == b'\x02\x02'` i.e. `write_version = 2` (WAL), directory holds only `.gitignore` +
`codegraph.db`; plain `ro` connect succeeds and its **first execute** →
`OperationalError: unable to open database file`;
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

**Two more private openers — "one opener" must be literally true (RT-r2 C1).** `blast_radius` was
not the only duplicate. `artifact_claims` opens the index itself, twice, with the same URI and the
same `row_factory = sqlite3.Row`:

- `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py:2166-2168` `_c16_resolve_node`
  — `con = sqlite3.connect(` / `f"file:{Path(repo) / '.codegraph' / 'codegraph.db'}?mode=ro",`
- `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py:2488-2490` `_c12_container`
  — same two lines.

Both are reached **after** their check's `probe != "usable"` guard has already passed, i.e. exactly
on the fresh-WAL index that OQ-4 A just made `usable`. Left alone they raise, get swallowed by their
`except sqlite3.Error: return None` / `rows = []`, and C12/C16 go quiet on a healthy index — the
same silent-empty failure as the blast reader, in the two checks whose whole job is to catch an
unnamed consumer. Point both at `codegraph_index._connect(repo)` (same lazy sibling import these
functions' neighbours already use: `sys.path.insert(...)` then `import codegraph_index`), keep each
function's own `try/except` and return contract unchanged, and copy the retry nowhere.

**Complete inventory of index opens under `bin/lib/` — re-verified live this session, two greps
(the `mode=ro` grep alone is gameable; see §7):**

```
$ grep -rn 'mode=ro' bin/lib/
bin/lib/artifact_claims.py:2167:            f"file:{Path(repo) / '.codegraph' / 'codegraph.db'}?mode=ro",
bin/lib/artifact_claims.py:2489:            f"file:{Path(repo) / '.codegraph' / 'codegraph.db'}?mode=ro",
bin/lib/blast_radius.py:135:    con = sqlite3.connect(f"file:{_index_path(repo)}?mode=ro", uri=True)
bin/lib/codegraph_index.py:48:    con = sqlite3.connect(f"file:{_index_path(repo)}?mode=ro", uri=True)

$ grep -rn 'sqlite3.connect' bin/lib/
bin/lib/codegraph_index.py:48 · bin/lib/artifact_claims.py:2166 · bin/lib/artifact_claims.py:2488 ·
bin/lib/blast_radius.py:135        # same four sites, no others
```

Four hits, three files, and **every** `sqlite3.connect` under `bin/lib/` is an index open — so after
this design there is exactly **one** production opener by both greps, which is what the §7 guard test
pins (on `sqlite3.connect(`, not on `mode=ro`). `writ/origin_context.py:37` is a different database
(its own read-write store, not the codegraph index), outside `bin/lib/` and out of scope.

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

**Same step, second file — the Cursor twin (mechanical path specified; authorization OPEN —
OQ-5.2 re-opened, RT-r8 M2: owner must answer whether impl may overwrite the live
`~/.cursor/hooks/writ-blast-gate.sh`).**
`~/.cursor/hooks/writ-blast-gate.sh` is a byte-identical copy wired on Cursor `preToolUse` / `Write`;
editing only the falkor-writ source leaves Cursor running the pre-fix three-branch copy, where
`unreadable` falls into `else:  # stale`
(`external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/.claude/hooks/writ-blast-gate.sh:196`).
Only if the owner authorizes the copy (OQ-5.2 OPEN), the step's done-cell is **a one-file body copy plus a silent `diff -q`** — nothing more:

```sh
install -m 0755 \
  /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/.claude/hooks/writ-blast-gate.sh \
  ~/.cursor/hooks/writ-blast-gate.sh
diff -q /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/.claude/hooks/writ-blast-gate.sh \
        ~/.cursor/hooks/writ-blast-gate.sh      # must be silent
```

**Never invoke `agent_village/scripts/hooks/install.sh`, and never edit any `hooks.json`.** The prior
round named `install.sh` `copy_pair` as "the one supported path"; that was **unsatisfiable** and is
retracted. Verified on-disk this session:

- `copy_pair` is an internal bash function invoked at script load
  (`external: /Users/phatchenh/all-projects/vibe-coding-setup/agent_village/scripts/hooks/install.sh:771-784`),
  **not** a subcommand — any unrecognized argv hits
  `echo "install.sh: unknown argument: $1"` / `exit 2` (`:117-120`).
- Bare `install.sh` refuses by design: "refusing bare install — pass `--only <id>…` or `--all`…
  Bare install strips every Village-owned hook and re-emits the whole manifest. That is how
  failClosed / Shell blockers landed by accident (2026-08-09)" (`:131-143`).
- `--all` is the documented blast ("strip all Village markers, emit every non-declined manifest row
  … use rarely", `:60-63`) and `--only writ-blast-gate` still **writes `~/.cursor/hooks.json`** —
  which the grill froze out of this bucket ("No settings/hooks.json edit").
- It would also copy from the installer's own writ-root pin
  (`external: /Users/phatchenh/all-projects/vibe-coding-setup/agent_village/scripts/hooks/install.sh:406-407`
  — `WRIT_REPO_ROOT`, read from `~/.config/agent-village/writ-root`), not from the worktree just edited.
  gate-waive: C6-FICTION — `WRIT_REPO_ROOT` is agent_village installer code on the abs `external:` path cited on the same line; not a piggyback symbol, not new.

So the installer cannot be the refresh here without breaking a frozen lock, and the earlier "do not
hand-patch the copy" sentence is **withdrawn**: a single `install -m 0755` of that one file is the
only move that satisfies `diff -q` while touching no wiring. Drift is prevented by making the copy
mechanical and same-step (source → copy, one direction, never edited in place), not by routing it
through an installer. `writ-doctor` remains irrelevant — it never copies this file (verified: no
`copy_pair` / `cursor/hooks` / `writ-blast-gate` match in `bin/writ-doctor.sh`).

**What the copied body actually supplies — do not overclaim it (RT-r5 M2).** The Cursor copy is not a
self-contained tree. Its own header walks up two directories for `bin/lib/common.sh` and, failing that
(from `~/.cursor/hooks` the walk-up is `$HOME`), falls back to the agent-village writ-root pin
(`external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/.claude/hooks/writ-blast-gate.sh:29-36`;
live this session the pin reads `/Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ`). So the
**deny strings come from the copied body**, while **`probe()` / `freshness()` come from whatever tree
the pin names**. Two consequences for the plan: never write that the Cursor copy runs its own private
Python; and if the impl happens in a worktree while the pin still points at the main clone, the copied
`unreadable` branch is dead code until the pin's tree carries the new `codegraph_index.py` — so the
step is done only when both the body copy and the pinned tree are the post-edit source.

**A silent `diff -q` is the done-cell if the owner authorizes the copy (OQ-5.2 OPEN); pytest is
not, either way.** The blast-gate suite executes the falkor-writ
source only (`external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/tests/test_blast_gate_hook.py:32-33`
— `HOOK = REPO / ".claude" / "hooks" / "writ-blast-gate.sh"`), so **skipping the copy leaves every
named test green** while Cursor keeps saying "stale". That asymmetry is why the plan's Done cell must
be the `diff -q`, and why no test may be cited as covering the twin. A silent `diff -q` is also
**not** evidence that Cursor *denies* — the copy still carries only Claude's nested envelope, which
stays open as **OQ-5.1**.

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
    …marker logic unchanged; only the PRE-INDEX message text changes (below)…
```

**PRE-INDEX and PRE-SCHEMA copy (RT-r2 M2, hardened for RT-r4 M1).** C-08 bans the repair *command*
from every audit message; two live messages still issue it, **un-backticked**. These are **full-sentence
replacements — the old instruction is deleted, not supplemented.** Appending
`Run \`writ codegraph-init\`` beside `Run the codegraph index` is explicitly a violation, and it is
the exact gamed shape the §7 tests must fail (booleans under C-08).

- `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py:987-989` PRE-INDEX
  — live: `"No codegraph index for this repo. Run the codegraph index "` / `"before dispatch, or mark the repo greenfield "`.
  **Replacement, verbatim (delete `Run the codegraph index`):**

  ```
  No codegraph index for this repo. Run `writ codegraph-init` before dispatch, or mark the repo greenfield (`writ predispatch-audit --mark-greenfield <artifact>`).
  ```

  The noun phrase "No codegraph index for this repo" stays (legal per C-08); the greenfield escape
  hatch keeps its exact command.
- `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py:1002-1004` PRE-SCHEMA
  — live: `"{sorted(found)} but this reader knows {sorted(known)}. Rebuild "` / `"the index at a known schema version."`.
  **Replacement tail, verbatim (the sentence-initial `Rebuild the index` is deleted):**

  ```
  Codegraph index at an unrecognized schema version: found {sorted(found)} but this reader knows {sorted(known)}. Run `writ codegraph-init` to rebuild the index at a known schema version.
  ```

  Both version sets stay plumbed from the probe tuple (C-03 untouched).

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
  existing four probe tests unchanged. Fixture identities: all three are **no-lock**
  perms/corruption gates (journal mode incidental, no second connection, no lock); the
  `chmod 000` fixture here is a *permissions* gate and is **forbidden** as the locked-db fixture
  of the §7 assert-5 test (which names its own lock mechanism: `BEGIN EXCLUSIVE`, DELETE journal,
  reader `timeout=0`).
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
  fixture on a **code** Write → the deny reason is pinned by **equality with §3's specified unreadable
  sentence** (it is fully specified, so equality is available and is the strongest pin), plus these
  belts: **contains** `writ codegraph-init`; **contains** `cannot be read`; **does not contain**
  `unrecognized`; **does not contain** ``Run `codegraph index` `` **nor the un-backticked
  `Run the codegraph index`**; **does not contain** `stale`.

  **The two RT-r5 M1 additions (`cannot be read` required, `unrecognized` forbidden) are what stop the
  cheapest lie:** reusing the existing unrecognized branch for the new verdict. Its live text renders
  an empty found-set as `{none}`
  (`external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/.claude/hooks/writ-blast-gate.sh:189-195`),
  and that sentence passes the r4 pin set. Live booleans this session:

  ```
  --- LIVE unrecognized {none} sentence ---
    contains 'writ codegraph-init'     True
    no 'Run `codegraph index`'         True
    no 'Run the codegraph index'       True
    no 'stale'                         True
    contains 'cannot be read'          False
    no 'unrecognized'                  False
    r4 four-pin set passes  = True     <-- the lie was green
    r5 six-pin set passes   = False
  --- SPECIFIED unreadable sentence (§3) ---
    contains 'cannot be read'          True
    no 'unrecognized'                  True
    r4 four-pin set passes  = True
    r5 six-pin set passes   = True     <-- honest copy still passes
  ```

  There are **zero** `unreadable` hits in `tests/test_blast_gate_hook.py` today (`grep -c` → 0), so
  this whole fixture is new work, and `test_unrecognized_deny_names_both_version_sets` (`:181-193`)
  covers only a foreign-version fixture — it does not cover this.
  (C1-a item 7, ban shape per C-08.) **The ban is the command in any imperative form, never the
  two-word noun** — the
  specified unreadable sentence itself contains the noun phrase "codegraph index file"
  (`'codegraph index' in s = True`, recorded under C-08), so a bare-substring ban would make honest
  copy fail and invite the worker to weasel the assert (RT-r3 M1). This is pre-mortem #1's promised
  test; without this file the `unreadable` branch can be skipped or misordered into the final `else`
  and every other named test still passes green.
- `tests/test_writ_codegraph_init.py`: fake `codegraph` that leaves a junk db → wrapper exits 1,
  marker survives, **db file still exists**, and the fake records that **`codegraph index` was
  never invoked** (the no-retry contract, C1-a item 3 — assert the invocation log holds exactly one
  `init` call); missing-db case → exit 1 with the init-output message; unrecognized case → exit 1
  naming both version sets. The existing
  `test_unusable_index_leaves_marker` asserts exit 0 on an unusable index — the new exit-1 contract
  flips it, so that test is **updated, not added**.
  The file's existing DELETE-fixture `usable` test (marker consume, exit 0) stays as-is — it still
  covers the consume contract. What it does **not** cover is the WAL fallback, and it must not be
  cited as if it did: **the `usable`-after-WAL-init path may NOT be asserted with this file's
  fixtures.** `fake_codegraph`
  (`external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/tests/test_writ_codegraph_init.py:47-54`)
  is `#!/usr/bin/env bash\nexit 0` and `_make_usable_index`
  (`:93-106`) is `sqlite3.connect(idx)` — a DELETE-journal db (`write_version 1`) that plain
  `mode=ro` already reads, so a wrapper-usable test built on it greens with the WAL fallback absent.
  The happy-path assertion lives in the **live check** below, on a real `codegraph init`.
- **OQ-4 A tests — ONE test function, asserts 1–3 AND 5a–5b in order (RT-r3 C1, hardened RT-r5 C1,
  bound RT-r7 C1).** The WAL fixture is built by running a **real `codegraph init` in a temp git
  repo**. **"Same test *or its fixture*" is deleted — a shared fixture name is not the pin — and the
  "second named test function" escape for assert 5 is deleted the same way (RT-r7 C1: a second
  function let 5b ride the chmod-000 fixture assert 7 already owns, while 5a became an independent
  fixture-fact proving nothing about `_connect`).** Asserts 1, 2, 3 (WAL db) and 5a, 5b (locked
  DELETE db) must sit inside a **single `def test_…(…)`**: the WAL `db` / `repo` variables serve
  asserts 1–4; then, in the same function scope, the locked DELETE `db` / `repo` / `writer` are
  built and the EXCLUSIVE holder **stays open** through 5a and 5b, with **no mutation of any kind
  between 5a and 5b — no rebuild, no `chmod`, no `unlink`, no rewrite** (RT-r8 C1: "no rebuild"
  is not enough; `chmod 000` applied after 5a, writer still open, flips the lock-skip URIs to
  `unable to open database file` — live re-run this session: `immutable=1` and `vfs=unix-none`
  both raise `unable to open database file` post-chmod — so a lock-skipping `_connect` greens a
  probe-outcome-only 5b while **no attempt ever raised `database is locked`**). Assert 7 keeps
  `chmod 000` as a *different* test's fixture, never as a mid-test mutation of assert 5's db. A split (1–2 in `test_wal_fixture_shape`, 3 in `test_probe_usable`, 5a in
  `test_lock_message`, 5b in `test_probe_unreadable`) lets the last function run on chmod-000 and
  greens the list with a lock-skipping `_connect` (RT-r7 C1 gaming transcript). Forbidden as fixture builders for any assert
  in this block: `make_index`
  (`external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/tests/test_codegraph_index.py:65-79`
  — `sqlite3.connect(idx)`), `_make_usable_index`, `_index_usable`, and "copy a `codegraph.db` alone"
  unless the copy's own header is asserted WAL by step 1. Rationale, live this session:

  ```
  # DELETE-mode fixture (what make_index / _make_usable_index build):
  DELETE-fixture header[18:20] = b'\x01\x01' write_version = 1
  plain ro execute -> [(1,)] (no retry needed)
  probe(DELETE fixture) = usable
  listing = ['codegraph.db']

  # real `codegraph init` in a mktemp git repo (the state OQ-4 A exists for):
  header[18:20] = b'\x02\x02' write_version = 2 read_version = 2
  plain ro EXECUTE raised OperationalError 'unable to open database file'
  immutable schema_versions = [(1,), (5,)]
  listing after reads = ['.gitignore', 'codegraph.db']
  ```

  A DELETE fixture satisfies "probe usable + no sidecars" **with the fallback deleted**, which is
  exactly how the r2 test list could be greened without implementing anything. The asserts, in order:

  1. **Fixture is WAL, by bytes:** `header = db.open('rb').read(100)`;
     `assert header[18:20] == b'\x02\x02'` (write_version 2, read_version 2). A name or comment
     saying "WAL fixture" is not evidence.
  2. **Plain `ro` still fails on that same db:** `sqlite3.connect(f"file:{db}?mode=ro", uri=True)`
     then `.execute("SELECT 1")` raises `sqlite3.OperationalError` whose message is
     `unable to open database file`. This is the assert a DELETE fixture cannot pass.
  3. **THEN the contract:** `codegraph_index.probe(repo) == "usable"`, and
     `sorted(os.listdir(db.parent))` still holds **no** `-wal` / `-shm` (the fallback must not write —
     C-12). Order matters: 3 is meaningless without 1+2 in front of it.
  4. **Same db, the folded readers:** on that identical fixture repo,
     `blast_radius.report_for_file(repo, <fixture file>)["symbols"]` returns **rows, not `[]`**;
     `artifact_claims._c16_resolve_node(repo, "<unique fixture symbol>")` is **not** `None`;
     `artifact_claims._c12_container(repo, <that node>)` is **not** `None`. Feasibility verified live
     on the fixture above (`unique_band1.py` + `def unique_band1_symbol`), through `immutable=1`:

     ```
     resolve rows: [{'id': 'function:b79ef97f…', 'name': 'unique_band1_symbol', 'kind': 'function',
                     'file_path': 'unique_band1.py', 'start_line': 1, 'end_line': 1}]
     container candidates: [{'id': 'file:unique_band1.py', 'kind': 'file', 'start_line': 1, 'end_line': 2}]
     ```
     — so `_c16_resolve_node` resolves to exactly one row (its `len(rows) != 1 → None` guard passes)
     and `_c12_container` returns the file node. Both are `None` today on this db, because their own
     `mode=ro` opener's first execute raises and each swallows it.
     **And the listing is re-asserted AFTER assert 4 (RT-r8 M1):** `sorted(os.listdir(db.parent))`
     must hold **no** `-wal` / `-shm` **once the folded readers have run**, not only at assert 3 —
     assert 3's listing executes **before** these readers, and a RW `connect(str(db))` in any one
     of them creates the sidecars after the earlier listing passed. Live this session:
     `['.gitignore', 'codegraph.db']` → `['.gitignore', 'codegraph.db', 'codegraph.db-shm',
     'codegraph.db-wal']` after a single RW open. C-12 (read-only index) is what this guards.
  5. **LOCKED DB STAYS UNREADABLE — the C-04 behaviour pin, two parts, discriminator message
     asserted, BOUND IN THE SAME `def` (RT-r5 C1, closed RT-r6 C1, bound RT-r7 C1).** Asserts 5a and
     5b live **inside the single `def` that also carries asserts 1–4** (see the block header) — no
     "second named test function", no separate locked-db test. Within that function the EXCLUSIVE
     holder stays open from fixture build through 5b:

     **Fixture, load-bearing, no substitutes:** a real db in **DELETE journal** with
     `schema_versions = {1, 5}`; a second connection holds **`BEGIN EXCLUSIVE` open for the
     duration of the test** (released only at teardown). DELETE is load-bearing: on WAL with
     sidecars present, `mode=ro` readers are **not** blocked (RT-r6 feasibility audit, re-verified
     band-2). Every reader connection in this test — the test's own plain-`ro` check — runs with
     **`timeout=0`** (or a small explicit one): the default lock timeout waits **≈5.1–5.3 s**
     before raising (measured 5.14 s and 5.34 s across two band-2 harness runs this session;
     evidence-only — a wall-clock time is not an assertable output), which is the exact incentive
     that pushed the r5 patch to reach for chmod instead.
     **Fixture anti-substitution (mandatory):** the lock mechanism is `BEGIN EXCLUSIVE` on a second
     live connection; the journal mode is DELETE; the reader timeout is 0. **Forbidden substitutes
     for THIS assert's fixture: `chmod 000`, absent file, junk bytes.** All three fail identically
     with `unable to open database file` on **both** URIs (r6 measured; band-2 re-run below), so
     they discriminate nothing — r6's gaming transcript greens this assert on chmod and never
     starts a lock. `chmod 000` stays in assert 7, named as a *different* gate (fallback must not
     launder a permissions failure into usable).

     **Part 1 (5a) — the discriminator, asserted:** the test's own plain
     `sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=0)` + `.execute(...)` on that fixture
     raises `sqlite3.OperationalError` and **`str(e) == 'database is locked'`** — the message
     asserted, not the exception type alone. **Part 2 (5b) — `_connect` itself saw the lock,
     recorder-pinned (RT-r8 C1):** on **that same locked fixture, with `writer` still open**, run
     `codegraph_index._connect(repo)` with the module's `sqlite3.connect` patched by the same
     recording shim used for 6b (wrapped connections, so a ping-time error is attributed to the
     recorded connect that produced it), then: **(i)** `_connect` raises
     `sqlite3.OperationalError` whose message is exactly **`'database is locked'`** — the error
     `_connect` propagated, cross-asserted against the recorder as belonging to the **first**
     recorded connect; **(ii)** the recorder shows **exactly ONE** recorded connect — the retry did
     **not** fire, because `'database is locked'` is not the GATE string; a two-call trace here
     means the retry predicate was broadened and this assert must go red; **(iii)**
     `codegraph_index.probe(repo) == "unreadable"` on the same fixture (kept as the outcome line,
     now third, **not** the whole of 5b). Part 1 proves the fixture actually locked a `mode=ro`
     reader; part 2 proves `probe`'s `"unreadable"` came from `_connect` **seeing that lock** — a
     probe-outcome-only 5b cannot distinguish "locked db stayed honest" from "probe was never
     reached", and greens on `chmod`-after-5a because the lock-skip URIs then raise
     `unable to open database file` instead (live re-run this session; that mutation is separately
     named and forbidden above). **5b is fast by design:** production `_connect` sets `timeout=0` on every connect
     (§1.0, RT-r7 C1) — the measured default wait is 5.14–5.34 s across three runs this session,
     which is the exact incentive that made chmod-000 look cheaper. If 5b as run takes ~5 s, the
     production `_connect` (not the test) is wrong.
     Live this session (python sqlite 3.51.0, band-2 + r7 harness runs):

     ```
     locked-fixture header[18:20] = b'\x01\x01' (write_version=1)
     plain ro (timeout=0) SELECT version FROM schema_versions -> 'database is locked'
     plain ro (timeout=0) SELECT 1                            -> 'database is locked'
     plain ro (default timeout)                               -> 'database is locked'  elapsed=5.14s / 5.24s / 5.34s (three runs)
     file:…?mode=ro&immutable=1 on the same locked db         = [(1,), (5,)]    # laundered to "usable"
     file:…?mode=ro&nolock=1    on the same locked db         = [(1,), (5,)]    # SAME skip-locking class (RT-r7 C1, live-verified)
     ```

     The lock raises **`database is locked`**, not `unable to open database file` — so the
     exact-string retry predicate specified in §1.0 is precisely what keeps this case honest, and
     a broadened predicate silently breaks C-04 while every other assert stays green. The band-2
     adversarial matrix (pasted below) shows parts 1+2 red for every lazy variant and green for
     the honest shape.
  6. **`_connect`'s shape, by the RUNTIME first URI plus call-arg literals — never by position
     over whole-function text, never by constants-only extraction (RT-r5 metric retracted;
     RT-r6 C1/M1 closed; RT-r7 C1/M1 closed).** Parse `_connect`'s **own** source
     (ast over `inspect.getsource(codegraph_index._connect)`) for 6a/6c/6d, **and drive `_connect`
     under a recording connect wrapper** on the WAL fixture for 6b:

     - **6a — count (static):** exactly **two** `sqlite3.connect(` call sites. This kills the
       no-retry shape, which vacuously satisfies a "no bare `except`" negative
       (`bare_except_present=False`, r6 measured): a function with **no** `except` at all has no
       broadened except to ban.
     - **6b — the runtime first URI carries no lock-skip (runtime pin, not source constants).**
       Patch `codegraph_index.sqlite3.connect` with a recording shim that captures `(uri, kwargs)`
       and delegates to the real connect (e.g. `unittest.mock.patch(..., wraps=sqlite3.connect)`
       or a module shim), drive `_connect(repo)` on the asserts-1–3 WAL fixture, and assert on the
       recorded calls **in order**:
       - exactly **two** recorded calls — the retry actually fired. (This self-pins the fixture:
         a DELETE substitute's plain-`ro` succeeds and records only one call, so a substituted
         fixture fails 6b, not just asserts 1–2.)
       - `recorded[0].uri` — the **evaluated** string the recorder sees — is **exactly equal**
         to `f"file:{db}?mode=ro"`. **One predicate: equality. No extra query keys.** A token ban
         is **NOT** 6b and the earlier "equivalently … neither `immutable` nor `nolock`" clause is
         **deleted** (RT-r8 C1): SQLite URI §3.3 carries a **third** lock-skip, `vfs=NAME`, and live
         this session `file:…?mode=ro&vfs=unix-none` on the `BEGIN EXCLUSIVE` DELETE db returns
         `[(1,), (5,)]` — the same laundering class as `immutable=1` / `nolock=1`
         (`nolock=1` "disables all calls to the xLock, xUnlock, and xCheckReservedLock methods",
         live-verified RT-r7) — while the r7 two-token ban greens it. Equality rejects every extra
         key (`vfs=…`, any future §3.3 parameter) by construction, which is why it is the only
         honest form of this clause.
       - `recorded[1].uri` contains `immutable=1`.
       - every recorded call's kwargs hold **`timeout == 0`** (the §1.0 production pin, RT-r7 C1).
       **Forbidden as 6b's metric: constants-only extractors** (ast `JoinedStr` constants, regex
       of the quoted literal). Measured blind this session: for `f"?mode=ro{extra}"` with
       `extra="&immutable=1"` the constants are `file:?mode=ro` while the runtime URI is
         `mode=ro&immutable=1`; for `mode=ro&nolock=1` the constants simply lack the banned token.
       A dead first attempt (real connect, `raise OperationalError(GATE)` before any ping) passes
       6b — its recorded first URI is clean — so **6b never substitutes for bound 5b**: on the
       locked db that shape probes `usable`, and only assert 5 in the one `def` goes red. That is
       the RT-r7 C1 bind and it stays.
     - **6c — second URI has it (static):** the second call site's literal contains `immutable=1`.
     - **6d — retry gated on the caught error (static):** the second connect sits inside an `If`
       whose test carries a comparison against the exact literal `unable to open database file`
       (`str(e) == '…'` or `'…' in str(e)`) and whose body carries the second connect. A condition
       on the caught error, **not** the absence of a bare `except`.

     **Forbidden:** `src.index(...)` / first-substring position over the whole function text
     (`inspect.getsource`) anywhere in this pin. RT-r6 measured it three ways against the r5
     patch: the *retry URI itself* satisfies it (`mode=ro&immutable=1` contains both substrings
     in order); a leading `# mode=ro` comment satisfies it (`comment_lie_immutable_first:
     order_ok=True`); and an honest warning docstring **fails** it
     (`honest_with_warning_doc: order_ok=False`) — it rewards the comment and punishes the safety
     note, pre-mortem 4's exact prediction. **House rule from RT-r6 M1 (binds every source pin in
     this section): a source pin on `_connect` is membership in / literal extraction from
     `codegraph_index._connect`'s own source — never a position comparison over the whole
     function text including docstring and comments.** The existing house-style cite
     `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/tests/test_pre_write_dispatch.py:325-333`
     (`import inspect` / `src = inspect.getsource(mod.cmd_can_write)` / `assert "_can_write_check" in src`)
     is **membership**, `in src` — clauses 6b/6c are literal extraction from the same source
     object and 6a/6d are structural counts/conditions over it; none is index-order.
     Source inspection alone stays **not** sufficient — text can lie about runtime order — which
     is why assert 5 (behaviour) and assert 6 (structure) are both required. Keep both. The pair
     was executed adversarially this session; matrix pasted below.
  7. Unchanged from the enum block: junk bytes → `"unreadable"` on **both** URIs
     (`DatabaseError: file is not a database`) and `chmod 000` → `"unreadable"` on **both** URIs
     (`unable to open database file`) — assert the fallback did not launder either into usable.
     **These are perms/corruption gates, a different gate than C1's locked-db pin:** they use no
     lock mechanism (DELETE journal is incidental), no `BEGIN EXCLUSIVE`, and they fail
     identically on both URIs — which is exactly why they can never satisfy assert 5 and must
     never be offered as its fixture (RT-r6 C1 gaming transcript used chmod-000 as assert 5).
- **One-opener tests (RT-r2 C1, hardened per RT-r3 gaming note)**, on the **same** WAL fixture — and
  since asserts 1–3 live in one function (above), `probe()` being `usable` there is proven to come
  from the fallback, not from a DELETE-journal fixture:
  (a) `tests/test_artifact_claims.py`: `_c16_resolve_node` / `_c12_container` not-`None` — the §4
  asserts above, which is where they live;
  (b) a repo-level guard test: **sqlite3 connect calls in any syntactic form occur in exactly one
  file under `bin/lib/` — `codegraph_index.py`** (ast walk over `bin/lib/*.py` — see below; the
  pre-r8 grep form `sqlite3.connect(` is subsumed, RT-r8 M1). Live today, before the fold:

  ```
  bin/lib/codegraph_index.py:48:    con = sqlite3.connect(f"file:{_index_path(repo)}?mode=ro", uri=True)
  bin/lib/artifact_claims.py:2166:        con = sqlite3.connect(
  bin/lib/artifact_claims.py:2488:        con = sqlite3.connect(
  bin/lib/blast_radius.py:135:    con = sqlite3.connect(f"file:{_index_path(repo)}?mode=ro", uri=True)
  ```

  The guard is **an ast walk, not a grep** (RT-r8 M1): parse every `bin/lib/*.py`; count every
  sqlite3 connect **call in any syntactic form** — a `Call` whose `func` is `Attribute(attr ==
  'connect', value == Name('sqlite3'))`, AND any `Call` whose `func` is a `Name` bound by a
  `from sqlite3 import connect` (`ImportFrom(module == 'sqlite3')`) node in the same file — and
  require the total to live in exactly one file, `codegraph_index.py`. Live this session:
  `from sqlite3 import connect` + `connect(f"file:…?mode=ro&immutable=1", uri=True)` has **no**
  `sqlite3.connect(` substring, so the r3/r7 grep-based count greens it silently. A private
  C12/C16/blast opener **fails the AST pin in every form**: renamed `import sqlite3 as sq`,
  `from sqlite3 import connect`, RW `connect(str(db))`, or an aliased private `immutable=1`
  (which creates no sidecars and would also slip a listing-only check — the AST is the door that
  stays shut; **private `immutable=1` via alias must fail this pin by construction**). The old
  door-1 framing — the guard is on `sqlite3.connect(`, **not** on the string `mode=ro`, because a
  `mode=ro` grep is satisfied by `sqlite3.connect(str(path))` opening read-write and creating
  sidecars — stays true, and the ast walk subsumes it. Pairing the AST opener pin with assert 4's
  **post-reader** no-sidecar re-listing (above) closes both doors the r3 gaming note opened:
  alias invisibility (door 1) and sidecar timing (door 2).
- **PRE-INDEX / PRE-SCHEMA copy test (RT-r2 M2, hardened per RT-r4 M1)**, in
  `tests/test_artifact_claims.py` alongside the existing
  `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/tests/test_artifact_claims.py:1665-1700`
  message assertions. **Primary pin is equality with §4's replacement sentence**
  (`assert msg == PRE_INDEX_EXPECTED`) — an append cannot game an equality assert. Belt asserts, for
  the PRE-SCHEMA case where the version sets are interpolated and equality needs a format:
  message **contains** `writ codegraph-init`; **does not contain** ``Run `codegraph index` ``;
  **does not contain** `Run the codegraph index`; and (PRE-SCHEMA) **does not contain**
  `Rebuild the index`. The two un-backticked bans are the RT-r4 discriminators: the live sentences
  carry no backticked command at all, so the r3-shape ban alone is green on a copy that keeps
  `Run the codegraph index` and merely adds the wrapper (recorded booleans under C-08). PRE-INDEX
  keeps the *noun* ("No codegraph index for this repo") — never ban the two words.
  Note the existing PRE-INDEX assertion at
  `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/tests/test_artifact_claims.py:1670`
  is `"index" in msg.lower()` — it matches live, gamed and specified copy alike and does **not**
  substitute for this test.
- One live `writ codegraph-init` on a fixture repo built by a **real `codegraph init`** (not a
  huge-tree rebuild, and not `fake_codegraph` + a DELETE-journal fixture — see the wrapper-test note
  above). With OQ-4 A applied this is the **happy path** — expect probe `usable`, marker consumed,
  exit 0 — and it is the only place that proves the fallback works end-to-end through the wrapper.
  Record the observed `write_version` of that fixture's db in the run notes; if it is 1, the check
  did not exercise WAL and does not count.

**Bad-faith executor pass — "can this test pass with the defect still present?"** (required by the
band-1 extra instruction; every named test above, one line each):

| Named test | Defect left in | Passes anyway? |
|---|---|---|
| probe: junk / schema-less / `chmod 000` → `unreadable` | enum change skipped | **no** — today they return `missing` / the empty-found tuple |
| `freshness()` schema-less → `unreadable` | pass-through line skipped | **no** — narrows to `unrecognized` |
| `unreadable` never cached | — | yes-by-construction; kept as a policy pin, not a defect catcher (stated as such in §2) |
| cache-mask test (`chmod 000` + restored mtime, inside TTL) | probe-before-cache skipped | **no** — cache hit returns `fresh` |
| `PRE-UNREADABLE` denies | branch skipped | **no** — falls to `missing`, no finding with a matching marker |
| unreadable + matching marker still denies | branch ordered after `missing` | **no** — marker path swallows it |
| blast-gate unreadable deny copy | branch misordered into `else stale` | **no** — `'stale' not in reason` fails |
| blast-gate unreadable deny copy | branch reuses the **unrecognized** `{none}` template | **no** — equality fails, `cannot be read` missing, `unrecognized` present. With the r4 pin set only: **yes** (r5 MAJOR-1) |
| blast-gate ban (backticked **and** un-backticked imperative) | copy left naming `codegraph index` as the command in either form | **no** — and honest copy still passes (C-08 booleans) |
| wrapper junk-db → exit 1, db exists, one `init` call | exit 0 kept / retry added | **no** |
| OQ-4 assert 1 (header `b'\x02\x02'`) | fallback skipped | **no** — a DELETE fixture fails the assert, so the test cannot be built on one |
| OQ-4 assert 2 (plain `ro` raises) | fallback skipped | **no** — this is the discriminator r2 lacked |
| OQ-4 assert 3 (`usable`, no sidecars) | fallback skipped | **no**, given 1+2 **in the same function** on the same path object. Alone: **yes** (r3 CRITICAL). With 1+2 in a *different* function: **yes** — the second function can run on a DELETE fixture (r5 CRITICAL). The single-`def` requirement is the pin, not the fixture name |
| OQ-4 assert 5 (locked DELETE db: 5a `str(e) == 'database is locked'` THEN 5b: `_connect`-recorder first attempt raised `'database is locked'`, retry NOT fired, `probe() == "unreadable"`, same `def` as asserts 1–4, writer held open, no inter-part mutation) | `_connect` leads with `immutable=1` or `nolock=1` or `vfs=unix-none`, or retries on any `OperationalError`, or never pings the first connect | **no** — live, that db returns rows under `immutable=1`, `nolock=1` **and** `vfs=unix-none` → `usable` ≠ `"unreadable"`, and each skip-shape's first recorded attempt never raises `'database is locked'` (v3 matrix: all seven lazy variants red on 5b; 5b1 red on every one). **chmod-000 as 5b's starting fixture: yes** — which is why the substitutes are named and forbidden **and** the one-`def` bind makes "5b in a second function" illegal (RT-r7 C1); **chmod-000 BETWEEN 5a and 5b: fails 5b1** — the error flips to `unable to open database file` on the lock-skip URIs (RT-r8 C1, live re-run this session), and the mutation is named forbidden |
| OQ-4 assert 6a (connect count == 2, static) | retry deleted — single combined-URI opener (the r6 CRITICAL shape) | **no** — count is 1 |
| OQ-4 assert 6b (**runtime** first URI clean; two recorded calls; `timeout=0` in kwargs) | first URI = `mode=ro&nolock=1` (constants look clean — RT-r7 C1's cheapest pass) | **no** — the recorder sees the evaluated URI, which contains `nolock`; and on the locked db 5b is red anyway |
| OQ-4 assert 6b (runtime) | `f"?mode=ro{extra}"`, `extra="&immutable=1"` (constants = `file:?mode=ro`, clean) | **no** — the recorder sees `mode=ro&immutable=1`; constants-only extractors are forbidden precisely because they miss this (RT-r7 M1, measured) |
| OQ-4 assert 6b (runtime) | **dead first connect** — real `connect`, `raise OperationalError(GATE)` before any ping | **6a–6d AND 6b-runtime: yes, all green** (recorded first URI is clean, two calls recorded, gate If present) — **5b: no.** This is the documented blind spot: no source or URI-shape pin can see a dead first attempt; bound 5b on the locked fixture is the only red — now red **twice**: 5b1 (no `database is locked` is ever observed — it never pings) and 5b2 (the retry fires: two recorded calls on the locked db, measured RT-r8). Stated so the plan keeps 5 bound rather than over-building 6 |
| OQ-4 assert 6b (runtime equality, RT-r8) | first URI = `?mode=ro&vfs=unix-none` (constants clean; **r7 two-token ban clean** — third §3.3 lock-skip) | **no** — equality: `recorded[0].uri` carries the extra `&vfs=unix-none` key → 6b red; on the locked db the first attempt returns rows, so 5b1 is red too (no `database is locked` observed). Measured v3, row v |
| OQ-4 assert 6c (second call-site URI literal: `immutable=1`, static) | immutable-first order lie (second URI is plain `ro`) | **no** |
| OQ-4 assert 6d (`str(e)` comparison against the exact literal guards the retry, static) | retry on any `OperationalError`; retry present but ungated | **no** — the comparison must sit on the caught error. With 6a, a no-`except` function cannot satisfy the set vacuously |
| honest-docstring inversion (RT-r6 M1) | worker adds the **required** "never lead with `immutable=1`" warning docstring | **greens the set** — the pins read recorded URIs and call-arg literals, never docstring/comment position. The retracted `src.index` order pin **failed** the warned docstring (band-2 matrix legacy column: honest = F) — that is the lie-magnet this row exists to prevent |
| OQ-4 assert 4 (`report_for_file` rows, `_c16`/`_c12` not None) | any of the three openers unfolded | **no** on this fixture; on a DELETE fixture: **yes** — hence the same-db requirement |
| one-opener guard (`sqlite3.connect(` count == 1) | C12/C16 rewritten to `sqlite3.connect(str(path))` | **no** — count stays 3; and assert 3's no-sidecar check catches the RW open |
| PRE-INDEX / PRE-SCHEMA copy (equality + 3 bans) | wrapper token **appended**, `Run the codegraph index` / `Rebuild the index` kept | **no** — equality fails and the un-backticked bans fail. With the r3-shape ban only: **yes** (that was RT-r4 M1). Noun-only ban: **yes-and-broken** |
| live wrapper happy path | fallback skipped | **no**, provided the fixture is a real init (`write_version 2` recorded) |
| Cursor twin refresh (`diff -q` Done cell, conditional on OQ-5.2 owner yes) | copy skipped entirely | **pytest: yes — it never reads the Cursor file** (`test_blast_gate_hook.py:32-33` execs the falkor-writ source). That is precisely why the Done cell is the `diff -q` and not a test; the plan must not cite any pytest as covering the twin (RT-r4 C1; whether it is a Done cell at all is OQ-5.2, re-opened RT-r8 M2) |

**Band-2 adversarial × honest verification (RT-r6 exit condition; executed this session, evidence
inline — a run, not a narration).** Both directions were executed: the lazy implementations below
were run against the real fixtures under the pins **exactly as specified above** (asserts 1–3, 5,
6a–d, 7 — same shapes, not paraphrases), and the honest implementation — plain `file:…?mode=ro`
first; on `OperationalError` with `str(e) == 'unable to open database file'` one retry with
`file:…?mode=ro&immutable=1`; **warning docstring included** — ran the same pins. Harness and
full transcript: RT-r8 harness `.village/runs/2026-08-19-bkt6-writ-probe/scratch/pin-set-harness-v3.py` →
`pin-set-rt8-output.txt` (re-run live on this patch; prior pairs: `pin-set-harness-v2.py` →
`pin-set-rt7-output.txt`, `pin-set-harness.py` → `pin-set-band2-output.txt`). sqlite re-measured
this session: **3.51.0**.

Fixture facts re-measured this session (re-run, not cited):

```
WAL no-sidecar (real `codegraph init`, rc=0):
  header[18:20] == b'\x02\x02'  (write_version=2, read_version=2)
  plain ro SELECT 1        -> 'unable to open database file'
  plain ro SELECT version  -> 'unable to open database file'
  immutable=1 schema_versions = [(1,), (5,)]
  nolock=1  (same WAL db)  -> OperationalError 'unable to open database file'  # RT-r7 live: no shortcut on the WAL hole
  vfs=unix-none (same WAL db) -> OperationalError 'unable to open database file'  # RT-r8 live: retry still needed
  listing after reads = ['.gitignore', 'codegraph.db']          # no sidecars created

Locked DELETE db (`BEGIN EXCLUSIVE` held):
  header[18:20] == b'\x01\x01'  (write_version=1)
  plain ro (timeout=0) SELECT version -> 'database is locked'
  plain ro (timeout=0) SELECT 1       -> 'database is locked'
  plain ro (default timeout)          -> 'database is locked'  elapsed = 5.14s / 5.24s / 5.25s / 5.34s (four harness runs, this session)
  immutable=1 on the same locked db   = [(1,), (5,)]           # the laundering r6 demonstrated
  nolock=1    on the same locked db   = [(1,), (5,)]           # SAME skip-locking class (RT-r7 C1, live-verified)
  vfs=unix-none on the same locked db = [(1,), (5,)]           # THIRD skip-locking class (RT-r8 C1, live this run)

chmod 000 db:  plain ro -> 'unable to open database file'      # fails BOTH URIs identically
junk bytes db: plain ro -> 'DatabaseError: file is not a database'
```

probe() verdicts per variant × fixture (this run):

```
  honest                 WAL=usable  LOCKED=unreadable  JUNK=unreadable  CHMOD=unreadable
  a (always-immutable)   WAL=usable  LOCKED=usable      JUNK=unreadable  CHMOD=unreadable
  b (immutable first)    WAL=usable  LOCKED=usable      JUNK=unreadable  CHMOD=unreadable
  c (comment lie)        WAL=usable  LOCKED=usable      JUNK=unreadable  CHMOD=unreadable
  n (nolock first)       WAL=usable  LOCKED=usable      JUNK=unreadable  CHMOD=unreadable
  d (dead first)         WAL=usable  LOCKED=usable      JUNK=unreadable  CHMOD=unreadable
  f (fmt hidden immutable) WAL=usable LOCKED=usable     JUNK=unreadable  CHMOD=unreadable
```

(The a/b/c rows are the band-2 printout; the n/d/f rows are read off the RT-r7 run's matrix
cells — col 3 = WAL probe, 5b = LOCKED probe, 7 = JUNK+CHMOD — same run, same fixtures.)

Boolean matrix (T = the assert passes; **RT-r8 run**, re-measured live for this patch —
`pin-set-harness-v3.py` → `pin-set-rt8-output.txt`):

| variant | 1–2 WAL header + plain-ro fail | 3 probe=usable, no sidecar | 5a lock msg == 'database is locked' | 5b **_connect** saw the lock (1st recorded attempt raises 'database is locked', retry NOT fired) → probe 'unreadable' | 6a connects==2 | 6b recorded[0].uri **== `file:{db}?mode=ro` (equality — RT-r8)** | 6c 2nd literal immutable=1 (static, per assert-6's own definition) | 6d exact-string gate guards retry | 7 junk+chmod unreadable | 6b-CONST constants-only first-URI check (tolerated here as blindness evidence; **forbidden** as a pin) | legacy `src.index` order (retracted) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| honest (warning docstring on) | T | T | T | T | T | T | T | T | T | T | **F** ← retracted pin failed honest docs |
| a: single `?mode=ro&immutable=1`, no except (r6 CRITICAL shape) | T | T | T | **F** | **F** | **F** | **F** | **F** | T | **F** (constants carry the token) | T |
| b: two connects, immutable FIRST (order lie) | T | T | T | **F** | T | **F** | **F** | T | T | **F** | T |
| c: `# mode=ro` comment, immutable-only URIs (comment lie) | T | T | T | **F** | T | **F** | T | T | T | **F** | T |
| n: **nolock-first** — first URI `?mode=ro&nolock=1` (RT-r7 C1) | T | T | T | **F** | T | **F** | T | T | T | **T** ← constants simply lack the token (blind) | T |
| d: **dead-first** — real connect, `raise OperationalError(GATE)` before any ping (RT-r7 M1) | T | T | T | **F** (no lock msg ever observed; retry fires) | T | T | T | T | T | T ← the recorded/constant shape IS honest | T |
| f: **fmt hidden immutable** — `f"?mode=ro{extra}"`, `extra="&immutable=1"` (RT-r7 M1) | T | T | T | **F** | T | **F** | T | T | T | **T** ← constants read `file:?mode=ro` (blind) | **F** ← caught only incidentally (the `extra=…` line precedes the first `mode=ro` in the text) |
| v: **vfs=unix-none-first** — first URI `?mode=ro&vfs=unix-none` (RT-r8 C1, third §3.3 lock-skip) | T | T | T | **F** (immutable-class read; no 'database is locked' observed) | T | **F** ← equality rejects the extra `&vfs=` key | T | T | T | **T** ← two-token ban AND constants both green a lock-skip | T |

**Gate verdict:** every lazy variant fails ≥1 proposed assert (a fails five); the honest variant
greens all nine updated asserts **with the warning docstring in place**. RT-r8 reads:
**vfs=unix-none-first** greens the r7 two-token ban, greens the constants-only column, greens the
retracted `src.index` pin, and fires the exact-string retry on the WAL fixture (recorded two calls
— the WAL shape needs the retry even over unix-none, live this run) — it goes red **only** under
equality 6b and under the `_connect`-observed 5b. That is the measured proof that 6b-as-equality
and 5b-as-`_connect`-observation are the two pins the r7 amend lacked. **Dead-first** now fails
three cells of 5b, not one: no `database is locked` is ever observed (5b1 red — it never pings)
and its retry fires on the locked db (5b2 red — two recorded calls). **Measurement note for 6c:**
the design defines 6c statically (literal extraction over the second call site) and this table
reports that static value; the runtime "2nd URI" trace cell can differ when a variant's first
connect succeeds and the retry never runs (runtime shape is retry-obs's job, and it is red on
a/b/c/f). Asserts 1–3 and 7 intentionally green every variant — they pin fixtures and fallback
honesty, not `_connect`'s structure; the discriminating load is carried by **5b (all three parts)
and 6a–6d**, and each discriminating cell above is a measured run, not a claim.

**Done (RT r7): patch complete.**

**Done (RT r8): patch complete** — equality 6b (one predicate: `recorded[0].uri == f"file:{db}?mode=ro"`),
`_connect`-observed 5b (5b1 lock-message on the first recorded attempt, 5b2 retry-not-fired),
no-mutation-between-5a-and-5b, **vfs=unix-none-first** matrix row + AST one-opener pin +
post-assert-4 sidecar re-listing, all re-run live (`pin-set-harness-v3.py` → `pin-set-rt8-output.txt`),
and **OQ-5.2 re-opened** (owner authorization pending).

**Evidence-string cross-check (RT-r6 admission item 5):** every live string quoted as prose
evidence in this design has a matching assert: `'database is locked'` → assert 5 part 1 asserts
`str(e)` exactly; `'unable to open database file'` → assert 2 asserts the message and assert 6d
asserts the literal as the retry gate; `b'\x02\x02'` → assert 1 asserts the header bytes; the
≈5.1–5.3 s lock wait is evidence-only with an inline note in assert 5 (it motivates `timeout=0`;
a wall-clock time is not an assertable output).

**Whole-doc claim sweep (RT-r6 M2, executed after this patch, output recorded):**
`rg` for the retracted claim `Claude deny` → one substantive hit, the retracted C-04 constraints
row itself (source-pytest proven; live session = OQ-6 operator step, unverified). Every `✅` in the Option A constraints
line re-read against C-04/OQ-6 — none overclaims now. `rg -n "src.index"` → hits only inside the
retracted-pin markers (assert 6's Forbidden clause, the bad-faith inversion row, the matrix
shadow column, pre-mortem 4). OQ-section sweep: every deferred/residual phrase terminates in a
numbered OQ entry; OQ-5.1 and OQ-6 untouched by this patch.


- **Cursor twin refresh — mechanical path specified, a Done cell only if the owner authorizes it
  (OQ-5.2 OPEN, RT-r8 M2).** `install -m 0755` the edited
  `.claude/hooks/writ-blast-gate.sh` onto `~/.cursor/hooks/writ-blast-gate.sh`, then `diff -q` the two
  files and require silence. No pytest can cover this (the suite execs the falkor-writ source), and no
  `hooks.json` is touched. Full rationale and the rejected installer invocations: §3 / OQ-5.2.
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
| "three split messages" vs "same strings on Claude and Cursor" | no | one source script; Cursor runs a byte-identical **copy** wired on Write — same strings, provided the plan's Done cell is the one-file `install -m 0755` + silent `diff -q` (§3), never the Village installer and never a `hooks.json` edit. Same *strings* is all that is claimed: whether Cursor honors the envelope as a deny is OQ-5.1, not settled here |

## Alternatives Considered

### Option A — plain-string `"unreadable"`, no retry hop (Recommended; C1-a form)

**Approach:** as specified above.
**Files touched:** `bin/lib/codegraph_index.py` (`_connect` WAL fallback + enum),
`bin/lib/blast_radius.py` (`_connect` delegation + pass-through + cache fail-closed),
`.claude/hooks/writ-blast-gate.sh` (deny branch) **plus a body-only `install -m 0755` refresh of its
`~/.cursor/hooks/` copy — no `hooks.json`, no Village installer (§3)**,
`bin/lib/artifact_claims.py` (PRE-UNREADABLE + comment), `bin/writ-codegraph-init.sh` (exit-1
branches), `docs/adr/0001-…md` (new), four test files.
**Cost:** dev low-med (~50–60 lines + ~14 tests) · runtime: one probe per gated Write (the cache
no longer skips it, §2) · maintenance: one more enum member in one docstring-documented contract.
**Risk:** *classification* — a locked (SQLITE_BUSY) db is named `unreadable` and the copy says
"rebuild it", which is the wrong advice while a daemon holds the file. Mitigated by naming
"or locked by another indexer" in the message text.
**Module depth:** no new boundary, no new interface; deepens `codegraph_index` (same API, better
answer). `freshness()` stays a 5-line map.
**What it defers:** writ has no `empty`/`busy` names (`busy` → **OQ-2**; `empty` is Bucket 5's);
the `schema_versions`-empty-table hole (**OQ-3**); the Cursor deny envelope
(**OQ-5.1**; the refresh authorization is **OQ-5.2**, re-opened RT-r8 M2 — mechanical path
stands, owner yes pending). Every deferral here has a numbered Open Questions entry — no prose-only punts.
**Constraints check:** C-01 ✅ · C-02 ✅ · C-03 ✅ (untouched branch) · **C-04 ⚠️ partial** — the
consumer half ✅ (every predicate compares to `"usable"`); the **Claude deny = source pytest proven
only** — the **live Claude session is OQ-6 operator work (cache refresh + restart), unverified here**,
and no row may check it off; the **Cursor deny is unverified and OQ-5.1-gated**, so this box is not
✅ on that harness · C-05 ✅ (consume predicate
untouched) · C-06 ✅ (no unlink anywhere) · C-07 ✅ (no retry hop at all) · C-08 ✅ (ban is the command
string ``Run `codegraph index` ``; the noun phrase is legal and recorded as such) · C-09 ✅ · C-10 ✅ ·
C-12 ✅ (read-only; plain `mode=ro` stays the first attempt, `immutable=1` only as the retry, and §7
assert 3 pins that no `-wal`/`-shm` is created) · C-11 ✅ (no MCP, no ready-file, no bus, and
`KNOWN_SCHEMA_VERSIONS` untouched)
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
| A healthy fresh index (WAL, no `-shm`) reads as unreadable | **Closed by OQ-4 A** (§1.0): `_connect` retries once with `immutable=1` after the plain `ro` ping fails, and `blast_radius` shares that opener. Pinned by the §7 WAL-fixture block — asserts 1–2 (header `b'\x02\x02'`, plain-`ro` raises) discriminate WAL from the DELETE-journal fixtures the repo's helpers build, which is the assert set RT-r3 C1 found missing — all three in **one test function** (RT-r5 C1) |
| `immutable=1` reads a db that IS being written (torn/stale read), or a locked db is laundered to `usable` | Two guards, both pinned: (i) plain `ro` leads, so a live indexer's db answers on the first attempt and never reaches the retry; (ii) the retry predicate is the **exact** string `unable to open database file`, while a locked db raises `database is locked` — verified live this session, where the same db reads `[(1,)]` under `immutable=1`, i.e. a broadened predicate *would* launder it. §7 assert 5 (locked DELETE db: plain-`ro` discriminator `str(e) == 'database is locked'` THEN `probe() == "unreadable"`, with chmod/junk/absent explicitly forbidden as substitute fixtures) is the behaviour pin, and assert 6 (two `sqlite3.connect` call sites; first URI literal has `mode=ro` and no `immutable`; second has `immutable=1`; retry guarded by a `str(e)` comparison against the exact error literal — literal extraction over `_connect`'s own source, never position over the whole function text) is the structure pin; both were executed adversarially this session (matrix in §7). `busy` therefore still surfaces as `unreadable` |
| With the retry dropped (C1-a), a `busy`/`unclassified` db gets no second attempt — `init` refuses and touches nothing, so the wrapper exits 1 on a db that may be perfectly fine once the daemon releases it | Accepted by C1-a: the message names the lock as a possible cause, and re-running `writ codegraph-init` after stopping the indexer is one command. Writ never deletes, so nothing is lost by waiting |
| `freshness()` gains a fifth verdict that some caller string-matches | Only two callers exist (blast-gate, `writ-doctor.sh`); doctor prints it verbatim, blast-gate gets an explicit branch; both are in the read-set |
| Wrapper exit-code change (0 → 1 on bad states) breaks a caller that treats nonzero as fatal | Callers: `writ/cli.py` `codegraph_init` passes the code through to the operator (`external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/writ/cli.py:990-992`); no hook consumes it. That passthrough is the intended loud failure |
| `PRE-UNREADABLE` is a new DENY id that could fire on repos mid-index and block dispatch | It fires only where the old code already denied or lied; and the audit seat's waiver machinery (`gate-waive: PRE-UNREADABLE — …`) applies unchanged |
| The two-line probe print in bash mis-parses when a path contains newlines | Detail line is a fixed `found=…;known=…` shape built from ints, never a path |

## Pre-mortem

Three months on, this failed because (1–3 from the original pass; 4–5 added RT-r5):

1. **`freshness()` was updated but the blast-gate's `else` still swallowed it** — the deny copy
   said "stale" for an unreadable index because `unreadable` fell into the final `else`.
   *Design change:* the branch order is specified explicitly (missing / unreadable / unrecognized /
   else stale) and a test asserts the deny reason for an unreadable index **contains**
   `writ codegraph-init`, **does not contain** the command string ``Run `codegraph index` ``, and
   **does not contain** the word "stale" (C1-a item 7; ban shape per C-08 — the noun phrase
   "codegraph index file" stays in the copy on purpose). That test is named in §7
   (`tests/test_blast_gate_hook.py`, unreadable fixture on a code Write) — this pre-mortem names no
   test that §7 omits.
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
4. **`_connect`'s comments said plain-`ro`-first while the code did something else** — the r5 source
   pin (`src.index` position over the whole function) passed on a comment, **failed** an honest
   warning docstring, and a single-combined-URI opener probed a locked index `usable` while the suite
   stayed green. *Design change (RT-r6 closure):* §7 now carries **both** a behaviour pin (assert 5:
   locked DELETE db under `BEGIN EXCLUSIVE` — discriminator `str(e) == 'database is locked'` asserted,
   then `probe() == "unreadable"`, with chmod/junk/absent named as forbidden fixtures) **and** a
   structure pin (assert 6a–d: two connect call sites; first URI literal free of `immutable`;
   retry guarded by a `str(e)` comparison on the caught error — literal extraction over `_connect`'s
   own source, **never** position over whole-function text, so a warning docstring cannot fail it and
   a `# mode=ro` comment cannot pass it). Neither alone is sufficient, and the set was executed
   against the laziest passing implementations before being kept (band-2 matrix in §7). Both are
   named in §7; this pre-mortem adds no test §7 omits.
5. **The merge was green and the owner's live Claude session kept denying with the old copy** — Claude
   execs the plugin cache, not the clone, so the new `unreadable` branch was not in the running hook and
   `freshness() == "unreadable"` rendered as `stale` there. *Design change:* this is stated in C-04's
   Claude row and carried as **OQ-6** (operator: refresh cache + restart), deliberately not a Done-cell.
   No test is claimed for it — pytest cannot reach that file.

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

**OQ-5 — The Cursor Write copy: deny envelope + refresh path (RT-r3 M2).** Two halves:
**OQ-5.1 OPEN** (deferred to spec+) and **OQ-5.2 OPEN** — re-opened **RT-r8 M2** (2026-08-19):
the RT-r4 "CLOSED" was closed by a red-team round, never recorded as an owner answer, and the step
it authorized overwrites the live hook the owner's running Cursor already executes (`$HOME/.cursor/
hooks/writ-blast-gate.sh`, wired `preToolUse`/Write/`failClosed`) — the same class of live-machine
burden OQ-6 correctly left open for the Claude cache. The mechanical refresh path below stands as
the specified way **if** the owner says yes; **the owner must answer, and this patch does not
close it.**

**OQ-5.1 — Does the Cursor Write copy actually deny? (OPEN.)** `~/.cursor/hooks/writ-blast-gate.sh` is a byte-identical copy of the Claude source,
   so it emits **only** `hookSpecificOutput.permissionDecision: "deny"`. Cursor's documented deny is
   flat `{"permission":"deny","user_message":…,"agent_message":…}`, and the recorded live finding is
   that **Claude nesting alone did NOT block a Write on this machine**
   (`external: /Users/phatchenh/all-projects/vibe-coding-setup/agent_village/docs/cursor/CURSOR-KNOWLEDGE.md:246-255`).
   The wiring is live and fail-closed
   (`external: /Users/phatchenh/.cursor/hooks.json:84-86` — `preToolUse`, matcher `Write`,
   `failClosed: true`), and the script always exits 0, so if the envelope is not honored, a Cursor
   operator is **not denied for missing, unreadable, unrecognized, or stale** — today, before this
   bucket. **If left:** the new `unreadable` sentence lands on Claude only and the Cursor half of C-04
   stays a claim. **If fixed:** emit both shapes in one JSON object — a script-body edit inside the
   step this design already opens (grill R15: deny copy is command text, not a `hooks.json` edit), and
   it needs one live Cursor Write against a bad index to confirm. Recommendation: the spec seat runs
   the live check first, then decides; do not write "the deny blocks on Cursor" anywhere until it does.
Do **not** emit the dual envelope this round — that is the decision OQ-5.1 defers.

**OQ-5.2 — What refreshes the copy, and may the impl run it? OPEN (re-opened RT-r8 M2,
2026-08-19).** The mechanical decision — copy the script body, never re-emit `hooks.json` — stands
as the specified path; the **authorization** is open. The grill froze `hooks.json` edits; it did
not record an owner yes to overwriting `$HOME/.cursor/hooks/writ-blast-gate.sh`, the live hook the
owner's running Cursor already executes (wired `preToolUse` / Write / `failClosed` —
`external: /Users/phatchenh/.cursor/hooks.json:84-86`). OQ-6 leaves the Claude cache refresh to
the operator for exactly this reason; the same reasoning re-opens this. **Question to the owner:**
may the impl step run the body copy below, or is it an operator action like OQ-6's? The mechanical
shape (only pending answer):

```sh
install -m 0755 <falkor-writ>/.claude/hooks/writ-blast-gate.sh ~/.cursor/hooks/writ-blast-gate.sh
diff -q <falkor-writ>/.claude/hooks/writ-blast-gate.sh ~/.cursor/hooks/writ-blast-gate.sh   # silent
```

Rejected: `agent_village/scripts/hooks/install.sh` in every one of its real argv forms — `copy_pair`
is an internal function, not a subcommand (unknown argv → `exit 2`); bare install refuses by design;
`--all` is the documented manifest blast; `--only writ-blast-gate` writes `~/.cursor/hooks.json`,
which the grill froze out ("No settings/hooks.json edit") and which would also copy from the
writ-root pin rather than the edited worktree. Evidence and line cites in §3. Also rejected:
`writ-doctor` (never copies this file). **If the owner answers yes**, the plan's Done cell for the
blast-gate step is the silent `diff -q` — **not** pytest, which only ever executes the falkor-writ
source script
(`external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/tests/test_blast_gate_hook.py:32-33`),
so a skipped copy stays green in CI and stale on Cursor; **if the owner answers no or stays
unasked**, the copy is an operator follow-up like OQ-6's, not a merge Done-cell, and the blast-gate
step is done on the falkor-writ source + pytest alone.

**OQ-6 — Who refreshes the Claude plugin cache, and when? (OPEN — operator; explicitly NOT a Done-cell
of this bucket. RT-r5 M2.)** Claude Code does not exec the falkor-writ clone:
`external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/hooks/hooks.json:245,258`
runs `bash ${CLAUDE_PLUGIN_ROOT}/.claude/hooks/writ-blast-gate.sh` — `CLAUDE_PLUGIN_ROOT` is Claude
gate-waive: C6-FICTION — `CLAUDE_PLUGIN_ROOT` is defined by the Claude Code platform (plugin runtime), used verbatim on the abs `external:`-cited falkor-writ line above; not a piggyback symbol, not new.
Code's own plugin variable, set to the
`writ@writ` `installPath` recorded in `~/.claude/plugins/installed_plugins.json` — on this machine
`/Users/phatchenh/.claude/plugins/cache/writ/writ/1.6.1`, verified 2026-08-19. The clone's own tool says
why: "Claude Code copies a plugin into `~/.claude/plugins/cache/…` and runs hooks/agents FROM THAT COPY
… The copy does not follow `git pull` … Restart Claude Code afterwards"
(`external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/writ-refresh-plugin-cache.sh:4-10`),
and the same file records the failure mode of pretending otherwise: "A remediation tool that cannot
affect the thing it remediates … manufactures confidence" (`:25-30`).

**Why it is not a Done-cell here.** Running a cache refresh plus a Claude restart is operating burden
on the owner's live machine, and no grill lock requires this bucket to carry it — the grill froze one
contract surface (`probe()` + four consumers) and no wiring edits. Making
`bin/writ-refresh-plugin-cache.sh` a required step would put a machine-wide, session-restarting action
inside a bucket whose scope is a Python enum and a deny string. **If left:** after merge, a Claude
session keeps the pre-fix three-branch hook until the operator refreshes — the new `unreadable` verdict
renders as `stale` there, exactly pre-mortem 1, on the harness the owner uses. **If adopted later:** the
sibling Done-cell is `bin/writ-refresh-plugin-cache.sh` followed by `diff -q` of the source hook against
the `installPath` copy, then a Claude restart. Recommendation: record it here, name it in the run
report's operator-follow-ups, and let the owner decide whether the refresh belongs to this merge or to
the normal post-merge routine. C-04's Claude row is written to match this (source-proven, not
live-proven) — no downstream doc may claim the live Claude session denies until the cache is refreshed.

A residual MAJOR is allowed to leave this design only as an entry here (OQ-5.1, OQ-5.2, OQ-6) — not as prose
elsewhere.

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
- `external: /Users/phatchenh/all-projects/vibe-coding-setup/falkor-writ/bin/lib/artifact_claims.py:2155-2185,2186-2200,2270-2280,2350-2360,2480-2510` (`_c16_resolve_node`, `check_c11`, `check_c12`, `check_c16` probe guards, `_c12_container`)
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
   dated 2026-08-19 11:23; `diff` re-run this session → IDENTICAL). Matters twice: the copy must be
   refreshed after the deny-copy edit — by a one-file `install -m 0755` of the script body, verified
   with a silent `diff -q` (**OQ-5.2**, re-opened RT-r8 M2 — mechanical path settled, owner
   authorization to overwrite the live `~/.cursor/hooks/` file pending; the Village installer and
   `writ-doctor` are both
   rejected, §3) — and the Cursor-side deny envelope is still the Claude nested shape, which the
   recorded live finding says did not block a Write on this machine (**OQ-5.1**, open). No downstream
   doc may claim Cursor blocks until OQ-5.1 closes.
10. **falkor-writ has no ADR directory yet.** No `docs/adr/` or `docs/decisions/` exists (find over
    the repo). Matters: the impl step creates the directory, it does not append to an index.

11. **A freshly built index is WAL-mode with no sidecars, and a read-only probe cannot read it —
    and the repo's own test fixtures are NOT that shape.** Re-verified live this session (band-1),
    real `codegraph init` in a mktemp git repo:

    ```
    header[18:20] = b'\x02\x02' write_version = 2 read_version = 2
    plain ro EXECUTE raised OperationalError 'unable to open database file'
    immutable schema_versions = [(1,), (5,)]
    listing after reads = ['.gitignore', 'codegraph.db']
    ```

    Contrast, same session, the shape `make_index` / `_make_usable_index` build
    (`sqlite3.connect(idx)`, default journal):

    ```
    DELETE-fixture header[18:20] = b'\x01\x01' write_version = 1
    plain ro execute -> [(1,)]      # no retry needed
    probe(DELETE fixture) = usable
    ```

    Junk bytes stay `DatabaseError: file is not a database` and `chmod 000` stays unreadable under
    both URIs. Matters twice: (i) it is the evidence behind OQ-4 A — plain-`ro`-then-`immutable` is
    what keeps `"unreadable"` meaning a dead index rather than every healthy fresh one; (ii) the two
    headers are the **only** thing that separates the fixture the tests must use from the fixture the
    repo's helpers hand you, which is why §7 asserts the header bytes and the plain-`ro` failure
    before it asserts `usable` (RT-r3 C1).

## Claim sweep

Amendments through RT-r8 (2026-08-19). Counts are **self-inclusive** — the artifact-claims gate
re-runs each pattern over the whole file, so each retired-claim line expects exactly **1** (its own
declaration; **0** in the body above this section), and each new-claim expectation is body + 1.
Corrected claims (residual = the declaration only):

- pattern: "equivalently it contains" · expect: 1 · files: docs/AI_artifacts/3_design/2026-08-19-bkt6-writ-probe.md
- pattern: "has neither immutable nor nolock" · expect: 1 · files: docs/AI_artifacts/3_design/2026-08-19-bkt6-writ-probe.md
- pattern: "OQ-5.2 CLOSED" · expect: 1 · files: docs/AI_artifacts/3_design/2026-08-19-bkt6-writ-probe.md
- pattern: "CLOSED this round** (RT-r4" · expect: 1 · files: docs/AI_artifacts/3_design/2026-08-19-bkt6-writ-probe.md
- pattern: "settled as OQ-5.2" · expect: 1 · files: docs/AI_artifacts/3_design/2026-08-19-bkt6-writ-probe.md
- pattern: "grep over \`bin/lib/*.py\`" · expect: 1 · files: docs/AI_artifacts/3_design/2026-08-19-bkt6-writ-probe.md
- pattern: "with no intervening rebuild" · expect: 1 · files: docs/AI_artifacts/3_design/2026-08-19-bkt6-writ-probe.md
- pattern: "probe(repo) == \"unreadable\"\` (not" · expect: 1 · files: docs/AI_artifacts/3_design/2026-08-19-bkt6-writ-probe.md

New claims pinned by the RT-r7/RT-r8 patches — must exist:

- pattern: "vfs=unix-none" · expect: 13 · files: docs/AI_artifacts/3_design/2026-08-19-bkt6-writ-probe.md
- pattern: "5b1" · expect: 7 · files: docs/AI_artifacts/3_design/2026-08-19-bkt6-writ-probe.md
- pattern: "no mutation of any kind" · expect: 2 · files: docs/AI_artifacts/3_design/2026-08-19-bkt6-writ-probe.md
- pattern: "re-opened RT-r8 M2" · expect: 5 · files: docs/AI_artifacts/3_design/2026-08-19-bkt6-writ-probe.md
- pattern: "One predicate: equality" · expect: 2 · files: docs/AI_artifacts/3_design/2026-08-19-bkt6-writ-probe.md
- pattern: "ast walk, not a grep" · expect: 2 · files: docs/AI_artifacts/3_design/2026-08-19-bkt6-writ-probe.md
- pattern: "re-asserted AFTER assert 4" · expect: 2 · files: docs/AI_artifacts/3_design/2026-08-19-bkt6-writ-probe.md
- pattern: "pin-set-harness-v3" · expect: 4 · files: docs/AI_artifacts/3_design/2026-08-19-bkt6-writ-probe.md
- pattern: "pin-set-rt8-output" · expect: 4 · files: docs/AI_artifacts/3_design/2026-08-19-bkt6-writ-probe.md
- pattern: "Done (RT r8): patch complete" · expect: 2 · files: docs/AI_artifacts/3_design/2026-08-19-bkt6-writ-probe.md
