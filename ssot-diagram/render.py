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
import base64
import json
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


# ── escape + font (Step 6; axis 2A, F3 invariant — copy verbatim) ────────────
# _escape_viewmodel_json: the payload between <script> tags can never break out.
# ensure_ascii=True escapes U+2028/U+2029 + all non-ASCII (A11); the sole
# remaining dangerous ASCII char '<' becomes < — simultaneously valid JSON +
# valid JS, so </script>, <!--, and any HTML-ish payload in narrative text or a
# --title is inert, AND the <'-bearing sentinels are collision-proof (the
# invariant lives in the '<' char, not obscurity — the escaped payload has zero
# '<', so it can never contain its own sentinel).
def _escape_viewmodel_json(viewmodel: dict) -> str:
    return (json.dumps(viewmodel, sort_keys=True, ensure_ascii=True,
                       separators=(",", ":")).replace("<", "\\u003c"))


# _font_face_css: the three vendored woff2 as base64 @font-face rules, fixed
# file order (weights 400/500/700), deterministic. A missing asset -> die 2
# (fail-loud beats silent system-font fallback masking the zero-network rule).
# Emitted CSS contains no '<' and no sentinel.
def _font_face_css(assets_dir: Path) -> str:
    rules = []
    for weight, fname in [(400, "DMSans-Regular.woff2"), (500, "DMSans-Medium.woff2"),
                          (700, "DMSans-Bold.woff2")]:
        p = assets_dir / fname
        if not p.is_file():
            die(f"missing font asset: {p}")   # fail-loud, never silent system-font fallback
        b64 = base64.b64encode(p.read_bytes()).decode("ascii")
        rules.append(f'@font-face{{font-family:"DM Sans";font-weight:{weight};'
                     f'font-style:normal;src:url(data:font/woff2;base64,{b64}) format("woff2")}}')
    return "\n".join(rules)


# ── build_viewmodel: the trust join (L2 heart) ────────────────────────────────
# Status vocab (A17 guard) — derived statuses are pure functions of (stored
# narrative, current signature) via gm._derive_status. Anything outside this
# set is a model/LLM bug, never a silent default.
_VALID_STATUSES = {"approved", "proposed", "stale", "none", "unnarratable", "orphaned"}

# Per-node PROSE chip (addendum §2): (chip_text, badge) keyed by status.
# None chip = painter omits the chip; narratable approved/none look unchanged.
_PROSE_CHIP = {
    "approved":    (None,                         None),
    "proposed":    ("PROPOSED — UNREVIEWED",      "action"),
    "stale":       ("NEEDS REVIEW — CODE CHANGED", "danger"),
    "unnarratable": ("UNNARRATABLE",               "disabled"),
    "none":        (None,                         None),
    "orphaned":    (None,                         None),  # never enters payload
}

# Decision chip (addendum §2 table): (extra label, badge) keyed by decision status.
_DECISION_CHIP = {
    "FRESH":      (None,                          "positive"),
    "STALE":      ("NEEDS REVIEW",                "danger"),
    "ORPHANED":   ("NEEDS REVIEW",                "danger"),
    "AMBIGUOUS":  ("AMBIGUOUS — anchor unclear",  "danger"),
    "superseded": ("SUPERSEDED",                  "disabled"),
}

# Icon key (Decision 9, precomputed in Python so the JS painter is a dumb mapper).
_ICON_FOR_KIND = {
    "component": "SERVICE",
    "file":      "default",
    "micro":     "default",
    "function":  "ACTION",
    "method":    "ACTION",
    "nano":      "ACTION",
}

# Kind display label for the badge strip (level channel; trust lives in chips).
_KIND_LABEL = {
    "component": "COMPONENT",
    "file":      "FILE",
    "micro":     "FILE",
    "function":  "FUNCTION",
    "method":    "FUNCTION",
    "nano":      "FUNCTION",
}


def _prose_chip_for(status: str) -> dict | None:
    text, badge = _PROSE_CHIP.get(status, (None, None))
    if text is None:
        return None
    return {"id": f"prose:{status}", "name": text, "doc": None,
            "status": status, "badge": badge, "label": None}


def _decision_chip_for(decision: dict) -> dict:
    status = decision.get("status", "AMBIGUOUS")
    label, badge = _DECISION_CHIP.get(status, (None, "neutral"))
    return {"id": decision.get("id", ""), "name": decision.get("name", ""),
            "doc": decision.get("doc"), "status": status,
            "badge": badge, "label": label}


def _tooltip_for(node: dict, chips: list, prose: dict, sample_callers: list | None) -> dict:
    """Precomputed tooltip block (F2, addendum §2 last bullet).

    Order: name → kind label → chip text(s) first when present → joined prose
    → capped sample_callers (3). Inserted via setText in the painter; the
    archived data-title/data-desc attribute pattern is NOT carried over.
    """
    name = node.get("name", "")
    kind_label = _KIND_LABEL.get(node.get("kind"), (node.get("kind") or "").upper())
    lines: list = [name, kind_label]
    if chips:
        chip_texts = []
        for c in chips:
            if c.get("label"):
                chip_texts.append(f"{c['name']} — {c['label']}")
            else:
                chip_texts.append(c["name"])
        lines.append(" · ".join(chip_texts))
    lines.append(prose["text"])
    if sample_callers:
        for s in sample_callers[:3]:
            lines.append(f"{s.get('file', '')}:{s.get('line', '')}")
    return {"name": name, "kind_label": kind_label, "lines": lines}


def _walk_node(node: dict, narratives: dict, decision_by_id: dict) -> dict | None:
    """Recursive join: collapsed → passthrough; else trust join + chips + tooltip
    + children. Emits the joined node at EACH tree position (Decision 8 — A15:
    duplicated nano ids at 2 positions with identical sigs paint identically).

    Branch order for collapsed is BEFORE _fallback_text (it raises on
    collapsed/decision, A2/A12) and BEFORE _derive_status (no point).
    """
    kind = node.get("kind")
    if kind == "collapsed":
        # Passthrough: {id, kind, name, signature, collapsed_count} only.
        # NO _fallback_text (A2) and NO decisions/edges/path passthrough.
        return {
            "id": node["id"],
            "kind": "collapsed",
            "name": node.get("name", ""),
            "signature": node.get("signature", ""),
            "collapsed_count": node.get("collapsed_count", 0),
        }

    nid = node["id"]
    stored = narratives.get(nid)
    sig = node.get("signature")
    status = gm._derive_status(stored, sig)
    if status not in _VALID_STATUSES:
        die(f"derive_status: unknown status {status!r} for {nid!r} (A17 guard)")
    if status == "orphaned":
        # gm._derive_status returns 'orphaned' only when current_sig is None
        # (vanished node) — vanishing can't happen for a node that IS in the
        # model, so this branch is defensive: drop rather than render.
        return None

    if status in ("approved", "proposed", "stale"):
        text = (stored or {}).get("text", "")
        source = "narrative"
    else:  # "none" or "unnarratable" — fallback path (A1 branch order, cmp-dist visible)
        text = gm._fallback_text(node)
        source = "fallback"

    prose = {"text": text, "status": status, "source": source}

    # Sample callers for the tooltip — pull from the first edge that has them
    # (informational only; not used by the trust join).
    sample_callers: list | None = None
    for e in node.get("edges", []) or []:
        if e.get("sample_callers"):
            sample_callers = e["sample_callers"]
            break

    # Chips: 0 or 1 prose chip + N decision chips (in model order).
    chips: list = []
    prose_chip = _prose_chip_for(status)
    if prose_chip is not None:
        chips.append(prose_chip)
    for did in node.get("decisions", []) or []:
        if did not in decision_by_id:
            die(f"decision {did!r} referenced by node {nid!r} not in "
                f"model['decisions'] (self-inconsistent model)")
        chips.append(_decision_chip_for(decision_by_id[did]))

    out = {
        "id": nid,
        "kind": kind,
        "name": node.get("name", ""),
        "path": node.get("path", ""),
        "signature": node.get("signature", ""),
        "icon": _ICON_FOR_KIND.get(kind, "default"),
        "kind_label": _KIND_LABEL.get(kind, (kind or "").upper()),
        "prose": prose,
        "chips": chips,
        "tooltip": _tooltip_for(node, chips, prose, sample_callers=sample_callers),
    }

    # Children — preserve model order; emit at each tree position.
    children_out: list = []
    for child in node.get("children", []) or []:
        joined_child = _walk_node(child, narratives, decision_by_id)
        if joined_child is not None:
            children_out.append(joined_child)
    if children_out:
        out["children"] = children_out
    return out


def _build_view_edges_and_stubs(
    source_nodes: list, view_level: str, view_id: str | None,
    id_to_comp: dict, id_to_micro: dict, is_full_artifact: bool,
) -> tuple[list, list]:
    """Per-view edge + stub precompute (A5 id→owning maps used here).

    view_level: "top" | "component" | "micro"
      - top: endpoints = component ids. Decision 7: omit edges whose BOTH
        endpoints resolve to the same component (self-edges belong in focus views).
      - component: endpoints = micro ids of view_id. Cross-component targets
        → OTHER COMPONENT stub.
      - micro: endpoints = nano ids of view_id. Sibling micro of the same
        component → OTHER FILE stub (Decision 1). Cross-component → OTHER COMPONENT.

    stub_nav: True iff is_full_artifact (full → navigable; --component → inert,
    matching the OQ-P5-1 owner ruling for OTHER COMPONENT and the Decision 1
    owner-ratified extension to OTHER FILE).
    """
    view_node_ids = {n["id"] for n in source_nodes}

    def resolve_target(tgt_id: str):
        if tgt_id in view_node_ids:
            return ("in_view", tgt_id)
        tgt_comp = id_to_comp.get(tgt_id)
        if tgt_comp is None:
            return ("unknown", None)
        if view_level == "top":
            return ("stub", ("component", tgt_comp))
        if view_level == "component":
            if tgt_comp == view_id:
                # In-component target — should already be in view if it's a micro
                # we know about; if not (rare), resolve to its micro as a stub.
                tgt_micro = id_to_micro.get(tgt_id, tgt_id)
                if tgt_micro in view_node_ids:
                    return ("in_view", tgt_micro)
                return ("unknown", None)
            return ("stub", ("component", tgt_comp))
        # micro
        if tgt_comp != view_id:
            return ("stub", ("component", tgt_comp))
        tgt_micro = id_to_micro.get(tgt_id)
        if tgt_micro is None or tgt_micro == view_id:
            return ("unknown", None)
        return ("stub", ("file", tgt_micro))

    edge_counts: dict = {}   # (from_id, to_id, kind) -> total count
    stub_keys: dict = {}     # (stub_kind, owner_id) -> True

    for node in source_nodes:
        src_id = node["id"]
        for edge in node.get("edges", []) or []:
            kind = edge.get("kind", "references")
            count = edge.get("count", 1)
            tgt = edge.get("target_id")
            res_kind, payload = resolve_target(tgt)
            if res_kind == "in_view":
                key = (src_id, payload, kind)
                edge_counts[key] = edge_counts.get(key, 0) + count
            elif res_kind == "stub":
                stub_kind, owner_id = payload
                stub_keys[(stub_kind, owner_id)] = True

    # Top view: omit same-component self-edges (Decision 7).
    view_edges: list = []
    for (from_id, to_id, kind), count in sorted(edge_counts.items()):
        if view_level == "top" and id_to_comp.get(from_id) == id_to_comp.get(to_id):
            continue
        view_edges.append({
            "from": from_id, "to": to_id, "kind": kind,
            "label": f"{kind} ×{count}",
        })

    stubs: list = []
    for (stub_kind, owner_id) in sorted(stub_keys):
        stubs.append({
            "owner_id": owner_id,
            "owner_kind": stub_kind,
            "owner_name": "",  # _fill_stub_names fills from comp/micro maps
            "stub": True,
            "stub_nav": is_full_artifact,
            "stub_label": "OTHER FILE" if stub_kind == "file" else "OTHER COMPONENT",
        })
    return view_edges, stubs


def _fill_stub_names(stubs: list, comp_by_id: dict, micro_by_id: dict) -> None:
    for s in stubs:
        if s["owner_kind"] == "component":
            comp = comp_by_id.get(s["owner_id"])
            s["owner_name"] = (comp or {}).get("name", s["owner_id"])
        elif s["owner_kind"] == "file":
            micro = micro_by_id.get(s["owner_id"])
            s["owner_name"] = (micro or {}).get("name", s["owner_id"])


def _collect_subtree_dec_names(node: dict, into: set) -> None:
    for c in node.get("chips", []) or []:
        if (c.get("id") or "").startswith("prose:"):
            continue
        into.add(c.get("name", ""))
    for ch in node.get("children", []) or []:
        if ch.get("kind") != "collapsed":
            _collect_subtree_dec_names(ch, into)


def _build_legend(joined_components: list, top_view_edges: list) -> dict:
    """Legend block (artifact-scope, what's present). The painter draws verbatim.

    node_types  : distinct (kind_label, icon) pairs in the payload
    edge_kinds  : distinct edge kinds in the top view
    trust_chips : distinct chip (name, label, badge) triples in the payload
    """
    node_types: set = set()
    edge_kinds: set = set()
    trust_chips: set = set()

    def walk_for_legend(node: dict) -> None:
        if node.get("kind") == "collapsed":
            return
        node_types.add((node.get("kind_label", ""), node.get("icon", "default")))
        for c in node.get("chips", []) or []:
            trust_chips.add((c.get("name", ""), c.get("label") or "", c.get("badge") or "neutral"))
        for ch in node.get("children", []) or []:
            walk_for_legend(ch)

    for c in joined_components:
        walk_for_legend(c)
    for e in top_view_edges:
        edge_kinds.add(e.get("kind", ""))

    return {
        "node_types": sorted(
            ({"kind_label": k, "icon": ic} for (k, ic) in node_types),
            key=lambda d: (d["kind_label"], d["icon"]),
        ),
        "edge_kinds": sorted(edge_kinds),
        "trust_chips": sorted(
            ({"name": n, "label": l, "badge": b} for (n, l, b) in trust_chips),
            key=lambda d: (d["name"], d["label"], d["badge"]),
        ),
    }


def build_viewmodel(
    model: dict, narratives: dict, *,
    component: str | None = None, title: str | None = None,
) -> dict:
    """The trust join (L2 heart) — pure function over model + narratives.

    For every node, derive status via gm._derive_status (IMPORTED, never
    copied — A1 branch order is load-bearing; A17 guard raises on unknown
    vocab). Apply the L3 matrix: approved/proposed/stale → stored prose;
    none/unnarratable → gm._fallback_text (A1 empty-sig caught FIRST, so
    cmp-dist/cmp-invoice-cost render fallback DESPITE any stored entry).
    Per-view edges + stubs precomputed so the painter is dumb. Duplicated
    nano ids emit at EACH tree position (Decision 8 — A15). Orphaned
    narrative entries are counted to stderr and never enter the payload.

    --component scopes the subtree; the breadcrumb root becomes the
    component itself; all stubs are inert. Unknown cid → die 2 listing known.
    """
    # 1. id→owning-component + id→owning-micro maps (A5) — one walk, mirrors
    #    the shape of gm._build_sig_index (graph_model.py:842-865) but
    #    additionally records the comp/micro dicts for stub name lookup.
    id_to_comp: dict[str, str] = {}
    id_to_micro: dict[str, str | None] = {}
    comp_by_id: dict[str, dict] = {}
    micro_by_id: dict[str, dict] = {}
    for comp in model.get("components", []) or []:
        cid = comp["id"]
        comp_by_id[cid] = comp
        id_to_comp[cid] = cid
        for micro in comp.get("children", []) or []:
            mid = micro["id"]
            micro_by_id[mid] = micro
            id_to_comp[mid] = cid
            id_to_micro[mid] = mid
            for nano in micro.get("children", []) or []:
                if nano.get("kind") == "collapsed":
                    continue
                id_to_comp[nano["id"]] = cid
                id_to_micro[nano["id"]] = mid

    # 2. Decisions list → id-keyed dict (A4: top-level decisions is a LIST).
    decision_by_id: dict[str, dict] = {}
    for d in model.get("decisions", []) or []:
        if "id" in d:
            decision_by_id[d["id"]] = d

    # 3. Validate --component (unknown cid → die 2 listing known; addendum §4).
    if component is not None and component not in comp_by_id:
        die(f"unknown --component {component!r}; known: {sorted(comp_by_id)}")

    # 4. Scope handling.
    raw_components = list(model.get("components", []) or [])
    if component is not None:
        raw_components = [c for c in raw_components if c["id"] == component]
    is_full_artifact = component is None

    # 5. Walk + join (tree copy; preserves model order; duplicates emit at
    #    each position per Decision 8).
    joined_components: list = []
    for c in raw_components:
        joined_c = _walk_node(c, narratives, decision_by_id)
        if joined_c is not None:
            joined_components.append(joined_c)

    # 6. Per-view edges + stubs (top + each component + each micro).
    top_view_edges, top_stubs = _build_view_edges_and_stubs(
        raw_components, "top", None, id_to_comp, id_to_micro, is_full_artifact,
    )
    _fill_stub_names(top_stubs, comp_by_id, micro_by_id)

    for joined_c, raw_c in zip(joined_components, raw_components):
        joined_c["view_edges"] = []
        joined_c["stubs"] = []
        if joined_c.get("kind") == "collapsed":
            continue
        raw_micros = [m for m in raw_c.get("children", []) or [] if m.get("kind") != "collapsed"]
        comp_edges, comp_stubs = _build_view_edges_and_stubs(
            raw_micros, "component", raw_c["id"], id_to_comp, id_to_micro, is_full_artifact,
        )
        _fill_stub_names(comp_stubs, comp_by_id, micro_by_id)
        joined_c["view_edges"] = comp_edges
        joined_c["stubs"] = comp_stubs
        for joined_m, raw_m in zip(joined_c.get("children", []) or [], raw_micros):
            joined_m["view_edges"] = []
            joined_m["stubs"] = []
            if joined_m.get("kind") == "collapsed":
                continue
            raw_nanos = [n for n in raw_m.get("children", []) or [] if n.get("kind") != "collapsed"]
            micro_edges, micro_stubs = _build_view_edges_and_stubs(
                raw_nanos, "micro", raw_m["id"], id_to_comp, id_to_micro, is_full_artifact,
            )
            _fill_stub_names(micro_stubs, comp_by_id, micro_by_id)
            joined_m["view_edges"] = micro_edges
            joined_m["stubs"] = micro_stubs

    # 7. Orphaned narrative entries (id in narratives but not in model) —
    #    gm.info to stderr; never enter the payload (A1 'orphaned' branch is
    #    for vanished current_sig; an unknown-from-narratives id is a different
    #    failure mode and the painter must not see it).
    model_ids: set = set(id_to_comp) | set(micro_by_id)
    for mid in micro_by_id:
        m = micro_by_id[mid]
        for n in m.get("children", []) or []:
            if n.get("kind") != "collapsed":
                model_ids.add(n["id"])
    orphaned = [nid for nid in narratives if nid not in model_ids]
    if orphaned:
        gm.info(f"build_viewmodel: {len(orphaned)} orphaned narrative entries dropped")

    # 8. Subtitle — F5: M = UNIQUE ADR names (decision "name" field, not "id").
    #    Real golden: 11 decisions with 8 unique names (ADR-0001..ADR-0008).
    unique_dec_names = len({d.get("name", "") for d in (model.get("decisions", []) or [])})
    if component is not None:
        sub = joined_components[0] if joined_components else {}
        n_files = sum(1 for ch in sub.get("children", []) or [] if ch.get("kind") != "collapsed")
        scoped_dec_names: set = set()
        _collect_subtree_dec_names(sub, scoped_dec_names)
        subtitle = f"{n_files} files · {len(scoped_dec_names)} decisions"
    else:
        subtitle = f"{len(joined_components)} components · {unique_dec_names} decisions"

    # 9. Legend + assembly. note is filled in by cmd_render from the L7 split
    #    (build_viewmodel does not know whether narratives.json was absent vs
    #    empty — that distinction lives at the loader).
    legend = _build_legend(joined_components, top_view_edges)

    return {
        "title": title if title is not None else DEFAULT_TITLE,
        "subtitle": subtitle,
        "note": None,
        "scope": "full" if component is None else component,
        "components": joined_components,
        "view_edges": top_view_edges,
        "legend": legend,
    }


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