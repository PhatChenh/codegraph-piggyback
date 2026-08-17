# Solution map — Bucket 4 codegraph CLI (design grill)
_Date:_ 2026-08-17  
_Posture:_ design (in-pipeline; split forbidden)  
_Parent:_ `docs/AI_artifacts/_scope/2026-08-16-feedback-bugs-scope.md`  
_Status:_ **LOCKED** 2026-08-17 (owner close)

## Shape (plain)

When this bucket ships:

1. If `--path` **or** `codegraph init`’s folder argument still contains `${…}` unexpanded, the CLI **errors**, names that literal string, tells you to pass a real folder, and **does not** use the current directory. Exit non-zero. Bare `codegraph explore` with no path still uses cwd.
2. `codegraph init` on a db that is **empty** (0 symbols) or **junk** (cannot read) **runs index**. A healthy index (any symbols) still no-ops. No `.codegraph/ready` file.
3. Junk file: replace **only** `codegraph.db` and index. Do **not** delete the rest of `.codegraph/` (lessons stay). If the file is merely **locked/busy**, stop and say so — do not replace.
4. Write a short ADR in the codegraph fork: why `init` now repairs hollow/junk trees.

Home: local `codegraph/` fork. One CLI surface.

## Owner locks this grill

| ID | Lock |
|---|---|
| 0-a | Adopt inherited IN/OUT/freezes |
| 1-a | Refuse `${…}` on init’s positional folder too (same poison, both doors) |
| 2-a | Empty or unreadable → index; healthy → skip |
| 3-c | Replace smashed `codegraph.db` only; locked/busy → error, no wipe |
| 4-a | Write init-repairs ADR with this bucket |
| C1 | Hard error, names the literal, no cwd fallback, non-zero exit |

## Frozen from scope (not reopened)

- `resolveProjectPath` refuse for **all** `--path` callers (not serve-only).
- ACP already sends an absolute worktree path (Bucket 1). Leftover `${…}` become errors here.
- Ready = usable index, not a third file.
- OUT: plugin/event bus; ready stamp; `CODEGRAPH_ALLOW_UNSAFE_ROOT`; MCP `tools/list` (Bucket 5); writ `probe()` (Bucket 6); Desktop `${workspaceFolder}`; npm upgrade of upstream.

## Alternatives dropped

- Serve-only refuse — leftover `init '${workspaceFolder}'` hole.
- Catch `$(` / `%VAR%` — freeze is `${` only.
- `.codegraph/ready` stamp — second source of truth.
- Treat unknown schema as unusable here — Bucket 6 probe contract.
- Auto-`uninit` (wipe whole `.codegraph/`) — would drop `lessons.db`.
- Wipe on any open failure including busy — surprise rebuild of a healthy index a live MCP server holds.
- Skip the ADR — next session re-litigates mkdir-only init.

## Risks accepted

- Empty brand-new repo: second `init` may index again (cheap).
- Locked db: `init` fails until the other process lets go (you retry).
- “Busy vs junk” is craft for design; grill locked the user-visible split only.

## Open questions remaining

None for this grill. Busy-vs-junk detection mechanics → design, not another owner value.

## Parked vs cut

| Item | Tag |
|---|---|
| ACP absolute `--path` | **DONE** in Bucket 1 |
| Desktop `${workspaceFolder}` | **DONE** in Bucket 1 (kept on purpose) |
| MCP missing / empty / usable | **PLANNED** in Bucket 5 |
| writ `probe()` + init wrapper | **PLANNED** in Bucket 6 |
| Native plugin / event bus | **THIS FEATURE, later re-grill** (TD-01) |
| `$(` / `%VAR%` unexpanded forms | **NEVER IN ORIGINAL SCOPE** |
| Prisma/markdown extractors | **NEVER IN ORIGINAL SCOPE** (other buckets) |

Nothing was **CUT**.

## Expert still doesn’t like

LIGHT process for a ~20-line CLI change is still the right call: user-visible contract, two doors, wipe-vs-busy split. Do not silently fold Bucket 5 into this run.

## ADR / CONTEXT / object-map

- ADR: **write** (4-a) in the codegraph fork with the implementation.
- CONTEXT.md: no write (tooling terms, not a product glossary).
- Object-map: no hit.
