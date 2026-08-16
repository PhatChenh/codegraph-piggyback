# Tech Debt

## Active

### TD-01 · No post-`codegraph init` completion hook for consumers
**Status:** OPEN
**Phase:** When codegraph grows a consumer-facing lifecycle event (or an official wrapper) that other tools can subscribe to without wrapping the binary themselves
**Risk if triggered early:** A half-baked wrapper in writ (or another consumer) that operators can bypass by running bare `codegraph init` trains a false “marker gone ⇒ indexed” invariant and splits the ecosystem into wrapper-users vs raw-CLI users
**What:** `codegraph init` is a third-party-facing CLI with **no completion hook / event / plugin seat** that a downstream tool (writ’s greenfield-marker consume, etc.) can bind to. Writ’s C11–C16 inference-gates design therefore cannot implement the owner’s original lock (“delete `.writ-greenfield` on first valid `codegraph init`”) as written. Provisional consumer behaviour (falkor-writ plan OQ-P2 / design OQ-6, owner pick 3c 2026-08-06): delete the marker at the **first audit that observes a usable index**. That leaves a short window after init and before first audit where marker + live index coexist; no consumer reads “marker absent ⇒ indexed” today.
**Why deferred:** Fix belongs in codegraph (emit a durable post-init signal, or ship a supported wrapper consumers call), not in each consumer inventing its own bypassable shim. Owner deferred the writ lock reword vs wrapper choice; provisional audit-time consume ships in falkor-writ until this TD lands.
**Source:** falkor-writ run `c11-c16-inference-gates` (2026-08-06); design OQ-6; plan OQ-P2; owner answers 3c + “put the TD in codegraph-piggyback”
**Cleanup when this TD lands (owner 2026-08-09, bucket-2 grill):** falkor-writ is shipping a **Writ-side `codegraph init` wrapper** that deletes `.writ-greenfield` on successful init (OQ-P2 → pick 5c, reversing the “provisional 3c only” stance). When codegraph gains a real post-init hook/event (this TD), **retire that Writ wrapper’s marker-consume duty** (or make it a thin call into the native signal) and scrub the dual-path docs so operators are not told two different consume rules. Track from falkor-writ run `2026-08-09-improv-bucket2-light`.

## Archive
