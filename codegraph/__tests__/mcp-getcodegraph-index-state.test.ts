/**
 * getCodeGraph explicit arm + explore emptyWarn (Bucket 5 Step 5).
 *
 * The explicit-path arm of `getCodeGraph` must route through the
 * `resolveMcpIndexState` mapper (NOT raw `probeIndexHealth`), so the mapper's
 * throw-fallback is not undone on the first tool call:
 *
 * - MUST-2 — a probe throw while a real `.codegraph/` root exists degrades to
 *   `usable` in the mapper; the execute result must NOT print `isn't indexed`
 *   or the missing-directory copy (an initialized project must not lose its
 *   index to a transient probe failure).
 * - Junk / unreadable db at a real root maps to `index_missing` with a
 *   non-null root → the junk NotIndexedError copy (`no usable index`), served
 *   SUCCESS-shaped (`isError` falsy) so the agent keeps trusting the toolset.
 * - The empty-index explore warning names `codegraph init` (the stale
 *   `init -i` is gone).
 *
 * Real-fixture cases (junk db → probe) are skipped on Node < 22.5 where
 * `node:sqlite` doesn't exist; the MUST-2 throw-spy case runs everywhere.
 */

import { describe, it, expect, afterEach, vi } from 'vitest';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import * as directory from '../src/directory';
import CodeGraph from '../src/index';
import { ToolHandler } from '../src/mcp/tools';

let nodeSqliteAvailable = false;
try {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  require('node:sqlite');
  nodeSqliteAvailable = true;
} catch {
  nodeSqliteAvailable = false;
}

function makeRoot(): string {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'cg-mcp-getcodegraph-'));
  fs.mkdirSync(path.join(root, '.codegraph'), { recursive: true });
  return root;
}

/** A real empty index (proper schema, 0 nodes) via the public API. */
function makeRealEmptyIndex(root: string): CodeGraph {
  const cg = CodeGraph.initSync(root, { config: { include: ['**/*.ts'], exclude: [] } });
  // Close the seeding connection so the handler's `openSync` is the only
  // holder of the db — a second connection on the wasm backend (no WAL)
  // could otherwise surface as a spurious "database is locked".
  cg.close();
  return cg;
}

describe('getCodeGraph explicit arm (MUST-2)', () => {
  let roots: string[] = [];

  function track(root: string): string {
    roots.push(root);
    return root;
  }

  afterEach(() => {
    vi.restoreAllMocks();
    for (const r of roots) {
      try {
        fs.rmSync(r, { recursive: true, force: true });
      } catch {
        /* ignore — already gone */
      }
    }
    roots = [];
  });

  it('probe throw at a real root must NOT print "isn\'t indexed" or the missing-directory copy', async () => {
    const root = track(makeRoot());
    makeRealEmptyIndex(root);

    const spy = vi.spyOn(directory, 'probeIndexHealth').mockImplementation(() => {
      throw new Error('probe exploded');
    });

    const res = await new ToolHandler(null).execute('codegraph_explore', {
      query: 'x',
      projectPath: root,
    });
    const text = res.content[0].text;

    // The arm must run the mapper (which probes), and the mapper's
    // throw+root → usable fallback must hold: getCodeGraph proceeds instead
    // of degrading to missing-behavior. (The lazy `require('../index')` can't
    // resolve under vitest, so openSync falls through to a generic error —
    // the point is the missing copy is never printed.)
    expect(spy).toHaveBeenCalled();
    expect(text).not.toContain("isn't indexed");
    expect(text).not.toContain('no .codegraph/ directory found');
  });

  it.skipIf(!nodeSqliteAvailable)(
    'junk db at a real root → SUCCESS-shaped NotIndexedError contains "no usable index"',
    async () => {
      const root = track(makeRoot());
      fs.writeFileSync(
        path.join(root, '.codegraph', 'codegraph.db'),
        'this is junk text, not a sqlite database',
      );

      const res = await new ToolHandler(null).execute('codegraph_explore', {
        query: 'x',
        projectPath: root,
      });
      const text = res.content[0].text;

      expect(res.isError).toBeFalsy();
      expect(text).toContain('no usable index');
      expect(text).not.toContain('no .codegraph/ directory found');
    },
  );
});

describe('codegraph_explore emptyWarn', () => {
  it('0-node explore names `codegraph init`, not `init -i`', async () => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'cg-mcp-emptywarn-'));
    const cg = CodeGraph.initSync(root, { config: { include: ['**/*.ts'], exclude: [] } });
    const handler = new ToolHandler(cg);
    try {
      expect(cg.getStats().nodeCount).toBe(0);

      const res = await handler.execute('codegraph_explore', { query: 'anything' });
      const text = res.content[0].text;

      expect(res.isError).toBeFalsy();
      expect(text).toContain('codegraph init');
      expect(text).not.toContain('init -i');
    } finally {
      try {
        cg.destroy();
      } catch {
        /* best effort */
      }
      if (fs.existsSync(root)) fs.rmSync(root, { recursive: true, force: true });
    }
  });
});
