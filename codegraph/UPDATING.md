# UPDATING CodeGraph — READ BEFORE ANY UPGRADE / REINSTALL / VERSION WORK

**This is a LOCAL FORK.** The npm package is uninstalled ON PURPOSE. Any
`npm install/update -g @colbymchenry/codegraph`, `codegraph upgrade`, or
installer re-run that pulls the registry build will **silently revert the local
patches** below. Guards block most of these paths — do not work around them
without reading this file.

## Why this fork exists (2026-07-19 incident)

An accidental 9.6 GB index of `$HOME` + Cursor passing a literal
`${workspaceFolder}` wedged the MCP daemon in a watchdog kill-loop and hung
agent tool calls for ~7 minutes. Full incident + root cause:
`agent_village/.dsk-worktrees/p9-w2b/docs/AI_artifacts/9_runs/2026-07-19-codegraph-hang-note.md`.

## Local patches (base: upstream v1.0.1)

| Patch | Files |
|---|---|
| Walk-up refuses `$HOME`/fs-root index roots (`CODEGRAPH_ALLOW_UNSAFE_ROOT=1` opts out) | `src/directory.ts` |
| Catch-up gate no longer blocks cross-project (`projectPath`) calls | `src/mcp/tools.ts` |
| Literal `${...}` in `--path` / `init` path refused (non-zero exit, no cwd fallback) | `src/bin/codegraph.ts` |
| `init` repairs an empty/unreadable index; refuses busy/unclassified without touching files | `src/bin/codegraph.ts`, `src/directory.ts` |
| Stack-overflow fix in `getUnresolvedReferencesByFiles` (150k-row spread) | `src/db/queries.ts` |
| Daemon kill-loop circuit breaker (3 watchdog kills / 15 min → refuse respawn) | `src/mcp/liveness-watchdog.ts`, `src/mcp/index.ts` |
| Upgrade clobber guard (`.local-patches.json` marker blocks upgrade/reinstall) | `src/upgrade/index.ts`, `src/installer/index.ts` |
| MCP mapper imports `probeIndexHealth`, maps CLI 5-arm → MCP 3-arm (missing/empty/usable; busy→empty-style) | `src/mcp/index-state.ts`, `src/mcp/session.ts`, `src/mcp/proxy.ts` |

Tests for all of the above live in `__tests__/` (unsafe-index-root,
mcp-catchup-gate, db-perf, liveness-watchdog, upgrade).

## Install layout (what actually runs)

- **The only live install** is the self-contained bundle:
  `~/.codegraph/versions/v1.0.1/` (own `node`, `lib/dist`, `lib/package.json`).
- `codegraph` on PATH = symlinks to that bundle's `bin/codegraph`, in BOTH:
  `~/.local/bin/codegraph` and `~/.nvm/versions/node/<ver>/bin/codegraph`.
- `codegraph --version` prints **999.0.0** — a deliberate anti-update pin
  (real base is 1.0.1, recorded in the marker). Do not "fix" it.
- Marker: `~/.codegraph/versions/v1.0.1/lib/.local-patches.json` — its presence
  is what makes `codegraph upgrade` and the installer's npm step refuse.
- Rollback of last resort: stock 1.0.1 dist at
  `~/.codegraph/versions/v1.0.1/lib/dist.orig-v1.0.1`.

## How to update (the ONLY supported way)

Source of truth: **this directory** (`codegraph-piggyback/codegraph/`).

```sh
cd ~/all-projects/vibe-coding-setup/codegraph-piggyback/codegraph

# 1. make/pull changes in src/, then:
npm run build
npm test                        # or at least the suites touching your change

# 2. deploy the built dist over the live bundle:
rsync -a --delete dist/ ~/.codegraph/versions/v1.0.1/lib/dist/

# 3. verify the live binary:
codegraph --version             # must still print 999.0.0
codegraph upgrade               # must print the "Upgrade blocked: LOCAL PATCHES" refusal
```

The rsync does NOT touch `lib/package.json` (the 999.0.0 pin) or
`lib/.local-patches.json` (the guard marker) — both live OUTSIDE `dist/`.
If you ever recreate the bundle from scratch, re-pin the version and rewrite
the marker, or every guard goes dead.

## Pulling upstream changes (upstream is ahead — 1.4.1+ on the registry)

Never via npm. Fetch upstream source and merge into this directory:

```sh
git remote add codegraph-upstream https://github.com/colbymchenry/codegraph 2>/dev/null || true
git fetch codegraph-upstream
# cherry-pick / diff-apply what you want into codegraph/ (it is a subtree of
# the piggyback repo, not a submodule), re-run the test suites, then deploy
# per "How to update" above.
```

The six local patches above must survive any merge — their tests are the
regression net; run them all.

## Deliberate escape hatches (require explicit human sign-off)

- `CODEGRAPH_ALLOW_CLOBBER=1 codegraph upgrade` — reverts ALL local patches.
- Explicit `npm install -g @colbymchenry/codegraph` — reinstalls the registry
  build and overwrites the nvm-bin symlink. Nothing blocks this on purpose;
  it is the "abandon the fork" action. Ask the owner first.
