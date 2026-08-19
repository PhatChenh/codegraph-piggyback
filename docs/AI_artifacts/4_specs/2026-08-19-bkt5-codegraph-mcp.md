# Phase Bucket 5 — MCP tells missing vs empty vs usable

_Date:_ 2026-08-19
_Design:_ `docs/AI_artifacts/3_design/2026-08-19-bkt5-codegraph-mcp.md` (Option A; r1 patch + r2 EXIT craft)
_Grill:_ `docs/AI_artifacts/_handoff/2026-08-19-bkt5-codegraph-mcp-grill.md` (LOCKED 2026-08-19)
_RT:_ `docs/AI_artifacts/7_reviews/2026-08-19-bkt5-codegraph-mcp-design-redteam.md` (r1) + `…-design-redteam-r2.md` (0 CRITICAL; r2 M1–M3 HOLD → Spec MUSTs below)
_Scope:_ `docs/AI_artifacts/_scope/2026-08-16-feedback-bugs-scope.md` Bucket 5 = ITEM-1-cg
_Surface:_ local fork `codegraph/` — MCP `initialize` + `tools/list` on **both** doors (`session.ts` **and** `proxy.ts`). One phase (grill: split forbidden).
_TD-01:_ stays **OPEN** (`docs/TECH_DEBT.md`). No plugin bus. No `.codegraph/ready`.
_OQ:_ OQ-1 CLOSED as A. OQ-4 CLOSED as A. **OQ-2 OPEN** (re-probe vs cache). **OQ-3 OPEN** (junk tool-call honesty).

## Purpose

MCP `initialize.instructions` and `tools/list` stop treating file-existence as “indexed.” After this phase a hollow 0-node db is `index_empty` (tools stay listed, short “run `codegraph init`” copy, **not** the full playbook); a missing/junk/unclassified index is `index_missing` (empty tool list + short inactive note); a locked index is empty-style with `SERVER_INSTRUCTIONS_INDEX_BUSY` (new) (tools stay, “busy, retry later” — not a fourth MCP name). Both the direct session door and the live local-handshake proxy emit the same payloads from `getStaticTools()` + one mapper. Cheap COUNT before the handshake reply; heavy engine init stays background (#172). Recoverable stays SUCCESS-shaped.

## Pre-dispatch audit

Codegraph MCP tools were **inactive** this workspace (no `.codegraph/` at piggyback root). Inventory is Read/Grep of the design `## Read-set` after `GetMcpTools` on `user-codegraph` returned only `mcp_auth`.

### 1. Consumer list per changed identifier

| Identifier | Consumers | Affected? |
|---|---|---|
| `initialize.result.instructions` | Cursor ACP MCP host; Claude Code MCP host (shared binary, protocol R15); `mcp-initialize.test.ts` (direct spawn) | YES — 4 constants, selected by mapper+busy flag |
| `tools/list` result | same hosts (tool registry) | YES — `[]` only for `index_missing`; else `getStaticTools()` on **both** doors |
| `MCPSession.handleInitialize` / `handleToolsList` | `handleMessage` (`session.ts:125,131`); daemon sessions; `CODEGRAPH_NO_DAEMON=1` direct | YES — existence/engine-open gates replaced |
| `runLocalHandshakeProxy` local answers | `MCPServer.start` step 4 (`index.ts:291`); production Cursor/Claude when a `.codegraph/` exists | YES — static playbook/tools gated on mapper of `deps.root` |
| `probeIndexHealth` | CLI `init` (`codegraph.ts:597`); `probe-index-health.test.ts` | NO behavior change. MCP **imports** it from `index-state.ts` only. Not barrel-exported. |
| `isInitialized` / `findNearestCodeGraphRoot` | walk-up everywhere | NO semantics change (existence-only) |
| `NotIndexedError` / `emptyWarn` / worktree copy | `ToolHandler.execute` catch (`tools.ts:1228`); explore empty path; tool-result text | YES — copy lock 5-a; explicit-path missing vs unreadable via helper |
| `MCPEngine.ensureInitialized` / `hasDefaultCodeGraph` | session `retryInitIfNeeded` (`session.ts:275-298`); `handleToolsCall` (`:258`) | NO product change. **Must remain legal after initialize** (`session.ts:216`). Must **not** decide `tools/list`. |
| `daemon.ts` idle timeout | daemon lifecycle | NO (CONSUMER-ONLY) |
| piggyback `manifest.json` / Claude `settings.json` / Cursor `hooks.json` | harness install | NO (R15: shared binary only) |

### 2. Recorded command + output per scope claim

| Scope claim | Command (this session) | Output |
|---|---|---|
| session instructions gate is existence-only | Read `codegraph/src/mcp/session.ts:202` | `const indexed = findNearestCodeGraphRoot(explicitPath ?? process.cwd()) !== null;` |
| session tools/list awaits engine then keys on open | Read `session.ts:221,230` | `await this.retryInitIfNeeded();` then `tools: this.engine.hasDefaultCodeGraph() ? this.engine.getToolHandler().getTools() : []` |
| background init after initialize (G-03; r2 M1 legal) | Read `session.ts:216` | `this.resolvePromise = this.engine.ensureInitialized(explicitPath);` |
| proxy always sends full playbook | Read `proxy.ts:298` | `instructions: SERVER_INSTRUCTIONS` (unconditional) |
| proxy always sends full static tools | Read `proxy.ts:301` | `result: { tools: getStaticTools() }` (unconditional) |
| stdin listener BEFORE daemon socket await | Read `proxy.ts:281` vs `:324` | `process.stdin.on('data', …)` precedes `socket = await deps.getDaemonSocket()` |
| `probeIndexHealth` not imported by `src/mcp/**` | `rg -n "probeIndexHealth" codegraph/src codegraph/__tests__` | def `directory.ts:116`; CLI `codegraph.ts:29,:597`; tests `probe-index-health.test.ts`; **zero** `src/mcp/` |
| `runProxy` has no caller | `rg -n "runProxy" codegraph/src codegraph/__tests__` | definition `proxy.ts:83` only |
| `isInitialized` existence-only | Read `directory.ts:100` | `return fs.existsSync(dbPath);` |
| probe COUNT + 500ms cap; require outside try | Read `directory.ts:123-133` | `require('node:sqlite')` then `try { DatabaseSync(…,{readOnly:true}); PRAGMA busy_timeout=500; SELECT COUNT(*)` |
| `getStaticTools` has no budget suffix; `getTools` appends one | Read `tools.ts:620-631,806-811` | static filter vs `` description: `${tool.description} Budget: make at most ${budget} calls...` `` |
| `hasDefaultCodeGraph` is null-check | Read `tools.ts:727-728` | `return this.cg !== null;` |
| hollow open has no 0-node reject | Read `engine.ts:167` | `this.cg = await loadCodeGraph().open(resolvedRoot);` |
| engine busy_timeout 5s (not the probe) | Read `codegraph/src/db/index.ts:31` | `db.pragma('busy_timeout = 5000');` |
| Node floor 20 | Read `package.json:54` + `node-version-check.ts:48` | `"node": ">=20.0.0 <25.0.0"` · `MIN_NODE_MAJOR = 20` |
| daemon poll ~6s | Read `index.ts:101-102` | `DAEMON_CONNECT_MAX_RETRIES = 240` × `RETRY_DELAY_MS = 25` |
| production proxy entered only when root found | Read `index.ts:277-291` | `if (!root) return this.startDirect('no .codegraph/ root found');` else `runProxyWithLocalHandshake(root)` |
| daemon initialize reply suppressed | Read `proxy.ts:344` | `if (clientInitId !== undefined && resp.id === clientInitId) continue;` |
| late emptyWarn stale `init -i` | `rg -n "init -i" codegraph/src` | `tools.ts:2276`; `worktree.ts:89`; `worktree.ts:103` |
| recoverable ≠ `isError` | Read `tools.ts:1228-1229` | `if (err instanceof NotIndexedError) { return this.textResult(err.message); }` |
| watcher-seq test is stderr-marker only | Read `mcp-initialize.test.ts:130,151` | `expect(response.seq).toBeLessThan(watcherLog.seq)` keys `'File watcher active'` |
| `LocalHandshakeDeps` injectable | Read `proxy.ts:180-204` | `getDaemonSocket` / `makeEngine` / `root` |
| ADR 0001 authorizes MCP import, not barrel | Read `codegraph/docs/adr/0001-init-repairs-unusable-index.md:70-77` | probe **not** in `src/index.ts`; Buckets 5/6 own their unions |

### 3. One contradiction looked for and not found

Hunted a **third** `initialize`/`tools/list` door via `runProxy` (stdio⇄socket pipe). `rg` returns only the definition. Live proxy entry is `runLocalHandshakeProxy` (`index.ts:458`). Two doors exactly.

Looked for `probeIndexHealth` already under `src/mcp/` — none. The bug is absence of the probe, not a second COUNT.

Looked for leftover design sentence **“degrade to missing-behavior”** as a spec instruction: **must not be carried**. Design Implications `:131` contradicts G-10/BT-6 (r2 M2). This spec’s throw rule is existence-gate fallback only (MUST-2).

## Already built (reuse, do not rebuild)

| Function/Module | Location | What it does | How this spec uses it | Depth |
|---|---|---|---|---|
| `probeIndexHealth` | `codegraph/src/directory.ts:116-166` | 5-arm read-only COUNT; `require('node:sqlite')` **outside** its `try` (`:123`) | import from mapper; do **not** duplicate COUNT; do **not** change CLI dispatch | deep |
| `findNearestCodeGraphRoot` / `isUsableRoot` / `isInitialized` | `directory.ts:93-100,263-293` | existence walk; unsafe-root skip | mapper walk; **unchanged** existence semantics | deep |
| `getStaticTools` | `tools.ts:625-632` | allowlist-filtered defs, **no** budget suffix | **sole nonempty `tools/list` source on both doors** | deep |
| `DEFAULT_MCP_TOOLS` | `tools.ts:645` | default surface = `explore` only | names of `getTools()` can match while JSON does not (r2 M1) | deep |
| `ToolHandler.getTools` | `tools.ts:759-817` | same allowlist **plus** budget suffix once `cg` loaded (`:810`) | **forbidden** as handshake `tools/list` source | deep |
| `ToolHandler.hasDefaultCodeGraph` | `tools.ts:727-728` | `this.cg !== null` | keep for `retryInitIfNeeded` (`session.ts:281`); **not** a list gate | deep |
| `NotIndexedError` + execute catch | `tools.ts:44,1228-1229` | SUCCESS-shaped recoverable | keep shape; explicit-path copy via helper | deep |
| `getCodeGraph` | `tools.ts:829-899` | walk + `openSync` | **extend**: health via `resolveMcpIndexState`, not raw `probeIndexHealth` | deep |
| `MCPSession.handleInitialize` / `handleToolsList` / `retryInitIfNeeded` | `session.ts:163-232,275-298` | existence gate; await-engine list; lazy init | replace gates; list must **not** await; `retryInitIfNeeded` stays for **calls** (`:258`) | deep |
| `ensureInitialized` kick | `session.ts:216` | background open after `sendResult` | **keep** (G-03 / #172). r2 M1: spy must not forbid this | deep |
| `runLocalHandshakeProxy` + `LocalHandshakeDeps` | `proxy.ts:180-378` | listen-first; static initialize/tools/list; suppress daemon init (`:344`) | gate the two `writeClient` payloads; keep listen-first + suppression | deep |
| `SERVER_INSTRUCTIONS` / `SERVER_INSTRUCTIONS_UNINDEXED` | `server-instructions.ts:20-91` | full playbook vs inactive note | reword UNINDEXED; add EMPTY + BUSY; selector | deep (pure constants) |
| `SERVER_INFO` / `PROTOCOL_VERSION` | `session.ts:30-36` | handshake envelope | unchanged; proxy already imports (`proxy.ts:28`) | deep |
| `MCPEngine.doInitialize` / `open` | `engine.ts:95-175` | better-sqlite3 open; no `node:sqlite` | CONSUMER-ONLY for handshake; throw-fallback matches this path | deep |
| `MCPServer.start` mode pick | `index.ts:259-291` | NO_DAEMON / no-root → direct; else proxy | unchanged. True no-dir missing is **session** door in production | deep |
| `resolveDaemonRoot` | `index.ts:158-163` | existence walk + realpath | why proxy `deps.root` is a **found** root | deep |
| `worktreeMismatchWarning` / `Notice` | `worktree.ts:83-105` | MCP-served tool-result text | copy lock: `init -i` → `codegraph init` | deep |
| spawn BIN + `CODEGRAPH_NO_DAEMON=1` | `mcp-initialize.test.ts:20-34` | #172 ordering spawn | keep; **not** sufficient for BT-3 (mini-RT M3) | deep |
| probe fixtures (junk/empty/busy/skip) | `probe-index-health.test.ts:1-70` | errcode recipes; Node <22.5 skip | MCP mapping tests reuse shapes; junk pin is **also** at MCP layer | deep |
| ADR 0001 carve-out | `codegraph/docs/adr/0001-….md:70-77` | probe not barrelled; B5/B6 own unions | MCP imports `../directory` directly | n/a |
| `MIN_NODE_MAJOR` | `node-version-check.ts:48` | floor 20 | must stay 20; no MCP-only floor | deep |
| `UPDATING.md` patch table | `codegraph/UPDATING.md:18-26` | fork survival | new row: MCP imports probe | n/a |
| `CHANGELOG.md` `[Unreleased]` | `codegraph/CHANGELOG.md:10` | user-facing notes | one MCP-honesty bullet | n/a |

### Partially built (extend)

| What exists | What must change | Why |
|---|---|---|
| `session.ts:202-230` boolean + engine list | mapper + `getStaticTools()`; no `await retryInitIfNeeded` on list | hollow db looks indexed; r2 M1 |
| `session.ts:192-201` “existsSync only” comment | rewrite: COUNT-before-reply is the #172 contract | else the comment lies (design Implications) |
| `proxy.ts:289-301` static constants | same mapper + instruction selector of `deps.root` | live lie (grill 4-a) |
| `SERVER_INSTRUCTIONS_UNINDEXED` “no `.codegraph/` directory” (`server-instructions.ts:84`) | reword: `no usable index`; must **not** claim directory absent | junk **has** the dir+file (`isInitialized`=`existsSync`) |
| `tools.ts:2276` `init -i` | `codegraph init` | lock 5-a; Bucket 4 already indexes |
| `worktree.ts:89,103` `init -i` | `codegraph init` | MCP-served (BT-4) |
| `getCodeGraph` explicit-path (`tools.ts:870-897`) | `resolveMcpIndexState`; junk copy ≠ “no directory”; probe-throw → open path | r2 M2 fifth COUNT |
| `mcp-initialize.test.ts` handshake shape only | content asserts + BT-3 spy (not watcher-seq alone) | BT-2 / BT-3 |
| ADR 0001 “not imported by `src/mcp/**`” | still true of the **barrel**; MCP mapper **does** import `directory.ts` | this bucket **is** the carve-out (`:76-77`) |

### Not built (create)

- `codegraph/src/mcp/index-state.ts` — `McpIndexState`, `resolveMcpIndexState(startPath) → { state, busy, root }`
- `SERVER_INSTRUCTIONS_INDEX_EMPTY` (new) / `SERVER_INSTRUCTIONS_INDEX_BUSY` (new) + `instructionsForMcpIndex({state,busy})` (new) in `codegraph/src/mcp/server-instructions.ts`
- Session-door in-process payload tests (busy equality, `tools` deep-equals `getStaticTools()`, no list-path await)
- Proxy stub-deps tests (BT-1 / BT-1b) — no live daemon spawn
- Mapper unit tests (5→3 table + probe-throw fallback + spy that probe is called when root exists)
- `getCodeGraph` probe-throw fixture (MUST-2)
- `codegraph/docs/adr/0002-mcp-index-tri-state.md` (grill ADR-with-impl)
- UPDATING.md patch row + CHANGELOG `[Unreleased]` bullet

## Feature overview

Happy path (usable db, COUNT>0): both doors send `SERVER_INSTRUCTIONS` + `getStaticTools()`. Session still kicks `ensureInitialized` **after** `sendResult` (`codegraph/src/mcp/session.ts:216`). `tools/list` does **not** wait on that promise.

Empty-db (COUNT=0): `SERVER_INSTRUCTIONS_INDEX_EMPTY` (new) + nonempty `getStaticTools()`. Copy must **not** say tools are unavailable / “inactive this session” (hosts list once — `codegraph/src/mcp/session.ts:228`).

Busy (probe errcode 5): `state='index_empty'`, `busy=true` → `SERVER_INSTRUCTIONS_INDEX_BUSY` (new) (exact imported constant on **both** doors) + nonempty `getStaticTools()`. Not a fourth MCP name.

Missing (no root) / unreadable / unclassified: `index_missing` → reworded UNINDEXED + `tools: []`. `CODEGRAPH_MCP_TOOLS` allowlist is applied only to a **nonempty** list (missing stays `[]`).

Probe throw (`node:sqlite` absent on Node 20–22.4): if walk found a root → `{ state:'usable', busy:false }` (existence-gate: full playbook + `getStaticTools()` + `getCodeGraph` proceeds to `openSync`). If no root → `index_missing`. **Never** map throw → `index_missing` while a root exists. **Never** “degrade to missing-behavior.”

Pickup: OQ-2 default **A** — re-resolve on every `initialize` and every `tools/list` (same `startPath` each time). Empty→usable after `codegraph init` is visible on the next list.

`tools/call` still `await retryInitIfNeeded()` (`codegraph/src/mcp/session.ts:258`) — engine is required for calls, not for listing.

### Mapping table (pin)

| Condition | `state` | `busy` | instructions | `tools/list` |
|---|---|---|---|---|
| `root === null` | `index_missing` | false | UNINDEXED (reworded) | `[]` |
| probe `usable` | `usable` | false | `SERVER_INSTRUCTIONS` | `getStaticTools()` |
| probe `empty` | `index_empty` | false | `SERVER_INSTRUCTIONS_INDEX_EMPTY` (new) | `getStaticTools()` |
| probe `busy` | `index_empty` | **true** | `SERVER_INSTRUCTIONS_INDEX_BUSY` (new) | `getStaticTools()` |
| probe `unreadable` / `unclassified` | `index_missing` | false | UNINDEXED (reworded) | `[]` |
| probe **throws**, root found | `usable` | false | `SERVER_INSTRUCTIONS` | `getStaticTools()` |
| probe **throws**, root null | `index_missing` | false | UNINDEXED (reworded) | `[]` |

`instructionsForMcpIndex`: `busy===true` selects BUSY **before** switching on `state` (OQ-1 CLOSED: not a builder over EMPTY).

Production note (m4): proxy `deps.root` is already a found root (`index.ts:277-291`). True no-directory missing is the **session** door (`startDirect`). Proxy `index_missing` in prod is junk/unreadable/unclassified at that root (or a delete race). Door-parity tests that compare payloads MUST feed the **same** `startPath` into both `resolveMcpIndexState` calls — session `explicitPath ?? cwd` vs proxy `deps.root` are different sources.

## Out of scope

- **CLI `init` / `resolveProjectPath` / `isInitialized` semantics** — Bucket 4 DONE. — deferred: never this phase.
- **writ `probe()` / `writ-codegraph-init.sh`** — Bucket 6. — deferred: Bucket 6.
- **Recoverable empty → `isError`** — freeze. — deferred: never.
- **Plugin bus / `.codegraph/ready` / close TD-01** — grill C2-a. — deferred: TD-01 OPEN.
- **`engine.ts` + daemon idle-kill as a second product** — C1-a: A-split only if FCV proves a **different** contract. Default: untouched (`daemon.ts:60` stays CONSUMER-ONLY).
- **Installer `targets/cursor.ts`** — OUT.
- **`npm install -g` / `codegraph upgrade` / bump Node floor** — OUT. Floor stays `MIN_NODE_MAJOR = 20`.
- **`CODEGRAPH_ALLOW_UNSAFE_ROOT` policy** — walk unchanged.
- **`site/` / historical markdown / CHANGELOG body of past releases** rewriting `init -i` — copy lock is **code-served strings** only (BT-4 Out). `[Unreleased]` **new** bullet is in scope.
- **`src/index.ts` barrel export** of the probe or `McpIndexState` — G-04.
- **Duplicate COUNT** in session/proxy/`getCodeGraph` — lock 3-a. Only `index-state.ts` calls `probeIndexHealth`.
- **Fourth MCP-visible state name** — freeze.
- **Per-harness settings.json / hooks.json / mcp.json edits** — R15: shared binary.
- **OQ-3 full junk/busy `openSync` → SUCCESS retry copy** — OPEN; this phase only differentiates explicit-path `NotIndexedError` via the helper. Residual internal `errorResult` on racing `openSync` (`codegraph/src/mcp/tools.ts:897`) stays unless FCV+OQ-3 close A.

## Constraints

**Binding MUSTs from design↔RT EXIT r2 (judge 2026-08-19, HOLD — not silent drop):**

1. **MUST-1 (r2 M1 / BT-5 repaired).** Session `tools/list` result **deep-equals** `getStaticTools()` (full `ToolDefinition[]`, **not** `.map(t => t.name)`). `handleToolsList` must **not** `await` `retryInitIfNeeded` / `ensureInitialized` / `hasDefaultCodeGraph` to **decide** the nonempty list. Background `ensureInitialized` after initialize stays **legal** (`codegraph/src/mcp/session.ts:216` quote: `this.resolvePromise = this.engine.ensureInitialized(explicitPath);`). Plan-verify **cannot** be unused-import `grep-present getStaticTools` in `codegraph/src/mcp/session.ts` — the call must be the `tools` payload (`tools: state === 'index_missing' ? [] : getStaticTools()` or equivalent).

   Honest `hasDefaultCodeGraph` stays on the retry path (`codegraph/src/mcp/session.ts:281` quote: `if (this.engine.hasDefaultCodeGraph()) return;`). No whole-file `grep-absent hasDefaultCodeGraph`.

2. **MUST-2 (r2 M2 / BT-6 repaired).** Do **not** carry Implications leftover “degrade to missing-behavior” on probe throw. `getCodeGraph` health goes through `resolveMcpIndexState`, **not** a second raw `probeIndexHealth`. Probe-throw with root present → existence-gate (full playbook / nonempty static tools / **engine-open** path), **not** `index_missing`. Fixture on that **explicit-path** throw (stub probe, `projectPath` pointing at a real root, `execute` does **not** `NotIndexedError` “isn’t indexed”).

3. **MUST-3 (r2 M3).** Session-door **busy** fixture: `initialize.result.instructions === SERVER_INSTRUCTIONS_INDEX_BUSY` (new) (imported constant), tools nonempty from `getStaticTools()`. Proxy BT-1 equality is **not** enough.

**Binding tests to carry (design BT-\* + r1 m2/m4/m5):**

- **BT-1** — stub-deps `runLocalHandshakeProxy`; never-ready daemon; per-state stdout table; busy copy **===** imported `SERVER_INSTRUCTIONS_INDEX_BUSY` (new). `grep-present 'resolveMcpIndexState' codegraph/src/mcp/proxy.ts`.
- **BT-1b** — `getDaemonSocket` **stays pending** for the assertion window; initialize written to stdout while pending. Immediate-null stub does **not** satisfy.
- **BT-2** — instructions **content** (empty/missing snippets); `tools/list` `[]` for missing **and** junk, nonempty for empty-db; mapper **calls** `probeIndexHealth` when a root exists (spy). Junk UNINDEXED contains `no usable index` and MUST NOT contain `no \`.codegraph/\` directory`. EMPTY MUST NOT claim tools unavailable / inactive this session. `grep-present 'probeIndexHealth' codegraph/src/mcp/index-state.ts`.
- **BT-3** — on usable-db fixture, `CodeGraph.open` / `loadCodeGraph().openSync` / `Parser.init` were **not** invoked before initialize `sendResult`/`writeClient`. Watcher-seq (`codegraph/__tests__/mcp-initialize.test.ts:151` quote: `expect(response.seq).toBeLessThan(watcherLog.seq);`) is **not** sufficient. Pin is **COUNT not `open`**, **not** a ≤500ms wall (`busy_timeout` cannot enforce wall-time) — r1 m5.
- **BT-4** — `codegraph/src/sync/worktree.ts:89` quote: `Run "codegraph init -i" in this worktree` and `:103` quote: `Run "codegraph init -i" here for a` name `codegraph init` not `init -i`. Plan-verify greps both sites. Out: `site/`, historical CHANGELOG, markdown docs.
- **BT-6** — stub probe throw + root present → full `SERVER_INSTRUCTIONS` + nonempty `getStaticTools()`; root absent → `[]` + reworded UNINDEXED. `grep-present 'MIN_NODE_MAJOR = 20' codegraph/src/bin/node-version-check.ts`. Plus MUST-2 explicit-path fixture.
- **r1 m2** — proxy `resolveMcpIndexState` **call-count ≥ 2** on a handshake that performs initialize **and** `tools/list` (unused import / single call does not pass).
- **r1 m4** — door-parity is for the **same `startPath`**. Do not claim byte-identical payloads when session start (`explicitPath ?? cwd`) ≠ proxy `deps.root`.

From CLAUDE.md / grill / design / protocol card:

1. Frozen tri-state `index_missing` / `index_empty` / usable. Junk/unclassified → missing behavior. Busy → empty-style. No fourth MCP-visible **name**. — grill 1-a; G-10 throw is existence-fallback, not a name.
2. Empty `tools/list` **only** for missing. — scope freeze.
3. Cheap COUNT before handshake reply; heavy init background (#172). Probe is `readOnly` + `busy_timeout=500` + one COUNT (`codegraph/src/directory.ts:131` quote: `db = new DatabaseSync(dbPath, { readOnly: true });` · `:132` quote: `db.exec('PRAGMA busy_timeout = 500');` · `:133` quote: `const row = db.prepare('SELECT COUNT(*) AS n FROM nodes').get()`). Do not `await` daemon socket before answering initialize (BT-1b).
4. Import `probeIndexHealth`, map 5→3 in `src/mcp/`. No third public enum from `src/index.ts`. `isInitialized` unchanged. — grill 3-a; G-04; G-05.
5. Same payloads on both doors when startPath matches. — grill 4-a; MUST-1 source pin.
6. Recoverable ≠ `isError`. — `codegraph/src/mcp/tools.ts:1228` quote: `if (err instanceof NotIndexedError) {`; G-02. Do not add `errorResult` for empty/busy handshake copy.
7. Copy: user runs `codegraph init`; agent never self-inits; never stale `init -i` in code-served strings. — lock 5-a; G-09.
8. Never write `codegraph.db` from MCP. Probe already `readOnly`. — G-01; piggyback CLAUDE.md.
9. TD-01 stays OPEN. — G-08.
10. R15: shared MCP binary; no per-harness settings/hooks edit.
11. Fork: `npm run build` + rsync per `UPDATING.md`; never `npm upgrade`. Version `999.0.0`.
12. Env the new logic may read: `CODEGRAPH_DIR`, `CODEGRAPH_NO_DAEMON`, `CODEGRAPH_DAEMON_INTERNAL`, `CODEGRAPH_MCP_TOOLS` (nonempty lists only), `CODEGRAPH_ALLOW_UNSAFE_ROOT` (unchanged).
13. One helper deletion-test: deleting `index-state.ts` would re-spray walk+probe+throw-guard+map into **5** call sites (session initialize + tools/list; proxy initialize + tools/list; `getCodeGraph`). Design’s “4 sites” is **stale** post-r2 M2.
14. G-07: UPDATING.md patch row + CHANGELOG `[Unreleased]` with impl.

## Assumptions

FLOOR from design `## Assumptions to verify` (verbatim claims). FCV checks each.

| ID | Assumption | Source implication | What would prove it wrong |
|---|---|---|---|
| A1 | **Proxy never gates its instructions today.** `codegraph/src/mcp/proxy.ts:298` quote: `serverInfo: SERVER_INFO, instructions: SERVER_INSTRUCTIONS } });`. | implication “proxy never consults the db” | some wrapper already rewrites instructions before stdout |
| A2 | **Nor its tool list.** `codegraph/src/mcp/proxy.ts:301` quote: `result: { tools: getStaticTools() } });`. Why: the entire bug lives or dies here; if some wrapper rewrites these, the fix point moves. | same | a wrapper already filters/replaces `tools` |
| A3 | **Hollow db opens cleanly as the default project.** `codegraph/src/mcp/engine.ts:167` quote: `this.cg = await loadCodeGraph().open(resolvedRoot);` — no 0-node rejection. | implication “direct-mode indexed is true for empty” | `open` rejects `COUNT=0` |
| A4 | **Availability is a mere null-check.** `codegraph/src/mcp/tools.ts:728` quote: `return this.cg !== null;`. Why: these two prove direct-mode “indexed” is true for empty dbs today. | same | `hasDefaultCodeGraph` inspects node count |
| A5 | **Probe does not mutate and closes its handle.** `codegraph/__tests__/probe-index-health.test.ts:10` quote: `* the probe never mutates bytes (sha256 unchanged) and it always closes its`. Why: safe on the handshake hot path. | implication “probe reuse” | handshake COUNT changes sha256 or leaks the handle |
| A6 | **`resolveDaemonRoot` only proves existence.** `codegraph/src/mcp/index.ts:160` quote: `const root = findNearestCodeGraphRoot(candidate);`. Why: proxy mode is entered for hollow/junk dbs alike; the fix cannot be skipped “because root resolved”. | implication “proxy entered for junk” | mode pick already probes health |
| A7 | **Daemon’s own sessions never answer a host’s `initialize` visibly.** `codegraph/src/mcp/proxy.ts:344` quote: `if (clientInitId !== undefined && resp.id === clientInitId) continue;`. Why: keeps “both doors” the only payload owners. | implication “two doors exactly” | host observes daemon initialize result |
| A8 | **Stale `init -i` copy sites (superseded by mini-RT m1 enumeration):** three code-served sites now pinned — `codegraph/src/mcp/tools.ts:2276` quote: `run \`codegraph init -i\` in this directory before exploring.` | implication “copy lock 5-a” | that string already names `codegraph init` |
| A8a | `codegraph/src/sync/worktree.ts:89` quote: `"codegraph init -i"` · `codegraph/src/sync/worktree.ts:103` quote: `"codegraph init -i"` — both MCP-served via tool-result text. FCV must STILL `grep` the whole fork for `init -i` to catch any remainder; `site/`/`CHANGELOG.md`/docs hits are explicitly out of this bucket. Why (8+8a): lock 5-a applies to all user-visible strings, not one site. | mini-RT m1 | a fourth **code-served** `init -i` exists in `src/` |
| A9 | **`node:sqlite` require can throw at runtime.** `codegraph/src/directory.ts:123` quote: `const { DatabaseSync } = require('node:sqlite') as {`. | implication “probe failure modes”; G-10 | require is inside the probe `try` or always present on Node 20 |
| A10 | **The Node-version skip guard confirms the throw branch.** `codegraph/__tests__/probe-index-health.test.ts:13` quote: `* Skipped on Node < 22.5 where node:sqlite doesn't exist.`. Why (9+10): mapper **try/catch** around `probeIndexHealth` (existence-fallback), **not** throw→missing. | G-10; MUST-2 | tests skip for a different reason, or require never throws on 20–22.4 |
| A11 | **Direct mode is the minority host path.** tests pin daemon-off: `codegraph/__tests__/mcp-initialize.test.ts:33` quote: `env: { ...process.env, CODEGRAPH_NO_DAEMON: '1' },`. | implication “proxy is the live path” | production hosts set `CODEGRAPH_NO_DAEMON` |
| A12 | **Production hosts launch plain `serve --mcp`.** `codegraph/src/bin/codegraph.ts:1597` quote: `const { MCPServer } = await import('../mcp/index');`. Why (11+12): the proxy door is the live path and drives this bucket’s ROI. | grill ORCH-burden 4-a | serve no longer constructs `MCPServer` |

Additional (decomposition; FCV should still check):

| ID | Assumption | Source implication | What would prove it wrong |
|---|---|---|---|
| A13 | Production proxy `deps.root` is a **found** initialized root (`index.ts:277-291` quote: `return this.startDirect('no .codegraph/ root found');`). True no-dir missing is session/direct. Proxy unit tests may still pass a bare temp dir as `root`. | m4; A6 | proxy runs `runLocalHandshakeProxy` when `resolveDaemonRoot` is null |
| A14 | `getTools()` byte-diverges from `getStaticTools()` once `cg` loads via budget suffix (`tools.ts:806-811`). Default **names** can still match (`DEFAULT_MCP_TOOLS` = `explore`). | r2 M1; BT-5 repair | `getTools()` descriptions equal static with `cg` set |
| A15 | `handleToolsCall` must keep `await this.retryInitIfNeeded()` (`session.ts:258`). List-path await removal must not delete the call-path await. | #172 vs tool usefulness | calls run with `cg===null` and only `NotIndexedError` |
| A16 | `require('node:sqlite')` is **outside** the probe `try` (`directory.ts:123` then `:130`). Throw never becomes a 5-arm status; only the mapper catch sees it. | r2 M2 evidence | probe catches MODULE_NOT_FOUND and returns `unclassified` |
| A17 | `execute` is the single tool-call intake (`session.ts:260`; `tools.ts:1199`). No internal re-entry bypasses `getCodeGraph`. | design Chosen Approach | a handle* method opens sqlite without `getCodeGraph` |
| A18 | `LocalHandshakeDeps` is sufficient to test proxy payloads without a live daemon (`proxy.ts:180-204`). OQ-4 CLOSED as A. | BT-1 | `runLocalHandshakeProxy` reads process cwd instead of `deps.root` for the handshake gate |
| A19 | Session initialize startPath is `explicitPath ?? process.cwd()` (`session.ts:202`) where `explicitPath` is `rootUri` / `workspaceFolders[0]` / `--path`. Parity tests must set that equal to proxy `deps.root`. | r1 m4 | a third startPath (e.g. `roots/list`) is used for the **initialize** instruction pick |
| A20 | `getCodeGraph` without `projectPath` (`tools.ts:830-845`) is already SUCCESS-shaped when `cg` is null. Helper is required on the **explicit-path** arm (`:870+`). | OQ-3 boundary | default-arm also raw-probes |

## Component dependency order

What must EXIST before each component works — not the code-writing order.

### 1. Instruction constants + selector
**Goal.** Four byte-static instruction strings; busy cannot collapse into empty copy.
**Build.** `codegraph/src/mcp/server-instructions.ts`: reword `SERVER_INSTRUCTIONS_UNINDEXED` to `no usable index` (MUST NOT contain `no \`.codegraph/\` directory`); add `SERVER_INSTRUCTIONS_INDEX_EMPTY` (new) — short, user runs `codegraph init`, agent does not self-init, **does not** say tools unavailable / inactive this session; add `SERVER_INSTRUCTIONS_INDEX_BUSY` (new) — short “busy, retry later”, **not** a parameterized builder over EMPTY (OQ-1 CLOSED A). Add `instructionsForMcpIndex({ state, busy })` that selects BUSY when `busy===true`, else switches on `state`. `SERVER_INSTRUCTIONS` playbook unchanged.
**Depends on.** None.
**Assumes.** —
**Interface shape.** Public constants + one selector. Hidden: nothing. Callers never duplicate the switch.
**Done when.** Junk-shaped UNINDEXED contains `no usable index` and does not mention a missing directory. `instructionsForMcpIndex({state:'index_empty', busy:true}) === SERVER_INSTRUCTIONS_INDEX_BUSY`. EMPTY text does not include “inactive this session”.

### 2. Mapper `index-state.ts`
**Goal.** One owner of walk → probe → throw-guard → 5→3 map.
**Build.** New `codegraph/src/mcp/index-state.ts`. Export `McpIndexState = 'index_missing' \| 'index_empty' \| 'usable'` and `resolveMcpIndexState(startPath: string): { state: McpIndexState; busy: boolean; root: string \| null }`. Walk via `findNearestCodeGraphRoot`; null → missing. Else `try probeIndexHealth(root)` and map per table. Catch: root found → `{ state:'usable', busy:false, root }`; root null → missing. **Never** import from `src/index.ts` barrel. **Never** change `directory.ts` probe. `busy===true` only with `state==='index_empty'`.
**Depends on.** 1 (not for compile — for pairing tests). Probe already exists.
**Assumes.** A5, A9, A10, A16.
**Interface shape.** 1 module, 2 exports, consumed by session, proxy, `tools.ts` = real seam (deletion test: 5 call sites).
**Dependency category.** in-process.
**Decisions.** OQ-2 OPEN — implement **A** (re-probe every call; no cache field). OQ-3 does not live here.
**Done when.** Spy: `probeIndexHealth` invoked when a root fixture exists. Throw stub + root → `state==='usable'`. Throw stub + no root → `index_missing`. Busy fixture → `{state:'index_empty', busy:true}`. Junk → `index_missing`. Empty COUNT=0 → `index_empty` `busy:false`. `rg` shows `probeIndexHealth` under `src/mcp/` **only** in this file.

### 3. Session door
**Goal.** Direct-mode initialize + tools/list follow the mapping table without waiting on the engine for the list.
**Build.** `codegraph/src/mcp/session.ts`: replace `indexed` boolean (`:202`) with `resolveMcpIndexState(explicitPath ?? process.cwd())`; `instructions: instructionsForMcpIndex(resolved)`. Keep `sendResult` **before** `ensureInitialized` (`:204-216`). `handleToolsList`: **do not** `await retryInitIfNeeded()`; re-resolve; `tools: state==='index_missing' ? [] : getStaticTools()`. Import `getStaticTools` **and use it as the payload**. Rewrite the `:192-201` comment (COUNT-before-reply, not “existsSync only”). Leave `handleToolsCall` + `retryInitIfNeeded` + `hasDefaultCodeGraph` recovery intact.
**Depends on.** 1, 2.
**Assumes.** A3, A4, A11, A14, A15, A19.
**Done when.** MUST-1: after initialize, `tools/list` deep-equals `getStaticTools()` on busy **and** empty fixtures; spies show `handleToolsList` did not await `retryInitIfNeeded`/`ensureInitialized`; process **may** have started `ensureInitialized` from initialize. MUST-3: busy fixture `initialize.result.instructions === SERVER_INSTRUCTIONS_INDEX_BUSY`. Missing/junk → `tools:[]` + UNINDEXED content (BT-2). BT-3: no `open`/`openSync`/`Parser.init` before `sendResult` on usable fixture.

### 4. Proxy door
**Goal.** Live local-handshake answers the same table from `deps.root` without waiting for the daemon.
**Build.** `codegraph/src/mcp/proxy.ts` initialize (`:289-298`) and tools/list (`:300-301`) call `resolveMcpIndexState(deps.root)` **each** (m2: ≥2 calls on initialize+list). Instructions via `instructionsForMcpIndex`. Nonempty tools = `getStaticTools()`. Keep listen-first (`:281` before `:324`), daemon-init suppression (`:344`), fallback `handleLocally`. Do not `await getDaemonSocket` before attaching stdin.
**Depends on.** 1, 2.
**Assumes.** A1, A2, A6, A7, A13, A18.
**Done when.** BT-1 full table on stub-deps stdout. BT-1b initialize while `getDaemonSocket` pending. Spy call-count of `resolveMcpIndexState` ≥ 2 on initialize+`tools/list`. Busy instructions === imported BUSY constant.

### 5. `getCodeGraph` + emptyWarn copy
**Goal.** Explicit-path health uses the helper; handshake throw-fallback is not undone on the first tool call; stale `init -i` gone from explore emptyWarn.
**Build.** `codegraph/src/mcp/tools.ts` `getCodeGraph` explicit-path arm (`:870+`): call `resolveMcpIndexState(projectPath)` (not `probeIndexHealth`). `state==='index_missing'` → `NotIndexedError`: if `root===null` keep absence guidance; if `root` present (junk) copy must **not** say “no `.codegraph/` directory found” (`:874`). Probe-throw with root (helper returns usable) → existing `openSync` path (`:897`). `emptyWarn` (`:2276`): `codegraph init` not `init -i`. Do not expand into OQ-3 (`openSync` throw → generic `errorResult` stays unless that OQ closes).
**Depends on.** 2.
**Assumes.** A8, A17, A20.
**Done when.** MUST-2 fixture: stub probe throw + `projectPath` at a real root → no NotIndexedError-as-missing; open path runs. Junk explicit path → NotIndexedError text has `no usable index` (or equivalent) and not “no `.codegraph/` directory”. `rg -n "init -i" codegraph/src/mcp/tools.ts` is empty.

### 6. Worktree copy lock
**Goal.** MCP-served worktree strings name `codegraph init`.
**Build.** `codegraph/src/sync/worktree.ts:89` and `:103` replace `codegraph init -i` with `codegraph init`. Do not rewrite `site/` / docs / historical CHANGELOG.
**Depends on.** None (can parallel 1–5).
**Assumes.** A8a.
**Done when.** BT-4 greps: both sites contain `codegraph init` and do not contain `init -i`.

### 7. Contract tests
**Goal.** Every BT/MUST is a failing-without-fix test, not a grep-only green.
**Build.** Extend `codegraph/__tests__/mcp-initialize.test.ts` (content + BT-3 spy; keep existing #172 watcher-seq **and** do not treat it as BT-3). New in-process session tests (stub `JsonRpcTransport.sendResult`) for MUST-1/MUST-3/BT-2/BT-6. New stub-deps proxy tests for BT-1/BT-1b/m2. Mapper tests for the table + probe spy. `getCodeGraph`/execute MUST-2 fixture. Reuse probe junk/empty/busy fixture recipes; MCP junk pin lives **here**, not only in `probe-index-health.test.ts`. No live daemon spawn (OQ-4 CLOSED A). R4-a “live = vitest spawn” remains the existing `mcp-initialize` BIN spawn plus these in-process tests — ORCH does not run a second cert.
**Depends on.** 1–6.
**Assumes.** A11, A18.
**Done when.** Each BT/MUST row above has an assertion that fails the gaming transcripts in r2 (names-only BT-5; throw→missing in tools.ts; proxy-only busy equality; unused-import greps; watcher-seq-only #172).

### 8. Fork survival + ADR
**Goal.** Upstream merge sees the new mcp→directory edge; 5→3 map is recorded.
**Build.** `codegraph/UPDATING.md` patch-table row: MCP mapper imports `probeIndexHealth`, maps 5→3. `codegraph/CHANGELOG.md` `[Unreleased]` user-facing bullet (no internal paths). New `codegraph/docs/adr/0002-mcp-index-tri-state.md`: Option A, mapping table, throw→existence, `getStaticTools()` as the nonempty list, TD-01 still OPEN. Do **not** amend ADR 0001’s repair table; 0002 cites 0001 `:76-77` carve-out. `codegraph --version` stays `999.0.0`.
**Depends on.** 2 (the edge exists).
**Assumes.** A12.
**Done when.** `grep-present` the UPDATING row names `probeIndexHealth` + `src/mcp`. CHANGELOG `[Unreleased]` has a sentence an agent-user would understand (missing vs empty vs usable at handshake). ADR 0002 exists.

## Handoff notes

- **Contract with Bucket 4:** `${…}` already refused on `serve --mcp`. This phase does **not** re-export the 5-arm probe. MCP 3-arm is independent (ADR 0001 `:76-77`).
- **Contract with Bucket 6:** writ keeps its own `missing|unreadable|unrecognized|usable`. Do not share `McpIndexState`. TD-01 stays OPEN here too.
- **Contract with hosts:** Cursor ACP + Claude Code consume the same binary. No `settings.json` / `hooks.json` / `mcp.json` edits (R15).
- **Open uncertainty — OQ-2** (OPEN): re-probe every `tools/list` vs cache-until-change. Spec implements **A** (re-probe). FCV/plan must not silently switch to cache. Cost: +1 read-only COUNT per list (sub-ms; ≤500ms busy cap).
- **Open uncertainty — OQ-3** (OPEN): junk/busy `openSync` on explicit `projectPath` may still `errorResult` (`tools.ts:897,1235`). Spec does **not** map that to SUCCESS retry copy. Close A only if FCV shows it reachable in a realistic ACP flow; else B in RT review scope, not the plan.
- **TD-01:** OPEN. Shipping `.codegraph/ready` or a plugin bus **fails** this spec.
- **Suggested research before planning:** FCV A1–A20, especially A9/A10/A16 (require throw), A13 (proxy missing reachability), A14 (budget suffix), A19 (startPath). C1-a: confirm `engine.ts` / idle-kill are the same contract (no A-split).
- **Planner traps (r2 gaming):** (1) `getTools()` for session list — names match, JSON does not; (2) `await retryInitIfNeeded()` then static tools — still waits; (3) spy “`ensureInitialized` never ran this process” — fights G-03; (4) unused `import { getStaticTools }`; (5) proxy-only BUSY equality; (6) `getCodeGraph` raw `probeIndexHealth` + catch→NotIndexedError; (7) leftover “degrade to missing-behavior”; (8) BT-3 = watcher-seq; (9) BT-1b with immediately-null socket; (10) `grep-absent hasDefaultCodeGraph` whole `session.ts`; (11) cache initialize state for tools/list (OQ-2 B without closing OQ-2); (12) fourth state string `'index_busy'`; (13) `isError` on empty/busy; (14) agent-facing `init -i`; (15) export mapper from `src/index.ts`.
- **Next stage:** `/factual-code-verification` on A1–A20, then `/plan`.
