/**
 * resolveMcpIndexState — the single owner of walk → probe → throw-guard →
 * 5→3 map (Bucket 5 Step 2).
 *
 * The mapper answers "is there a usable index reachable from this path?"
 * without ever touching the engine: `findNearestCodeGraphRoot` walks up to
 * the nearest `.codegraph/`, `probeIndexHealth` classifies the db read-only,
 * and a throw while the root exists degrades to `usable` — never `missing`
 * (the handshake must not lose an initialized project to a transient probe
 * failure). Fixtures reuse the probe suite's recipes: junk text (errcode 26
 * → unreadable), a COUNT=0 db (empty), a db with nodes (usable), plus stubs
 * for the paths the real SQLite probe can't drive deterministically (busy,
 * unclassified, throw).
 *
 * Skipped on Node < 22.5 where node:sqlite doesn't exist (real-fixture
 * cases only — the stub cases run everywhere).
 */

import { describe, it, expect, afterEach, vi } from 'vitest';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import * as directory from '../src/directory';
import { resolveMcpIndexState } from '../src/mcp/index-state';

let nodeSqliteAvailable = false;
try {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  require('node:sqlite');
  nodeSqliteAvailable = true;
} catch {
  nodeSqliteAvailable = false;
}

function makeRoot(): string {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'cg-mcp-index-state-'));
  fs.mkdirSync(path.join(root, '.codegraph'), { recursive: true });
  return root;
}

function makeDbWithNodes(dbPath: string, n: number): void {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { DatabaseSync } = require('node:sqlite') as {
    DatabaseSync: new (
      p: string
    ) => { exec: Function; prepare: Function; close: Function };
  };
  const db = new DatabaseSync(dbPath);
  db.exec('CREATE TABLE nodes(id INTEGER PRIMARY KEY, name TEXT)');
  const ins = db.prepare('INSERT INTO nodes(name) VALUES (?)');
  for (let i = 0; i < n; i++) ins.run(`sym${i}`);
  db.close();
}

describe('resolveMcpIndexState', () => {
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

  it('missing dir (no .codegraph/ ancestor) → index_missing, root null', () => {
    const r = resolveMcpIndexState(track(fs.mkdtempSync(path.join(os.tmpdir(), 'cg-mcp-index-state-none-'))));
    expect(r).toEqual({ state: 'index_missing', busy: false, root: null });
  });

  describe.skipIf(!nodeSqliteAvailable)('real index fixtures', () => {
    it('junk text db (errcode 26 → unreadable) → index_missing', () => {
      const root = track(makeRoot());
      fs.writeFileSync(path.join(root, '.codegraph', 'codegraph.db'), 'this is junk text, not a sqlite database');
      const r = resolveMcpIndexState(root);
      expect(r).toEqual({ state: 'index_missing', busy: false, root });
    });

    it('empty db (COUNT=0) → index_empty', () => {
      const root = track(makeRoot());
      makeDbWithNodes(path.join(root, '.codegraph', 'codegraph.db'), 0);
      const r = resolveMcpIndexState(root);
      expect(r).toEqual({ state: 'index_empty', busy: false, root });
    });

    it('usable db (nodes>0) → usable', () => {
      const root = track(makeRoot());
      makeDbWithNodes(path.join(root, '.codegraph', 'codegraph.db'), 5);
      const r = resolveMcpIndexState(root);
      expect(r).toEqual({ state: 'usable', busy: false, root });
    });

    it('spies: probeIndexHealth is invoked when a root fixture exists', () => {
      const root = track(makeRoot());
      makeDbWithNodes(path.join(root, '.codegraph', 'codegraph.db'), 1);
      const spy = vi.spyOn(directory, 'probeIndexHealth');
      resolveMcpIndexState(root);
      expect(spy).toHaveBeenCalledTimes(1);
      expect(spy).toHaveBeenCalledWith(root);
    });
  });

  describe('stubs', () => {
    it('busy stub → index_empty with busy=true', () => {
      const root = track(makeRoot());
      fs.writeFileSync(path.join(root, '.codegraph', 'codegraph.db'), 'placeholder so root resolves');
      const spy = vi.spyOn(directory, 'probeIndexHealth').mockReturnValue({ status: 'busy' } as never);
      const r = resolveMcpIndexState(root);
      expect(r).toEqual({ state: 'index_empty', busy: true, root });
      expect(spy).toHaveBeenCalledWith(root);
    });

    it('unclassified stub → index_missing', () => {
      const root = track(makeRoot());
      fs.writeFileSync(path.join(root, '.codegraph', 'codegraph.db'), 'placeholder so root resolves');
      vi.spyOn(directory, 'probeIndexHealth').mockReturnValue({ status: 'unclassified' } as never);
      const r = resolveMcpIndexState(root);
      expect(r).toEqual({ state: 'index_missing', busy: false, root });
    });

    it('throw stub + root fixture → usable (never missing while root exists)', () => {
      const root = track(makeRoot());
      fs.writeFileSync(path.join(root, '.codegraph', 'codegraph.db'), 'placeholder so root resolves');
      vi.spyOn(directory, 'probeIndexHealth').mockImplementation(() => {
        throw new Error('probe exploded');
      });
      const r = resolveMcpIndexState(root);
      expect(r).toEqual({ state: 'usable', busy: false, root });
    });

    it('throw stub + missing dir → index_missing, probe never invoked', () => {
      const spy = vi.spyOn(directory, 'probeIndexHealth').mockImplementation(() => {
        throw new Error('probe exploded');
      });
      const r = resolveMcpIndexState(track(fs.mkdtempSync(path.join(os.tmpdir(), 'cg-mcp-index-state-none-'))));
      expect(r).toEqual({ state: 'index_missing', busy: false, root: null });
      expect(spy).not.toHaveBeenCalled();
    });
  });
});
