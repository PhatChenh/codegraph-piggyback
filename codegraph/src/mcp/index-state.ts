/**
 * Index-state mapper — one owner of walk → probe → throw-guard → 5→3 map.
 *
 * MCP session/proxy/tools each need "is there a usable index reachable from
 * this path, and is it mid-build?" before the engine is initialized. This
 * module answers that from `.codegraph/codegraph.db` alone (read-only),
 * collapsing `probeIndexHealth`'s five statuses into the three the handshake
 * acts on:
 *
 * - `usable`     → a working index
 * - `index_empty` → index dir exists but has no nodes yet — and `busy:true`
 *                   when the db is locked (an index build in progress)
 * - `index_missing` → nothing usable at the nearest root (no root at all, an
 *                   unreadable/corrupt db, or an unclassifiable state)
 *
 * A throw from the probe with a root present degrades to `usable` — never
 * `missing`: an initialized project must not silently lose its index to a
 * transient probe failure. `busy === true` only pairs with `index_empty`.
 */

import { findNearestCodeGraphRoot, probeIndexHealth } from '../directory';

export type McpIndexState = 'index_missing' | 'index_empty' | 'usable';

export function resolveMcpIndexState(startPath: string): {
  state: McpIndexState;
  busy: boolean;
  root: string | null;
} {
  const root = findNearestCodeGraphRoot(startPath);
  if (!root) {
    return { state: 'index_missing', busy: false, root: null };
  }

  try {
    const health = probeIndexHealth(root);
    switch (health.status) {
      case 'usable':
        return { state: 'usable', busy: false, root };
      case 'empty':
        return { state: 'index_empty', busy: false, root };
      case 'busy':
        return { state: 'index_empty', busy: true, root };
      case 'unreadable':
      case 'unclassified':
        return { state: 'index_missing', busy: false, root };
    }
  } catch {
    return { state: 'usable', busy: false, root };
  }
}
