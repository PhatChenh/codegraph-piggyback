# Phase Bucket 4 — codegraph CLI refuses `${…}` + `init` repairs an unusable index

_Date:_ 2026-08-17
_Design:_ `docs/AI_artifacts/3_design/2026-08-17-bkt4-codegraph-cli.md` (Option A)
_Grill:_ `docs/AI_artifacts/_handoff/2026-08-17-bkt4-codegraph-cli-grill.md` (LOCKED 2026-08-17)
_RT:_ `docs/AI_artifacts/7_reviews/2026-08-17-bkt4-codegraph-cli-design-redteam.md` (0 CRITICAL; M1–M8 absorbed into design)
_Scope:_ `docs/AI_artifacts/_scope/2026-08-16-feedback-bugs-scope.md` Bucket 4 = ITEM-2-cg + ITEM-5
_Surface:_ local fork `codegraph/` — CLI only. One phase (grill: split forbidden).

## Purpose

CLI `--path` and `codegraph init <folder>` refuse an unexpanded `${…}` string: stderr names the literal, exit non-zero, cwd is not used, no index opened or created. `codegraph init` on an already-present db classifies `usable|empty|unreadable|busy|unclassified` and either no-ops (usable), rebuilds in place (empty), replaces only the `codegraph.db` file set then indexes (unreadable), or errors without touching files (busy / unclassified). After this phase the 9.6 GB `$HOME` fallback cannot recur from an unexpanded template, and a hollow/junk `.codegraph/codegraph.db` is repaired by `init` instead of exiting 0 as a no-op.

## Already built (reuse, do not rebuild)

| Function/Module | Location | What it does | How this spec uses it | Depth |
|---|---|---|---|---|
| `isUnexpandedTemplatePath` | `codegraph/src/directory.ts:169` — `return p.includes('${');` | `${` detector | `assertExpandedPath` calls this; do not widen to `$(` / `%VAR%` | deep (pure predicate) |
| `resolveProjectPath` | `codegraph/src/bin/codegraph.ts:197` | resolves `--path` / positional; today warns + cwd-fallback at `:205` | insert guard at top; 14 callers inherit (`:542,605,684,746,913,989,1107,1172,1437,1507,1544,1623,1701,1808`) | deep |
| `init` action resolve | `codegraph/src/bin/codegraph.ts:468` — `path.resolve(pathArg \|\| process.cwd())` | **does not** call `resolveProjectPath` | second guard call before this resolve (grill 1-a) | shallow (duplicated resolve) |
| `isInitialized` | `codegraph/src/directory.ts:93` / `:100` — `return fs.existsSync(dbPath);` | existence-only | **unchanged**; `init` already-initialized branch (`codegraph.ts:487`) grows a probe *beside* it | deep (21 `src/` call sites; 0 in `src/mcp/**`) |
| `createDirectory` db-exists guard | `codegraph/src/directory.ts:295` — `if (fs.existsSync(dbPath))` | blocks re-init while db file exists | `unreadable` must unlink the file set *before* fresh-init | deep |
| `cg.clear()` + `indexAll` | `codegraph/src/bin/codegraph.ts:643` / `:648` | `index` rebuild shape | `empty` repair reuses this shape on the **same** file | shallow-duplicated with init `:506` |
| init index-run block | `codegraph/src/bin/codegraph.ts:506` `cg.indexAll` · `:518` `printIndexResult` | progress + print + telemetry + watch-fallback | extract `runInitialIndex(...)`; 3 callers | shallow + duplicated |
| `CodeGraph.getStats` / `getNodesByName` / `getCallees` | `codegraph/src/index.ts:762` / `:825` / `:1000` | stats; exact-name lookup; callees (conjoins `calls\|references\|imports\|instantiates`) | **test assertion surface only** — repair proof: names + `main→greet` with `edge.kind === 'calls'` | deep |
| empty definition | `codegraph/src/db/queries.ts:1784` `COUNT(*) FROM nodes` · `codegraph/src/mcp/tools.ts:2273` `nodeCount === 0` | fork-wide empty | probe uses the same COUNT; do not invent a threshold | deep |
| `DatabaseConnection.open` / `configureConnection` / `createDatabase` / `CodeGraph.open` | `codegraph/src/db/index.ts:30-37,112` · `sqlite-adapter.ts:56,137-148` · `index.ts:309` | WAL + `busy_timeout=5000` + **migrations** (writes). `OpenOptions.readOnly` is **dead** (`index.ts:109` never read) | **forbidden** for the probe | deep — do not call |
| `isReplacedOnDisk` / `statInode` | `codegraph/src/db/index.ts:255,270` — win32 `return null` | inode unreliable on win32 | empty Done: POSIX inode; win32 unlink-spy | deep |
| CLI E2E BIN pattern | `codegraph/__tests__/index-command.test.ts:23` `../dist/bin/codegraph.js` | spawn built binary | all CLI Done rows | deep |
| fixture symbols | `codegraph/__tests__/index-command.test.ts:53` `export function greet` (+ `hello`, `main`; `b.ts` imports `a.ts`) | indexed temp repo | repair proof; derive expected names from the **same constant** the fixture is written from | shallow |
| Cursor literal emitter | `codegraph/src/installer/targets/cursor.ts:173` | global install emits `'${workspaceFolder}'` | **do not edit**; refusal is the loud-failure for unexpanded Desktop configs (C1) | n/a (OUT) |
| fatal handler | `codegraph/src/bin/fatal-handler.ts:90` `unhandledRejection` | scars if guard **throws** | guard must `console.error` + `process.exit(nonzero)` — never throw | deep |
| patch table row | `codegraph/UPDATING.md:22` `ignored with warning` · rsync `:55` | merge-survival + deploy | amend row; rsync is ship Done | n/a |

### Partially built (extend)

| What exists | What must change | Why |
|---|---|---|
| `resolveProjectPath` warn + `Falling back to the current directory.` (`codegraph.ts:205`) | hard error, name literal, no cwd, non-zero | grill C1; 9.6 GB incident |
| `init` already-initialized branch (`codegraph.ts:487`) | dispatch on `probeIndexHealth`; keep usable no-op | ITEM-5; existence-only `isInitialized` is the bug |
| init / index duplicated `indexAll` blocks | extract local `runInitialIndex` | R7: three copies would diverge telemetry / watch-fallback |
| `UPDATING.md:22` warn wording | “refused (non-zero exit)” + new init-repair row | fork patch table |
| `codegraph/__tests__/index-command.test.ts` | add already-initialized empty / unreadable / busy / unclassified cases | E2E contract |
| `codegraph/CHANGELOG.md` `[Unreleased]` | two user-facing bullets | fork changelog rules |

### Not built (create)

- `assertExpandedPath(pathArg, label)` — local in `codegraph.ts`
- `probeIndexHealth(projectRoot)` — **unexported** in `directory.ts`
- `runInitialIndex(...)` — local in `codegraph.ts`
- snapshot helper + known-answer fixture (test file, `node:fs` / `node:crypto`)
- `codegraph/__tests__/unexpanded-path-refusal.test.ts`
- `codegraph/docs/adr/0001-init-repairs-unusable-index.md` (new dir)
- committed known-answer bytes for the snapshot helper unit test

## Feature overview

Happy path: provided path without `${` is unchanged; bare `codegraph explore` / `init` still `process.cwd()`. `init` on a db with `COUNT(*) FROM nodes > 0` still prints `Already initialized in ` and offers watch-fallback, exit 0, file identity+bytes unchanged.

Repair path: `init` sees db exists → `probeIndexHealth`. `empty` → `CodeGraph.open` same file + `cg.clear()` + `runInitialIndex` (never unlink). `unreadable` → unlink exactly `{codegraph.db, codegraph.db-wal, codegraph.db-shm}` → existing fresh-init path via `runInitialIndex`. Both succeed at exit 0 and must prove a real index (cross-file `main→greet` `calls` edge), not a node-count bump.

Refusal path: any provided `--path` or `init` positional containing `${` → stderr names the literal + which flag/arg, “pass a real folder” / MCP: “set `--path` to an absolute folder in your MCP config”, `process.exit(nonzero)` **before** resolve/mkdir/open. `serve --mcp` inherits via `resolveProjectPath` (`codegraph.ts:1437`); stdout stays JSON-RPC-clean.

Stop-and-say-so path: probe or any repair **write** throws SQLite errcode 5 → `busy` error naming db path + `codegraph daemon`, exit non-zero, **no unlink**. Any other write failure (incl. nodes-only db: probe COUNT=0 then `CodeGraph.open` / migrations throw `no such table: unresolved_refs` errcode 1 — **`clear()` never runs**) → `unclassified`, abort, **never unlink**. Do **not** map any `no such table:*` (only the probe’s message-confirmed `no such table: nodes`) to `unreadable` unlink. Probe throw with no numeric `errcode`, errcode 14 (chmod 000), errcode 266 (directory-at-db-path under `{ readOnly: true }`), bare errcode 1, or any other code → `unclassified`, touch nothing.

## Out of scope

- **MCP `tools/list` tri-state / session gating** — Bucket 5. Do not edit `codegraph/src/mcp/**`. Do not export `probeIndexHealth` for MCP to consume.
- **writ `probe()` + `writ-codegraph-init.sh`** — Bucket 6. No writ file, no writ deny-copy rewrite. writ keeps reading exit code + its own probe.
- **`isInitialized` health-aware** — frozen this bucket (Option C rejected). MCP couples via `findNearestCodeGraphRoot` → `isUsableRoot`, not a direct `isInitialized` import from `mcp/**`.
- **Installer `targets/cursor.ts` `${workspaceFolder}` emission** — Bucket 1 kept on purpose. Refusal converts failed expand into startup failure (C1), not an installer edit.
- **`.codegraph/ready` stamp** — scope Q5-a / grill. Ready = `nodes` count > 0.
- **`$(cmd)` / `%VAR%` detection** — freeze is `${` only (`directory.ts:169`).
- **Schema-version / unrecognized-schema as unreadable** — Bucket 6 `probe()`. A db that opens and answers COUNT is not `unreadable` here.
- **Auto-`uninit` / wipe of `.codegraph/`** (lessons, daemon logs, gate state) — lock 3-c.
- **Wipe on busy / unknown open failure** — lock 3-c.
- **Native plugin / post-init event bus** — TD-01 stays OPEN; this bucket ships repair, not a lifecycle event.
- **ACP absolute `--path`** — Bucket 1 DONE.
- **Piggyback tools / `.codegraph/codegraph.db` writes from this repo’s Python tools** — n/a; change lives in the fork that owns the db.
- **`npm install -g` / `codegraph upgrade`** — never; ship per `codegraph/UPDATING.md`.

## Constraints

**Binding MUSTs (dispatch / mini-RT / design / RT — do not drop):**

- chmod-000 unclassified snapshot compares **inode + entry list + `'<unreadable>'` sentinel** — never sha256 of an unreadable file.
- Repair proof is **cross-file `main→greet` with `edge.kind === 'calls'`** (same-file `greet→hello` is not the proof).
- Known-answer digest comes from `shasum -a 256` / openssl of a **committed** file, pasted **literal** — never computed by calling the helper.
- Unreadable Done: vanished ⊆ three-file set **AND** leftover `-wal`/`-shm` **absent-or-different-sha** (plant leftover wal in the junk fixture).
- Probe: `new DatabaseSync(dbPath, { readOnly: true })`; never `configureConnection` / `createDatabase` / `CodeGraph.open` / WAL pragma; `try/finally` close; **unexported**; raw `node:sqlite` in `directory.ts` (no `../db`). **Do not drop `readOnly`** to make directory-at-path throw 14.
- chmod-000 probe/unclassified tests pin errcode **14**; directory-at-db-path + specified probe pins errcode **266** (`disk I/O error`) — both `unclassified`, no unlink (FCV A13, bundled Node v24.16.0).
- Write-path: SQLite code 5 → `busy` abort, no unlink; **any other write fail → unclassified, never unlink**. Nodes-only (`nodes` table, no `files`): empty probe then **`CodeGraph.open`/migrations** throw `no such table: unresolved_refs` errcode 1; **`clear()` never runs** (FCV A19). Never map any `no such table:*` to unreadable unlink.
- win32 empty: **unlink spy**, not inode.
- OQ-1/2/3 **CLOSED**: `directory.ts`; name `codegraph daemon`; **no prompt**.
- **Both** busy fixtures (non-WAL probe **and** WAL write-path).

From CLAUDE.md / grill / design:

1. **One surface.** Only `codegraph/src/bin/codegraph.ts`, `codegraph/src/directory.ts`, `codegraph/__tests__/**`, `codegraph/UPDATING.md`, `codegraph/CHANGELOG.md`, one new ADR. OUT: `codegraph/src/mcp/**`, `falkor-writ/**`, `codegraph/src/installer/**`, `agent_village/**`. — source: design Constraint 1; G7.
2. **No `.codegraph/ready`.** Ready = db with `nodes` count > 0. — grill; scope Q5-a.
3. **Detector unchanged** — `codegraph/src/directory.ts:169` quote: `return p.includes('${');`. No escape hatch. Guard runs only when a path argument is **present**.
   Bare cwd intact — `codegraph/src/bin/codegraph.ts:210` quote: `const absolutePath = path.resolve(pathArg || process.cwd());`.
4. **`isInitialized` semantics frozen** — still `existsSync`. Directory-at-db-path is a reachable production state (A15).
5. **Never widen deletion.** Unlink only after positive `unreadable` (errcode 26, 11, or message-confirmed missing-core-table errcode 1). Literal three-element list, not a directory walk. `busy` / `unclassified` / bare errcode 1 / errcode 14 / errcode 266 / no-`errcode` / any other code delete nothing. Survivors in `.codegraph/` keep sha256.
6. **Probe must not mutate.** No `DatabaseConnection.open` (runs migrations — `codegraph/src/db/index.ts:112` quote: `runMigrations(db, currentVersion);`). No `configureConnection` (WAL pragma changes sha256 at constant size). No `createDatabase` (strips `errcode`; cannot pass `readOnly`). No `CodeGraph.open({ readOnly: true })` — dead field, still migrates. No `PRAGMA journal_mode = WAL` in the probe.
7. **Fork discipline.** Source + `npm run build` + rsync `dist/` → live bundle (`codegraph/UPDATING.md:55` quote: `rsync -a --delete dist/ ~/.codegraph/versions/v1.0.1/lib/dist/`). Never npm-global / `codegraph upgrade`. `codegraph --version` stays `999.0.0`.
8. **Exit codes:** `${…}` refusal ≠ 0; `busy` ≠ 0; `unclassified` ≠ 0; successful repair = 0; healthy no-op = 0. Do not `return` from the already-initialized branch with implicit 0 on busy (today’s warn branch `codegraph/src/bin/codegraph.ts:486-494` quote: `Already initialized in` is exit 0 — easy miss).
9. **Stderr only** for the refusal (stdout = MCP protocol on `serve --mcp`).
10. **Guard must not throw** — fatal-handler `unhandledRejection` (`codegraph/src/bin/fatal-handler.ts:89` quote: `target.on('unhandledRejection', (reason: unknown) => {`) is the scarred path.
11. **No TTY confirm** on repair (OQ-3 CLOSED). Grill 2-a is “runs index”; a prompt hangs `writ-codegraph-init.sh`.
12. **Do not export `probeIndexHealth`.** LIGHT freeze: not a new multi-consumer API. Buckets 5/6 keep their own unions (R9). Tests may import the module file directly.
13. G1 n/a (fork owns the db). G5 n/a (installer not modified). G8: only deletion is the db file set after positive `unreadable`.

## Assumptions

FLOOR from design `## Assumptions to verify` (verbatim claims). FCV checks each.

| ID | Assumption | Source implication | What would prove it wrong |
|---|---|---|---|
| A1 | **`init` does not route through `resolveProjectPath`.** `codegraph/src/bin/codegraph.ts:468` — quote: `    const projectPath = path.resolve(pathArg \|\| process.cwd());` — if this is ever changed to call `resolveProjectPath`, the second guard call becomes redundant (harmless, but the plan should notice). | implication A; grill 1-a | `init` action calls `resolveProjectPath` |
| A2 | **The detector is `${`-only.** `codegraph/src/directory.ts:169` — quote: `return p.includes('${');` — the refusal inherits exactly this predicate; no widening. | implication B | detector matches `$(` / `%VAR%` or no longer uses `includes('${')` |
| A3 | **`isInitialized` is existence-only.** `codegraph/src/directory.ts:100` — quote: `  return fs.existsSync(dbPath);` — the whole ITEM-5 defect. Must still be true (unchanged) after this bucket. | implication E | predicate opens SQLite or checks node count |
| A4 | **Empty is already defined by a zero node count in this fork.** `codegraph/src/mcp/tools.ts:2273` — quote: `        if (cg.getStats().nodeCount === 0) {` — the CLI must not invent a different threshold. | implication F | CLI empty ≠ `nodeCount === 0` |
| A5 | **That count is a plain `COUNT(*)` over `nodes`.** `codegraph/src/db/queries.ts:1784` — quote: `        (SELECT COUNT(*) FROM nodes) AS node_count,` — so a raw probe query is equivalent without loading grammars. | implication F | `getStats` empty check is not COUNT over `nodes` |
| A6 | **Opening a db runs migrations (a write).** `codegraph/src/db/index.ts:112` — quote: `      runMigrations(db, currentVersion);` — hence the probe must use its own connection. | implication I | `DatabaseConnection.open` no longer migrates |
| A7 | **WAL is requested on every connection.** `codegraph/src/db/index.ts:33` — quote: `  db.pragma('journal_mode = WAL');` — this is why a reader probe usually survives a concurrent writer, and why `busy` must also be handled on the write path. | implication H | production connections are not WAL-first |
| A8 | **Re-init is blocked while the db file exists.** `codegraph/src/directory.ts:295` — quote: `if (fs.existsSync(dbPath)) {` — so the `unreadable` repair must unlink before re-initializing. | implication J | `createDirectory` allows re-init with db present |
| A9 | **`index` clears before rebuilding.** `codegraph/src/bin/codegraph.ts:643` — quote: `      cg.clear();` — the `empty` repair should reuse this shape rather than an incremental `sync`. | implication J | `index` no longer `clear()`s |
| A10 | **Cursor global installs still emit the literal.** `codegraph/src/installer/targets/cursor.ts:173` — quote: `  const pathArg = loc === 'local' ? process.cwd() : '${workspaceFolder}';` — confirms the refusal's only in-fork trigger. | implication D | installer no longer emits `${workspaceFolder}` |
| A11 | **CLI behaviour is tested against the built binary.** `codegraph/__tests__/index-command.test.ts:23` — quote: `const BIN = path.resolve(__dirname, '../dist/bin/codegraph.js');` — new tests need `npm run build` first. | implication N | CLI tests import in-process and never spawn `dist/` |
| A12 | **The patch table records the old warn-behaviour and must be amended.** `codegraph/UPDATING.md:22` — quote: `ignored with warning`. | implication M | row already says refused, or table gone |
| A13 | **[ENV, verified by probe, not by file; FCV-amended 2026-08-17]** On the deployed runtime `~/.codegraph/versions/v1.0.1/node` (`v24.16.0`), with the specified probe `new DatabaseSync(dbPath, { readOnly: true })`: junk file ⇒ SQLite code 26 at the first file-touching statement (the constructor does **not** throw **for this input** — read that as a fact about junk files only, never as "construction is safe"; chmod-000 and directory-at-path throw *at* construction, which is why the probe's `try` wraps it — Hold 7); write blocked by another process's `BEGIN EXCLUSIVE` ⇒ SQLite code 5; **read** blocked on a **non-WAL** db ⇒ SQLite code 5 (so the probe can observe `busy`); db with no `nodes` table ⇒ SQLite code 1 / "no such table: nodes"; db with smashed pages after the header ⇒ SQLite code 11 / "database disk image is malformed"; `chmod 000` db ⇒ SQLite code **14** / "unable to open database file", thrown at construction; a **directory** at the db path ⇒ SQLite code **266** / "disk I/O error" (`SQLITE_IOERR_READ`), thrown at construction — **not** 14. A writable `new DatabaseSync(dir)` (no `readOnly`) does throw 14; that is **not** this probe — **do not drop `readOnly`** to keep 14. Both 14 and 266 stay `unclassified` (no unlink). Tests pin **266** for the directory fixture and **14** for chmod-000. The first two also hold on the dev `node` (`v24.15.0`). Re-run all seven on the machine that ships the change if the bundled node is ever swapped — the whole dispatch rests on these codes. | implication G; pre-dispatch audit 2; FCV A13 | bundled node yields different errcodes / throw sites, or directory+readOnly throws 14 |
| A14 | **The dispatch must stay total over thrown values, and the destructive arm must stay specific.** Only errcode `26`, `11`, and a **message-confirmed** missing-core-table errcode `1` (`no such table: nodes` only — not any `no such table:*`) reach `unreadable`. A bare errcode 1 (SQLITE_ERROR is a catch-all), errcode `14` (chmod 000), errcode `266` (directory-at-path + `readOnly: true`), any other code, and any throw with no `errcode` at all land in `unclassified` and refuse. No unknown failure may reach the unlink path: a permissions or IO error is not a junk db, and treating it as one would delete a healthy index. | implication G; Hold 3; RT M8; FCV A13/A19 | any other code (or bare 1 / 14 / 266 / no-code) unlinks |
| A15 | **`isInitialized` is satisfied by a directory at the db path.** `codegraph/src/directory.ts:100` — quote: `  return fs.existsSync(dbPath);` — `existsSync` is true for a directory, so "`codegraph.db` is a directory" is a reachable production state that the probe must classify (it does: errcode **266** ⇒ `unclassified` under `{ readOnly: true }` — A13), not a contrived test-only input. | implication G; Hold 5; FCV A13 | `existsSync` false for directories, or init never reaches probe for that shape |

Additional (decomposition; FCV should still check):

| ID | Assumption | Source implication | What would prove it wrong |
|---|---|---|---|
| A16 | `getCallees` matching edge must be filtered to `edge.kind === 'calls'` because the method conjoins `calls\|references\|imports\|instantiates` (`traversal.ts:305` per RT). | Hold 6; RT audit 4 | `getCallees` already returns only `calls` |
| A17 | `codegraph/src/directory.ts` today imports only `fs`/`os`/`path` (RT M5). Importing `../db` is a cycle (`codegraph/src/db/index.ts:12` quote: `import { getCodeGraphDir } from '../directory';`). | OQ-1 CLOSED; RT M5 | `directory.ts` already imports `../db` without a cycle |
| A18 | `CodeGraph.open` always migrates; `options.readOnly` is never read (`codegraph/src/index.ts:109` quote: `readOnly?: boolean;`). | RT M2 | `readOnly` actually skips migrations |
| A19 | **[FCV-found 2026-08-17]** A db with a `nodes` table and no `files` table: probe `SELECT COUNT(*) FROM nodes` returns 0 ⇒ `empty`. Repair then **`CodeGraph.open` / `runMigrations`** throws errcode **1** / `no such table: unresolved_refs` (`codegraph/src/db/migrations.ts:40` ALTER after `getCurrentVersion` returns 0 at `:89-91`). **`clear()` never runs** — `QueryBuilder.clear`’s `DELETE FROM files` (`queries.ts:1867`) is not the throw site. Write-path `unclassified`, **never unlink**. Must **not** map any `no such table:*` to `unreadable`. | FCV A19; component 5 | `CodeGraph.open` on that shape reaches `clear()`, or throws `no such table: files`, or unlinks |

## Component dependency order

What must EXIST before each component works — not the code-writing order.

### 1. Snapshot helper + known-answer fixture
**Goal.** Tests compare `.codegraph/` (and cwd) on **bytes + identity**, not size+mtime, including unreadable/dir/symlink entries.
**Build.** In the test file(s) themselves (not production): a helper over `node:fs` + `node:crypto` against the real temp dir. `lstat` first, then:

| Entry kind | Record |
|---|---|
| readable regular file | `{kind:'file', ino, sha256}` |
| unreadable regular file | `{kind:'file', ino, hash:'<unreadable>'}` after `fs.access(R_OK)` — **never** sha256, never silent skip |
| directory | `{kind:'dir', ino}` |
| symlink | `{kind:'symlink', ino, target}` via `readlink` |
| missing after | absent from entry list |

No wrapper around production, no stub, no injectable comparator. Own unit test: **known-answer** — `shasum -a 256` or `openssl dgst -sha256` of a **committed** fixture file; hex pasted as a **literal**; helper must match that literal. Do **not** compute expected digest by calling the helper. Also: mutate-a-byte / add-an-entry / replace-file-with-symlink / make-file-unreadable. Record `ino` beside the sentinel (Hold 1: rewrite-by-replace of a still-unreadable file).
**Depends on.** None.
**Assumes.** A11 (E2E lives in tests).
**Done when.** Helper unit test greens only if the pasted external-oracle hex matches; a helper that always returns `''` fails. chmod-000 compare uses `{ino, hash:'<unreadable>'}` + entry list, not file sha256.

### 2. `assertExpandedPath` at both doors
**Goal.** Any *provided* path containing `${` is a hard CLI error; cwd is never the fallback; `init '${workspaceFolder}'` cannot mkdir a literal-named directory.
**Build.** Local `assertExpandedPath(pathArg, label)` in `codegraph/src/bin/codegraph.ts`: if `pathArg` is present and `isUnexpandedTemplatePath(pathArg)`, print to **stderr** naming the literal string and the flag/arg (`--path` vs init positional); tell operator to pass a real folder; for MCP-relevant wording include “set `--path` to an absolute folder in your MCP config”; `process.exit(nonzero)`. **Never throw.** Call sites **both**: (a) top of `resolveProjectPath` (`codegraph.ts:197`) — covers 14 callers including `serve --mcp` `:1437`; (b) `init` action **before** its own resolve (`codegraph.ts:468`). Implication L’s “14 callers inherit, zero call-site edits” must **not** be read as “skip (b)”. Detector stays `directory.ts:169`.
**Depends on.** None (reuse `isUnexpandedTemplatePath`).
**Assumes.** A1, A2, A10.
**Interface shape.** Unexported local function. Two call sites = real seam.
**Done when.** Behaviour table rows 1–3 (see component 6). Guard does not use the fatal-handler rejection path.

### 3. `probeIndexHealth` (unexported, `directory.ts`)
**Goal.** Classify an existing db as `'usable' \| 'empty' \| 'unreadable' \| 'busy' \| 'unclassified'` without mutating it and without importing `../db`.
**Build.** Unexported `probeIndexHealth(projectRoot)` in `codegraph/src/directory.ts` beside `isInitialized`. `import { DatabaseSync } from 'node:sqlite'` in `directory.ts` — **no** `../db`. Open with `new DatabaseSync(dbPath, { readOnly: true })`. Then `busy_timeout` pragma (value: OQ-4) + `SELECT COUNT(*) FROM nodes`. **Never** `PRAGMA journal_mode = WAL`. **Never** `configureConnection` / `createDatabase` / `CodeGraph.open` / `DatabaseConnection.open`. All three steps in **one `try`**, `finally` closes a handle if one exists (null-guard: ctor throw ⇒ nothing to close).

Total dispatch over the **caught value**, this order:

1. throw with **no numeric `errcode`** → `unclassified` (check first)
2. `errcode === 5` → `busy`
3. `errcode === 26` or `11` → `unreadable`
4. `errcode === 1` **and** message contains `no such table: nodes` → `unreadable`; any other errcode 1 → `unclassified`
5. any other errcode including **14** (chmod 000) and **266** (directory-at-path + `readOnly: true`) → `unclassified`
6. no throw: count `=== 0` → `empty`; count `> 0` → `usable`

Verdict of 6 is **not terminal** for the run: on WAL, a later repair write can still throw 5 (component 5).
**Depends on.** None.
**Assumes.** A3, A4, A5, A6, A7, A13, A14, A15, A17, A18, A19.
**Interface shape.** Unexported. String union CLI-local. Tests may import the module file. Do **not** freeze this union for Buckets 5/6.
**Dependency category.** in-process.
**Decisions.** Q: probe `busy_timeout` 500 vs 5000? A: 500 (matches recorded non-WAL busy fixture ~546ms; `init` on locked DELETE-mode db stays <1s). B: 5000 (matches `configureConnection`, waits ~5s). **Leaning A.** Human-authority latency → OQ-4 OPEN in Handoff; if owner has not closed it, implement **500**.
**Done when.** In-process (module import) fixtures on the **deployed** errcode recipes: text file → unreadable 26; smashed pages → unreadable 11; no `nodes` table → unreadable 1; other errcode-1 message → unclassified; non-WAL + `BEGIN EXCLUSIVE` + COUNT → busy 5; chmod 000 → unclassified **14** at **construction**; directory-at-path + `{ readOnly: true }` → unclassified **266** at **construction** (not 14); `new DatabaseSync` programmer error / no errcode → unclassified. Probe does not change db sha256 (WAL pragma must not run). Handle closed after return/throw (`finally`). `isInitialized` source still `existsSync` only.

### 4. `runInitialIndex` extraction
**Goal.** Fresh init, empty repair, and unreadable-then-fresh-init share one index-run / print / telemetry / watch-fallback implementation.
**Build.** Extract the block at `codegraph.ts:506` (`cg.indexAll`) + `:518` (`printIndexResult`) into a local `runInitialIndex(...)`. `index` command at `:648` may keep its own `clear()`+index or call the helper after `clear()` — planner’s call, but **all three `init` indexing paths** (fresh, empty, post-unlink) must call the extracted helper. No third copy inside `init`.
**Depends on.** None (exists as duplicated code today).
**Assumes.** A9.
**Done when.** Review can name exactly one function that all three init index paths call. Repair cannot skip telemetry / watch-fallback / result printing that fresh-init performs (R7).

### 5. `init` already-initialized dispatch + write-path abort
**Goal.** Existence-true `init` no longer exit-0 no-ops on empty/junk; never deletes on busy/unknown; never prompts.
**Build.** After `isInitialized` (`codegraph.ts:487` branch), call `probeIndexHealth`. **No confirmation prompt** (OQ-3). Dispatch:

| Probe | Action |
|---|---|
| `usable` | today’s warn + watch-fallback offer; exit 0; touch nothing |
| `busy` | error naming **db path** and likely holder via **`codegraph daemon`** (OQ-2); exit non-zero; touch nothing |
| `unclassified` | error naming **raw errcode + message**; exit non-zero; touch nothing |
| `empty` | open **same** db (`CodeGraph.open` — writes/migrations OK here); `cg.clear()`; `runInitialIndex`. **Never unlink.** File identity must survive (POSIX inode; win32: production never `unlink`s the db path). A db with `nodes` and no `files` classifies empty (COUNT=0) then dies on **`CodeGraph.open` / migrations** (`no such table: unresolved_refs`, errcode 1) — **`clear()` never runs**. That is write-path `unclassified`, **not** a back-door `unreadable`. Do **not** map any `no such table:*` to unlink. |
| `unreadable` | unlink **exactly** `codegraph.db`, `codegraph.db-wal`, `codegraph.db-shm` (ignore missing sidecars); then existing fresh-init path (`createDirectory` + `runInitialIndex`). Catch-all “then unlink” **forbidden**. |

Write-path (every repair write: `CodeGraph.open` / migrations / `validateDirectory`→`ensureGitignore` / `clear()` / `indexAll`): SQLite code **5** → same `busy` error, **delete nothing** (even if this is the empty path that never unlinked, or mid-unreadable after unlink already happened — abort indexing; do not keep deleting). **Any other write failure** → abort as `unclassified`, **never unlink** (and do not treat as unreadable — including errcode 1 `no such table: unresolved_refs` on a nodes-only db at **open**, A19). Partial mutation on empty `clear()` failure is `unclassified` + non-zero, not a wipe.

`unreadable` unlink is the **only** deletion, and only after a **positive** `unreadable` classification already returned.
**Depends on.** 2 (init door already refused `${…}`), 3 (probe), 4 (`runInitialIndex`).
**Assumes.** A3, A8, A9, A14, A15, A19.
**Done when.** Behaviour table rows 4–8 (component 7). No `readline` / clack confirm on the repair path. `uninit` prompt at `codegraph.ts:550-565` is **not** copied.

### 6. E2E unexpanded-path-refusal tests
**Goal.** Both doors refuse `${…}` without touching cwd; bare cwd still works.
**Build.** New `codegraph/__tests__/unexpanded-path-refusal.test.ts`, spawn `BIN` = `../dist/bin/codegraph.js` (A11). Requires `npm run build` first. Use snapshot helper (component 1). Cover at least one `resolveProjectPath` command (`explore`/`status`/`index`/`serve --mcp`) **and** `init` positional. `serve --mcp` assertion: process exits non-zero **before** serving; stderr contains literal; stdout is not the only channel for the message.
**Depends on.** 1, 2.
**Assumes.** A2, A10, A11.
**Done when.** (invariant, not proxy)

| Input | Exit | Effect | Done assertion |
|---|---|---|---|
| `--path '${workspaceFolder}'` (any command through `resolveProjectPath`) | ≠ 0 | stderr names `${workspaceFolder}`; cwd not used; no index opened/created | snapshot cwd `.codegraph/` (entry-name list + **sha256 per file**) before/after identical; `readdirSync(cwd)` has **no** entry named `${workspaceFolder}`; if cwd had no `.codegraph/`, none exists after; exit ≠ 0; stderr contains the literal |
| `codegraph init '${workspaceFolder}'` | ≠ 0 | same message; no `.codegraph/` created anywhere | same cwd snapshot pair, **plus** `existsSync('${workspaceFolder}')` is false in cwd **and** in the temp root |
| `codegraph explore` (no path) | unchanged | `process.cwd()` as today | healthy indexed fixture still answers |

### 7. E2E init-repair tests
**Goal.** Empty rebuilds in place; unreadable replaces the three-file set only; busy/unclassified mutate nothing; repair is a real index.
**Build.** Extend `codegraph/__tests__/index-command.test.ts` (and/or a sibling). Spawn `dist/` BIN. Snapshot helper for every mutation claim. Fixture source + expected symbol names from **one constant** (Hold 6). Plant leftover `-wal` in junk fixtures.

**Busy fixtures — both required (Hold 2):**
- **Probe busy:** non-WAL (`PRAGMA journal_mode = DELETE`) + second process `BEGIN EXCLUSIVE` + probe/init (errcode 5 on read).
- **Write-path busy:** WAL tree + concurrent writer; init classified empty/usable-then-write (or empty repair write) throws 5 → same busy error, no unlink.

**Unclassified fixtures:** (b) `codegraph.db` as a **directory** = **primary** (platform-independent, `existsSync` true). Probe `{ readOnly: true }` throws errcode **266** / `disk I/O error` — tests **pin 266**, not 14. (a) `chmod 000` = `it.runIf(process.platform !== 'win32' && process.getuid?.() !== 0)`; restore mode in `afterEach`; tests **pin 14**. Add a **nodes-only** write-path fixture (A19): `nodes` table, no `files`; `init` exits ≠ 0 as `unclassified`; error names errcode 1 + `unresolved_refs`; vanished-names empty; **no unlink**.

**Repair proof** (empty **and** unreadable rows): reopen db; `getNodesByName` for `greet`, `hello`, `main` each ≥1 node; `getCallees(main)` includes `greet` with **`edge.kind === 'calls'`**; both `a.ts` and `b.ts` in `files`. Same-file `greet→hello` optional. A hand-inserted dummy node must fail this.
**Depends on.** 1, 5 (hence 3, 4). 2 already applied to init.
**Assumes.** A4, A8, A9, A11, A13, A14, A15, A16, A19.
**Done when.**

| Input | Exit | Effect | Done assertion |
|---|---|---|---|
| `init <dir>` nodes > 0 | 0 | today’s no-op + watch-fallback | db **inode + sha256** unchanged; node count unchanged; no index-result line |
| `init <dir>` 0 nodes | 0 | open, `clear`, full-index **in place** | **POSIX:** db **inode same** before/after. **win32:** do **not** gate on inode (`statInode` returns null); spy that production **never `unlink`s** the db path; `.codegraph/` entry list otherwise unchanged. **Plus repair proof.** |
| `init <dir>` unreadable (26 / 11 / missing-`nodes` code 1) | 0 | delete db+wal+shm **only**, re-init, full-index | **full** before/after listing: vanished ⊆ `{codegraph.db, codegraph.db-wal, codegraph.db-shm}`; every other entry present with **unchanged sha256**; for each `-wal`/`-shm` that existed before: after, path **absent or sha256 ≠ before-sha**. Plant leftover `-wal` so unlink-db-only cannot green. Plus repair proof. **One fixture per junk shape.** Hollow-db (code 1) must assert repair **happened**, not merely “did not delete extra” (Hold 3 successor). |
| `init <dir>` locked (errcode 5) | ≠ 0 | error names db path + other process; no delete, no index | db sha256 **and** inode unchanged; `.codegraph/` entry list + every file sha256 unchanged; node count unchanged. **Non-WAL exclusive** fixture (deterministic). |
| `init <dir>` unclassified | ≠ 0 | error names raw errcode + message; no delete, no index | vanished-names **empty**. Per-entry: readable files by sha256; chmod-000 db by `{ino, hash:'<unreadable>'}` (**not** sha256 of unreadable) **and named errcode 14**; directory-at-db-path by `{kind:'dir', ino}` **and named errcode 266** (not 14). Fixtures (a)+(b) as above. Nodes-only (A19): named errcode 1 + `unresolved_refs`; no unlink. |

### 8. ADR + UPDATING.md + CHANGELOG.md
**Goal.** Fork merge-survival and operator-visible record; grill 4-a.
**Build.**
1. `codegraph/docs/adr/0001-init-repairs-unusable-index.md` (create `codegraph/docs/adr/`). Why `init` stopped being mkdir-only; why repair beats a `ready` stamp; why `busy` ≠ wipe; Buckets 5/6 own their own unions (`probeIndexHealth` unexported).
2. `codegraph/UPDATING.md`: amend `:22` from `ignored with warning` to refused (non-zero exit); **add** a row for init-repair.
3. `codegraph/CHANGELOG.md` under `## [Unreleased]`, user-facing, fork changelog rules.
**Depends on.** Behaviour of 2 and 5 specified (can be written in parallel with code).
**Assumes.** A12.
**Done when.** ADR file exists at that path. Patch table no longer claims warn-and-ignore. CHANGELOG has both behaviours. No writ / MCP / installer files touched.

### 9. Build, test, rsync deploy
**Goal.** Change is not dark on the live binary (implication M, R6).
**Build.** `npm run build` then `npm test` at minimum: new test files + `unsafe-index-root` + `index-command` + `foundation` + an MCP **smoke** suite (run existing; do not edit `src/mcp/**`). Then rsync per `UPDATING.md:55`: `rsync -a --delete dist/ ~/.codegraph/versions/v1.0.1/lib/dist/`. Then `codegraph --version` prints `999.0.0`. Acceptance: live `codegraph init` against a hollowed temp repo (0-node or junk) indexes.
**Depends on.** 2–8.
**Assumes.** A11, A12, A13 (re-run seven recipes if bundled node swapped).
**Done when.** Deployed binary refuses `${…}` and repairs hollow/junk `init`; version still `999.0.0`. Session deploy-drift banner gone for these files.

## Handoff notes

- **Contract with Bucket 5:** this phase promises a loud `${…}` CLI/`serve --mcp` failure (process does not serve a wrong index). It does **not** promise the agent sees stderr (fail-closed ≠ fail-visible). It does **not** export a 5-arm probe. MCP keeps `index_missing` / `index_empty`. Do not start Bucket 5 from this union.
- **Contract with Bucket 6:** `init` now indexes empty/unreadable (exit 0) and fails busy/unclassified (exit ≠ 0) with no prompt. writ wrapper is unchanged. writ’s `missing|unreadable|unrecognized|usable` stays writ’s.
  gate-waive: C7-ARMDRIFT -- two distinct unions (CLI probe vs writ probe)
- **Contract with piggyback / this repo’s Python tools:** none. Fork owns the db. G1 still holds for piggyback.
- **Open uncertainty (OQ-4, human-authority latency):** probe `busy_timeout` **500 vs 5000**. RT m5: 500 → errcode 5 in ~546ms; 5000 → ~5213ms on locked DELETE-mode. Owner was not asked. **Recommended: 500** (fixture match, `init` stays snappy). Implement 500 unless owner closes otherwise. OQ-1/2/3 remain CLOSED — do not reopen (`directory.ts`; `codegraph daemon`; no prompt).
- **Suggested research before planning:** none beyond FCV of A1–A19. If FCV finds `init` already calls `resolveProjectPath`, drop redundant second call but keep an explicit init-path test. If bundled node ≠ v24.16.0, re-run A13’s recipes (directory+readOnly must still be 266, chmod-000 14) before coding dispatch.
- **Planner traps (RT gaming):** (1) guard only in `resolveProjectPath` — init positional hole; (2) `console.error` then continue with `pathArg = undefined` — today’s control flow; (3) probe via `configureConnection` / `createDatabase` / `CodeGraph.open({ readOnly: true })`; (4) empty = unlink+reinit (stdout-identical; fail POSIX inode / win32 unlink spy); (5) unreadable = unlink db only (fail planted-wal sha clause); (6) busy = `clack.log.error` + `return` exit 0; (7) write-fail catch-all unlink; (8) export the probe; (9) copy `uninit` TTY prompt; (10) new `index-health.ts` (Constraint 1); (11) directory fixture asserts errcode 14 — specified probe throws **266**; (12) map any `no such table:*` to unreadable unlink — nodes-only dies at **open** with `unresolved_refs`, not `files`/`clear()`.
- **TD-01:** stays OPEN. Do not add a native post-init hook in this phase.
- **Next stage:** `/factual-code-verification` on A1–A19, then `/plan`.