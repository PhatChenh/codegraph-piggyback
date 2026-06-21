# Codegraph Piggyback

Tools and scripts that query `codegraph.db` to enforce better AI coding agent behavior.

Codegraph docs: https://github.com/colbymchenry/codegraph/tree/main

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
