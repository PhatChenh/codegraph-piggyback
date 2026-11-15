# Verdict — Bucket 4 codegraph CLI live cert (2026-08-18)

After `main` `83a6a7d`. Live binary = rsync of this tree's `codegraph/dist/` onto `~/.codegraph/versions/v1.0.1/lib/dist/`. Never `npm i -g` / `codegraph upgrade`.

Seat: Cursor grok 4.6, this session. No village daemon.

| Check | Command | Observed | Pass/Fail |
|---|---|---|---|
| Step 7 vitest | `npm test -- __tests__/fs-snapshot.test.ts __tests__/probe-index-health.test.ts __tests__/unexpanded-path-refusal.test.ts __tests__/index-command.test.ts __tests__/unsafe-index-root.test.ts __tests__/foundation.test.ts __tests__/mcp-explore-empty-warn.test.ts` | `Test Files  7 passed (7)` / `Tests  92 passed \| 1 skipped (93)` | **PASS** |
| Rsync | `rsync -a --delete dist/ ~/.codegraph/versions/v1.0.1/lib/dist/` | live `codegraph.js` sha `3f360bb7…` = checkout dist | **PASS** |
| C14 version pin | `codegraph --version` | `999.0.0`; `lib/package.json` still 999.0.0; `.local-patches.json` untouched | **PASS** |
| C2 refuse (status door) | `codegraph status '${workspaceFolder}'` in empty temp | exit 1; stderr names literal + `Pass a real folder` + `absolute folder in your MCP config`; no template dir; no `.codegraph/` | **PASS** |
| C3 refuse (init door) | `codegraph init '${workspaceFolder}'` | exit 1; same refuse text (`init path`); no template dir; no `.codegraph/` | **PASS** |
| C5 refuse (serve door) | `codegraph serve --mcp --path '${workspaceFolder}'` (15s alarm) | exit 1 in <15s; stderr names `--path "${workspaceFolder}"` | **PASS** |
| C9 junk repair | junk `codegraph.db` + leftover `-wal` then `codegraph init` | exit 0; `Indexed 2 files` / `6 nodes, 8 edges`; `-wal` gone; `codegraph explore greet` shows `main` → `greet` | **PASS** |
| C7 healthy no-op | second `codegraph init` | `Already initialized`; db sha unchanged `144b04ef…` | **PASS** |

**Trap:** plan walkthrough wrote `status --path`. Live `status` is **positional** (`status [path]`). First attempt `codegraph status --path '${workspaceFolder}'` → `error: unknown option '--path'` (not a product fail). Re-ran positional; that is the door the E2E test uses.

**Not in this cert:** lock/busy/errcode-266/nodes-only (vitest only). Desktop Cursor MCP `${workspaceFolder}` expansion (Bucket 4 OUT).

Temps: `/tmp/bkt4-livecert-auu84A` (repair), `/tmp/bkt4-livecert-c2-kklQDu` (refuse).
