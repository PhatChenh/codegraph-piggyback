# Step 7 Implementation Report — _render_html splice + _save_text + cmd_render assembly

## Files changed
- `ssot-diagram/render.py` — added _render_html + _save_text (verbatim from plan
  §6); wired cmd_render end-to-end (resolve → load → build_viewmodel →
  _font_face_css + _escape_viewmodel_json → _render_html → _save_text → ok); os
  import; removed the dead `_, narratives_rel = gm._load_narrate_config(...)`
  (narratives_rel was unused after Step 5; CLEAN-DEAD-001). Passes component +
  title to build_viewmodel; lifts the L7 `note` from the loader boundary into the
  view-model.

## Verify (2026-07-10) — the renderer is now functionally complete
- E2E: `render render --model golden --out /tmp/x.html` → writes 313091-byte
  self-contained HTML, exit 0, "10 components".
- Splice: both sentinels pre-counted == 1 (no drift); zero sentinels survive
  splice (grep SSOT = 0). `const MODEL = {...}` (object literal, not null);
  `<` in the view-model is escaped to < everywhere (json.dumps ensure_ascii
  + replace). No </script> breakout.
- Self-contained: 3 base64 data:font/woff2 @font-face rules embedded; ZERO
  `<link>` / @import / external src (opens offline, zero network).
- Byte-deterministic: two renders → identical sha256 e25d74cb….
- --component cmp-lib scoped render → 183423-byte HTML, exit 0.
- Narratives fixture render → UNNARRATABLE chip present (A1 case via the join).
- L7 regression intact: missing template → exit 2; absent narratives → note in
  payload + exit 0; missing/malformed model → exit 2; empty {} → no note exit 0.
- pytest 105/3 (0 new); graph_model.py + golden byte-unchanged.

## Literal testCmd (Step-7 gate)
```
python3 ssot-diagram/render.py render --model ssot-diagram/testdata/mkt_engine.model.json --out /tmp/p5_step7.html
```

=== END REPORT ===
