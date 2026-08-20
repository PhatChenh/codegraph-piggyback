/**
 * runLocalHandshakeProxy — per-state local handshake payloads (Bucket 5 Step 4).
 *
 * The proxy answers `initialize` + `tools/list` from STATIC constants the
 * instant the client asks, so headless agents register tools at process-startup
 * time instead of waiting ~600ms for the daemon to spawn. This test drives the
 * proxy directly with injected `LocalHandshakeDeps` (no live daemon) and pins
 * the two handshake writes to the same mapping table the session door uses:
 *
 *   - missing / unreadable / unclassified → `index_missing` → reworded UNINDEXED
 *     + `tools: []`
 *   - empty db → `SERVER_INSTRUCTIONS_INDEX_EMPTY` + nonempty `getStaticTools()`
 *   - busy (locked) → `SERVER_INSTRUCTIONS_INDEX_BUSY` (exact imported constant)
 *     + nonempty `getStaticTools()`
 *   - usable → `SERVER_INSTRUCTIONS` + nonempty `getStaticTools()`
 *
 * `runLocalHandshakeProxy` never returns (it hangs on `await new
 * Promise(() => {})` once the socket resolves), so these tests must NOT await
 * it to completion. Pattern: start the promise, `process.stdin.emit('data', …)`
 * to drive the handler synchronously, spy `process.stdout.write`, and stub
 * `process.exit` so a shutdown can't kill the test process.
 *
 * BT-1b: `getDaemonSocket` returns a Promise that STAYS PENDING for the whole
 * assertion window. An immediate-null stub does NOT satisfy this — only a
 * regression that waits on the daemon socket before attaching the stdin
 * listener fails to answer initialize while the socket is pending.
 */

import { describe, it, expect, afterEach, vi } from 'vitest';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import * as net from 'net';
import * as directory from '../src/directory';
import * as indexState from '../src/mcp/index-state';
import {
  runLocalHandshakeProxy,
  LocalHandshakeDeps,
} from '../src/mcp/proxy';
import {
  SERVER_INSTRUCTIONS,
  SERVER_INSTRUCTIONS_UNINDEXED,
  SERVER_INSTRUCTIONS_INDEX_EMPTY,
  SERVER_INSTRUCTIONS_INDEX_BUSY,
} from '../src/mcp/server-instructions';
import { getStaticTools } from '../src/mcp/tools';

let nodeSqliteAvailable = false;
try {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  require('node:sqlite');
  nodeSqliteAvailable = true;
} catch {
  nodeSqliteAvailable = false;
}

interface RpcEnvelope {
  jsonrpc: string;
  id: number;
  result?: { instructions?: string; tools?: unknown[] };
}

/** Fixture roots: a `.codegraph/codegraph.db` must exist for the walk to find
 *  the root (`isInitialized` = `existsSync(dbPath)`), so a bare dir is the
 *  "missing" fixture and the rest write a db file. */
function makeRoot(prefix: string): string {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), prefix));
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

function makeDeps(
  root: string,
  getDaemonSocket: () => Promise<net.Socket | null> = () => Promise.resolve(null)
): LocalHandshakeDeps {
  return {
    getDaemonSocket,
    // The in-process fallback engine is only created on `tools/call`, which
    // these handshake tests never send — a minimal stub suffices.
    makeEngine: (() => ({})) as LocalHandshakeDeps['makeEngine'],
    root,
  };
}

const initialize = (id: number) => ({
  jsonrpc: '2.0',
  id,
  method: 'initialize',
  params: { protocolVersion: 1, capabilities: {}, clientInfo: { name: 'test', version: '1' } },
});

const toolsList = (id: number) => ({ jsonrpc: '2.0', id, method: 'tools/list', params: {} });

/** Start the proxy, drive the given JSON-RPC messages through stdin, and return
 *  the parsed stdout writes. The handler runs synchronously on each emit, so
 *  the writes are complete when this returns — no waiting on the daemon socket. */
function driveHandshake(
  deps: LocalHandshakeDeps,
  msgs: unknown[]
): { writes: RpcEnvelope[]; promise: Promise<void> } {
  const writes: RpcEnvelope[] = [];
  vi.spyOn(process.stdout, 'write').mockImplementation(((chunk: unknown) => {
    const text = typeof chunk === 'string' ? chunk : String(chunk);
    writes.push(JSON.parse(text.trim()) as RpcEnvelope);
    return true;
  }) as never);
  // `shutdown` calls `process.exit(0)` — stub it so a teardown can't kill the
  // test process.
  vi.spyOn(process, 'exit').mockImplementation((() => {}) as never);
  const promise = runLocalHandshakeProxy(deps).catch(() => {});
  for (const m of msgs) {
    process.stdin.emit('data', JSON.stringify(m) + '\n');
  }
  return { writes, promise };
}

describe('runLocalHandshakeProxy — per-state stdout table (BT-1)', () => {
  let roots: string[] = [];

  function track(root: string): string {
    roots.push(root);
    return root;
  }

  afterEach(() => {
    vi.restoreAllMocks();
    // The proxy's stdin listeners are still attached; removing the data
    // listener returns the stream to paused mode so it can't hold the worker
    // event loop open. The end/close/error listeners are inert once no data
    // flows and no terminal event is emitted.
    process.stdin.removeAllListeners('data');
    process.stdin.removeAllListeners('end');
    process.stdin.removeAllListeners('close');
    process.stdin.removeAllListeners('error');
    for (const r of roots) {
      try {
        fs.rmSync(r, { recursive: true, force: true });
      } catch {
        /* ignore — already gone */
      }
    }
    roots = [];
  });

  it('missing root (no .codegraph/ ancestor) → UNINDEXED + tools []', () => {
    const root = track(fs.mkdtempSync(path.join(os.tmpdir(), 'cg-mcp-proxy-missing-')));
    const { writes } = driveHandshake(makeDeps(root), [initialize(1), toolsList(2)]);
    const init = writes.find((w) => w.id === 1);
    const list = writes.find((w) => w.id === 2);
    expect(init?.result?.instructions).toBe(SERVER_INSTRUCTIONS_UNINDEXED);
    expect(list?.result?.tools).toEqual([]);
  });

  it('junk db (unreadable) → reworded UNINDEXED (no dir claim) + tools []', () => {
    const root = track(makeRoot('cg-mcp-proxy-junk-'));
    fs.writeFileSync(path.join(root, '.codegraph', 'codegraph.db'), 'this is junk text, not a sqlite database');
    const { writes } = driveHandshake(makeDeps(root), [initialize(1), toolsList(2)]);
    const init = writes.find((w) => w.id === 1);
    const list = writes.find((w) => w.id === 2);
    expect(init?.result?.instructions).toBe(SERVER_INSTRUCTIONS_UNINDEXED);
    // The junk db HAS the directory and the file — the copy must not claim
    // otherwise (BT-2 pin).
    expect(init?.result?.instructions).toContain('no usable index');
    expect(init?.result?.instructions).not.toContain('no `.codegraph/` directory');
    expect(list?.result?.tools).toEqual([]);
  });

  it('empty db (COUNT=0) → EMPTY copy + nonempty getStaticTools()', () => {
    const root = track(makeRoot('cg-mcp-proxy-empty-'));
    makeDbWithNodes(path.join(root, '.codegraph', 'codegraph.db'), 0);
    const { writes } = driveHandshake(makeDeps(root), [initialize(1), toolsList(2)]);
    const init = writes.find((w) => w.id === 1);
    const list = writes.find((w) => w.id === 2);
    expect(init?.result?.instructions).toBe(SERVER_INSTRUCTIONS_INDEX_EMPTY);
    expect(init?.result?.instructions).not.toContain('inactive this session');
    expect(list?.result?.tools).toEqual(getStaticTools());
  });

  it('busy (probe status busy) → SERVER_INSTRUCTIONS_INDEX_BUSY (=== imported) + getStaticTools()', () => {
    const root = track(makeRoot('cg-mcp-proxy-busy-'));
    fs.writeFileSync(path.join(root, '.codegraph', 'codegraph.db'), 'placeholder so root resolves');
    vi.spyOn(directory, 'probeIndexHealth').mockReturnValue({ status: 'busy' } as never);
    const { writes } = driveHandshake(makeDeps(root), [initialize(1), toolsList(2)]);
    const init = writes.find((w) => w.id === 1);
    const list = writes.find((w) => w.id === 2);
    // Exact equality against the imported constant — a 3-arm helper that
    // collapses busy into EMPTY must fail here (MUST-3).
    expect(init?.result?.instructions).toBe(SERVER_INSTRUCTIONS_INDEX_BUSY);
    expect(list?.result?.tools).toEqual(getStaticTools());
  });

  describe.skipIf(!nodeSqliteAvailable)('real index fixtures', () => {
    it('usable db (nodes>0) → SERVER_INSTRUCTIONS + nonempty getStaticTools()', () => {
      const root = track(makeRoot('cg-mcp-proxy-usable-'));
      makeDbWithNodes(path.join(root, '.codegraph', 'codegraph.db'), 5);
      const { writes } = driveHandshake(makeDeps(root), [initialize(1), toolsList(2)]);
      const init = writes.find((w) => w.id === 1);
      const list = writes.find((w) => w.id === 2);
      expect(init?.result?.instructions).toBe(SERVER_INSTRUCTIONS);
      expect(list?.result?.tools).toEqual(getStaticTools());
    });
  });
});

describe('runLocalHandshakeProxy — BT-1b pending daemon socket', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    process.stdin.removeAllListeners('data');
    process.stdin.removeAllListeners('end');
    process.stdin.removeAllListeners('close');
    process.stdin.removeAllListeners('error');
  });

  it('answers initialize to stdout while getDaemonSocket stays pending', () => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'cg-mcp-proxy-pending-'));
    fs.mkdirSync(path.join(root, '.codegraph'), { recursive: true });
    fs.writeFileSync(path.join(root, '.codegraph', 'codegraph.db'), 'placeholder so root resolves');
    // Never settles during the assertion window — an immediate-null stub does
    // NOT satisfy this pin (a regression that awaited the socket would pass a
    // instantly-resolved stub but hang the real ~6s poll).
    const neverSettles = new Promise<net.Socket | null>(() => {});
    const { writes } = driveHandshake(makeDeps(root, () => neverSettles), [initialize(1)]);
    // No await of the socket before the assert: listen-first means the reply is
    // written synchronously from the stdin handler.
    const init = writes.find((w) => w.id === 1);
    expect(init?.result?.instructions).toBe(SERVER_INSTRUCTIONS_UNINDEXED);
    try {
      fs.rmSync(root, { recursive: true, force: true });
    } catch {
      /* ignore */
    }
  });
});

describe('runLocalHandshakeProxy — m2 resolveMcpIndexState call-count', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    process.stdin.removeAllListeners('data');
    process.stdin.removeAllListeners('end');
    process.stdin.removeAllListeners('close');
    process.stdin.removeAllListeners('error');
  });

  it('calls resolveMcpIndexState ≥ 2 (once per initialize AND tools/list), each with deps.root', () => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'cg-mcp-proxy-count-'));
    fs.mkdirSync(path.join(root, '.codegraph'), { recursive: true });
    fs.writeFileSync(path.join(root, '.codegraph', 'codegraph.db'), 'placeholder so root resolves');
    const spy = vi.spyOn(indexState, 'resolveMcpIndexState');
    driveHandshake(makeDeps(root), [initialize(1), toolsList(2)]);
    expect(spy.mock.calls.length).toBeGreaterThanOrEqual(2);
    for (const call of spy.mock.calls) {
      expect(call[0]).toBe(root);
    }
    try {
      fs.rmSync(root, { recursive: true, force: true });
    } catch {
      /* ignore */
    }
  });
});
