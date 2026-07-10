# Step 3 Implementation Report — `ssot-diagram/render.py`

Step 3 of the P5 HTML renderer plan (`ssot-diagram/ai-artifacts/4_plans/p5-html-renderer.md`).
Scope: CLI plumbing only — header, sibling-import seam, constants, `build_parser`,
`_render_paths`, `cmd_render` shell, `main`. No load/escape/splice/save (later steps).

## Files changed (declared file list)

- `ssot-diagram/render.py` — NEW (only file touched)

## Plan-verify qualifiers (Step 3)

- new: `ssot-diagram/render.py::build_parser` — line 92
- new: `ssot-diagram/render.py::_render_paths` — line 34
- new: `ssot-diagram/render.py::cmd_render` — line 78
- new: `ssot-diagram/render.py::main` — line 109
- tier: B
- qualifiers:
  - grep-absent `sqlite3.connect` in `ssot-diagram/render.py` — confirmed (no matches)
  - byte-unchanged `ssot-diagram/graph_model.py` — not touched
  - byte-unchanged `ssot-diagram/testdata/mkt_engine.model.json` — not touched

## Symbol verification

```
$ grep -n -E "^def (build_parser|_render_paths|cmd_render|main)\b" ssot-diagram/render.py
34:def _render_paths(args) -> tuple[Path, Path | None, Path | None, Path, str]:
78:def cmd_render(args) -> None:
92:def build_parser() -> argparse.ArgumentParser:
109:def main() -> None:

$ grep -n "sqlite3.connect" ssot-diagram/render.py
(no matches — grep rc=1)
```

All four claimed symbols present. `sqlite3.connect` absent — render never opens the DB
(per the plan's stronger-than-read-only rule, FCV A9).

## Verify commands — real output

### 1. `python3 ssot-diagram/render.py --help` → exit 0 (lists exactly six flags)

```
usage: render [-h] [--model MODEL] [--narratives NARRATIVES] [--config CONFIG]
              [--out OUT] [--component COMPONENT] [--title TITLE]

render diagram-model + narratives into a self-contained HTML file

options:
  -h, --help            show this help message and exit
  --model MODEL         diagram-model.json (default: <root>/ssot-
                        diagram/diagram-model.json)
  --narratives NARRATIVES
                        narratives.json (default: config narratives_path)
  --config CONFIG       config (default: <root>/ssot-diagram/ssot-
                        diagram.config.json)
  --out OUT             output HTML (default: <root>/ssot-diagram/ssot-
                        diagram.html)
  --component COMPONENT
                        scoped view: one component id (emits ssot-
                        diagram.<cid>.html)
  --title TITLE         artifact title (default: 'SSOT diagram')

rc=0
```

Six flags: `--model`, `--narratives`, `--config`, `--out`, `--component`, `--title`.

### 2. `python3 ssot-diagram/render.py` — bare, indexed repo → exit 0

```
model       = /Users/phatchenh/all-projects/vibe-coding-setup/codegraph-piggyback/ssot-diagram/diagram-model.json
narratives  = /Users/phatchenh/all-projects/vibe-coding-setup/codegraph-piggyback/ssot-diagram/narratives.json
config      = /Users/phatchenh/all-projects/vibe-coding-setup/codegraph-piggyback/ssot-diagram/ssot-diagram.config.json
out         = /Users/phatchenh/all-projects/vibe-coding-setup/codegraph-piggyback/ssot-diagram/ssot-diagram.html
title       = SSOT diagram
rc=0
```

Repo-root discovery via `di.find_db(Path.cwd())` → repo root → relative defaults resolved.

### 3. `python3 ssot-diagram/render.py --model /tmp/M --narratives /tmp/N --out /tmp/O` — explicit all three → exit 0 (A14 deviation)

Run from `/tmp` (no `.codegraph` anywhere above cwd):

```
model       = /tmp/M
narratives  = /tmp/N
config      = None
out         = /tmp/O
title       = SSOT diagram
rc=0
```

A14 deviation verified: all three flags explicit → discovery skipped → no die on absent DB.
`config` is `None` (not loaded) for the same reason.

### 4. `python3 ssot-diagram/render.py --component cmp-lib` — exit 0, scoped out path resolved

```
model       = /Users/phatchenh/all-projects/vibe-coding-setup/codegraph-piggyback/ssot-diagram/diagram-model.json
narratives  = /Users/phatchenh/all-projects/vibe-coding-setup/codegraph-piggyback/ssot-diagram/narratives.json
config      = /Users/phatchenh/all-projects/vibe-coding-setup/codegraph-piggyback/ssot-diagram/ssot-diagram.config.json
out         = /Users/phatchenh/all-projects/vibe-coding-setup/codegraph-piggyback/ssot-diagram/ssot-diagram.cmp-lib.html
title       = SSOT diagram
rc=0
```

`--component cmp-lib` resolved to `ssot-diagram.cmp-lib.html` per the
`ssot-diagram.<cid>.html` slug rule.

### 5. `python3 ssot-diagram/render.py nounneeded 2>&1; echo "rc=$?"` — unknown positional → exit 2

```
usage: render [-h] [--model MODEL] [--narratives NARRATIVES] [--config CONFIG]
              [--out OUT] [--component COMPONENT] [--title TITLE]
render: error: unrecognized arguments: nounneeded
rc=2
```

## Notes

- **Design deviation from §7 subparsers (intentional, matches Step-3 test criteria).**
  Plan Notes §7 shows a `required=True` subparser pattern (mirroring `graph_model.py`).
  But the plan's own Step-3 test criterion #2 requires "bare render.py ... + exit 0",
  and the prompt's verify list expects `--model M --narratives N --out O` (no verb) to
  also exit 0. With `required=True`, both would exit 2. To satisfy the test criteria
  AND the verify expectations, `build_parser` is flat (six flags directly on the top-
  level parser, no subparsers). The function signatures (`() -> argparse.ArgumentParser`,
  `(args) -> tuple[...]`, `(args) -> None`, `() -> None`) match §7 verbatim. `cmd_render`
  is dispatched via `args.fn(args)` per §7's `main`.
- `cmd_render` is the Step-3 shell: resolve paths → print summary to stderr (via
  `gm.info`) → exit 0. Steps 4-7 fill the body with load → join → escape → splice → save.
- `DEFAULT_OUT_REL = "ssot-diagram/ssot-diagram.html"` and `DEFAULT_TITLE = "SSOT
  diagram"` are defined in the header (Notes §1). The sentinels `SENTINEL_VM` and
  `SENTINEL_FONT` are also declared here but unused in Step 3 (Step 7 splices them).
- `_render_paths` honors the A14 deviation: root discovery runs ONLY if at least
  one of `--model`/`--narratives`/`--out` is absent. Verified by commands 2 (discovery
  runs) vs 3 (discovery skipped). `--config` is overridable without triggering
  discovery when the other three are explicit.

## Literal testCmd (Step-3 gate)

```
python3 ssot-diagram/render.py render --help
```

## Adjudicated deviation (orchestrator, 2026-07-10)

Worker shipped a flat parser (no subparser) to satisfy plan line 676 ("bare →
exit 0"). Owner adjudicated the plan's self-contradiction (line 676 vs line 682
+ §7 "subparser required=True"): **subparser required wins** (matches P4
narrate convention + line 682; line 676 rejected). Orchestrator reverted
`build_parser` to the §7 subparser form; bare/no-verb now exits 2. The five
Step-3 test criteria re-verified post-fix: `--help` lists 6 flags; bare/no-verb
=> exit 2; `render --model M --narratives N --out O.html` in a no-DB dir =>
exit 0 (A14 deviation); `render --component cmp-lib` resolves the
ssot-diagram.cmp-lib.html out path; `sqlite3.connect` absent; graph_model.py +
mkt_engine.model.json byte-unchanged. (The command outputs captured above in
sections 1/2 reflect the pre-fix flat parser; the post-fix re-verification
output is per the gate testCmd below.)

=== END REPORT ===