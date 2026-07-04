# codegraph-piggyback — Context

A delivery rail for hook scripts and CLIs that read `.codegraph/codegraph.db`
(read-only) to make AI coding agents safer and cheaper. This file pins the
domain terms that recur across tools and phases so a non-coder can read the
design docs without guessing.

## Language

**Diagram model**:
The machine-emitted JSON (`diagram-model.json`) a renderer turns into a picture — the single source of truth for "what the code looks like right now."
_Avoid_: code map, architecture graph, model file

**Component (macro)**:
A human-named bucket of files at the top level of the diagram (e.g. "AI image generation" = everything under `lib/ai/**`).
_Avoid_: module, package, layer, subsystem

**Micro**:
A single file inside a component, or the one dominant class when a file is one class. The middle level of the diagram.
_Avoid_: file-node, unit, leaf

**Nano**:
A function or method inside a micro — the deepest level of the diagram, capped per micro to avoid a hairball.
_Avoid_: symbol, function-node, member

**Nano cap**:
The per-micro limit (default 8) on how many nano nodes appear; symbols past the cap collapse into one honest "+K more" node instead of being silently dropped.
_Avoid_: truncation, max-functions, limit

**Collapsed node**:
The synthetic "+K more" node that stands in for the nanos beyond the nano cap; carries a signature over its members' hashes so drift is still visible.
_Avoid_: overflow-node, summary-node, ellipsis

**Rolled-up edge**:
A dependency arrow between two components (or two micros) that aggregates many symbol-level `calls`/`imports`/`references` edges into one line with a count and a 3-row sample of callers.
_Avoid_: aggregate-edge, summarized-link, count-edge

**Decision attachment**:
A decision (ADR) pinned to the component (and/or micro) that owns its verified anchors; carries a live FRESH/STALE/ORPHANED badge. One decision can attach to several components.
_Avoid_: decision-link, ADR-pin, badge-node

**Anchor**:
A pointer from a decision to a specific file or symbol in the code, used to detect when that decision might be stale because the code drifted.
_Avoid_: link, ref, pointer, reference (except in edge kind)

**Signature (content)**:
A sha256 fingerprint of a file's content or a symbol's source slice, used to pin LLM-written prose (narratives) and decision attachments so silent drift is impossible.
_Avoid_: hash, checksum, content-hash, type-signature (the codegraph `nodes.signature` column is a CODE signature, NOT this — avoid "signature" for type info)

**bootstrap-config**:
The seed command that scans top-level dirs and proposes a `ssot-diagram.config.json` for a human to curate; never re-seeds automatically (re-seed = `bootstrap-config --force`).
_Avoid_: init, generate-config, auto-config

**Extract**:
The command that reads the DB + curated decision index + curated config and emits one byte-identical `diagram-model.json`; fails loud if the config is missing.
_Avoid_: build, render, generate (render is reserved for P5 HTML)

## Flagged ambiguities

- **"signature"** — overloaded in this codebase. The codegraph DB has a `nodes.signature` column (the function's type signature in code, e.g. `(x: number): string`). The diagram model has a `signature` field (a sha256 content fingerprint). Whenever "signature" appears unqualified, it means the content fingerprint. When the DB column is meant, write "codegraph `nodes.signature` column" or "type signature".
- **"edge"** — the codegraph DB has raw symbol-level edges (table `edges`, kinds include `contains`, `instantiates`, `implements`). The diagram model has rolled-up edges (per-node `edges[]`, kinds only `calls`/`imports`/`references`). "Edge" unqualified in a design doc means the rolled-up model edge; "codegraph edge" or "raw edge" means the DB row.

## Example dialogue

**Curator:** "I ran `graph_model.py bootstrap-config` on mkt_engine — it seeded 8 components from the top-level dirs. I want to merge `scripts` and `prisma` into one `cmp-infra` component."

**Builder:** "Edit `ssot-diagram.config.json`: drop the two rows, add one with `glob: "{scripts,prisma}/**"` and `id: cmp-infra`. Leave `cmp-misc` as the default component for anything unmatched."

**Curator:** "What about the ADR-0006 decision — it anchors across `lib/canvas/**` and `lib/store/**?"

**Builder:** "The decision attaches to every component owning one of its verified anchors — so it'll appear on both `cmp-canvas` and `cmp-store`, same FRESH/STALE badge on each, id `decision:ADR-0006@cmp-canvas` and `decision:ADR-0006@cmp-store`. No phantom cross-cutting component."

**Curator:** "And if the index has an unverified anchor?"

**Builder:** "The pre-extract guard prints a stderr warning telling you to run `decision_index refresh <id>`, exit 0, and the model is still produced — but that unverified anchor produces no decision node. Truthful either way."
