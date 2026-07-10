#!/usr/bin/env python3
"""render — render diagram-model + narratives into a self-contained HTML file.

P5 of the ssot-diagram phase. Reads diagram-model.json + the curated narratives
sidecar + the ssot-diagram config, joins them into a view-model whose trust
verdicts are computed in Python at render time, and splices the result into a
repo-owned HTML shell (CSS + dumb painter). The output is a single
browser-openable file that never touches the network.

Command:
  render           build ssot-diagram/ssot-diagram.html (or a --component scope)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Sibling import seam — mirror graph_model.py:26-28 + add `import graph_model as gm`.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import decision_index as di  # noqa: E402
import graph_model as gm     # noqa: E402
die = gm.die                 # di.die alias, exit 2
warn, info, ok = gm.warn, gm.info, gm.ok
DEFAULT_OUTPUT_REL = gm.DEFAULT_OUTPUT_REL   # "ssot-diagram/diagram-model.json"
DEFAULT_CONFIG_REL = gm.DEFAULT_CONFIG_REL   # "ssot-diagram/ssot-diagram.config.json"
SENTINEL_VM = "/*<SSOT:VIEWMODEL_JSON>*/null"    # template's replace target (incl "null")
SENTINEL_FONT = "/*<SSOT:FONT_FACE>*/"          # inside <style>
DEFAULT_OUT_REL = "ssot-diagram/ssot-diagram.html"
DEFAULT_TITLE = "SSOT diagram"


def _render_paths(args) -> tuple[Path, Path | None, Path | None, Path, str]:
    """Resolve (model, narratives, config, out, title) for the render command.

    A14 deviation: root discovery (`di.find_db` + `di.repo_root_for`) runs ONLY
    if at least one of --model/--narratives/--out is absent; when all three are
    explicit, NO discovery + NO die on absent DB (Decision 4: a defaulted
    --narratives STILL triggers discovery since `narratives_rel` is relative).
    --config is overridable without triggering discovery (when the other three
    are explicit).
    """
    need_discovery = not (args.model and args.narratives and args.out)
    if need_discovery:
        db_path = di.find_db(Path.cwd())
        if not db_path:
            die("no .codegraph/codegraph.db found (run `codegraph init` first)")
        root = di.repo_root_for(db_path)
        config = (
            Path(args.config) if getattr(args, "config", None)
            else root / DEFAULT_CONFIG_REL
        )
        _, narratives_rel = gm._load_narrate_config(config)
        model = Path(args.model) if args.model else root / DEFAULT_OUTPUT_REL
        narratives = (
            Path(args.narratives) if args.narratives else root / narratives_rel
        )
    else:
        model = Path(args.model)
        narratives = Path(args.narratives) if args.narratives else None
        config = Path(args.config) if getattr(args, "config", None) else None
        root = None

    # Out path: --out beats --component beats default.
    if getattr(args, "out", None):
        out = Path(args.out)
    elif getattr(args, "component", None):
        slug = f"ssot-diagram/ssot-diagram.{args.component}.html"
        out = root / slug if root is not None else Path(slug)
    else:
        out = root / DEFAULT_OUT_REL if root is not None else Path(DEFAULT_OUT_REL)

    title = getattr(args, "title", None) or DEFAULT_TITLE
    return model, narratives, config, out, title


def cmd_render(args) -> None:
    """render verb — Step-3 shell: resolve paths + print summary + exit 0.

    Steps 4-7 fill this body with load → join → escape → splice → write.
    """
    model, narratives, config, out, title = _render_paths(args)
    # Placeholder summary — Steps 4-7 replace this with the actual load/join/splice.
    gm.info(f"model       = {model}")
    gm.info(f"narratives  = {narratives}")
    gm.info(f"config      = {config}")
    gm.info(f"out         = {out}")
    gm.info(f"title       = {title}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="render",
        description="render diagram-model + narratives into a self-contained HTML file",
    )
    # One verb, six flags. Subparser required=True so bare `render.py` (no verb)
    # exits 2 (mirrors P4 narrate's pattern; §7; adjudicated 2026-07-10 vs the
    # plan's line-676 "bare -> exit 0", which self-contradicts line 682's
    # "no verb -> exit 2" — 682 + §7 win).
    sub = p.add_subparsers(dest="render_cmd", required=True)
    pr = sub.add_parser("render", help="render the HTML artifact")
    pr.add_argument("--model", help=f"diagram-model.json (default: <root>/{DEFAULT_OUTPUT_REL})")
    pr.add_argument("--narratives", help="narratives.json (default: config narratives_path)")
    pr.add_argument("--config", help=f"config (default: <root>/{DEFAULT_CONFIG_REL})")
    pr.add_argument("--out", help="output HTML (default: <root>/ssot-diagram/ssot-diagram.html)")
    pr.add_argument("--component", help="scoped view: one component id (emits ssot-diagram.<cid>.html)")
    pr.add_argument("--title", help=f"artifact title (default: {DEFAULT_TITLE!r})")
    pr.set_defaults(fn=cmd_render)
    return p


def main() -> None:
    args = build_parser().parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()