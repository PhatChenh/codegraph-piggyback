#!/usr/bin/env python3
"""graph_model — deterministic diagram-model.json extractor.

Builds a three-level model (component -> micro -> nano) from the codegraph DB
plus the curated decision index, plus a config that maps glob patterns to
component names. The output is a byte-deterministic diagram-model.json
consumed by P5 (renderer) and plan-visualizer.

Commands:
  extract           build diagram-model.json from DB + index + config
  bootstrap-config  seed a ssot-diagram.config.json from top-level dirs
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import sqlite3
import sys
from pathlib import Path

# Sibling import of P1 — same seam as decision_hook.py:22-23
sys.path.insert(0, str(Path(__file__).resolve().parent))
import decision_index as di  # noqa: E402

DEFAULT_CONFIG_REL = "ssot-diagram/ssot-diagram.config.json"
DEFAULT_OUTPUT_REL = "ssot-diagram/diagram-model.json"
DEFAULT_NANO_CAP = 8
MODEL_VERSION = 1

FRESH, STALE, ORPHANED, AMBIGUOUS = di.FRESH, di.STALE, di.ORPHANED, di.AMBIGUOUS

# Worst-to-best ordering for decision status reduce (lower index = worse)
_WORST_ORDER = {ORPHANED: 0, STALE: 1, AMBIGUOUS: 2, "superseded": 3, FRESH: 4}


# ── helpers ─────────────────────────────────────────────────────────────────────

def info(msg: str) -> None:
    print(msg, file=sys.stderr)


def warn(msg: str) -> None:
    print(f"! {msg}", file=sys.stderr)


def ok(msg: str) -> None:
    print(f"\u2713 {msg}", file=sys.stderr)


# Reuse P1's die (exit 2 per E1 carry-forward). No own die().
die = di.die


# ── sha256 helpers ───────────────────────────────────────────────────────────────

def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


def _sorted_sha256(parts: list[str]) -> str:
    """SHA256 of concatenated parts sorted (for deterministic member aggregation)."""
    parts = sorted(parts)
    return _sha256("".join(parts))


# ── config load + validate (Step 3) ─────────────────────────────────────────────

def load_config(path: Path) -> dict:
    """Load and validate ssot-diagram.config.json.

    Schema:
    - version: int (required, must be 1)
    - components: list[dict] with id, name, glob (required)
    - default_component: str (required, must be an id in components)
    - nano_cap: int (optional, default 8)
    """
    if not path.is_file():
        die(f"{path} not found — run `bootstrap-config` first (or point --config at an existing config)")
    try:
        cfg = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        die(f"{path}: invalid JSON: {e}")

    if not isinstance(cfg, dict):
        die(f"{path}: top-level must be a JSON object")

    if not isinstance(cfg.get("version"), int):
        die(f"{path}: 'version' must be an integer")

    comps = cfg.get("components")
    if not isinstance(comps, list) or not comps:
        die(f"{path}: 'components' must be a non-empty list")

    seen_ids = set()
    for c in comps:
        if not isinstance(c, dict):
            die(f"{path}: each component must be a JSON object")
        cid = c.get("id")
        if not isinstance(cid, str) or not cid:
            die(f"{path}: each component must have a non-empty string 'id'")
        if cid in seen_ids:
            die(f"{path}: duplicate component id {cid!r}")
        seen_ids.add(cid)
        for k in ("name", "glob"):
            if not isinstance(c.get(k), str) or not c[k]:
                die(f"{path}: component {cid!r} missing non-empty '{k}'")

    default_component = cfg.get("default_component")
    if not isinstance(default_component, str) or default_component not in seen_ids:
        die(f"{path}: 'default_component' must be one of the component ids")

    nano_cap = cfg.get("nano_cap", DEFAULT_NANO_CAP)
    if not isinstance(nano_cap, int) or nano_cap < 1:
        die(f"{path}: 'nano_cap' must be a positive integer")

    return cfg


# ── bootstrap-config (Step 13) ──────────────────────────────────────────────────

def bootstrap_config(db_path: Path, out: Path, force: bool) -> None:
    """Seed a ssot-diagram.config.json from top-level directories in the repo."""
    if out.exists() and not force:
        die(f"{out} exists — refusing to overwrite a curated config. Pass --force to reseed.")

    root = di.repo_root_for(db_path)
    skip = {".codegraph", "node_modules", ".git", ".claude"}
    dirs = sorted(d for d in root.iterdir() if d.is_dir() and d.name not in skip and not d.name.startswith("."))
    components = []
    for d in dirs:
        slug = d.name.lower().replace("_", "-").replace(" ", "-")
        components.append({
            "id": f"cmp-{slug}",
            "name": d.name,
            "glob": f"{d.name}/**",
        })
    components.append({
        "id": "cmp-misc",
        "name": "Other",
        "glob": "**",
    })

    cfg = {
        "version": MODEL_VERSION,
        "components": components,
        "default_component": "cmp-misc",
        "nano_cap": DEFAULT_NANO_CAP,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(cfg, indent=2) + "\n")
    os.replace(tmp, out)
    ok(f"wrote {out} ({len(components)} component(s), nano_cap={DEFAULT_NANO_CAP})")


# ── schema guard (Step 4, R4 carry-forward #5) ──────────────────────────────────

def _verify_model_schema(con: sqlite3.Connection, path: Path) -> None:
    """Extend P1's verify_schema with P3's extra columns."""
    di.verify_schema(con, path)

    node_cols = {r[1] for r in con.execute("PRAGMA table_info(nodes)")}
    edge_cols = {r[1] for r in con.execute("PRAGMA table_info(edges)")}

    need_nodes_extra = {"kind", "id", "docstring", "is_exported", "signature"}
    need_edges = {"source", "target", "kind", "line"}
    if not need_nodes_extra <= node_cols:
        missing = need_nodes_extra - node_cols
        die(f"{path} schema missing nodes columns: {missing} (codegraph version drift?)")
    if not need_edges <= edge_cols:
        missing = need_edges - edge_cols
        die(f"{path} schema missing edges columns: {missing} (codegraph version drift?)")


# ── component grouping (Step 5) ──────────────────────────────────────────────────

def _assign_components(files: list[dict], config: dict) -> dict[str, list]:
    """Assign each file to a component via glob matching (first-match wins).

    Returns dict of component_id -> list of file dicts.
    """
    comps = config["components"]
    default_cid = config["default_component"]
    assigned: dict[str, list] = {c["id"]: [] for c in comps}

    # Multi-match detection: every file's matches against non-misc globs
    non_default_comps = [c for c in comps if c["id"] != default_cid]

    for f in files:
        matched = False
        for c in comps:
            if fnmatch.fnmatch(f["path"], c["glob"]):
                assigned[c["id"]].append(f)
                matched = True
                break
        if not matched:
            # Shouldn't happen since cmp-misc uses **, but keep as fallback
            assigned[default_cid].append(f)

    # Multi-match warning
    for f in files:
        matches = [c["id"] for c in non_default_comps if fnmatch.fnmatch(f["path"], c["glob"])]
        if len(matches) > 1:
            warn(f"{matches[0]} matched first (also {matches[1:]}) for {f['path']}")
    return assigned


# ── micro building (Step 6) ──────────────────────────────────────────────────────

def _micro_id(relpath: str, dominant_class: str | None = None) -> str:
    """Plan Step 6: file-dominant = micro:<relpath>; class-dominant = micro:<relpath>#<qname>."""
    if dominant_class:
        return f"micro:{relpath}#{dominant_class}"
    return f"micro:{relpath}"


def _build_micros(con: sqlite3.Connection, assigned: dict[str, list],
                  config: dict) -> tuple[dict[str, dict], dict[str, str]]:
    """Build micro nodes: one per file, with dominant_class detection.

    Returns (micro_by_id, file_path_to_micro_id).
    """
    comps = config["components"]
    comp_by_id = {c["id"]: c for c in comps}

    # Find class nodes per file for dominant_class
    class_rows = con.execute(
        "SELECT qualified_name, file_path FROM nodes WHERE kind = 'class'"
    ).fetchall()
    classes_by_file: dict[str, list[str]] = {}
    for qname, fpath in class_rows:
        classes_by_file.setdefault(fpath, []).append(qname)

    micro_by_id: dict[str, dict] = {}
    file_path_to_micro_id: dict[str, str] = {}

    for cid, file_list in assigned.items():
        for f in sorted(file_list, key=lambda x: x["path"]):
            relpath = f["path"]

            dominant_class = None
            cls_list = classes_by_file.get(relpath, [])
            if len(cls_list) == 1:
                dominant_class = cls_list[0]

            mid = _micro_id(relpath, dominant_class)

            micro = {
                "id": mid,
                "kind": "micro",
                "name": Path(relpath).name,
                "path": relpath,
                "dominant_class": dominant_class,
                "signature": _sha256(relpath),  # placeholder; recomputed after nanos
                "children": [],
                "edges": [],
                "decisions": [],
                "_component_id": cid,  # internal, removed before serialization
            }
            micro_by_id[mid] = micro
            file_path_to_micro_id[relpath] = mid

    return micro_by_id, file_path_to_micro_id


# ── nano building (Step 7) ──────────────────────────────────────────────────────

def _nano_id(qname: str, relpath: str) -> str:
    return f"nano:{qname}@{relpath}"


def _collapsed_id(micro_id: str) -> str:
    """Plan Step 7: nano:+collapsed@micro:<micro_id>."""
    return f"nano:+collapsed@micro:{micro_id}"


def _build_nanos(con: sqlite3.Connection, root: Path,
                 micro_by_id: dict[str, dict],
                 file_path_to_micro_id: dict[str, str],
                 config: dict) -> dict[str, dict]:
    """Build nano nodes (functions/methods) within each micro, with nano-cap.

    Returns nano_by_id mapping nano_id -> nano dict for edge roll-up.

    ID SYNTHESIS (A1 carry-forward):
        All nano ids are path-derived via _nano_id(qname, relpath).
        NEVER pass nodes.id through — content-hash ids (function:<32-hex>)
        change on every edit and cannot be pinned by narratives.
        Do NOT dispatch on source-id prefix even for hook:<path>:<name>:<line>
        forms, which happen to be path-stable — the rule is uniform.
    """
    nano_cap = config.get("nano_cap", DEFAULT_NANO_CAP)
    nano_by_id: dict[str, dict] = {}

    # Get all function/method nodes
    rows = con.execute(
        "SELECT id, kind, qualified_name, file_path, docstring, is_exported, "
        "signature, start_line, end_line FROM nodes "
        "WHERE kind IN ('function', 'method') "
        "ORDER BY file_path, qualified_name"
    ).fetchall()

    # Group by file
    file_to_symbols: dict[str, list[dict]] = {}
    for node_id, kind, qname, fpath, docstring, is_exported, sig, start_line, end_line in rows:
        file_to_symbols.setdefault(fpath, []).append({
            "node_id": node_id,
            "kind": kind,
            "qname": qname,
            "docstring": docstring or "",
            "is_exported": bool(is_exported),
            "sig": sig or "",
            "start_line": int(start_line),
            "end_line": int(end_line),
        })

    for fpath, symbols in file_to_symbols.items():
        mid = file_path_to_micro_id.get(fpath)
        if mid is None or mid not in micro_by_id:
            continue
        micro = micro_by_id[mid]

        # Pre-compute caller counts
        candidate_nanos: list[dict] = []
        for s in symbols:
            row = con.execute(
                "SELECT COUNT(*) FROM edges "
                "WHERE target = ? AND kind IN ('calls', 'instantiates')",
                (s["node_id"],)
            ).fetchone()
            caller_count = row[0] if row else 0

            # Content-based signature: sha256 of source lines (Block 1e recipe)
            content_sig = di.slice_hash(root, fpath, s["start_line"], s["end_line"]) or _sha256("")

            nid = _nano_id(s["qname"], fpath)
            nano = {
                "id": nid,
                "kind": "nano",
                "name": s["qname"].split(".")[-1].split("::")[-1],
                "qualified_name": s["qname"],
                "path": fpath,
                "docstring": s["docstring"],
                "is_exported": s["is_exported"],
                "signature": content_sig,
                "caller_count": caller_count,
                "edges": [],
                "decisions": [],
            }
            nano_by_id[nid] = nano
            # Record candidate for sort: caller_count DESC, qualified_name ASC, path ASC (A17)
            candidate_nanos.append({
                "nid": nid,
                "caller_count": caller_count,
                "qname": s["qname"],
                "path": fpath,
            })

        # Sort: caller_count DESC (-), qualified_name ASC, path ASC
        candidate_nanos.sort(key=lambda x: (-x["caller_count"], x["qname"], x["path"]))

        # Apply nano cap
        visible = candidate_nanos[:nano_cap]
        rest = candidate_nanos[nano_cap:]

        for cn in visible:
            micro["children"].append(nano_by_id[cn["nid"]])

        if rest:
            collapsed_count = len(rest)
            collapsed_sigs = [nano_by_id[cn["nid"]]["signature"] for cn in rest]
            collapsed_sig = _sorted_sha256(collapsed_sigs)
            collapsed = {
                "id": _collapsed_id(mid),
                "kind": "collapsed",
                "name": f"+{collapsed_count} more",
                "collapsed_count": collapsed_count,
                "signature": collapsed_sig,
            }
            micro["children"].append(collapsed)

        # Update micro signature as sha256 of member sigs
        member_sigs = []
        for child in micro["children"]:
            member_sigs.append(child["signature"])
        micro["signature"] = _sorted_sha256(member_sigs)

    return nano_by_id


# ── edge roll-up (Step 8) ──────────────────────────────────────────────────────

def _roll_up_edges(con: sqlite3.Connection, root: Path,
                   micro_by_id: dict[str, dict],
                   nano_by_id: dict[str, dict],
                   file_path_to_micro_id: dict[str, str]) -> None:
    """Roll up edges at nano and micro levels.

    Nano level: incoming calls + references per nano.
    Micro level: import edges (file A -> symbol in file B).
    """
    # Build DB node_id -> nano_id mapping
    db_id_to_nano: dict[str, str] = {}
    for nid, nano in nano_by_id.items():
        qname = nano["qualified_name"]
        fpath = nano["path"]
        rows = con.execute(
            "SELECT id FROM nodes WHERE qualified_name = ? AND file_path = ? AND kind IN ('function', 'method')",
            (qname, fpath)
        ).fetchall()
        for row in rows:
            db_id_to_nano[row[0]] = nid

    # Pre-load node info for source resolution
    node_info: dict[str, tuple[str, str]] = {}
    for row in con.execute("SELECT id, qualified_name, file_path FROM nodes"):
        node_info[row[0]] = (row[1], row[2])

    # Load all relevant edges
    edge_rows = con.execute(
        "SELECT source, target, kind, line FROM edges "
        "WHERE kind IN ('calls', 'imports', 'references', 'instantiates', 'implements')"
    ).fetchall()

    # --- Nano-level edges ---
    # Collect incoming edges per nano
    nano_incoming: dict[str, list[tuple[str, str, dict]]] = {}
    for nid in nano_by_id:
        nano_incoming[nid] = []

    for source, target, kind_raw, line in edge_rows:
        target_nano = db_id_to_nano.get(target)
        if target_nano is None:
            continue

        # Determine aggregated kind
        if kind_raw in ("calls", "instantiates"):
            agg_kind = "calls"
        elif kind_raw == "references":
            agg_kind = "references"
        elif kind_raw == "imports":
            # Handled separately at micro level
            continue
        elif kind_raw == "implements":
            continue  # dropped entirely (A16)
        else:
            continue

        # Determine source file for sample_callers
        source_file = None
        if source.startswith("file:"):
            source_file = source[len("file:"):]
        elif source in node_info:
            source_file = node_info[source][1]

        source_nano = db_id_to_nano.get(source)

        # Determine source_entity_id for edge.source in model
        if source_nano:
            source_entity = nano_by_id[source_nano]["id"]
        else:
            # Non-nano source -> use source file's micro
            if source_file and source_file in file_path_to_micro_id:
                source_entity = file_path_to_micro_id[source_file]
            else:
                source_entity = source_file if source_file else "unknown"

        caller = {}
        if source_file:
            caller["file"] = source_file
            if line is not None:
                caller["line"] = int(line)

        nano_incoming.setdefault(target_nano, []).append((source_entity, agg_kind, caller))

    # Group and aggregate per nano
    for nid, incoming in nano_incoming.items():
        groups: dict[tuple[str, str], dict] = {}
        for source_entity, agg_kind, caller in incoming:
            key = (source_entity, agg_kind)
            if key not in groups:
                groups[key] = {
                    "source": source_entity,
                    "target": nid,
                    "kind": agg_kind,
                    "count": 0,
                    "sample_callers": {},
                }
            groups[key]["count"] += 1
            if caller:
                cf = (caller.get("file", ""), caller.get("line", 0))
                groups[key]["sample_callers"][cf] = caller

        edges = []
        for key in sorted(groups):
            g = groups[key]
            sorted_callers = sorted(g["sample_callers"].values(),
                                    key=lambda x: (x.get("file", ""), x.get("line", 0)))
            g["sample_callers"] = sorted_callers[:3]
            edges.append(g)

        if edges:
            nano_by_id[nid]["edges"] = edges

    # --- Micro-level import edges ---
    # Drop self-micro (same-file) placeholders (A14).
    # Roll up: source micro -> target micro for real symbol imports.
    micro_imports: dict[tuple[str, str], dict] = {}

    for source, target, kind_raw, line in edge_rows:
        if kind_raw != "imports":
            continue

        # Source file
        source_file = None
        if source.startswith("file:"):
            source_file = source[len("file:"):]
        elif source in node_info:
            source_file = node_info[source][1]

        # Target node kind — check if it's an 'import' placeholder
        target_kind = None
        if target.startswith("import:"):
            target_kind = "import"
        elif target in node_info:
            tk = con.execute("SELECT kind FROM nodes WHERE id = ?", (target,)).fetchone()
            target_kind = tk[0] if tk else None

        # Drop if target is an 'import' placeholder (self-file import)
        if target_kind == "import":
            continue

        # Only keep cross-micro imports
        source_micro_id = file_path_to_micro_id.get(source_file) if source_file else None
        target_file = node_info.get(target, (None, None))[1]
        target_micro_id = file_path_to_micro_id.get(target_file) if target_file else None

        if source_micro_id and target_micro_id and source_micro_id != target_micro_id:
            key = (source_micro_id, target_micro_id)
            if key not in micro_imports:
                micro_imports[key] = {
                    "source": source_micro_id,
                    "target": target_micro_id,
                    "kind": "imports",
                    "count": 0,
                    "sample_callers": {},
                }
            micro_imports[key]["count"] += 1
            if source_file:
                cf = (source_file, int(line) if line is not None else 0)
                micro_imports[key]["sample_callers"][cf] = {
                    "file": source_file,
                    "line": int(line) if line is not None else 0,
                }

    # Add import edges to source micros
    for key, edge in sorted(micro_imports.items()):
        src_mid = key[0]
        if src_mid in micro_by_id:
            sorted_callers = sorted(edge["sample_callers"].values(),
                                    key=lambda x: (x.get("file", ""), x.get("line", 0)))
            edge["sample_callers"] = sorted_callers[:3]
            micro_by_id[src_mid]["edges"].append(edge)


# ── decision merge (Step 9) ────────────────────────────────────────────────────

def _merge_decisions(con: sqlite3.Connection, root: Path,
                     decisions: dict,
                     assigned: dict[str, list],
                     micro_by_id: dict[str, dict],
                     nano_by_id: dict[str, dict],
                     file_path_to_micro_id: dict[str, str],
                     ) -> tuple[dict[str, dict], dict[str, list[str]]]:
    """Merge decision anchors into model nodes.

    Returns (decision_nodes, decision_attachments) where decision_attachments maps
    decision_id -> list of node_ids the decision is attached to.
    """
    decision_nodes: dict[str, dict] = {}
    decision_attachments: dict[str, list[str]] = {}

    for did, dec in decisions.items():
        if not isinstance(dec, dict):
            continue
        anchors = dec.get("anchors")
        if not anchors:
            continue

        # Only verified anchors
        validated_anchors = [a for a in anchors if a.get("verified")]
        if not validated_anchors:
            continue

        # Evaluate each anchor
        anchor_statuses: list[str] = []
        # Map component_id -> list of (model_node_id, component_id)
        comp_to_nodes: dict[str, list[str]] = {}

        for a in validated_anchors:
            ref = a["ref"]
            state = di.anchor_status(con, root, a)
            anchor_statuses.append(state)

            # Find which micro this anchor resolves to
            parsed = di.parse_ref(ref)
            if parsed[0] == "file":
                relpath = parsed[1]
                mid = file_path_to_micro_id.get(relpath)
                if mid:
                    cid = micro_by_id[mid].get("_component_id", "unknown")
                    comp_to_nodes.setdefault(cid, []).append(mid)
            else:
                _, qname, relpath = parsed
                mid = file_path_to_micro_id.get(relpath)
                if mid:
                    cid = micro_by_id[mid].get("_component_id", "unknown")
                    comp_to_nodes.setdefault(cid, []).append(mid)
                    # Also attach to nano if it exists
                    nid = _nano_id(qname, relpath)
                    if nid in nano_by_id:
                        comp_to_nodes[cid].append(nid)

        if not comp_to_nodes:
            continue

        # Reduce to worst status
        worst = min(anchor_statuses, key=lambda s: _WORST_ORDER.get(s, 0))
        # Plan Step 9 action 7: supersedes→"superseded" (only if it points at a known ADR)
        supersedes_ref = dec.get("supersedes")
        if supersedes_ref and supersedes_ref in decisions:
            final_status = "superseded"
        else:
            final_status = worst

        for cid, node_ids in comp_to_nodes.items():
            decision_id = f"decision:{did}@{cid}"
            decision_node = {
                "id": decision_id,
                "kind": "decision",
                "name": did,
                "doc": dec.get("doc", ""),
                "status": final_status,
                "signature": _sha256(decision_id),
            }
            decision_nodes[decision_id] = decision_node
            decision_attachments[decision_id] = node_ids

    return decision_nodes, decision_attachments


# ── common prefix helper ─────────────────────────────────────────────────────────

def _common_prefix(paths: list[str]) -> str:
    """Find the common path prefix of a list of relative paths."""
    if not paths:
        return ""
    if len(paths) == 1:
        p = Path(paths[0])
        return str(p.parent) if p.parts else ""
    parts_list = [Path(p).parts for p in paths]
    common = []
    for parts in zip(*parts_list):
        if len(set(parts)) == 1:
            common.append(parts[0])
        else:
            break
    return "/".join(common)


# ── component edge aggregation ───────────────────────────────────────────────────

def _aggregate_component_edges(children: list[dict], component_id: str) -> list[dict]:
    """Aggregate micro-level edges to component level."""
    edge_groups: dict[tuple[str, str, str], dict] = {}

    for child in children:
        for edge in child.get("edges", []):
            source = component_id
            # Target remains as-is (micro or nano id), since cross-component
            # resolution would need the full component map
            key = (source, edge["target"], edge["kind"])
            if key not in edge_groups:
                edge_groups[key] = {
                    "source": source,
                    "target": edge["target"],
                    "kind": edge["kind"],
                    "count": 0,
                    "sample_callers": [],
                }
            edge_groups[key]["count"] += edge["count"]
            if edge.get("sample_callers"):
                edge_groups[key]["sample_callers"].extend(edge["sample_callers"])

    result = []
    for key in sorted(edge_groups):
        g = edge_groups[key]
        # Deduplicate and sort sample_callers
        seen = set()
        unique_callers = []
        for c in g.get("sample_callers", []):
            frozen = (c.get("file", ""), c.get("line", 0))
            if frozen not in seen:
                seen.add(frozen)
                unique_callers.append(c)
        g["sample_callers"] = sorted(unique_callers,
                                     key=lambda x: (x.get("file", ""), x.get("line", 0)))[:3]
        result.append(g)
    return result


# ── pre-extract guard (Step 10) ─────────────────────────────────────────────────

def _pre_extract_guard(con: sqlite3.Connection, root: Path, index_doc: dict) -> None:
    """Check for unverified/stale anchors before extract. Warn-and-continue, exit 0."""
    decisions = index_doc.get("decisions", {})
    if not decisions:
        return

    # Check for unverified anchors (scan ALL decisions — plan Step 10 action 4)
    for did, dec in decisions.items():
        if not isinstance(dec, dict):
            continue
        for a in dec.get("anchors", []):
            if not a.get("verified"):
                warn(f"anchor {a['ref']} in {did} is NOT verified "
                     f"— run `decision_index refresh {did}`")

    # Check for non-FRESH (but verified) anchors
    rows, _ = di._evaluate(con, root, decisions)
    for did, ref, state in rows:
        if state != FRESH:
            warn(f"anchor {ref} in {did} is {state} — run `decision_index refresh {did}`")

    # Exit 0 always — warn-and-continue


# ── writer (Step 12) ────────────────────────────────────────────────────────────

def _save_model(path: Path, model: dict) -> None:
    """Atomic write with byte-deterministic serialization.

    Inherits P1's temp+os.replace pattern (carry-forward #4).
    Uses sort_keys=True, generated_at is null, fixed indent, trailing newline.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(model, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


# ── extract command (Steps 5-12) ────────────────────────────────────────────────

def cmd_extract(args) -> None:
    """Build diagram-model.json from DB + index + config."""
    db_path = Path(args.db) if args.db else di.find_db(Path.cwd())
    if not db_path:
        die("no .codegraph/codegraph.db found (run `codegraph init` first)")
    root = di.repo_root_for(db_path)
    index_path = Path(args.index) if args.index else di.default_index_path(root)
    config_path = Path(args.config) if args.config else root / DEFAULT_CONFIG_REL

    # Config (Step 3)
    config = load_config(config_path)
    nano_cap = config.get("nano_cap", args.nano_cap if args.nano_cap is not None else DEFAULT_NANO_CAP)
    out_path = Path(args.out) if args.out else root / DEFAULT_OUTPUT_REL

    # Open DB read-only
    con = di.open_db(db_path)

    # Schema guard (Step 4)
    _verify_model_schema(con, db_path)

    # Load decision index for steps 9-10. Absent file → no decisions (warn);
    # present but corrupt/unloadable → fail-loud via di.die (exit 2, contract C2).
    index_doc = None
    if index_path.is_file():
        index_doc = di.load_index(index_path)  # raises (die, exit 2) on bad JSON / shape
    else:
        warn(f"decision index not found at {index_path} — model will have 0 decisions")
    decisions_dict = index_doc.get("decisions", {}) if index_doc else {}

    # Pre-extract guard (Step 10) — warn-and-continue
    if index_doc:
        _pre_extract_guard(con, root, index_doc)

    # Step 5: Load files and assign to components
    file_rows = con.execute("SELECT path, content_hash FROM files").fetchall()
    all_files = [{"path": r[0], "content_hash": r[1]} for r in file_rows]
    assigned = _assign_components(all_files, config)

    # Step 6: Build micros
    micro_by_id, file_path_to_micro_id = _build_micros(con, assigned, config)

    # Step 7: Build nanos (pass root for content-based signatures)
    nano_by_id = _build_nanos(con, root, micro_by_id, file_path_to_micro_id, config)

    # Step 8: Roll up edges
    _roll_up_edges(con, root, micro_by_id, nano_by_id, file_path_to_micro_id)

    # Step 9: Merge decisions
    decision_nodes, decision_attachments = _merge_decisions(
        con, root, decisions_dict, assigned, micro_by_id, nano_by_id, file_path_to_micro_id
    )

    # Attach decisions to micros/nanos
    for did, node_ids in decision_attachments.items():
        for node_id in node_ids:
            if node_id.startswith("micro:"):
                if node_id in micro_by_id and did not in micro_by_id[node_id]["decisions"]:
                    micro_by_id[node_id]["decisions"].append(did)
            elif node_id.startswith("nano:"):
                if node_id in nano_by_id and did not in nano_by_id[node_id]["decisions"]:
                    nano_by_id[node_id]["decisions"].append(did)

    # Determinism (Block 1): sort per-node decision lists — attachment order follows
    # decision_attachments dict iteration, which follows index JSON key order, which
    # is not a contract. Sort so identical inputs ⇒ byte-identical output.
    for node in list(micro_by_id.values()) + list(nano_by_id.values()):
        node["decisions"].sort()

    # Build component tree
    comps = config["components"]
    component_nodes = []
    for c in comps:
        cid = c["id"]
        children = []
        for f in sorted(assigned.get(cid, []), key=lambda x: x["path"]):
            mid = file_path_to_micro_id.get(f["path"])
            if mid and mid in micro_by_id:
                # Remove internal field before adding to output
                m = dict(micro_by_id[mid])
                m.pop("_component_id", None)
                children.append(m)

        # Common prefix for component path
        matched_paths = [f["path"] for f in assigned.get(cid, [])]
        comp_path = _common_prefix(matched_paths) if matched_paths else c.get("glob", "")

        # Component edges: aggregate from micro edges
        comp_edges = _aggregate_component_edges(children, cid)

        # Component-level decisions: deduplicate from child micros and
        # decisions directly targeting this component
        comp_decisions_set: set[str] = set()
        for child in children:
            comp_decisions_set.update(child.get("decisions", []))
        # Also add any decision that ends with @cid
        for did in decision_nodes:
            if did.endswith(f"@{cid}"):
                comp_decisions_set.add(did)
        comp_decisions = sorted(comp_decisions_set)

        # Component signature: sha256 over member signatures
        member_sigs = [c["signature"] for c in children]
        comp_sig = _sorted_sha256(member_sigs)

        component_node = {
            "id": cid,
            "kind": "component",
            "name": c["name"],
            "path": comp_path,
            "signature": comp_sig,
            "children": children,
            "edges": comp_edges,
            "decisions": comp_decisions,
        }
        component_nodes.append(component_node)

    # Assemble model
    model = {
        "version": MODEL_VERSION,
        "generated_at": None,  # byte-deterministic (never a timestamp)
        "nano_cap": nano_cap,
        "components": component_nodes,
        "decisions": sorted(decision_nodes.values(), key=lambda x: x["id"]),
    }

    # Write atomically (Step 12)
    _save_model(out_path, model)
    ok(f"wrote {out_path}")

    # Update golden if requested
    if args.update_golden:
        script_dir = Path(__file__).resolve().parent
        golden = script_dir / "testdata" / "mkt_engine.model.json"
        golden.parent.mkdir(parents=True, exist_ok=True)
        _save_model(golden, model)
        ok(f"updated golden {golden}")

    con.close()


# ── CLI (Step 2) ────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="graph_model",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    pe = sub.add_parser("extract", help="build diagram-model.json from DB + index + config")
    pe.add_argument("--db", help="path to .codegraph/codegraph.db (default: search upward)")
    pe.add_argument("--index", help="path to decision index json (default: <root>/docs/decision-index.json)")
    pe.add_argument("--config", help=f"path to ssot-diagram.config.json (default: <root>/{DEFAULT_CONFIG_REL})")
    pe.add_argument("--out", help=f"output path (default: <root>/{DEFAULT_OUTPUT_REL})")
    pe.add_argument("--nano-cap", type=int, default=None, help=f"max nanos per micro (default: {DEFAULT_NANO_CAP})")
    pe.add_argument("--update-golden", action="store_true", help=argparse.SUPPRESS)
    pe.set_defaults(fn=cmd_extract)

    pb = sub.add_parser("bootstrap-config", help="seed a ssot-diagram.config.json from top-level dirs")
    pb.add_argument("--db", help="path to .codegraph/codegraph.db (default: search upward)")
    pb.add_argument("--out", help=f"output config path (default: <root>/{DEFAULT_CONFIG_REL})")
    pb.add_argument("--force", action="store_true", help="overwrite an existing config")
    pb.set_defaults(fn=cmd_bootstrap_config)

    return p


def cmd_bootstrap_config(args) -> None:
    db_path = Path(args.db) if args.db else di.find_db(Path.cwd())
    if not db_path or not db_path.is_file():
        die("no .codegraph/codegraph.db found (run `codegraph init` first)")
    root = di.repo_root_for(db_path)
    out = Path(args.out) if args.out else root / DEFAULT_CONFIG_REL
    bootstrap_config(db_path, out, args.force)


def main() -> None:
    args = build_parser().parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
