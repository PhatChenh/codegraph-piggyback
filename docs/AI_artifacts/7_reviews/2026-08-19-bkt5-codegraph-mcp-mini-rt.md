# Mini-RT — Bucket 5 MCP tells missing vs empty vs usable

- _Date:_ 2026-08-19
- _Artifact:_ `docs/AI_artifacts/3_design/2026-08-19-bkt5-codegraph-mcp.md`
- _Mode:_ same-model (tier 1, clx-deepseek-v4-flash) — certifies craft (line cites, map), not shared-judgment blind spots.
- _Verdict:_ **NOT green** — 3 MAJOR, 3 MINOR across the three questions. Direction sound; enforcement under-pinned.

## Q1 — Both-doors proxy audit

**Verified true:** exactly two host-facing doors. `runProxy` has zero callers (only def `proxy.ts:83` + doc mentions `proxy.ts:128`, `index.ts:470`). Direct = `startDirect` (`index.ts:335→341` `new MCPSession`); proxy = `runProxyWithLocalHandshake` (`index.ts:441→458`). Daemon `MCPSession`s (`daemon.ts:276`) serve only proxy-forwarded traffic and their initialize reply is suppressed (`proxy.ts:344`). Session door gates today: `session.ts:202` existence-only walk, `:209` instructions, `:230` tools. Proxy door: `proxy.ts:298` writes `SERVER_INSTRUCTIONS` and `:301` writes `getStaticTools()` — both unconditional, no db knowledge.

**Finding M1 (MAJOR) — proxy gate is prose, not structure.** The design names the proxy gate ("The proxy resolves state from `deps.root` at its initialize branch", "at its tools/list branch … identical payload table, so door parity is structural") but pins no failing mechanism if it is skipped. The promised test is only "state cases, both doors" (`Options…Files touched`) with OQ-4 leaving its shape open ("[A] stub-deps unit test … [B] real daemon spawn", recommendation A). No existing test touches the proxy's `initialize`/`tools/list` stdout payloads (`mcp-initialize.test.ts` spawns direct mode only, `CODEGRAPH_NO_DAEMON=1`). An executor that adds `index-state.ts`, rewires `session.ts`, and leaves `proxy.ts:298/301` static ships with **the full playbook + full tools still served on a hollow or junk db** through the live door — and every test currently passes. Close: pin a stub-deps proxy test asserting the payload table per state (missing→`[]`, empty/busy→static list, junk→`[]`) **or** a plan-verify `grep-present 'resolveMcpIndexState' codegraph/src/mcp/proxy.ts`.

**MINOR (context):** direct-door `session.ts:230` `engine.hasDefaultCodeGraph()` is already accidentally health-aware for junk (open throws at `engine.ts:167` → cg null → `[]`); its lie is empty-db instructions/tools. The proxy door is the pure static lie and correctly drives the bucket's ROI.

## Q2 — Gaming sim (one path per hole)

1. **Skip the proxy gate** (same as M1). Add helper, gate `session.ts` only, leave `proxy.ts:298/301` unconditional. Nothing fails.
2. **Existence-as-usable.** Define `resolveMcpIndexState` as `root null → index_missing; else → usable`, never calling `probeIndexHealth`. The bucket's exact bug (hollow db → full playbook) persists inside the new vocabulary. **No test today or pinned asserts the empty copy is ever sent:** `mcp-initialize.test.ts` asserts only `protocolVersion`, `capabilities.tools`, `serverInfo.name` — never `instructions` content nor `tools: []`.
3. **Map junk → `index_empty`** instead of `index_missing` (tools stay listed, empty copy instead of missing copy). The mapping table (`design.md:204-212`) pins `unreadable/unclassified → index_missing`, but no test is pinned with a junk-db fixture asserting `tools: []` at the MCP layer — `probe-index-health.test.ts` tests the probe, not the MCP mapping.
4. **Keep `init -i`.** Fix `tools.ts:2276` only; leave **`sync/worktree.ts:89` and `:103`** — two more user-visible `codegraph init -i` strings the design never names. Assumption 8 defers the whole-fork grep to FCV ("if more sites exist") without listing them.
5. **Collapse busy into `INDEX_EMPTY`.** OQ-1 leaves the busy constant's shape open (constant vs builder); an executor ships plain `SERVER_INSTRUCTIONS_INDEX_EMPTY` for busy and still matches the table's "busy → `index_empty`-style".

## Q3 — #172 vs COUNT

**Verdict: yes — the design keeps heavy init behind the reply.** `sendResult` at `session.ts:205-210` precedes the background kick `this.resolvePromise = this.engine.ensureInitialized(explicitPath)` at `:216`. The new probe replaces only the existsSync walk at `:202`; it is a read-only open + `PRAGMA busy_timeout = 500` + one COUNT (`directory.ts:131-133`), ≤500ms sync budget (G-03, Risks). Engine open / WASM bootstrap stays backgrounded. Contract intact.

**Finding M3 (MAJOR) — the guard that "stays green" cannot see COUNT→engine-open.** `mcp-initialize.test.ts:130` (`it('sends initialize response BEFORE tryInitializeDefault finishes')`) is the only test observing init-before-reply, and it keys on the **"File watcher active" stderr marker** emitted by the *background* `startWatching()`, asserting relative order `response.seq < watcherLog.seq`. If COUNT were replaced by a heavy sync `loadCodeGraph().openSync(root)` before `sendResult` (e.g. to decide "usable"), the response is delayed but still precedes the background init's watcher log — **the ordering assertion holds and the test passes** (whenever the open finishes inside the 10s response wait). The test's own comment scopes it: it catches "re-awaits `tryInitializeDefault` *before* `sendResult`" — i.e. the awaited work must include the watcher-emitting path. The pinned new busy-lock case (5s wall) also can't catch it (a busy db never reaches a usable open). `:118` is vacuous (no root → neither probe nor open runs). Only a latency/type assertion on the **usable-db probe path** distinguishes COUNT from open; the design pins none.

## Findings summary

| # | Sev | Section | Finding |
|---|---|---|---|
| M1 | MAJOR | Q1/Q2-1 | Proxy gate is prose only — no pinned proxy-state test or plan-verify grep; skipping it keeps the live door's full playbook/tools on hollow/junk db |
| M2 | MAJOR | Q2-2 | `resolveMcpIndexState` can be existence-only; no test asserts the empty instructions copy or `tools: []` at MCP layer |
| M3 | MAJOR | Q3 | `mcp-initialize.test.ts:130` passes if COUNT→heavy engine open before sendResult (relative marker ordering, not absolute latency) |
| m1 | MINOR | Q2-4 | `sync/worktree.ts:89,103` hold two more user-visible `codegraph init -i` sites beyond `tools.ts:2276` |
| m2 | MINOR | Q2-3 | junk→missing mapping explicit in prose but no pinned MCP-layer junk-db test |
| m3 | MINOR | Q2-5 | OQ-1 leaves busy constant shape open; busy can collapse into `INDEX_EMPTY` |
