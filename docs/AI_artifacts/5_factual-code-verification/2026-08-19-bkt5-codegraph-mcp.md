# Factual Code Verification: Bucket 5 — MCP missing vs empty vs usable
_Last updated: 2026-08-19_

Spec: `docs/AI_artifacts/4_specs/2026-08-19-bkt5-codegraph-mcp.md`
Design: `docs/AI_artifacts/3_design/2026-08-19-bkt5-codegraph-mcp.md`
Grill: `docs/AI_artifacts/_handoff/2026-08-19-bkt5-codegraph-mcp-grill.md` (LOCKED)
Protocol: `.village/runs/2026-08-19-bkt5-codegraph-mcp/protocol-card.md`
TD-01: OPEN (`docs/TECH_DEBT.md`). OQ-2 OPEN (spec builds A). OQ-3 OPEN.

Runtime this session: shell `codegraph explore` worked (`.codegraph/` present at piggyback root). MCP `user-codegraph` served **only** `mcp_auth` with inactive-index copy — that is the live lie this bucket fixes (existence-true index still advertised as missing to this Cursor session, or tools gated). Inventory is Read of the spec `## Read-set` after MCP tools failed.

`node:sqlite` `DatabaseSync` **Added in: v22.5.0** (fetched 2026-08-19): https://nodejs.org/dist/latest-v22.x/docs/api/sqlite.html — Node 20–22.4 `require('node:sqlite')` throws; mapper catch is load-bearing.

## Overview

MCP handshake today is **existence-only on the session door** and **ungated full playbook + `getStaticTools()` on the proxy door**. Hollow 0-node dbs look indexed (engine `open` has no COUNT reject; `hasDefaultCodeGraph` is `cg !== null`). Proxy never consults the db. Session `tools/list` **awaits** `retryInitIfNeeded()` then keys on `hasDefaultCodeGraph()` + `getTools()` (budget suffix once `cg` loads). `probeIndexHealth` is CLI-only (`directory.ts`); zero `src/mcp/` importers. `index-state.ts` does not exist.

This pass verified spec A1–A20 + S1–S6 against disk. **0 invalidated. 0 unverifiable. Structural audit: pass.** C1-a: `engine.ts` open + `daemon.ts` idle-kill are the **same** handshake-adjacent contract (existence walk, no COUNT, lifecycle not payload) — **no A-split**. Ready for `/plan`.

Calibration (auto-proceed, NON-INTERACTIVE): deep-trace `proxy.ts`, `session.ts`, `tools.ts` (`getStaticTools`/`getTools`/`getCodeGraph`/`execute`), `directory.ts` (`probeIndexHealth`/`findNearestCodeGraphRoot`/`isInitialized`), `engine.ts`, `mcp/index.ts` (`start`/`resolveDaemonRoot`/`runProxyWithLocalHandshake`), `server-instructions.ts`, `worktree.ts`, `mcp-initialize.test.ts`, `probe-index-health.test.ts`; surface `node-version-check.ts`, `codegraph.ts` serve, installer `shared.ts`/`cursor.ts`, ADR 0001, `daemon.ts:60`, `db/index.ts:31`, UPDATING/CHANGELOG; skip `installer/targets/cursor.ts` body beyond MCP args (OUT), writ probe (Bucket 6), `runProxy` (definition only).

## Key Components

| Symbol | Site | Role now |
|---|---|---|
| `runLocalHandshakeProxy` | `codegraph/src/mcp/proxy.ts:204-378` | listen-first stdin; initialize `:298` always `SERVER_INSTRUCTIONS`; tools/list `:301` always `getStaticTools()`; suppress daemon init `:344`; `getDaemonSocket` await `:324` **after** stdin `:281` |
| `LocalHandshakeDeps` | `proxy.ts:180-189` | `getDaemonSocket` / `makeEngine` / `root` — handshake **does not read `deps.root` today** (the lie) |
| `runProxy` | `proxy.ts:83` | **definition only** — no `src/` caller |
| `handleInitialize` | `session.ts:163-218` | `indexed = findNearestCodeGraphRoot(explicitPath ?? cwd) !== null` `:202`; `sendResult` then `ensureInitialized` `:216` |
| `handleToolsList` | `session.ts:220-232` | **`await retryInitIfNeeded()`** `:221` then `hasDefaultCodeGraph() ? getTools() : []` `:230` |
| `handleToolsCall` | `session.ts:234-265` | keeps `await retryInitIfNeeded()` `:258` then `execute` `:260` |
| `retryInitIfNeeded` | `session.ts:275-298` | await in-flight; `hasDefaultCodeGraph` `:281`; roots/list **after** initialize; `retryInitializeSync` |
| `getStaticTools` | `tools.ts:625-632` | allowlist, **no** budget suffix. Callers: `proxy.ts` only |
| `DEFAULT_MCP_TOOLS` | `tools.ts:645` | `explore` only |
| `ToolHandler.getTools` | `tools.ts:759-817` | same allowlist **plus** budget suffix `:806-811` once `cg`; tiny-repo extra filter `:802-804` |
| `hasDefaultCodeGraph` | `tools.ts:727-728` + `engine.ts:82-83` | `this.cg !== null` / delegate |
| `getCodeGraph` | `tools.ts:829-899` | no-path: NotIndexedError SUCCESS-shaped `:833-843`; explicit: `findNearestCodeGraphRoot` then `openSync` `:897` — **no probe** |
| `execute` | `tools.ts:1149-1241` | sole tool-call intake; NotIndexedError → `textResult` `:1228-1229`; other → `errorResult` `:1235` |
| `emptyWarn` | `tools.ts:2273-2276` | `codegraph init -i` |
| `probeIndexHealth` | `directory.ts:116-166` | `require('node:sqlite')` **outside** try `:123`; try `:130`; COUNT `:133`; `finally` close `:157-164` |
| `isInitialized` | `directory.ts:93-100` | `existsSync(dbPath)` |
| `findNearestCodeGraphRoot` | `directory.ts:274-293` | existence walk + unsafe-root skip |
| `MCPEngine.doInitialize` | `engine.ts:155-175` | walk then `loadCodeGraph().open` `:167` — **no 0-node reject** |
| `MCPServer.start` | `mcp/index.ts:259-300` | NO_DAEMON → direct; `!root` → `startDirect('no .codegraph/ root found')` `:281`; else proxy `:291` |
| `resolveDaemonRoot` | `mcp/index.ts:158-163` | `findNearestCodeGraphRoot` + `realpathSync` |
| `SERVER_INSTRUCTIONS_UNINDEXED` | `server-instructions.ts:82-91` | claims **no `.codegraph/` directory** `:84` |
| `worktreeMismatchWarning` / `Notice` | `worktree.ts:83-105` | `codegraph init -i` `:89,:103` |
| `MIN_NODE_MAJOR` | `node-version-check.ts:48` | `20` |
| `DEFAULT_IDLE_TIMEOUT_MS` | `daemon.ts:60` | `300_000` — CONSUMER-ONLY |
| `configureConnection` | `db/index.ts:31` | `busy_timeout = 5000` (engine, not probe) |
| `index-state.ts` / `McpIndexState` / `instructionsForMcpIndex` / EMPTY / BUSY | **absent** | spec create |

## How It Works

**Production host path (no `CODEGRAPH_NO_DAEMON`).** `serve --mcp` constructs `MCPServer` (`codegraph.ts:1597-1599`). Installer injects `args: ['serve', '--mcp']` (`installer/targets/shared.ts:28`); Cursor adds `--path` (`cursor.ts:173`) — **does not** set `CODEGRAPH_NO_DAEMON`. `start()`: if a `.codegraph/` root exists → `runProxyWithLocalHandshake(root)` (`index.ts:277-291`). Proxy attaches stdin **before** awaiting the daemon (`proxy.ts:281` then `:324`). `initialize` writes full `SERVER_INSTRUCTIONS` + routes the line to the daemon; daemon initialize result with matching id is dropped (`:344`). `tools/list` writes `getStaticTools()` and is **not** forwarded. True no-directory missing never enters proxy — `startDirect`.

**Direct / test path (`CODEGRAPH_NO_DAEMON=1`).** `mcp-initialize.test.ts:33` pins this. Session `handleInitialize`: existence walk `:202`; `sendResult` with playbook vs UNINDEXED; then background `ensureInitialized` `:216` (G-03 / #172). `handleToolsList` **waits on engine** then `getTools()` or `[]`. Hollow db: walk finds root → full playbook; `open` succeeds with 0 nodes → `cg !== null` → nonempty `getTools()` (budget suffix). Junk db: walk still finds root (`isInitialized`=`existsSync`); `open` may fail → `cg` stays null → **empty tools** on session door while proxy would still list tools — **door desync today**.

**Probe (CLI only).** `require` `:123` throws on Node <22.5 before `try` `:130` — never a 5-arm status. Catch maps errcodes. `finally` closes. Tests: sha256 unchanged `:169,:207`; close+reopen `:218`. ADR 0001 `:70-77`: not barrelled, **not imported by `src/mcp/**`** — this bucket **is** the carve-out.

**Tool calls.** `handleToolsCall` awaits engine (`session.ts:258`) then `execute`. All `handle*` (incl. `handleStatus` `:3622`) call `getCodeGraph`. Explicit junk: walk finds root → `openSync` `:897` → throw → `errorResult` `:1235` (`isError`) — OQ-3 residual, reachable on `projectPath`. Default-arm missing: NotIndexedError → SUCCESS `textResult`.

## Spec Verification

| Assumption ID | Spec Claim | Verdict | Evidence |
| A1 | Proxy never gates instructions; `:298` always `SERVER_INSTRUCTIONS` | ✅ Validated | `proxy.ts:298` `instructions: SERVER_INSTRUCTIONS`. `writeClient` `:230-231` is `process.stdout.write` — no rewrite wrapper |
| A2 | Proxy never gates tools; `:301` always `getStaticTools()` | ✅ Validated | `proxy.ts:301` `tools: getStaticTools()`. tools/list not forwarded to daemon |
| A3 | Hollow db opens as default; `engine.ts:167` no 0-node reject | ✅ Validated | `engine.ts:167` `this.cg = await loadCodeGraph().open(resolvedRoot);`. `CodeGraph.open` `index.ts:292-319` isInitialized + validateDirectory + `DatabaseConnection.open` — no COUNT |
| A4 | Availability is null-check `tools.ts:728` | ✅ Validated | `return this.cg !== null;`. Engine `:82-83` delegates to that |
| A5 | Probe does not mutate; always closes | ✅ Validated | `{ readOnly: true }` `directory.ts:131`; `finally` close `:157-164`; tests `:169-177`, `:207-215`, `:218-228` |
| A6 | `resolveDaemonRoot` existence-only | ✅ Validated | `index.ts:160` `findNearestCodeGraphRoot(candidate)` — no probe |
| A7 | Daemon initialize never visible to host | ✅ Validated | `proxy.ts:344` `if (clientInitId !== undefined && resp.id === clientInitId) continue;` |
| A8 | `tools.ts:2276` still `codegraph init -i` | ✅ Validated | `run \`codegraph init -i\` in this directory before exploring.` |
| A8a | worktree `:89,:103` still `init -i`; no fourth **src/** site | ✅ Validated | `rg -n "init -i" codegraph/src` → only those three. `site/`/CHANGELOG/docs out |
| A9 | `node:sqlite` require can throw | ✅ Validated | `directory.ts:123` outside try. Official: module Added in v22.5.0 (URL above). Tests `:24-30` catch require |
| A10 | Skip guard is Node <22.5 / module missing | ✅ Validated | `probe-index-health.test.ts:13` + `describe.skipIf(!nodeSqliteAvailable)` `:42` |
| A11 | Direct mode is minority; tests pin `CODEGRAPH_NO_DAEMON=1` | ✅ Validated | `mcp-initialize.test.ts:33`. Installer `shared.ts:28` `args: ['serve', '--mcp']` — no NO_DAEMON |
| A12 | Production `serve --mcp` constructs `MCPServer` | ✅ Validated | `codegraph.ts:1597-1599` `await import('../mcp/index')` / `new MCPServer` / `server.start()` |
| A13 | Proxy `deps.root` is a found root; true no-dir is session | ✅ Validated | `index.ts:277-281` `if (!root) return this.startDirect('no .codegraph/ root found');` else `:291` |
| A14 | `getTools()` byte-diverges via budget suffix; default **names** can match | ✅ Validated | `tools.ts:806-811` `` description: `${tool.description} Budget: make at most ${budget} calls...` ``. `DEFAULT_MCP_TOOLS` `:645` `explore`. Extra: tiny-repo filter `:802-804` — default names still `explore` |
| A15 | `handleToolsCall` must keep `await retryInitIfNeeded()` | ✅ Validated | `session.ts:258`. List also awaits today `:221` — that await is the bug to **remove from list only** |
| A16 | `require` outside probe `try` | ✅ Validated | `:123` then `try {` `:130`. Throw never becomes 5-arm status |
| A17 | `execute` is single intake; no handle* bypasses `getCodeGraph` | ✅ Validated | `session.ts:260`; `execute` `:1149`; switch `:1199`; every handle* calls `this.getCodeGraph` (grep). Other sqlite opens: `engine.ts:131,:167` + `tools.ts:897` only |
| A18 | `LocalHandshakeDeps` sufficient without live daemon | ✅ Validated | interface `:180-189`; stdin answers without `deps.root` today (fix will use it). Listen-first `:281` vs `:324` |
| A19 | Initialize startPath is `explicitPath ?? cwd`; not `roots/list` | ✅ Validated | `:202`. `explicitPath` from rootUri / workspaceFolders[0] / `--path` `:184-190`. `roots/list` only in `retryInitIfNeeded`/`initFromRoots` `:284-318` **after** initialize |
| A20 | Default-arm `getCodeGraph` already SUCCESS-shaped; helper needed on explicit arm | ✅ Validated | no-path NotIndexedError `:833-843` → `textResult` `:1228`. Explicit `:870+` existence walk only |
| S1 | Assumptions falsifiable | ✅ Validated | each A-row has a disproof condition |
| S2 | Done-when observable | ✅ Validated | C1–C8 name payloads/strings/spies, not “pytest green” |
| S3 | Independently testable | ✅ Validated | 1–6 have own Done-when; 7 depends on **earlier**, not later |
| S4 | No silent HOW deferrals | ✅ Validated | OQ-2 implements A in-spec; OQ-3 explicit defer; selector/mapper interfaces stated |
| S5 | Data model declared | ✅ Validated | `McpIndexState`, `{state,busy,root}`, mapping table |
| S6 | Dependency order sound | ✅ Validated | no cycles; engine/daemon CONSUMER-ONLY in Out-of-scope |

## Edge Cases & Silent Failure Modes

- **Door desync today:** junk/unreadable at a found root → proxy lists tools + full playbook; session list may be `[]` if `open` failed (`cg===null`). Spec makes both `index_missing` + `[]`.
- **Hollow db:** both doors look fully indexed. Spec: EMPTY copy + static tools, not playbook.
- **Busy (errcode 5):** probe returns `busy`; MCP maps empty-style + BUSY copy. Engine `busy_timeout=5000` is a **different** connection — handshake must use probe’s 500ms, not await engine.
- **Probe throw (Node 20–22.4):** existence-fallback **usable** if root found. Mapping throw→missing while root exists **undoes** today’s session playbook and is MUST-2.
- **`getTools()` vs `getStaticTools()`:** names can match (`explore`); JSON descriptions **do not** once `cg` loads (budget suffix). Session list using `getTools()` fails MUST-1 deep-equals.
- **List-path await:** `await retryInitIfNeeded()` then static tools still waits — MUST-1 forbids deciding the nonempty list via that await. Call-path await **must stay** (`:258`).
- **BT-3:** watcher-seq `mcp-initialize.test.ts:151` is stderr-marker only — a sync `open` before `sendResult` still passes it.
- **BT-1b:** immediately-null `getDaemonSocket` does **not** prove listen-first; pending promise required.
- **OQ-3 residual:** explicit-path junk that still `existsSync` → `openSync` `:897` → `errorResult` `isError`. Reachable in ACP if the agent passes `projectPath`. Spec does **not** map to SUCCESS this phase.
- **Hosts list once** (`session.ts:228` comment): EMPTY copy saying “inactive / don’t call” strands listed tools.
- **UNINDEXED `:84`** “no `.codegraph/` directory” is a **lie for junk** (file exists).
- **Proxy `index_missing` in prod** is junk/unreadable/unclassified at `deps.root` (or delete race), not a missing directory (A13).
- **`CODEGRAPH_MCP_TOOLS`** applies to nonempty lists only after this phase; missing stays `[]`.

## Dependencies & Coupling

- Mapper **must** import `probeIndexHealth` + `findNearestCodeGraphRoot` from `../directory` — **not** `src/index.ts` barrel (ADR 0001 `:70-77` carve-out; G-04).
- Session currently imports `findNearestCodeGraphRoot` (`session.ts:21`) — replace with mapper; keep `hasDefaultCodeGraph` on retry path.
- Proxy already imports `getStaticTools`, `SERVER_INSTRUCTIONS`, `SERVER_INFO`. Add mapper + selector; keep listen-first + `:344`.
- `getCodeGraph` explicit arm: call mapper not raw probe (MUST-2; one COUNT owner).
- Engine `ensureInitialized` after initialize **stays legal** (`session.ts:216`). Must **not** gate `tools/list`.
- Deletion test: helper consumed at **5** sites (session initialize + list; proxy initialize + list; `getCodeGraph`). Design “4 sites” is stale post-r2 M2 (spec constraint 13).
- CONSUMER-ONLY: `engine.ts` open, `daemon.ts` idle, `directory.ts` probe body, `isInitialized`, installer `cursor.ts`.
- R15: shared binary; no `settings.json` / `hooks.json` / `mcp.json` edits.

## Extension Points

- `[closed]` mapping table in `index-state.ts` — adding a fourth MCP name is a freeze break.
- `[extensible: config]` `CODEGRAPH_MCP_TOOLS` already filters `getStaticTools` / `getTools`.
- Instructions selector `[closed]` four constants; busy **before** state (OQ-1 CLOSED A).
- Probe 5-arm stays CLI; MCP 3-arm is independent (Bucket 6 writ union also independent).

## Open Questions

- **OQ-2** OPEN — spec implements **A** (re-resolve every `initialize` and `tools/list`; no cache). Plan must not silently switch to B.
- **OQ-3** OPEN — explicit-path `openSync` throw → `errorResult` (`tools.ts:897,1235`) **is reachable** (junk db that still satisfies `isInitialized`). Spec still defers SUCCESS-retry copy. Plan: do not expand. Residual stays.
- **TD-01** OPEN — shipping `.codegraph/ready` or plugin bus **fails** this spec.
- Human-authority: none new (copy + live=vitest locked in grill).

## Technical Debt Spotted

- Session `:192-201` comment still says “existsSync loop only, no DB open” — will be false after COUNT-before-reply; spec requires rewrite in the same edit.
- ADR 0001 sentence “not imported by `src/mcp/**`” becomes false for `directory.ts` (barrel stays clean). ADR 0002 cites the carve-out; **do not** amend 0001’s repair table.
- `getTools` comment `:761` still says “default 4-tool surface” while `DEFAULT_MCP_TOOLS` is explore-only — out of this bucket unless a test asserts it.
- Live MCP `user-codegraph` in this Cursor session advertises inactive copy despite `.codegraph/` existing — reproduces the honesty bug (or a stale MCP process). Not a code-change in FCV.

## Claim sweep

First write. A1–A20 + S1–S6 verified from disk this session (shell codegraph + Read). Spec line numbers were **not** trusted; several matched. Extra finding (not an invalidation): `getTools` tiny-repo filter when `cg` set — default names still match.

C1-a check: `engine.ts:167` still existence-walk + `open` with no COUNT; `daemon.ts:60` is client-idle linger, not initialize payload. Same contract. No A-split.
