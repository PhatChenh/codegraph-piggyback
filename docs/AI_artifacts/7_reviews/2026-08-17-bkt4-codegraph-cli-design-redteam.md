# Design red-team — Bucket 4 codegraph CLI

_Date:_ 2026-08-17  
_Artifact:_ `docs/AI_artifacts/3_design/2026-08-17-bkt4-codegraph-cli.md`  
_Mode:_ **cross-model** (author: claude-opus; reviewer: cursor-grok-46). Certifies craft against repo + contracts; cannot certify judgment the reviewer shares with the author, and cannot certify same-model “fresh eyes on own prose.”  
_Stakes aimed:_ (1) refuse `${…}` at both doors, no cwd fallback (2) `init` repairs empty/unreadable without wiping busy (3) probe must not open via `DatabaseConnection.open` (no migration writes).  
_Fix:_ nothing.

---

## Executive summary

Option A (shared `${…}` guard at both resolve sites + a five-arm probe + in-place empty repair / three-file unreadable replace / busy refuse) is the right shape for the locked promises. The three SQLite classification recipes that the dispatch table rests on **reproduce on the deployed runtime** `~/.codegraph/versions/v1.0.1/node` (v24.16.0). No CRITICAL. Eight MAJOR holes, all “revise the spec/gates,” not “rethink refuse + repair”: the unreadable Done cell does not catch a stale-WAL under-delete; the probe is forbidden from `DatabaseConnection.open` **by name** while `configureConnection` / `createDatabase` still write; `OpenOptions.readOnly` is a dead trap; `{ readOnly: true }` works on the bundled Node and is not required; empty-vs-recreate is gated on POSIX inode that this fork already nulls on Windows; Option A omits `finally` close; OQ-1’s alt file and OQ-3’s prompt can violate frozen constraints; exporting the 5-arm probe is a new multi-consumer contract the LIGHT freeze forbade.

---

## Steelmans (then the hunt)

**Steelmans.** Two doors really exist: `resolveProjectPath` is 14 call sites and `init` resolves at `codegraph/src/bin/codegraph.ts:468` without it — a guard only in the helper leaves `codegraph init '${workspaceFolder}'` able to `mkdirSync(..., { recursive: true })` a directory literally named `${workspaceFolder}`. Existence-only `isInitialized` (`directory.ts:100` `fs.existsSync`) is the ITEM-5 bug; changing it would hit MCP walk-up (`findNearestCodeGraphRoot` → `isUsableRoot`). A total dispatch with `unclassified` as the non-destructive default, busy as errcode 5, and unreadable limited to 26 / 11 / message-gated 1, matches lock 3-c. Empty = `COUNT(*) FROM nodes === 0` matches `getStats().nodeCount` (`queries.ts:1784`). Not using `DatabaseConnection.open` for the probe is required: `open` runs `runMigrations` (`db/index.ts:112`).

**Hunt.** Hidden coupling: an exported 5-arm `probeIndexHealth` becomes the thing Buckets 5/6 are told to start from (R9 + ADR), while scope called this LIGHT because it is “not a new multi-consumer API.” Stronger alternative the design never considered: `new DatabaseSync(dbPath, { readOnly: true })` — verified on v24.16.0; a WAL pragma then throws errcode 8 instead of mutating. Codebase contradiction: `OpenOptions.readOnly` exists (`index.ts:109`) and is **never read**; `CodeGraph.open` always calls `DatabaseConnection.open`. Simpler design that removes stake-3: require readonly open + COUNT, and ban `configureConnection` / `createDatabase`. Irreversibility trap: unreadable unlink is intended, but the Done cell that is supposed to prove “three-file set, not a leftover WAL” accepts an under-delete.

---

## Gate co-satisfiability (audit 2 opening)

Honest implementation of Option A against the behaviour-contract table:

| Pair | Honest path | Result |
|---|---|---|
| must refuse `${…}` **and** never use cwd | guard before resolve; exit; no mkdir | PASS if tests snapshot cwd |
| must refuse init positional **and** keep bare cwd | guard only when `pathArg` present | PASS (specified) |
| must index empty **and** never re-index healthy | `nodeCount === 0` vs `> 0` | PASS |
| must index empty **and** never replace the file | `cg.clear()` same inode | PASS on POSIX; **FAIL as a gate on win32** (M4) |
| must replace unreadable **and** never delete anything else | vanished ⊆ `{db,wal,shm}` | PASS for over-delete; **FAIL to catch under-delete of wal/shm** (M1) |
| must replace unreadable **and** never wipe busy | total dispatch, disjoint arms | PASS (cannot be both) |
| must not probe via `DatabaseConnection.open` **and** empty repair must `CodeGraph.open` | probe ≠ repair | PASS if followed; **gamed if probe reuses `configureConnection`** (M2) |
| Constraint 1 file list **and** OQ-1 new module | mutually exclusive if OQ-1 alt picked | **RED if OQ left open** (M5) |
| lock 2-a index-without-asking **and** OQ-3 TTY prompt | mutually exclusive if prompt picked | **RED if OQ left open** (M6) |

No unsatisfiable pair inside the chosen numbered steps. Two red cells appear only if still-open OQs are answered against the freeze.

---

## Findings

### CRITICAL

None. Option A does not need a different architecture.

### MAJOR

**M1 — Unreadable Done cell does not catch the stale-WAL under-delete the design itself names.**  
Verdict: **revise** the unreadable assertion.  
`file:location:` design behaviour table unreadable row (`docs/AI_artifacts/3_design/2026-08-17-bkt4-codegraph-cli.md` ~298) vs Implication K / R3 (~143, ~371).  
Evidence: the gate is “names that disappeared ⊆ `{codegraph.db, codegraph.db-wal, codegraph.db-shm}`” plus survivors’ sha256. Recreating `codegraph.db` means the db **name did not disappear**. Sidecars are in the three-file set, so their sha256 is **not** required to change.  
Reproduced:

```
# unlink only codegraph.db, rewrite it, leave codegraph.db-wal
vanished: []
vanishedSubset: true
walUnchanged: true
after: ['codegraph.db', 'codegraph.db-wal', 'lessons.db']
```

An implementation that unlinks only the db file therefore **passes the Done cell** while doing the exact failure Implication K exists to prevent (“Deleting `codegraph.db` while leaving a stale `-wal`/`-shm` next to a brand-new db is how a repair produces a second corrupt db”). R3’s prose says unlink the three together; the gate does not require it. Over-delete of `lessons.db` **is** caught (name not in the set). The load-bearing hazard is the uncaught one.

**M2 — Probe “must not use `DatabaseConnection.open`” is a name ban, not a write ban. `configureConnection` mutates; `createDatabase` strips `errcode`; `{ readOnly: true }` exists on the bundled runtime and is not required.**  
Verdict: **revise** the probe contract to a mechanically unwritable open.  
`file:location:` design Option A step 2 (~197) + Implication I (`db/index.ts:112`); `configureConnection` `db/index.ts:30-37`; `createDatabase` `sqlite-adapter.ts:137-148`; dead `OpenOptions.readOnly` `index.ts:109` vs `CodeGraph.open` `index.ts:309`.  
Evidence, bundled `v24.16.0`:

- `PRAGMA journal_mode = WAL` on a DELETE-mode db **changes sha256** at **same size** (8192 → 8192). That is the mutation class the snapshot helper was invented to catch — and a probe that “isn’t `DatabaseConnection.open`” but calls `configureConnection` still does it.
- `PRAGMA busy_timeout = 500` alone does **not** change sha256 (so the design’s minimal pair is actually non-mutating, if followed).
- `createDatabase` wrap of a directory-at-path error: thrown object keys `["stack","message"]` — **no `errcode`**. Same destination (`unclassified`) today; the adapter cannot pass `readOnly` (`new DatabaseSync(dbPath)` with no options, `sqlite-adapter.ts:56`). Adapter is **not** on Constraint 1’s file list, so the probe cannot grow `readOnly` through the official helper without expanding the surface.
- `new DatabaseSync(p, { readOnly: true })` succeeds; `PRAGMA journal_mode = WAL` then throws errcode **8** `attempt to write a readonly database` (Node docs: https://nodejs.org/docs/latest-v24.x/api/sqlite.html fetched 2026-08-17; behaviour confirmed on `~/.codegraph/versions/v1.0.1/node`).
- Gaming: `CodeGraph.open({ readOnly: true })` looks like the probe. `options.readOnly` is never read; `open` always migrates.

Stake 3 is therefore not enforced by the text that implementers will copy. Require `DatabaseSync(dbPath, { readOnly: true })` (or equivalent SQLITE_OPEN_READONLY), COUNT only, no `configureConnection`, no `createDatabase`, no `CodeGraph.open`.

**M3 — Production probe has no `finally` close. Hold 7 parks it on “the plan.”**  
Verdict: **revise** Option A step 2, not a later plan.  
`file:location:` Option A step 2 (~197: one `try`, no `finally`) vs Hold 7 (~361).  
Evidence: Hold 7’s own successor is the fork’s known Windows `EPERM` `afterEach` when a handle leaks (`codegraph/CLAUDE.md` Windows-gated tests). The Chosen Approach is what gets implemented; a hold that says “the plan must specify `finally`” is not a production contract. Same class as a Done cell that lives only in premortem prose.

**M4 — Empty-row “inode unchanged” cannot distinguish delete-and-reinit on Windows. This fork already knows that.**  
Verdict: **revise** the empty identity gate.  
`file:location:` empty Done row (~297) vs `statInode` `codegraph/src/db/index.ts:269-276` — quote: `if (process.platform === 'win32') return null;` and `isReplacedOnDisk` comment `index.ts:252-253` “Windows … st_ino is unreliable.”  
The empty vs unreadable distinction **is** “same inode” vs “file replaced.” On win32 the fork refuses to use inode for that reason. Hold 5 gates `chmod 000` off win32; the empty inode assertion is **not** gated. A Windows run can pass a cheating unlink+reinit for `empty`, which is the exact dishonest path the inode sentence exists to catch.

**M5 — OQ-1’s still-live alternative violates Constraint 1 and, if implemented via `db/index.ts`, is a circular import.**  
Verdict: **revise** — close OQ-1 or strike the alt.  
`file:location:` Constraint 1 (~178: files = `codegraph.ts`, `directory.ts`, tests, `UPDATING.md`, `CHANGELOG.md`, one ADR) vs OQ-1 (~383: “or a new `codegraph/src/index-health.ts`”).  
`db/index.ts:12` `import { getCodeGraphDir } from '../directory';`. `directory.ts` today imports only `fs`/`os`/`path` (lines 7–9). Importing `DatabaseConnection` / `configureConnection` from `../db` into `directory.ts` is a cycle. Raw `node:sqlite` is the leaf OQ-1 claims; the OQ does not say so, and the alt file is not on the allowed list.

**M6 — OQ-3 (TTY confirm) is still open and the wrong answer breaks lock 2-a and Bucket 6.**  
Verdict: **revise** — close as no-prompt.  
`file:location:` OQ-3 (~397) vs grill lock 2-a (`docs/AI_artifacts/_handoff/2026-08-17-bkt4-codegraph-cli-grill.md`: “Empty or unreadable → index”) vs design Constraint 9 / writ consumer row (~170: wrapper is non-interactive).  
`uninit` already prompts (`codegraph.ts:550-565`). Copying that pattern for `init` repair is the lazy reading. A prompt without a documented `--yes` / non-TTY bypass hangs `writ-codegraph-init.sh`. Grill: “Open questions remaining: None.” Reopening this is a silent owner-value (destructive confirm) after the lock already chose “runs index.”

**M7 — Exporting `probeIndexHealth` as the 5-arm seam for Buckets 5/6 violates the LIGHT freeze that justified this bucket.**  
Verdict: **revise** — keep the function unexported / CLI-local, or explicitly freeze a new contract (that is FULL).  
`file:location:` scope ITEM-2-cg (`docs/AI_artifacts/_scope/2026-08-16-feedback-bugs-scope.md` ~108: “not a new multi-consumer API”) vs design L (~148) + R9 (~378) + ADR blurb (~408).  
Scope §4 FULL admission test includes “new contract other parts consume.” The design names two future consumers and tells Bucket 5 to start from this union. The 5-arm set (`usable|empty|unreadable|busy|unclassified`) is **not** writ’s freeze (`missing|unreadable|unrecognized|usable`) and **not** MCP’s (`index_missing|index_empty`). Exporting it now either freezes a third enum or invites parallel vocabularies — the thing R9 treats as a risk while still shipping the export.

**M8 — Repair write failures other than errcode 5 are unspecified; the destructive arm can be reached by a catch-all.**  
Verdict: **revise** the write-path dispatch.  
`file:location:` Option A step 3 (~208: “Errcode 5 raised during any *write* of the repair aborts into the same `busy` error”) vs Constraint 6 (~185: unlink only after positive `unreadable`).  
`CodeGraph.open` (empty repair) runs migrations + `validateDirectory` → `ensureGitignore` (a write, `directory.ts:268-279`). `cg.clear()` (`queries.ts:1861-1868`) DELETEs `files`/`edges`/… — a db with a `nodes` table and no `files` table: probe `COUNT(*)` succeeds (verified: “nofiles nodes COUNT ok”), classification `empty`, then `clear()` throws errcode 1 `no such table: files`.  
Gaming: `catch (e) { if (busy) … else treat as unreadable and unlink }` widens deletion to every non-5 write failure, including permissions. Honest-but-lazy: let it fall into init’s existing `catch { process.exit(1) }` (`codegraph.ts:528-530`) after a partial mutation, with no reclassify and no “touch nothing” snapshot. Either way the write path is not the total dispatch the probe is.

---

### MINOR

**m1 — “10 callers including `codegraph/src/mcp/**`” is false.**  
`directory.ts` `isInitialized`: **21** call sites in `src/` (`bin/codegraph.ts` 15, `index.ts` 5, `directory.ts` 1). **Zero** in `src/mcp/`. MCP coupling is `findNearestCodeGraphRoot` (`mcp/session.ts:21`, `mcp/tools.ts:8`, `mcp/index.ts:40`, `mcp/engine.ts:14`) → `isUsableRoot` → `isInitialized`. Conclusion (do not change the predicate) still holds; the cited blast radius does not.

**m2 — `createDatabase` is a silent errcode launderer.**  
Directory-at-path through the wrap: no `errcode` property (verified). Fine today because no-errcode → `unclassified`. Becomes a dispatch bug the moment anyone adds a code-based arm for 14.

**m3 — Partial schema with `nodes` but no `files` is `empty`, not `unreadable`.**  
Verified: `no such table: files` is errcode 1 with a **different** message, so the message-gated unreadable arm does not fire. Empty repair then dies in `clear()`. Constraint 7 may intend this; say so, or the implementer “fixes” it via M8’s catch-all.

**m4 — chmod-000 in-place rewrite is invisible to the `<unreadable>` sentinel.**  
Hold 1 already says this. The unclassified/busy “sha256 unchanged” claim for that fixture is really `ino` + sentinel. Not closed in the Done cell.

**m5 — Production `busy_timeout` for the probe is unspecified (test recipes use 500; `configureConnection` uses 5000).**  
Non-WAL exclusive + timeout 500 → errcode 5 in 546ms; timeout 5000 → errcode 5 in 5213ms (verified). If production copies 5000, `init` on a locked DELETE-mode db waits five seconds. Not asked (human-authority: latency); not a lock break.

**m6 — Pre-dispatch “grep workspaceFolder returns exactly one generator” overstates the grep.**  
`codegraph/src` hits also include `mcp/session.ts` `workspaceFolders` and comments in `directory.ts` / `codegraph.ts`. The **literal emitter** is still only `cursor.ts:173`. Claim’s meaning holds; the grep sentence does not.

---

## Simulation transcripts

### Audit 3 — gaming the three stakes

**Stake 1 — `${…}` both doors, no cwd fallback.**  
Bad-faith: put the hard error only in `resolveProjectPath`; `init` keeps `path.resolve(pathArg || process.cwd())`. `codegraph init '${workspaceFolder}'` still `mkdirSync` recursive (`createDirectory` `directory.ts:300`) and creates a folder named `${workspaceFolder}`. `--path` commands look fixed. The init Done row catches this **if** the plan copies `existsSync('${workspaceFolder}') is false`. Option A numbered step 1 does name both call sites; a planner who implements “add the guard inside `resolveProjectPath`” from Implication L’s “14 callers inherit” sentence and skips step 1(b) ships the hole the grill exists for. Under-specified relative to that sentence, specified relative to step 1. **Not a finding against the table; a finding against Implication L as a competing instruction.** (Logged as part of M5/M7 class: competing instructions. Severity: folded into gaming, not a separate MAJOR.)

Bad-faith 1b: `console.error` + `pathArg = undefined` + continue (today’s control flow at `codegraph.ts:202-210`). Exit 0 or even non-zero **after** `findNearestCodeGraphRoot(cwd)` has already borrowed an index. Snapshot of cwd `.codegraph/` identical **fails** if they created nothing; borrowed **read** of a parent index may leave bytes unchanged. The row also requires `readdirSync(cwd)` contains no `${workspaceFolder}` entry — a fallback that only *reads* still passes. **Gap:** “cwd is not used” is not fully implied by “cwd `.codegraph/` snapshot identical.” A status command that walked up and printed another tree would pass. Need an assertion that no index was opened (no SQLite busy on cwd db, or spy). **MINOR under-spec; not promoted** because serve `--mcp` exiting before `MCPServer` start is the locked loud-failure, and that row’s “no index is opened” is explicit.

**Stake 2 — repair empty/unreadable, do not wipe busy.**  
Bad-faith unreadable: unlink db only (M1). Green on vanished-names.  
Bad-faith empty: unlink+reinit (same stdout as clear+index). Caught by inode **on POSIX**, not on Windows (M4).  
Bad-faith busy: `clack.log.error` + `return` (copy the already-initialized branch at `codegraph.ts:486-494`, which exits **0**). Constraint 9 says non-zero; the surrounding function’s pattern is `return` with 0. Tests must assert spawn status, not only stderr. Specified, easy to miss.  
Bad-faith unclassified: treat errcode 14 / no-errcode as unreadable so `init` “always makes progress.” Directly violates Constraint 6; fixtures (b) directory-at-db-path and (a) chmod 000 exist to stop this **if** written.

**Stake 3 — probe must not migrate.**  
Bad-faith: `createDatabase` + `configureConnection` without `runMigrations`. Not `DatabaseConnection.open`. Still WAL-writes (M2, sha256 change at constant size).  
Bad-faith: `CodeGraph.open({ readOnly: true })`. Typechecks. Still migrates.  
Honest-but-wrong: import from `../db` into `directory.ts` (cycle, M5) and call `DatabaseConnection.open` because that is “how this fork opens sqlite.”

### Audit 4 — feasibility (ran, did not opine)

Runtime: `~/.codegraph/versions/v1.0.1/node` v24.16.0. Recipes:

| Input | Result | Design arm |
|---|---|---|
| text file, ctor | ctor OK | (junk fails at statement) |
| text file, `PRAGMA journal_mode` / `COUNT(*)` | errcode **26** `file is not a database` | unreadable |
| valid sqlite, no `nodes` | errcode **1** `no such table: nodes` | unreadable |
| smashed pages after 4096 | errcode **11** `database disk image is malformed` | unreadable |
| `chmod 000` | ctor errcode **14** `unable to open database file` | unclassified |
| directory at path | ctor errcode **14** same | unclassified |
| `new DatabaseSync(12345)` | `ERR_INVALID_ARG_TYPE`, **no errcode** | unclassified |
| WAL + `BEGIN EXCLUSIVE`, read COUNT | **succeeds** 0ms | node count (not terminal) |
| WAL + exclusive, write insert | errcode **5** | busy on write |
| DELETE journal + exclusive, read COUNT, timeout 500 | errcode **5** in 546ms | busy from probe |
| same, timeout 5000 | errcode **5** in 5213ms | — |
| `{ readOnly: true }` then WAL pragma | errcode **8** | not in the table → would be unclassified |
| `nodes` exists, `files` missing, COUNT nodes | OK | empty (then repair write fails) |
| `createDatabase`-style wrap of dir ctor | Error, **no errcode** | unclassified via first arm |

Assumptions 1–12, 15: **hold** (quotes and line numbers checked in this session). Assumption 13: **holds** on this runtime for the seven recipes. Assumption 14: **holds as policy**; M1/M2/M8 are about gates not matching that policy.

`getCallees` conjoins `calls|references|imports|instantiates` (`traversal.ts:305`). Current design already requires `edge.kind === 'calls'` and `main → greet` (b.ts → a.ts). Fixture source at `index-command.test.ts:53-58` matches. That bar is feasible.

WAL sidecars: while a connection is open, `-wal`/`-shm` exist; after a clean `close()` this runtime checkpointed them away. Live MCP/daemon is the leftover-sidecar case, which is also the busy case. Crash/kill leftovers still make M1’s planted-sidecar gate hole live.

---

## Audit 1 — fact & arithmetic (delta only)

Verified exact: `resolveProjectPath` definition `:197` + 14 call sites `542, 605, 684, 746, 913, 989, 1107, 1172, 1437, 1507, 1544, 1623, 1701, 1808`; init own resolve `:468` absent from that list; warning text `:205`; detector `:169`; `serve --mcp` `:1437`; `isInitialized` existsSync `:100`; `Already initialized` `:487`; `createDirectory` existsSync `:295`; `cg.clear()` `:643`; `getNodesByName` `:825`; `getCallees` `:1000`; `getStats` COUNT `:1784`; MCP empty `tools.ts:2273`; migrations `:112`; WAL pragma `:33`; busy_timeout `:5000`; journal-mode comment `:145-149`; adapter `:56`; fatal handler `:90`; UPDATING `:22` `ignored with warning`; rsync `:55`; BIN test `:23`; cursor `:173`; 9.6 GB incident `UPDATING.md:11`.

Failed facts: “10 callers including mcp/**” (m1); “grep workspaceFolder returns exactly one generator” as a grep result (m6).

---

## Audit 5 — contract compliance

| Contract | Result |
|---|---|
| Grill 1-a both doors | Specified (Option A step 1). Competing “14 callers inherit” sentence can be read as init-unnecessary (gaming stake 1). |
| Grill 2-a empty/unreadable → index | Specified. OQ-3 can undo it (M6). Directory-at-path / chmod 000 carved to unclassified (lock 3-c wins over a maximal reading of “unusable”). |
| Grill 3-c smashed db only; busy no wipe | Specified in dispatch. M1 gate does not prove sidecar unlink. M8 can widen wipe. |
| Grill 4-a ADR | Specified. |
| Grill C1 hard error, name literal, no cwd, non-zero | Specified. |
| Scope OUT mcp / writ / installer | File list respects it. Exporting the probe for those consumers does not (M7). |
| Scope LIGHT “not a new multi-consumer API” | Breaks if the function is exported (M7). |
| CLAUDE.md never write piggyback-side to the db | n/a (fork owns the db). |
| CLAUDE.md fork discipline / UPDATING.md | Specified (ship checklist). |
| `isInitialized` frozen | Specified. Fact about MCP callers wrong (m1). |
| No `.codegraph/ready` | Specified. |
| Detector `${` only | Specified; line 169 holds. |
| Human-authority | OQ-3 is asked (good) but left open after the grill closed owner questions. No silent spend/SLO. Probe timeout 500 vs 5000 unasked (m5). |

---

## Audit 6 — missing-by-construction

The artifact argues Option A is the only option that hits both locks — true vs B/C as written. What that position hides:

1. Mechanical readonly open (not in Alternatives Considered) removes the classification-mutation class without a new module.
2. The LIGHT process choice is treated as settled while the recommended seam is FULL-shaped (exported enum).
3. Rollback: unreadable unlink has no restore of the junk bytes (acceptable if junk; not stated). Empty `clear()` is transactional; unreadable-then-failed-index leaves **no** db (re-runnable `init`, not stated).
4. `OpenOptions.readOnly` as an attractor for the wrong implementation is never mentioned.
5. Self-review residue: Mini-RT holds 1–7 are authored as already-absorbed; several successors are still “the plan must…,” which this review treats as open production spec (M1/M3/M4).

---

## Mode (what this cannot certify)

Cross-model, verification-based, this session. Cannot certify: shared taste about LIGHT-vs-FULL (flagged as contract, not taste); Windows VM behaviour (read `statInode` + fork docs, did not boot the VM); whether a leftover WAL after a **crash** (not clean close) actually corrupts a replacement db on this SQLite (M1 does not need that — the Done cell is already too weak).

**Verdict for ORCH:** 0 CRITICAL, 8 MAJOR (M1–M8). Do not implement from this draft until M1–M2–M6 are closed; M3–M5–M7–M8 are the same class of “implementer can honestly ship the wrong thing.”
