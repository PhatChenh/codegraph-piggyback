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

**The install root is whichever checkout you run `install` from.** `piggyback install`
writes the `piggyback` launcher (`~/.local/bin/piggyback`) to point at *that* checkout,
installs stock codegraph if absent, and reconciles your **global**-scoped hooks. Pick a
model:

**A — Consumer (use the published hooks).** One line: clones to the fixed path
`~/.codegraph-piggyback` (same on every machine → portable) and runs `install` for you:

```sh
curl -fsSL https://raw.githubusercontent.com/PhatChenh/codegraph-piggyback/main/install.sh | sh
```

**B — Dev machine (edit + use the same checkout).** Clone wherever you work, then run
`install` from that clone — it becomes the root, so edits to scripts go live immediately
(no commit/pull):

```sh
git clone https://github.com/PhatChenh/codegraph-piggyback.git ~/projects/codegraph-piggyback
python3 ~/projects/codegraph-piggyback/piggyback.py install
```

Either way: **restart your agent session** afterwards, and ensure `~/.local/bin` is on
your PATH so `piggyback` resolves. **Switching the root later** = just run `install` from
the checkout you want — it rewrites the launcher, no manual edit. (Avoid two checkouts
both wired into the same repo: hooks carry the path of the root that wrote them, so two
roots = duplicate hooks. One root per machine.)

### Per repo (once each)

```sh
cd /path/to/repo
piggyback init            # interactive: pick scripts (default = all)
piggyback init --all      # non-interactive: install everything, no prompt
```

`init` is the single per-repo setup and is **idempotent / safe to re-run**. In one
command it:

1. **asks which scripts to install** (Enter = all; or `1,3`; or `n` = none). A
   non-interactive stdin (CI, pipes) installs all without prompting.
2. installs codegraph if absent and runs `codegraph init` only if `.codegraph/`
   is missing.
3. wires the chosen repo-scoped hooks. Full selection **reconciles** (idempotent +
   self-healing: re-runs never duplicate, and a renamed/removed script's old hook is
   pruned); a subset is add-only (run `piggyback update` to reconcile the whole scope).
4. if **decision-index** was chosen, **seeds `docs/decision-index.json`** from
   `docs/adrs/*.md` (only when absent — your curated index is never clobbered).

Per-script control still exists: `piggyback register <name>` / `unregister <name>`
wire one script at a time; `piggyback status` shows what's registered.

### Updating — consumers (the runbook you run tomorrow)

`install` / `init` / `update` **self-update first** (`git pull` the install dir),
so you always run the newest scripts + manifest. Offline / local edits → it skips
the pull and uses the local copy (never blocks).

**Two scopes, two commands — don't mix them up:**

- `piggyback install` → **global** hooks only (`impact-analyzer`). Run once per
  machine, from anywhere. Does **not** wire `codegraph-gate` (gate is repo-scope).
- `piggyback init` → **repo** hooks (`codegraph-gate`, `decision-index`). Run once
  per project repo, **from inside that repo**. Wires into `./.claude/settings.json`.

**Refresh a machine after a push (dev → GitHub → consumers):**

```sh
# 1. global hooks (impact-analyzer) — any dir, once per machine:
piggyback update                # pull + reconcile global (+ current repo if indexed)
# or: piggyback install --no-update

# 2. repo hooks (the gate) — inside EACH project you want the gate active in:
cd /path/to/project
piggyback init --all            # re-runs safely; prunes stale, adds current
```

Then **restart your agent session** (hooks load at session start).

**Cross-machine sync without re-init on every box:** commit each project's
`.claude/settings.json` to git. Repo-scope hooks point at `~/.codegraph-piggyback/...`
(portable `$HOME` form), so the same file works on every machine. Then machine B
just `git pull`s the project and restarts — no `piggyback init` needed there.
(Only the global `install` step is per-machine.)

**Gotcha that bites:** running `piggyback install` (or `update`) reconciles
**global** only. If `codegraph-gate` was previously wired globally (legacy, when
its scope was `global`), `install`/`update` will **remove it as stale** — that's
correct under the current repo-scope design, but it looks like the gate
"disappeared." Re-wire it with `piggyback init --all` inside the project repo.

Changing a script's *content* (not its hooks) needs no `settings.json` edit at
all — the hook path is stable, so a `pull` is enough.

### Adding / changing / removing scripts — dev machine

```sh
# add or update an entry (overwrite-by-name), then apply it locally:
piggyback add doc-coverage --script doc-coverage/doc_coverage.py \
  --scope repo --hook 'PostToolUse:Edit|Write'
# multi-hook script: repeat --hook
piggyback add codegraph-gate --script codegraph-gate/codegraph-gate.py \
  --scope repo --hook 'PreToolUse:Grep|Glob|Read' --hook 'PostToolUse:mcp__codegraph__.*' \
  --hook 'PostToolUse:Edit|Write'
# remove an entry (and its hooks locally):
piggyback rm doc-coverage
```

Then **`git commit && git push`**. Consumers pick up the change — add *or* remove —
on their next `init` / `update`.

`status` shows what's registered; `unregister <name>` / `uninstall` reverse things
manually.

## Active scripts

A folder usually matches its manifest key; a larger feature may host several
scripts under one folder (e.g. `ssot-diagram/` hosts the `decision-index` engine +
hook). The `init` picker lists these:

| Name | Scope | Hook(s) | What |
|---|---|---|---|
| `impact-analyzer` | global | `PostToolUse:Read` | show callers affected by what you just read |
| `codegraph-gate` | repo | `PreToolUse:Grep\|Glob\|Read` + `PostToolUse:mcp__codegraph__.*` + `PostToolUse:Edit\|Write` | codegraph-first ordering gate |
| `decision-index` | repo | `PostToolUse:Read` | surface stale ADRs when you read them |

Scope decides the installer: **`piggyback init`** (per-repo) wires the **repo**-scoped
scripts into `./.claude` and its picker lists only those; **`piggyback install`**
(per-machine) wires the **global**-scoped scripts into `~/.claude`. So
`impact-analyzer` comes from `install`; `codegraph-gate` + `decision-index` from `init`.

### decision-index — decision-staleness tracking

Tracks whether the code an ADR depends on has drifted, deterministically, off the
codegraph index. Each decision declares **anchors** (a file or a symbol) with a
**signature** snapshot; the engine recomputes and compares — no LLM in the verdict.

States: `FRESH` (unchanged) · `STALE` (code drifted, review it) · `ORPHANED`
(anchor gone) · `AMBIGUOUS` (anchor matches >1 symbol).

The hook (wired by `init`) **surfaces** staleness when you read an ADR; it never
edits the ADR. Resolution is human-gated.

The engine is also a standalone CLI ([`ssot-diagram/decision_index.py`](ssot-diagram/decision_index.py)):

```sh
# from a codegraph-indexed repo with docs/adrs/*.md:
decision_index bootstrap              # seed docs/decision-index.json (also run by `piggyback init`)
decision_index status                 # FRESH/STALE/ORPHANED per anchor; exit 1 if any not FRESH
decision_index status --json          # machine-readable (CI gate)
decision_index check docs/adrs/ADR-0007-*.md   # one doc (the hook calls this)
decision_index refresh ADR-0007       # re-snapshot after confirming the decision still holds
```

`bootstrap` is a **seed**: every anchor lands `verified:false` for you to curate
(drop wrong anchors, disambiguate `name@path`, set `supersedes`). Ambiguous /
unresolved doc tokens are skipped and reported, never guessed. Anchor signatures
come from `.codegraph/codegraph.db` (read-only): file anchor = `files.content_hash`;
symbol anchor = sha256 of the symbol's source slice.

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
