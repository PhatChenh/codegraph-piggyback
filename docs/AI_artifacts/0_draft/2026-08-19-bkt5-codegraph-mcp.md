# Design — Bucket 5: MCP tells missing vs empty vs usable (ITEM-1-cg)

- _Date:_ 2026-08-19
- _Run:_ `2026-08-19-bkt5-codegraph-mcp` (protocol card `.village/runs/2026-08-19-bkt5-codegraph-mcp/protocol-card.md`)
- _Locked requirements:_ `docs/AI_artifacts/_handoff/2026-08-19-bkt5-codegraph-mcp-grill.md` (LOCKED 2026-08-19)
- _Scope parent:_ `docs/AI_artifacts/_scope/2026-08-16-feedback-bugs-scope.md` Bucket 5
- _Code home:_ `codegraph/` fork (tracked under this repo's `codegraph/` tree)
- _Dispatcher:_ `NON-INTERACTIVE: true` — no AskUserQuestion gates; non-recommended branches go to Open Questions

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
- **Mapping 5→3:** `usable`→usable, `empty`→`index_empty`, `unreadable`→missing-behavior, `unclassified`→missing-behavior, `busy`→empty-style (tools stay listed, short "busy, retry later" copy). Locks 3-a + 1-a.
- **`tools/list` empty ONLY for missing.** Empty-db and busy keep tools listed (scope freeze in `docs/AI_artifacts/_scope/2026-08-16-feedback-bugs-scope.md`).
- **Cheap COUNT before the handshake reply; heavy init stays background** (lock 2-a; #172). The probe is a read-only open: `codegraph/src/directory.ts:131` quote: "db = new DatabaseSync(dbPath, { readOnly: true });".
- Plus a 500ms busy cap: `codegraph/src/directory.ts:132` quote: "db.exec('PRAGMA busy_timeout = 500');".
- Plus one COUNT: `codegraph/src/directory.ts:133` quote: "const row = db.prepare('SELECT COUNT(*) AS n FROM nodes').get() as { n: number };".
- **Import, don't duplicate:** MCP imports `probeIndexHealth` from `../directory` and maps it; no second COUNT implementation; no third public enum from `src/index.ts` (dispatch). `isInitialized` semantics unchanged: `codegraph/src/directory.ts:100` quote: "return fs.existsSync(dbPath);".
- **Same payloads on both doors** (lock 4-a).
- **Recoverable ≠ `isError`**: `codegraph/src/mcp/tools.ts:1228` quote: "if (err instanceof NotIndexedError) {".
- **Copy:** missing/empty text says the **user** runs `codegraph init`; the agent never self-inits; never stale `init -i` (lock 5-a). Stale site today at `codegraph/src/mcp/tools.ts:2276` quote: "run `codegraph init -i` in this directory before exploring.".
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
| G-10 | Probe throw must not wedge the handshake (fail-open serving, fail-closed state) | probe's require lives inside the function body: `codegraph/src/directory.ts:123` quote: "const { DatabaseSync } = require('node:sqlite') as {" | every new call site wraps the probe in try/catch → throw maps to missing-behavior — designed in Chosen Approach |

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

**Approach:** add `codegraph/src/mcp/index-state.ts` (new) exporting `McpIndexState` (new) = `'index_missing' | 'index_empty' | 'usable'` plus `resolveMcpIndexState(startPath)` (new): walk via `findNearestCodeGraphRoot`; null → `index_missing`; else try `probeIndexHealth(root)` and map (`usable`→usable; `empty`→`index_empty`; `busy`→`index_empty` with busy flag; `unreadable`/`unclassified`/throw → `index_missing`). Both doors call it at every `initialize` and `tools/list`; instructions selected from 4 constants (`SERVER_INSTRUCTIONS` / `SERVER_INSTRUCTIONS_UNINDEXED` reworded / `SERVER_INSTRUCTIONS_INDEX_EMPTY` (new) / `SERVER_INSTRUCTIONS_INDEX_BUSY` (new)); `tools/list` returns `[]` only for `index_missing`. `tools.ts` gets two copy fixes: emptyWarn → `codegraph init` (`codegraph/src/mcp/tools.ts:2276` quote: "run `codegraph init -i` in this directory before exploring.") and explicit-path `NotIndexedError` differentiates missing vs unreadable (`codegraph/src/mcp/tools.ts:873` quote: "throw new NotIndexedError(").
**Files touched (reason):** new `codegraph/src/mcp/index-state.ts` (mapping, single owner); `codegraph/src/mcp/session.ts` (gate initialize + tools/list on state instead of existsSync/engine-open); `codegraph/src/mcp/proxy.ts` (gate local-handshake initialize + tools/list on probe of `deps.root`); `codegraph/src/mcp/server-instructions.ts` (reword UNINDEXED + two new constants); `codegraph/src/mcp/tools.ts` (two copy sites); `codegraph/__tests__/mcp-initialize.test.ts` + new proxy-handshake test (state cases, both doors); `codegraph/UPDATING.md` patch row + `CHANGELOG.md` `[Unreleased]` (fork discipline).
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

One mcp-internal helper `codegraph/src/mcp/index-state.ts` (new) owns the walk → probe → throw-guard → 5→3 map and the `McpIndexState` union. Direct detail and door wiring:

- `MCPSession` replaces the boolean gate: `codegraph/src/mcp/session.ts:202` quote: "const indexed = findNearestCodeGraphRoot(explicitPath ?? process.cwd()) !== null;" with a `resolveMcpIndexState(explicitPath ?? process.cwd())` call; instructions selected per state.
- `handleToolsList` re-resolves and returns `[]` only for `index_missing`, otherwise the existing engine/static list for usable, `index_empty`, and busy (pickup-after-init preserved per `codegraph/src/mcp/session.ts:227` quote: "// picked up on the next tools/list — retryInitIfNeeded re-walks — though").
- The direct-mode caller chain is unchanged (`handleMessage` → `handleInitialize`): `codegraph/src/mcp/session.ts:125` quote: "if (isRequest) await this.handleInitialize(message as JsonRpcRequest);".
- The proxy resolves state from `deps.root` at its initialize branch inside `runLocalHandshakeProxy`: `codegraph/src/mcp/proxy.ts:289` quote: "if (msg.method === 'initialize') {".
- Its production caller is `runProxyWithLocalHandshake`: `codegraph/src/mcp/index.ts:458` quote: "await runLocalHandshakeProxy({ getDaemonSocket, makeEngine: () => new MCPEngine(), root });".
- Which in turn is invoked by `MCPServer.start`'s step 4: `codegraph/src/mcp/index.ts:291` quote: "await this.runProxyWithLocalHandshake(root);".
- And at its tools/list branch: `codegraph/src/mcp/proxy.ts:300` quote: "} else if (msg.method === 'tools/list') {" — identical payload table, so door parity is structural.
- Busy is `index_empty`-style for tools but carries its own short constant `SERVER_INSTRUCTIONS_INDEX_BUSY` (new) — not a fourth state name.
- `tools.ts` copy edit 1: `codegraph/src/mcp/tools.ts:2276` quote: "run `codegraph init -i` in this directory before exploring." → names `codegraph init`.
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
| `busy` | `index_empty` (busy flag) | `SERVER_INSTRUCTIONS_INDEX_BUSY` (new) | defs |
| `unreadable` | `index_missing` | UNINDEXED (reworded) | `[]` |
| `unclassified` | `index_missing` | UNINDEXED (reworded) | `[]` |
| probe throws (no node:sqlite) | `index_missing` | UNINDEXED (reworded) | `[]` |

## Risks

- **Handshake latency regression** (#172): the sync probe sits inside the initialize reply path where previously only existsSync ran — old invariant: `codegraph/src/mcp/session.ts:193` quote: "// synchronous walk-up (existsSync loop only, no DB open, so the #172"; worst case is the probe's busy cap: `codegraph/src/directory.ts:132` quote: "db.exec('PRAGMA busy_timeout = 500');".
  - *Mitigation:* engine init stays backgrounded: `codegraph/src/mcp/session.ts:216` quote: "this.resolvePromise = this.engine.ensureInitialized(explicitPath);".
  - The ordering test stays green: `codegraph/__tests__/mcp-initialize.test.ts:130` quote: "it('sends initialize response BEFORE tryInitializeDefault finishes', async () => {"; spec pins a new "initialize under busy lock still replies" case with a 5s wall.
- **Busy flapping:** an index being written during handshake reads busy → busy copy; the very next `tools/list` may already be usable. *Mitigation:* re-probe per `tools/list` instead of caching the initialize decision; busy copy says "retry later", which matches flapping gracefully.
- **Residual internal `isError` on racing tool calls:** the default no-`projectPath` failure path is already SUCCESS-shaped: `codegraph/src/mcp/tools.ts:834` quote: "'No CodeGraph project is loaded for this session.\\n' +"; the explicit-path busy/junk-on-open residual (`codegraph/src/mcp/tools.ts:897` quote: "const cg = loadCodeGraph().openSync(resolvedRoot);") is deferred via OQ-3. *Mitigation:* FCV enumerates all NotIndexedError/internal-error paths before the plan locks the spec.
- **Probe unavailable (Node < 22.5):** the require can throw: `codegraph/src/directory.ts:123` quote: "const { DatabaseSync } = require('node:sqlite') as {". *Mitigation:* throw → `index_missing` (the agent gets the safe "inactive" note instead of a lying playbook); documented in the helper's JSDoc + Assumptions to verify #7.
- **Fork survival:** the new mcp→`directory.ts` probe dependency must be recorded in `codegraph/UPDATING.md` or an upstream merge silently reverts it. *Mitigation:* implementation step + plan verify qualifier `grep-present` on the UPDATING.md row.

## Open Questions

**OQ-1 — Busy copy: separate constant vs parameterized builder** · Current: design pins a 4th constant `SERVER_INSTRUCTIONS_INDEX_BUSY` (new). Question: one constant, or build busy as a one-line prefix over `SERVER_INSTRUCTIONS_INDEX_EMPTY`? **If [A] separate constant:** byte-static, greppable, test asserts equality — chosen default. **If [B] builder:** less text duplication, one more indirection for a single reuse. Recommendation: A — constants are the module's established shape and tests pin them verbatim.

**OQ-2 — Probe re-run on every `tools/list` vs cache-until-change** · Current: design re-probes per request to preserve pickup-after-init. **If [A] re-probe:** +1 read-only COUNT per request (sub-ms), state always fresh — default. **If [B] cache:** saves microseconds, adds invalidation rules (today only implicit as engine-reopen). Recommendation: A — the COUNT is cheaper than the existsSync re-walk that already runs per call: `codegraph/src/mcp/tools.ts:870` quote: "const resolvedRoot = findNearestCodeGraphRoot(projectPath);".

**OQ-3 — Scope of junk-db tool-CALL honesty** · Current design only differentiates the explicit-path `NotIndexedError` copy. A `projectPath` pointing at a *busy* db may still fail at open: `codegraph/src/mcp/tools.ts:897` quote: "const cg = loadCodeGraph().openSync(resolvedRoot);" as a generic internal error. **If [A] spec also maps that open failure to SUCCESS-shaped retry copy:** more recoverable≠isError compliance, more tools.ts churn. **If [B] defer:** initialize + tools/list already say busy; a racing tool call is the narrow residual. Recommendation: A if FCV shows the failure reachable in a realistic ACP flow; else B, recorded in the RT's review scope rather than the plan's.

**OQ-4 — Live daemon-door test shape (R4-a craft)** · R4-a pins "live = vitest spawn of `serve --mcp`". The proxy door can also be unit-tested by injecting stubbed `LocalHandshakeDeps` (never-ready daemon) into `runLocalHandshakeProxy` and asserting stdout payloads directly. **If [A] stub-deps unit test:** fast, no daemon cleanup, covers the payload table for empty/junk/busy. **If [B] real daemon spawn:** also covers daemon-session parity but reproduces the Windows `EPERM` afterEach flakiness class already documented for this suite (codegraph CLAUDE.md: spawned `serve --mcp` holding SQLite). Recommendation: A as the primary, B only as an optional POSIX-gated smoke if the RT demands end-to-end proof.

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
8. **Stale `init -i` copy has exactly one site in mcp/**: `codegraph/src/mcp/tools.ts:2276` quote: "run `codegraph init -i` in this directory before exploring."; FCV must `grep` the whole fork for `init -i` to extend the copy fix if more sites exist. Why: lock 5-a applies to all user-visible strings, not one site.
9. **`node:sqlite` require can throw at runtime**: `codegraph/src/directory.ts:123` quote: "const { DatabaseSync } = require('node:sqlite') as {".
10. **The Node-version skip guard confirms the throw branch**: `codegraph/__tests__/probe-index-health.test.ts:13` quote: "* Skipped on Node < 22.5 where node:sqlite doesn't exist.". Why (9+10): mandates try/catch at every new MCP call site.
11. **Direct mode is the minority host path**: tests pin daemon-off: `codegraph/__tests__/mcp-initialize.test.ts:33` quote: "env: { ...process.env, CODEGRAPH_NO_DAEMON: '1' },".
12. **Production hosts launch plain `serve --mcp`**: `codegraph/src/bin/codegraph.ts:1597` quote: "const { MCPServer } = await import('../mcp/index');". Why (11+12): the proxy door is the live path and drives this bucket's ROI, as the grill's ORCH-burden table already concluded.

Next step: red-team review of this design, then `/writing-detailed-specs` to structure the chosen option into build steps.
