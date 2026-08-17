# Design — Bucket 4: codegraph CLI refuses `${…}` + `init` repairs an unusable index

_Date:_ 2026-08-17 · _Tier:_ LIGHT PLAN (`code-read: light-plan`)
_Parent scope:_ `docs/AI_artifacts/_scope/2026-08-16-feedback-bugs-scope.md` (Bucket 4 = ITEM-2-cg + ITEM-5)
_Locked requirements:_ `docs/AI_artifacts/_handoff/2026-08-17-bkt4-codegraph-cli-grill.md` (LOCKED 2026-08-17)
_Surface:_ local fork `codegraph/` — CLI only. MCP `tools/list` (Bucket 5) and writ `probe()` (Bucket 6) are OUT.

---

## Pre-dispatch audit

**Consumer list — who reads the surfaces this design touches**

| Consumer | Reads what | Effect of this change |
|---|---|---|
| `codegraph` CLI operator (human) | `init` / `index` / `status` / `explore` exit codes + stderr | new hard error on `${…}`; `init` may now index instead of no-op |
| Cursor Desktop / global install | MCP args written by the Cursor installer target | when Cursor DOES expand → unchanged; when it does NOT → server refuses to start instead of indexing cwd |
| Village ACP seat | staged `.cursor/mcp.json` with an absolute worktree path (Bucket 1, DONE) | unaffected — no `${` left to refuse |
| Claude Code MCP | `serve --mcp` with an installer-written absolute path | unaffected |
| `writ-codegraph-init.sh` + writ `probe()` | runs `codegraph init`, then probes | `init` now leaves a usable index in the empty/junk cases the wrapper was papering over. No writ file is edited in this bucket (Bucket 6). |
| Bucket 5 (MCP tri-state) | same fork, `codegraph/src/mcp/session.ts` | inherits a loud `${…}` failure; no shared symbol is renamed here |

**Recorded command + output per scope claim**

1. Claim "`resolveProjectPath` has ~15 callers and `init` is NOT one of them":
   `grep -n "resolveProjectPath(" codegraph/src/bin/codegraph.ts` → definition at `:197` plus 14 call sites (`542, 605, 684, 746, 913, 989, 1107, 1172, 1437, 1507, 1544, 1623, 1701, 1808`). Line `468` (init's own resolve) is absent from that list.
2. Claim "every classification arm is a real, reproducible SQLite error code on the runtime that ships" — all seven probes run on **the deployed runtime** `~/.codegraph/versions/v1.0.1/node` (`v24.16.0`); the first two also on the dev `node` (`v24.15.0`):
   - junk: `new DatabaseSync('/tmp/cgprobe/junk.db'); d.exec('PRAGMA journal_mode = WAL')` on a text file → SQLite code 26 `file is not a database` (the constructor itself does not throw).
   - locked (write, WAL): second process in `BEGIN EXCLUSIVE`, then insert → SQLite code 5 `database is locked`.
   - locked (**read**, non-WAL): fixture with `PRAGMA journal_mode = DELETE`, second process in `BEGIN EXCLUSIVE`, then `SELECT COUNT(*) FROM nodes` with probe `busy_timeout=500` (today) → `READ ERR` SQLite code 5 `"database is locked"`. This is what makes `busy` reachable from a read-only probe, and makes its test deterministic. Distinct from production `DatabaseConnection.open`'s `busy_timeout = 5000`.
   - hollow schema: valid SQLite with no `nodes` table → SQLite code 1 `"no such table: nodes"`.
   - corrupt: 5000-row db, 8 KB of `0x5a` written at offset 4096 (header intact), then `SELECT COUNT(*)` → SQLite code 11 `"database disk image is malformed"`. Code 11 is therefore reproduced, not assumed.
   - unclassifiable (a): `chmod 000` on a healthy db → throws at `new DatabaseSync(...)` with `code=ERR_SQLITE_ERROR` SQLite code 14 `"unable to open database file"`.
   - unclassifiable (b): a **directory** at the db path → same SQLite code 14. Both carry a numeric SQLite code; the only shapes observed *without* one are programmer errors (`new DatabaseSync(12345)` → `code=ERR_INVALID_ARG_TYPE`, code field undefined), which is why the code-less arm is a defensive first check rather than the permissions case the round-2 review assumed.
   gate-waive: C6-FICTION — `ERR_SQLITE_ERROR` / `SQLITE_NOTADB` are `node:sqlite` runtime error identifiers captured in the probes above, not env vars this repo defines.
3. Claim "no existing test pins the current cwd-fallback behaviour":
   `grep -rn "isUnexpandedTemplatePath\|Falling back to the current directory\|workspaceFolder" codegraph/__tests__ codegraph/src` → the only test hits are the pure-predicate cases in `codegraph/__tests__/unsafe-index-root.test.ts:119` — quote: `expect(isUnexpandedTemplatePath('${workspaceFolder}')).toBe(true);` — nothing asserts the fallback.

**One contradiction looked for and not found**

Looked for a second writer of the `${workspaceFolder}` literal inside the fork that a hard refusal would break (i.e. codegraph generating a path it then rejects). `grep -rn "workspaceFolder" codegraph/src` returns exactly one generator — `codegraph/src/installer/targets/cursor.ts:173` — and it emits the literal **only** for the `global` install, which Cursor is expected to expand before launch. No self-inflicted refusal path found.

---

## Summary

Two user-visible CLI behaviours change in the local `codegraph/` fork, both in one surface (`codegraph/src/bin/codegraph.ts` plus a small helper in `codegraph/src/directory.ts`).

**(1) Unexpanded `${…}` is a hard error, not a warning.** Today `resolveProjectPath` prints a warning and then indexes/serves whatever index sits at or above the current directory — the exact path that produced the 9.6 GB `$HOME` index incident this fork exists for. After this change, any `--path` containing `${` — and `codegraph init`'s positional folder argument, which does not go through `resolveProjectPath` at all — prints an error naming the literal string, tells the operator to pass a real folder, and exits non-zero without touching the current directory. A bare `codegraph explore` with no path still uses cwd; nothing about the no-argument path changes.

**(2) `codegraph init` repairs a tree it already "owns".** Today `init` no-ops on any tree where `.codegraph/codegraph.db` merely *exists*. After this change `init` classifies the existing db as `usable` / `empty` / `unreadable` / `busy` / `unclassified`: `usable` keeps today's no-op, `empty` (0 nodes) re-indexes **in place** (same file, cleared and rebuilt), `unreadable` (SQLite errcode 26, 11 or 1 — junk bytes, malformed pages, or no `nodes` table) replaces **only** the `codegraph.db` file set and indexes, `busy` (errcode 5 — another process holds the lock) errors out and changes nothing, and `unclassified` (any other SQLite error, e.g. permissions or IO) also errors out and changes nothing rather than treating an unknown failure as junk. No `.codegraph/ready` stamp is introduced — "ready" stays "the index has nodes". The rest of `.codegraph/` (`.gitignore`, `daemon.log`, freshness/gate state, any lessons db) is never deleted.

Shipping also includes an ADR in the fork (grill lock 4-a), an amended local-patch row in `codegraph/UPDATING.md`, and the fork's mandatory `npm run build` + rsync deploy — without the deploy the change is dark on the live binary.

---

## Guardrail Checklist

No `docs/rules/` or `CONSTRAINTS.md` exists in this repo (dispatch: `constraints: (none in this repo)`), so the checklist is drawn from the two governing CLAUDE.md files and the grill locks.

| # | Guardrail | Source | Verdict for the chosen option |
|---|---|---|---|
| G1 | Never write to `.codegraph/codegraph.db` from piggyback tooling; connect `mode=ro` | repo `CLAUDE.md` → Critical Rules | n/a — this change lives inside the codegraph fork, which *owns* the db. No piggyback tool is touched. |
| G2 | `codegraph/` is a LOCAL FORK: never `npm install -g` / `codegraph upgrade`; update only per `codegraph/UPDATING.md` | repo `CLAUDE.md` → What AI Gets Wrong | satisfies — edit source, `npm run build`, rsync `dist/`, add a patch-table row. |
| G3 | Every local patch is listed in the `UPDATING.md` patch table and has a regression test | `codegraph/UPDATING.md:16` — quote: `## Local patches (base: upstream v1.0.1)` | satisfies — the `${…}` row is amended (warn → refuse), a new row is added for init-repair, tests land in `codegraph/__tests__/`. |
| G4 | Errors teach abandonment: recoverable states must not look like malfunctions to an agent | `codegraph/CLAUDE.md` → retrieval section | satisfies — the two new hard failures are **CLI** exits an operator sees, not MCP tool results. No MCP payload changes here (Bucket 5 owns that). |
| G5 | Any installer/`targets/` change needs test coverage + CHANGELOG | `codegraph/CLAUDE.md` → House rules | n/a — `codegraph/src/installer/` is not modified. |
| G6 | Contracts frozen by an earlier bucket are not reopenable | scope §7 | satisfies — Bucket 1's ACP absolute path and the Desktop `${workspaceFolder}` split are untouched. |
| G7 | Do not silently fold Bucket 5 (MCP) into this run | grill "Expert still doesn't like" | satisfies — `codegraph/src/mcp/**` is out of the file list. |
| G8 | Destructive ops need explicit justification | global contract §4 | the only deletion is the `codegraph.db` file set, and only after a positive `unreadable` classification; `busy` and every other state delete nothing. |

---

## Implications (code-verified)

**A. `--path` refusal has one chokepoint; `init` has a second door.**
`resolveProjectPath` is the single funnel for every `--path` / positional path in the CLI except `init` — `codegraph/src/bin/codegraph.ts:210` — quote: `  const absolutePath = path.resolve(pathArg || process.cwd());` — and it is called at 14 sites (`542, 605, 684, 746, 913, 989, 1107, 1172, 1437, 1507, 1544, 1623, 1701, 1808`).
`init` resolves its own argument instead — `codegraph/src/bin/codegraph.ts:468` — quote: `    const projectPath = path.resolve(pathArg || process.cwd());`.
So grill lock 1-a ("both doors") is not optional bookkeeping — a refusal placed only in `resolveProjectPath` leaves `codegraph init '${workspaceFolder}'` creating a `.codegraph/` in a directory literally named `${workspaceFolder}`.

**B. The current fallback is a warning, not a refusal.** The warning text itself:
`codegraph/src/bin/codegraph.ts:205` — quote: `Falling back to the current directory.`
The detector is a pure one-liner and stays untouched:
`codegraph/src/directory.ts:169` — quote: `return p.includes('${');`
Only the `${` form is detected; `$(cmd)` and `%VAR%` are deliberately out of scope (grill "Alternatives dropped").

**C. `serve --mcp` inherits the refusal, and that is the loud-failure case.**
`codegraph/src/bin/codegraph.ts:1437` — quote: `    const projectPath = options.path ? resolveProjectPath(options.path) : undefined;`
A refusal here means the MCP server process exits non-zero at startup instead of serving a borrowed index. stdout is the MCP protocol channel, so the message must go to stderr only.

**D. Cursor's global install is the one place codegraph itself emits the literal.**
`codegraph/src/installer/targets/cursor.ts:173` — quote: `  const pathArg = loc === 'local' ? process.cwd() : '${workspaceFolder}';`
Bucket 1 deliberately kept this. The refusal therefore converts "Cursor failed to expand" from a silent wrong-index into a startup failure — which is the locked intent (C1), not a regression.

**E. `isInitialized` is existence-only — this is the whole of ITEM-5.**
`codegraph/src/directory.ts:100` — quote: `  return fs.existsSync(dbPath);`
and the branch it gates:
`codegraph/src/bin/codegraph.ts:487` — quote: `Already initialized in `
A 0-node or unreadable db satisfies the existence check and short-circuits `init` to a no-op with **exit code 0**. The gated predicate itself:
`codegraph/src/directory.ts:93` — quote: `export function isInitialized(projectRoot: string): boolean {`
It has 10 callers (per the CodeGraph blast radius) including `codegraph/src/mcp/**`, so its semantics must NOT change here — Bucket 5 owns the MCP side.

**F. "Empty" already has a definition in this fork — reuse it, don't invent one.**
`codegraph/src/mcp/tools.ts:2273` — quote: `        if (cg.getStats().nodeCount === 0) {`
and `nodeCount` comes from a single aggregate query — `codegraph/src/db/queries.ts:1784` — quote: `        (SELECT COUNT(*) FROM nodes) AS node_count,`
Using `nodeCount === 0` for the CLI's `empty` keeps one definition of empty across CLI and MCP, which matters when Bucket 5 lands.

**G. The classification is decidable from the *thrown value* — not from an error code alone.** Two payload kinds carry the decision and the design says so up front: a numeric `errcode` for every arm except one, **plus a message substring for the errcode-1 arm only** (SQLITE_ERROR is SQLite's catch-all, so the code alone cannot separate "the index has no `nodes` table" from any other statement failure). Anything with no `errcode` at all is a third shape. "Code-first, message-gated at exactly one arm, total over thrown values" is the whole rule; no part of this design should be read as "dispatch on the code".

The **throw site also varies**, which is why the probe's `try` must wrap construction and statement alike. The adapter constructs lazily — `codegraph/src/db/sqlite-adapter.ts:56` — quote: `    this._db = new DatabaseSync(dbPath);` — so a *junk* file does not fail at construction; it fails at the first statement that reads the file header. A *permission-denied or directory-at-path* db fails at construction itself (errcode 14, recorded). Both are inside one `try`. `errcode` is a plain property on the thrown error on both the dev (v24.15.0) and bundled (v24.16.0) runtimes. Every arm below was **reproduced on the deployed runtime** `~/.codegraph/versions/v1.0.1/node` (v24.16.0); the recipes are in the Pre-dispatch audit and are what the tests re-run:

| Input state | errcode | message | classification |
|---|---|---|---|
| text file at `codegraph.db` | **26** | `file is not a database` | `unreadable` |
| valid header, page bytes smashed after byte 4096 | **11** | `database disk image is malformed` | `unreadable` |
| valid SQLite, no `nodes` table (foreign/hollow schema) | **1** | `no such table: nodes` | `unreadable` |
| valid SQLite, some *other* errcode-1 failure (message ≠ a missing core table) | 1 | e.g. `malformed database schema` | `unclassified` — refuse, never delete |
| non-WAL db, another process in `BEGIN EXCLUSIVE` (read blocked) | **5** | `database is locked` | `busy` |
| WAL db, another process writing | — | read succeeds | node count decides — but **not terminally**; a later repair write can still throw 5 |
| `chmod 000 codegraph.db` (permission denied) | **14** | `unable to open database file` | `unclassified` — refuse, never delete |
| `codegraph.db` is a **directory** (passes `existsSync`, so `isInitialized` says yes) | **14** | `unable to open database file` | `unclassified` — refuse, never delete |
| anything thrown with **no numeric `errcode`** (a Node `SystemError` / programmer error, not a SQLite fault) | — | — | `unclassified` — refuse, never delete |

Four consequences the earlier draft got wrong. Errcode **1** is a real arm, but a **generic** one — SQLite's catch-all — so it maps to `unreadable` **only** when the message says a core table is missing (`no such table: nodes`); any other code-1 failure is `unclassified`, because mapping SQLITE_ERROR wholesale onto the delete branch would let a future widening of the probe query silently widen the destruction. Errcode **11** is reproducible and therefore not a speculative branch. Permission/IO failures surface as errcode **14** thrown at **construction** — recorded on this runtime for both `chmod 000` and a directory sitting at the db path — so they are `unclassified`, never junk. And the catch must accept a throw with **no `errcode` at all** and still route it to `unclassified`: the dispatch is total over *thrown values*, not merely over the codes it enumerates.
gate-waive: C6-FICTION — those are SQLite/`node:sqlite` error identifiers from the recorded probes, not repo-defined env vars.

**H. Under WAL a reader probe survives a concurrent writer — but WAL is not guaranteed, so `busy` IS reachable from the probe.** The connection is configured WAL-first — `codegraph/src/db/index.ts:33` — quote: `  db.pragma('journal_mode = WAL');` — and the busy window is bounded at `codegraph/src/db/index.ts:31` — quote: `  db.pragma('busy_timeout = 5000');`. Probing a *WAL* db that a live writer holds returned the row count normally in the recorded probe — so on the common path `busy` surfaces on the repair's **write** step, not the probe.

WAL is not always in effect, and the fork already says so:
`codegraph/src/db/index.ts:145` — quote: `* filesystems without shared-memory support (some network/virtualized mounts,`
with the operator-visible consequence one line down:
`codegraph/src/db/index.ts:149` — quote: `* writer; anything else ⇒ they can. See issue #238.`
On such a tree the recorded probe shows a **read-only** `COUNT(*)` failing with SQLite code 5 while another process holds `BEGIN EXCLUSIVE`. So `busy` is genuinely observable by the probe (non-WAL trees) **and** by the repair's writes (WAL trees). It stays in the probe's return union because the probe can in fact produce it, and errcode 5 is additionally mapped to the same refusal at every write step of the repair. This is also what makes the `busy` test deterministic to construct rather than a race: build the fixture non-WAL, hold an exclusive transaction, probe.

**I. `DatabaseConnection.open` is not a side-effect-free probe.** It applies the full pragma set and then runs migrations — `codegraph/src/db/index.ts:112` — quote: `      runMigrations(db, currentVersion);`. Migrations are writes. A health probe must therefore use its own minimal connection (`busy_timeout` + one `SELECT`), not `DatabaseConnection.open`, or classification itself mutates the file it is judging and can fail busy for the wrong reason.

**J. The re-init path is blocked by design and must be unblocked by removing the file, not by flags.**
`codegraph/src/index.ts:242` — quote: `CodeGraph already initialized in `
with the same guard one level down:
`codegraph/src/directory.ts:295` — quote: `if (fs.existsSync(dbPath)) {`
So the `unreadable` repair is exactly "unlink the db file set, then take the normal fresh-init path". The `empty` repair does not need that — it can open the existing (structurally fine) db and full-rebuild it the way `index` does — `codegraph/src/bin/codegraph.ts:643` — quote: `      cg.clear();`.

**K. WAL sidecars are part of the db, not decoration.** The live `.codegraph/` carries `codegraph.db`, `codegraph.db-shm`, `codegraph.db-wal` (`ls -a .codegraph` on this repo, alongside `.gitignore`, `daemon.log`, `daemon.pid`, `daemon.sock`, `.freshness-verdict.json`, `.gate_shown`, `.gate_edited`, `.last_graph_use`). Deleting `codegraph.db` while leaving a stale `-wal`/`-shm` next to a brand-new db is how a "repair" produces a second corrupt db. "Replace only `codegraph.db`" (lock 3-c) must be read as "the `codegraph.db` file set" — and everything else in `.codegraph/` stays, which is what the lock is actually protecting.

**L. Module depth / deletion test.**
- `resolveProjectPath` (`codegraph/src/bin/codegraph.ts:197` — quote: `function resolveProjectPath(pathArg?: string): string {`) is a **deep** helper: 14 callers, one small signature. Adding the refusal *inside* it deepens it further — every caller inherits the guard with zero call-site edits. Deleting it would push path-resolution + the guard into 14 places. It earns its keep.
- `init`'s action body is currently **shallow-ish and duplicated**: the index-run block at `codegraph/src/bin/codegraph.ts:506` — quote: `        result = await cg.indexAll({` — is a near-copy of the `index` command's at `codegraph/src/bin/codegraph.ts:648` — quote: `        result = await cg.indexAll({`. The repair paths would make three copies inside `init` alone; extracting a local `runInitialIndex(...)` collapses them to one (3 callers → passes the deletion test).
- The new health probe is a **new function, not a new module boundary**: it lives beside `isInitialized` in `codegraph/src/directory.ts`, has one caller today (`init`). It is **not exported** (LIGHT freeze: not a new multi-consumer API). Tests may import the module file directly. Bucket 5 / Bucket 6 keep their own enums; they are not told to start from this union.

**M. The fix is dark until it is deployed.** The patch table records today's behaviour:
`codegraph/UPDATING.md:22` — quote: `ignored with warning`
That row becomes wrong the moment this ships, and the live binary keeps the old behaviour until the deploy step:
`codegraph/UPDATING.md:55` — quote: `rsync -a --delete dist/ ~/.codegraph/versions/v1.0.1/lib/dist/`
The session's own deploy-drift banner is the standing reminder that source ≠ live here.

**N. Tests for this must be end-to-end against `dist/`.** The established pattern for CLI behaviour in this fork — `codegraph/__tests__/index-command.test.ts:23` — quote: `const BIN = path.resolve(__dirname, '../dist/bin/codegraph.js');` — so a new test file must run after `npm run build`, and a `process.exit(1)` inside the refusal is observable (exit code + stderr) rather than untestable.

---

## Surface-capability matrix

Every boundary hop this design asserts behaviour across:

| Surface / hop | Vendor-enforced? | Payload / channel | Operator surface |
|---|---|---|---|
| `codegraph <cmd> --path '${…}'` (CLI, interactive) | ours — commander action, we own the exit | stderr line naming the literal + non-zero exit | terminal; exit code visible to shells and CI |
| `codegraph init '${…}'` (positional) | ours — same process, separate resolve site (`codegraph/src/bin/codegraph.ts:468`) | same stderr shape via the shared guard | terminal |
| `codegraph serve --mcp --path '${…}'` (spawned by Cursor/Claude) | **the block is ours and is enforced** — we `exit` before any index is opened, so the process cannot serve a wrong index. **What is NOT vendor-enforced is the *surfacing*:** the host decides whether anyone ever reads our stderr | stderr only (stdout is the JSON-RPC channel); process exits non-zero before any `initialize` response | the host's MCP server list shows the server as failed; the text lands in the host's MCP log, not in the agent's transcript |
| `codegraph init` repair → SQLite file (`codegraph.db` + `-wal`/`-shm`) | **no** — SQLite/OS enforce locking, not us; under WAL a reader is not blocked by a writer, and WAL itself is not guaranteed (Implication H) | total dispatch over the caught value: no `errcode` ⇒ `unclassified`; `5` ⇒ `busy`; `26`/`11` ⇒ `unreadable`; `1` **with** a missing-core-table message ⇒ `unreadable`, otherwise `unclassified`; `14` and every other code ⇒ `unclassified`. No throw ⇒ the node count decides `empty`/`usable` — **and that verdict is not terminal**: on a WAL tree the probe reads straight through a live writer, so the repair's first write can still throw errcode 5 and reclassify the run to `busy` (which is why 5 is mapped at every write step, not only in the probe) | clack log lines + exit code |
| `writ-codegraph-init.sh` → `codegraph init` (Bucket 6 consumer) | **no** — a shell wrapper reading exit code + its own probe; codegraph emits no event/hook (that gap **is** TD-01) | process exit code only | writ deny copy — **unchanged in this bucket** |

Read the `serve --mcp` row carefully, because two different things are being scored in one column. **The fail-closed guarantee is ours and is not weakened by the "no":** the guard runs inside our process, before any index is opened, so a wrong index is never served — that is as enforced as rows 1–2. The "no" applies strictly to **delivery of the message**: no vendor contract guarantees an operator or agent ever sees the stderr line. So this design does not claim the refusal "alerts the agent" or "routes to the session"; it claims exactly one thing, and claims it strongly: the process does not serve a wrong index. Fail-closed ≠ fail-visible.

---

## Constraints

1. **One surface.** Only `codegraph/src/bin/codegraph.ts`, `codegraph/src/directory.ts`, `codegraph/__tests__/**`, `codegraph/UPDATING.md`, `codegraph/CHANGELOG.md`, and one new ADR file. `codegraph/src/mcp/**` (Bucket 5), `falkor-writ/**` (Bucket 6), `codegraph/src/installer/**`, and `agent_village/**` are out.
2. **No `.codegraph/ready` stamp** (grill lock, scope Q5-a). Ready = a db whose `nodes` count is > 0.
3. **No escape hatch for `${…}`** and no `$(` / `%VAR%` detection — the detector stays as it is at `codegraph/src/directory.ts:169` — quote: `return p.includes('${');`.
4. **Bare cwd still works.** `codegraph explore` / `init` with no path argument keeps resolving `process.cwd()` — `codegraph/src/bin/codegraph.ts:210` — quote: `path.resolve(pathArg || process.cwd());`. Only a *provided* path containing `${` is refused.
5. **`isInitialized` semantics are frozen** for this bucket — 21 call sites in `src/` (`bin/codegraph.ts` 15, `index.ts` 5, `directory.ts` 1). **Zero** direct calls from `src/mcp/**`; MCP couples through `findNearestCodeGraphRoot` → `isUsableRoot`. Making the predicate health-aware is Bucket 5's decision, not this one (`codegraph/src/directory.ts:93` — quote: `export function isInitialized(projectRoot: string): boolean {`).
6. **Never widen the deletion.** Only `codegraph.db` + its `-wal`/`-shm` sidecars, only on a positive `unreadable` classification (errcode 26, 11, or a **message-confirmed** missing-core-table errcode 1). `busy` and `unclassified` delete nothing (lock 3-c); an unrecognised failure, a permissions/CANTOPEN error (14), a bare errcode 1, and any throw without an `errcode` are never treated as junk. Everything else in `.codegraph/` survives, asserted by a before/after entry listing with per-file sha256.
7. **Schema-version disagreement is not this bucket's business.** A db that opens and answers a `nodes` count is not `unreadable` even if `schema_versions` holds a version this reader does not know (a db missing the `nodes` **table** is a different thing — errcode 1, `unreadable`); migrations already run on open — `codegraph/src/db/index.ts:111` — quote: `    if (currentVersion < CURRENT_SCHEMA_VERSION) {` — and the version enum belongs to writ's `probe()` (Bucket 6).
8. **Fork discipline.** Ship = source edit + `npm run build` + rsync — `codegraph/UPDATING.md:52` — quote: `npm test                        # or at least the suites touching your change` — plus a patch-table row. Never npm / `codegraph upgrade`.
9. **Exit codes are part of the contract:** refusal = non-zero; `busy` = non-zero; successful repair = 0; healthy no-op = 0 (unchanged).

---

## Alternatives Considered

### Option A — Guard inside `resolveProjectPath` + a health probe beside `isInitialized` (Recommended)

**Approach.** Add one shared guard and one health probe, then rewrite `init`'s already-initialized branch to dispatch on the probe.

1. `assertExpandedPath(pathArg, label)` — prints an error naming the literal string and the flag it came from, then exits non-zero. Called (a) at the top of `resolveProjectPath` (`codegraph/src/bin/codegraph.ts:197`), which covers all 14 `--path`/positional callers including `serve --mcp`, and (b) in `init`'s action before its own resolve (`codegraph/src/bin/codegraph.ts:468`). Two call sites = a real seam, not a speculative one.
2. `probeIndexHealth(projectRoot): 'usable' | 'empty' | 'unreadable' | 'busy' | 'unclassified'` in `codegraph/src/directory.ts`, beside `isInitialized`. **Unexported.** It opens a **readonly** `node:sqlite` connection itself — `new DatabaseSync(dbPath, { readOnly: true })` — then the `busy_timeout` pragma and a single `COUNT(*)` over `nodes`. Never `DatabaseConnection.open`, never `configureConnection`, never `createDatabase`, never `CodeGraph.open` (those migrate or WAL-write; `OpenOptions.readOnly` on `CodeGraph.open` is a dead field and still migrates). Never `PRAGMA journal_mode = WAL` in the probe (that pragma changes sha256 at constant size). Import `DatabaseSync` from `node:sqlite` in `directory.ts`; do **not** import `../db` (that is a cycle: `db/index.ts` already imports `directory.ts`). **All three steps sit inside one `try`, with a `finally` that closes a handle if one exists** (null-guard: ctor throw means nothing to close). A `try` that wraps only the query lets SQLite code 14 escape to the fatal handler as an unhandled rejection — the very path this design rejects for the `${…}` guard. Do not read assumption 13's "the constructor does not throw" as scoping: that is a statement about *junk files*, not about construction in general.

   It then dispatches **totally over whatever it catches** (Implication G's table), in this order:
   - a throw with **no numeric `errcode`** (Node `SystemError` / programmer error) ⇒ `unclassified` — this arm is checked *first*, because such a value has no code to dispatch on and must never reach the unlink path;
   - `errcode 5` ⇒ `busy`;
   - `errcode 26` or `11` ⇒ `unreadable`;
   - `errcode 1` **and** the message names a missing core table (`no such table: nodes`) ⇒ `unreadable`; **any other errcode 1** ⇒ `unclassified` (SQLITE_ERROR is a catch-all — it is not by itself evidence of junk);
   - any other errcode, including **14** (`unable to open database file` — permissions, or a directory at the db path) ⇒ `unclassified`;
   - no throw and count 0 ⇒ `empty`; count > 0 ⇒ `usable`.

   Every arm is producible by this probe on the deployed runtime and has a recorded fixture (Pre-dispatch audit claim 2), including `busy` (non-WAL tree) and `unclassified` (`chmod 000`, or a directory at `codegraph.db`). `unclassified` exists so the dispatch is total without a destructive default.
3. `init`'s already-initialized branch becomes: `usable` ⇒ today's warn + watch-fallback offer; `busy` ⇒ error naming the db path and the likely holder (`codegraph daemon` / MCP), exit non-zero, touch nothing; `unclassified` ⇒ error naming the raw SQLite code + message, exit non-zero, touch nothing; `empty` ⇒ open the **same** db file + `cg.clear()` + index (never unlink — the file identity must survive, see the contract's inode assertion); `unreadable` ⇒ unlink exactly `codegraph.db`, `codegraph.db-wal`, `codegraph.db-shm`, then the existing fresh-`init` path. Write-path dispatch is total and **never widens deletion**: SQLite code 5 during any repair write ⇒ same `busy` error, delete nothing; **any other write failure** (including `clear()` throwing `no such table: files` on a nodes-only db) ⇒ abort as `unclassified`, delete nothing. A catch-all “then unlink” is forbidden. A db with `nodes` and no `files` classifies as `empty` (COUNT works) and then dies on `clear()` — that is `unclassified`, not a back-door `unreadable`.
4. Extract the index-run block into a local `runInitialIndex(...)` so all three indexing paths share one implementation, one progress renderer, one result printer, one telemetry call, and one watch-fallback offer (`codegraph/src/bin/codegraph.ts:518` — quote: `      printIndexResult(clack, result, projectPath);`).

**Files touched.** `codegraph/src/bin/codegraph.ts` (guard call ×2, init branch, extracted helper) · `codegraph/src/directory.ts` (`probeIndexHealth`) · `codegraph/__tests__/unexpanded-path-refusal.test.ts` (new, E2E via `dist/`) · `codegraph/__tests__/index-command.test.ts` (add already-initialized-unusable cases) · `codegraph/UPDATING.md` (amend the `${…}` patch row, add an init-repair row) · `codegraph/CHANGELOG.md` · new ADR file in the fork.

**Cost.** dev: low-med (~35–45 lines production + ~80 lines tests) · runtime: a repair now spends a real index (seconds–minutes) where `init` used to return instantly; the probe adds one SQLite open + one COUNT · maintenance: one new **unexported** function with one caller (`init`).

**Risk.** Behavioural: `serve --mcp` now fails closed for unexpanded Desktop configs (intended, C1). Destructive: file deletion exists on one classified path — mitigated by never deleting on `busy`/`unclassified` and by deleting the sidecars together with the db.

**Module depth.** New boundaries: none (both additions are functions in existing modules). New interfaces: none — `probeIndexHealth` returns a string union and is not exported. Existing modules affected: `resolveProjectPath` (deep, deepened further — 14 callers inherit the guard); `init`'s action body (shallow + duplicated, deepened by the `runInitialIndex` extraction, 3 callers).

**What it defers.** MCP's view of missing/empty (Bucket 5) and writ's probe enum (Bucket 6) — they keep their own taxonomies; this bucket does not freeze a third. TD-01's native post-init hook/event stays deferred: this ships repair, not a lifecycle event.

**Constraints check.** [x] 1 one surface · [x] 2 no ready stamp · [x] 3 detector unchanged · [x] 4 bare cwd intact · [x] 5 `isInitialized` untouched · [x] 6 deletion narrow · [x] 7 schema version untouched · [x] 8 fork discipline (patch row + build/rsync in the plan) · [x] 9 exit codes explicit.

### Option B — Refuse only; `init` prints "run `codegraph index`" instead of repairing (Not recommended — conservative rung)

**Approach.** Ship the `${…}` refusal exactly as in Option A. For ITEM-5, keep `init` a no-op but detect the unusable db and print a loud, actionable error with a non-zero exit telling the operator to run `codegraph index`.

**Files touched.** `codegraph/src/bin/codegraph.ts` · `codegraph/src/directory.ts` (a probe is still needed to know *what* to print) · tests · `codegraph/UPDATING.md`.

**Cost.** dev: low (~20 lines) · runtime: none — no surprise indexing · maintenance: lowest.

**Risk.** Contract: it fails the locked promise. Scope §5 ITEM-5's promise is that `init` on a db-exists-but-empty/unusable tree **runs index**, and scope §8 ROI row 3 says the no-op "is why the named fix does nothing". A louder no-op still leaves writ's wrapper and every operator doing the second step by hand.

**Module depth.** Same probe, no `runInitialIndex` extraction (init keeps one indexing path). Passes the deletion test trivially because it deletes nothing — and repairs nothing.

**What it defers.** The entire repair duty, permanently, onto Bucket 6's wrapper and onto humans.

**Constraints check.** [x] 1–5, 7–9 · [x] 6 (never deletes) · ⚠️ violates locked requirement 2-a ("empty or unreadable → index").

### Option C — Make `isInitialized` health-aware globally (Not recommended — aggressive rung)

**Approach.** Change `isInitialized` from "db file exists" to "db exists and is usable" (`codegraph/src/directory.ts:100` — quote: `  return fs.existsSync(dbPath);`), so `init`, `index`, `uninit`, MCP session gating, and the walk-up all get the honest answer in one edit.

**Files touched.** `codegraph/src/directory.ts` and, by blast radius, its 10 callers across `codegraph/src/index.ts`, `codegraph/src/bin/codegraph.ts`, `codegraph/src/directory.ts`, plus MCP consumers.

**Cost.** dev: med-high · runtime: every walk-up call would open and query SQLite, and the walk runs on every MCP tool call — `codegraph/src/directory.ts:178` — quote: `// Warn once per unsafe root per process — the walk runs on every tool call.` · maintenance: high.

**Risk.** Contract + scope: this *is* Bucket 5's decision surface (scope §5 ITEM-1-cg names `isInitialized` / `findNearestCodeGraphRoot` explicitly in its IN list), so taking it here reopens a bucket boundary — a plan-compliance failure per the scope preamble, not a design choice. Performance: turns a cheap `existsSync` into a db open in a hot path. Correctness: `uninit` would refuse to clean up a broken tree because it no longer counts as initialized (`codegraph/src/bin/codegraph.ts:545` — quote: `      if (!isInitialized(projectPath)) {`).

**Module depth.** Deepens one function but couples MCP gating to db health mid-program; the interface it changes has 10 adapters that did not ask for the change.

**What it defers.** Nothing — it *pulls forward* Bucket 5 work, which is exactly what the grill forbids ("Do not silently fold Bucket 5 into this run").

**Constraints check.** ⚠️ violates 1 (one surface) and 5 (`isInitialized` frozen); satisfies the rest.

**Rejected alternatives** (not viable, one line each):

- **Scope the refusal to `serve` only** — leaves the `codegraph init '${workspaceFolder}'` door open (grill "Alternatives dropped"; the scope freeze says all callers).
- **Also catch `$(` / `%VAR%`** — the freeze is `${` only.
- **`.codegraph/ready` stamp file** — a second source of truth next to the probe (scope Q5-a).
- **Auto-`uninit` on unreadable (wipe all of `.codegraph/`)** — drops lessons/gate state the lock protects.
- **Wipe on any open failure including busy** — surprise rebuild of a healthy index a live MCP daemon holds.
- **Throw a typed error from `resolveProjectPath` and catch per command** — 14 call sites to edit for one message.
- **Let the refusal throw and rely on the fatal handler** — it reaches the operator as an unhandled-rejection line (`codegraph/src/bin/fatal-handler.ts:90` — quote: `  target.on('unhandledRejection', (reason: unknown) => {`), the exact path two production incidents scarred, and the message would not name `--path`.

> **Recommended: Option A.** It is the only option that satisfies both locked promises (refuse at both doors; `init` actually indexes an empty/junk tree) while keeping the blast radius inside one surface — the extra cost over Option B is one probe function and one extracted helper, and the extra cost over Option C is nothing, because Option C's "savings" are Bucket 5's contract.

---

## Chosen Approach

**Option A.** Refuse unexpanded `${…}` in a shared guard called from both `resolveProjectPath` and `init`'s own resolve; classify an already-initialized tree with a minimal-connection health probe; repair `empty` by clearing + re-indexing in place, repair `unreadable` by replacing the `codegraph.db` file set and taking the fresh-init path; refuse to touch anything when the db is `busy`.

**Behaviour contract (this is what "done" means — verified by tests, not by prose):**

Each row's **Done assertion** is the invariant itself, not an observable that stands in for it. Exit code and stderr are *necessary but never sufficient* — every mutation claim is asserted against the filesystem before and after the run.

**"Unchanged" means the bytes, never the metadata.** The shared snapshot helper records, for a directory: the sorted entry-name list, and per entry a record built by `lstat` first, then content:

| Entry kind | Recorded | Why not sha256 |
|---|---|---|
| readable regular file | `{kind:'file', ino, sha256}` | — |
| **unreadable** regular file (the `chmod 000` fixture) | `{kind:'file', ino, hash:'<unreadable>'}` — an explicit sentinel, recorded **after** an `fs.access(R_OK)` check, never a silent skip | a file the process cannot read cannot be hashed; the fixture that makes the arm reachable is exactly the file that defeats a hash-everything helper (round-3 F2) |
| directory (incl. the directory-at-db-path fixture) | `{kind:'dir', ino}` | a directory has no contents hash; recording it as a *kind* is what makes "`codegraph.db` turned into a directory" visible instead of crashing the helper |
| symlink | `{kind:'symlink', ino, target}` from `readlink` | hashing through the link would report the *target's* bytes and miss a swapped link |
| missing after the run | absent from the entry list | the vanished-names predicate is what the `unreadable` row asserts |

Comparison is on that structure, so "unchanged" holds for unreadable and non-file entries too — the sentinel changes if the entry's kind, identity, or readability changes, which is the mutation class those rows care about. Size + mtime are deliberately NOT the comparison basis — a same-size write inside a one-second mtime window is exactly the mutation these rows exist to catch, and on a coarse-granularity filesystem it would pass a metadata compare unnoticed. Inode is recorded *in addition*, because file identity (did this file get replaced?) is a different question from file content (did these bytes change?) and the `empty` row turns on the former.

**The helper is a real function, not an oracle the implementer can shape.** It is written in the test file itself, over `node:fs` and `node:crypto` against the real temp directory — no wrapper around production code, no stub, no injectable comparator, nothing the implementation under test can influence. Its own unit test must include a **known-answer case** whose expected digest is produced **outside the helper** — `shasum -a 256` (or `openssl dgst -sha256`) of a **committed** fixture file, hex pasted as a literal — plus mutate-a-byte / add-an-entry / replace-file-with-symlink / make-file-unreadable cases. The helper under test must match that pasted literal. Do **not** compute the expected digest by calling the helper (a helper that always returns `''` would then green itself). Only an external-oracle literal catches a self-consistent but wrong helper.

| Input | Exit | Effect | Done assertion (the invariant, not its proxy) |
|---|---|---|---|
| `--path '${workspaceFolder}'` (any command routed through `resolveProjectPath`) | non-zero | stderr names the literal `${workspaceFolder}`; **cwd is not used**; no index is opened or created | snapshot cwd's `.codegraph/` (entry-name list + **sha256 per file**) before and after → identical; `readdirSync(cwd)` contains **no entry named `${workspaceFolder}`**; if cwd had no `.codegraph/`, none exists after; plus exit ≠ 0 and stderr contains the literal |
| `codegraph init '${workspaceFolder}'` | non-zero | same message; no `.codegraph/` created anywhere | same snapshot pair on cwd, **plus** `existsSync('${workspaceFolder}')` is false in cwd and in the temp root — the literal-named-directory hazard (Implication A) is asserted directly, not inferred from the exit code |
| `codegraph explore` (no path) | unchanged | resolves `process.cwd()` as today | a healthy indexed fixture still answers; regression only |
| `codegraph init <dir>` where the db has nodes > 0 | 0 | today's "Already initialized" no-op + watch-fallback offer | db file **inode unchanged and sha256 unchanged**; node count unchanged; no re-index ran (no index-result line) |
| `codegraph init <dir>` where the db has 0 nodes | 0 | opens, clears, full-indexes **in place** | **POSIX:** db file **inode is the same before and after** (this is what distinguishes the honest open+clear from a delete-and-reinit that would produce identical stdout). **win32:** inode is not the gate — `codegraph/src/db/index.ts:270` — quote: `  if (process.platform === 'win32') return null;` — `isReplacedOnDisk` (`:255`) already refuses to use inode there. The test spies that production never `unlink`s the db path, and the `.codegraph/` entry list is otherwise unchanged. **and the fixture's own source is in the graph** — see the repair-proof assertion below |
| `codegraph init <dir>` where the db is unreadable by SQLite (SQLite code 26, 11, or a missing-core-table code 1 — see Implication G) | 0 | deletes `codegraph.db` + `-wal` + `-shm` **only**, re-inits, full-indexes | **full before/after entry listing of `.codegraph/`**: (over-delete) the set of names that disappeared is a subset of `{codegraph.db, codegraph.db-wal, codegraph.db-shm}`, and every other entry is present after with an **unchanged sha256**; **(under-delete / stale-WAL)** for each of `-wal`/`-shm` that existed before, after the run that path is **absent or its sha256 ≠ the before-sha** (a leftover sidecar with identical bytes fails). Plant a leftover `-wal` in the junk fixture so unlink-db-only cannot green. Plus the repair-proof assertion below. Run the fixture once per junk shape: text file (26), page-smashed (11), no-`nodes`-table (1). |
| `codegraph init <dir>` where the db is locked (errcode 5) | non-zero | error naming the db path and that another process holds it; **no file deleted, no index run** | db file **sha256 and inode unchanged**; `.codegraph/` entry-name list and every file's sha256 unchanged; node count unchanged. Fixture is deterministic, not a race: non-WAL journal mode + a second process holding `BEGIN EXCLUSIVE` (Implication H) |
| `codegraph init <dir>` where the probe cannot classify the failure (`unclassified`) | non-zero | error naming the raw errcode + message; **no file deleted, no index run** | **no file deleted** (entry-name list identical; vanished-names empty). Per-entry compare uses the typed snapshot: readable files by sha256; the chmod-000 db by `{ino, hash:'<unreadable>'}` (do **not** require sha256 of an unreadable file); the directory-at-db-path fixture by `{kind:'dir', ino}`. **Two recorded fixtures, both reproduced on the deployed runtime:** (a) `chmod 000 .codegraph/codegraph.db` → errcode 14 `unable to open database file`; (b) `codegraph.db` created as a **directory** → same errcode 14 (it passes `existsSync`, so `isInitialized` is true and the branch is genuinely reachable). Restore the mode in the test's `afterEach` so the temp-dir cleanup can unlink. Primary fixture is (b) (platform-independent); (a) is `it.runIf` gated (not root, not win32). |

**Repair proof — the `empty` and `unreadable` rows assert the fixture's symbols, not a moved counter.** "Node count > 0" is a side-effect proxy: a single inserted row greens it without an index ever running over the repo (round-3 F1). Both repair rows instead assert, against the reopened db, that **named symbols from the fixture's own source resolved**:

- Every fixture symbol resolves by exact name — the lookup used is
  `codegraph/src/index.ts:825` — quote: `  getNodesByName(name: string): Node[] {`
  and the fixture whose symbols it must find is already in the suite:
  `codegraph/__tests__/index-command.test.ts:53` — quote: `export function greet(name: string) { return hello(name); }`
  So the assertion is: a lookup for each of `greet`, `hello` and `main` returns at least one node.
- The **cross-file call edge** survives, which extraction alone cannot fake — the edge exists only if resolution ran:
  `codegraph/src/index.ts:1000` — quote: `  getCallees(nodeId: string, maxDepth: number = 1): Array<{ node: Node; edge: Edge }> {`
  So the assertion is: `main`'s callees include `greet` (fixture `b.ts` imports `a.ts`), **and** the matching edge has `kind === 'calls'` (not `references` / `imports` / `instantiates` — `getCallees` conjoins those). Same-file `greet→hello` is optional extra, not the cross-file proof.
- Both fixture files appear in `files` (`a.ts` and `b.ts`), so a partial index over one file fails too.

(Both cited methods are the **test's** assertion surface, not a production mechanism this bucket changes — neither is called by the code under test. The C11 "name a production caller" prompt does not apply: what matters here is only that the lookup is exact-name rather than FTS-ranked, which the quoted signature and its docstring establish.)

The bar is explicit: **one dummy node inserted by hand must fail these assertions.** A counter cannot distinguish a real index from an `INSERT`; a resolved **cross-file** `calls` edge (`main→greet`) can. Same-file `greet→hello` is not that proof.

**Load-bearing must/never/only pairs (Step 3b co-satisfiability check).**

- *must* run index when `empty` **and** *never* re-index when healthy → satisfied by one predicate: node count `=== 0`. Single honest path.
- *must* replace the db when `unreadable` **and** *never* delete anything else in `.codegraph/` → satisfied: the unlink list is a literal three-element list (`codegraph.db`, `-wal`, `-shm`), not a directory walk.
- *must* replace when `unreadable` **and** *never* wipe when `busy` → these can only fight if a state is both. They cannot be: the classification is a **single total dispatch over the caught value** — one thrown thing, one arm (no `errcode` ⇒ `unclassified` · `5` ⇒ `busy` · `26`/`11` ⇒ `unreadable` · `1` ⇒ `unreadable` only when the message names a missing core table, else `unclassified` · every other code ⇒ `unclassified`), so `busy` and `unreadable` are disjoint by construction and nothing falls through. The delete is additionally guarded three ways: **unlink only after a positive `unreadable` classification** (never as a default for a failure the dispatch did not recognise), the destructive arm is reachable only from a *specific* signature rather than from SQLite's catch-all code, and any errcode 5 raised *during* the repair's writes aborts into the busy error instead of continuing.
- *must* re-index when `empty` **and** *never* replace the file when `empty` → satisfied by opening the existing db and calling `cg.clear()`; the contract asserts the db's **inode is unchanged**, which is the only observable that separates this from a delete-and-reinit with identical stdout.
- *must* exit non-zero on `${…}` **and** *must* keep bare-cwd behaviour → satisfied: the guard runs only when the path argument is present.
- *only* the `codegraph/` fork changes **and** *must* leave writ's deny copy honest → satisfied because writ reads exit code + its own probe; no writ file is edited and no writ contract is asserted here (Bucket 6).

No residual unsatisfiable pair; nothing is promoted to an Open Question on this axis.

**Ship checklist (grill lock 4-a + fork discipline):**
1. ADR in the fork — `codegraph/docs/adr/0001-init-repairs-unusable-index.md` (new directory; mirrors this repo's existing `<tool>/adrs/NNNN-slug.md` convention, e.g. `ssot-diagram/adrs/0001-reuse-p1-recipe-by-sibling-import-defer-shared-to-phase-b.md`). Content: why `init` stopped being mkdir-only, why repair beats a `ready` stamp, why `busy` is not a wipe.
2. `codegraph/UPDATING.md` — amend the `${…}` row (`:22`) from "ignored with warning" to "refused (non-zero exit)", and add a row for init-repair. That table is the fork's merge-survival contract.
3. `npm run build` + `npm test` (at minimum the new files plus `unsafe-index-root`, `index-command`, `foundation`, and an MCP smoke suite), then the rsync deploy, then `codegraph --version` must still print `999.0.0`.
4. `codegraph/CHANGELOG.md` under `## [Unreleased]`, user-facing wording per the fork's changelog rules.

---

## Mini-RT holds (2026-08-17)

Absorbed from `docs/AI_artifacts/7_reviews/2026-08-17-bkt4-codegraph-cli-mini-rt.md` (round 1), `…-mini-rt-2.md` (round 2) and `…-mini-rt-3.md` (round 3). Option A and every grill lock stand; these are the seven things the design now has to hold, each with the next silent failure it hands forward.

**Hold 1 — every Done cell asserts the invariant, not the observable, and "unchanged" means the bytes.** Exit code, stderr text and "Indexed N files" are entry conditions; the gate is a filesystem snapshot pair per row, compared on **entry names + per-file sha256** (never size+mtime, which a same-size write in the same mtime second defeats) plus **inode** where file identity is the claim: cwd `.codegraph/` unchanged and no `${workspaceFolder}` directory · db inode preserved on `empty` · vanished-names ⊆ the three-file set and every survivor's sha256 intact on `unreadable` · sha256 + inode + entry list untouched on `busy` and `unclassified`.
The helper's per-entry record is typed (readable file ⇒ sha256 · unreadable file ⇒ an explicit `'<unreadable>'` sentinel after an access check · directory · symlink target), it lives in the test file over `node:fs`/`node:crypto`, and its own unit test carries a **known-answer digest**.
*Successor premortem:* If this fix ships, the next thing that can silently fail is **the sentinel swallowing a real mutation**, because `'<unreadable>'` compares equal to itself no matter what the bytes underneath did. A repair that rewrote a `chmod 000` file's contents *and left it unreadable* is invisible to the comparison — the one file the fixture deliberately makes opaque is the one the snapshot can no longer speak for. The plan must therefore record `ino` alongside the sentinel (a rewrite-by-replace changes it) and, where the test can afford it, restore the mode at the end and hash once before cleanup.

**Hold 2 — `busy` is not a probe lie.** Kept in the union because it is *reproducible from the probe itself* on a non-WAL tree (recorded read-lock probe), not merely asserted; errcode 5 is additionally mapped to the same refusal at every write step of the repair, and the union grew a total-dispatch `unclassified` arm so no unrecognised error can fall into the destructive branch.
*Successor premortem:* If this fix ships, the next thing that can silently fail is **the WAL-tree write path**, because the deterministic `busy` fixture is non-WAL while every real user's tree is WAL. A green non-WAL probe test would let an implementation ship that handles errcode 5 in `probeIndexHealth` and nowhere else, so the WAL case — the common one — still dies mid-index. The plan must keep both fixtures, not the cheaper one.

**Hold 3 — the destructive arm is reached only by a specific signature, never by a catch-all.** Errcode 26 and 11 are junk signatures and were reproduced on the deployed runtime. Errcode **1 is SQLite's catch-all**, so it reaches `unreadable` **only** when the message names a missing core table (`no such table: nodes`); any other code-1 failure, errcode 14 (permissions / a directory at the db path), and any throw carrying no `errcode` at all go to `unclassified` and delete nothing. Both fall-throughs the round-2 review split apart are now separate rules, and the `errcode`-less case is checked first because it has no code to dispatch on.
*Successor premortem:* If this fix ships, the next thing that can silently fail is **the message match**, because `no such table: nodes` is a SQLite string this repo does not own. A SQLite upgrade that rewords it, or a localized build, flips every hollow db from `unreadable` to `unclassified` — `init` quietly stops repairing exactly the state ITEM-5 exists for, and stays exit-non-zero-but-safe, so no test that only checks "did not delete" would notice. The plan must assert the repair *happened* for the hollow-db fixture, not merely that nothing was destroyed.

**Hold 4 — the `serve --mcp` row's "no" is about surfacing, not about the block.** The guard runs in-process before any index is opened, so the fail-closed guarantee is as strong as rows 1–2; what no vendor enforces is whether anyone reads the stderr line. Fail-closed ≠ fail-visible, stated in the row itself rather than only in the prose beneath it.
*Successor premortem:* If this fix ships, the next thing that can silently fail is **operator diagnosis of a refused MCP server**, because it depends entirely on a host log the design does not control. A Cursor user whose Desktop config never expands sees a dead codegraph server and no message in the transcript, and may "fix" it by removing `--path` — trading a loud refusal for a silent cwd index again. Bucket 5's instructions payload is where that gets a visible surface; this bucket only guarantees the wrong index is not served.

**Hold 5 — `unclassified` has a fixture, so it cannot ship unexercised.** Two recipes, both reproduced on the deployed runtime and both landing on errcode 14 `unable to open database file`: `chmod 000` on `codegraph.db`, and `codegraph.db` created as a *directory* (which passes `existsSync`, so `isInitialized` returns true and the arm is genuinely reachable in production, not just in a test). Without a recipe this arm would have been round-1's "errcode 11 never verified" defect relocated onto the very arm invented to close it.
*Successor premortem:* If this fix ships, the next thing that can silently fail is **the fixture itself on another platform or user**, because `chmod 000` does not deny **root**, and Windows ignores POSIX modes entirely. In CI-as-root or on the fork's Windows VM the file stays readable, the probe returns `usable`/`empty`, and the test greens while asserting nothing about `unclassified`. The plan must gate that fixture (`it.runIf(process.platform !== 'win32' && process.getuid?.() !== 0)`) and keep the directory-at-db-path recipe, which is platform- and privilege-independent, as the primary one.

**Hold 6 — a repair is proved by the fixture's own symbols, never by a counter.** `empty` and `unreadable` assert that `greet`, `hello` and `main` resolve by exact name, that **`main`'s callees include `greet` with `edge.kind === 'calls'`** (the actual cross-file edge: `b.ts` → `a.ts`), and that both fixture files are in `files`. Same-file `greet→hello` is not the proof. One hand-inserted dummy node must fail these — which is the whole point, since it would pass "node count > 0".
*Successor premortem:* If this fix ships, the next thing that can silently fail is **the assertion drifting from the fixture**, because the symbol names are duplicated between the fixture source and the expectations. Someone editing the temp-repo source (renaming `greet`, adding a third file) leaves assertions that still pass against stale names as long as *some* index ran, and the sharpness quietly degrades back to a counter. The plan should derive the expected names from the same constant the fixture is written from, so a rename breaks the test loudly instead of weakening it.

**Hold 7 — the probe's `try` covers construction, not just the query, and `finally` closes.** `new DatabaseSync(dbPath, { readOnly: true })`, the `busy_timeout` pragma and the `COUNT(*)` are all inside one `try`, because SQLite code 14 is thrown *at construction* while code 26 is thrown at the first statement. A `finally` with a null-guard closes a handle if one exists (Option A step 2). Assumption 13's "the constructor does not throw" is scoped to junk files.

---

## Risks

| # | Risk | Mitigation / what later stages must watch |
|---|---|---|
| R1 | Cursor Desktop global installs (`codegraph/src/installer/targets/cursor.ts:173`) that fail to expand now get a **dead MCP server** instead of a wrong index. | Intended per lock C1. The stderr text must name the literal and say "set `--path` to an absolute folder in your MCP config" so the log is self-diagnosing. Bucket 1 already fixed the ACP seat, so the blast radius is Desktop-only. If this bites often, the follow-up is an installer change (a different bucket), not a softening here. |
| R2 | Exiting from inside a shared guard is not unit-testable in-process. | Test E2E against the built binary (`codegraph/__tests__/index-command.test.ts:23` pattern). Exit code + stderr are the *entry* assertions only — the row's Done assertion (cwd `.codegraph/` snapshot identical, no `${workspaceFolder}` directory) is what actually gates it, because a guard that prints and exits after already touching cwd must fail. Requires `npm run build` before the suite. |
| R3 | Deleting `codegraph.db` while leaving stale `-wal`/`-shm` produces a *second* broken db — and the mirror risk, an over-delete that wipes the whole `.codegraph/`. | Unlink the three-file set together. Gate both directions: vanished-names ⊆ the three-file set (over-delete), **and** each pre-existing sidecar is absent-or-different-sha after (under-delete). A vanished-names-only gate greens unlink-db-only. "No sidecars remain" alone would also pass `rm -rf` of the directory — the rejected auto-uninit — so the listing plus the sidecar-sha clause together are the gate. |
| R4 | A live MCP daemon holds the old inode when the file is replaced (#925). | The fork already heals this — `codegraph/src/index.ts:207` — quote: `    if (!this.db.isReplacedOnDisk()) return false;`. Repair must not attempt to kill daemons; if the write path hits errcode 5, abort with the busy error. |
| R5 | On a WAL tree the probe reads straight through a concurrent writer (Implication H), so a locked db can instead fail mid-index during the repair's writes. | Map errcode 5 to the same "another process holds the index" refusal at *every* write step of the repair, not only in the probe. The probe's own `busy` arm is exercised deterministically on a **non-WAL** fixture (recorded probe), and a WAL concurrent-writer case covers the write-step path — both, not one. |
| R6 | The change stays dark on the live binary (source ≠ deployed — the session's own drift banner). | Build + rsync is step 3 of the ship checklist and must be part of the plan's Done criteria, with `codegraph --version` = `999.0.0` and a live `codegraph init` run against a hollowed temp repo as the acceptance check. |
| R7 | Repair paths silently skip telemetry / watch-fallback / result printing that the fresh-init path performs. | The `runInitialIndex` extraction exists precisely to prevent three divergent copies; review must confirm all three paths call it. |
| R8 | An unusable-but-*intentional* db (e.g. a stub file a user dropped in on purpose) gets rebuilt without asking. | `init` is an explicit operator action requesting an index, and the healthy case is still a no-op; the accepted risk is recorded in the grill ("Empty brand-new repo: second `init` may index again (cheap)"). |
| R9 | Bucket 5 later needs a *different* health taxonomy (`index_missing` / `index_empty`) and ends up with two vocabularies in one fork. | Keep `probeIndexHealth` **unexported** and CLI-local. Do not freeze a third enum for Buckets 5/6. The ADR records that those buckets own their own unions. |

---

## Open Questions

**OQ-1 — CLOSED (owner + RT M5).** `probeIndexHealth` lives in `codegraph/src/directory.ts`. Raw `node:sqlite` import. No `../db` import (cycle). No new `index-health.ts` (Constraint 1 file list). Unexported.

**OQ-2 — CLOSED (owner).** The `busy` error names `codegraph daemon` as the way to find the holder.

**OQ-3 — CLOSED (owner + RT M6).** No confirmation prompt. Grill lock 2-a is “runs index”; a TTY prompt hangs `writ-codegraph-init.sh`.

*(All three were owner-locked before RT; RT found the design still offered the rejected alts. Closed in the artifact so an implementer cannot pick them.)*

---

## ADR references

- **New (this bucket, grill lock 4-a):** `codegraph/docs/adr/0001-init-repairs-unusable-index.md` — `codegraph init` repairs hollow/junk trees instead of being mkdir-only; ready = a populated index, not a stamp file; `busy` ≠ wipe. All three ADR gates hold: hard to reverse (operators and writ will depend on init repairing), surprising without context (init used to be a pure no-op), and the result of a real trade-off (repair vs stamp vs wrapper-only).
- **Related, not amended here:** `ssot-diagram/adrs/0001-reuse-p1-recipe-by-sibling-import-defer-shared-to-phase-b.md` (naming convention only) and TD-01 in `docs/TECH_DEBT.md` — TD-01 stays OPEN; this bucket ships the repair half, not the lifecycle event.

---

## Options explored

- **Option A — shared guard + health probe (CHOSEN).** Satisfies both locked promises inside one surface.
- **Option B — refuse only, loud no-op for init.** Viable and cheapest, not selected: it fails locked requirement 2-a and leaves the "init doesn't fix it" complaint intact.
- **Option C — health-aware `isInitialized`.** Viable in the abstract, not selected: it reopens Bucket 5's frozen IN list and puts a db open in the per-tool-call walk-up path.
- **Rejected (not viable):** serve-only refusal · `$(` / `%VAR%` detection · `.codegraph/ready` stamp · auto-`uninit` wipe · wipe-on-busy · typed error caught at 14 sites · throw-and-let-the-fatal-handler-print.

---

## Read-set

Files and line ranges surveyed this session (the spec warm-starts here):

- `codegraph/src/bin/codegraph.ts:150-270` (chalk helpers, telemetry hook, `resolveProjectPath`), `:284-308` (`success`/`error`/`info`/`warn`), `:440-660` (`init`, `uninit`, `index` commands), `:1425-1460` (`serve --mcp`)
- `codegraph/src/directory.ts:82-210` (`getCodeGraphDir`, `isInitialized`, `unsafeIndexRootReason`, `isUnexpandedTemplatePath`, `allowUnsafeRoot`, `isUsableRoot`), `:289-320` (`createDirectory`, `removeDirectory`), `:426-458` (`validateDirectory`)
- `codegraph/src/index.ts:200-360` (`reopenIfReplaced`, `init`, `initSync`, `open`, `openSync`, `isInitialized`), `:762-782` (`getStats`)
- `codegraph/src/db/index.ts:1-140` (`configureConnection`, `DatabaseConnection.initialize`, `.open`), `:141-190` (`getJournalMode`, `getSchemaVersion`, `getSize`)
- `codegraph/src/db/sqlite-adapter.ts:40-149` (`NodeSqliteAdapter`, `createDatabase`)
- `codegraph/src/db/queries.ts:1780-1824` (`getStats`)
- `codegraph/src/mcp/tools.ts:2265-2287` (empty-index warning / node count)
- `codegraph/src/installer/targets/cursor.ts:168-175` (`buildCursorMcpConfig`)
- `codegraph/src/bin/fatal-handler.ts:1-93`
- `codegraph/__tests__/index-command.test.ts:1-107` · `codegraph/__tests__/unsafe-index-root.test.ts:117-124`
- `codegraph/UPDATING.md:1-88` · `codegraph/CLAUDE.md` (fork rules, house rules) · repo `CLAUDE.md`
- `docs/AI_artifacts/_handoff/2026-08-17-bkt4-codegraph-cli-grill.md` · `docs/AI_artifacts/_scope/2026-08-16-feedback-bugs-scope.md` · `docs/TECH_DEBT.md` · `.village/runs/2026-08-16-feedback-scope-scout/channel/SCOUT_DIGEST.md` (ITEM-2-cg, ITEM-5)

---

## Assumptions to verify

FLOOR for downstream verification — each is a checkable factual claim, not a risk.

1. **`init` does not route through `resolveProjectPath`.** `codegraph/src/bin/codegraph.ts:468` — quote: `    const projectPath = path.resolve(pathArg || process.cwd());` — if this is ever changed to call `resolveProjectPath`, the second guard call becomes redundant (harmless, but the plan should notice).
2. **The detector is `${`-only.** `codegraph/src/directory.ts:169` — quote: `return p.includes('${');` — the refusal inherits exactly this predicate; no widening.
3. **`isInitialized` is existence-only.** `codegraph/src/directory.ts:100` — quote: `  return fs.existsSync(dbPath);` — the whole ITEM-5 defect. Must still be true (unchanged) after this bucket.
4. **Empty is already defined by a zero node count in this fork.** `codegraph/src/mcp/tools.ts:2273` — quote: `        if (cg.getStats().nodeCount === 0) {` — the CLI must not invent a different threshold.
5. **That count is a plain `COUNT(*)` over `nodes`.** `codegraph/src/db/queries.ts:1784` — quote: `        (SELECT COUNT(*) FROM nodes) AS node_count,` — so a raw probe query is equivalent without loading grammars.
6. **Opening a db runs migrations (a write).** `codegraph/src/db/index.ts:112` — quote: `      runMigrations(db, currentVersion);` — hence the probe must use its own connection.
7. **WAL is requested on every connection.** `codegraph/src/db/index.ts:33` — quote: `  db.pragma('journal_mode = WAL');` — this is why a reader probe usually survives a concurrent writer, and why `busy` must also be handled on the write path.
8. **Re-init is blocked while the db file exists.** `codegraph/src/directory.ts:295` — quote: `if (fs.existsSync(dbPath)) {` — so the `unreadable` repair must unlink before re-initializing.
9. **`index` clears before rebuilding.** `codegraph/src/bin/codegraph.ts:643` — quote: `      cg.clear();` — the `empty` repair should reuse this shape rather than an incremental `sync`.
10. **Cursor global installs still emit the literal.** `codegraph/src/installer/targets/cursor.ts:173` — quote: `  const pathArg = loc === 'local' ? process.cwd() : '${workspaceFolder}';` — confirms the refusal's only in-fork trigger.
11. **CLI behaviour is tested against the built binary.** `codegraph/__tests__/index-command.test.ts:23` — quote: `const BIN = path.resolve(__dirname, '../dist/bin/codegraph.js');` — new tests need `npm run build` first.
12. **The patch table records the old warn-behaviour and must be amended.** `codegraph/UPDATING.md:22` — quote: `ignored with warning`.
13. **[ENV, verified by probe, not by file]** On the deployed runtime `~/.codegraph/versions/v1.0.1/node` (`v24.16.0`): junk file ⇒ SQLite code 26 at the first file-touching statement (the constructor does **not** throw **for this input** — read that as a fact about junk files only, never as "construction is safe"; code 14 below throws *at* construction, which is why the probe's `try` wraps it — Hold 7); write blocked by another process's `BEGIN EXCLUSIVE` ⇒ SQLite code 5; **read** blocked on a **non-WAL** db ⇒ SQLite code 5 (so the probe can observe `busy`); db with no `nodes` table ⇒ SQLite code 1 / "no such table: nodes"; db with smashed pages after the header ⇒ SQLite code 11 / "database disk image is malformed"; `chmod 000` db **and** a directory at the db path ⇒ SQLite code 14 / "unable to open database file", thrown at construction. The first two also hold on the dev `node` (`v24.15.0`). Re-run all seven on the machine that ships the change if the bundled node is ever swapped — the whole dispatch rests on these codes.
14. **The dispatch must stay total over thrown values, and the destructive arm must stay specific.** Only errcode `26`, `11`, and a **message-confirmed** missing-core-table errcode `1` reach `unreadable`. A bare errcode 1 (SQLITE_ERROR is a catch-all), errcode `14`, any other code, and any throw with no `errcode` at all land in `unclassified` and refuse. No unknown failure may reach the unlink path: a permissions or IO error is not a junk db, and treating it as one would delete a healthy index.
15. **`isInitialized` is satisfied by a directory at the db path.** `codegraph/src/directory.ts:100` — quote: `  return fs.existsSync(dbPath);` — `existsSync` is true for a directory, so "`codegraph.db` is a directory" is a reachable production state that the probe must classify (it does: errcode 14 ⇒ `unclassified`), not a contrived test-only input.

---

## Discoveries

None beyond what is already recorded in TD-01 and the grill. (No new constraint, tech-debt item, open question, or ADR was found that belongs outside this document.)
