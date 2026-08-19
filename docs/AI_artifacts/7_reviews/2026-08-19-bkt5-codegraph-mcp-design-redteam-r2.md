# Design red-team r2 — Bucket 5 MCP missing vs empty vs usable

_Date:_ 2026-08-19
_Artifact:_ `docs/AI_artifacts/3_design/2026-08-19-bkt5-codegraph-mcp.md` (post-big-RT r1 patch)
_Mode:_ **cross-model** (author: syn-3-kimi-k3; reviewer: cursor-grok-4.6-high, fresh session, artifact + repo + contracts only). Certifies craft + some shared-judgment misses this lineage can see. **Cannot certify** same-lineage blind spots, live Cursor/Claude initialize rendering, or COUNT wall time on a large `nodes` table.
_Stakes aimed:_ (1) both doors same payload from `getStaticTools()` with no engine wait (2) 5→3 map plus probe-throw existence fallback, not missing (3) cheap COUNT before handshake; initialize answered while daemon socket still pending
_r1:_ `docs/AI_artifacts/7_reviews/2026-08-19-bkt5-codegraph-mcp-design-redteam.md` — **not overwritten**. Closed r1 M1–M4 / BT-1b / `{state,busy}` / throw→existence are not re-filed as if unpatched; this round attacks the **amend’s own new gates**.
_Fix:_ nothing. Report-only. MINORs omitted per dispatch.

## Steelman

The r1 holes were real and the patch aims them: nonempty `tools/list` is now specified as `getStaticTools()` on both doors with no `await retryInitIfNeeded` / `hasDefaultCodeGraph` veto; probe throw is existence-gate fallback (root found ⇒ full playbook, not `index_missing`); busy rides `{ state, busy }` so the 3-arm name freeze can still select `SERVER_INSTRUCTIONS_INDEX_BUSY`; BT-1b pins initialize written while `getDaemonSocket` stays pending, which is the listen-first order already in `codegraph/src/mcp/proxy.ts:281` vs `:324`. Option A (one helper, import `probeIndexHealth`, COUNT not `open` before reply) remains the only shape that satisfies lock 4-a structurally. The live lie is still the proxy door answering from static constants with no DB knowledge (`proxy.ts:298,301`). That is the strongest honest case. The new pins do not actually enforce it.

## Executive summary

Zero CRITICAL. Three MAJOR, all on the r1 amend’s new gates. Option A does not need a different architecture. BT-5 pins tool **names** and a process-lifetime “no `ensureInitialized` having run” spy that fights G-03 background init. Implications `:131` still orders throw→missing while G-10/BT-6 order existence-fallback, and `tools.ts` is a fifth probe site BT-6 never sees. Busy copy equality is proxy-only (BT-1); the session door can ignore the new flag.

**Verdict: revise.**

---

## Findings

### CRITICAL

None. Do not rethink helper / both-doors / import-the-probe / throw→existence.

### MAJOR

**M1 — BT-5 does not pin “same payload from `getStaticTools()`, no engine wait.” It pins names, and its spy fights G-03.**
Verdict: **revise** (byte-compare the `tools` array to `getStaticTools()`; spy window = handleToolsList did not *await* open, not “ensureInitialized never started this process”).

```
Where: artifact Binding tests BT-5; Chosen Approach handleToolsList; G-03 / session.ts:216
Severity: MAJOR
Confidence: VERIFIED
Impact (plain language): The agent on the direct door can still wait on the engine, then get a different letter than Cursor on the proxy door — extra “Budget: N calls” text, or an empty toolbox if open fails — while every named BT-5 check stays green. Same helper, two different letters. The r1 M1 fix is specified in prose and then undercut by the test that claims to enforce it.
```

**Evidence:**

BT-5 (new this patch):

> Session-door test on busy and empty fixtures: `tools/list` returns the SAME tool NAMES as `getStaticTools()` and produces them with NO `CodeGraph.open` / `loadCodeGraph().openSync` / `ensureInitialized` **having run**

Chosen Approach still starts heavy init **after** initialize, as G-03 requires:

> engine init stays backgrounded (`codegraph/src/mcp/session.ts:216` quote: "this.resolvePromise = this.engine.ensureInitialized(explicitPath);")

Today that assignment is real:

```212:217:codegraph/src/mcp/session.ts
    if (explicitPath) {
      // Kick off engine init in the background. If another session in the
      // same daemon already opened the project, `ensureInitialized` is a
      // ~free no-op — N concurrent clients pay exactly one open.
      this.resolvePromise = this.engine.ensureInitialized(explicitPath);
    }
```

MCP hosts send `initialize` then `tools/list`. Honest Option A has already **started** `ensureInitialized` before the list. A literal “having run” spy fails the honest path. Deleting the background kick to pass BT-5 restores the #172 wait on the next `retryInitIfNeeded` (still required at `session.ts:258` for tool calls) or leaves `cg` null longer.

Names are not bytes. `getStaticTools()` has no budget suffix (`tools.ts:620-624`). `getTools()` appends one once `cg` loads:

```806:811:codegraph/src/mcp/tools.ts
      return visible.map(tool => {
        if (tool.name === 'codegraph_explore') {
          return {
            ...tool,
            description: `${tool.description} Budget: make at most ${budget} calls for this project (${stats.fileCount.toLocaleString()} files indexed).`,
          };
```

Default surface is only `explore` (`DEFAULT_MCP_TOOLS` at `tools.ts:645`). Names match; JSON does not. Plan-verify `grep-present 'getStaticTools' codegraph/src/mcp/session.ts` is an unused-import pass (r1 m2 class; this patch’s own deferred note admits the twin for BT-1).

Grill lock 4-a / protocol card: “`session.ts` **and** `proxy.ts` same payloads.” Design line after the mapping table: `"defs" = getStaticTools() on BOTH doors — never engine.getToolHandler().getTools()`.

**Check:** session-door test: after initialize, `tools/list` result deep-equals `getStaticTools()` (not `.map(t => t.name)`); `handleToolsList` stack does not `await ensureInitialized` / `retryInitIfNeeded`. Background `ensureInitialized` from initialize must remain legal.

---

**M2 — Throw→missing is still a binding sentence; `tools.ts` is a fifth probe the throw pin never sees.**
Verdict: **revise** (kill Implications `:131`; every COUNT goes through `resolveMcpIndexState`; BT-6 on the explicit-path throw site too).

```
Where: artifact Implications “Probe failure modes” :131; Assumptions 9–10; Chosen Approach tools.ts copy edit 2; G-10 / BT-6
Severity: MAJOR
Confidence: VERIFIED
Impact (plain language): On Node 20–22.4 the thermometer throws before it can count (the require sits *outside* the probe’s own try). If the worker follows the leftover sentence, a working index looks missing: empty toolbox + “inactive.” If they follow G-10, handshake is fine and tool calls can still throw NotIndexedError on that same index. Either way the r1 M2 hole comes back on a path BT-6 does not test.
```

**Evidence:**

Patched constraint / G-10 / BT-6 (existence-gate, **not** missing):

> throw means **existence-gate fallback** (root found ⇒ usable-enough serving …), NOT mapped to missing-behavior

Unpatched Implications `:131` (opposite instruction, same artifact):

> MCP call sites run on the host's Node, so they MUST wrap and **degrade to missing-behavior** rather than crash the handshake.

Assumptions `:313`: “Why (9+10): mandates try/catch at **every new MCP call site**.”

`require('node:sqlite')` is **outside** the function’s try/catch, so it throws out of `probeIndexHealth` entirely:

```121:135:codegraph/src/directory.ts
  const dbPath = path.join(getCodeGraphDir(projectRoot), 'codegraph.db');
  const { DatabaseSync } = require('node:sqlite') as {
    DatabaseSync: new (
      p: string,
      o?: { readOnly?: boolean }
    ) => { exec: Function; prepare: Function; close: Function };
  };
  let db: { exec: Function; prepare: Function; close: Function } | null = null;
  try {
    db = new DatabaseSync(dbPath, { readOnly: true });
    db.exec('PRAGMA busy_timeout = 500');
    const row = db.prepare('SELECT COUNT(*) AS n FROM nodes').get() as { n: number };
    return { status: row.n === 0 ? 'empty' : 'usable' };
```

Chosen Approach adds a **fifth** COUNT, not via the helper:

> Probe the resolved root once there and differentiate missing vs unreadable.

That site is `getCodeGraph` after `findNearestCodeGraphRoot` succeeds (`tools.ts:870-897`). Option A’s deletion test counts “4 call sites across 2 files (session initialize + tools/list; proxy initialize + tools/list)” — it omits this one. BT-6 stubs the imported probe for **initialize / tools/list** only. A tools.ts `catch` that maps throw→`NotIndexedError` (Implications `:131`) hides a working better-sqlite3 index on the declared Node 20 floor (`package.json:54` `>=20.0.0`; `MIN_NODE_MAJOR = 20` at `node-version-check.ts:48`). Engine open never needs `node:sqlite` (`engine.ts:167` `loadCodeGraph().open`).

Grill lock 3-a: import and map, don’t duplicate the COUNT. Protocol card: junk→missing, throw was never “pretend there is no index.”

**Check:** `rg -n "missing-behavior|degrade to" docs/AI_artifacts/3_design/2026-08-19-bkt5-codegraph-mcp.md` must not contain a throw→missing order; spec: `getCodeGraph` calls `resolveMcpIndexState`, not raw `probeIndexHealth`; BT-6-class fixture on the explicit-path throw.

---

**M3 — Busy copy is pinned on the proxy door only. Session can ignore `{ busy: true }` and still pass every new test.**
Verdict: **revise** (same BT-1 equality vs `SERVER_INSTRUCTIONS_INDEX_BUSY` on the session initialize payload).

```
Where: artifact BT-1 busy equality; mapping table busy row; lock 1-a / 4-a; session.ts:202-210
Severity: MAJOR
Confidence: VERIFIED
Impact (plain language): While an indexer holds the lock, Cursor on the live proxy door is told “busy, retry later.” Direct-mode / daemon-off is told the map is hollow and to run `codegraph init`. Bucket 4 refuses busy. The agent abandons or fights the lock. The helper grew a busy flag so this could not happen; only one door is tested using it.
```

**Evidence:**

BT-1 (proxy stub-deps):

> **Busy copy is asserted by exact equality against the imported `SERVER_INSTRUCTIONS_INDEX_BUSY` constant** (big-RT M4)

BT-5 session door: tool **names** on busy/empty fixtures — no initialize text. BT-2: “empty/missing snippet”; “`tools/list` is `[]` for missing AND junk, non-empty for empty-db” — no session busy instructions.

Helper return is `{ state: 'index_empty', busy: true }` (busy row). Doors must branch on the **flag** to pick BUSY vs EMPTY. A session `switch (state)` with no `if (busy)` emits `SERVER_INSTRUCTIONS_INDEX_EMPTY` (OQ-1 closed: not a builder; a 3-arm-only read is the m3 gaming path). Proxy still passes BT-1.

Today session initialize is a boolean existence gate with no busy discriminant:

```202:210:codegraph/src/mcp/session.ts
    const indexed = findNearestCodeGraphRoot(explicitPath ?? process.cwd()) !== null;
    this.transport.sendResult(request.id, {
      protocolVersion: PROTOCOL_VERSION,
      capabilities: { tools: {} },
      serverInfo: SERVER_INFO,
      instructions: indexed ? SERVER_INSTRUCTIONS : SERVER_INSTRUCTIONS_UNINDEXED,
    });
```

Lock 1-a: busy → empty-style **copy** (“busy, retry later”), not empty-db copy. Lock 4-a: same payloads on both doors.

**Check:** session-door busy fixture: `initialize.result.instructions === SERVER_INSTRUCTIONS_INDEX_BUSY` (imported constant), tools non-empty from `getStaticTools()`.

---

## Simulation transcripts

### Stake 1 — both doors, `getStaticTools()`, no engine wait

```
G1. Add index-state.ts. Proxy tools/list: missing? [] : getStaticTools().
G2. handleInitialize: COUNT, sendResult, then ensureInitialized (G-03 honest).
G3. handleToolsList: await retryInitIfNeeded(); then
      hasDefaultCodeGraph() ? getTools() : getStaticTools();
    Names of getTools() === names of getStaticTools() on default surface (explore only).
G4. grep-present getStaticTools session.ts → PASS (import used in the else branch).
BT-5 names: PASS.
BT-5 "ensureInitialized having run": FAIL on honest handshake (G-03 started it)
     OR PASS if the test is tools/list-only (never called initialize).
If the spy is written tools/list-only: G3 wait + getTools() budget suffix ships.
Proxy BT-1: static tools, no wait. Lock 4-a dead for descriptions / wait.
Intent of r1 M1 not enforced.  [this finding = M1]
```

### Stake 2 — 5→3 + throw fallback not missing

```
G-throw-helper: catch in resolveMcpIndexState → { state:'usable', busy:false }. BT-6 PASS.
G-throw-implications: tools.ts getCodeGraph calls probeIndexHealth raw;
    catch → throw NotIndexedError (Implications :131 "degrade to missing-behavior").
BT-6 does not execute getCodeGraph. PASS.
Node 20 + usable db: initialize serves full playbook + tools;
    first tools/call returns NotIndexedError SUCCESS-shaped "isn't indexed".
    Agent stops calling. Working index hidden on the call path.  [M2]
G-busy-session: helper returns busy:true; session switch(state) → EMPTY constant.
BT-1 proxy BUSY equality PASS. BT-5 names PASS. Session initialize ≠ proxy.  [M3]
```

### Stake 3 — COUNT before reply; initialize while daemon pending

```
G-listen-first + COUNT in initialize branch: BT-1b PASS; BT-1 empty copy PASS.
G-await-socket-then-listen: BT-1b FAIL. Pin holds for initialize.
G-tools/list-awaits-socket: BT-1b still PASS (only initialize asserted).
    Lazy worker will not add that await; not filed as MAJOR this round.
```

## Six audits (short)

1. **Fact & arithmetic.** Cited gates still match files read this session (`session.ts:202,216,221,230`; `proxy.ts:281,298,301,324`; `directory.ts:100,123-133`; `tools.ts:625-631,645,728,810,870-897,2276`; `index.ts:101-102,281,291`; `db/index.ts:31`; `MIN_NODE_MAJOR = 20`; `DAEMON_CONNECT_*` 240×25ms = 6000ms). `require('node:sqlite')` is outside the probe try. r1 line cites for `runProxy` no callers / `probeIndexHealth` zero `src/mcp/` hits not re-run as a hunt; grep this session: worktree strings at `worktree.ts:89,103` are MCP-served (`tools.ts:1034,2280,3648`) **and** CLI-served (`codegraph.ts:956`).
2. **Internal consistency.** Red cells: Implications `:131` vs G-10/BT-6 (**M2**); BT-5 “having run” vs G-03 `ensureInitialized` after initialize (**M1**); helper `{busy}` vs session tests that never read it (**M3**). Mapping table throw row vs 3-arm return type is consistent only if throw maps to `state: 'usable'` — not named as a return value (spec-level; not a fourth MAJOR).
3. **Gaming.** Transcripts above. BT-5 names + grep are the cheap pass. Implications `:131` is the cheap throw→missing pass on `tools.ts`.
4. **Assumption feasibility.** Proxy static playbook: YES (`proxy.ts:298,301`). Hollow open: YES (`engine.ts:167`). Probe require throws: YES (outside try). Throw→existence is **feasible** on handshake if helper wraps; **not** implied for `tools.ts`. `runLocalHandshakeProxy` deps injectable: YES (`proxy.ts:180-204`). BT-1b pending stub is feasible without live daemon.
5. **Contract.** Tri-state + junk→missing + busy→empty-style: held in the table; session busy copy unpinned (**M3**). Empty `tools/list` missing-only: held in prose. COUNT before initialize + #172: BT-1b holds initialize-before-pending-daemon; COUNT-before-reply held by BT-1 empty copy. Import probe, no barrel, `isInitialized` unchanged: held. Both doors same payloads: **not** enforced by BT-5 (**M1**). Throw not missing: held in G-10, contradicted at `:131` (**M2**). TD-01 OPEN / R15 / OUT list: held. R4-a live spawn still stub-deps; BT-1b covers the substance of r1 M3 — not re-filed.
6. **Missing-by-construction.** The amend’s position (BT-5 + BT-6 + BT-1b) hides: (1) `getTools()` description drift behind **names**; (2) a tools.ts COUNT behind a handshake-only throw test; (3) session busy copy behind a proxy-only equality. Rollback remains revert MCP files.

## Human-authority audit

No new silent SLO / floor / budget. 500ms busy cap stays grill-accepted. Node 20 floor + throw→existence is now recorded (r1 M2 closure), not assumed. The leftover `:131` throw→missing is a **craft contradiction**, not a fresh HA pick — but following it would silently decide “hide tools when the thermometer is broken,” which r1 already flagged. OQ-2 / OQ-3 remain open.

## Mode

**Cross-model** (syn-3-kimi-k3 author, cursor-grok-4.6-high reviewer). Certifies line-cite craft, BT-5/BT-6/BT-1 co-satisfiability vs current `session.ts` / `tools.ts` / `directory.ts`, and the three stake simulations. Cannot certify: live host `tools/list` timing vs `ensureInitialized` completion, Windows EPERM of a real proxy spawn, COUNT duration on a large table.
