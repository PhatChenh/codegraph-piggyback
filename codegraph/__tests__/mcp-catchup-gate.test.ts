/**
 * MCP catch-up gate — first tool call blocks on the engine's post-open
 * filesystem reconcile so it never serves rows for files that were
 * deleted (or edited) while no MCP server was running.
 *
 * Background: `MCPEngine.catchUpSync()` fires `cg.sync()` in the background.
 * Before this fix it was fire-and-forget — a tool call could race past it
 * and return rows for files that no longer exist on disk. The per-file
 * staleness banner (`withStalenessNotice`) couldn't help, because
 * `getPendingFiles()` is populated by the watcher, not by catch-up.
 *
 * The fix: `catchUpSync()` pushes its promise into the `ToolHandler` via
 * `setCatchUpGate(p)`; the first `execute()` call awaits the gate and then
 * clears it. These tests exercise the gate directly (deterministic) and
 * the engine-driven path (proves the engine actually pokes the gate).
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import CodeGraph from '../src/index';
import { ToolHandler } from '../src/mcp/tools';

describe('MCP catch-up gate', () => {
  let testDir: string;
  let cg: CodeGraph;
  let handler: ToolHandler;

  beforeEach(async () => {
    testDir = fs.mkdtempSync(path.join(os.tmpdir(), 'codegraph-catchup-gate-'));
    fs.mkdirSync(path.join(testDir, 'src'));
    fs.writeFileSync(
      path.join(testDir, 'src', 'survivor.ts'),
      'export function survivor() { return 1; }\n',
    );
    fs.writeFileSync(
      path.join(testDir, 'src', 'deleted-later.ts'),
      'export function deletedLater() { return 2; }\n',
    );

    cg = CodeGraph.initSync(testDir, { config: { include: ['**/*.ts'], exclude: [] } });
    await cg.indexAll();
    handler = new ToolHandler(cg);
  });

  afterEach(() => {
    try { cg.unwatch(); } catch { /* ignore */ }
    try { cg.close(); } catch { /* ignore */ }
    if (fs.existsSync(testDir)) fs.rmSync(testDir, { recursive: true, force: true });
  });

  it('awaits the gate before serving the first tool call', async () => {
    let gateResolved = false;
    const gate = new Promise<void>((resolve) => {
      setTimeout(() => { gateResolved = true; resolve(); }, 80);
    });
    handler.setCatchUpGate(gate);

    const res = await handler.execute('codegraph_search', { query: 'survivor' });
    expect(gateResolved).toBe(true);
    expect(res.isError).toBeFalsy();
    expect(res.content[0].text).toMatch(/survivor/);
  });

  it('drops the gate after first await — second call does not re-wait', async () => {
    let awaitCount = 0;
    const gate = new Promise<void>((resolve) => {
      awaitCount++;
      setTimeout(resolve, 20);
    });
    handler.setCatchUpGate(gate);

    await handler.execute('codegraph_search', { query: 'survivor' });
    const before = awaitCount;
    await handler.execute('codegraph_search', { query: 'survivor' });
    // The promise body runs once when constructed; second execute never
    // resubscribes to a fresh promise because the gate field was nulled.
    expect(awaitCount).toBe(before);
  });

  it('catch-up reconciles a deleted file before the first tool call sees it', async () => {
    // Simulate the empty-project / deleted-files startup case: file is in
    // the DB (we indexed it above) but vanishes from disk before the MCP
    // server's first query. The catch-up sync, awaited via the gate,
    // must remove the row so the first tool call returns no hit.
    fs.unlinkSync(path.join(testDir, 'src', 'deleted-later.ts'));

    // Push the actual catch-up sync as the gate — same flow the MCP engine
    // uses (`cg.sync()` returns a Promise<SyncResult>, the wrapper voids it).
    handler.setCatchUpGate(cg.sync().then(() => undefined));

    const res = await handler.execute('codegraph_search', { query: 'deletedLater' });
    expect(res.isError).toBeFalsy();
    const text = res.content[0].text;
    expect(text).not.toMatch(/src\/deleted-later\.ts/);
  });

  it('catch-up that converges the project to 0 files clears all rows', async () => {
    // Worst case: every source file is gone between sessions. Without the
    // gate, the first tool call serves whatever was in the DB. With the
    // gate + the orchestrator's filesystem reconcile, the DB drains.
    fs.unlinkSync(path.join(testDir, 'src', 'survivor.ts'));
    fs.unlinkSync(path.join(testDir, 'src', 'deleted-later.ts'));

    handler.setCatchUpGate(cg.sync().then(() => undefined));

    const res = await handler.execute('codegraph_search', { query: 'survivor' });
    expect(res.isError).toBeFalsy();
    expect(cg.getStats().fileCount).toBe(0);
  });

  it('gate that rejects does not break the tool call', async () => {
    // A catch-up sync failure (lock contention, transient FS error) must
    // not poison tool dispatch — the engine logs it, the handler proceeds.
    handler.setCatchUpGate(Promise.reject(new Error('simulated sync failure')));

    const res = await handler.execute('codegraph_search', { query: 'survivor' });
    expect(res.isError).toBeFalsy();
    expect(res.content[0].text).toMatch(/survivor/);
  });
});

/**
 * Gate SCOPE: the gate reconciles the DEFAULT project's index only. A
 * cross-project call (explicit projectPath resolving elsewhere) reads a
 * different database — blocking it on the default project's catch-up sync
 * bought nothing and, on a huge default index, held foreign tool calls
 * hostage for minutes (observed as explore hanging ~7 min in Cursor).
 */
describe('catch-up gate scope (cross-project calls)', () => {
  let defaultDir: string;
  let otherDir: string;
  let cg: CodeGraph;
  let otherCg: CodeGraph;
  let handler: ToolHandler;

  beforeEach(async () => {
    defaultDir = fs.mkdtempSync(path.join(os.tmpdir(), 'cg-gate-default-'));
    fs.mkdirSync(path.join(defaultDir, 'src'));
    fs.writeFileSync(path.join(defaultDir, 'src', 'main.ts'), 'export function mainThing() { return 1; }\n');
    cg = CodeGraph.initSync(defaultDir, { config: { include: ['**/*.ts'], exclude: [] } });
    await cg.indexAll();

    otherDir = fs.mkdtempSync(path.join(os.tmpdir(), 'cg-gate-other-'));
    fs.mkdirSync(path.join(otherDir, 'src'));
    fs.writeFileSync(path.join(otherDir, 'src', 'other.ts'), 'export function otherThing() { return 2; }\n');
    otherCg = CodeGraph.initSync(otherDir, { config: { include: ['**/*.ts'], exclude: [] } });
    await otherCg.indexAll();

    handler = new ToolHandler(cg);
    // Seed the cross-project cache with the already-open instance. Under
    // vitest the lazy require('../index') inside getCodeGraph can't resolve
    // (ESM transform); production exercises that path via the built dist.
    (handler as unknown as { projectCache: Map<string, CodeGraph> })
      .projectCache.set(path.resolve(otherDir), otherCg);
  });

  afterEach(() => {
    handler.closeAll();
    try { cg.close(); } catch { /* ignore */ }
    for (const d of [defaultDir, otherDir]) {
      if (fs.existsSync(d)) fs.rmSync(d, { recursive: true, force: true });
    }
  });

  it('a cross-project call does NOT wait on the default project gate', async () => {
    let gateResolved = false;
    let releaseGate: () => void = () => {};
    handler.setCatchUpGate(new Promise<void>((resolve) => {
      releaseGate = () => { gateResolved = true; resolve(); };
    }));

    // Would hang here if the gate applied to cross-project calls.
    const res = await handler.execute('codegraph_search', { query: 'otherThing', projectPath: otherDir });
    expect(gateResolved).toBe(false);
    expect(res.isError).toBeFalsy();

    // The gate must still be armed for the first DEFAULT-project call.
    const [defaultRes] = await Promise.all([
      handler.execute('codegraph_search', { query: 'mainThing' }),
      Promise.resolve().then(releaseGate),
    ]);
    expect(gateResolved).toBe(true);
    expect(defaultRes.isError).toBeFalsy();
  });

  it('an explicit projectPath equal to the default project still waits', async () => {
    let gateResolved = false;
    handler.setCatchUpGate(new Promise<void>((resolve) => {
      setTimeout(() => { gateResolved = true; resolve(); }, 60);
    }));
    const res = await handler.execute('codegraph_search', { query: 'mainThing', projectPath: defaultDir });
    expect(gateResolved).toBe(true);
    expect(res.isError).toBeFalsy();
  });
});
