/**
 * End-to-end coverage for the `codegraph` CLI's `index` and `init` commands.
 *
 * Two suites live here:
 *
 * 1. The #874 regression suite — `codegraph index` must be a true full rebuild
 *    (clear, then re-index) so it reproduces `init`'s node/edge counts instead
 *    of reporting "0 nodes, 0 edges".
 *
 * 2. The bucket-4 init-repair suite — `codegraph init` on an already-existing
 *    index must repair (empty → rebuild in place; unreadable → replace only the
 *    three SQLite files) or refuse (busy / unclassified → name the problem and
 *    touch nothing), never wipe `.codegraph/` blindly.
 *
 * Both are exercised against the built binary (`dist/bin/codegraph.js`) so the
 * CLI wiring — not just the library — is what's under test. The repair suite
 * uses `spawnSync` (not `execFileSync`) so a non-zero exit is observed rather
 * than thrown.
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { execFileSync, spawnSync, spawn, type ChildProcess } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { CodeGraph } from '../src';
import { snapshotTree, type Snapshot } from './fs-snapshot';
import { MINI_GRAPH_FILES, MINI_GRAPH_SYMBOLS } from './mini-graph-fixture';

const BIN = path.resolve(__dirname, '../dist/bin/codegraph.js');

/** The only three files an unreadable-index repair is allowed to remove. */
const DB_NAMES = ['codegraph.db', 'codegraph.db-wal', 'codegraph.db-shm'];

function codegraphDir(dir: string): string {
  return path.join(dir, '.codegraph');
}

function dbPath(dir: string): string {
  return path.join(codegraphDir(dir), 'codegraph.db');
}

function writeMiniGraph(dir: string): void {
  for (const [name, source] of Object.entries(MINI_GRAPH_FILES)) {
    fs.writeFileSync(path.join(dir, name), source);
  }
}

/** execFileSync helper for the #874 suite — throws on non-zero exit. */
function runCodegraph(args: string[], cwd: string): string {
  return execFileSync(process.execPath, [BIN, ...args], {
    cwd,
    encoding: 'utf-8',
    env: { ...process.env, CODEGRAPH_NO_DAEMON: '1' },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
}

/** spawnSync helper for the repair suite — observes non-zero exits. */
function runCodegraphRaw(args: string[], cwd: string, timeoutMs = 15000) {
  return spawnSync(process.execPath, [BIN, ...args], {
    cwd,
    encoding: 'utf-8',
    env: { ...process.env, CODEGRAPH_NO_DAEMON: '1', CODEGRAPH_WASM_RELAUNCHED: '1' },
    timeout: timeoutMs,
  });
}

/** Combined stdout+stderr — clack's log methods emit to stdout, not stderr. */
function outputOf(result: { stdout: string; stderr: string }): string {
  return result.stdout + result.stderr;
}

/** Open `.codegraph/codegraph.db` writable with Node's built-in SQLite. */
function openWritable(db: string): { exec: (s: string) => void; close: () => void } {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { DatabaseSync } = require('node:sqlite');
  return new DatabaseSync(db);
}

/**
 * Hold a SQLite write lock on the db from a *sibling* process (not the test
 * process) until killed. The lock must live in a separate process: a lock held
 * by the test process itself is not observed by the CLI it spawns (POSIX lock
 * semantics across the fork that `spawnSync` performs), so the busy fixture
 * needs a sibling holder. Resolves once the holder has printed `LOCKED`.
 */
function startLockHolder(db: string, journalMode: 'DELETE' | 'WAL'): Promise<ChildProcess> {
  const setDelete = journalMode === 'DELETE' ? "db.exec('PRAGMA journal_mode = DELETE');" : '';
  const script =
    "const {DatabaseSync}=require('node:sqlite');" +
    'const db=new DatabaseSync(process.argv[1]);' +
    setDelete +
    "db.exec('BEGIN EXCLUSIVE');" +
    "console.log('LOCKED');" +
    'setInterval(()=>{},1000);';
  const child = spawn(process.execPath, ['-e', script, db], {
    stdio: ['ignore', 'pipe', 'ignore'],
  });
  return new Promise<ChildProcess>((resolve, reject) => {
    let settled = false;
    const timer = setTimeout(() => {
      if (settled) return;
      settled = true;
      child.kill();
      reject(new Error('lock holder did not acquire the lock in time'));
    }, 5000);
    child.stdout.on('data', (chunk: Buffer) => {
      if (settled) return;
      if (chunk.toString().includes('LOCKED')) {
        settled = true;
        clearTimeout(timer);
        resolve(child);
      }
    });
    child.on('error', (err) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      reject(err);
    });
    child.on('exit', (code) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      reject(new Error(`lock holder exited early (code ${code})`));
    });
  });
}

function graphCounts(dir: string): { nodes: number; edges: number } {
  const cg = CodeGraph.openSync(dir);
  try {
    const stats = cg.getStats();
    return { nodes: stats.nodeCount, edges: stats.edgeCount };
  } finally {
    cg.close();
  }
}

/**
 * Prove a repair rebuilt a real graph — not just recreated empty tables.
 * `greet`/`hello`/`main` must all exist, `main` must call `greet`, and both
 * source files must be tracked. A dummy extra node would not satisfy this.
 */
function assertRepairProof(dir: string): void {
  const cg = CodeGraph.openSync(dir);
  try {
    for (const sym of [MINI_GRAPH_SYMBOLS.greet, MINI_GRAPH_SYMBOLS.hello, MINI_GRAPH_SYMBOLS.main]) {
      expect(cg.getNodesByName(sym).length).toBeGreaterThanOrEqual(1);
    }
    const main = cg.getNodesByName(MINI_GRAPH_SYMBOLS.main)[0];
    const callees = cg.getCallees(main.id);
    expect(
      callees.some(({ node, edge }) => edge.kind === 'calls' && node.name === MINI_GRAPH_SYMBOLS.greet),
    ).toBe(true);
    const files = cg.getFiles().map((f) => f.path);
    expect(files).toContain('a.ts');
    expect(files).toContain('b.ts');
  } finally {
    cg.close();
  }
}

/**
 * Assert an unreadable-index repair deleted only the three SQLite files: every
 * vanished entry must be one of `{codegraph.db, codegraph.db-wal,
 * codegraph.db-shm}`, and every other surviving entry must be byte-identical.
 */
function assertOnlySqliteFilesVanished(before: Snapshot, after: Snapshot): void {
  const allowed = new Set(DB_NAMES);
  for (const name of Object.keys(before)) {
    if (!(name in after)) {
      expect(allowed.has(name), `unexpected vanished entry: ${name}`).toBe(true);
    }
  }
  for (const name of Object.keys(before)) {
    if (!(name in after) || allowed.has(name)) continue;
    const b = before[name];
    const a = after[name];
    if (b.kind === 'file' && a.kind === 'file' && b.sha256 !== undefined && a.sha256 !== undefined) {
      expect(a.sha256, `sha256 changed for ${name}`).toBe(b.sha256);
    } else {
      expect(a).toEqual(b);
    }
  }
}

describe('codegraph index — full re-index keeps the graph populated (#874)', () => {
  let tempDir: string;

  beforeEach(() => {
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'codegraph-index-cmd-'));
    // A couple of files with a call edge so there is a non-trivial graph to
    // (fail to) reproduce.
    writeMiniGraph(tempDir);
  });

  afterEach(() => {
    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  it('reproduces init\'s node/edge counts instead of emptying the index', () => {
    runCodegraph(['init'], tempDir);
    const afterInit = graphCounts(tempDir);
    expect(afterInit.nodes).toBeGreaterThan(0);
    expect(afterInit.edges).toBeGreaterThan(0);

    const out = runCodegraph(['index'], tempDir);
    const afterIndex = graphCounts(tempDir);

    // The graph is still fully populated — `index` rebuilt it, it did not wipe it.
    expect(afterIndex.nodes).toBe(afterInit.nodes);
    expect(afterIndex.edges).toBe(afterInit.edges);

    // ...and the CLI reported the real counts, never the misleading "0 nodes".
    expect(out).not.toMatch(/\b0 nodes, 0 edges\b/);
    expect(out).toMatch(new RegExp(`\\b${afterInit.nodes} nodes\\b`));
  });

  it('is idempotent: a second index does not grow the graph', () => {
    runCodegraph(['init'], tempDir);
    runCodegraph(['index'], tempDir);
    const first = graphCounts(tempDir);
    runCodegraph(['index'], tempDir);
    const second = graphCounts(tempDir);

    // A clean rebuild each time — no duplicate (re-resolved) edges accumulating
    // across runs (the C# "+18 edges" symptom in the report).
    expect(second.nodes).toBe(first.nodes);
    expect(second.edges).toBe(first.edges);
  });

  it('--quiet path also rebuilds a populated graph', () => {
    runCodegraph(['init'], tempDir);
    const afterInit = graphCounts(tempDir);

    runCodegraph(['index', '--quiet'], tempDir);
    const afterIndex = graphCounts(tempDir);

    expect(afterIndex.nodes).toBe(afterInit.nodes);
    expect(afterIndex.edges).toBe(afterInit.edges);
  });
});

describe('codegraph init — repairs an unusable index and refuses to wipe anything else', () => {
  let tempDir: string;

  beforeEach(() => {
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'codegraph-init-repair-'));
  });

  afterEach(() => {
    // A chmod-000 fixture leaves the db unreadable; restore before removal.
    try {
      fs.chmodSync(dbPath(tempDir), 0o644);
    } catch {
      /* ignore — path may be a directory or already gone */
    }
    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  it('treats a usable index as a no-op: same bytes, no re-index', () => {
    writeMiniGraph(tempDir);
    expect(runCodegraphRaw(['init'], tempDir).status).toBe(0);

    const before = snapshotTree(codegraphDir(tempDir));
    const result = runCodegraphRaw(['init'], tempDir);
    const after = snapshotTree(codegraphDir(tempDir));

    expect(result.status).toBe(0);
    // The db file is untouched: same identity (inode) and same bytes (sha256).
    expect(after['codegraph.db'].ino).toBe(before['codegraph.db'].ino);
    expect(after['codegraph.db'].sha256).toBe(before['codegraph.db'].sha256);
    // No new index pass ran — "Already initialized" is the only marker.
    expect(outputOf(result)).not.toContain('Indexed ');
    expect(outputOf(result)).toContain('Already initialized');
  });

  it.runIf(process.platform !== 'win32')(
    'rebuilds an empty (0-node) index in place without replacing the db file',
    () => {
      writeMiniGraph(tempDir);
      expect(runCodegraphRaw(['init'], tempDir).status).toBe(0);

      // Empty the graph but keep the schema: the repair must rebuild it.
      const db = openWritable(dbPath(tempDir));
      db.exec('DELETE FROM nodes');
      db.close();

      const before = snapshotTree(codegraphDir(tempDir));
      const result = runCodegraphRaw(['init'], tempDir);
      const after = snapshotTree(codegraphDir(tempDir));

      expect(result.status).toBe(0);
      // In-place repair (open + clear + re-index) keeps the same inode; only a
      // fresh init (unlink + recreate) would change it.
      expect(after['codegraph.db'].ino).toBe(before['codegraph.db'].ino);
      assertRepairProof(tempDir);
    },
  );

  it.runIf(process.platform === 'win32')(
    'rebuilds an empty index without unlinking the db file (win32: no inode gate)',
    () => {
      writeMiniGraph(tempDir);
      expect(runCodegraphRaw(['init'], tempDir).status).toBe(0);

      const db = openWritable(dbPath(tempDir));
      db.exec('DELETE FROM nodes');
      db.close();

      // The CLI runs in a child process, so spy on the child's fs.unlinkSync via
      // a `-r` preload that logs every unlinked path. The empty repair must not
      // unlink the db (win32 `stat.ino` is null, so inode can't gate identity).
      const spyLog = path.join(tempDir, 'unlink-spy.log');
      const preload = path.join(tempDir, 'unlink-spy.cjs');
      fs.writeFileSync(
        preload,
        "const fs = require('fs');" +
          "const orig = fs.unlinkSync.bind(fs);" +
          "fs.unlinkSync = function (p) {" +
          "  try { fs.appendFileSync(process.env.CG_UNLINK_SPY, String(p) + '\\n'); } catch {}" +
          "  return orig(p);" +
          '};',
      );

      const result = spawnSync(process.execPath, ['-r', preload, BIN, 'init'], {
        cwd: tempDir,
        encoding: 'utf-8',
        env: {
          ...process.env,
          CODEGRAPH_NO_DAEMON: '1',
          CODEGRAPH_WASM_RELAUNCHED: '1',
          CG_UNLINK_SPY: spyLog,
        },
        timeout: 30000,
      });

      expect(result.status).toBe(0);
      const unlinked = fs.existsSync(spyLog)
        ? fs.readFileSync(spyLog, 'utf-8').split('\n').filter(Boolean).map((p) => path.normalize(p))
        : [];
      expect(unlinked).not.toContain(path.normalize(dbPath(tempDir)));
      assertRepairProof(tempDir);
    },
  );

  it('replaces a junk-text index plus a leftover -wal with a fresh index', () => {
    writeMiniGraph(tempDir);
    fs.mkdirSync(codegraphDir(tempDir), { recursive: true });
    fs.writeFileSync(dbPath(tempDir), 'this is junk text, not a sqlite database');
    fs.writeFileSync(path.join(codegraphDir(tempDir), 'codegraph.db-wal'), 'leftover-wal-bytes');
    // A non-sqlite entry that must survive repair — the file `init` writes to
    // keep the index out of git, planted by hand so the "no prior init" shape
    // of this fixture is preserved.
    fs.writeFileSync(path.join(codegraphDir(tempDir), '.gitignore'), '*\n!.gitignore\n');

    const before = snapshotTree(codegraphDir(tempDir));
    const result = runCodegraphRaw(['init'], tempDir);
    const after = snapshotTree(codegraphDir(tempDir));

    expect(result.status).toBe(0);
    assertOnlySqliteFilesVanished(before, after);
    // Catches a `-wal` surviving byte-identical — NOT unlink-db-only, because
    // SQLite removes a stale `-wal` itself on a clean close.
    expect(
      after['codegraph.db-wal'] === undefined ||
        after['codegraph.db-wal'].sha256 !== before['codegraph.db-wal'].sha256,
      'leftover -wal must be absent or rewritten',
    ).toBe(true);
    assertRepairProof(tempDir);
  });

  it('replaces a truncated (smashed) index plus a leftover -wal with a fresh index', () => {
    writeMiniGraph(tempDir);
    expect(runCodegraphRaw(['init'], tempDir).status).toBe(0);

    // Truncate a real db mid-page: SQLite reports "database disk image is
    // malformed" (SQLITE_CORRUPT, errcode 11).
    const buf = fs.readFileSync(dbPath(tempDir));
    fs.writeFileSync(dbPath(tempDir), buf.subarray(0, 4096));
    fs.writeFileSync(path.join(codegraphDir(tempDir), 'codegraph.db-wal'), 'leftover-wal-bytes');

    const before = snapshotTree(codegraphDir(tempDir));
    const result = runCodegraphRaw(['init'], tempDir);
    const after = snapshotTree(codegraphDir(tempDir));

    expect(result.status).toBe(0);
    assertOnlySqliteFilesVanished(before, after);
    // Catches a `-wal` surviving byte-identical — NOT unlink-db-only, because
    // SQLite removes a stale `-wal` itself on a clean close.
    expect(
      after['codegraph.db-wal'] === undefined ||
        after['codegraph.db-wal'].sha256 !== before['codegraph.db-wal'].sha256,
      'leftover -wal must be absent or rewritten',
    ).toBe(true);
    assertRepairProof(tempDir);
  });

  it('replaces a hollow (no nodes table) index plus a leftover -wal with a fresh index', () => {
    writeMiniGraph(tempDir);
    fs.mkdirSync(codegraphDir(tempDir), { recursive: true });
    const db = openWritable(dbPath(tempDir));
    db.exec('CREATE TABLE foo(id INTEGER)');
    db.close();
    fs.writeFileSync(path.join(codegraphDir(tempDir), 'codegraph.db-wal'), 'leftover-wal-bytes');
    // A non-sqlite entry that must survive repair — the file `init` writes to
    // keep the index out of git, planted by hand so the "no prior init" shape
    // of this fixture is preserved.
    fs.writeFileSync(path.join(codegraphDir(tempDir), '.gitignore'), '*\n!.gitignore\n');

    const before = snapshotTree(codegraphDir(tempDir));
    const result = runCodegraphRaw(['init'], tempDir);
    const after = snapshotTree(codegraphDir(tempDir));

    expect(result.status).toBe(0);
    assertOnlySqliteFilesVanished(before, after);
    // Catches a `-wal` surviving byte-identical — NOT unlink-db-only, because
    // SQLite removes a stale `-wal` itself on a clean close.
    expect(
      after['codegraph.db-wal'] === undefined ||
        after['codegraph.db-wal'].sha256 !== before['codegraph.db-wal'].sha256,
      'leftover -wal must be absent or rewritten',
    ).toBe(true);
    // The hollow db had no `nodes` table, so the only way this passes is that
    // the repair actually rebuilt the index — not merely "deleted nothing extra".
    assertRepairProof(tempDir);
  });

  it('refuses a locked (non-WAL) index and touches nothing', { timeout: 30000 }, async () => {
    writeMiniGraph(tempDir);
    expect(runCodegraphRaw(['init'], tempDir).status).toBe(0);

    // A non-WAL db: a held EXCLUSIVE transaction blocks even a read-only probe.
    // The lock lives in a sibling process: `snapshotTree` (taken below) reads
    // the db bytes, and on POSIX closing any fd to the file releases all of
    // *this process's* locks on it — so an in-process holder would silently
    // drop its EXCLUSIVE lock before the CLI probe ever sees it.
    const holder = await startLockHolder(dbPath(tempDir), 'DELETE');
    try {
      const before = snapshotTree(codegraphDir(tempDir));
      const result = runCodegraphRaw(['init'], tempDir);

      expect(result.status).not.toBe(0);
      expect(outputOf(result)).toContain(dbPath(tempDir));
      expect(outputOf(result)).toContain('codegraph daemon');
      expect(snapshotTree(codegraphDir(tempDir))).toEqual(before);
    } finally {
      holder.kill();
    }
  });

  it(
    'refuses a locked (WAL write-path) empty index without unlinking it',
    { timeout: 30000 },
    () => {
      writeMiniGraph(tempDir);
      expect(runCodegraphRaw(['init'], tempDir).status).toBe(0);

      // Empty schema, still WAL: the probe's read succeeds (WAL readers are not
      // blocked), so the repair proceeds to the write-path, where the held
      // EXCLUSIVE lock makes `clear()` throw SQLITE_BUSY (errcode 5).
      const db = openWritable(dbPath(tempDir));
      db.exec('DELETE FROM nodes');
      db.close();

      const holder = openWritable(dbPath(tempDir));
      holder.exec('BEGIN EXCLUSIVE');
      try {
        const beforeIno = fs.statSync(dbPath(tempDir)).ino;
        const result = runCodegraphRaw(['init'], tempDir, 30000);

        expect(result.status).not.toBe(0);
        expect(outputOf(result)).toContain(dbPath(tempDir));
        expect(outputOf(result)).toContain('codegraph daemon');
        // No unlink — the locked db is still the same file (same inode), not a
        // replacement recreated at the same path.
        expect(fs.statSync(dbPath(tempDir)).ino).toBe(beforeIno);
      } finally {
        holder.exec('ROLLBACK');
        holder.close();
      }
    },
  );

  it('refuses a directory at the db path (errcode 266) and leaves it in place', () => {
    writeMiniGraph(tempDir);
    fs.mkdirSync(dbPath(tempDir), { recursive: true });

    const before = snapshotTree(codegraphDir(tempDir));
    const result = runCodegraphRaw(['init'], tempDir);

    expect(result.status).not.toBe(0);
    expect(outputOf(result)).toContain('errcode 266');
    expect(outputOf(result)).not.toContain('errcode 14');
    // The directory entry is untouched — same kind, same inode.
    expect(snapshotTree(codegraphDir(tempDir))).toEqual(before);
  });

  it.runIf(process.platform !== 'win32' && process.getuid?.() !== 0)(
    'refuses a chmod-000 index (errcode 14) without deleting it',
    () => {
      fs.mkdirSync(codegraphDir(tempDir), { recursive: true });
      fs.writeFileSync(dbPath(tempDir), 'x');
      fs.chmodSync(dbPath(tempDir), 0o000);

      const before = snapshotTree(codegraphDir(tempDir));
      const result = runCodegraphRaw(['init'], tempDir);
      const after = snapshotTree(codegraphDir(tempDir));

      expect(result.status).not.toBe(0);
      expect(outputOf(result)).toContain('errcode 14');
      // The file is observed by identity + an unreadable sentinel — never by a
      // sha256 of bytes that cannot be read.
      expect(after['codegraph.db']).toEqual({
        kind: 'file',
        ino: before['codegraph.db'].ino,
        hash: '<unreadable>',
      });
      expect(after['codegraph.db'].sha256).toBeUndefined();
    },
  );

  it('refuses a nodes-only index (errcode 1, missing unresolved_refs) without deleting it', () => {
    writeMiniGraph(tempDir);
    fs.mkdirSync(codegraphDir(tempDir), { recursive: true });
    const db = openWritable(dbPath(tempDir));
    db.exec('CREATE TABLE nodes(id INTEGER PRIMARY KEY, name TEXT)');
    db.close();

    const before = snapshotTree(codegraphDir(tempDir));
    const result = runCodegraphRaw(['init'], tempDir);

    expect(result.status).not.toBe(0);
    expect(outputOf(result)).toContain('errcode 1');
    expect(outputOf(result)).toContain('unresolved_refs');
    // The db file survives — refused init never unlinks it (same inode). The
    // tree is NOT byte-identical here: `CodeGraph.open` → `validateDirectory`
    // writes `.gitignore` and `configureConnection` sets WAL (creating -wal/-shm
    // and rewriting the db header) before the missing-table check fails, so an
    // identity gate is the correct contract, not a full snapshot equality.
    expect(fs.statSync(dbPath(tempDir)).ino).toBe(before['codegraph.db'].ino);
  });
});
