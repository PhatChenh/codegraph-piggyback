# Plan: Bucket 5 — MCP tells missing vs empty vs usable
_Last updated: 2026-08-19_
_Status: [ ] pending_

Spec: `docs/AI_artifacts/4_specs/2026-08-19-bkt5-codegraph-mcp.md` (components 1–8). FCV: `docs/AI_artifacts/5_factual-code-verification/2026-08-19-bkt5-codegraph-mcp.md` (A1–A20 + S1–S6 ✅; **no** `## Invalidated Assumptions`). Design: `docs/AI_artifacts/3_design/2026-08-19-bkt5-codegraph-mcp.md`. Grill LOCKED. TD-01 stays OPEN. OQ-2 OPEN → implement **A** (re-probe every call). OQ-3 OPEN → do **not** expand.

## Analysis

This phase extends the local `codegraph/` fork MCP only (spec Constraint 10 / R15 shared binary). Two doors already exist and already disagree: session `handleInitialize`/`handleToolsList` gate on existence + engine-open; proxy `runLocalHandshakeProxy` always sends the full playbook + `getStaticTools()`. Cites live in ## Facts. Spec owns WHAT (mapping table, MUST-1/2/3, BT-*). This plan owns TDD order, exact signatures, **byte-static instruction strings**, and the list-payload one-liner that MUST-1 deep-equals.

**HOW lock A (one COUNT owner):** new `codegraph/src/mcp/index-state.ts` is the **only** `src/mcp/` caller of `probeIndexHealth`. Import from `../directory`, never `../index` barrel. Do not change `directory.ts`. OQ-2 A: **no cache field** — `resolveMcpIndexState(startPath)` re-walks + re-probes every call.

**HOW lock B (MUST-1 payload, not import):** session `handleToolsList` body is exactly: no `await`; `const resolved = resolveMcpIndexState(this.explicitProjectPath ?? process.cwd());` then `this.transport.sendResult(request.id, { tools: resolved.state === 'index_missing' ? [] : getStaticTools() });`. Do **not** use `getTools()`. Do **not** `await retryInitIfNeeded` / `ensureInitialized` / `hasDefaultCodeGraph` to decide the list. Keep `await this.retryInitIfNeeded()` on `handleToolsCall`. Keep `if (this.engine.hasDefaultCodeGraph()) return;` in `retryInitIfNeeded`. Keep `this.resolvePromise = this.engine.ensureInitialized(explicitPath);` **after** initialize `sendResult` — G-03; spies must not forbid that process-wide. Verbatim sites live in ## Facts.

**HOW lock C (MUST-3 / OQ-1 CLOSED A):** `instructionsForMcpIndex({ state, busy })` selects `SERVER_INSTRUCTIONS_INDEX_BUSY` (new) when `busy === true` **before** switching on `state`. Not a builder over EMPTY. Tests use `===` on the imported constant.

**HOW lock D (MUST-2):** `getCodeGraph` explicit arm calls `resolveMcpIndexState(projectPath)`, never raw `probeIndexHealth`. Throw+root → helper `usable` → existing `openSync`. Do not map throw → `index_missing` while a root exists. Do not “degrade to missing-behavior.” OQ-3: `openSync` throw still `errorResult` at `execute` `:1235`.

**HOW lock E (copy, exact user-visible strings — Bucket 4 lesson):** paste these bytes; do not paraphrase.

UNINDEXED (replace body; keep export name). MUST contain `no usable index`. MUST NOT contain `no \`.codegraph/\` directory`:

```
export const SERVER_INSTRUCTIONS_UNINDEXED = `# Codegraph — inactive (workspace not indexed)

This workspace has no usable index, so no
codegraph tools are available this session. Work with your built-in tools as
usual.

Indexing is the user's decision — do not run it yourself. If the user asks
about codegraph, they can enable it by running \`codegraph init\` in the
project root and starting a new session.
`;
```

EMPTY (new). MUST NOT contain `inactive this session` or `unavailable`. MUST name `codegraph init`. MUST NOT demand a new session for empty→usable (OQ-2 A: next `tools/list` re-probes):

```
export const SERVER_INSTRUCTIONS_INDEX_EMPTY = `# Codegraph — index is empty

This project's codegraph index exists but has 0 symbols. Tools stay listed; calls will return empty until the user runs \`codegraph init\` in the project root. Do not run init yourself.
`;
```

BUSY (new). Short “busy, retry later”. Exact `===` in tests:

```
export const SERVER_INSTRUCTIONS_INDEX_BUSY = `# Codegraph — index is busy

The codegraph index is busy (locked). Retry later. Do not run \`codegraph init\` yourself.
`;
```

`SERVER_INSTRUCTIONS` playbook **byte-unchanged**.

Junk `NotIndexedError` when `resolved.root !== null` (exact):

```
`The project at ${projectPath} isn't indexed with codegraph (no usable index ` +
'walking up from it), so codegraph cannot query it. Use your built-in tools (Read/Grep/Glob) ' +
"for that codebase instead, and don't call codegraph for it again this session. " +
"Indexing is the user's decision — they can run 'codegraph init' in that project to enable it."
```

When `resolved.root === null`, keep today’s absence string **verbatim** (`codegraph/src/mcp/tools.ts:874` quote: "`The project at ${projectPath} isn't indexed with codegraph (no .codegraph/ directory found `").

`emptyWarn`: `run \`codegraph init\` in this directory before exploring.` (drop `-i`).

Worktree `:89` / `:103`: `codegraph init -i` → `codegraph init` (keep surrounding words). Existing `codegraph/__tests__/worktree-detection.test.ts:103` quote: "`expect(msg).toContain('codegraph init');`" still passes with `-i` left in — Step 6 adds `not.toContain('init -i')`.

## Pre-dispatch audit

### 1. Consumer list per changed identifier

| Identifier | Consumers | Affected? |
|---|---|---|
| `initialize.result.instructions` | Cursor ACP + Claude MCP hosts; `mcp-initialize.test.ts` | YES — 4 constants via selector |
| `tools/list` | same hosts | YES — `[]` iff `index_missing`; else `getStaticTools()` both doors |
| `handleInitialize` / `handleToolsList` | `handleMessage` `:125,:131`; `CODEGRAPH_NO_DAEMON=1` | YES — mapper; list no await |
| `runLocalHandshakeProxy` local answers | `MCPServer.start` `:291` | YES — gate both `writeClient` payloads |
| `probeIndexHealth` | CLI `init` only today | NO CLI behavior change. MCP imports it in `index-state.ts` only |
| `isInitialized` / `findNearestCodeGraphRoot` | walk-up everywhere | NO semantics change |
| `getStaticTools` | proxy only today | YES — session list payload too |
| `ToolHandler.getTools` / `hasDefaultCodeGraph` | session list today | list **stops** using them; retry path **keeps** `hasDefaultCodeGraph` |
| `getCodeGraph` explicit arm | all `handle*` via `execute` | YES — helper; junk copy |
| `NotIndexedError` catch | `execute` `:1228` | shape kept (SUCCESS `textResult`) |
| `ensureInitialized` after initialize | `:216` | NO product change; stays legal |
| `daemon.ts` idle | daemon lifecycle | NO (CONSUMER-ONLY) |
| piggyback manifest / settings.json / hooks.json | harness install | NO (R15) |

### 2. Recorded command + output per scope claim

Carried from spec pre-dispatch (this FCV session re-Read the same lines; MCP tools still `mcp_auth` only). Session gate existence-only `:202`. Session list awaits engine `:221,:230`. Proxy unconditional playbook/tools `:298,:301`. Listen-first `:281` before `:324`. `probeIndexHealth` zero `src/mcp/` hits. `runProxy` definition-only.

### 3. One contradiction looked for and not found

No third initialize/`tools/list` door (`runProxy` has no caller). C1-a: `engine.ts:167` still no COUNT; `daemon.ts:60` is idle linger — **no A-split**. FCV A1–A20 all ✅.

## Facts (live-certified — do NOT re-derive)

- Proxy initialize is ungated playbook — (`codegraph/src/mcp/proxy.ts:298`) — quote: "`instructions: SERVER_INSTRUCTIONS } });`"
- Proxy tools/list is ungated static tools — (`codegraph/src/mcp/proxy.ts:301`) — quote: "`result: { tools: getStaticTools() } });`"
- Stdin listener precedes daemon await — (`codegraph/src/mcp/proxy.ts:281`) — quote: "`process.stdin.on('data', (chunk: string) => {`"
- Daemon socket await is later — (`codegraph/src/mcp/proxy.ts:324`) — quote: "`try { socket = await deps.getDaemonSocket(); } catch { socket = null; }`"
- Daemon initialize reply suppressed — (`codegraph/src/mcp/proxy.ts:344`) — quote: "`if (clientInitId !== undefined && resp.id === clientInitId) continue;`"
- `LocalHandshakeDeps` is injectable — (`codegraph/src/mcp/proxy.ts:180`) — quote: "`export interface LocalHandshakeDeps {`"
- `runLocalHandshakeProxy` never returns (hangs) — (`codegraph/src/mcp/proxy.ts:377`) — quote: "`await new Promise<void>(() => { /* stdin keeps the loop alive; exit via shutdown() */ });`"
- `runProxy` has no caller — (`codegraph/src/mcp/proxy.ts:83`) — quote: "`export async function runProxy(`"
- Session initialize existence gate — (`codegraph/src/mcp/session.ts:202`) — quote: "`const indexed = findNearestCodeGraphRoot(explicitPath ?? process.cwd()) !== null;`"
- `sendResult` before heavy init — (`codegraph/src/mcp/session.ts:204-216`) — quote: "`this.transport.sendResult(request.id, {`" / "`this.resolvePromise = this.engine.ensureInitialized(explicitPath);`"
- List awaits engine — (`codegraph/src/mcp/session.ts:221`) — quote: "`await this.retryInitIfNeeded();`"
- List keys on engine + `getTools` — (`codegraph/src/mcp/session.ts:230`) — quote: "`tools: this.engine.hasDefaultCodeGraph() ? this.engine.getToolHandler().getTools() : [],`"
- Call path awaits engine — (`codegraph/src/mcp/session.ts:258`) — quote: "`await this.retryInitIfNeeded();`"
- Call path execute — (`codegraph/src/mcp/session.ts:260`) — quote: "`const result = await this.engine.getToolHandler().execute(toolName, toolArgs);`"
- Retry null-check stays — (`codegraph/src/mcp/session.ts:281`) — quote: "`if (this.engine.hasDefaultCodeGraph()) return;`"
- `MCPSession` ctor takes transport + engine — (`codegraph/src/mcp/session.ts:92-96`) — quote: "`constructor(`" / "`private transport: JsonRpcTransport,`"
- `start()` binds `handleMessage` — (`codegraph/src/mcp/session.ts:105`) — quote: "`this.transport.start(this.handleMessage.bind(this));`"
- `JsonRpcTransport.sendResult` exists — (`codegraph/src/mcp/transport.ts:80`) — quote: "`sendResult(id: string | number, result: unknown): void;`"
- UNINDEXED claims missing directory — (`codegraph/src/mcp/server-instructions.ts:84`) — quote: "`This workspace has no codegraph index (no \`.codegraph/\` directory), so no`"
- `getStaticTools` has no budget suffix — (`codegraph/src/mcp/tools.ts:625-628`) — quote: "`export function getStaticTools(): ToolDefinition[] {`" / "`return tools.filter(t => DEFAULT_MCP_TOOLS.has(t.name.replace(/^codegraph_/, '')));`"
- Default surface is explore only — (`codegraph/src/mcp/tools.ts:645`) — quote: "`const DEFAULT_MCP_TOOLS = new Set(['explore']);`"
- `getTools` appends budget once `cg` set — (`codegraph/src/mcp/tools.ts:810`) — quote: "`Budget: make at most ${budget} calls for this project`"
- Availability is null-check — (`codegraph/src/mcp/tools.ts:728`) — quote: "`return this.cg !== null;`"
- Default-arm NotIndexedError — (`codegraph/src/mcp/tools.ts:833-834`) — quote: "`throw new NotIndexedError(`" / "`'No CodeGraph project is loaded for this session.\\n' +`"
- Explicit missing copy names directory — (`codegraph/src/mcp/tools.ts:874`) — quote: "`The project at ${projectPath} isn't indexed with codegraph (no .codegraph/ directory found `"
- Explicit open is `openSync` — (`codegraph/src/mcp/tools.ts:897`) — quote: "`const cg = loadCodeGraph().openSync(resolvedRoot);`"
- Recoverable ≠ `isError` — (`codegraph/src/mcp/tools.ts:1228-1229`) — quote: "`if (err instanceof NotIndexedError) {`" / "`return this.textResult(err.message);`"
- Generic execute failure is `errorResult` — (`codegraph/src/mcp/tools.ts:1235-1236`) — quote: "`return this.errorResult(`" / "`\`Tool execution failed: ${err instanceof Error ? err.message : String(err)}. \` +`"
- emptyWarn stale `init -i` — (`codegraph/src/mcp/tools.ts:2276`) — quote: "`codegraph init -i` in this directory before exploring"
- Engine open has no 0-node reject — (`codegraph/src/mcp/engine.ts:167`) — quote: "`this.cg = await loadCodeGraph().open(resolvedRoot);`"
- Engine `hasDefaultCodeGraph` delegates — (`codegraph/src/mcp/engine.ts:82-83`) — quote: "`hasDefaultCodeGraph(): boolean {`" / "`return this.toolHandler.hasDefaultCodeGraph();`"
- No-root → direct — (`codegraph/src/mcp/index.ts:281`) — quote: "`return this.startDirect('no .codegraph/ root found');`"
- Production proxy entry — (`codegraph/src/mcp/index.ts:291`) — quote: "`await this.runProxyWithLocalHandshake(root);`"
- `resolveDaemonRoot` is walk-only — (`codegraph/src/mcp/index.ts:160`) — quote: "`const root = findNearestCodeGraphRoot(candidate);`"
- Daemon poll ~6s — (`codegraph/src/mcp/index.ts:101-102`) — quote: "`const DAEMON_CONNECT_MAX_RETRIES = 240;`" / "`const DAEMON_CONNECT_RETRY_DELAY_MS = 25;`"
- Daemon idle is CONSUMER-ONLY — (`codegraph/src/mcp/daemon.ts:60`) — quote: "`const DEFAULT_IDLE_TIMEOUT_MS = 300_000;`"
- Probe require outside try — (`codegraph/src/directory.ts:123`) — quote: "`const { DatabaseSync } = require('node:sqlite') as {`"
- Probe try starts after require — (`codegraph/src/directory.ts:130-133`) — quote: "`try {`" / "`db = new DatabaseSync(dbPath, { readOnly: true });`"
- Probe COUNT + 500ms — (`codegraph/src/directory.ts:132-133`) — quote: "`db.exec('PRAGMA busy_timeout = 500');`" / "`const row = db.prepare('SELECT COUNT(*) AS n FROM nodes').get() as { n: number };`"
- `isInitialized` existence-only — (`codegraph/src/directory.ts:100`) — quote: "`return fs.existsSync(dbPath);`"
- Engine busy_timeout 5s — (`codegraph/src/db/index.ts:31`) — quote: "`db.pragma('busy_timeout = 5000');      // MUST be first — see above`"
- Node floor 20 — (`codegraph/src/bin/node-version-check.ts:48`) — quote: "`export const MIN_NODE_MAJOR = 20;`"
- Engines range — (`codegraph/package.json:54`) — quote: "`"node": ">=20.0.0 <25.0.0"`"
- `serve --mcp` constructs MCPServer — (`codegraph/src/bin/codegraph.ts:1597-1599`) — quote: "`const { MCPServer } = await import('../mcp/index');`" / "`const server = new MCPServer(projectPath);`"
- Installer does not set NO_DAEMON — (`codegraph/src/installer/targets/shared.ts:28`) — quote: "`args: ['serve', '--mcp'],`"
- Cursor adds `--path` only — (`codegraph/src/installer/targets/cursor.ts:173`) — quote: "`const pathArg = loc === 'local' ? process.cwd() : '${workspaceFolder}';`"
- Tests pin direct mode — (`codegraph/__tests__/mcp-initialize.test.ts:33`) — quote: "`env: { ...process.env, CODEGRAPH_NO_DAEMON: '1' },`"
- Watcher-seq is not BT-3 — (`codegraph/__tests__/mcp-initialize.test.ts:151`) — quote: "`expect(response.seq).toBeLessThan(watcherLog.seq);`"
- Probe tests skip without node:sqlite — (`codegraph/__tests__/probe-index-health.test.ts:13`) — quote: "`* Skipped on Node < 22.5 where node:sqlite doesn't exist.`"
- ADR 0001 MCP carve-out — (`codegraph/docs/adr/0001-init-repairs-unusable-index.md:72`) — quote: "`**not** imported by `src/mcp/**`. Its raw `node:sqlite` read-only`"
- Worktree warning `init -i` — (`codegraph/src/sync/worktree.ts:89`) — quote: "`Run "codegraph init -i" in this worktree `"
- Worktree notice `init -i` — (`codegraph/src/sync/worktree.ts:103`) — quote: "`Run "codegraph init -i" here for a `"
- Worktree test substring is too weak — (`codegraph/__tests__/worktree-detection.test.ts:103`) — quote: "`expect(msg).toContain('codegraph init');`"
- `npm test` is vitest — (`codegraph/package.json:21`) — quote: "`vitest run`"
- CHANGELOG Unreleased — (`codegraph/CHANGELOG.md:10`) — quote: "`## [Unreleased]`"
- TD-01 stays OPEN — (`docs/TECH_DEBT.md:5`) — quote: "`### TD-01 · No post-`codegraph init` completion hook for consumers`"
- Barrel does not export probe — FCV: `rg probeIndexHealth codegraph/src/index.ts` empty this session.

## Files

- `codegraph/src/mcp/server-instructions.ts` — reword UNINDEXED; add EMPTY + BUSY + `instructionsForMcpIndex`
- `codegraph/src/mcp/index-state.ts` — **create** `McpIndexState` + `resolveMcpIndexState`
- `codegraph/src/mcp/session.ts` — mapper + static list; rewrite existsSync comment; keep call-path await + `:216` kick
- `codegraph/src/mcp/proxy.ts` — mapper both handshake writes; keep listen-first + `:344`
- `codegraph/src/mcp/tools.ts` — `getCodeGraph` helper; emptyWarn `codegraph init`
- `codegraph/src/sync/worktree.ts` — two `init -i` → `codegraph init`
- `codegraph/__tests__/mcp-server-instructions.test.ts` — **create** selector + copy pins
- `codegraph/__tests__/mcp-index-state.test.ts` — **create** mapping table + probe spy + throw fallback
- `codegraph/__tests__/mcp-session-index-state.test.ts` — **create** MUST-1/MUST-3/BT-2/BT-6 in-process
- `codegraph/__tests__/mcp-proxy-handshake.test.ts` — **create** BT-1/BT-1b/m2 stub-deps
- `codegraph/__tests__/mcp-getcodegraph-index-state.test.ts` — **create** MUST-2 execute fixture
- `codegraph/__tests__/mcp-initialize.test.ts` — add BT-3 spy; **keep** watcher-seq
- `codegraph/__tests__/worktree-detection.test.ts` — `not.toContain('init -i')` on warning + notice
- `codegraph/docs/adr/0002-mcp-index-tri-state.md` — **create**
- `codegraph/UPDATING.md` — patch-table row
- `codegraph/CHANGELOG.md` — `[Unreleased]` user-facing bullet

## Delegation Authority

- **Allowed set** = the union of every step's "Files to modify" (= ## Files). Nothing outside it.
- A file in ## Files assigned to ANOTHER step = a dependency (run per ## Implementation Order), not a deviation.
- A file NOT in ## Files → STOP, don't silently edit. Record in an `### Out-of-scope touches` block of the end-of-implementation report (file, why the step needed it, the change, whether it signals a plan/spec gap).
- **Hard off-limits (escalate before touching):** `codegraph/src/directory.ts` (probe body / `isInitialized`); `codegraph/src/mcp/engine.ts`; `codegraph/src/mcp/daemon.ts`; `codegraph/src/index.ts` barrel; `codegraph/src/installer/**` (esp. `targets/cursor.ts`); `codegraph/src/bin/node-version-check.ts` (`MIN_NODE_MAJOR` stays 20); `codegraph/src/bin/codegraph.ts` CLI `init` dispatch; `.codegraph/ready`; plugin bus; `site/`; historical CHANGELOG bodies; markdown docs except the two fork files in ## Files; piggyback Python tools; `settings.json` / `hooks.json` / `mcp.json`; `CLAUDE.md` / `STATE.md` / `docs/TECH_DEBT.md` (TD-01 OPEN); `npm install -g` / `codegraph upgrade`.
- **Escalate, don't improvise (verbatim — copy into the plan):** *If a test cannot pass without violating this plan's design, STOP and report it. Do not improvise a fix and do not revert anything.*

## Rules Applied

No matching rules (no WRIT `PROJ-*` / `--- WRIT RULES ---` block in this dispatch). Binding MUSTs: spec MUST-1/2/3 + Constraints 1–14.

## Capabilities

- [ ] C1 — `instructionsForMcpIndex({state:'index_empty', busy:true}) === SERVER_INSTRUCTIONS_INDEX_BUSY`; UNINDEXED contains `no usable index` and not `no \`.codegraph/\` directory`; EMPTY lacks `inactive this session`
- [ ] C2 — `resolveMcpIndexState` maps the spec table; spy: `probeIndexHealth` called when a root exists; throw+root → `usable`; throw+no root → `index_missing`; busy → `{state:'index_empty', busy:true}`; `rg` `probeIndexHealth` under `src/mcp/` **only** in `index-state.ts`
- [ ] C3 — MUST-1: session `tools/list` **deep-equals** `getStaticTools()` (full `ToolDefinition[]`, not names) on busy **and** empty; list path did not await `retryInitIfNeeded`/`ensureInitialized`; process **may** have started `ensureInitialized` from initialize
- [ ] C4 — MUST-3: busy fixture `initialize.result.instructions === SERVER_INSTRUCTIONS_INDEX_BUSY`
- [ ] C5 — BT-1 full stdout table on stub-deps; busy copy `===` imported BUSY; BT-1b initialize while `getDaemonSocket` pending; `resolveMcpIndexState` call-count ≥ 2 on initialize+list
- [ ] C6 — BT-2: missing **and** junk → `tools: []` + UNINDEXED content; empty-db → nonempty static tools + EMPTY; mapper calls probe when root exists
- [ ] C7 — BT-3: usable fixture — `CodeGraph.open` / `openSync` / `Parser.init` **not** invoked before initialize `sendResult`/`writeClient`; watcher-seq test still present
- [ ] C8 — MUST-2: stub probe throw + `projectPath` at a real root → execute does **not** NotIndexedError “isn't indexed”; open path runs
- [ ] C9 — BT-4: `tools.ts` + `worktree.ts` have `codegraph init` and no `init -i`
- [ ] C10 — BT-6: throw+root → full `SERVER_INSTRUCTIONS` + nonempty `getStaticTools()`; throw+no root → `[]` + reworded UNINDEXED; `MIN_NODE_MAJOR = 20` unchanged
- [ ] C11 — UPDATING row names `probeIndexHealth` + `src/mcp`; CHANGELOG `[Unreleased]` user-facing missing/empty/usable sentence; ADR 0002 exists; version stays `999.0.0` live / package `1.0.1`

## Implementation Order

codegraph this session: `getStaticTools` callers = proxy only (session will join). `handleInitialize` ← `handleMessage`. `runLocalHandshakeProxy` ← `runProxyWithLocalHandshake`. `getCodeGraph` ← handle* inside `execute`. `probeIndexHealth` ← CLI only until Step 2. Verbatim caller sites live in ## Facts.

**Dependency table:**

| Step | Produces | Depends on | Why |
|---|---|---|---|
| 1 | 4 instruction constants + selector | none | spec C1 |
| 2 | mapper | 1 (pairing tests only; compile-free of selector) | sole `probeIndexHealth` owner |
| 3 | session door | 1, 2 | `handleInitialize`/`handleToolsList` import mapper+selector+`getStaticTools` |
| 4 | proxy door | 1, 2 | both `writeClient` paths call mapper (m2 ≥2) |
| 5 | `getCodeGraph` + emptyWarn | 2 | explicit arm helper; MUST-2 |
| 6 | worktree copy | none | disjoint from 1–5 |
| 7 | spawn BT-3 + keep watcher-seq | 3 | BIN spawn hits session door |
| 8 | ADR/UPDATING/CHANGELOG | 2 | documents the mcp→directory edge |

**Parallel waves:** Wave A: Steps 1 + 6. Wave B: Step 2. Wave C: Steps 3 + 4 + 5 (disjoint files). Wave D: Step 7. Wave E: Step 8 (may start after 2).
**Critical path:** 1 → 2 → 3 → 7. Solo linear: 1, 6, 2, 3, 4, 5, 7, 8.

## Steps

### Step 1 — Instruction constants + selector
**Goal**: Spec component 1 — four byte-static strings; busy cannot collapse into empty copy.
**Design** (imperative — decision already made, no design freedom): Edit `codegraph/src/mcp/server-instructions.ts`. Replace `SERVER_INSTRUCTIONS_UNINDEXED` with HOW lock E UNINDEXED bytes. Add `SERVER_INSTRUCTIONS_INDEX_EMPTY` (new) and `SERVER_INSTRUCTIONS_INDEX_BUSY` (new) with HOW lock E bytes. Add `export function instructionsForMcpIndex(r: { state: 'index_missing' | 'index_empty' | 'usable'; busy: boolean }): string` — if `r.busy` return BUSY; else switch `usable`→`SERVER_INSTRUCTIONS`, `index_empty`→EMPTY, `index_missing`→UNINDEXED. Do not import sqlite. Do not edit `SERVER_INSTRUCTIONS` body.
**Actions**: 1. Write `codegraph/__tests__/mcp-server-instructions.test.ts` **first** (TDD): `instructionsForMcpIndex({state:'index_empty', busy:true}) === SERVER_INSTRUCTIONS_INDEX_BUSY` (new); `{state:'index_empty', busy:false} === SERVER_INSTRUCTIONS_INDEX_EMPTY` (new); `{state:'usable', busy:false} === SERVER_INSTRUCTIONS`; `SERVER_INSTRUCTIONS_UNINDEXED` `toContain('no usable index')` and `not.toContain('no `.codegraph/` directory')`; EMPTY `not.toContain('inactive this session')` and `toContain('codegraph init')`; BUSY `toContain('Retry later')`. 2. Replace `SERVER_INSTRUCTIONS_UNINDEXED`; add `SERVER_INSTRUCTIONS_INDEX_EMPTY` (new), `SERVER_INSTRUCTIONS_INDEX_BUSY` (new), and `instructionsForMcpIndex` as HOW lock E. 3. Run the test command.
**Files to modify**:
- `codegraph/__tests__/mcp-server-instructions.test.ts` — create
- `codegraph/src/mcp/server-instructions.ts` — UNINDEXED reword; EMPTY; BUSY; selector

<!-- plan-verify
touch: codegraph/src/mcp/server-instructions.ts::SERVER_INSTRUCTIONS_UNINDEXED
new:   codegraph/src/mcp/server-instructions.ts::SERVER_INSTRUCTIONS_INDEX_EMPTY
new:   codegraph/src/mcp/server-instructions.ts::SERVER_INSTRUCTIONS_INDEX_BUSY
new:   codegraph/src/mcp/server-instructions.ts::instructionsForMcpIndex
tier: B
qualifiers: grep-present "no usable index" codegraph/src/mcp/server-instructions.ts
qualifiers: grep-absent "no `.codegraph/` directory" codegraph/src/mcp/server-instructions.ts
qualifiers: grep-present "inactive this session" codegraph/src/mcp/server-instructions.ts
qualifiers: byte-unchanged codegraph/src/directory.ts
-->

**Test criteria**: - [ ] `npx vitest run __tests__/mcp-server-instructions.test.ts` pass. EMPTY file still contains `inactive this session` **only** inside UNINDEXED (qualifier grep-present is the missing-state copy; EMPTY test forbids that substring on the EMPTY constant).
**Do not regress**: UNINDEXED still tells the agent not to self-init (`codegraph init` user-run). G-09.
**Report contract**: on done, report the literal test command run (copy-paste exact, e.g. `npx vitest run __tests__/mcp-server-instructions.test.ts`), its pass/fail tail, files touched, any `### Out-of-scope touches`; end with the sentinel line `END`. The orchestrator greps every claim against the diff — an unverifiable/truncated claim fails the step. Don't paraphrase the command; paste it.
**Status**: [ ] pending

### Step 2 — Mapper `index-state.ts`
**Goal**: Spec component 2 — one owner of walk → probe → throw-guard → 5→3 map.
**Design**: Create `codegraph/src/mcp/index-state.ts`. `export type McpIndexState = 'index_missing' | 'index_empty' | 'usable'`. `export function resolveMcpIndexState(startPath: string): { state: McpIndexState; busy: boolean; root: string | null }`. `const root = findNearestCodeGraphRoot(startPath)`; if `!root` return `{ state:'index_missing', busy:false, root:null }`. `try { const health = probeIndexHealth(root); }` — map `usable`→`{state:'usable', busy:false, root}`; `empty`→`{state:'index_empty', busy:false, root}`; `busy`→`{state:'index_empty', busy:true, root}`; `unreadable`/`unclassified`→`{state:'index_missing', busy:false, root}`. `catch` → `{ state:'usable', busy:false, root }` (**never** missing while root exists). Import `findNearestCodeGraphRoot, probeIndexHealth` from `../directory`. No import from `../index`. No cache. `busy===true` only with `state==='index_empty'`.
**Actions**: 1. Write `codegraph/__tests__/mcp-index-state.test.ts` **first**. Reuse probe fixture recipes (junk text errcode 26, empty COUNT=0, usable nodes>0, busy if the suite can lock; else stub `probeIndexHealth` returning `{status:'busy'}`). Spy: when root fixture exists, `probeIndexHealth` is invoked. Throw stub + root → `state==='usable'`. Throw stub + missing dir → `index_missing`. 2. Create `codegraph/src/mcp/index-state.ts` exporting `McpIndexState` and `resolveMcpIndexState` as Design. 3. Run tests.
**Files to modify**:
- `codegraph/__tests__/mcp-index-state.test.ts` — create
- `codegraph/src/mcp/index-state.ts` — create

<!-- plan-verify
new:   codegraph/src/mcp/index-state.ts::McpIndexState
new:   codegraph/src/mcp/index-state.ts::resolveMcpIndexState
tier: B
qualifiers: grep-present "probeIndexHealth" codegraph/src/mcp/index-state.ts
qualifiers: grep-absent "from '../index'" codegraph/src/mcp/index-state.ts
qualifiers: byte-unchanged codegraph/src/directory.ts
qualifiers: byte-unchanged codegraph/src/index.ts
-->

**Test criteria**: - [ ] `npx vitest run __tests__/mcp-index-state.test.ts` pass.
**Do not regress**: Bucket 4 CLI `probeIndexHealth` dispatch (`codegraph.ts:597`) — do not edit `directory.ts` / CLI init.
**Report contract**: on done, report the literal test command run (copy-paste exact, e.g. `npx vitest run __tests__/mcp-index-state.test.ts`), its pass/fail tail, files touched, any `### Out-of-scope touches`; end with the sentinel line `END`. The orchestrator greps every claim against the diff — an unverifiable/truncated claim fails the step. Don't paraphrase the command; paste it.
**Status**: [ ] pending

### Step 3 — Session door
**Goal**: Spec component 3 — direct-mode initialize + tools/list follow the mapping table without waiting on the engine for the list (MUST-1, MUST-3).
**Design**: `session.ts`: import `resolveMcpIndexState` from `./index-state`, `instructionsForMcpIndex` + keep `SERVER_INSTRUCTIONS` unused if selector covers it (may drop direct `SERVER_INSTRUCTIONS` import if unused), import `getStaticTools` from `./tools`. Replace `const indexed = …` with `const resolved = resolveMcpIndexState(explicitPath ?? process.cwd());` then `instructions: instructionsForMcpIndex(resolved)`. Keep `sendResult` **before** `if (explicitPath) { this.resolvePromise = this.engine.ensureInitialized(explicitPath); }`. `handleToolsList`: **delete** `await this.retryInitIfNeeded();`. Re-resolve `resolveMcpIndexState(this.explicitProjectPath ?? process.cwd())`. Payload: `{ tools: resolved.state === 'index_missing' ? [] : getStaticTools() }`. Rewrite the `:192-201` comment to: COUNT-before-reply via mapper; heavy `ensureInitialized` stays after `sendResult` (#172). Leave `handleToolsCall` + `retryInitIfNeeded` + `hasDefaultCodeGraph` intact. `explicitPath` for initialize mapper is `explicitPath ?? process.cwd()` (same as today’s indexed line). For list, `this.explicitProjectPath ?? process.cwd()` — do **not** invent a `roots/list` startPath for the handshake (FCV A19). Parity tests that compare to proxy must set session startPath **equal** to `deps.root` (spec m4).
**Actions**: 1. Write `codegraph/__tests__/mcp-session-index-state.test.ts` **first**. Stub `JsonRpcTransport`: record `sendResult` ids+payloads; `start(handler)` stores handler; test calls `handler({jsonrpc:'2.0', id:1, method:'initialize', params:{rootUri:'file://'+fixture}})`. Stub `MCPEngine`: spy `ensureInitialized` (may be called after initialize — legal); spy `hasDefaultCodeGraph` / `getToolHandler().getTools` — MUST-1 fails if list equals `getTools()` or if list waited on a pending `ensureInitialized` (use a never-resolving `ensureInitialized` after initialize and assert `tools/list` still returns immediately with `getStaticTools()`). Busy fixture: `initialize` result `instructions === SERVER_INSTRUCTIONS_INDEX_BUSY`. Empty: instructions === EMPTY, tools deep-equals `getStaticTools()`. Missing/junk: tools `[]`, instructions contain `no usable index`. Throw stub + root: instructions === `SERVER_INSTRUCTIONS`, tools deep-equals `getStaticTools()`. 2. Edit `handleInitialize` and `handleToolsList` in `session.ts` as Design. 3. Run tests.
**Files to modify**:
- `codegraph/__tests__/mcp-session-index-state.test.ts` — create
- `codegraph/src/mcp/session.ts` — mapper, static list, comment

<!-- plan-verify
touch: codegraph/src/mcp/session.ts::handleInitialize
touch: codegraph/src/mcp/session.ts::handleToolsList
tier: A
qualifiers: grep-present "getStaticTools()" codegraph/src/mcp/session.ts
qualifiers: grep-present "resolved.state === 'index_missing' ? [] : getStaticTools()" codegraph/src/mcp/session.ts
qualifiers: grep-present "await this.retryInitIfNeeded()" codegraph/src/mcp/session.ts
qualifiers: grep-present "if (this.engine.hasDefaultCodeGraph()) return;" codegraph/src/mcp/session.ts
qualifiers: grep-present "this.engine.ensureInitialized(explicitPath)" codegraph/src/mcp/session.ts
qualifiers: byte-unchanged codegraph/src/mcp/engine.ts
-->

**Test criteria**: - [ ] `npx vitest run __tests__/mcp-session-index-state.test.ts` pass. MUST-1 uses `expect(tools).toEqual(getStaticTools())` not `.map(t => t.name)`.
**Do not regress**: #172 `sendResult` before `ensureInitialized`. Recoverable ≠ `isError`. Do not `grep-absent hasDefaultCodeGraph` the whole file.
**Report contract**: on done, report the literal test command run (copy-paste exact, e.g. `npx vitest run __tests__/mcp-session-index-state.test.ts`), its pass/fail tail, files touched, any `### Out-of-scope touches`; end with the sentinel line `END`. The orchestrator greps every claim against the diff — an unverifiable/truncated claim fails the step. Don't paraphrase the command; paste it.
**Status**: [ ] pending

### Step 4 — Proxy door
**Goal**: Spec component 4 — live local-handshake same table from `deps.root` without waiting for the daemon.
**Design**: `proxy.ts` initialize branch (`:289-298`) and tools/list branch (`:300-301`) each call `resolveMcpIndexState(deps.root)` (separate calls; m2 ≥ 2 on initialize+list). Instructions = `instructionsForMcpIndex(resolved)`. Tools = `resolved.state === 'index_missing' ? [] : getStaticTools()`. Keep listen-first (`:281` before `:324`), daemon-init suppression (`:344`), `handleLocally` fallback. Do not `await getDaemonSocket` before attaching stdin. Tests must **not** `await runLocalHandshakeProxy(...)` to completion — it hangs (`:377`). Pattern: start the promise; `process.stdin.emit('data', line+'\n')`; spy `process.stdout.write`; stub `process.exit` (shutdown). `getDaemonSocket` for BT-1b = `new Promise(() => {})` (never settles during asserts).
**Actions**: 1. Write `codegraph/__tests__/mcp-proxy-handshake.test.ts` **first** (BT-1 table, BT-1b pending socket, m2 call-count spy on `resolveMcpIndexState` ≥ 2). No live daemon. 2. Edit `runLocalHandshakeProxy` initialize + tools/list `writeClient` gates as Design. 3. Run tests.
**Files to modify**:
- `codegraph/__tests__/mcp-proxy-handshake.test.ts` — create
- `codegraph/src/mcp/proxy.ts` — both handshake writes

<!-- plan-verify
touch: codegraph/src/mcp/proxy.ts::runLocalHandshakeProxy
tier: A
qualifiers: grep-present "resolveMcpIndexState" codegraph/src/mcp/proxy.ts
qualifiers: grep-present "getStaticTools()" codegraph/src/mcp/proxy.ts
qualifiers: byte-unchanged codegraph/src/mcp/daemon.ts
-->

**Test criteria**: - [ ] `npx vitest run __tests__/mcp-proxy-handshake.test.ts` pass. Busy instructions `=== SERVER_INSTRUCTIONS_INDEX_BUSY`. Immediate-null socket does **not** satisfy BT-1b.
**Do not regress**: #172 listen-first; daemon initialize suppression `:344`.
**Report contract**: on done, report the literal test command run (copy-paste exact, e.g. `npx vitest run __tests__/mcp-proxy-handshake.test.ts`), its pass/fail tail, files touched, any `### Out-of-scope touches`; end with the sentinel line `END`. The orchestrator greps every claim against the diff — an unverifiable/truncated claim fails the step. Don't paraphrase the command; paste it.
**Status**: [ ] pending

### Step 5 — `getCodeGraph` + emptyWarn
**Goal**: Spec component 5 — explicit-path health uses the helper; handshake throw-fallback is not undone on the first tool call; stale `init -i` gone from explore emptyWarn.
**Design**: `getCodeGraph` explicit arm after path-refusal checks: `const resolved = resolveMcpIndexState(projectPath)` (not `probeIndexHealth`). If `resolved.state === 'index_missing'`: if `resolved.root === null` throw today’s absence `NotIndexedError` **verbatim** (## Facts explicit-missing copy); else throw HOW lock E junk copy (`no usable index`, **not** `no .codegraph/ directory found`). If not missing, keep existing default-reuse / cache / `openSync` path. `emptyWarn` (## Facts emptyWarn line): drop `-i`. Do not catch `openSync` into NotIndexedError (OQ-3 stays OPEN). Import mapper from `./index-state`.
**Actions**: 1. Write `codegraph/__tests__/mcp-getcodegraph-index-state.test.ts` **first**. MUST-2: real temp root with `.codegraph/` (empty nodes db via probe fixture `makeDbWithNodes(0)` or `CodeGraph.init`); `vi.spyOn` `probeIndexHealth` to throw; `new ToolHandler(null).execute('codegraph_explore', { query: 'x', projectPath: root })`; assert result text does **not** include `isn't indexed` and does **not** include `no .codegraph/ directory found`. Junk file at db path: execute → SUCCESS-shaped (`isError` falsy) NotIndexedError text contains `no usable index`. emptyWarn in `handleExplore`: 0-node explore contains `codegraph init` and not `init -i`. 2. Edit `getCodeGraph` explicit arm + `handleExplore` emptyWarn as Design. 3. Run tests.
**Files to modify**:
- `codegraph/__tests__/mcp-getcodegraph-index-state.test.ts` — create
- `codegraph/src/mcp/tools.ts` — helper on explicit arm; emptyWarn

<!-- plan-verify
touch: codegraph/src/mcp/tools.ts::getCodeGraph
touch: codegraph/src/mcp/tools.ts::handleExplore
tier: A
qualifiers: grep-present "resolveMcpIndexState" codegraph/src/mcp/tools.ts
qualifiers: grep-absent "init -i" codegraph/src/mcp/tools.ts
qualifiers: grep-absent "degrade to missing-behavior" codegraph/src/mcp
-->

**Test criteria**: - [ ] `npx vitest run __tests__/mcp-getcodegraph-index-state.test.ts` pass.
**Do not regress**: NotIndexedError → `textResult` (`:1228`). Default-arm missing copy. PathRefusalError still `isError`.
**Report contract**: on done, report the literal test command run (copy-paste exact, e.g. `npx vitest run __tests__/mcp-getcodegraph-index-state.test.ts`), its pass/fail tail, files touched, any `### Out-of-scope touches`; end with the sentinel line `END`. The orchestrator greps every claim against the diff — an unverifiable/truncated claim fails the step. Don't paraphrase the command; paste it.
**Status**: [ ] pending

### Step 6 — Worktree copy lock
**Goal**: Spec component 6 — MCP-served worktree strings name `codegraph init`.
**Design**: Replace the two MCP-served strings (## Facts worktree warning + notice) — `codegraph init -i` → `codegraph init`, keep surrounding words. Do not rewrite `site/` / docs / historical CHANGELOG.
**Actions**: 1. In `worktree-detection.test.ts` add `expect(msg).not.toContain('init -i')` beside `:103`; same for `worktreeMismatchNotice`. 2. Edit `worktreeMismatchWarning` and `worktreeMismatchNotice` strings (`init -i` → `codegraph init`). 3. Run tests.
**Files to modify**:
- `codegraph/src/sync/worktree.ts` — two copy sites
- `codegraph/__tests__/worktree-detection.test.ts` — `not.toContain('init -i')`

<!-- plan-verify
touch: codegraph/src/sync/worktree.ts::worktreeMismatchWarning
touch: codegraph/src/sync/worktree.ts::worktreeMismatchNotice
tier: B
qualifiers: grep-present "codegraph init" codegraph/src/sync/worktree.ts
qualifiers: grep-absent "init -i" codegraph/src/sync/worktree.ts
-->

**Test criteria**: - [ ] `npx vitest run __tests__/worktree-detection.test.ts` pass.
**Do not regress**: issue #155 mismatch detection logic — only the two user-visible strings change.
**Report contract**: on done, report the literal test command run (copy-paste exact, e.g. `npx vitest run __tests__/worktree-detection.test.ts`), its pass/fail tail, files touched, any `### Out-of-scope touches`; end with the sentinel line `END`. The orchestrator greps every claim against the diff — an unverifiable/truncated claim fails the step. Don't paraphrase the command; paste it.
**Status**: [ ] pending

### Step 7 — Spawn BT-3 + keep watcher-seq
**Goal**: Spec component 7 remainder — BT-3 spy on usable-db spawn; do not treat watcher-seq as BT-3.
**Design**: Extend `mcp-initialize.test.ts`. Keep existing watcher-seq test (`:151`). Add usable-db test: spy/hook `CodeGraph.open` / `loadCodeGraph().openSync` / `Parser.init` (or stderr-independent module spies) and assert they were **not** called before the initialize JSON appeared on stdout. Pin is COUNT not `open`, **not** a ≤500ms wall. Keep `CODEGRAPH_NO_DAEMON: '1'` and BIN spawn. Do not spawn a live daemon (OQ-4 CLOSED A).
**Actions**: 1. Keep `spawnServer` as-is (`CODEGRAPH_NO_DAEMON: '1'`). Add the BT-3 test (fails if handshake awaits `open` before `sendResult`). 2. Run this file.
**Files to modify**:
- `codegraph/__tests__/mcp-initialize.test.ts` — BT-3 spy; keep watcher-seq

<!-- plan-verify
touch: codegraph/__tests__/mcp-initialize.test.ts::spawnServer
tier: B
qualifiers: grep-present "expect(response.seq).toBeLessThan(watcherLog.seq)" codegraph/__tests__/mcp-initialize.test.ts
qualifiers: grep-present "MIN_NODE_MAJOR = 20" codegraph/src/bin/node-version-check.ts
qualifiers: byte-unchanged codegraph/src/bin/node-version-check.ts
-->

**Test criteria**: - [ ] `npx vitest run __tests__/mcp-initialize.test.ts` pass.
**Do not regress**: #172 watcher-seq; BIN `serve --mcp`; `CODEGRAPH_NO_DAEMON=1`.
**Report contract**: on done, report the literal test command run (copy-paste exact, e.g. `npx vitest run __tests__/mcp-initialize.test.ts`), its pass/fail tail, files touched, any `### Out-of-scope touches`; end with the sentinel line `END`. The orchestrator greps every claim against the diff — an unverifiable/truncated claim fails the step. Don't paraphrase the command; paste it.
**Status**: [ ] pending

### Step 8 — Fork survival + ADR
**Goal**: Spec component 8 — upstream merge sees mcp→directory edge; 5→3 map recorded.
**Design**: `UPDATING.md` patch-table: new row `MCP mapper imports probeIndexHealth, maps CLI 5-arm → MCP 3-arm (missing/empty/usable; busy→empty-style)` files `src/mcp/index-state.ts`, `src/mcp/session.ts`, `src/mcp/proxy.ts`. `CHANGELOG.md` `[Unreleased]` **Fixes** (or New Features) one user-facing sentence: handshake now tells missing vs empty vs usable (no internal paths). Create `codegraph/docs/adr/0002-mcp-index-tri-state.md`: Option A, mapping table, throw→existence, `getStaticTools()` as nonempty list, TD-01 still OPEN, cite ADR 0001 `:76-77` carve-out. Do **not** amend ADR 0001’s repair table. Do not change `package.json` version. Live binary stays `999.0.0`.
**Actions**: 1. Write ADR `0002` at `codegraph/docs/adr/0002-mcp-index-tri-state.md`. 2. Add the patch-table row in `codegraph/UPDATING.md`. 3. Add the `[Unreleased]` bullet in `codegraph/CHANGELOG.md`.
**Files to modify**:
- `codegraph/docs/adr/0002-mcp-index-tri-state.md` — create
- `codegraph/UPDATING.md` — patch row
- `codegraph/CHANGELOG.md` — Unreleased bullet

<!-- plan-verify
new:   codegraph/docs/adr/0002-mcp-index-tri-state.md::0002
touch: codegraph/UPDATING.md
touch: codegraph/CHANGELOG.md
tier: C
qualifiers: grep-present "probeIndexHealth" codegraph/UPDATING.md
qualifiers: grep-present "src/mcp" codegraph/UPDATING.md
qualifiers: grep-present "## [Unreleased]" codegraph/CHANGELOG.md
-->

**Test criteria**: - [ ] Files exist with the greps above. No version bump.
**Do not regress**: G-07 fork survival; never `npm upgrade`.
**Report contract**: on done, report the literal test command run (copy-paste exact, e.g. `grep -n probeIndexHealth codegraph/UPDATING.md codegraph/src/mcp/index-state.ts`), its pass/fail tail, files touched, any `### Out-of-scope touches`; end with the sentinel line `END`. The orchestrator greps every claim against the diff — an unverifiable/truncated claim fails the step. Don't paraphrase the command; paste it.
**Status**: [ ] pending

## E2E Done Criteria

**Prerequisites:** built `codegraph/dist/bin/codegraph.js`; Node ≥20; vitest; no second ORCH-operated live cert (R4-a = vitest spawn).
**Walkthrough** (map to Capabilities):
1. `npx vitest run __tests__/mcp-server-instructions.test.ts __tests__/mcp-index-state.test.ts __tests__/mcp-session-index-state.test.ts __tests__/mcp-proxy-handshake.test.ts __tests__/mcp-getcodegraph-index-state.test.ts __tests__/mcp-initialize.test.ts __tests__/worktree-detection.test.ts` → observe all pass → C1–C10.
2. Session busy fixture: `initialize.instructions === SERVER_INSTRUCTIONS_INDEX_BUSY` and `tools/list` deep-equals `getStaticTools()` → C3, C4.
3. Proxy stub-deps: initialize on stdout while `getDaemonSocket` pending → C5.
4. Junk fixture: `tools: []` and UNINDEXED contains `no usable index` not missing-directory claim → C6.
5. MUST-2 execute: throw+root does not print `isn't indexed` → C8.
6. `rg -n "init -i" codegraph/src/mcp/tools.ts codegraph/src/sync/worktree.ts` empty → C9.
7. `rg -n probeIndexHealth codegraph/src/mcp` only `index-state.ts` → C2.
8. CHANGELOG Unreleased + UPDATING row + ADR 0002 on disk → C11.
**Done gate:** every line observed + matching, step tests passing. Live Cursor MCP still inactive until rsync `dist/` (out of this plan’s ship; UPDATING already documents rsync).

## Open Questions

- OQ-2 OPEN — this plan implements **A** (re-probe). Do not cache.
- OQ-3 OPEN — explicit-path `openSync` throw remains `errorResult`. FCV: reachable; still deferred.
- TD-01 OPEN — no `.codegraph/ready`, no plugin bus.

## Out of Scope

CLI `init` / `isInitialized` semantics (Bucket 4). writ probe (Bucket 6). Recoverable empty → `isError`. Plugin bus / `.codegraph/ready`. `engine.ts` + daemon idle-kill product change (C1-a: FCV same contract). Installer `cursor.ts`. `npm install -g` / Node floor bump. `CODEGRAPH_ALLOW_UNSAFE_ROOT` policy. `site/` / historical CHANGELOG / markdown `init -i`. Barrel-export probe or `McpIndexState`. Duplicate COUNT. Fourth MCP name `'index_busy'`. Per-harness settings/hooks/mcp.json. Whole-file `grep-absent hasDefaultCodeGraph`.

## Gate co-satisfiability

One honest impl (HOW locks A–E) vs active gates:

| Gate | Honest impl |
|---|---|
| `grep-present "getStaticTools()"` session.ts | payload call HOW lock B |
| `grep-present "resolved.state === 'index_missing' ? [] : getStaticTools()"` session.ts | same one-liner |
| `grep-present "await this.retryInitIfNeeded()"` session.ts | **call** path kept |
| `grep-present "if (this.engine.hasDefaultCodeGraph()) return;"` | retry path kept — **no** whole-file absent |
| `grep-present "this.engine.ensureInitialized(explicitPath)"` | G-03 kick kept |
| `grep-present resolveMcpIndexState` proxy.ts | both writes |
| `grep-present probeIndexHealth` index-state.ts | HOW lock A |
| `grep-present resolveMcpIndexState` tools.ts | helper, not raw probe |
| `grep-absent init -i` tools.ts + worktree.ts | copy lock; plan Actions name the **old** string here only |
| `grep-present inactive this session` server-instructions.ts | UNINDEXED only; EMPTY test forbids it on EMPTY |
| `grep-absent "no \`.codegraph/\` directory"` server-instructions.ts | UNINDEXED reword |
| `grep-present MIN_NODE_MAJOR = 20` + byte-unchanged node-version-check | untouched |
| `byte-unchanged directory.ts / engine.ts / daemon.ts / index.ts` | CONSUMER-ONLY |
| `grep-absent degrade to missing-behavior` src/mcp | MUST-2 |
| MUST-1 deep-equals | test, not grep |
| MUST-3 `=== BUSY` | test, not grep |
| BT-1b pending socket | test, not immediate-null |

No red cells. `grep-absent hasDefaultCodeGraph` is **not** a gate (would fight retry path).

## Claim sweep

Swept this session: every `path:line` + quote in ## Facts, Implementation Order, and per-step Design/Actions. Line numbers re-read from disk (FCV + this plan). First write — no prior-plan C1-STALE. Extra FCV fact carried: `getTools` tiny-repo filter when `cg` set — default **names** still match; MUST-1 still needs deep-equals not names.