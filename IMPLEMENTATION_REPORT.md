# Step 4 Implementation Report — render.py INPUT-LOAD (the L7 split)

`cmd_render` fleshed out with the load half: model via `gm._load_model`, config via
`gm._load_narrate_config`, narratives via `gm._load_narratives`, template read from
the script's own dir. All four loaded inputs held forward for Step 5's join.

## Files changed
- `ssot-diagram/render.py` — `_render_paths` config-default fix (A14 explicit
  branch now resolves config to cwd-relative `DEFAULT_CONFIG_REL` instead of
  `None`; `gm._load_narrate_config` is permissive to absent files so it never
  dies) + `cmd_render` load-half body.

## Plan-verify block (Step 4)
touch: ssot-diagram/graph_model.py::_load_model
touch: ssot-diagram/graph_model.py::_load_narratives
touch: ssot-diagram/graph_model.py::_load_narrate_config
tier:  B
qualifiers: byte-unchanged ssot-diagram/graph_model.py ; byte-unchanged ssot-diagram/testdata/mkt_engine.model.json ; grep-absent "sqlite3.connect" ssot-diagram/render.py

(The touch: functions are gm loaders IMPORTED read-only, not edited; verified
at graph_model.py:831/946/809, byte-identical.)

## L7 failure modes (verified 2026-07-10)
- [x] Missing model → exit 2 (rc=2, no output).
- [x] Missing narratives file → renders + note "no narratives yet — run
      graph_model.py narrate" + `!` warn + exit 0 (rc=0).
- [x] Malformed narratives file → exit 2 (rc=2).
- [x] Existing empty `{}` narratives file → renders, NO note, no warn, exit 0
      (note-count=0, rc=0).
- [x] Missing template → exit 2 (rc=2).
- [x] A14 deviation intact: explicit `--model/--narratives/--out` from a no-
      `.codegraph` dir with a REAL model → exit 0, no discovery, no die.
- [x] `sqlite3.connect` absent in render.py; graph_model.py + golden byte-unchanged.

Why absent-vs-empty distinguishes: `gm._load_narratives` returns `{}` for BOTH
absent and empty, so `cmd_render` checks `narratives_path.is_file()` itself —
absent sets the note + warns, curated empty `{}` gets neither.

## Literal testCmd (Step-4 gate)

```
python3 ssot-diagram/render.py render --model ssot-diagram/testdata/mkt_engine.model.json --narratives /tmp/empty.json --out /tmp/O.html
```

=== END REPORT ===
