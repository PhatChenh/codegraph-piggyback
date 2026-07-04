# Scout — macro component grouping prior art

_Prior-art scouting for ssot P3 extractor landmine: macro component grouping is a
human call (config seed-then-curate). Phase A tier-A landmine per
`docs/roadmap/roadmap.md`. Gathered 2026-07-04._

## Our landmine (restated)

P3 builds a deterministic extractor: codegraph DB → `diagram-model.json`,
3-level hierarchy: **macro** (components) → **micro** (files/classes) → **nano**
(functions). Default macro = top-level dirs containing indexed files; overridable
by `ssot-diagram.config.json` (glob → component name). Bad grouping degrades
every downstream picture. Pattern = seed-then-curate (machine proposes, human
edits), same as the decision index.

## Tool 1 — Structurizr / C4 model

Two modes, both represented:

**Manual curated DSL** (https://docs.structurizr.com/dsl/basics):
- Hierarchy is hand-written in a DSL: `softwareSystem =`, `container =`,
  `component =` statements. Names must be unique (component unique within
  container; container within software system).
- `group` keyword wraps child elements:
  ```
  group "${ORGANISATION_NAME} - ${_GROUP_NAME}" {
      user = person "User"
  }
  ```
- Curly braces host child content; tags comma-separated.
- Verbatim rules: "Software and people names must be unique." / "Container names
  must be unique within the context of a software system." / "Component names
  must be unique within the context of a container."

**Auto-discovery via Component Finder** (Java; https://docs.structurizr.com/java/component/introduction
— content not fetched, nav confirms it exists): discovers components from
code (annotations/types). This is the "seed" path; the DSL is the "curate" path.

**Takeaway for us:** Structurizr embodies exactly the seed-vs-curate split our
roadmap already prescribes — auto-from-code is the proposal, hand-DSL is the
override. Confirms the seed-then-curate pattern is industry-standard.

## Tool 2 — dependency-cruiser

URL: https://github.com/sverweij/dependency-cruiser/blob/main/doc/rules-reference.md

**Path matching = regex (not glob), forward slashes internally.**

**Group matching via capture groups** (their core folder-grouping mechanism):
- `from.path` regex with a capture group: `"^src/([^/]+)/.+"`
- `to.path`/`pathNot` references the group with `$1`: `"pathNot": "^src/$1/.+"`
- Multiple groups: `$1`, `$2`…; `$0` = entire match.

Verbatim example (prevent inter-component deps):
```json
{
  "name": "no-inter-ubc",
  "comment": "Don't allow relations between business components",
  "severity": "error",
  "from": { "path": "^src/business-components/([^/]+)/.+" },
  "to": {
    "path": "^src/business-components/([^/]+)/.+",
    "pathNot": "^src/business-components/$1/.+"
  }
}
```

**`scope` attribute** (verbatim): "What to apply the rule to — either `module`
(the default) or `folder`." Folder-level rules let folders be treated as the
grouping unit even when modules live inside them.

**`ancestor` boolean** matches modules in a folder above the current module's
folder — folder-hierarchy as a constraint.

**Known limitation (verbatim):** group matching "does **not** work with
`numberOfDependentsLessThan`/`numberOfDependentsMoreThan` because 'with more
than one result... there's also more than one thing `$1` means — making use in
e.g. `to.path` ambiguous.'" → capture-group grouping is fragile when a path
matches multiple groups.

**`comment` field** carries documentation, never used in logic — same role as
our config's human notes.

**Takeaway for us:** regex-with-capture-groups is a real alternative to glob →
name mapping. More expressive (`$1` backrefs) but error-prone (ambiguous on
multi-match) and harder for a non-coder to curate. Glob → component-name mapping
(our roadmap's choice) is the simpler, safer subset for a non-SWE owner.

## Tool 3 — ArchUnit

URL: https://www.archunit.org/ (landing only — DSL detail behind userguide
login wall at https://www.archunit.org/userguide/html/000_Index.html)

Landing verbatim:
> "ArchUnit can check dependencies between packages and classes, layers and
> slices, check for cyclic dependencies and more."
> "It does so by analyzing given Java bytecode, importing all classes into a
> Java code structure."

Concepts represented (per landing): **packages** (Java = directories) as the
default grouping unit, **layers** (named ordered groups) and **slices**
(parallel same-level groups, used for cyclic-dep detection). Grouping is by
package-naming convention.

**Takeaway for us:** validates "top-level dirs as default components" — ArchUnit
does the same (packages = dirs). No config-derived override surfaced beyond
package matchers; the override layer is code (DSL), not a data file.

## Cross-tool patterns (what others converge on)

1. **Default = directory structure mirrors the component tree.** All three
   treat paths/dirs/packages as the seed grouping (ArchUnit packages, dependency-
   cruiser `scope: folder`, Structurizr Component Finder from code). Our
   roadmap's "top-level dirs" default is the same instinct.
2. **The override layer is a separate curated artifact.** Structurizr DSL,
   dependency-cruiser `.dependency-cruiser.js` rules, ArchUnit test code.
   None try to fully auto-derive good macro grouping — all assume a human edits.
3. **Glob/regex-to-name mapping is the simplest override form.** dependency-
   cruiser's regex+capture is the most expressive; Structurizr's named elements
   the most manual. Our `ssot-diagram.config.json` glob → component name sits
   between them — simpler than regex, more declarative than hand-listing.
4. **Uniqueness is enforced.** Structurizr: component names unique within
   container. An invariant our model should mirror (component ids unique).
5. **Capture-group / dynamic grouping is fragile** (dependency-cruiser's own
   caveat). Argues against any "derive component name from path prefix
   automatically" cleverness — favor explicit glob → name rules.

## What this scout does NOT do

Per pipeline rule: scout is prior-art only, does NOT decide. The config schema
for `ssot-diagram.config.json` is a DESIGN decision, owned by the design step
with HITL approval. This file lists what others do; the design step picks.
