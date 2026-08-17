# Factual Code Verification: Bucket 4 codegraph CLI
_Last updated: 2026-08-17_

Spec: `docs/AI_artifacts/4_specs/2026-08-17-bkt4-codegraph-cli.md`
Design: `docs/AI_artifacts/3_design/2026-08-17-bkt4-codegraph-cli.md`
Runtime probed: `~/.codegraph/versions/v1.0.1/node` **v24.16.0**; dev `node` **v24.15.0**; live `codegraph --version` **999.0.0**.
`node:sqlite` `DatabaseSync` `{ readOnly: true }` confirmed Node 24 docs (fetched 2026-08-17): https://nodejs.org/docs/latest-v24.x/api/sqlite.html

## Overview

CLI today: `resolveProjectPath` warns + cwd-falls-back on `${`; `init` positional **bypasses** that helper and `path.resolve`s; `isInitialized` is `existsSync` of the db path (true for a directory); already-initialized `init` warns + `return` (implicit exit 0). Empty/junk/busy classification does **not** exist.

Re-check 2026-08-17 (after spec patch): A13 and A19 now match live bundled Node **v24.16.0** — directory+`{readOnly:true}` ⇒ errcode **266**; nodes-only ⇒ probe COUNT=0 then `CodeGraph.open`/`runMigrations` ⇒ `no such table: unresolved_refs` errcode **1** (`clear()` never runs). No new invalidations. Ready for `/plan`.

Structural audit: pass.

## Key Components

| Symbol | Site | Role now |
|---|---|---|
| `resolveProjectPath` | `codegraph/src/bin/codegraph.ts:197-218` | warn + `pathArg=undefined` + `path.resolve(cwd)` + `findNearestCodeGraphRoot`. **14 callers**, none is `init`: `:542,605,684,746,913,989,1107,1172,1437,1507,1544,1623,1701,1808` |
| `init` action | `codegraph.ts:461-532` | own resolve `:468` `path.resolve(pathArg \|\| process.cwd())` **outside** `try` (`:473`). `clack.intro` also before `try`. Already-init `:486-494` warn + watch-fallback + `return` (exit 0). Catch `:528-530` `process.exit(1)` |
| `isUnexpandedTemplatePath` | `codegraph/src/directory.ts:168-170` | `return p.includes('${');` |
| `isInitialized` | `directory.ts:93-101` | dir exists + `existsSync(dbPath)` — **no** `isFile()`, **no** SQLite. 21 `src/` call sites (bin 15, `index.ts` 5, `directory.ts` 1). **0** in `src/mcp/**`. MCP couples via `isUsableRoot` `:198` → `findNearestCodeGraphRoot` `:209` |
| `createDirectory` | `directory.ts:289-305` | `existsSync(dbPath)` throws “already initialized” `:295-296` |
| `index` command | `codegraph.ts:598-674` | `cg.clear()` `:628` quiet / `:643` UI then `indexAll`. `printIndexResult` `:661` |
| `printIndexResult` | `codegraph.ts:323` | clack success/info; “Indexed N files” / “N nodes” |
| `runInitialIndex` | **absent** | extract target: init `:506-524` (`indexAll` + print + telemetry + watch-fallback) |
| `probeIndexHealth` | **absent** | specified unexported in `directory.ts` |
| `assertExpandedPath` | **absent** | specified local in `codegraph.ts` |
| `CodeGraph.open` | `codegraph/src/index.ts:292-319` | `isInitialized` → `validateDirectory` → `DatabaseConnection.open`. Reads `options.sync` only. `OpenOptions.readOnly` `:109` **never read** |
| `CodeGraph.getStats` | `index.ts:770-773` | spec inventory `:762` is **stale** (+8) |
| `CodeGraph.getNodesByName` | `index.ts:825-827` | exact-name |
| `CodeGraph.getCallees` | `index.ts:1000-1001` | → `GraphTraverser.getCallees` |
| `getCalleesRecursive` | `codegraph/src/graph/traversal.ts:289-318` | `getOutgoingEdges(..., ['calls','references','imports','instantiates'])` `:305` |
| `QueryBuilder.getStats` | `codegraph/src/db/queries.ts:1780-1823` | `(SELECT COUNT(*) FROM nodes) AS node_count` `:1784` |
| `QueryBuilder.clear` | `queries.ts:1861-1868` | `DELETE` unresolved_refs, edges, nodes, **files** |
| `configureConnection` | `codegraph/src/db/index.ts:30-37` | `busy_timeout=5000` then `journal_mode=WAL` `:33`. Imported by `initialize` + `open` |
| `DatabaseConnection.open` | `db/index.ts:98-115` | `createDatabase` → `configureConnection` → `runMigrations` if `currentVersion < 5` `:111-112` |
| `createDatabase` | `codegraph/src/db/sqlite-adapter.ts:137-148` | `new NodeSqliteAdapter` `:56` `new DatabaseSync(dbPath)` **no readOnly**; catch **wraps** into `new Error(...)` — **strips `errcode`** |
| `getCurrentVersion` / `runMigrations` | `codegraph/src/db/migrations.ts:83-123` | missing `schema_versions` → `0`; migrations 2–5 ALTER existing tables, **do not** apply `schema.sql` |
| `statInode` / `isReplacedOnDisk` | `db/index.ts:255-277` | win32 `statInode` **returns null** `:270` |
| `buildCursorMcpConfig` | `codegraph/src/installer/targets/cursor.ts:171-175` | global `'${workspaceFolder}'` `:173` |
| `installFatalHandlers` | `codegraph/src/bin/fatal-handler.ts:79-92` | `unhandledRejection` `:89` → stderr + `exit(1)` |
| `error` / `warn` helpers | `codegraph.ts:291-306` | `error` → `console.error`; **`warn`/`info`/`success` → `console.log` (stdout)** |
| CLI E2E BIN | `codegraph/__tests__/index-command.test.ts:23` | `../dist/bin/codegraph.js`; fixture `greet`/`hello`/`main` `:53-59` |
| detector tests | `codegraph/__tests__/unsafe-index-root.test.ts:117-125` | predicate only; **no** cwd-fallback / refusal E2E |
| patch table | `codegraph/UPDATING.md:22` | `Literal \${...} in --path ignored with warning` |
| ADR | `codegraph/docs/adr/` | **absent** (new dir). Naming precedent: `ssot-diagram/adrs/0001-….md` |
| `directory.ts` imports | `directory.ts:7-9` | `fs`/`os`/`path` only. `db/index.ts:12` `import { getCodeGraphDir } from '../directory'` — `../db` would cycle |

## How It Works

**`--path` / most positionals.** Caller → `resolveProjectPath` `:197`. If `pathArg && isUnexpandedTemplatePath(pathArg)` `:202` → `console.error` warn naming literal + “Falling back to the current directory.” `:203-206` → `pathArg = undefined` `:207` → `path.resolve(process.cwd())` `:210` → walk-up `findNearestCodeGraphRoot` `:214` (skips `$HOME` via `isUsableRoot`). **Does not exit.** `serve --mcp` `:1437` `options.path ? resolveProjectPath(options.path) : undefined` — unexpanded `--path` therefore **serves cwd’s index**. stdout is MCP; current warn is already stderr.

**Bare `explore`.** `.command('explore <query...>')` `:984`; `resolveProjectPath(options.path)` `:989`. No `--path` ⇒ `undefined` ⇒ cwd walk-up. Query token is required by commander; spec row “`codegraph explore` (no path)” means no `--path`, not zero args.

**`init [path]`.** Does **not** call `resolveProjectPath`. `:468` `path.resolve(pathArg \|\| process.cwd())` **before** `try`. `init '${workspaceFolder}'` resolves to `cwd/${workspaceFolder}` and will `CodeGraph.init` there. `unsafeIndexRootReason` then `isInitialized` `:486`. If db path exists → warn “Already initialized in” `:487` + `offerWatchFallback` + `return` **exit 0**. Else `CodeGraph.init` `:498` (`createDirectory` + `DatabaseConnection.initialize`) then duplicated `indexAll` block `:506-516` + `printIndexResult` `:518` + telemetry `:519` + watch-fallback `:521-524`. Failures in `try` → `process.exit(1)` `:530`. Unsafe-root uses `process.exitCode = 1; return` `:482-483` (different from `process.exit`).

**Empty/junk today.** Existence-only `isInitialized` `:100` is true for 0-node db, junk file, chmod-000 file, **and a directory at `codegraph.db`**. All take the exit-0 no-op.

**`index` rebuild.** `clear()` then `indexAll` (`:643-656`). `clear` → `DELETE FROM files` (`queries.ts:1867`).

**Open is a write.** `DatabaseConnection.open` always `configureConnection` (WAL pragma **changes sha256** — probed) and may `runMigrations`. `CodeGraph.open({ readOnly: true })` still migrates. `validateDirectory` may `ensureGitignore` write (`directory.ts:268-278`, called `:447`).

## Spec Verification

| ID | Spec claim | Verdict | Evidence |
|---|---|---|---|
| A1 | `init` does not call `resolveProjectPath`; `:468` own `path.resolve` | ✅ Validated | `codegraph.ts:468` vs callers list (init absent) |
| A2 | Detector is `` p.includes('${') `` only | ✅ Validated | `directory.ts:169`; tests `unsafe-index-root.test.ts:119` |
| A3 | `isInitialized` existence-only `existsSync(dbPath)` | ✅ Validated | `directory.ts:99-100`; no SQLite/count. Preceding dir check `:94-96` does not change db-path semantics |
| A4 | Empty = `nodeCount === 0` (MCP); CLI must not invent another threshold | ✅ Validated | `mcp/tools.ts:2273`; CLI has **no** empty check today |
| A5 | `nodeCount` is `COUNT(*) FROM nodes` | ✅ Validated | `queries.ts:1784` |
| A6 | `DatabaseConnection.open` runs migrations (a write) | ✅ Validated | `db/index.ts:111-112` `runMigrations`; also always WAL `:105→33`. Conditional on `currentVersion < 5`, but open is never a pure reader |
| A7 | WAL requested on every production connection | ✅ Validated | `configureConnection` `:33`; `initialize` `:77` and `open` `:105` |
| A8 | `createDirectory` blocks re-init while db exists | ✅ Validated | `directory.ts:295-296` |
| A9 | `index` `clear()`s before rebuild | ✅ Validated | `codegraph.ts:628,643`; comment `#874` `:638-642` |
| A10 | Cursor global still emits `'${workspaceFolder}'` | ✅ Validated | `cursor.ts:173` |
| A11 | CLI E2E spawns `dist/bin/codegraph.js` | ✅ Validated | `index-command.test.ts:23-31` `execFileSync(process.execPath, [BIN,…])` |
| A12 | Patch table still says `ignored with warning` | ✅ Validated | `UPDATING.md:22` |
| A13 | Specified probe `{ readOnly: true }`: junk COUNT ⇒ 26; chmod-000 ctor ⇒ **14**; directory@db-path ctor ⇒ **266** (`disk I/O error`), not 14. Writable ctor on directory still 14 (not the probe). | ✅ Resolved | Re-probe 2026-08-17 bundled v24.16.0: `readOnly` dir `{errcode:266,message:"disk I/O error"}`; writable dir `{errcode:14}`; chmod-000 `{errcode:14}`; junk ctor-ok then COUNT `{errcode:26}`. Spec A13/A15/component-3 Done pin 266 vs 14. `isInitialized` `directory.ts:100` `existsSync` true for dir. |
| A14 | Only 26/11/message-confirmed-1 unlink; 14/bare-1/no-code/other never unlink | ✅ Validated | Probe/unlink **absent** today (`:486-494` never deletes). 266 is “other” → unclassified under specified dispatch. `createDatabase` wrap (`sqlite-adapter.ts:140-147`) is why probe must not use it |
| A15 | `existsSync` true for directory ⇒ reachable `isInitialized`; probe must classify | ✅ Validated | Probe 2026-08-17: `existsSync(dir.db)===true`. Init would take already-init branch. Classification is **266 unclassified**, not 14 (see A13) |
| A16 | `getCallees` conjoins calls\|references\|imports\|instantiates; tests must filter `kind==='calls'` | ✅ Validated | `traversal.ts:305`. Live fixture after `codegraph init`: `main→greet` `kind:"calls"` (6 nodes / 8 edges) |
| A17 | `directory.ts` imports only fs/os/path; `../db` is a cycle | ✅ Validated | `directory.ts:7-9`; `db/index.ts:12` |
| A18 | `CodeGraph.open` always migrates; `options.readOnly` unread | ✅ Validated | `index.ts:108-109` field; `open` `:292-319` never reads it; `DatabaseConnection.open` `:309` |
| A19 | nodes-only: probe COUNT=0 (`empty`); `CodeGraph.open`/`runMigrations` throws `no such table: unresolved_refs` errcode 1; **`clear()` never runs** | ✅ Resolved | Re-probe: `{probe:ok,count:0}` then `{stage:open,message:"no such table: unresolved_refs",errcode:1}`. `migrations.ts:40` ALTER `unresolved_refs`; `getCurrentVersion` `:89-91` → 0; `DatabaseConnection.open` `:111-112` `runMigrations`; `queries.ts:1867` `DELETE FROM files` unreached. Spec component 5 empty arm + A19 match. |
| S1 | Assumptions falsifiable | ✅ Validated | each row has “what would prove it wrong” |
| S2 | Done-when observable | ✅ Validated | FS snapshot / inode / edge.kind, not test-proxy |
| S3 | Components independently testable | ✅ Validated | 1–4 have no later-component dep; 5 needs 2–4 (earlier) |
| S4 | No silent HOW deferrals | ✅ Validated | `busy_timeout` 500 vs 5000 is a **Decisions** entry (lean A / implement 500). Index-command reuse of helper is explicit optional, not a missing interface |
| S5 | Data model declared | ✅ Validated | probe union; snapshot record kinds |
| S6 | Dependency order acyclic | ✅ Validated | no cycle; implications map to components 1–9 |

## Edge Cases & Silent Failure Modes

1. **Directory@db-path + specified probe.** Writable/`new DatabaseSync(p)` ctor → errcode **14**. `{ readOnly: true }` → errcode **266** `disk I/O error`. Spec now pins 266 for (b), 14 for chmod-000 (a). Do not drop `readOnly`.
2. **`init` guard placement.** `:468` resolve and `clack.intro` sit **outside** `try` `:473`. A thrown guard → async action rejection → `fatal-handler.ts:89`. Must `console.error` + `process.exit(nonzero)` **before** `:468`, never throw. Do not use `warn()` helper (`:305` stdout).
3. **Busy `return` vs `exit`.** Already-init `:494` `return` ⇒ exit 0. Unsafe-root `:482` sets `exitCode=1` then `return`. Planner trap (6): `clack.log.error` + `return` on busy is still 0. Use `process.exit(nonzero)` (or `exitCode` + return) like `:530`.
4. **Write-path busy on WAL.** Probe read on WAL+EXCLUSIVE **succeeds** (0ms, count returned). Write INSERT with `busy_timeout=500` → errcode **5** at **545ms**. Non-WAL probe COUNT → errcode **5** at **548ms**. Both fixtures required (Hold 2).
5. **WAL pragma mutates bytes.** Probe `busy_timeout` + `COUNT(*)` **sha256 unchanged**. `journal_mode=WAL` **changes sha256** at constant-ish size. Probe must not call `configureConnection`.
6. **`createDatabase` strips errcode.** Ctor throw wrapped (`sqlite-adapter.ts:140-147`). Probe/write-path classification on 14/266 **cannot** use it. Statement-time 5/26/11/1 keep `errcode` if thrown after adapter construct.
7. **nodes-only schema (A19).** Probe `empty` (COUNT=0). Repair `CodeGraph.open` → `runMigrations` from version 0 → errcode 1 `no such table: unresolved_refs`. Spec now says `clear()` never runs; write-path unclassified; **must not** map any `no such table:*` to unreadable unlink.
8. **`ensureGitignore` on empty repair.** `CodeGraph.open` → `validateDirectory` `:302` may create/upgrade `.gitignore`. Empty Done “entry list otherwise unchanged” is unsatisfiable unless fixtures plant a current gitignore (or snapshot excludes it).
9. **`CODEGRAPH_DIR`.** Db dir is not always `.codegraph/` (`directory.ts:17-27`). Unlink list must go through `getCodeGraphDir` + `codegraph.db{-wal,-shm}`, not a hardcoded `.codegraph/` walk.
10. **`serve --mcp` no `--path`.** `:1437` leaves `projectPath` undefined — unchanged; refusal only when `--path` is present and contains `${`.
11. **Fixture proof.** Same constants as `index-command.test.ts:53-59` produce cross-file `main→greet` `calls` after live `init`. Same-file `greet→hello` is extra, not the proof.

## Dependencies & Coupling

- `directory.ts` ← `db/index.ts:12` (`getCodeGraphDir`). Probe **must** `import { DatabaseSync } from 'node:sqlite'` (or `require`, matching `sqlite-adapter.ts:55`) — **not** `../db`.
- `isInitialized` frozen: 21 call sites; MCP uses `isUsableRoot` only. Do not health-ify.
- `init` / `index` share near-copy `indexAll`+print+telemetry+watch. Third copy inside `init` for repair would drift (R7). `index --quiet` `:625-632` skips print/telemetry — helper is for **init’s three** paths, not necessarily quiet-index.
- `uninit` TTY confirm `codegraph.ts:550-565` — **do not copy**.
- Installer `cursor.ts` OUT. Fatal-handler OUT except “don’t throw”.
- Tests: spawn `dist/` after `npm run build`. `codegraph/node_modules/@types/node` not present in this worktree until install; `tsconfig` `skipLibCheck: true`, `@types/node` `^20.19.30` in `package.json` — `node:sqlite` types may be missing; adapter already `require`s for that reason.
- Ship: `UPDATING.md:55` rsync `dist/` → `~/.codegraph/versions/v1.0.1/lib/dist/`. Version pin 999.0.0 lives **outside** `dist/`.

## Extension Points

- `resolveProjectPath` is the `--path` chokepoint (14 callers, zero call-site edits for door A). Door B is `init` `:468` — **not** inherited.
- Probe unexported: Buckets 5/6 keep own unions. Tests may `import` the module file.
- `runInitialIndex` local in `codegraph.ts` — do not new-file (`index-health.ts` forbidden, Constraint 1).
- `OpenOptions.readOnly` is a trap, not an extension: dead field, still migrates.

## Open Questions

- **OQ-4 (human-authority, still OPEN):** probe `busy_timeout` 500 vs 5000. Spec: implement **500** unless owner closes otherwise. This pass: non-WAL exclusive COUNT with 500 → errcode 5 at **548ms**; WAL write with 500 → 5 at **545ms**. Matches design’s ~546ms. OQ-1/2/3 CLOSED — do not reopen.
- Bundled node still v24.16.0 — A13 recipes re-checked this pass (directory+readOnly **266**, chmod-000 **14**, junk COUNT **26**). Re-run if the bundle node is swapped.

## Technical Debt Spotted

- **TD-01** remains OPEN (`docs/TECH_DEBT.md`). This bucket ships repair, not a post-init event. Spec agrees.
- `OpenOptions.readOnly` dead (`index.ts:109`) — pre-existing; do not use it as the probe.
- `warn()`/`info()` stdout vs MCP stdout — pre-existing; refusal must keep `console.error`.

## Update — 2026-08-17

### Re-check: all assumptions resolved

Re-check mode — prior ❌ A13/A19 vs patched spec + live bundled `~/.codegraph/versions/v1.0.1/node` v24.16.0. Skip Step 3. Full scan: A1–A12, A14–A18, S1–S6 unchanged ✅; A14/A15 spec text now names 266 and still matches code (`existsSync` + unclassified-via-other). No new invalidations.

| ID | Was | Now | Evidence |
|---|---|---|---|
| A13 | ❌ Invalidated (directory+readOnly claimed 14, live 266) | ✅ Resolved | Spec A13/component-3 Done/unclassified fixtures pin **266** for directory+`{readOnly:true}`, **14** for chmod-000. Re-probe: readOnly dir `errcode:266` `disk I/O error`; writable dir `errcode:14`; chmod-000 `errcode:14`; junk COUNT `errcode:26`. `directory.ts:100` `existsSync`. |
| A19 | ❌ Invalidated (claimed `clear()` / `no such table: files`) | ✅ Resolved | Spec A19 + component 5 empty arm: COUNT=0 then **`CodeGraph.open`/`runMigrations`** `no such table: unresolved_refs` errcode 1; **`clear()` never runs**. Re-probe: `{count:0}` then `{stage:open,errcode:1,message:"no such table: unresolved_refs"}`. `migrations.ts:40`; `db/index.ts:111-112`; `queries.ts:1867` unreached. |

All assumptions validated. Ready for /plan 2026-08-17-bkt4-codegraph-cli.
