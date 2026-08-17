# Verdict — Bucket 1 ACP CodeGraph live cert (2026-08-16)

Daemon: **own** `bkt1-acp-livecert` pid **61207** port **19701**. Did not touch :19341 / :19581 / :19621.

Seat: `cursor-composer` SID `3927783f-11c7-4dee-8c01-6d1cd9391b58`

| Capability | What was done | Observed | Pass/Fail | Evidence |
|---|---|---|---|---|
| Staged ACP `--path` is absolute worktree cwd | Created session; read worktree `.cursor/mcp.json` | `--path` = `/Users/phatchenh/all-projects/vibe-coding-setup/agent_village/.village/worktrees/cursor-3927783f11c74dee8c016d1cd9391b58`. Absolute. Not `${workspaceFolder}`. Not `profile.worktree` (`…/agent_village`). | **PASS** | `worktree-mcp.json`, `path-assert.txt` |
| Worktree index usable | sqlite `select count(*) from nodes` | 6721 nodes | **PASS** | `path-assert.txt` (printed at cert time) |
| ACP worker can call CodeGraph MCP and get a body | One `av turn`: Read TASK.md, one `codegraph_explore` `buildVillageMcpConfig` | `av turn` exit 0, `outcome: ok`. Permission auto-allowed (`readonly-auto-allow`). Worker reply `LINE1: MCP_OK` + `## Exploration: buildVillageMcpConfig` / `Found 188 symbols across 58 files`. No `non_convergence`. | **PASS** | `turn-envelope.json`, `worker-reply.txt`, `transcript.ndjson` seq 80–83 |
| 08-14 class (literal placeholder → empty MCP / exit 6) | Same ACP MCP call path | 1 completed MCP (`rawOutput.success: true` on the wire). Worker quoted real explore text. Exit 0, not 6. | **PASS** | `turn-exit.txt`, transcript seq 81–83 |

**Note:** village transcript still stores MCP complete as `{success: true}`, not the explore body. The **worker reply** carries the body. That is a recording gap, not the 08-14 failure (which had zero completed MCP and loop-breaker exit 6).

**Not in this cert:** Desktop `${workspaceFolder}` (left on purpose). Bucket 4/5/6 (empty/unreadable index). A5 skill note.

## Your own re-check

1. `cat docs/AI_artifacts/8_verification/2026-08-16-bkt1-acp-livecert/worktree-mcp.json` — `--path` must be the `cursor-3927783f…` worktree folder, not `${workspaceFolder}`.
2. `rg MCP_OK docs/AI_artifacts/8_verification/2026-08-16-bkt1-acp-livecert/worker-reply.txt` — must show `Exploration: buildVillageMcpConfig`.
