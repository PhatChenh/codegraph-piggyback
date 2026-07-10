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
        # --config overridable without triggering discovery (A14). When absent,
        # fall back to a cwd-relative DEFAULT_CONFIG_REL: gm._load_narrate_config
        # is permissive to missing files (returns DEFAULT_NARRATIVES_REL), so this
        # never dies — it just reads narratives_rel from the default if present.
        config = Path(args.config) if getattr(args, "config", None) else Path(DEFAULT_CONFIG_REL)
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
    """render verb — resolve paths → load inputs → (Step 5 joins, 6 escapes, 7 splices/writes).

    Step 4 fills the LOAD half only. The L7 split: every failure mode lands exactly
    where P4 pinned it — absent narratives is a note (exit 0), everything malformed
    is a loud exit 2. Narratives load through P4's own loaders (never re-written);
    because `gm._load_narratives` returns `{}` for BOTH absent and empty, render
    checks `is_file()` ITSELF to tell the absent case (note + `!` warn) from the
    curated empty-`{}` case (no note).
    """
    model_path, narratives_path, config_path, out, title = _render_paths(args)

    # 1. Model — absent/malformed -> die 2 (owner must run `extract` first).
    model = gm._load_model(model_path)

    # 3. Config — permissive; threshold ignored, only `narratives_rel` is used.
    _, narratives_rel = gm._load_narrate_config(config_path)

    # 2. Narratives — the absent-vs-malformed split is L7's entire contract.
    note = None
    if narratives_path is not None and narratives_path.is_file():
        narratives = gm._load_narratives(narratives_path)   # malformed -> die 2; {} -> no note
    elif narratives_path is not None:
        # Absent: load nothing, set the note + warn, continue to exit 0.
        narratives = {}
        note = "no narratives yet — run graph_model.py narrate"
        gm.warn(f"{narratives_path} not found — {note}")
    else:
        narratives = {}   # all-explicit path set with no narratives file (A14 no-DB branch)

    # 4. Template — ships WITH the tool (script's own dir), never the target repo.
    template_path = Path(__file__).resolve().parent / "render_template.html"
    try:
        template_text = template_path.read_text()
    except FileNotFoundError:
        die(f"render_template.html not found beside {template_path}")
    except OSError as e:
        die(f"render_template.html unreadable: {e}")

    # 5. Loaded inputs held for Step 5's join (build_viewmodel takes these forward).
    gm.info(f"model       = {model_path} ({len(model.get('components', []))} components)")
    gm.info(f"narratives  = {narratives_path} ({len(narratives)} entries{' [absent — ' + note + ']' if note else ''})")
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