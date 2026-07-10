# Step 6 Implementation Report — _escape_viewmodel_json + _font_face_css

## Files changed
- `ssot-diagram/render.py` — added _escape_viewmodel_json + _font_face_css (verbatim
  from plan Implementer Notes §5) + `base64`/`json` imports.

## Verify (2026-07-10)
- Escaped payload (golden model + empty narratives, 240108 bytes): zero `<`,
  zero bytes >= 0x80. ensure_ascii=True escapes U+2028/2029 + all non-ASCII (A11).
  Output stable on re-escape (no `<` => the replace is a no-op on the output).
- _font_face_css: 3 @font-face rules, weights 400/500/700 fixed order, no `<` in
  emitted CSS, deterministic.
- Missing font asset (deleted DMSans-Bold.woff2) -> die 2 naming the asset.
- graph_model.py + mkt_engine.model.json byte-unchanged; pytest 105/3 (0 new).

## Literal testCmd (Step-6 gate)
```
python3 -c "import sys;sys.path.insert(0,'ssot-diagram');import render as r,graph_model as gm;from pathlib import Path;m=gm._load_model(Path('ssot-diagram/testdata/mkt_engine.model.json'));e=r._escape_viewmodel_json(r.build_viewmodel(m,{}));print('<' not in e, len(e))"
```

=== END REPORT ===
