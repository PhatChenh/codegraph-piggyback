# Design red-team — Bucket 5 MCP missing vs empty vs usable

_Date:_ 2026-08-19
_Artifact:_ `docs/AI_artifacts/3_design/2026-08-19-bkt5-codegraph-mcp.md` (post-mini-RT patch)
_Mode:_ **cross-model** (author: syn-3-kimi-k3; reviewer: cursor-grok-4.6-high, fresh session, artifact + repo + contracts only). Certifies craft + some shared-judgment misses this lineage can see. **Cannot certify** same-lineage blind spots, and cannot certify live ACP host behavior (no MCP spawn of Cursor/Claude in this review).
_Stakes aimed:_ (1) both doors same payload (2) 5→3 map (junk→missing, busy→empty-style) (3) cheap COUNT before handshake; heavy init backgrounded
_Fix:_ nothing. Report-only.

## Steelman

The live lie is real and it is the proxy door. `findNearestCodeGraphRoot` is existence-only (`isInitialized` → `fs.existsSync(dbPath)` at `codegraph/src/directory.ts:100`), a hollow 0-node db therefore counts as indexed, and `runLocalHandshakeProxy` answers `initialize` / `tools/list` from static constants with no DB knowledge (`codegraph/src/mcp/proxy.ts:298,301`). Direct mode’s `tools/list` already accidentally looks missing for junk (open throws, `cg` stays null) but still serves the full playbook on empty. Importing `probeIndexHealth` and mapping 5→3 in one mcp-internal helper, with `tools: []` only for missing-behavior, is the only option that satisfies lock 4-a structurally rather than by hoping two inline tables stay twins. Mini-RT M1–M3 / m1–m3 correctly forced stub-deps payload tests, a probe spy, a pre-`sendResult` open spy, worktree `init -i` copy, and a byte-static busy constant. Option A remains the right shape.

## Executive summary

Zero CRITICAL. Four MAJOR. Option A (one helper, both doors, 5→3 map, COUNT-not-open on the initialize path) does not need a different architecture — it needs the helper’s return type, the nonempty `tools/list` source, the probe-unavailable fail mode, and the proxy #172 ordering pins that the post-mini-RT binding tests still do not actually enforce. Human-authority silent assume: treating “`node:sqlite` missing” as `index_missing` hides a working index on the declared Node 20 floor.

**Verdict: revise.**

---

## Findings

### CRITICAL

None. Do not rethink the helper / both-doors / import-the-probe approach.

### MAJOR

**M1 — “Same payloads on both doors” is not structural: the helper unifies the 3-arm name, not the JSON the host sees.**
Verdict: **revise** (pin one nonempty-list source that does not wait on engine open).

```
Where: artifact Chosen Approach “otherwise the existing engine/static list”; mapping table `defs` cells; lock 4-a
Severity: MAJOR
Confidence: VERIFIED
Impact (plain language): Cursor/Claude on the live proxy door get tools instantly. A direct-mode or “unified” implementation waits for the engine and can answer `[]` for busy/empty-before-open — the agent sees “tools exist, retry” in initialize and then an empty toolbox. Same helper, two different letters.
```

**Evidence:**

Design Chosen Approach:

> `handleToolsList` re-resolves and returns `[]` only for `index_missing`, otherwise the existing engine/static list for usable, `index_empty`, and busy

Today those lists are different functions, and one of them is gated on a successful heavy open:

```229:231:codegraph/src/mcp/session.ts
    this.transport.sendResult(request.id, {
      tools: this.engine.hasDefaultCodeGraph() ? this.engine.getToolHandler().getTools() : [],
    });
```

`handleToolsList` **awaits** `retryInitIfNeeded()` first (`session.ts:221`), which can `await ensureInitialized` / `openSync` (`engine.ts:131,167`). Engine open uses `busy_timeout = 5000` (`codegraph/src/db/index.ts:31`).

Proxy nonempty list is sync and engine-free:

```300:301:codegraph/src/mcp/proxy.ts
      } else if (msg.method === 'tools/list') {
        writeClient({ jsonrpc: '2.0', id: msg.id, result: { tools: getStaticTools() } });
```

`getTools()` after a 0-file open also appends a budget suffix (`tools.ts:806-811`); `getStaticTools()` does not (`tools.ts:625-631`). Byte-identical `defs` are already false.

Grill lock 4-a: “Same contract on `session.ts` **and** `proxy.ts`.” Protocol card: “`session.ts` **and** `proxy.ts` same payloads.”

Stronger alternative the design did not choose: both doors answer nonempty `tools/list` from `getStaticTools()` (or one shared filtered defs helper) **without** `await retryInitIfNeeded` / `ensureEngine`. That is the payload the proxy already sends, and it is why local-handshake exists (`proxy.ts:194-196`: tools register in process-startup time, not daemon-open time).

**Check:** after spec, assert session `tools/list` on a busy fixture returns the same tool **names** as `getStaticTools()` without `CodeGraph.open` having been called.

---

**M2 — G-10 throw→`index_missing` is the wrong fail mode: it hides a working index whenever `node:sqlite` cannot load.**
Verdict: **revise** (probe-unavailable ≠ missing; fail open to today’s existence gate, or require the bundled Node explicitly).

```
Where: artifact G-10, mapping table last row, Risks “Probe unavailable”, Assumptions 9–10
Severity: MAJOR
Confidence: VERIFIED
Impact (plain language): If the handshake thermometer is broken, the design tells the agent the house has no map — and hides the tools that still work. Like a dead battery in a smoke alarm causing the fire department to be told the building does not exist.
```

**Evidence:**

Design mapping table:

> probe throws (no node:sqlite) → `index_missing` → UNINDEXED → `tools: []`

G-10: “every new call site wraps the probe in try/catch → throw maps to missing-behavior.”

`probeIndexHealth` `require('node:sqlite')` is inside the function (`directory.ts:123-128`). Tests skip that require on Node < 22.5 (`probe-index-health.test.ts:13,22-30`). Package engines and CLI floor are **Node 20**, not 22.5:

- `codegraph/package.json` `"node": ">=20.0.0 <25.0.0"`
- `MIN_NODE_MAJOR = 20` (`codegraph/src/bin/node-version-check.ts:48`)

MCP serving does **not** need `node:sqlite`. The engine opens via `better-sqlite3` / wasm (`codegraph/src/db/index.ts` + `engine.ts:167` `loadCodeGraph().open`). Today a Node 20 host with a usable db gets tools. After this design it gets `tools: []` + UNINDEXED.

Live install for this fork is the bundled Node (`codegraph/UPDATING.md`: `~/.codegraph/versions/v1.0.1/` own `node`) — so **this machine** is probably fine. The artifact still silently decides the product-wide fail mode for every `codegraph serve --mcp` launched with the supported Node 20–22.4 range (`getMcpServerConfig` command is bare `codegraph`, `installer/targets/shared.ts:24-28`).

Human-authority: operating burden / runtime floor. Grill lock 2-a is “cheap COUNT before reply,” not “if COUNT cannot run, pretend there is no index.”

**Check:** `node -e "require('node:sqlite')"` on Node 20 vs 22.5; design/spec must name the throw branch’s user-visible payload as either existence-only (today) or a documented 22.5 MCP floor.

---

**M3 — Binding tests still cannot see a proxy that waits for the daemon before answering initialize. R4-a spawn was dropped.**
Verdict: **revise** (pin “initialize written while `getDaemonSocket` is still pending”; do not treat BT-1 as a #172 test).

```
Where: artifact BT-1 / OQ-4 CLOSED as stub-deps; G-03; grill R4-a + Risks accepted “Proxy COUNT must not wait for daemon engine open”
Severity: MAJOR
Confidence: VERIFIED
Impact (plain language): The whole point of the local handshake is that the agent gets tools before the background daemon has even bound. A worker that probes, then waits for the daemon, then replies, still passes BT-1 (the stub returns `null` immediately) and still passes BT-3 (that spy is the direct-mode door). The host waits seconds; tools never appear in time. Same failure #172 already named, now on the live door.
```

**Evidence:**

Current listen-before-daemon order (load-bearing):

```278:324:codegraph/src/mcp/proxy.ts
  process.stdin.on('data', (chunk: string) => {
    // … initialize writeClient at :298, tools/list at :301 …
  });
  // ---- daemon connection (background) ----
  let socket: net.Socket | null = null;
  try { socket = await deps.getDaemonSocket(); } catch { socket = null; }
```

Production `getDaemonSocket` can poll 240 × 25ms = **6s** (`index.ts:95-102,441-456`).

BT-1: `getDaemonSocket` “resolves `null` forever (never-ready daemon)” — an immediately-settled null. A reorder to `await deps.getDaemonSocket()` **then** `stdin.on` still answers in the test, and hangs the host for up to 6s in production.

BT-3 spies `CodeGraph.open` / `Parser.init` / `openSync` on the **usable-db direct** path (`mcp-initialize.test.ts` already sets `CODEGRAPH_NO_DAEMON: '1'` at `:33`). It cannot see proxy listen-vs-daemon.

Grill R4-a (LOCKED): “**Live = vitest spawn of `serve --mcp`** (extend `mcp-initialize` / add proxy spawn).” Protocol card: “R4 live = vitest spawn.” Design OQ-4 CLOSED: “No live daemon spawn required.” That close dodges Windows `EPERM` afterEach (valid craft) and also deletes the only test class that would watch proxy initialize vs daemon bind.

**Check:** a stub whose `getDaemonSocket` is a Promise that remains pending for N ms; assert initialize stdout arrives before it settles.

---

**M4 — Helper type is 3-arm; busy copy needs a 4th discriminant. Literal Option A cannot satisfy BT-1 busy.**
Verdict: **revise** (return `{ state, busy }` or equivalent; keep the MCP-**name** freeze).

```
Where: artifact Option A `McpIndexState = 'index_missing' | 'index_empty' | 'usable'` vs mapping table busy row vs BT-1 vs lock 1-a
Severity: MAJOR
Confidence: VERIFIED
Impact (plain language): The cookbook says three boxes, then a fourth label on one of them. A worker who only builds the three boxes has no legal place to put “busy, retry later,” so busy becomes empty. The agent is told the map is hollow while an indexer holds the lock — and may run `codegraph init` (Bucket 4 refuses busy) or abandon, instead of waiting.
```

**Evidence:**

Option A:

> exporting `McpIndexState` (new) = `'index_missing' | 'index_empty' | 'usable'` plus `resolveMcpIndexState(startPath)` (new): … `busy`→`index_empty` with busy flag

Chosen Approach mapping table:

> `busy` | `index_empty` (busy flag) | `SERVER_INSTRUCTIONS_INDEX_BUSY` (new) | defs

BT-1: “busy → tools stay listed + `SERVER_INSTRUCTIONS_INDEX_BUSY` copy.” OQ-1 CLOSED: separate constant, **not** a builder over EMPTY (m3 gaming path).

A function typed to return only the 3-arm union **cannot** select `SERVER_INSTRUCTIONS_INDEX_BUSY` without an extra channel. Lock 1-a / protocol card: “No fourth MCP-visible **name**” — a busy **flag** is allowed; omitting it from the type is not.

Surface matrix already admits “instructions (one of 4 constants)” while Constraints say “Frozen tri-state … No fourth MCP-visible name.” That is consistent only if the 4th constant is keyed by a flag the type currently does not carry.

**Check:** spec signature of `resolveMcpIndexState` must be sufficient to pick all four instruction constants; BT-1 equality vs `SERVER_INSTRUCTIONS_INDEX_BUSY`, not merely “empty-style.”

---

### MINOR

**m1 — UNINDEXED still says “no `.codegraph/` directory”; junk→missing will lie about the cause unless the reword is gated.**
`server-instructions.ts:84-85`: “This workspace has no codegraph index (no \`.codegraph/\` directory)”. Design Implications: “one reword keeps one constant truthful for both.” BT-1/BT-2 only require “reworded UNINDEXED copy” / a snippet, not “must not claim the directory is absent.” Junk db: directory and file both exist (`findNearestCodeGraphRoot` requires `isInitialized` which requires the db file — `directory.ts:93-100,263-281`). Remediation (`codegraph init`) is still right (Bucket 4 unreadable repair). Spec-fix: pin a substring the junk fixture must contain (“no usable index”) and one it must not (“no `.codegraph/` directory”).

**m2 — BT-1 `grep-present 'resolveMcpIndexState' codegraph/src/mcp/proxy.ts` is an unused-import pass.**
Design already has the stub-deps stdout table as the real pin; keep grep as backup only if the plan also requires a call at both `initialize` and `tools/list` branches (or a count ≥ 2).

**m3 — EMPTY copy is undrafted; session comment says hosts list tools once.**
`session.ts:227-228`: “most hosts only request the list once per connection.” OQ-2 re-probe therefore does not pick up empty→usable via `tools/list`. If `SERVER_INSTRUCTIONS_INDEX_EMPTY` copies UNINDEXED’s “don’t call this session,” listed tools are wasted and same-session init pickup dies. Grill 5-a: short copy, user runs `codegraph init` — does not say “treat as inactive.” Spec-fix: EMPTY must not say tools are unavailable.

**m4 — Session initialize startPath ≠ proxy `deps.root`.**
Session probes `rootUri` / `workspaceFolders` / `--path` / cwd (`session.ts:184-202`). Proxy probes launch-time `deps.root` from `resolveDaemonRoot(this.projectPath)` (`index.ts:158-163,277-291`) and **does not read** initialize `rootUri` (`proxy.ts:289-298`). Cursor (live door) injects `--path` and does not send `rootUri` (`installer/targets/cursor.ts:12-25`) — so production Cursor agrees. Claude-with-rootUri vs `--path` mismatch is pre-existing; “same payloads” is false across those two start paths. Spec should say parity is for the **same startPath**, not “whatever each door already used.”

**m5 — COUNT duration is not capped by `busy_timeout = 500`.**
`busy_timeout` waits on a lock (`directory.ts:132`); `SELECT COUNT(*) FROM nodes` on a large table is uncapped. Grill accepted the 500ms lock wait, not COUNT wall time. FCV/spec: pin “probe is COUNT not `open`,” not “always ≤500ms including COUNT.”

---

## Six audits

### 1. Fact & arithmetic

Cited line numbers for the current gates (`session.ts:202,209,230`; `proxy.ts:298,301`; `directory.ts:100,116,123,131-133`; `engine.ts:167`; `tools.ts:728,874,897,1228,2276`; `index.ts:160,281,291,458`; `mcp-initialize.test.ts:33,130,151`; `worktree.ts:89,103`) **match the files read this session**. `runProxy(` has one definition and no callers (verified). `probeIndexHealth` has **zero** hits under `src/mcp/` (verified). ADR 0001:70-77 does pre-authorize an MCP import without a barrel export. Daemon idle `300_000` at `daemon.ts:60` is CONSUMER-ONLY as claimed. `2+2=4` instruction constants is arithmetic, not a fourth **state name**. “~15–25 lines” is the scope estimate, not a file budget — not a finding. “sub-ms warm COUNT” is **unverified** (not measured here).

### 2. Internal consistency

Red cells: (a) 3-arm type vs 4 instruction rows vs BT-1 busy copy (**M4**); (b) “identical payload table” vs two list sources (**M1**); (c) G-10 “fail-open serving, fail-closed state” names throw→missing as safety, which is fail-**closed against a usable index** (**M2**); (d) G-03 “watcher-seq stays green” vs BT-3 correctly saying that test cannot see COUNT→open — internally acknowledged, but BT-1 does not close the **proxy** twin (**M3**).

No unsatisfiable pair inside Option A once M4’s return type exists.

### 3. Gaming simulation (three stakes)

**Stake 1 — both doors same payload**

```
G1. Add index-state.ts. Gate session+proxy initialize instructions on it.
G2. handleToolsList: await retryInitIfNeeded(); then
    state==missing ? [] : (hasDefaultCodeGraph() ? getTools() : [])
G3. proxy tools/list: state==missing ? [] : getStaticTools()
BT-1 (proxy, never-ready stub): busy/empty → static tools. PASS.
BT-2 grep probeIndexHealth. PASS.
Direct busy: await open (5s), cg null → []. Host saw BUSY copy + empty tools/list.
Intent dead. Same-payload lock satisfied only for initialize.instructions.
```

**Stake 2 — 5→3 map**

```
G-junk: map unreadable → index_empty (tools stay). BT-1 junk → tools [] FAILS if BT-1 exists. OK.
G-busy-copy: return index_empty only (M4 type). Pick EMPTY constant. BT-1 BUSY equality FAILS if written; type as specified encourages this. M4.
G-existence-helper: root? usable : missing; never call probe. BT-2 spy FAILS. OK.
G-unclassified→empty: no BT names unclassified. MINOR hole; table says missing.
```

**Stake 3 — COUNT before handshake, heavy init background**

```
G-open-before-reply (direct): BT-3 spy FAILS. OK.
G-daemon-before-listen (proxy): await getDaemonSocket(); then stdin.on; COUNT at initialize.
    BT-1 stub null is instant → PASS.
    BT-3 is CODEGRAPH_NO_DAEMON spawn → does not run this function.
    Production: up to 6s before initialize can be answered. #172 on the live door. M3.
G-COUNT-after-sendResult: initialize still existence-only. BT-1 empty copy FAILS. OK.
```

### 4. Assumption feasibility

| Assumption | Holds? |
|---|---|
| Proxy always full playbook + `getStaticTools()` | YES (`proxy.ts:298,301`) |
| Hollow db opens (`engine.ts:167`) | YES (no 0-node rejection in `doInitialize`) |
| `hasDefaultCodeGraph` is `cg !== null` | YES (`tools.ts:728`) |
| Probe does not mutate + closes | YES (test header `probe-index-health.test.ts:10`; `finally` close `:157-164`) |
| `resolveDaemonRoot` existence-only | YES (`index.ts:160` + `isInitialized`) |
| Daemon initialize reply suppressed | YES (`proxy.ts:344`) |
| `node:sqlite` can throw | YES |
| Throw ⇒ treat as missing is **safe** | **NO** (M2) — engine can still serve |
| Direct is minority; production is `serve --mcp` proxy | YES (`index.ts:284-291`; tests pin `NO_DAEMON`) |
| `runLocalHandshakeProxy` deps injectable | YES (`proxy.ts:180-204`) — mini-RT M1 seam exists |
| worktree strings are MCP-served | YES (`tools.ts:1034,2280,3648`) |
| WAL readers never busy vs daemon writer | LIKELY (`db/index.ts:26-28`); busy fixture is `BEGIN EXCLUSIVE` (`probe-index-health.test.ts:124-128`), not a normal daemon hold |

### 5. Contract compliance

| Contract | Result |
|---|---|
| Tri-state names; junk/unclassified→missing; busy→empty-style | Held in the table; **type cannot implement busy copy** (M4) |
| Empty `tools/list` only for missing | Held in prose; session `hasDefaultCodeGraph` can empty a busy/empty list (M1) |
| Cheap COUNT before initialize; #172 heavy init background | Direct path specified; **proxy wait-for-daemon unpinned** (M3) |
| Import probe, no barrel, `isInitialized` unchanged | Held |
| Both doors same payloads | **Not structural** (M1) |
| Recoverable ≠ `isError` | Held for new copies; OQ-3 still open for explicit-path `openSync` |
| Copy: user `codegraph init`, not `init -i` | Held for named sites (tools emptyWarn + worktree); site/CHANGELOG carved out |
| TD-01 stays OPEN | Held |
| R15 shared binary, no settings/hooks | Held |
| R4-a vitest spawn + proxy spawn | **Deviated** (OQ-4 stub-deps only) (M3) |
| OUT: CLI init, writ, `isError`, plugin bus, `.codegraph/ready`, npm upgrade, `cursor.ts` | Held |
| `codegraph/CLAUDE.md` recoverable SUCCESS-shaped + unindexed = empty tools | Held for missing; empty-db tools listed is the freeze, not that house-rule’s unindexed paragraph |
| ADR 0001 MCP must not import probe | **Carved out** at ADR `:76-77`; design uses the carve-out honestly |

### 6. Missing-by-construction

The author’s position (helper + mapping table + BT-1/2/3) hides: (1) the **list source** (`getTools` vs `getStaticTools`) as if `defs` were one cell; (2) **probe-unavailable** as a missing index rather than a broken thermometer; (3) **proxy #172 ordering** behind a direct-mode spy and an immediately-null daemon stub; (4) the busy **flag** behind a 3-arm type. Rollback is “revert the MCP files”; agents will have cached initialize text until reconnect — irreversibility the ADR offer already names, not a new trap. No `.codegraph/ready` slipped in (TD-01 respected).

---

## Human-authority audit

Silent assume flagged as **M2**: “if we cannot COUNT, hide tools” is an operating-burden / runtime-floor decision. 500ms busy cap is **not** silent — grill Risks accepted + existing `probeIndexHealth`. Exact EMPTY/BUSY strings are grill-deferred craft (lock 5-a + “exact instruction strings … craft for design/spec”); leftover pin is m3, not a silent SLO. OQ-2/OQ-3 remain open (latency of re-probe; junk **call** honesty) — correctly not closed by a subagent.

---

## Mode

**Cross-model** (syn-3-kimi-k3 author, cursor-grok-4.6-high reviewer). Certifies line-cite craft, 5→3 table vs code, and the three stake simulations above. Cannot certify: live Cursor/Claude initialize rendering, COUNT wall time on a large `nodes` table, or Windows EPERM afterEach of a real proxy spawn.
