# Design — Bucket 5: MCP tells missing vs empty vs usable (ITEM-1-cg)

- _Date:_ 2026-08-19
- _Run:_ `2026-08-19-bkt5-codegraph-mcp` (protocol card `.village/runs/2026-08-19-bkt5-codegraph-mcp/protocol-card.md`)
- _Locked requirements:_ `docs/AI_artifacts/_handoff/2026-08-19-bkt5-codegraph-mcp-grill.md` (LOCKED 2026-08-19)
- _Scope parent:_ `docs/AI_artifacts/_scope/2026-08-16-feedback-bugs-scope.md` Bucket 5
- _Code home:_ `codegraph/` fork (tracked under this repo's `codegraph/` tree)
- _Dispatcher:_ `NON-INTERACTIVE: true` — no AskUserQuestion gates; non-recommended branches go to Open Questions
- _Patched:_ 2026-08-19 post-mini-RT (`docs/AI_artifacts/7_reviews/2026-08-19-bkt5-codegraph-mcp-mini-rt.md`, ORCH-adjudicated HOLD) — M1–M3 + m1–m3 folded in as binding tests / closed OQs.
- _Patched r1:_ 2026-08-19 post-big-RT r1 (`docs/AI_artifacts/7_reviews/2026-08-19-bkt5-codegraph-mcp-design-redteam.md`, ORCH-adjudicated HOLD) — big-RT M1–M4 + m1/m3 folded in (BT-5/BT-6, BT-1/BT-2 strengthened, mapping-table throw row replaced, `{state,busy}` helper return); m2/m4/m5 deferred to spec, not closed. Option A, 5→3 map, #172-backgrounded init, and TD-01-OPEN all unchanged; BT-1–BT-4 kept and only strengthened.

## Pre-dispatch audit

**Consumers of the contract surface (CONSUMER-ONLY):**

1. **Cursor ACP MCP host** — reads `initialize.result.instructions` into the agent context and `tools/list` into the tool registry; hits the **local-handshake proxy** path, the common case when a `.codegraph/` exists, per `codegraph/src/mcp/index.ts:291` quote: "await this.runProxyWithLocalHandshake(root);".
2. **Claude Code MCP host** — same shared binary (protocol card R15: one MCP server for both harnesses). Hits the same proxy when a `.codegraph/` exists; hits `MCPSession` directly when `CODEGRAPH_NO_DAEMON=1` or no `.codegraph/` is reachable, per `codegraph/src/mcp/index.ts:281` quote: "return this.startDirect('no .codegraph/ root found');".
3. **`codegraph/__tests__/mcp-initialize.test.ts`** — drives the direct-mode door via spawn, per `codegraph/__tests__/mcp-initialize.test.ts:33` quote: "env: { ...process.env, CODEGRAPH_NO_DAEMON: '1' },".

**Recorded command + output per scope claim (all run this session):**

| Scope claim (grill) | Command | Output |
|---|---|---|
| session.ts instructions gate is existence-only | Read `codegraph/src/mcp/session.ts:202` | `const indexed = findNearestCodeGraphRoot(explicitPath ?? process.cwd()) !== null;` |
| session.ts tools/list gate keys on engine open | Read `codegraph/src/mcp/session.ts:230` | `tools: this.engine.hasDefaultCodeGraph() ? this.engine.getToolHandler().getTools() : [],` |
| proxy always sends full playbook | Read `codegraph/src/mcp/proxy.ts:298` | `writeClient({ jsonrpc: '2.0', id: msg.id, result: { protocolVersion: PROTOCOL_VERSION, capabilities: { tools: {} }, serverInfo: SERVER_INFO, instructions: SERVER_INSTRUCTIONS } });` (unconditional) |
| proxy always sends full tools | Read `codegraph/src/mcp/proxy.ts:301` | `writeClient({ jsonrpc: '2.0', id: msg.id, result: { tools: getStaticTools() } });` (unconditional) |
| `probeIndexHealth` exists, 5-arm, not imported by mcp/** | `grep -rn "probeIndexHealth" codegraph/src codegraph/__tests__` | definition `codegraph/src/directory.ts:116`; importers `codegraph/src/bin/codegraph.ts:29` + `:597`, `codegraph/__tests__/probe-index-health.test.ts:21`; **zero hits under `src/mcp/`** |
| `isInitialized` is existence-only | Read `codegraph/src/directory.ts:100` | `return fs.existsSync(dbPath);` |
| late emptyWarn names stale `init -i` | Read `codegraph/src/mcp/tools.ts:2275-2276` | `'⚠ codegraph index is empty here (0 nodes indexed) — '` + `'run \`codegraph init -i\` in this directory before exploring.'` |
| recoverable stays SUCCESS-shaped | Read `codegraph/src/mcp/tools.ts:1228-1229` | `if (err instanceof NotIndexedError) {` → `return this.textResult(err.message);` |
| `runLocalHandshakeProxy` takes injectable deps (mini-RT M1 test seam) | Read `codegraph/src/mcp/proxy.ts:180-204` | `export interface LocalHandshakeDeps {` … `getDaemonSocket(): Promise<net.Socket \| null>;` … `makeEngine(): MCPEngine;` … `root: string;` … `export async function runLocalHandshakeProxy(deps: LocalHandshakeDeps): Promise<void> {` |
| `getStaticTools()` carries NO per-repo budget suffix; `getTools()` appends one once `cg` loads (big-RT M1: byte-identical `defs` across doors was already false) | Read `codegraph/src/mcp/tools.ts:620-624` + `:810` | "the static surface the proxy answers `tools/list` with before any project is open" … "(the dynamic per-repo budget note in a description only adds once `cg` is loaded; the schemas are static)" · `description: \`... Budget: make at most ${budget} calls...\`` |
| session `tools/list` awaits engine init before answering (big-RT M1) | Read `codegraph/src/mcp/session.ts:221` | `await this.retryInitIfNeeded();` — first statement of `handleToolsList`; then `:230` `tools: this.engine.hasDefaultCodeGraph() ? this.engine.getToolHandler().getTools() : [],` |
| session engine open uses `busy_timeout = 5000` (big-RT M1: the await can block 5s) | Read `codegraph/src/db/index.ts:31` | `db.pragma('busy_timeout = 5000');      // MUST be first — see above` |
| Node floor is 20, not 22.5 (big-RT M2: `node:sqlite` may be absent on supported hosts) | Read `codegraph/package.json:54` + `codegraph/src/bin/node-version-check.ts:48` | `"node": ">=20.0.0 <25.0.0"` · `export const MIN_NODE_MAJOR = 20;` |
| proxy listens on stdin BEFORE awaiting the daemon socket; production socket poll can take ~6s (big-RT M3) | Read `codegraph/src/mcp/proxy.ts:281` + `:324`; `codegraph/src/mcp/index.ts:101-102` + `:97` | `process.stdin.on('data', (chunk: string) => {` … then `try { socket = await deps.getDaemonSocket(); } catch { socket = null; }` · `const DAEMON_CONNECT_MAX_RETRIES = 240;` / `const DAEMON_CONNECT_RETRY_DELAY_MS = 25;` · "// cold-start handshake (the window the headless agent races). Same ~6s total" |
| watcher-seq test keys on stderr marker only (mini-RT M3) | Read `codegraph/__tests__/mcp-initialize.test.ts:130,151` | `it('sends initialize response BEFORE tryInitializeDefault finishes', async () => {` … assertion `expect(response.seq).toBeLessThan(watcherLog.seq);` — marker is stderr `'File watcher active'`; a heavy sync open before `sendResult` still precedes it → test passes on a COUNT→open swap |
| two more user-visible `init -i` sites in fork (mini-RT m1) | Read `codegraph/src/sync/worktree.ts:89,103` | `symbols changed only here are missing. Run "codegraph init -i" in this worktree` · `and symbols changed only here are missing. Run "codegraph init -i" here for a` |

**One contradiction looked for and not found:** the grill says "one contract surface … both doors (`session.ts` and `proxy.ts`)". I hunted for a **third door** — a path where an MCP host could receive `initialize`/`tools/list` via the pure stdio⇄socket pipe `runProxy`, which forwards everything verbatim to the daemon (whose `MCPSession` would then be payload-authoritative). `grep -rn "runProxy\b" codegraph/src codegraph/__tests__` returns only the definition (`codegraph/src/mcp/proxy.ts:83` quote: "export async function runProxy(") and a doc mention (`codegraph/src/mcp/index.ts:470` quote: "{@link runProxy}. So this only ever runs for an in-process direct session.") — **no caller**. The only live proxy entry is `runLocalHandshakeProxy` (`codegraph/src/mcp/index.ts:458` quote: "await runLocalHandshakeProxy({ getDaemonSocket, makeEngine: () => new MCPEngine(), root });"). Two doors exactly, as the grill says.

## Summary

The MCP server today answers `initialize` and `tools/list` on **file existence, not index health**.

- In direct mode, a hollow 0-node `codegraph.db` counts as "indexed": `codegraph/src/mcp/session.ts:202` quote: "const indexed = findNearestCodeGraphRoot(explicitPath ?? process.cwd()) !== null;".
- The agent then gets the full playbook: `codegraph/src/mcp/session.ts:209` quote: "instructions: indexed ? SERVER_INSTRUCTIONS : SERVER_INSTRUCTIONS_UNINDEXED,".
- And a full tool list, because the engine opens an empty DB without complaint and the availability check is a null-check — the open: `codegraph/src/mcp/engine.ts:167` quote: "this.cg = await loadCodeGraph().open(resolvedRoot);".
- The null-check: `codegraph/src/mcp/tools.ts:728` quote: "return this.cg !== null;".
- The tools gate itself: `codegraph/src/mcp/session.ts:230` quote: "tools: this.engine.hasDefaultCodeGraph() ? this.engine.getToolHandler().getTools() : [],".
- In proxy mode the local handshake answers with no DB knowledge at all — the static playbook: `codegraph/src/mcp/proxy.ts:298` quote: "serverInfo: SERVER_INFO, instructions: SERVER_INSTRUCTIONS } });".
- And the static tools: `codegraph/src/mcp/proxy.ts:301` quote: "result: { tools: getStaticTools() } });".

That proxy behavior is the live lie the grill names. This design imports the CLI's probe (`codegraph/src/directory.ts:116` quote: "export function probeIndexHealth(projectRoot: string): {"), maps its 5-arm health union to the frozen MCP tri-state (`index_missing` / `index_empty` / usable, busy → empty-style), and gates both doors' `initialize` instructions and `tools/list` on the result, while keeping heavy engine init in the background per issue #172.

## Constraints

- **Frozen tri-state:** `index_missing` / `index_empty` / usable. No fourth MCP-visible name (protocol card "Frozen contracts"; grill lock 1-a).
- **Mapping 5→3:** `usable`→usable, `empty`→`index_empty`, `unreadable`→missing-behavior, `unclassified`→missing-behavior, `busy`→empty-style (tools stay listed, short "busy, retry later" copy). Locks 3-a + 1-a. The busy discriminant rides a **flag on the helper return value** (`{ state: McpIndexState, busy: boolean }` (new), big-RT M4), selecting `SERVER_INSTRUCTIONS_INDEX_BUSY` (new) — still no fourth MCP-visible **name**.
- **One nonempty list source on both doors (big-RT M1):** a served (nonempty) `tools/list` comes from `getStaticTools()` on BOTH doors, decided by the state alone. The session door must NOT `await retryInitIfNeeded()` / `ensureInitialized` / `hasDefaultCodeGraph()` to decide the nonempty list — today it awaits before answering, and `getTools()` byte-diverges from `getStaticTools()` once `cg` loads (budget suffix); cites for both facts are in the Pre-dispatch audit rows above. So "identical payloads" means pinning the static source, not "whatever each door had."
- **Probe throw → existence-gate fallback, NOT missing (big-RT M2):** when `probeIndexHealth` throws (`node:sqlite` absent on supported Node 20–22.4 — the floor is `codegraph/src/bin/node-version-check.ts:48` quote: "export const MIN_NODE_MAJOR = 20;"), the helper behaves as today's gate: root found ⇒ usable-enough serving (full playbook + `getStaticTools()`, matching the engine path that opens via better-sqlite3, never `node:sqlite`); root absent ⇒ `index_missing`. The Node floor does not move; `node:sqlite` stays a probe-only dependency.
- **`tools/list` empty ONLY for missing.** Empty-db and busy keep tools listed (scope freeze in `docs/AI_artifacts/_scope/2026-08-16-feedback-bugs-scope.md`).
- **Cheap COUNT before the handshake reply; heavy init stays background** (lock 2-a; #172). The probe is a read-only open: `codegraph/src/directory.ts:131` quote: "db = new DatabaseSync(dbPath, { readOnly: true });".
- Plus a 500ms busy cap: `codegraph/src/directory.ts:132` quote: "db.exec('PRAGMA busy_timeout = 500');".
- Plus one COUNT: `codegraph/src/directory.ts:133` quote: "const row = db.prepare('SELECT COUNT(*) AS n FROM nodes').get() as { n: number };".
- **Import, don't duplicate:** MCP imports `probeIndexHealth` from `../directory` and maps it; no second COUNT implementation; no third public enum from `src/index.ts` (dispatch). `isInitialized` semantics unchanged: `codegraph/src/directory.ts:100` quote: "return fs.existsSync(dbPath);".
- **Same payloads on both doors** (lock 4-a).
- **Recoverable ≠ `isError`**: `codegraph/src/mcp/tools.ts:1228` quote: "if (err instanceof NotIndexedError) {".
- **Copy:** missing/empty text says the **user** runs `codegraph init`; the agent never self-inits; never stale `init -i` (lock 5-a). Stale sites (mini-RT m1 extended): `codegraph/src/mcp/tools.ts:2276` quote: "run `codegraph init -i` in this directory before exploring."
- **Copy (m1-extended, `worktreeMismatchWarning`):** `codegraph/src/sync/worktree.ts:89` quote: "codegraph init -i" — full string: `Run "codegraph init -i" in this worktree for a worktree-local index.`
- **Copy (m1-extended, `worktreeMismatchNotice`):** `codegraph/src/sync/worktree.ts:103` quote: "codegraph init -i" — full string: `Run "codegraph init -i" here for a worktree-local index.`
- **Out this bucket (m1 carve-out):** `site/` / `CHANGELOG.md` / markdown docs rewrites of historical `init -i` mentions — copy lock applies to code-served strings only.
- **Do not touch:** CLI `init` / `resolveProjectPath` (dispatch), `engine.ts` + daemon idle-kill as a second product (C1-a: A-split only if FCV proves a different contract), `falkor-writ/**`, `CODEGRAPH_ALLOW_UNSAFE_ROOT` policy, installer `cursor.ts`, npm upgrade. TD-01 stays OPEN — no plugin bus, no `.codegraph/ready`.
- **Env surface the new logic touches (C4):** `CODEGRAPH_DIR` (db path via `getCodeGraphDir`), `CODEGRAPH_NO_DAEMON` (mode pick, unchanged), `CODEGRAPH_DAEMON_INTERNAL` (mode pick, unchanged), `CODEGRAPH_MCP_TOOLS` (allowlist applied to a *nonempty* list only), `CODEGRAPH_ALLOW_UNSAFE_ROOT` (walk-up root rejection, unchanged).

## Guardrail Checklist

| # | Guardrail | Source | This design |
|---|---|---|---|
| G-01 | Never write to `codegraph.db` — MCP reads only | piggyback CLAUDE.md "Critical Rules" | probe opens read-only (`codegraph/src/directory.ts:131` quote: "db = new DatabaseSync(dbPath, { readOnly: true });") — satisfies |
| G-02 | Recoverable states stay SUCCESS-shaped; `isError` reserved | `codegraph/src/mcp/tools.ts:1228` quote: "if (err instanceof NotIndexedError) {" | empty/busy copies are text payloads; no new `errorResult` — satisfies |
| G-03 | #172 respond-fast contract: initialize reply before heavy init | `codegraph/__tests__/mcp-initialize.test.ts:130` quote: "it('sends initialize response BEFORE tryInitializeDefault finishes', async () => {" | probe replaces only the existsSync walk; engine init stays backgrounded (`codegraph/src/mcp/session.ts:216` quote: "this.resolvePromise = this.engine.ensureInitialized(explicitPath);") — satisfies with a ≤500ms sync budget |
| G-04 | No third public enum from `src/index.ts` barrel | dispatch | mapper lives in `src/mcp/`, imports `../directory` directly — satisfies |
| G-05 | `isInitialized` semantics unchanged | dispatch + `external: /Users/phatchenh/all-projects/vibe-coding-setup/codegraph-piggyback/codegraph/docs/adr/0001-init-repairs-unusable-index.md:9` | untouched — satisfies |
| G-06 | CLI `init` / `resolveProjectPath` untouched | dispatch | untouched — satisfies |
| G-07 | Local fork: no `npm upgrade`; deploy = build + rsync; patch row | `codegraph/CLAUDE.md` banner + `codegraph/UPDATING.md` | impl adds an UPDATING.md patch row + CHANGELOG `[Unreleased]` entry — deferred to plan |
| G-08 | TD-01 stays OPEN; no plugin bus / `.codegraph/ready` | `docs/TECH_DEBT.md` TD-01 + grill C2-a | no new lifecycle surface — satisfies |
| G-09 | Agent never self-inits; copy names the user's `codegraph init` | lock 5-a + `codegraph/src/mcp/server-instructions.ts:66` quote: "Indexing is the user's decision — mention they can run `codegraph init` if it comes up, but don't run it yourself." | all new copies name `codegraph init`, not `init -i` — satisfies |
| G-10 | Probe throw must not wedge the handshake AND must not hide a working index (big-RT M2: the engine never needs `node:sqlite`) | probe's require lives inside the function body: `codegraph/src/directory.ts:123` quote: "const { DatabaseSync } = require('node:sqlite') as {" | every new call site wraps the probe in try/catch → throw means **existence-gate fallback** (root found ⇒ usable-enough serving, exactly today's behavior; root absent ⇒ `index_missing`), NOT mapped to missing-behavior. Node floor stays `>=20`: `codegraph/package.json:54` quote: "\"node\": \">=20.0.0 <25.0.0\"" |

## Surface-capability matrix

| Event / surface | Vendor-enforced? | Payload fields this design sets | Operator surface |
|---|---|---|---|
| MCP `initialize` result | yes — MCP schema; hosts render `instructions` into agent context automatically | `protocolVersion`, `capabilities.tools`, `serverInfo`, `instructions` (one of 4 constants) | `codegraph/src/mcp/server-instructions.ts` — single source of truth for agent-facing guidance (codegraph CLAUDE.md house rule) |
| MCP `tools/list` result | yes — MCP schema; an empty list is honored by hosts as "no tools" | `tools: []` (missing-shape) or filtered defs (empty/busy/usable) | session.ts gate + proxy.ts local answer — both doors identical payloads |
| Daemon socket (internal, proxy↔daemon) | no — own protocol, hello line version-pinned (`codegraph/src/mcp/proxy.ts:105` quote: "if (hello.codegraph !== expectedVersion) {") | forwarded `initialize` priming line; daemon's initialize reply is **suppressed** (`codegraph/src/mcp/proxy.ts:344` quote: "if (clientInitId !== undefined && resp.id === clientInitId) continue;") | unchanged — daemon session state machine not touched beyond session.ts gating |
| SQLite probe (`node:sqlite` read-only) | driver-enforced errcodes 5 / 26 / 11 / 1 pinned by `codegraph/__tests__/probe-index-health.test.ts` | `{ status, errcode?, message? }` 5-arm union | `probeIndexHealth` stays CLI-owned in `directory.ts`; MCP is a read-only consumer, does NOT freeze it as public API |

## Implications

**Two doors, two different bugs; caller chains verified:**

- Direct-mode existence gate: `codegraph/src/mcp/session.ts:202` quote: "const indexed = findNearestCodeGraphRoot(explicitPath ?? process.cwd()) !== null;".
- Direct-mode tools gate: `codegraph/src/mcp/session.ts:230` quote: "tools: this.engine.hasDefaultCodeGraph() ? this.engine.getToolHandler().getTools() : [],".
- Both turn true for a hollow db because the open succeeds: `codegraph/src/mcp/engine.ts:167` quote: "this.cg = await loadCodeGraph().open(resolvedRoot);".
- The production caller of the direct gate is `handleMessage` dispatching `initialize`: `codegraph/src/mcp/session.ts:125` quote: "if (isRequest) await this.handleInitialize(message as JsonRpcRequest);" — no internal re-entry bypass.
- Proxy never consults the db; its initialize payload writer sits in the stdin handler: `codegraph/src/mcp/proxy.ts:289` quote: "if (msg.method === 'initialize') {".
- Which writes the static answer: `codegraph/src/mcp/proxy.ts:298` quote: "serverInfo: SERVER_INFO, instructions: SERVER_INSTRUCTIONS } });".
- The tool list comes from the same handler: `codegraph/src/mcp/proxy.ts:300` quote: "} else if (msg.method === 'tools/list') {".
- Again statically: `codegraph/src/mcp/proxy.ts:301` quote: "result: { tools: getStaticTools() } });".

**Probe reuse, module edges:**

- `session.ts` already imports from `../directory`: `codegraph/src/mcp/session.ts:21` quote: "import { findNearestCodeGraphRoot } from '../directory';".
- `engine.ts` too: `codegraph/src/mcp/engine.ts:14` quote: "import { findNearestCodeGraphRoot } from '../directory';".
- Adding `probeIndexHealth` to that import adds no new module edge; `proxy.ts` gains one new but cycle-free edge (mcp→directory precedent exists).

**Copy sites:**

- The unindexed variant is truthful only for "no directory": `codegraph/src/mcp/server-instructions.ts:84` quote: "This workspace has no codegraph index (no \`.codegraph/\` directory), so no" — it would lie about an unreadable/junk db once junk maps to missing; one reword keeps one constant truthful for both (no fourth name).
- The explicit-`projectPath` `NotIndexedError` text is accurate only for genuine absence: `codegraph/src/mcp/tools.ts:874` quote: "`The project at ${projectPath} isn't indexed with codegraph (no .codegraph/ directory found ` +".
- A junk db on an explicit path otherwise fails as a generic internal error at open: `codegraph/src/mcp/tools.ts:897` quote: "const cg = loadCodeGraph().openSync(resolvedRoot);". Bucket scope: differentiate missing vs unreadable at the throw site; full junk-handling of tool calls is OQ-3.
- The stale `init -i` copy: `codegraph/src/mcp/tools.ts:2276` quote: "run `codegraph init -i` in this directory before exploring." — must name `codegraph init` per lock 5-a (grill: Bucket 4's `init` already indexes).

**Probe failure modes:**

- The require runs inside the function body: `codegraph/src/directory.ts:123` quote: "const { DatabaseSync } = require('node:sqlite') as {".
- Which throws on Node < 22.5, per the skip guard: `codegraph/__tests__/probe-index-health.test.ts:13` quote: "* Skipped on Node < 22.5 where node:sqlite doesn't exist.".
- The CLI call site does not wrap the probe: `codegraph/src/bin/codegraph.ts:597` quote: "const health = probeIndexHealth(projectPath);" — MCP call sites run on the host's Node, so they MUST wrap and degrade to missing-behavior rather than crash the handshake.
- Invariant: the probe never mutates and always closes: `codegraph/__tests__/probe-index-health.test.ts:10` quote: "* the probe never mutates bytes (sha256 unchanged) and it always closes its".

**Speed accounting + comment truth:**

- The current comment credits existsSync-only speed: `codegraph/src/mcp/session.ts:193` quote: "// synchronous walk-up (existsSync loop only, no DB open, so the #172" — lock 2-a accepts the sync read-only open + COUNT inside that contract (grill "Risks accepted": 500ms busy cap already on the probe); the comment must be rewritten in the same edit or it becomes a lie.

**Depth / lifecycle / pickup:**

- Module depth: `server-instructions.ts` is a pure-constant module (deep); the proxy handshake block is shallow for payloads (two static writes). Duplicating the mapping session↔proxy would be a shallow smear → one mcp-internal helper (deletion test in Option A).
- Daemon idle-kill stays CONSUMER-ONLY: `codegraph/src/mcp/daemon.ts:60` quote: "const DEFAULT_IDLE_TIMEOUT_MS = 300_000;" — nothing here changes daemon lifecycle (C1-a gate deferred to FCV).
- Pickup-after-init is a documented behavior: `codegraph/src/mcp/session.ts:227` quote: "// picked up on the next tools/list — retryInitIfNeeded re-walks — though" — re-probing per request keeps it for empty→usable too.
- Daemon-unreachable fallback shares one gate: `tools/list` is answered before the fallback handler: `codegraph/src/mcp/proxy.ts:300` quote: "} else if (msg.method === 'tools/list') {" — one probe of `deps.root` covers daemon-ready and daemon-failed alike.

## Constraints (scope inheritance)

`constraints: (none authored in piggyback)` per dispatch — no `docs/CONSTRAINTS.*` or writ PROJ-* rule applies to this repo layer. The operative constraint set is the frozen contract block sourced from the protocol card + grill (enumerated above in Constraints) plus the guardrails in the Guardrail Checklist. TD-01 (`docs/TECH_DEBT.md`) is consumed as KEEP-OPEN: this design adds no consumer-facing lifecycle event, which is exactly what TD-01 tracks as missing; shipping one here would violate the freeze "No plugin bus. No `.codegraph/ready`" and is recorded only in the return summary's Discoveries, never promoted into the artifact's own to-do list.

## Alternatives Considered

### Option A — Shared mcp-internal `index-state` helper feeding both doors (Recommended)

**Approach:** add `codegraph/src/mcp/index-state.ts` (new) exporting `McpIndexState` (new) = `'index_missing' | 'index_empty' | 'usable'` plus `resolveMcpIndexState(startPath)` (new) returning `{ state: McpIndexState, busy: boolean }` (new; big-RT M4 — the 3-arm union alone cannot select the busy constant): walk via `findNearestCodeGraphRoot`; null → `index_missing`; else try `probeIndexHealth(root)` and map (`usable`→usable; `empty`→`index_empty`; `busy`→`index_empty` with busy flag true; `unreadable`/`unclassified` → `index_missing`). Probe **throw** (big-RT M2; `node:sqlite` absent on the supported Node 20–22.4 floor) is NOT missing — fall back to today's existence gate: the root the walk already found means usable-enough serving (full playbook + static tools), matching the current engine path that never touches `node:sqlite`. Both doors call it at every `initialize` and `tools/list`; instructions selected from 4 constants (`SERVER_INSTRUCTIONS` / `SERVER_INSTRUCTIONS_UNINDEXED` reworded / `SERVER_INSTRUCTIONS_INDEX_EMPTY` (new) / `SERVER_INSTRUCTIONS_INDEX_BUSY` (new)); `tools/list` returns `[]` only for `index_missing`, and the nonempty list is `getStaticTools()` on BOTH doors (big-RT M1 — no engine await / `hasDefaultCodeGraph` gate may veto a served list, and `getTools()` byte-diverges via its budget suffix). `tools.ts` gets two copy fixes: emptyWarn → `codegraph init` (`codegraph/src/mcp/tools.ts:2276` quote: "run `codegraph init -i` in this directory before exploring.") and explicit-path `NotIndexedError` differentiates missing vs unreadable (`codegraph/src/mcp/tools.ts:873` quote: "throw new NotIndexedError(").
**Files touched (reason):** new `codegraph/src/mcp/index-state.ts` (mapping, single owner); `codegraph/src/mcp/session.ts` (gate initialize + tools/list on state instead of existsSync/engine-open); `codegraph/src/mcp/proxy.ts` (gate local-handshake initialize + tools/list on probe of `deps.root`); `codegraph/src/mcp/server-instructions.ts` (reword UNINDEXED + two new constants); `codegraph/src/mcp/tools.ts` (two copy sites); `codegraph/src/sync/worktree.ts` (two MCP-served `init -i` strings at `:89`/`:103`, mini-RT m1); `codegraph/__tests__/mcp-initialize.test.ts` + new stub-deps proxy-handshake test (payload table per state, both doors — mini-RT M1/M2) + new no-heavy-open-before-sendResult test (mini-RT M3); `codegraph/UPDATING.md` patch row + `CHANGELOG.md` `[Unreleased]` (fork discipline).
**Cost:** dev effort med (~15-25 lines + tests, per scope) · runtime = one extra read-only sqlite open + COUNT per initialize/tools-list (sub-ms warm; ≤500ms worst busy case) · maintenance = one new private module, no config.
**Risk:** [performance]: probe inside handshake on a very slow FS — mitigated by busy_timeout 500 + backgrounded engine init. [fork-maintenance]: new mcp→directory import edge recorded in UPDATING.md so upstream merges surface it.
**Module depth:** the new boundary passes the deletion test — deleting it re-sprays walk+probe+throw-guard+mapping into 4 call sites across 2 files (session initialize + tools/list; proxy initialize + tools/list). Interface: 1 type + 1 function consumed by 2 modules = real seam, not speculative.
**What it defers:** explicit-path junk-db tool-call UX beyond copy differentiation (OQ-3); daemon idle-kill/health exposure (C1-a); Bucket 6 writ probe.
**Constraints check:** [x] tri-state freeze · [x] 5→3 map · [x] empty `tools/list` missing-only · [x] COUNT before reply · [x] import-not-duplicate (G-04) · [x] both doors · [x] SUCCESS-shaped · [x] copy lock 5-a · [x] TD-01 open.

### Option B — Inline the mapping in each door (no new module)

**Approach:** same state machine, duplicated: ~15 lines in `session.ts` and ~15 lines in `proxy.ts` each doing walk+probe+try/catch+map locally.
**Files touched:** session.ts, proxy.ts, server-instructions.ts, tools.ts, tests (same as A minus the helper).
**Cost:** dev effort low-med · runtime identical · maintenance = two copies of an errcode→state table that must stay in lockstep.
**Risk:** [drift]: the exact failure the grill rejected as "Duplicate MCP COUNT — two sqlite probes" — a future edit updates one door; the two doors then answer differently for the same db.
**Module depth:** no new boundary, but creates replicated shallowness — the inverse of deepening.
**What it defers:** same as A plus a future helper extraction.
**Constraints check:** [x] tri-state · [⚠] no duplicate COUNT, but the *mapping* is duplicated — violates the single-owner intent of lock 3-a · [x] everything else as A.

### Option C — Selector in `server-instructions.ts`; doors probe independently

**Approach:** deepen the instructions module with `instructionsForState(state)` (new); each call site still does its own walk+probe+throw guard to compute `state`.
**Files touched:** server-instructions.ts (+selector), session.ts, proxy.ts, tools.ts, tests.
**Cost:** dev med · runtime identical · maintenance: probe logic still duplicated between the doors while only text selection centralizes.
**Risk:** [layering]: the module is documented as the single source of truth for agent-facing guidance (codegraph CLAUDE.md house rule) — state computation there tempts future edits to import db logic into a text module.
**Module depth:** deepens instructions.ts only superficially (one switch), leaves the real seam unbuilt.
**What it defers:** the helper extraction anyway.
**Constraints check:** [⚠] same partial-duplication warning as B.

### Option D — Health-aware `isInitialized` / engine knows state (aggressive)

**Approach:** change `isInitialized` to return health, or move tri-state into `MCPEngine`.
**Files touched:** directory.ts (semantics), engine.ts, all callers incl. CLI `uninit`/`init`.
**Cost:** high — CLI blast radius across commands; contradicts the dispatch freeze "Do not change `isInitialized` semantics."
**Risk:** [contract break]: `init`'s already-initialized branch (`codegraph/src/bin/codegraph.ts:596` quote: "if (isInitialized(projectPath)) {") keys its no-op on existence-only today; making it health-aware double-probes and re-opens Bucket 4.
**Viability:** **not viable** — explicitly OUT (grill "Alternatives dropped": "Health-aware `isInitialized` — CLI `uninit`/`init` blast; Bucket 4 rejected.").

### Option E — Per-reason instruction constants for missing (missing-dir vs junk-db)

**Approach:** ship two missing-shape variants so the agent is told exactly why.
**Cost:** low · risk: a 4th/5th instruction surface drifts from the frozen tri-state vocabulary the consumers key on.
**Rejected:** one reworded UNINDEXED covers both sub-cases truthfully ("no usable index"); remediation (`codegraph init`) is identical either way.

**Recommendation:** Option A — one helper is the only option that satisfies "same payloads on both doors" structurally rather than by convention, at the cost of one small private module.

> ADR offer: gate check — (1) hard to reverse: yes, agents learn from these payloads; (2) surprising without context: yes, the 5→3 mapping hides the CLI union; (3) real trade-off: yes (import vs duplicate). All three true → **offer an ADR in `codegraph/docs/adr/` with the impl**, as the grill pre-approved.

## Chosen Approach

One mcp-internal helper `codegraph/src/mcp/index-state.ts` (new) owns the walk → probe → throw-guard → 5→3 map, returning `{ state: McpIndexState, busy: boolean }` (new; big-RT M4). Direct detail and door wiring:

- `MCPSession` replaces the boolean gate: `codegraph/src/mcp/session.ts:202` quote: "const indexed = findNearestCodeGraphRoot(explicitPath ?? process.cwd()) !== null;" with a `resolveMcpIndexState(explicitPath ?? process.cwd())` call; instructions selected per state (+busy flag).
- `handleToolsList` re-resolves and returns `[]` only for `index_missing`; otherwise it serves `getStaticTools()` WITHOUT `await retryInitIfNeeded()` and WITHOUT consulting `hasDefaultCodeGraph()` — the two gates that today let an engine-open stall or failure empty a busy/empty list on this door alone: `codegraph/src/mcp/session.ts:230` quote: "tools: this.engine.hasDefaultCodeGraph() ? this.engine.getToolHandler().getTools() : [],". This is the big-RT M1 fix: one served-list source across both doors, byte-identical because `getTools()`'s budget suffix only exists under `cg`. Pickup-after-init is preserved by re-resolving **state** per request (the list never depended on the engine open for content; only the state can flip `[]`→defs, per `codegraph/src/mcp/session.ts:227` quote: "// picked up on the next tools/list — retryInitIfNeeded re-walks — though").
- The direct-mode caller chain is unchanged (`handleMessage` → `handleInitialize`): `codegraph/src/mcp/session.ts:125` quote: "if (isRequest) await this.handleInitialize(message as JsonRpcRequest);".
- The proxy resolves state from `deps.root` at its initialize branch inside `runLocalHandshakeProxy`: `codegraph/src/mcp/proxy.ts:289` quote: "if (msg.method === 'initialize') {".
- Its production caller is `runProxyWithLocalHandshake`: `codegraph/src/mcp/index.ts:458` quote: "await runLocalHandshakeProxy({ getDaemonSocket, makeEngine: () => new MCPEngine(), root });".
- Which in turn is invoked by `MCPServer.start`'s step 4: `codegraph/src/mcp/index.ts:291` quote: "await this.runProxyWithLocalHandshake(root);".
- And at its tools/list branch: `codegraph/src/mcp/proxy.ts:300` quote: "} else if (msg.method === 'tools/list') {" — identical payload table, so door parity is structural.
- Busy is `index_empty`-style for tools but carries its own short constant `SERVER_INSTRUCTIONS_INDEX_BUSY` (new) — not a fourth state name.
- `tools.ts` copy edit 1: `codegraph/src/mcp/tools.ts:2276` quote: "run `codegraph init -i` in this directory before exploring." → names `codegraph init`.
- worktree copy edits (mini-RT m1): `codegraph/src/sync/worktree.ts:89` quote: "codegraph init -i" (`worktreeMismatchWarning`) and `:103` (`worktreeMismatchNotice`) → name `codegraph init`; both strings are MCP-served via tool-result text, so lock 5-a covers them. `site/` + `CHANGELOG.md` + docs are NOT rewritten in this bucket.
- `tools.ts` copy edit 2: the explicit-path throw text: `codegraph/src/mcp/tools.ts:874` quote: "`The project at ${projectPath} isn't indexed with codegraph (no .codegraph/ directory found ` +".
- Probe the resolved root once there and differentiate missing vs unreadable. Production callers of that throw site: the `handle*` tool methods (`handleExplore`, `handleNode`, `handleSearch`, `handleCallers`, `handleCallees`, `handleImpact`, `handleFiles`, `handleStatus`) all route through `getCodeGraph` inside the `execute` dispatch: `codegraph/src/mcp/tools.ts:1199` quote: "switch (toolName) {".
- No bypassing internal re-entry: `execute` is the single tool-call intake; the direct door calls it at `codegraph/src/mcp/session.ts:260` quote: "const result = await this.engine.getToolHandler().execute(toolName, toolArgs);".
- The stale speed comment is rewritten in the same edit: `codegraph/src/mcp/session.ts:193` quote: "// synchronous walk-up (existsSync loop only, no DB open, so the #172".

Mapping table to be pinned in spec:

| `probeIndexHealth` | MCP state | instructions | tools/list |
|---|---|---|---|
| root null | `index_missing` | UNINDEXED (reworded) | `[]` |
| `usable` | usable | SERVER_INSTRUCTIONS | defs |
| `empty` | `index_empty` | `SERVER_INSTRUCTIONS_INDEX_EMPTY` (new) | defs |
| `busy` | `index_empty` + busy flag (big-RT M4: the flag rides the `{ state, busy }` return) | `SERVER_INSTRUCTIONS_INDEX_BUSY` (new) | defs |
| `unreadable` | `index_missing` | UNINDEXED (reworded) | `[]` |
| `unclassified` | `index_missing` | UNINDEXED (reworded) | `[]` |
| probe throws (no node:sqlite), root FOUND | usable-enough fallback (big-RT M2) — serve exactly as today's existence gate | SERVER_INSTRUCTIONS | defs |
| probe throws (no node:sqlite), root null | `index_missing` | UNINDEXED (reworded) | `[]` |

"defs" = `getStaticTools()` on BOTH doors (big-RT M1) — never `engine.getToolHandler().getTools()`, whose budget suffix only exists once `cg` loads and whose availability depends on a successful engine open.

### Binding tests (mini-RT 2026-08-19 HOLD — M1/M2/M3 + m1/m2/m3 closures; non-negotiable pins the spec must carry)

**BT-1 (M1, closes OQ-4 as A) — stub-deps proxy-door test, no live daemon spawn.** New vitest drives `runLocalHandshakeProxy(deps)` directly with injected `LocalHandshakeDeps` (`codegraph/src/mcp/proxy.ts:180-188` quote: "export interface LocalHandshakeDeps {"): `getDaemonSocket` resolves `null` forever (never-ready daemon), `makeEngine` returns a stub, `root` points at per-state fixtures. Assert the full payload table on stdout per state: missing → `tools: []` + reworded UNINDEXED copy; junk (unreadable) → `tools: []` + reworded UNINDEXED copy; empty → tools stay listed + `SERVER_INSTRUCTIONS_INDEX_EMPTY` copy; busy → tools stay listed + `SERVER_INSTRUCTIONS_INDEX_BUSY` copy. **Busy copy is asserted by exact equality against the imported `SERVER_INSTRUCTIONS_INDEX_BUSY` constant** (big-RT M4) — "empty-style" is not enough; a 3-arm-only helper that collapses busy into `SERVER_INSTRUCTIONS_INDEX_EMPTY` must fail this test. Plan-verify pin: `grep-present 'resolveMcpIndexState' codegraph/src/mcp/proxy.ts` — skipping the proxy gate must fail something.

**BT-1b (big-RT M3) — initialize answered BEFORE the daemon socket settles.** Same stub-deps harness, but `getDaemonSocket` is a Promise that **stays pending for the whole assertion window** (never settles; settled at cleanup). Assert the initialize reply is written to stdout while that Promise is still pending. A proxy regression that `await`s the daemon socket before attaching the stdin listener would still answer an instantly-null stub — so an immediate-null stub does NOT satisfy this pin; pending is load-bearing. Production stake: the poll budget is 240 × 25ms ≈ 6s (`codegraph/src/mcp/index.ts:101-102` quote: "const DAEMON_CONNECT_MAX_RETRIES = 240;" / "const DAEMON_CONNECT_RETRY_DELAY_MS = 25;"), so a reorder hangs every cold host handshake for up to 6s — #172 relapse on the live door. Today's order is listen-first: `codegraph/src/mcp/proxy.ts:281` quote: "process.stdin.on('data', (chunk: string) => {" precedes `codegraph/src/mcp/proxy.ts:324` quote: "try { socket = await deps.getDaemonSocket(); } catch { socket = null; }". No live daemon spawn; stub-deps stand (OQ-4 stays CLOSED as A).

**BT-2 (M2 + m2) — MCP-layer mapping assertions, not handshake-shape-only.** Assert `initialize.result.instructions` CONTENT contains the empty/missing snippet for those states (today's tests assert only `protocolVersion`/`capabilities`/`serverInfo`), and `tools/list` is `[]` for missing AND junk, non-empty for empty-db. Junk-db fixture pinned at the MCP mapping layer (inside the new proxy/session state tests), not only in `probe-index-health.test.ts`. **`resolveMcpIndexState` MUST call `probeIndexHealth` when a root exists** — an existence-only helper is a fail; assert via spy/stub of the imported probe and/or plan-verify `grep-present 'probeIndexHealth' codegraph/src/mcp/index-state.ts`.

**BT-2 copy pins (big-RT m1 + m3):** on the **junk fixture** the reworded UNINDEXED MUST contain the substring `no usable index` and MUST NOT contain `no \`.codegraph/\` directory` — the junk db HAS the directory and the file (`findNearestCodeGraphRoot` requires `isInitialized`, which requires the db file: `codegraph/src/directory.ts:100` quote: "return fs.existsSync(dbPath);"), so today's wording (`codegraph/src/mcp/server-instructions.ts:84` quote: "This workspace has no codegraph index (no \`.codegraph/\` directory), so no") is a lie in exactly this state. `SERVER_INSTRUCTIONS_INDEX_EMPTY` (new) MUST NOT claim tools are unavailable / the server is inactive this session (no reuse of the "inactive this session" framing) — tools stay listed for empty-db, and hosts commonly list once per connection (`codegraph/src/mcp/session.ts:228` quote: "// most hosts only request the list once per connection."), so EMPTY copy that says "don't call" kills same-session pickup and strands the listed tools.

**BT-3 (M3) — no heavy open before `sendResult`.** Pin a test that fails if the initialize handshake awaits `CodeGraph.open` / `Parser.init` / `loadCodeGraph().openSync` before `sendResult`. The existing watcher-seq test (`codegraph/__tests__/mcp-initialize.test.ts:151` quote: "expect(response.seq).toBeLessThan(watcherLog.seq);") is NOT sufficient — a heavy sync open before `sendResult` still precedes the background "File watcher active" stderr marker it keys on, so the COUNT→open swap passes it. Required shape: on a usable-db fixture, assert engine `open`/`openSync`/`Parser.init` was NOT invoked before the initialize reply was written (spy/ordering assertion on the pre-reply window), not relative sequence of two logs — usable-db path may run only the probe's COUNT before the reply.

**BT-4 (m1) — worktree copy lock.** `codegraph/src/sync/worktree.ts:89` and `:103` (`codegraph init -i` → `codegraph init`) are part of the bucket's copy lock; plan-verify pins greps on both sites. Out: `site/`, `CHANGELOG.md`, markdown docs.

**BT-5 (big-RT M1) — nonempty list source pinned on BOTH doors.** Session-door test on busy and empty fixtures: `tools/list` returns the SAME tool NAMES as `getStaticTools()` and produces them with NO `CodeGraph.open` / `loadCodeGraph().openSync` / `ensureInitialized` having run (spy the engine/loader; the list must be a state decision, not an engine decision). Same assertion class runs on the proxy door via BT-1's fixtures. Plan-verify pins: `grep-present 'getStaticTools' codegraph/src/mcp/session.ts` and `grep-present 'getStaticTools' codegraph/src/mcp/proxy.ts`. No whole-file `grep-absent 'hasDefaultCodeGraph'` in session.ts — `retryInitIfNeeded` still legitimately uses it for engine recovery at `codegraph/src/mcp/session.ts:281` (`if (this.engine.hasDefaultCodeGraph()) return;`); a targeted grep-absent aimed at the tools-list path must name the pairing so an honest mention stays legal (Step 3b dual-predicate discipline).

**BT-6 (big-RT M2) — probe-throw fallback test.** Stub the imported probe to throw; with a root fixture PRESENT, assert initialize serves the full `SERVER_INSTRUCTIONS` playbook and `tools/list` is nonempty from `getStaticTools()` — this is today's exact behavior and must be preserved as the fallback, NOT mapped to `index_missing`. With root absent, assert `[]` + reworded UNINDEXED (unchanged). Floor pin: `MIN_NODE_MAJOR` stays 20 — plan-verify `grep-present 'MIN_NODE_MAJOR = 20' codegraph/src/bin/node-version-check.ts`; no MCP-specific Node floor is introduced.

Deferred to spec per dispatch — big-RT m2 (BT-1 grep needs call-count ≥2 or per-branch pin to dodge the unused-import pass), m4 (parity claim is for the **same startPath**; session vs proxy read different start sources), m5 (pin "probe is COUNT not `open`", not a ≤500ms wall that `busy_timeout` cannot enforce).

## Risks

- **Handshake latency regression** (#172): the sync probe sits inside the initialize reply path where previously only existsSync ran — old invariant: `codegraph/src/mcp/session.ts:193` quote: "// synchronous walk-up (existsSync loop only, no DB open, so the #172"; worst case is the probe's busy cap: `codegraph/src/directory.ts:132` quote: "db.exec('PRAGMA busy_timeout = 500');".
  - *Mitigation:* engine init stays backgrounded: `codegraph/src/mcp/session.ts:216` quote: "this.resolvePromise = this.engine.ensureInitialized(explicitPath);".
  - The ordering test stays green: `codegraph/__tests__/mcp-initialize.test.ts:130` quote: "it('sends initialize response BEFORE tryInitializeDefault finishes', async () => {"; spec pins a new "initialize under busy lock still replies" case with a 5s wall.
  - Mini-RT M3 caveat: that watcher-seq test alone is NOT sufficient — it keys on the background "File watcher active" stderr marker, so a heavy sync `openSync`/`CodeGraph.open` before `sendResult` would still pass it. BT-3 (Binding tests) closes this: spy/ordering assertion that no heavy open runs before the reply on the usable-db path.
- **Busy flapping:** an index being written during handshake reads busy → busy copy; the very next `tools/list` may already be usable. *Mitigation:* re-probe per `tools/list` instead of caching the initialize decision; busy copy says "retry later", which matches flapping gracefully.
- **Residual internal `isError` on racing tool calls:** the default no-`projectPath` failure path is already SUCCESS-shaped: `codegraph/src/mcp/tools.ts:834` quote: "'No CodeGraph project is loaded for this session.\\n' +"; the explicit-path busy/junk-on-open residual (`codegraph/src/mcp/tools.ts:897` quote: "const cg = loadCodeGraph().openSync(resolvedRoot);") is deferred via OQ-3. *Mitigation:* FCV enumerates all NotIndexedError/internal-error paths before the plan locks the spec.
- **Probe unavailable (Node < 22.5):** the require can throw: `codegraph/src/directory.ts:123` quote: "const { DatabaseSync } = require('node:sqlite') as {". *Mitigation:* throw → existence-gate fallback (root found ⇒ usable-enough serving + `getStaticTools()`, matching today's engine path that never uses `node:sqlite`; root absent ⇒ `index_missing`). Not mapped to missing-behavior — that would hide a working index on the declared Node 20 floor. Documented in G-10 + BT-6 + Assumptions to verify #9/#10.
- **Fork survival:** the new mcp→`directory.ts` probe dependency must be recorded in `codegraph/UPDATING.md` or an upstream merge silently reverts it. *Mitigation:* implementation step + plan verify qualifier `grep-present` on the UPDATING.md row.

## Open Questions

**OQ-1 — Busy copy: separate constant vs parameterized builder** · **CLOSED 2026-08-19 as A (mini-RT m3, ORCH-adjudicated).** Ship a separate `SERVER_INSTRUCTIONS_INDEX_BUSY` constant (new) — NOT a builder over `SERVER_INSTRUCTIONS_INDEX_EMPTY` (a builder lets busy silently collapse into empty copy, exactly the m3 gaming path). Byte-static, greppable, test asserts equality.

**OQ-2 — Probe re-run on every `tools/list` vs cache-until-change** · Current: design re-probes per request to preserve pickup-after-init. **If [A] re-probe:** +1 read-only COUNT per request (sub-ms), state always fresh — default. **If [B] cache:** saves microseconds, adds invalidation rules (today only implicit as engine-reopen). Recommendation: A — the COUNT is cheaper than the existsSync re-walk that already runs per call: `codegraph/src/mcp/tools.ts:870` quote: "const resolvedRoot = findNearestCodeGraphRoot(projectPath);".

**OQ-3 — Scope of junk-db tool-CALL honesty** · Current design only differentiates the explicit-path `NotIndexedError` copy. A `projectPath` pointing at a *busy* db may still fail at open: `codegraph/src/mcp/tools.ts:897` quote: "const cg = loadCodeGraph().openSync(resolvedRoot);" as a generic internal error. **If [A] spec also maps that open failure to SUCCESS-shaped retry copy:** more recoverable≠isError compliance, more tools.ts churn. **If [B] defer:** initialize + tools/list already say busy; a racing tool call is the narrow residual. Recommendation: A if FCV shows the failure reachable in a realistic ACP flow; else B, recorded in the RT's review scope rather than the plan's.

**OQ-4 — Live daemon-door test shape (R4-a craft)** · **CLOSED 2026-08-19 as A (mini-RT M1, ORCH-adjudicated).** Stub-deps unit test: inject `LocalHandshakeDeps` (never-ready daemon) into `runLocalHandshakeProxy` (`codegraph/src/mcp/proxy.ts:204` quote: "export async function runLocalHandshakeProxy(deps: LocalHandshakeDeps): Promise<void> {") and assert stdout payloads per state — BT-1 above. No live daemon spawn required; the Windows `EPERM` afterEach flakiness class (codegraph CLAUDE.md: spawned `serve --mcp` holding SQLite) is dodged entirely.

## ADR references

- `external: /Users/phatchenh/all-projects/vibe-coding-setup/codegraph-piggyback/codegraph/docs/adr/0001-init-repairs-unusable-index.md:70-71` — "It is deliberately **not** added to the `src/index.ts` barrel and **not** imported by `src/mcp/**`"; the same ADR pre-authorizes this bucket's carve-out at `external: /Users/phatchenh/all-projects/vibe-coding-setup/codegraph-piggyback/codegraph/docs/adr/0001-init-repairs-unusable-index.md:76-77` — "Buckets 5 and 6 own their own health/ready unions (the MCP empty-warning threshold, any future ready-stamp or daemon-visible health signal) independently; this ADR does not pre-empt them." This bucket is the carve-out: MCP imports the probe directly (barrel untouched) and owns the 3-arm mapping. The ADR's repair decision table is the 5-arm vocabulary being mapped from.
- New ADR offered with impl (see Recommendation gate check above).

## Options explored (not chosen)

- **B — door-inline duplication:** viable but re-creates the two-doors-drift hazard the frozen contract exists to kill; the mapping table is exactly the content Bucket 6 will need to read consistently.
- **C — selector-only centralization:** half a seam (text yes, probe no); leaves try/catch + mapping duplicated anyway; the spec then has no single owner for the state decision.
- **D — health-aware `isInitialized`:** not viable under the dispatch freeze + grill's dropped-alternatives list; re-opens Bucket 4's settled CLI contract.
- **E — per-reason missing constants:** constant proliferation against a frozen tri-state vocabulary; the remediation text would be identical anyway.

## Read-set

- `codegraph/src/mcp/session.ts:1-320` (full) — gates at `:202`, `:209`, `:220-232`, retry walk `:275-298`.
- `codegraph/src/mcp/proxy.ts:176-378` — `runLocalHandshakeProxy`, payload sites `:289-301`, suppression `:340-346`, fallback `:245-266`.
- `codegraph/src/directory.ts:93-166, 263-293` — `isInitialized`, `probeIndexHealth`, `isUsableRoot`, `findNearestCodeGraphRoot`.
- `codegraph/src/mcp/engine.ts:42-175` — `MCPEngine` init/ensure/retry, open sites `:131`, `:167`.
- `codegraph/src/mcp/server-instructions.ts:20-91` (full).
- `codegraph/src/mcp/tools.ts:44, 625-645, 653-818, 829-899, 1190-1241, 2240-2290` — `NotIndexedError`, `getStaticTools`/`DEFAULT_MCP_TOOLS`, `ToolHandler` gates, catch shape, emptyWarn.
- `codegraph/src/mcp/index.ts:133-160, 259-300, 433-459` — daemon root resolution, mode pick, local-handshake wiring.
- `codegraph/src/mcp/daemon.ts:47-235` (CONSUMER-ONLY — idle timeout line `:60`).
- `codegraph/src/bin/codegraph.ts:590-640, 1555-1605` — CLI probe dispatch table, `serve` wiring to `MCPServer`.
- `codegraph/__tests__/mcp-initialize.test.ts` (full); `codegraph/__tests__/probe-index-health.test.ts:1-70` (fixture patterns: junk text / missing `nodes` table / exclusive lock / version skip guard).
- `codegraph/docs/adr/0001-init-repairs-unusable-index.md` (full).
- `docs/AI_artifacts/_handoff/2026-08-19-bkt5-codegraph-mcp-grill.md` (full); `docs/AI_artifacts/_scope/2026-08-16-feedback-bugs-scope.md` Bucket 5; `.village/runs/2026-08-16-feedback-scope-scout/channel/SCOUT_DIGEST.md` ITEM-1-cg; `docs/TECH_DEBT.md` TD-01.

## Assumptions to verify

1. **Proxy never gates its instructions today**: `codegraph/src/mcp/proxy.ts:298` quote: "serverInfo: SERVER_INFO, instructions: SERVER_INSTRUCTIONS } });".
2. **Nor its tool list**: `codegraph/src/mcp/proxy.ts:301` quote: "result: { tools: getStaticTools() } });". Why: the entire bug lives or dies here; if some wrapper rewrites these, the fix point moves.
3. **Hollow db opens cleanly as the default project**: `codegraph/src/mcp/engine.ts:167` quote: "this.cg = await loadCodeGraph().open(resolvedRoot);" — no 0-node rejection.
4. **Availability is a mere null-check**: `codegraph/src/mcp/tools.ts:728` quote: "return this.cg !== null;". Why: these two prove direct-mode "indexed" is true for empty dbs today.
5. **Probe does not mutate and closes its handle**: `codegraph/__tests__/probe-index-health.test.ts:10` quote: "* the probe never mutates bytes (sha256 unchanged) and it always closes its". Why: safe on the handshake hot path.
6. **`resolveDaemonRoot` only proves existence**: `codegraph/src/mcp/index.ts:160` quote: "const root = findNearestCodeGraphRoot(candidate);". Why: proxy mode is entered for hollow/junk dbs alike; the fix cannot be skipped "because root resolved".
7. **Daemon's own sessions never answer a host's `initialize` visibly**: `codegraph/src/mcp/proxy.ts:344` quote: "if (clientInitId !== undefined && resp.id === clientInitId) continue;". Why: keeps "both doors" the only payload owners.
8. **Stale `init -i` copy sites (superseded by mini-RT m1 enumeration):** three code-served sites now pinned — `codegraph/src/mcp/tools.ts:2276` quote: "run `codegraph init -i` in this directory before exploring."
8a. · `codegraph/src/sync/worktree.ts:89` quote: "codegraph init -i" · `codegraph/src/sync/worktree.ts:103` quote: "codegraph init -i" — both MCP-served via tool-result text. FCV must STILL `grep` the whole fork for `init -i` to catch any remainder; `site/`/`CHANGELOG.md`/docs hits are explicitly out of this bucket. Why (8+8a): lock 5-a applies to all user-visible strings, not one site.
9. **`node:sqlite` require can throw at runtime**: `codegraph/src/directory.ts:123` quote: "const { DatabaseSync } = require('node:sqlite') as {".
10. **The Node-version skip guard confirms the throw branch**: `codegraph/__tests__/probe-index-health.test.ts:13` quote: "* Skipped on Node < 22.5 where node:sqlite doesn't exist.". Why (9+10): mandates try/catch at every new MCP call site.
11. **Direct mode is the minority host path**: tests pin daemon-off: `codegraph/__tests__/mcp-initialize.test.ts:33` quote: "env: { ...process.env, CODEGRAPH_NO_DAEMON: '1' },".
12. **Production hosts launch plain `serve --mcp`**: `codegraph/src/bin/codegraph.ts:1597` quote: "const { MCPServer } = await import('../mcp/index');". Why (11+12): the proxy door is the live path and drives this bucket's ROI, as the grill's ORCH-burden table already concluded.

Next step: red-team review of this design, then `/writing-detailed-specs` to structure the chosen option into build steps.
