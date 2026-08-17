# Plan: Bucket 4 — codegraph CLI `${…}` refusal + `init` repair
_Last updated: 2026-08-17_
_Status: [ ] pending_

Spec: `docs/AI_artifacts/4_specs/2026-08-17-bkt4-codegraph-cli.md` (components 1–9). FCV: `docs/AI_artifacts/5_factual-code-verification/2026-08-17-bkt4-codegraph-cli.md` (A1–A19 resolved; no `## Invalidated Assumptions`). Design: `docs/AI_artifacts/3_design/2026-08-17-bkt4-codegraph-cli.md`. Do not re-litigate A13/A19.

gate-waive: C7-ARMDRIFT -- CLI probe union vs writ probe union (spec Bucket 6 contract; this plan ships CLI only)

## Analysis

This phase extends the local `codegraph/` fork CLI only (spec Constraint 1). Two seams already exist: `resolveProjectPath` is the `--path` chokepoint (14 callers, including `serve --mcp`); `init` does **not** use it and must get its own door. `isInitialized` stays `existsSync`. Beside that predicate, `init` will call a new `probeIndexHealth` that opens the db with raw `node:sqlite` `{ readOnly: true }` — never `../db` (cycle with `getCodeGraphDir`). Empty repair = `CodeGraph.open` + `cg.clear()` + extracted `runInitialIndex` on the **same** inode. Unreadable = unlink exactly three names via `getCodeGraphDir`, then the existing `CodeGraph.init` + `runInitialIndex` path. Busy/unclassified = stderr + non-zero, no unlink. `${…}` refusal = `console.error` + `process.exit(nonzero)` — never throw (fatal-handler `unhandledRejection`). Spec owns WHAT; this plan owns TDD order, exact signatures, and the two small HOW locks below (TypeScript cannot import a non-exported binding; `@types/node` 20 has no `node:sqlite` types).

**HOW lock A (Constraint 12 vs tests):** `export function probeIndexHealth` in `codegraph/src/directory.ts` so `__tests__` can `import { probeIndexHealth } from '../src/directory'` (same pattern as `isUnexpandedTemplatePath`). Do **not** add it to `codegraph/src/index.ts` barrel (`export { getCodeGraphDir, isInitialized, findNearestCodeGraphRoot, CODEGRAPH_DIR }`). Do **not** import it from `src/mcp/**`. ADR still records “not a public/MCP API”.

**HOW lock B (spec ESM import vs compile):** probe uses `const { DatabaseSync } = require('node:sqlite')` with `{ readOnly: true }` — copy the require form from `NodeSqliteAdapter`. Do not add/upgrade `@types/node`. Spec’s ESM import is the intent (raw `node:sqlite`, not `../db`); require is the compile-safe HOW.

**HOW lock C (unclassified needs errcode):** `probeIndexHealth` returns `{ status: 'usable'|'empty'|'unreadable'|'busy'|'unclassified'; errcode?: number; message?: string }` so CLI/tests can name raw 14/266/1. `status` **is** the spec’s string union. Do not export a second public API.

**HOW lock D:** `index` command keeps its own `clear()`+`indexAll` copy. Only the three **init** index paths call `runInitialIndex`.

**HOW lock E:** OQ-4 still OPEN → implement probe `PRAGMA busy_timeout = 500` (spec). Leave `configureConnection` at 5000.

## Facts (live-certified — do NOT re-derive)

- Detector is `${`-only — (`codegraph/src/directory.ts:169`) — quote: "`return p.includes('${');`"
- `isUnexpandedTemplatePath` is already imported by the CLI — (`codegraph/src/bin/codegraph.ts:29`) — quote: "`import { getCodeGraphDir, isInitialized, unsafeIndexRootReason, findNearestCodeGraphRoot, isUnexpandedTemplatePath } from '../directory';`"
- `resolveProjectPath` warns then cwd-falls-back — (`codegraph/src/bin/codegraph.ts:202-208`) — quote: "`if (pathArg && isUnexpandedTemplatePath(pathArg)) {`" / "`pathArg = undefined;`"
- Fallback string (must vanish) — (`codegraph/src/bin/codegraph.ts:204-205`) — quote: "`variable (the MCP host failed to substitute it). Falling back to the current directory.`"
- Bare cwd resolve — (`codegraph/src/bin/codegraph.ts:210`) — quote: "`const absolutePath = path.resolve(pathArg || process.cwd());`"
- `resolveProjectPath` callers (none is `init`): `:542,605,684,746,913,989,1107,1172,1437,1507,1544,1623,1701,1808` — (`codegraph/src/bin/codegraph.ts:1437`) — quote: "`const projectPath = options.path ? resolveProjectPath(options.path) : undefined;`"
- `explore` requires a query token; “no path” means no `--path` — (`codegraph/src/bin/codegraph.ts:984-989`) — quote: "`.command('explore <query...>')`" / "`const projectPath = resolveProjectPath(options.path);`"
- `init` uses its own resolve, not `resolveProjectPath` — (`codegraph/src/bin/codegraph.ts:468`) — quote: "`const projectPath = path.resolve(pathArg || process.cwd());`"
- That resolve sits **before** `try` — (`codegraph/src/bin/codegraph.ts:468-473`) — quote: "`const projectPath = path.resolve(pathArg || process.cwd());`" / "`try {`"
- Already-init branch is warn + `return` (implicit exit 0) — (`codegraph/src/bin/codegraph.ts:486-494`) — quote: "`if (isInitialized(projectPath)) {`" / "`clack.log.warn(\`Already initialized in ${projectPath}\`);`"
- Unsafe-root uses `exitCode = 1; return` (busy must not copy the implicit-0 `return`) — (`codegraph/src/bin/codegraph.ts:482-483`) — quote: "`process.exitCode = 1;`" / "`return;`"
- Init catch already `process.exit(1)` — (`codegraph/src/bin/codegraph.ts:530`) — quote: "`process.exit(1);`"
- Fresh-init index block to extract — (`codegraph/src/bin/codegraph.ts:506-524`) — quote: "`result = await cg.indexAll({`" / "`printIndexResult(clack, result, projectPath);`"
- `index` UI path `clear()` then `indexAll` — (`codegraph/src/bin/codegraph.ts:643-648`) — quote: "`cg.clear();`"
- `printIndexResult` exists — (`codegraph/src/bin/codegraph.ts:323`) — quote: "`function printIndexResult(clack: typeof import('@clack/prompts'), result: IndexResult, projectPath?: string): void {`"
- `warn`/`info` write **stdout** — (`codegraph/src/bin/codegraph.ts:298-306`) — quote: "`console.log(chalk.blue(getGlyphs().info) + ' ' + message);`" / "`console.log(chalk.yellow(getGlyphs().warn) + ' ' + message);`"
- `error()` writes stderr — (`codegraph/src/bin/codegraph.ts:291-292`) — quote: "`console.error(chalk.red(getGlyphs().err) + ' ' + message);`"
- Fatal handler scars thrown rejections — (`codegraph/src/bin/fatal-handler.ts:89-91`) — quote: "`target.on('unhandledRejection', (reason: unknown) => {`" / "`write(\`[CodeGraph] Unhandled rejection: ${describeFatal(reason)}\\n\`);`"
- `installFatalHandlers()` runs at CLI startup — (`codegraph/src/bin/codegraph.ts:97`) — quote: "`installFatalHandlers();`"
- `isInitialized` is existence-only — (`codegraph/src/directory.ts:99-100`) — quote: "`const dbPath = path.join(codegraphDir, 'codegraph.db');`" / "`return fs.existsSync(dbPath);`"
- `directory.ts` imports only fs/os/path — (`codegraph/src/directory.ts:7-9`) — quote: "`import * as fs from 'fs';`" / "`import * as os from 'os';`" / "`import * as path from 'path';`"
- `getCodeGraphDir` honors `CODEGRAPH_DIR` — (`codegraph/src/directory.ts:35-36`) — quote: "`export function codeGraphDirName(): string {`" / "`const raw = process.env.CODEGRAPH_DIR?.trim();`"
- `getCodeGraphDir` joins project + dir name — (`codegraph/src/directory.ts:85-86`) — quote: "`return path.join(projectRoot, codeGraphDirName());`"
- `createDirectory` throws while db exists — (`codegraph/src/directory.ts:295-296`) — quote: "`if (fs.existsSync(dbPath)) {`" / "`throw new Error(\`CodeGraph already initialized in ${projectRoot}\`);`"
- `ensureGitignore` may write on validate — (`codegraph/src/directory.ts:268-278`) — quote: "`function ensureGitignore(gitignorePath: string): boolean {`" / "`fs.writeFileSync(gitignorePath, GITIGNORE_CONTENT, 'utf-8');`"
- `db/index.ts` imports directory (probe `../db` would cycle) — (`codegraph/src/db/index.ts:12`) — quote: "`import { getCodeGraphDir } from '../directory';`"
- `configureConnection` sets 5000 then WAL — (`codegraph/src/db/index.ts:31-33`) — quote: "`db.pragma('busy_timeout = 5000');      // MUST be first — see above`" / "`db.pragma('journal_mode = WAL');       // node:sqlite supports WAL on every platform`"
- `DatabaseConnection.open` migrates — (`codegraph/src/db/index.ts:111-112`) — quote: "`if (currentVersion < CURRENT_SCHEMA_VERSION) {`" / "`runMigrations(db, currentVersion);`"
- `DATABASE_FILENAME` is `codegraph.db` — (`codegraph/src/db/index.ts:282`) — quote: "`export const DATABASE_FILENAME = 'codegraph.db';`"
- win32 `statInode` is null — (`codegraph/src/db/index.ts:270`) — quote: "`if (process.platform === 'win32') return null;`"
- `isReplacedOnDisk` uses that inode helper (empty Done: POSIX inode; win32 unlink-spy) — (`codegraph/src/db/index.ts:255`) — quote: "`isReplacedOnDisk(): boolean {`"
- Adapter ctor is writable `DatabaseSync` (no readOnly) — (`codegraph/src/db/sqlite-adapter.ts:55-56`) — quote: "`const { DatabaseSync } = require('node:sqlite');`" / "`this._db = new DatabaseSync(dbPath);`"
- `createDatabase` strips `errcode` — (`codegraph/src/db/sqlite-adapter.ts:141-147`) — quote: "`const msg = error instanceof Error ? error.message : String(error);`" / "`throw new Error(`"
- Empty = `COUNT(*) FROM nodes` — (`codegraph/src/db/queries.ts:1784`) — quote: "`(SELECT COUNT(*) FROM nodes) AS node_count,`"
- MCP empty threshold is `nodeCount === 0` — (`codegraph/src/mcp/tools.ts:2273`) — quote: "`if (cg.getStats().nodeCount === 0) {`"
- `QueryBuilder.clear` deletes `files` — (`codegraph/src/db/queries.ts:1867`) — quote: "`this.db.exec('DELETE FROM files');`"
- Missing `schema_versions` ⇒ version 0 — (`codegraph/src/db/migrations.ts:89-91`) — quote: "`} catch {`" / "`return 0;`"
- Migration v2 ALTERs `unresolved_refs` — (`codegraph/src/db/migrations.ts:40`) — quote: "`ALTER TABLE unresolved_refs ADD COLUMN file_path TEXT NOT NULL DEFAULT '';`"
- `CodeGraph.init` calls `createDirectory` then `DatabaseConnection.initialize` — (`codegraph/src/index.ts:246-250`) — quote: "`createDirectory(resolvedRoot);`" / "`const db = DatabaseConnection.initialize(dbPath);`"
- `CodeGraph.open` always `DatabaseConnection.open` — (`codegraph/src/index.ts:308-309`) — quote: "`const dbPath = getDatabasePath(resolvedRoot);`" / "`const db = DatabaseConnection.open(dbPath);`"
- `OpenOptions.readOnly` is dead — (`codegraph/src/index.ts:109`) — quote: "`readOnly?: boolean;`"
- Barrel does not export a probe — (`codegraph/src/index.ts:63-68`) — quote: "`getCodeGraphDir,`" / "`isInitialized,`"
- `getNodesByName` is exact-name — (`codegraph/src/index.ts:825-826`) — quote: "`getNodesByName(name: string): Node[] {`" / "`return this.queries.getNodesByName(name);`"
- `getCallees` delegates to traverser — (`codegraph/src/index.ts:1000-1001`) — quote: "`getCallees(nodeId: string, maxDepth: number = 1): Array<{ node: Node; edge: Edge }> {`" / "`return this.traverser.getCallees(nodeId, maxDepth);`"
- Traverser conjoins four edge kinds — (`codegraph/src/graph/traversal.ts:305`) — quote: "`const outgoingEdges = this.queries.getOutgoingEdges(nodeId, ['calls', 'references', 'imports', 'instantiates']);`"
- Cursor global still emits the literal — (`codegraph/src/installer/targets/cursor.ts:173`) — quote: "`const pathArg = loc === 'local' ? process.cwd() : '${workspaceFolder}';`"
- CLI E2E BIN — (`codegraph/__tests__/index-command.test.ts:23`) — quote: "`const BIN = path.resolve(__dirname, '../dist/bin/codegraph.js');`"
- Mini-graph fixture `greet`/`hello`/`main` — (`codegraph/__tests__/index-command.test.ts:53-58`) — quote: "`export function greet(name: string) { return hello(name); }`" / "`export function main() { return greet('world'); }`"
- Detector unit tests exist; no refusal E2E — (`codegraph/__tests__/unsafe-index-root.test.ts:117-119`) — quote: "`describe('isUnexpandedTemplatePath', () => {`" / "`expect(isUnexpandedTemplatePath('${workspaceFolder}')).toBe(true);`"
- `uninit` TTY confirm must not be copied — (`codegraph/src/bin/codegraph.ts:550-556`) — quote: "`if (!options.force) {`" / "`const readline = await import('readline');`"
- Tests import exported directory symbols — (`codegraph/__tests__/unsafe-index-root.test.ts:5`) — quote: "`import { unsafeIndexRootReason, findNearestCodeGraphRoot, isUnexpandedTemplatePath } from '../src/directory';`"
- `npm test` is vitest — (`codegraph/package.json:21`) — quote: "`vitest run`"
- `npm run build` starts with tsc — (`codegraph/package.json:16`) — quote: "`tsc && npm run copy-assets`"
- `@types/node` is v20 — (`codegraph/package.json:48`) — quote: "`^20.19.30`"
- `skipLibCheck` is on — (`codegraph/tsconfig.json:25`) — quote: "`skipLibCheck`"
- Patch table still says warn — (`codegraph/UPDATING.md:22`) — quote: "`ignored with warning`"
- Ship rsync — (`codegraph/UPDATING.md:55`) — quote: "`rsync -a --delete dist/`"
- Version pin lives outside dist — (`codegraph/UPDATING.md:62`) — quote: "`The rsync does NOT touch `"
- CHANGELOG Unreleased grouping — (`codegraph/CHANGELOG.md:10`) — quote: "`## [Unreleased]`"
- Fork changelog writes under Unreleased — (`codegraph/CLAUDE.md:220`) — quote: "`write entries under `"
- `codegraph/docs/adr/` is absent (create it). Naming precedent: `ssot-diagram/adrs/0001-reuse-p1-recipe-by-sibling-import-defer-shared-to-phase-b.md`.
- Bundled runtime (FCV, do not re-probe unless node swapped) — (`docs/AI_artifacts/5_factual-code-verification/2026-08-17-bkt4-codegraph-cli.md:6`) — quote: "`**v24.16.0**`"
- Directory+readOnly ⇒ 266; chmod-000 ⇒ 14; junk COUNT ⇒ 26; smash ⇒ 11; missing-nodes ⇒ 1; non-WAL EXCLUSIVE COUNT ⇒ 5 ~548ms; WAL write ⇒ 5 ~545ms; WAL pragma changes sha256; busy_timeout+COUNT does not — FCV A13/Update 2026-08-17.
- Nodes-only: probe empty then open/migrations `no such table: unresolved_refs` errcode 1; `clear()` never runs — FCV A19.
- TD-01 stays OPEN — (`docs/TECH_DEBT.md:5`) — quote: "`TD-01 · No post-`"
- Known-answer fixture bytes **this plan pins:** file `codegraph/__tests__/fixtures/bkt4-known-answer.txt` contents exactly `bkt4-known-answer-v1\n` (UTF-8). Oracle `shasum -a 256` this session: `0f1838a54d465456862a5d44d65cecbc043a495897a45777a4986d8a3d1a2cdb`. Paste that hex as a **literal** in the unit test. Do not compute expected digest by calling the helper.

## Files

- `codegraph/__tests__/fixtures/bkt4-known-answer.txt` — committed known-answer bytes
- `codegraph/__tests__/fs-snapshot.ts` — test-only snapshot helper (`snapshotTree`)
- `codegraph/__tests__/fs-snapshot.test.ts` — known-answer + mutate/unreadable/symlink tests
- `codegraph/__tests__/mini-graph-fixture.ts` — one constant for `a.ts`/`b.ts` source + symbol names
- `codegraph/__tests__/probe-index-health.test.ts` — in-process probe fixtures
- `codegraph/__tests__/unexpanded-path-refusal.test.ts` — CLI `${…}` E2E vs `dist/`
- `codegraph/__tests__/index-command.test.ts` — import mini-graph; add init-repair E2E
- `codegraph/src/directory.ts` — add `probeIndexHealth`; **do not** change `isInitialized` / `isUnexpandedTemplatePath` bodies
- `codegraph/src/bin/codegraph.ts` — `assertExpandedPath`, both doors; `runInitialIndex`; init dispatch + unlink helper + write-path abort
- `codegraph/docs/adr/0001-init-repairs-unusable-index.md` — create `codegraph/docs/adr/`
- `codegraph/UPDATING.md` — amend patch-table row 22; add init-repair row
- `codegraph/CHANGELOG.md` — two user-facing `[Unreleased]` bullets (Fixes)

## Delegation Authority

- **Allowed set** = the union of every step's "Files to modify" (= ## Files). Nothing outside it.
- A file in ## Files assigned to ANOTHER step = a dependency (run per ## Implementation Order), not a deviation.
- A file NOT in ## Files → STOP, don't silently edit. Record in an `### Out-of-scope touches` block of the end-of-implementation report (file, why the step needed it, the change, whether it signals a plan/spec gap).
- **Hard off-limits (escalate before touching):** `codegraph/src/mcp/**`; `codegraph/src/installer/**` (esp. `targets/cursor.ts`); `codegraph/src/bin/fatal-handler.ts`; `codegraph/src/db/**`; `codegraph/src/index.ts` barrel / `OpenOptions.readOnly` / `CodeGraph.init` library; `falkor-writ/**`; `agent_village/**`; `isInitialized` / `isUnexpandedTemplatePath` bodies; `.codegraph/ready`; `npm install -g` / `codegraph upgrade`; piggyback Python tools; `CLAUDE.md` / `STATE.md` / `docs/TECH_DEBT.md` (TD-01 stays OPEN).
- **Escalate, don't improvise (verbatim — copy into the plan):** *If a test cannot pass without violating this plan's design, STOP and report it. Do not improvise a fix and do not revert anything.*

## Rules Applied

No matching rules (no WRIT `PROJ-*` / `--- WRIT RULES ---` block in this dispatch). Binding MUSTs are spec Constraints 1–13.

## Capabilities

- [ ] C1. Snapshot helper records file `{kind:'file', ino, sha256}`, unreadable `{kind:'file', ino, hash:'<unreadable>'}`, dir `{kind:'dir', ino}`, symlink `{kind:'symlink', ino, target}`; known-answer hex `0f1838a54d465456862a5d44d65cecbc043a495897a45777a4986d8a3d1a2cdb` matches helper; helper returning `''` fails
- [ ] C2. Provided `--path '${workspaceFolder}'` on a `resolveProjectPath` command exits ≠0; stderr names the literal; cwd `.codegraph/` snapshot identical; no cwd entry named `${workspaceFolder}`
- [ ] C3. `codegraph init '${workspaceFolder}'` exits ≠0; no `.codegraph/` created; `existsSync('${workspaceFolder}')` false in cwd and temp root
- [ ] C4. Bare `codegraph explore greet` (no `--path`) on a healthy indexed fixture still answers
- [ ] C5. `serve --mcp --path '${workspaceFolder}'` exits ≠0 **before** serving; message on stderr not stdout-only
- [ ] C6. Probe: junk→unreadable 26; smash→unreadable 11; no-`nodes`→unreadable 1; other errcode-1→unclassified; non-WAL EXCLUSIVE COUNT→busy 5; chmod-000→unclassified **14** at construction; directory+`readOnly`→unclassified **266** at construction; no-`errcode`→unclassified; COUNT 0→empty; COUNT>0→usable; sha256 unchanged across probe; handle closed
- [ ] C7. `init` on nodes>0: exit 0, inode+sha256 unchanged, no index-result line
- [ ] C8. `init` on 0-node full schema: exit 0, POSIX inode same (win32: unlink-spy never db path), repair proof (`greet`/`hello`/`main` + `main→greet` `edge.kind==='calls'` + both files)
- [ ] C9. `init` on unreadable (26 / 11 / missing-`nodes` 1), one fixture each, leftover `-wal` planted: vanished ⊆ three-file set; leftover wal absent-or-different-sha; repair proof; exit 0
- [ ] C10. Both busy fixtures (non-WAL probe **and** WAL write-path): exit ≠0, names db path + `codegraph daemon`, no unlink
- [ ] C11. Unclassified: directory pins 266; chmod-000 pins 14 + `{ino,hash:'<unreadable>'}` (never sha256 of unreadable); nodes-only pins errcode 1 + `unresolved_refs`, no unlink
- [ ] C12. Detector still `p.includes('${')`; `isInitialized` still `existsSync`
- [ ] C13. ADR + UPDATING patch table no longer “ignored with warning” + init-repair row; CHANGELOG two user-facing Unreleased bullets
- [ ] C14. Live bundle after rsync: `codegraph --version` is `999.0.0`; live `init` repairs hollow/junk; live `--path '${workspaceFolder}'` refuses

## Implementation Order

Call-graph facts (one cite each; do not re-derive):

- `init` does not call `resolveProjectPath` — (`codegraph/src/bin/codegraph.ts:468`) — quote: "`path.resolve(pathArg || process.cwd())`"
- Already-init branch is the dispatch hook — (`codegraph/src/bin/codegraph.ts:486`) — quote: "`if (isInitialized(projectPath)) {`"
- `createDirectory` blocks while db exists — (`codegraph/src/directory.ts:295`) — quote: "`if (fs.existsSync(dbPath)) {`"
- CLI E2E spawns dist BIN — (`codegraph/__tests__/index-command.test.ts:23`) — quote: "`../dist/bin/codegraph.js`"
- Probe `../db` would cycle — (`codegraph/src/db/index.ts:12`) — quote: "`from '../directory'`"
- Ship command — (`codegraph/UPDATING.md:55`) — quote: "`rsync -a --delete dist/`"

`assertExpandedPath` is called from `resolveProjectPath` (14 callers inherit) and from `init`. `runInitialIndex` is called from three init paths; `index` keeps its own `clear()`. E2E requires `npm run build` first.

**Dependency table:**

| Step | Produces | Depends on | Why (cite) |
|---|---|---|---|
| 1 | `snapshotTree` + known-answer fixture | none | spec component 1; used by steps 3 and 5 snapshots |
| 2 | `probeIndexHealth` + in-process fixtures | none | beside `isInitialized`; no `../db` (see Facts `db/index.ts` import) |
| 3 | `assertExpandedPath` + refusal E2E | 1 | both doors; E2E uses `snapshotTree` |
| 4 | `runInitialIndex` + init dispatch + unlink | 2, 3 | after `isInitialized`; unlink before `createDirectory` |
| 5 | init-repair E2E | 1, 4 | spawn dist BIN; repair proof via `getNodesByName`/`getCallees` |
| 6 | ADR + UPDATING + CHANGELOG | none (docs) | spec component 8; can parallel 1–2 |
| 7 | build + vitest + rsync + live check | 3–6 | rsync line in UPDATING; A11 |

**Parallel waves** (disjoint files): **Wave A:** Step 1 ∥ Step 2 ∥ Step 6. **Wave B:** Step 3 (after 1). **Wave C:** Step 4 (after 2+3; same file as Step 3). **Wave D:** Step 5 (after 1+4). **Wave E:** Step 7.
**Critical path:** 1 → 3 → 4 → 5 → 7 with 2 → 4. Solo linear: 1, 2, 6, 3, 4, 5, 7.

## Steps

### Step 1 — Snapshot helper + known-answer fixture
**Goal**: Test-only `snapshotTree` that compares bytes+identity, including unreadable/dir/symlink (spec component 1).
**Design** (imperative — decision already made, no design freedom): Create `codegraph/__tests__/fs-snapshot.ts` exporting `snapshotTree(dir: string): Record<string, {kind:'file', ino:number, sha256?:string, hash?:'<unreadable>'} | {kind:'dir', ino:number} | {kind:'symlink', ino:number, target:string}>`. Implementation: `readdirSync` + `lstatSync` first. Regular file: `fs.accessSync(p, fs.constants.R_OK)` — if it throws, record `{kind:'file', ino, hash:'<unreadable>'}` and **never** `createHash`. If readable, `sha256` hex of file bytes via `node:crypto`. Directory: `{kind:'dir', ino}`. Symlink: `{kind:'symlink', ino, target: readlinkSync}`. Keys = relative entry names. No production import, no stub, no injectable comparator. Write `codegraph/__tests__/fixtures/bkt4-known-answer.txt` with **exactly** the bytes `bkt4-known-answer-v1\n`. Unit test `codegraph/__tests__/fs-snapshot.test.ts`: `expect(snapshotTree(...).sha256).toBe('0f1838a54d465456862a5d44d65cecbc043a495897a45777a4986d8a3d1a2cdb')` as a **literal** (do not call the helper to produce the expected). Also: mutate-a-byte changes sha256; add-an-entry adds a key; replace-file-with-symlink changes kind+target; chmod-000 (POSIX non-root) records `{ino, hash:'<unreadable>'}` and still records `ino`. A helper that always returns `''` must fail the known-answer test.
**Actions**: 1. Add `codegraph/__tests__/fixtures/bkt4-known-answer.txt` with exact bytes `bkt4-known-answer-v1\n`. 2. Add `codegraph/__tests__/fs-snapshot.ts::snapshotTree`. 3. Add `codegraph/__tests__/fs-snapshot.test.ts` with the pasted-literal known-answer and mutate/unreadable/symlink cases. 4. RED then GREEN: `npm test -- __tests__/fs-snapshot.test.ts` from `codegraph/`. 5. Do not edit `src/`.
**Files to modify**: - `codegraph/__tests__/fixtures/bkt4-known-answer.txt` — create - `codegraph/__tests__/fs-snapshot.ts` — create `snapshotTree` - `codegraph/__tests__/fs-snapshot.test.ts` — create

<!-- plan-verify
new:   codegraph/__tests__/fs-snapshot.ts::snapshotTree
tier: C
qualifiers: grep-present "<unreadable>" codegraph/__tests__/fs-snapshot.ts ; grep-present "0f1838a54d465456862a5d44d65cecbc043a495897a45777a4986d8a3d1a2cdb" codegraph/__tests__/fs-snapshot.test.ts ; diff-only-within codegraph/__tests__
-->

**Test criteria**: - [ ] `cd codegraph && npm test -- __tests__/fs-snapshot.test.ts` passes - [ ] known-answer uses the literal hex above, not `snapshotTree` output as expected
**Do not regress**: none in this test-only file (no BUG-ID). Do not weaken later chmod-000 E2E to sha256-of-unreadable.
**Report contract**: on done, report the literal test command run (copy-paste exact, e.g. `npm test -- foo.test.ts`), its pass/fail tail, files touched, any `### Out-of-scope touches`; end with the sentinel line `END`. The orchestrator greps every claim against the diff — an unverifiable/truncated claim fails the step. Don't paraphrase the command; paste it.
*If a test cannot pass without violating this plan's design, STOP and report it. Do not improvise a fix and do not revert anything.*
**Status**: [ ] pending

### Step 2 — `probeIndexHealth` in `directory.ts`
**Goal**: Classify existing db without mutating it and without `../db` (spec component 3).
**Design** (imperative — decision already made, no design freedom): In `codegraph/src/directory.ts` beside `isInitialized`, add `export function probeIndexHealth(projectRoot: string): { status: 'usable'|'empty'|'unreadable'|'busy'|'unclassified'; errcode?: number; message?: string }`. Resolve `dbPath` via `path.join(getCodeGraphDir(projectRoot), 'codegraph.db')` — never a hardcoded `.codegraph/`. Load sqlite with `const { DatabaseSync } = require('node:sqlite')` (eslint-disable `@typescript-eslint/no-require-imports`, same as (`codegraph/src/db/sqlite-adapter.ts:55`) — quote: "`const { DatabaseSync } = require('node:sqlite');`"). `let db: { exec: Function; prepare: Function; close: Function } | null = null`. One `try`: `db = new DatabaseSync(dbPath, { readOnly: true })`; `db.exec('PRAGMA busy_timeout = 500')`; `const row = db.prepare('SELECT COUNT(*) AS n FROM nodes').get() as { n: number }`; return `{ status: row.n === 0 ? 'empty' : 'usable' }`. **Never** `PRAGMA journal_mode = WAL`. **Never** import `../db`, `configureConnection`, `createDatabase`, `CodeGraph.open`, `DatabaseConnection.open`. `catch (err)` dispatch **this order**: (1) `typeof (err as {errcode?: unknown}).errcode !== 'number'` → `{ status:'unclassified', message }`; (2) `errcode === 5` → `{ status:'busy', errcode, message }`; (3) `26` or `11` → `{ status:'unreadable', errcode, message }`; (4) `errcode === 1` **and** `message.includes('no such table: nodes')` → unreadable; any other 1 → unclassified; (5) any other including **14** and **266** → unclassified. `finally { if (db) { try { db.close(); } catch { /* ignore */ } } }`. Do **not** change `isInitialized` (`return fs.existsSync(dbPath)`). Do **not** add `probeIndexHealth` to `src/index.ts`. TDD: write `codegraph/__tests__/probe-index-health.test.ts` **first** (RED), import `probeIndexHealth` from `../src/directory`. Live fixtures: junk text → unreadable 26 (COUNT may throw, ctor may not); smash@4096 → unreadable 11; no `nodes` table → unreadable 1 + `no such table: nodes`; `SELECT nosuchfn() FROM nodes` if it yields errcode 1 with a different message → unclassified (else keep the branch + comment `// other errcode 1 → unclassified (A14)`); `new DatabaseSync(12345 as never)` in the **test file only** documents no-errcode; non-WAL `BEGIN EXCLUSIVE` + probe → busy 5 (~2s timeout); chmod-000 POSIX non-root → unclassified 14 at construction (`it.runIf`, restore mode in `afterEach`); `mkdirSync(dbPath)` → unclassified 266 at construction; usable = init+index then probe, sha256 unchanged; empty = init then `DELETE FROM nodes`, snapshot after delete, probe, sha256 unchanged. After probe, a writable reopen must still work (handle closed).
**Actions**: 1. Write RED tests in `codegraph/__tests__/probe-index-health.test.ts` importing `codegraph/src/directory.ts::probeIndexHealth`. 2. Implement `codegraph/src/directory.ts::probeIndexHealth` using `codegraph/src/directory.ts::getCodeGraphDir` for the db path and `require('node:sqlite')` (same form as `sqlite-adapter.ts:55` — quote: "`const { DatabaseSync } = require('node:sqlite');`"), `{ readOnly: true }`, `busy_timeout = 500`, COUNT, ordered dispatch, try/finally close. 3. Keep `codegraph/src/directory.ts::isInitialized` body `return fs.existsSync(dbPath)`. 4. Do not change `codegraph/src/directory.ts::isUnexpandedTemplatePath`. 5. Do not import `from '../db'`. 6. GREEN: `cd codegraph && npm test -- __tests__/probe-index-health.test.ts`.
**Files to modify**: - `codegraph/src/directory.ts` — add probe - `codegraph/__tests__/probe-index-health.test.ts` — create

<!-- plan-verify
new:   codegraph/src/directory.ts::probeIndexHealth
touch: codegraph/src/directory.ts::isInitialized, codegraph/src/directory.ts::getCodeGraphDir, codegraph/src/directory.ts::isUnexpandedTemplatePath
remove:
tier: A
qualifiers: grep-present "busy_timeout = 500" codegraph/src/directory.ts ; grep-absent "busy_timeout = 5000" codegraph/src/directory.ts ; grep-absent "journal_mode = WAL" codegraph/src/directory.ts ; grep-absent "from '../db'" codegraph/src/directory.ts ; grep-absent "probeIndexHealth" codegraph/src/index.ts ; grep-present "readOnly: true" codegraph/src/directory.ts ; byte-unchanged codegraph/src/mcp/tools.ts ; byte-unchanged codegraph/src/installer/targets/cursor.ts ; byte-unchanged codegraph/src/db/index.ts ; byte-unchanged codegraph/src/index.ts
-->

**Test criteria**: - [ ] `cd codegraph && npm test -- __tests__/probe-index-health.test.ts` passes - [ ] pins 26, 11, nodes-missing 1, busy 5, 14, 266, empty, usable - [ ] probe does not change db sha256 - [ ] `isInitialized` source still `existsSync` only
**Do not regress**: #845 unsafe-root (`unsafeIndexRootReason` untouched); detector tests in `unsafe-index-root.test.ts`; MCP empty warning (`mcp/tools.ts` byte-unchanged).
**Report contract**: on done, report the literal test command run (copy-paste exact, e.g. `npm test -- foo.test.ts`), its pass/fail tail, files touched, any `### Out-of-scope touches`; end with the sentinel line `END`. The orchestrator greps every claim against the diff — an unverifiable/truncated claim fails the step. Don't paraphrase the command; paste it.
*If a test cannot pass without violating this plan's design, STOP and report it. Do not improvise a fix and do not revert anything.*
**Status**: [ ] pending

### Step 3 — `assertExpandedPath` at both doors + refusal E2E
**Goal**: Provided `${…}` is a hard CLI error; cwd is never the fallback (spec components 2 + 6).
**Design** (imperative — decision already made, no design freedom): In `codegraph/src/bin/codegraph.ts` add **unexported** `function assertExpandedPath(pathArg: string | undefined, label: string): void`. If `pathArg` is truthy **and** `isUnexpandedTemplatePath(pathArg)`: `console.error` one message that includes (1) the literal `pathArg`, (2) `label` (`--path` vs `init path`), (3) `Pass a real folder`, (4) exact substring `absolute folder in your MCP config`. Then `process.exit(1)`. **Never throw. Never `warn()`. Never `console.log`.** Call site A: **first line** of `resolveProjectPath` — replace the current warn+`pathArg=undefined` block entirely (delete `Falling back to the current directory`). Call site B: **first line** of the `init` action, **before** `path.resolve` and before `clack.intro`. Detector stays `isUnexpandedTemplatePath` (do not edit). Bare omitted path still hits `path.resolve(pathArg || process.cwd())`. E2E file `codegraph/__tests__/unexpanded-path-refusal.test.ts`: `BIN` = `path.resolve(__dirname, '../dist/bin/codegraph.js')`; `spawnSync(process.execPath, [BIN, ...args], { cwd, encoding:'utf-8', env:{...process.env, CODEGRAPH_NO_DAEMON:'1', CODEGRAPH_WASM_RELAUNCHED:'1'}, timeout: 15000 })` — **not** `execFileSync` (it throws on ≠0). Use `snapshotTree` from `./fs-snapshot`. Cases: (1) `['status', '--path', '${workspaceFolder}']` (resolveProjectPath door) — status≠0, stderr contains `${workspaceFolder}`, stdout must not be the only channel (assert stderr length>0), cwd snapshot identical, `readdirSync(cwd)` has no entry named `${workspaceFolder}`, if no `.codegraph/` before then none after. (2) `['init', '${workspaceFolder}']` — same plus `existsSync(path.join(cwd,'${workspaceFolder}'))===false` and same in the temp root. (3) healthy fixture: write mini-graph files, `init`, then `['explore', 'greet']` with **no** `--path` — status 0 and output mentions `greet`. (4) `['serve', '--mcp', '--path', '${workspaceFolder}']` — status≠0 **before** hang; stderr contains literal; do not treat stdout as the message channel. `npm run build` before these tests. TDD: write the test file first; it fails while fallback still exists; then implement the guard.
**Actions**: 1. Add RED `codegraph/__tests__/unexpanded-path-refusal.test.ts` (build first so BIN exists). 2. Add `codegraph/src/bin/codegraph.ts::assertExpandedPath` that calls existing `isUnexpandedTemplatePath` (do not edit `codegraph/src/directory.ts::isUnexpandedTemplatePath`). 3. Call `assertExpandedPath` at top of `codegraph/src/bin/codegraph.ts::resolveProjectPath` and at top of the `init` action before `path.resolve`. 4. Delete the warn+fallback assignment. 5. GREEN: `cd codegraph && npm run build && npm test -- __tests__/unexpanded-path-refusal.test.ts __tests__/unsafe-index-root.test.ts`.
**Files to modify**: - `codegraph/src/bin/codegraph.ts` — guard + both doors - `codegraph/__tests__/unexpanded-path-refusal.test.ts` — create

<!-- plan-verify
new:   codegraph/src/bin/codegraph.ts::assertExpandedPath
touch: codegraph/src/bin/codegraph.ts::resolveProjectPath, codegraph/src/directory.ts::isUnexpandedTemplatePath
remove:
tier: B
qualifiers: grep-absent "Falling back to the current directory" codegraph/src/bin/codegraph.ts ; grep-present "absolute folder in your MCP config" codegraph/src/bin/codegraph.ts ; grep-present "assertExpandedPath" codegraph/src/bin/codegraph.ts ; byte-unchanged codegraph/src/installer/targets/cursor.ts ; byte-unchanged codegraph/src/mcp/tools.ts ; byte-unchanged codegraph/src/bin/fatal-handler.ts
-->

**Test criteria**: - [ ] `cd codegraph && npm run build && npm test -- __tests__/unexpanded-path-refusal.test.ts` passes - [ ] C2 C3 C4 C5 - [ ] `unsafe-index-root` still passes
**Do not regress**: #845 unsafe-root; Cursor still emits `'${workspaceFolder}'` (installer byte-unchanged); fatal-handler still installed; stdout-MCP cleanliness (`console.error` only).
**Report contract**: on done, report the literal test command run (copy-paste exact, e.g. `npm test -- foo.test.ts`), its pass/fail tail, files touched, any `### Out-of-scope touches`; end with the sentinel line `END`. The orchestrator greps every claim against the diff — an unverifiable/truncated claim fails the step. Don't paraphrase the command; paste it.
*If a test cannot pass without violating this plan's design, STOP and report it. Do not improvise a fix and do not revert anything.*
**Status**: [ ] pending

### Step 4 — `runInitialIndex` + `init` dispatch + write-path abort
**Goal**: Existence-true `init` repairs empty/unreadable and refuses busy/unclassified without prompts (spec components 4–5).
**Design** (imperative — decision already made, no design freedom): In `codegraph/src/bin/codegraph.ts` extract local `async function runInitialIndex(clack: typeof import('@clack/prompts'), cg: { indexAll: Function; destroy: Function }, projectPath: string, options: { verbose?: boolean }): Promise<IndexResult>` containing **exactly** today’s init block `:506-524` (verbose vs shimmer `indexAll`, `printIndexResult`, `recordIndexTelemetry`, `offerWatchFallback`). Fresh-init path after `CodeGraph.init` **must** call `runInitialIndex` (replace the inlined block). Do **not** change the `index` command (`cg.clear` at `:628`/`:643` stays). Import `probeIndexHealth` from `../directory`. After `if (isInitialized(projectPath))`, call `const health = probeIndexHealth(projectPath)` then:

| `health.status` | Action |
|---|---|
| `usable` | keep today’s warn + `offerWatchFallback` + `return` (exit 0). Touch nothing. |
| `busy` | `clack.log.error` naming **db path** (`path.join(getCodeGraphDir(projectPath), 'codegraph.db')`) and `codegraph daemon`; `clack.outro(''); process.exit(1)` — **not** bare `return`. Touch nothing. |
| `unclassified` | error naming **raw `health.errcode` + `health.message`**; `process.exit(1)`. Touch nothing. |
| `empty` | `CodeGraph.open(projectPath)` (writes/migrations OK); `cg.clear()`; `runInitialIndex`. **Never unlink.** |
| `unreadable` | `unlinkUnreadableIndex(projectPath)` then fall through to existing fresh `CodeGraph.init` + `runInitialIndex`. |

Add local `function unlinkUnreadableIndex(projectPath: string): void` that unlinks **exactly** `codegraph.db`, `codegraph.db-wal`, `codegraph.db-shm` under `getCodeGraphDir(projectPath)` (honor `CODEGRAPH_DIR`). Ignore `ENOENT`; rethrow other unlink errors. No `readdir` / no recursive rm.

Write-path: wrap repair writes (`CodeGraph.open` / `clear` / `init` / `runInitialIndex`) so if thrown value has `errcode === 5` → same busy error, **no further unlink**; **any other throw** (including A19 `no such table: unresolved_refs` errcode 1) → unclassified error naming errcode+message, **never unlink**. Do **not** map any `no such table:*` to unreadable. No `readline` / `clack.confirm` on this branch. Do not copy `uninit` `:550-565`. `isInitialized` still existence-only.

TDD: Step 5 owns E2E; this step’s GREEN is `npm run build` plus existing `index-command` + `foundation` still passing, and a **thin** init-dispatch unit is optional. Prefer shipping dispatch here so Step 5 is RED→GREEN on E2E only. If you add no new test in this step, run `cd codegraph && npm run build && npm test -- __tests__/index-command.test.ts __tests__/foundation.test.ts __tests__/unexpanded-path-refusal.test.ts __tests__/probe-index-health.test.ts` and keep them green.
**Actions**: 1. Add `codegraph/src/bin/codegraph.ts::runInitialIndex` by moving `:506-524`; it must call `printIndexResult`. 2. Point the fresh-init path at `runInitialIndex`. 3. Add `codegraph/src/bin/codegraph.ts::unlinkUnreadableIndex` using `getCodeGraphDir` (honor `CODEGRAPH_DIR`); unlink only after `createDirectory` would otherwise throw (`codegraph/src/directory.ts:295`). 4. After `isInitialized`, dispatch on `probeIndexHealth` (created in Step 2; do not re-declare). 5. Write-path: errcode 5 → busy exit 1 no unlink; else unclassified no unlink. 6. No TTY confirm. 7. Do not edit `index` command’s `clear()`.
**Files to modify**: - `codegraph/src/bin/codegraph.ts` — extract + dispatch

<!-- plan-verify
new:   codegraph/src/bin/codegraph.ts::runInitialIndex, codegraph/src/bin/codegraph.ts::unlinkUnreadableIndex
touch: codegraph/src/bin/codegraph.ts::printIndexResult, codegraph/src/directory.ts::createDirectory, codegraph/src/directory.ts::isInitialized, codegraph/src/directory.ts::getCodeGraphDir
remove:
tier: A
qualifiers: grep-present "codegraph daemon" codegraph/src/bin/codegraph.ts ; grep-present "runInitialIndex" codegraph/src/bin/codegraph.ts ; grep-absent "clack.confirm" codegraph/src/bin/codegraph.ts ; grep-present "codegraph.db-wal" codegraph/src/bin/codegraph.ts ; grep-present "codegraph.db-shm" codegraph/src/bin/codegraph.ts ; byte-unchanged codegraph/src/mcp/tools.ts ; byte-unchanged codegraph/src/installer/targets/cursor.ts ; byte-unchanged codegraph/src/db/migrations.ts ; byte-unchanged codegraph/src/index.ts
-->

**Test criteria**: - [ ] `cd codegraph && npm run build && npm test -- __tests__/index-command.test.ts __tests__/foundation.test.ts __tests__/unexpanded-path-refusal.test.ts __tests__/probe-index-health.test.ts` passes - [ ] Review can name exactly one function (`runInitialIndex`) that all three init index paths call
**Do not regress**: #874 `index` still `clear()`s then rebuilds; #845 unsafe-root branch still sets `exitCode=1`; foundation `isInitialized` tests; MCP tools byte-unchanged.
**Report contract**: on done, report the literal test command run (copy-paste exact, e.g. `npm test -- foo.test.ts`), its pass/fail tail, files touched, any `### Out-of-scope touches`; end with the sentinel line `END`. The orchestrator greps every claim against the diff — an unverifiable/truncated claim fails the step. Don't paraphrase the command; paste it.
*If a test cannot pass without violating this plan's design, STOP and report it. Do not improvise a fix and do not revert anything.*
**Status**: [ ] pending

### Step 5 — E2E init-repair tests
**Goal**: Empty rebuilds in place; unreadable replaces the three-file set only; busy/unclassified mutate nothing; repair is a real index (spec component 7).
**Design** (imperative — decision already made, no design freedom): Create `codegraph/__tests__/mini-graph-fixture.ts` exporting `MINI_GRAPH_FILES` (new) `Record<string,string>` with the **same** `a.ts`/`b.ts` source currently inlined in `index-command.test.ts:53-58` — quote: "`export function greet(name: string) { return hello(name); }`" — and `MINI_GRAPH_SYMBOLS` (new) `{ greet:'greet', hello:'hello', main:'main' } as const`. Refactor `index-command.test.ts` to write files from that constant (Hold 6). Add describe blocks to `index-command.test.ts` (or sibling `init-repair.test.ts` imported helpers — prefer **extend** `index-command.test.ts` per spec). Spawn `BIN` via `spawnSync` + `CODEGRAPH_NO_DAEMON=1` + `CODEGRAPH_WASM_RELAUNCHED=1`. Every mutation claim uses `snapshotTree`. Repair proof helper: `CodeGraph.openSync` → `getNodesByName(MINI_GRAPH_SYMBOLS.greet/hello/main)` each `.length >= 1`; find `main` node; `getCallees(main.id)` some `edge.kind === 'calls'` and callee name `greet`; `getFiles()` includes both `a.ts` and `b.ts`. Same-file `greet→hello` optional. A dummy extra node must not satisfy this (don’t insert one and call it passing).

Fixtures:
1. **Usable:** init mini-graph; snapshot inode+sha256; `init` again; exit 0; inode+sha256 unchanged; stdout/stderr has no `Indexed ` / nodes-count success line from a new index (`Already initialized` OK).
2. **Empty POSIX:** init, then DELETE all rows from `nodes` (keep schema + plant current `.gitignore` — init already wrote it); snapshot; `init`; exit 0; **same `ino`**; repair proof. **win32:** `it.runIf(process.platform === 'win32')` spy `fs.unlinkSync` — production must **not** unlink the db path; do not gate on inode (`statInode` null).
3. **Unreadable ×3** (separate tests): (a) junk text file + **plant leftover** `codegraph.db-wal` with distinct bytes; (b) smash@4096 of a real sqlite + leftover wal; (c) sqlite **without** `nodes` table (hollow) + leftover wal. After `init` exit 0: vanished names ⊆ `{codegraph.db, codegraph.db-wal, codegraph.db-shm}`; every other `.codegraph/` entry unchanged sha256; leftover wal **absent or sha256 ≠ before**; repair proof. Hollow must assert repair **happened** (proof), not merely “did not delete extra”.
4. **Busy probe (required):** non-WAL `PRAGMA journal_mode=DELETE` + child `BEGIN EXCLUSIVE` + `init` → ≠0; stderr names db path + `codegraph daemon`; snapshot identical (inode+every sha256).
5. **Busy write-path (required, do not drop):** WAL tree, 0 nodes (empty schema), child holds `BEGIN EXCLUSIVE` **writable** so probe COUNT succeeds then repair write throws 5 → same busy error, no unlink. Keep **both** fixtures.
6. **Unclassified directory (primary):** `mkdir` at db path; `init` ≠0; stderr names **266** (not 14); snapshot `{kind:'dir', ino}` unchanged; vanished-names empty.
7. **Unclassified chmod-000:** `it.runIf(process.platform !== 'win32' && process.getuid?.() !== 0)`; restore mode in `afterEach` **before** `rmSync`; stderr names **14**; compare `{ino, hash:'<unreadable>'}` — **never sha256 of the unreadable file**.
8. **Nodes-only A19:** sqlite with `CREATE TABLE nodes(...)` and **no** `files` / `unresolved_refs`; `init` ≠0; stderr contains errcode 1 and `unresolved_refs`; vanished-names empty; db file still present.

`npm run build` before the suite.
**Actions**: 1. Add `codegraph/__tests__/mini-graph-fixture.ts` with `MINI_GRAPH_FILES` (new) + `MINI_GRAPH_SYMBOLS` (new). 2. Refactor `codegraph/__tests__/index-command.test.ts` to import that constant. 3. Add all init-repair E2E rows (usable, empty POSIX+win32 spy, three unreadable, **both** busy, directory 266, chmod-000 14 sentinel, nodes-only A19). 4. RED then GREEN: `cd codegraph && npm run build && npm test -- __tests__/index-command.test.ts`.
**Files to modify**: - `codegraph/__tests__/mini-graph-fixture.ts` — create - `codegraph/__tests__/index-command.test.ts` — extend

<!-- plan-verify
new:   codegraph/__tests__/mini-graph-fixture.ts
touch: codegraph/__tests__/index-command.test.ts
remove:
tier: A
qualifiers: grep-present "edge.kind === 'calls'" codegraph/__tests__/index-command.test.ts ; grep-present "unresolved_refs" codegraph/__tests__/index-command.test.ts ; grep-present "<unreadable>" codegraph/__tests__/index-command.test.ts ; grep-present "codegraph daemon" codegraph/__tests__/index-command.test.ts ; grep-present "MINI_GRAPH_SYMBOLS" codegraph/__tests__/index-command.test.ts ; diff-only-within codegraph/__tests__
-->

**Test criteria**: - [ ] `cd codegraph && npm run build && npm test -- __tests__/index-command.test.ts` passes - [ ] C7–C11 all asserted, including **both** busy fixtures and chmod-000 sentinel (not sha256)
**Do not regress**: #874 index full-rebuild test in the same file; mini-graph `greet`/`hello`/`main` names stay in one constant.
**Report contract**: on done, report the literal test command run (copy-paste exact, e.g. `npm test -- foo.test.ts`), its pass/fail tail, files touched, any `### Out-of-scope touches`; end with the sentinel line `END`. The orchestrator greps every claim against the diff — an unverifiable/truncated claim fails the step. Don't paraphrase the command; paste it.
*If a test cannot pass without violating this plan's design, STOP and report it. Do not improvise a fix and do not revert anything.*
**Status**: [ ] pending

### Step 6 — ADR + UPDATING.md + CHANGELOG.md
**Goal**: Fork merge-survival and operator-visible record (spec component 8).
**Design** (imperative — decision already made, no design freedom): Create directory `codegraph/docs/adr/` and file `codegraph/docs/adr/0001-init-repairs-unusable-index.md` with Status Accepted (2026-08-17). Body must explain: (1) why `init` stopped being mkdir-only (existence-true hollow/junk used to exit 0); (2) why repair beats a `.codegraph/ready` stamp (ready = `nodes` count > 0); (3) why `busy` ≠ wipe; (4) Buckets 5/6 own their own unions — `probeIndexHealth` is not a public/MCP API (exported from `directory.ts` for tests only; not in `src/index.ts`). Amend `codegraph/UPDATING.md` patch table: change `:22` from `ignored with warning` to refused (non-zero exit, no cwd fallback). **Add** a row for `init` repair of empty/unreadable and busy/unclassified refuse. CHANGELOG under `## [Unreleased]` → `### Fixes` (not New Features unless you also have a feature sentence): **two** user-facing bullets, no `src/` paths, no internal symbol names, per `codegraph/CLAUDE.md` changelog rules. One bullet: unexpanded `${…}` in `--path` / `init` now errors instead of using the current folder. One bullet: `codegraph init` rebuilds an empty or unreadable index and refuses to delete anything when the database is locked or the failure is unknown. Do not create a `[X.Y.Z]` block. Do not touch writ/MCP/installer.
**Actions**: 1. Create `codegraph/docs/adr/0001-init-repairs-unusable-index.md`. 2. Amend `codegraph/UPDATING.md` row 22 and add init-repair row. 3. Add two `### Fixes` bullets under `## [Unreleased]` in `codegraph/CHANGELOG.md`.
**Files to modify**: - `codegraph/docs/adr/0001-init-repairs-unusable-index.md` — create - `codegraph/UPDATING.md` — patch table - `codegraph/CHANGELOG.md` — Unreleased Fixes

<!-- plan-verify
new:   codegraph/docs/adr/0001-init-repairs-unusable-index.md
tier: C
qualifiers: grep-absent "ignored with warning" codegraph/UPDATING.md ; grep-present "rsync -a --delete dist/" codegraph/UPDATING.md ; grep-present "## [Unreleased]" codegraph/CHANGELOG.md ; byte-unchanged codegraph/src/mcp/tools.ts ; byte-unchanged codegraph/src/installer/targets/cursor.ts
-->

**Test criteria**: - [ ] ADR file exists at that path - [ ] `UPDATING.md` no longer claims warn-and-ignore - [ ] CHANGELOG has both behaviours under Unreleased, user-facing
**Do not regress**: rsync deploy instructions (`UPDATING.md:55`) stay; 999.0.0 pin wording stays.
**Report contract**: on done, report the literal test command run (copy-paste exact, e.g. `npm test -- foo.test.ts`), its pass/fail tail, files touched, any `### Out-of-scope touches`; end with the sentinel line `END`. The orchestrator greps every claim against the diff — an unverifiable/truncated claim fails the step. Don't paraphrase the command; paste it. If no test binary applies, paste `test -f codegraph/docs/adr/0001-init-repairs-unusable-index.md && grep -n 'ignored with warning' codegraph/UPDATING.md || true`.
*If a test cannot pass without violating this plan's design, STOP and report it. Do not improvise a fix and do not revert anything.*
**Status**: [ ] pending

### Step 7 — Build, test, rsync deploy
**Goal**: Change is not dark on the live binary (spec component 9).
**Design** (imperative — decision already made, no design freedom): From `codegraph/`: `npm run build` then `npm test -- __tests__/fs-snapshot.test.ts __tests__/probe-index-health.test.ts __tests__/unexpanded-path-refusal.test.ts __tests__/index-command.test.ts __tests__/unsafe-index-root.test.ts __tests__/foundation.test.ts __tests__/mcp-explore-empty-warn.test.ts` (existing MCP smoke — **do not edit** `src/mcp/**`). Then `rsync -a --delete dist/ ~/.codegraph/versions/v1.0.1/lib/dist/`. Then `codegraph --version` must print `999.0.0`. Then live: temp dir with junk `codegraph.db` → `codegraph init` indexes (repair proof optional live); `codegraph status --path '${workspaceFolder}'` exits ≠0. Never `npm install -g` / `codegraph upgrade`. This step **must not edit** source files.
**Actions**: 1. `cd codegraph && npm run build`. 2. Run the vitest list above, including `codegraph/__tests__/index-command.test.ts` (do not edit it). 3. Follow the rsync line already in `codegraph/UPDATING.md` (`rsync -a --delete dist/ ~/.codegraph/versions/v1.0.1/lib/dist/`). 4. `codegraph --version` equals `999.0.0`. 5. Live refuse + live hollow/junk `init`. 6. Do not edit `codegraph/UPDATING.md` or other ## Files; rsync only generated gitignored `dist/`.
**Files to modify**: none (commands only; `dist/` is gitignored)

<!-- plan-verify
touch: codegraph/__tests__/index-command.test.ts
tier: B
qualifiers: grep-present "rsync -a --delete dist/" codegraph/UPDATING.md ; byte-unchanged codegraph/src/mcp/tools.ts
-->

**Test criteria**: - [ ] build + listed vitest pass (paste tail) - [ ] `codegraph --version` → `999.0.0` - [ ] live refuse + live repair observed
**Do not regress**: 999.0.0 pin; upgrade-blocked marker; MCP empty-warn suite.
**Report contract**: on done, report the literal test command run (copy-paste exact, e.g. `npm test -- foo.test.ts`), its pass/fail tail, files touched, any `### Out-of-scope touches`; end with the sentinel line `END`. The orchestrator greps every claim against the diff — an unverifiable/truncated claim fails the step. Don't paraphrase the command; paste it.
*If a test cannot pass without violating this plan's design, STOP and report it. Do not improvise a fix and do not revert anything.*
**Status**: [ ] pending

## E2E Done Criteria

**Prerequisites:** built `codegraph/dist/bin/codegraph.js`; live bundle `~/.codegraph/versions/v1.0.1/` after rsync; bundled node unchanged (v24.16.0). No mocks.

**Walkthrough** (action → observe → expected; map to Capabilities):
1. `printf 'bkt4-known-answer-v1\n' | shasum -a 256` → observe `0f1838a54d465456…` → expected matches test literal (C1).
2. In a temp project with no index: `codegraph status --path '${workspaceFolder}'` → observe exit ≠0, stderr contains `${workspaceFolder}`, cwd listing unchanged → C2.
3. `codegraph init '${workspaceFolder}'` in empty temp → observe exit ≠0, no dir named `${workspaceFolder}`, no `.codegraph/` → C3.
4. Indexed temp: `codegraph explore greet` (cwd, no `--path`) → observe greet source → C4.
5. `codegraph serve --mcp --path '${workspaceFolder}'` → observe exit ≠0 within 15s, stderr has literal → C5.
6. Usable index `codegraph init` → observe `Already initialized`, db sha256 unchanged → C7.
7. Hollow 0-node (schema present) `codegraph init` → observe index built; `main` calls `greet` → C8.
8. Junk db + leftover `-wal` `codegraph init` → observe exit 0, wal gone or different hash, graph proof → C9.
9. Locked non-WAL EXCLUSIVE `codegraph init` → observe ≠0, `codegraph daemon`, files unchanged → C10.
10. WAL empty + writer lock `codegraph init` → observe ≠0 busy, no unlink → C10.
11. `codegraph.db` is a directory → observe ≠0, names 266 → C11.
12. Nodes-only db → observe ≠0, `unresolved_refs`, file remains → C11.
13. `codegraph --version` → observe `999.0.0` → C14.

**Done gate:** every line observed + matching; listed vitest + live rsync done. Live observation diverging from a passing unit test → live wins; fix + re-run before marking done.

## Open Questions

- **OQ-4 (human-authority, not blocking):** probe `busy_timeout` 500 vs 5000. Spec: implement **500** unless owner closes otherwise. This plan locks 500. Do not reopen OQ-1/2/3.
- **TD-01** stays OPEN — no post-init event in this bucket.

No blocking questions. A13/A19 closed by FCV re-check.

## Out of Scope

Per spec: MCP `src/mcp/**`; writ; installer `cursor.ts` literal; `isInitialized` health-aware; `.codegraph/ready`; `$(cmd)` / `%VAR%`; schema-version as unreadable; auto-uninit / wipe of `.codegraph/`; wipe on busy/unknown; TD-01 event bus; ACP `--path` (Bucket 1); piggyback Python DB writes; `npm install -g` / `codegraph upgrade`. `index` command helper reuse (HOW lock D: keep own copy).

## Gate co-satisfiability

One honest implementation makes every cell green. `grep-absent` globs match existing files (Bucket 2: 0-file glob is a fail).

| Gate | After honest impl |
|---|---|
| `grep-present "<unreadable>" codegraph/__tests__/fs-snapshot.ts` | GREEN — helper sentinel |
| `grep-present "0f1838a54d465456862a5d44d65cecbc043a495897a45777a4986d8a3d1a2cdb" codegraph/__tests__/fs-snapshot.test.ts` | GREEN — pasted oracle |
| `diff-only-within codegraph/__tests__` (steps 1, 5) | GREEN — those waves only tests |
| `grep-present "busy_timeout = 500" codegraph/src/directory.ts` | GREEN — probe pragma |
| `grep-absent "busy_timeout = 5000" codegraph/src/directory.ts` | GREEN — 5000 stays in `db/index.ts` only |
| `grep-absent "journal_mode = WAL" codegraph/src/directory.ts` | GREEN — WAL stays in `configureConnection` |
| `grep-absent "from '../db'" codegraph/src/directory.ts` | GREEN — no cycle |
| `grep-absent "probeIndexHealth" codegraph/src/index.ts` | GREEN — HOW lock A (export from directory.ts, not barrel). Does **not** ban `export function probeIndexHealth` in `directory.ts` (tests must import it) |
| `grep-present "readOnly: true" codegraph/src/directory.ts` | GREEN — do not drop readOnly |
| `byte-unchanged codegraph/src/index.ts` (step 2) | GREEN — barrel untouched; fights adding barrel export (intentional) |
| `grep-absent "Falling back to the current directory" codegraph/src/bin/codegraph.ts` | GREEN after step 3 — string exists **now** (RED proof this session: present=`True`) |
| `grep-present "absolute folder in your MCP config" codegraph/src/bin/codegraph.ts` | GREEN after step 3 — does not fight the absent-fallback gate |
| `grep-present "assertExpandedPath" codegraph/src/bin/codegraph.ts` | GREEN |
| `byte-unchanged codegraph/src/installer/targets/cursor.ts` | GREEN — still emits `'${workspaceFolder}'` |
| `byte-unchanged codegraph/src/mcp/tools.ts` | GREEN — MCP empty threshold untouched |
| `grep-present "codegraph daemon" codegraph/src/bin/codegraph.ts` | GREEN — busy message |
| `grep-absent "clack.confirm" codegraph/src/bin/codegraph.ts` | GREEN — already absent; repair must not add it. `uninit` keeps `readline` (not this literal) |
| `grep-present "codegraph.db-wal"` / `codegraph.db-shm` in `codegraph.ts` | GREEN — unlink list |
| `byte-unchanged codegraph/src/db/migrations.ts` / `db/index.ts` | GREEN — A19 throw site stays migrations |
| `grep-present "edge.kind === 'calls'" codegraph/__tests__/index-command.test.ts` | GREEN — repair proof |
| `grep-present "unresolved_refs" codegraph/__tests__/index-command.test.ts` | GREEN — A19 fixture (does not fight unlink rules) |
| `grep-present "MINI_GRAPH_SYMBOLS"` | GREEN — Hold 6 |
| `grep-absent "ignored with warning" codegraph/UPDATING.md` | GREEN after step 6 — string exists **now** |
| `grep-present "rsync -a --delete dist/" codegraph/UPDATING.md` | GREEN — must keep ship line (pairs with absent-warning) |
| Step 7 `touch: codegraph/UPDATING.md` with no edit | wave-end may see no UPDATING diff — expected; gate is live commands. ORCH: admit empty touch if needed |

No pair requires failing another. `grep-absent probeIndexHealth` is **scoped to `src/index.ts`**, not `directory.ts` / tests (those must name it).

## Claim sweep

Checked this session against opened sources: detector `:169`; `isInitialized` `:100`; init resolve `:468`; `resolveProjectPath` fallback `:204-208`; 14 callers including `:1437`; `warn` stdout `:306`; fatal-handler `:89`; `createDatabase` wrap `:141-147`; `require('node:sqlite')` `:55`; `configureConnection` `:31-33`; `runMigrations` `:112`; cycle import `:12`; `statInode` win32 `:270`; `getCallees` kinds `:305`; MCP `nodeCount === 0` `:2273`; COUNT nodes `:1784`; `clear` DELETE files `:1867`; migration ALTER `:40` / version 0 `:89-91`; dead `readOnly` `:109`; Cursor literal `:173`; BIN `:23`; UPDATING `:22`/`:55`; `skipLibCheck` + `@types/node` 20; FCV bundled v24.16.0. Re-checked A13/A19 not re-opened. C2-NORED: `Falling back to the current directory` **present** in `codegraph.ts` now (future grep-absent goes red on current HEAD); `from '../db'` **absent** in `directory.ts` and **present** in the inverse `db/index.ts:12` (`from '../directory'`); `journal_mode = WAL` absent in `directory.ts`, present in `db/index.ts:33`; `busy_timeout = 500` absent in `directory.ts` now (grep-present is RED until step 2); `ignored with warning` present in UPDATING.md now.

## Discoveries

None that change the spec. HOW locks A–E are TypeScript/compile/test-import mechanics already implied by FCV (`require` in adapter; tests import `../src/directory`).
