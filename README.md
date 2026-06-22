# Codegraph Piggyback

Tools and scripts that query `codegraph.db` to enforce better AI coding agent behavior.

Codegraph docs: https://github.com/colbymchenry/codegraph/tree/main

## How it works

[`piggyback.py`](piggyback.py) wires the hook scripts (impact-analyzer, gate, …)
into Claude Code's `settings.json`. [`manifest.json`](manifest.json) is the
single source of truth: each entry = one script + its hook event(s)/matcher(s) +
scope (`global` → `~/.claude`, `repo` → `./.claude`).

Two roles:

- **Dev machine** (this repo): you add/edit scripts and run `piggyback add` /
  `rm` to mutate the manifest, then **`git commit && git push`**.
- **Any machine** (consumer): `piggyback install` / `init` / `update` pull the
  newest manifest from your remote and **reconcile** `settings.json` to match it —
  adding new hooks **and removing ones the manifest no longer lists**. Only hooks
  *piggyback wrote* (scripts under the install dir) are touched; your own hooks
  are left alone.

Prereqs: **Python 3**, **git**, **curl**.

> **Before first use:** set your repo slug. Edit `REPO=` in [`install.sh`](install.sh)
> (or `export PIGGYBACK_REPO=you/codegraph-piggyback`), and push this repo to GitHub.

## Setup (new machine)

One line — clones the repo to `~/.codegraph-piggyback`, installs stock codegraph
if absent, reconciles your global hooks, and puts a `piggyback` launcher on PATH:

```sh
curl -fsSL https://raw.githubusercontent.com/PhatChenh/codegraph-piggyback/main/install.sh | sh
```

Then **restart your agent session** (Claude Code loads hooks at session start),
and make sure `~/.local/bin` is on your PATH so the `piggyback` command resolves.

### Per repo (once each)

```sh
cd /path/to/repo
piggyback init
```

Idempotent: indexes the repo only if `.codegraph/` is missing, and reconciles the
repo-scope hooks. Safe to re-run.

### Updating — consumers

`install` / `init` / `update` **self-update first** (`git pull` the install dir),
so you always run the newest scripts + manifest. Offline / local edits → it skips
the pull and uses the local copy (never blocks). To refresh a machine:

```sh
piggyback update          # pull + reconcile global (and the current repo if indexed)
piggyback update --no-update   # reconcile only, skip the pull
```

Changing a script's *content* (not its hooks) needs no `settings.json` edit at
all — the hook path is stable, so a `pull` is enough.

### Adding / changing / removing scripts — dev machine

```sh
# add or update an entry (overwrite-by-name), then apply it locally:
piggyback add doc-coverage --script doc-coverage/doc_coverage.py \
  --scope repo --hook 'PostToolUse:Edit|Write'
# multi-hook script: repeat --hook
piggyback add codegraph-gate --script codegraph_adoption/codegraph-gate.py \
  --scope repo --hook 'PreToolUse:Grep|Glob|Read' --hook 'PostToolUse:mcp__codegraph__.*'
# remove an entry (and its hooks locally):
piggyback rm doc-coverage
```

Then **`git commit && git push`**. Consumers pick up the change — add *or* remove —
on their next `init` / `update`.

`status` shows what's registered; `unregister <name>` / `uninstall` reverse things
manually.

## Tools

| Folder | What | Delivery | Status |
|---|---|---|---|
| `dead-code-finder/` | Cron job — query DB for unreferenced nodes | cron script | not started |
| `impact-analyzer/` | Pre-commit hook — show callers affected by diff | git hook | not started |
| `doc-coverage/` | CI check — fail if new functions lack docstring | CI script | not started |
| `changeset-context/` | Auto-generate context brief before Claude session | script | not started |
| `arch-visualizer/` | Turn codegraph into non-coder-friendly architecture map | HTML output | not started |
| `sot-enrichment/` | Single source of truth — ADR + changelog + bugfixes baked in | script | not started |

## Planned scripts per tool

### dead-code-finder
- `dead_code.py` — query `nodes` LEFT JOIN `edges` WHERE no incoming `calls`/`imports` edges; output report

### impact-analyzer
- `impact.py` — parse git diff to extract changed node names, query edges for all callers, print warning
- `.git/hooks/pre-commit` — shell wrapper that calls `impact.py` and blocks commit on high-risk changes

### doc-coverage
- `doc_coverage.py` — query `nodes` WHERE `docstring IS NULL` AND `kind IN ('function','method')` AND recently added; exit 1 if any found
- CI config snippet (GitHub Actions / whatever CI the target repo uses)

### changeset-context
- `context_brief.py` — takes a branch name or file list, queries codegraph for all touched nodes + their callers/callees, outputs a structured brief for pasting into Claude session
- Optional: shell alias or Claude hook to auto-run before session start

### arch-visualizer
- `visualize.py` — query nodes/edges, group by module/file, output a human-readable architecture map
- HTML renderer — interactive graph non-coders can navigate without reading code
- Goal: works on any repo with a codegraph.db, not just ai_kms

### sot-enrichment
- `enrich.py` — merge ADR files, CHANGELOG, and bugfix notes into codegraph nodes as metadata
- `query_sot.py` — given a function name, return all decisions/bugs/changes that touched it
- Output format friendly to non-coders (plain English summary, not raw diffs)

## Shared

`_shared/` — DB connection helper and common SQL queries reused across tools.

## Codegraph DB schema (quick ref)

- `nodes` — functions, classes, methods, files, variables
- `edges` — calls, imports, contains, extends, decorates
- `nodes_fts` — full-text search on name, qualified_name, docstring, signature
- `files` — indexed files with hash + language
- `unresolved_refs` — references codegraph couldn't resolve
