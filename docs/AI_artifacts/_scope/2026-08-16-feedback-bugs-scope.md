# Scope — FEEDBACK bugs + TD-01 (2026-08-16)

Grill posture: **scope**. Owner: all eight named items in, home repos included.  
Scout: `clx-deepseek-v4-pro` SID `76933935-f63c-4520-b008-fc11fc9b04c7` on private village `orch-feedback-scope-scout` port 19341. Digest: `.village/runs/2026-08-16-feedback-scope-scout/channel/SCOUT_DIGEST.md`.

A contract frozen by an earlier bucket is not reopenable by a later one — touching it is a plan-compliance failure, not a design choice, and it re-runs the earlier bucket's approval.

---

## 1. Verdict

**6 IN items in 3 tiers, packed into 6 buckets. 2 items DONE in prior work (not in the queue).**

**Progress 2026-08-16:** Buckets **1** and **2** landed (uncommitted). Bucket 1 **LIVE-VERIFIED** (`docs/AI_artifacts/8_verification/2026-08-16-bkt1-acp-livecert/verdict.md`). A5 skill note skipped (no ACP skill file; do not invent). **Next: Bucket 4.** Remaining ROI: 4 → 3 → 6 → 5.

**Bucket 4 RUN_STATE:** `docs/AI_artifacts/9_runs/2026-08-17-bkt4-codegraph-cli.state.md` (pipeline started 2026-08-17).

Pressure: four repos (piggyback verifiers, local codegraph fork, falkor-writ, agent_village), two new contracts agents/gates consume (writ `probe()` states; MCP missing/empty), and a FULL-vs-LIGHT split inside the codegraph fork (CLI vs MCP) so one pipeline does not swallow the other.

---

## 2. Owner decisions locked

| ID | Lock | Rejected |
|---|---|---|
| C1 | BUG-023 and `files:` unknown-key refusal are **DONE in prior work**. Not re-implemented. | Re-cert as open bugs |
| Q1-a | Honest index states + `writ codegraph-init` runs `codegraph index` when the tree is already initialized but not usable. MCP returns `index_missing` / `index_empty`, never a blank success. Recoverable ≠ `isError`. | Honest names only; gate auto-indexes on every Write deny |
| Q2-a | Village ACP `.cursor/mcp.json` gets `--path <absolute worktree cwd>`. Desktop/global Cursor keeps `${workspaceFolder}`. Codegraph **refuses** an unexpanded `${…}` (no cwd fallback). ACP skill: 0–1 CodeGraph call then Read; R12 not load-bearing on ACP. | Always-absolute including Desktop; codegraph-only fail with village still writing the placeholder |
| Q3-a | `grep-absent`: zero files scanned = fail, same as `grep-present`. | Expand directories to every child file |
| Q4-a | Path-only `touch:`/`new:`: file exists on disk → not MISSING. `path::Symbol` stays MISSING if the index has no symbol. No Prisma/markdown language work in this program. | Index Prisma in codegraph; demote all unindexed MISSING to warn |
| Q5-a | `codegraph init` on an already-initialized tree whose index is unusable/empty **runs index**. Ready = writ `probe() == "usable"` (or codegraph equivalent). No `.codegraph/ready` stamp. No plugin bus. | New ready-file event; leave TD-01 open |
| Q6-a | REUSE: normalize spec name (strip `(...)`, unicode `…`, identifier before `(`). `--strict` stays warn-only for REUSE-DROPPED. | Leave matcher; CodeGraph relocation lookup |
| C2 | OUT of this program: `[id]` glob, swept-prose, `a\|b` grep, REUSE relocation, live painter E2E, ssot P6. | — |

**Probe state freeze (writ):** sqlite connect/select failure or missing `schema_versions` table → **`unreadable`**, never `unrecognized` with `found=frozenset()`. `unrecognized` stays for a real integer version outside `{1, 5}`. `missing` stays for “db file absent”. `usable` unchanged.

**MISSING freeze (plan_verify):** path-only + file exists → verdict **OK** (evidence may say “on disk, not in index”). Genuinely absent path → still **MISSING** / `--strict` fail. No new verdict enum.

---

## 3. Assumption ledger

| # | assumption | confidence | how to check | if wrong |
|---|---|---|---|---|
| A1 | Installed `av` includes BUG-023 two-phase create (`1e48ad2`) | PROBABLE | `av session create --help` shows `--staged`; village `BUGS.md` Status FIXED | Re-open BUG-023 as a village bucket |
| A2 | Village Step 3b `PLAN-MALFORMED:` headline is live in this `av` binary | PROBABLE | `test/av-verify-wave-malformed.test.ts` exists; run that file | Message-path-only follow-up in village, not a piggyback re-parse |
| A3 | `clx-deepseek-v4-pro` scout digest line refs match disk | VERIFIED | digest quotes vs files opened in grill | Re-scout that item before its bucket pipeline |
| A4 | `--spec` is used often enough that REUSE-DROPPED is seen | INHERITED-UNVERIFIED | count `--spec` in recent 9_runs | Q6-a still cheap; skip only if owner recuts |
| A5 | ACP skill patch lives in Cursor/village briefs, not piggyback R12 | GUESSED | grep skills for “CodeGraph first” + ACP | Bucket 1 OUT-list the skill file once found; do not invent a new skill |

---

## 4. Tier definitions

| tier | admission test | process |
|---|---|---|
| **QUICK FIX** | mechanical; ≤2 edit sites; no contract added or changed; correctness provable by one regression test (or docs-only) | direct edit → test → mini red-team on diff |
| **LIGHT PLAN** | one surface; behavior changes but the contract shape is obvious; no unresolved human-authority value inside | 1-page plan → implement → one reviewer |
| **FULL PIPE** | new contract other parts consume, OR irreversible/data-deleting, OR auth/payments/migrations/secrets/infra/CI, OR the failure mode is "silently wrong". **Hard ceiling: one surface.** | design → spec → FCV → plan → implement → review |

---

## 5. Items (by tier)

### QUICK FIX

#### ITEM-3 — grep-absent zero files = fail
- **Promise:** A `grep-absent` that matched zero files fails with `no file matches`, same as `grep-present`.
- **IN:** `diff-verifier/diff_verify.py` `run_qualifier` grep-absent (~106–114). Copy `matched_any` from grep-present (~116–132). Test next to `test_grep_present_no_matching_files`.
- **OUT (hard):** directory expansion; `grep-present` behavior; qualifier grammar; `--allow` / `[id]` glob.
- **Depends on:** nothing
- **Gated by:** nothing
- **Freezes:** vacuous glob is QUALIFIER_FAIL, not clean
- **Size:** 1 edit site, ~5 lines, 1 regression test
- **Why this tier:** mechanical copy of an existing branch; a wrong fix fails tests loudly

#### ITEM-2-village — ACP `--path` is the worktree directory
- **Promise:** Staged village `.cursor/mcp.json` for ACP has `--path` = absolute worktree cwd, not the string `${workspaceFolder}`.
- **IN:** `agent_village/daemon/cursor-bundle.ts` `buildVillageMcpConfig` (~1253–1265). Update `test/cursor-mcp-staging.test.ts` (~66–70) in lockstep. Desktop/global installer path unchanged.
- **OUT (hard):** Desktop `${workspaceFolder}` expansion; codegraph refuse (Bucket 4); rewriting R12 globally; other MCP servers in the bundle.
- **Depends on:** nothing (removes the trigger even before codegraph refuse)
- **Gated by:** A5 — exact ACP skill file path. Probe result that finds no skill file → escalate; do not invent a skill.
- **Freezes:** ACP mcp.json `--path` is an absolute directory; Desktop template may still use `${workspaceFolder}`
- **Size:** 1 production line + 1 test assertion; optional one-sentence skill note once A5 lands
- **Why this tier:** one writer (grep = 1 hit); test already pins the old string
- **R15:** Village ACP mcp.json only. Cursor Desktop global install stays `${workspaceFolder}`. Claude Code MCP is a different config (`~/.claude` / installer) — **no equivalent change in this item**. Claude Code keeps working via CLI/`codegraph serve` as today.

### LIGHT PLAN

#### ITEM-4+6 — disk exists for path-only claims + REUSE name-normalize
- **Promise:** `touch: hooks.json` / `touch: prisma/schema.prisma` on disk is not MISSING. `touch: prisma/schema.prisma::Asset` still MISSING if the index has no `Asset`. Spec `runFalQueue(...)` / `claim_one(stage=…)` matches plan `runFalQueue` / `claim_one`. REUSE-DROPPED never fails `--strict`.
- **IN:** `plan-verifier/plan_verify.py` `verdict_claim` (~208–234) and `check_spec_reuse` (~171–190). Tests: `test_touch_missing`, `TestSpecReuse` including `test_cli_spec_warn_only_never_strict_fails`.
- **OUT (hard):** Prisma/markdown extractors in codegraph; REUSE relocation via DB; swept-prose flood; new STRICT_FAILS member; treating `path::Symbol` as OK just because the file exists.
- **Depends on:** nothing
- **Gated by:** nothing
- **Freezes:** MISSING freeze in §2; REUSE identifier-normalize only
- **Size:** ~10 lines verdict_claim + ~15–20 lines check_spec_reuse + 3–5 tests
- **Why this tier:** one file; behavior change; a bad stat would hide real ghosts (not QUICK)

#### ITEM-2-cg + ITEM-5 — codegraph CLI: refuse `${…}` + init repairs unusable
- **Promise:** `--path '${workspaceFolder}'` (unexpanded) errors and does not use cwd. `codegraph init` on a db-exists-but-empty/unusable tree runs index. Healthy already-indexed trees still no-op. No `.codegraph/ready` file.
- **IN:** `codegraph/src/bin/codegraph.ts` `resolveProjectPath` (~197–218) and `init` already-initialized branch (~486–492). `directory.ts` `isUnexpandedTemplatePath` (~168–170) stays the detector. Tests: new refusal case; `index-command.test.ts` already-initialized-unusable case.
- **OUT (hard):** plugin/event bus; ready stamp; `CODEGRAPH_ALLOW_UNSAFE_ROOT` policy; MCP `tools/list` (Bucket 5); npm upgrade of upstream.
- **Depends on:** nothing
- **Gated by:** nothing. Freeze: refuse in `resolveProjectPath` for **all** callers (not serve-only). Bare `codegraph explore` with no `--path` still uses cwd.
- **Freezes:** unexpanded `${` in `--path` is a hard error; init+unusable ⇒ index; ready = usable index, not a third file
- **Size:** ~6 lines refuse + ~8 lines init branch + 2 tests; ~15 `resolveProjectPath` callers inherit the error
- **Why this tier:** user-visible CLI contract; one surface (`codegraph.ts`); not a new multi-consumer API
- **R15:** CLI/MCP server binary used by both Cursor and Claude Code. One change serves both. No settings.json / hooks.json edit in this bucket.

### FULL PIPE

#### ITEM-1-writ — `probe()` tells the truth; wrapper indexes
- **Promise:** Unreadable db is `unreadable`, not `{none}` unrecognized. `writ codegraph-init` after `codegraph init`, if probe ≠ `usable`, runs `codegraph index` and re-probes. Deny copy names `codegraph index` for that state. Marker still deleted only on `usable`.
- **IN:** `falkor-writ/bin/lib/codegraph_index.py` `probe()` (~53–79). Thread through `blast_radius.py` `freshness()` (~256–295), blast-gate deny strings, `writ-codegraph-init.sh`, `artifact_claims.py` PRE-SCHEMA. Tests: `test_codegraph_index.py` (no corrupt-db case today — add one).
- **OUT (hard):** auto-index inside the Write gate; changing `KNOWN_SCHEMA_VERSIONS`; piggyback probe clone; MCP empty tools (Bucket 5).
- **Depends on:** ITEM-5 helpful but not required — wrapper calls `codegraph index` itself
- **Gated by:** nothing
- **Freezes:** writ probe enum `{missing, unreadable, unrecognized, usable}`; `freshness()` must not map `unreadable` to `unrecognized`; fail-closed (unreadable is never usable)
- **Size:** probe ~8 lines + 1–2 lines per consumer (4 consumers) + tests for missing-table and connect-error
- **Why this tier:** new state other gates/audits consume; today’s lie is silently the wrong diagnosis
- **R15:** Writ blast-gate is registered on Claude Code and Cursor. Same wrapper + same `probe()`. Deny copy must stay harness-agnostic (command text, not a Claude-only hook event).

#### ITEM-1-cg — MCP missing vs empty
- **Promise:** No db → `index_missing` (empty `tools/list` + short instructions). Db with 0 nodes → `index_empty` (not the full playbook). Both SUCCESS-shaped guidance, not `isError`.
- **IN:** `codegraph/src/mcp/session.ts` `tools/list` (~221–231) and instructions (~196–205). `tools.ts` `NotIndexedError` / late `emptyWarn` (~832–845, ~2262–2280). Existence-only `isInitialized` / `findNearestCodeGraphRoot` must not treat 0 nodes as a healthy index for MCP.
- **OUT (hard):** CLI init (Bucket 4); writ probe (Bucket 6); turning recoverable empty into `isError`.
- **Depends on:** Bucket 4 freeze (refuse `${…}`) so MCP is not silently on cwd; does not need Bucket 4 to *start*
- **Gated by:** nothing
- **Freezes:** MCP tri-state missing / empty / usable; recoverable ≠ `isError`; empty `tools/list` only for missing, not for empty-db (empty-db must not look like a full indexed project)
- **Size:** ~15–25 lines across session.ts + tools.ts (+ engine if tri-state lives there) + mcp-initialize tests
- **Why this tier:** agents consume tools/list + instructions; empty-db today looks indexed then fails late
- **A-split on pickup:** only if FCV shows engine.ts + daemon idle-kill as a second surface. Default: one pipeline.
- **R15:** MCP server is shared. Cursor ACP and Claude MCP both see the new payloads. No per-harness settings edit.

---

## 6. Bucket table

| bucket | tier | items | size basis | depends on | status |
|---|---|---|---|---|---|
| **1** village ACP path | QUICK | ITEM-2-village | 1 line + 1 test | nothing | **DONE** 2026-08-16 + live cert |
| **2** grep-absent | QUICK | ITEM-3 | ~5 lines + 1 test | nothing | **DONE** 2026-08-16 tests |
| **3** plan_verify stat + REUSE | LIGHT | ITEM-4+6 | ~25–30 lines + 3–5 tests | nothing | OPEN |
| **4** codegraph CLI | LIGHT | ITEM-2-cg + ITEM-5 | ~14 lines + 2 tests | nothing | OPEN — **next** |
| **5** codegraph MCP | FULL | ITEM-1-cg | ~15–25 lines + tests | none required; prefer after 4 so `${…}` is already loud | OPEN |
| **6** writ probe + init wrapper | FULL | ITEM-1-writ | probe + 4 consumers + tests | none required; wrapper runs `index` even if 4 not merged | OPEN |

Each bucket = one `/build-pipeline` (or QUICK mini-spec) in that item’s **home repo**.

---

## 7. Cross-item contract freeze

| contract | frozen in | consumers |
|---|---|---|
| ACP mcp `--path` is absolute worktree cwd | Bucket 1 | Cursor ACP CodeGraph; Bucket 4 leftover `${…}` become errors not cwd |
| Unexpanded `${` in `--path` is a hard error | Bucket 4 | CLI + MCP serve; Bucket 5 |
| init + unusable db runs index; no ready-file | Bucket 4 | operators; Bucket 6 wrapper (still also calls `index`) |
| MCP missing / empty / usable; recoverable ≠ isError | Bucket 5 | Cursor ACP, Claude MCP, skills |
| writ probe `missing` \| `unreadable` \| `unrecognized` \| `usable` | Bucket 6 | freshness, blast-gate, writ-codegraph-init, PRE-SCHEMA |
| path-only on-disk → not MISSING; `::Symbol` still needs index | Bucket 3 | `--strict` plans |
| REUSE identifier-normalize; never `--strict` fail | Bucket 3 | `--spec` runs |
| grep-absent 0 files = fail | Bucket 2 | verify-wave qualifiers |

---

## 8. Run order (ROI)

Score: **impact / cost**. Impact 1–10 = how badly it bites when unfixed. Cost 1 / 3 / 8 = QUICK / LIGHT / FULL (process, not hours).

| ROI # | Bucket | Impact | Cost | Score | Why this slot |
|---|---|---|---|---|---|
| 1 | **1** village ACP path | 9 — ACP sessions die (08-14, 3 SIDs, exit 6) | 1 | **9.0** | Worst village failure, cheapest fix |
| 2 | **2** grep-absent | 4 — one qualifier class can pass with zero files checked | 1 | **4.0** | Small pain, almost free; same afternoon as #1 |
| 3 | **4** codegraph CLI | 8 — `init` no-op is why the named fix does nothing; `${…}` refuse stops cwd-guess | 3 | **2.7** | Unblocks “run index” for half-dead dbs before the FULL writ bag |
| 4 | **3** plan_verify | 6 — every Prisma/docs `--strict` plan is hand-patched; REUSE is warn-only | 3 | **2.0** | Real orch tax, LIGHT not QUICK |
| 5 | **6** writ probe + wrapper | 9 — Write/StrReplace denied on all product code | 8 | **1.1** | Highest daily pain, FULL process; Bucket 4 already makes `init` repair |
| 6 | **5** codegraph MCP | 7 — empty index looks fine, agent retries | 8 | **0.9** | Workaround exists (Read files); FULL; same fork as 4 so last |

**Solo pickup (this machine):** 1 → 2 → 4 → 3 → 6 → 5. **Remaining after 2026-08-16:** 4 → 3 → 6 → 5.

**If several agents:** still **1 then 2** first (both QUICK, no shared files). Then **4 ∥ 3 ∥ 6**. **5 after 4** (same codegraph fork). Do not start 5 in parallel with 4.

Rejected order: impact-only (1 → 6 → 4 → 5 → 3 → 2) — parks two QUICK wins behind a FULL pipeline. Speed-only (1 → 2 → 3 → 4 → 5 → 6) — does plan_verify before `init` actually repairing the index.

---

## 9. Pre-mortem

Three months later this failed because:

1. **Bucket 6 shipped `unreadable` but `freshness()` still mapped it to `unrecognized`.** Deny text still says “unknown schema `{none}`.” Design change: one test that `freshness()` of a missing-`schema_versions` db is not `unrecognized`.
2. **Bucket 1 wrote an absolute path that was the profile default, not the worktree cwd.** ACP still indexed the wrong tree. Design change: test asserts the staged path equals the session/worktree cwd, not `profile.worktree` when they differ (`/tmp/never-resolved` in the current test).
3. **Bucket 5 empty-db still advertised a full tool list** because `isInitialized` is existence-only. Agents kept treating empty as “wrong query.” Design change: mcp-initialize test with a 0-node db.

Accepted risk: path-only OK (Q4-a) skips blast-radius for files the index never parsed.

---

## 10. Risks if the owner rejects the split

Single bag: one agent in four repos, FULL MCP design dragged through grep-absent, and a probe contract “fixed” only in one consumer. Split cost: six pipeline bookkeepings; user-visible relief starts at Bucket 1, not at bucket 6.

---

## 11. Runner-up split, rejected

**By repo:** piggyback (3+4+6) / village (2-village) / codegraph (2-cg+5+1-cg) / writ (1-writ). Fails: codegraph bag mixes LIGHT CLI with FULL MCP (forbidden mix). Piggyback bag mixes QUICK grep with LIGHT plan_verify (strict protocol drags the 5-line fix).

---

## Solution map (plain)

When this program is done:

1. Village ACP CodeGraph is pointed at the real worktree folder.
2. If something still passes `${workspaceFolder}` unexpanded, codegraph stops instead of using a random directory.
3. `codegraph init` on a half-dead index actually indexes.
4. MCP says missing vs empty instead of looking fine and returning nothing.
5. Writ names unreadable indexes correctly and `writ codegraph-init` runs `codegraph index`.
6. Plan checks: folder `grep-absent` cannot pass on zero files; real files on disk are not MISSING; reuse names like `foo(...)` match `foo`.

**Already true (not this queue):** BUG-023 staged cwd; `files:` → `PLAN-MALFORMED:` / `MANIFEST-EMPTY`.

**Nothing on the leftover list is a scope cut of the original eight.** See parked table.

### Parked vs cut

| Item | Tag |
|---|---|
| BUG-023 | **DONE** 2026-07-10 `1e48ad2` |
| `files:` silent empty | **DONE** 2026-07-27 piggyback + village malformed test |
| `[id]` glob, swept prose, `a\|b` grep | **NEVER IN ORIGINAL SCOPE** of the six+two |
| REUSE CodeGraph relocation | **NEVER IN ORIGINAL SCOPE** (Q6-a rejected c) |
| Prisma-as-language | **NEVER IN ORIGINAL SCOPE** (Q4-a) |
| Live painter E2E, ssot P6 | **PLANNED** on ssot-diagram roadmap; not this program |
| Native codegraph plugin/event bus | **THIS FEATURE, later re-grill** — Q5-a closed TD-01 without it; reopen only if wrapper+init-index is not enough |

Nothing was **CUT**.

### Alternatives dropped

- Gate auto-index on Write deny — surprise minutes on every blocked edit
- Always-absolute mcp path including Desktop — breaks global “any folder” install
- Expand `grep-absent` directories — slow, easy to hit huge trees
- Demote all unindexed MISSING — hides real missing paths
- `.codegraph/ready` stamp — second source of truth vs probe
- Make REUSE-DROPPED fail `--strict` — warn becomes a blocker without fixing the matcher

### Expert still doesn’t like

Bucket 5 FULL for ~20 lines is heavy process, but empty-db looking indexed is the silently-wrong case the FULL rule exists for. Do not quietly demote it at pickup.

### Open questions remaining

- A5: which skill file gets the ACP “0–1 then Read” sentence (escalate if none).
- ADR offers below — owner pick write/skip.

---

## ADR / object-map / CONTEXT

**ADR offers** (all three gates true):

1. Writ `probe()` adds `unreadable` vs keep stuffing sqlite errors into `unrecognized`.
2. ACP absolute `--path` vs Desktop `${workspaceFolder}` split.
3. `codegraph init` repairs unusable trees vs init = mkdir-only forever.

Say which to write. Format: repo ADR next to the bucket that freezes it (writ / village / codegraph fork).

**Object-map:** no map hit (tooling, not a product object model).

**CONTEXT.md:** no write. falkor-writ `CONTEXT.md` is FalkorDB terms, not index-probe states. New enum lives in this freeze table + writ `codegraph_index.py` docstring when Bucket 6 lands.
