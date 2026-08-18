/**
 * probeIndexHealth — classify an existing CodeGraph index without mutating it.
 *
 * `probeIndexHealth` opens `.codegraph/codegraph.db` read-only via Node's
 * built-in `node:sqlite` and classifies it by a single `SELECT COUNT(*)` on
 * `nodes`. The fixtures here exercise every dispatch branch: junk text (26),
 * a truncated/smashed db (11), a db missing the `nodes` table (1 + `no such
 * table: nodes`), a locked db (5), chmod-000 (14), a directory at the db path
 * (266), empty, and usable — plus the two invariants that matter for the CLI:
 * the probe never mutates bytes (sha256 unchanged) and it always closes its
 * handle (a writable reopen still works).
 *
 * Skipped on Node < 22.5 where node:sqlite doesn't exist.
 */

import { describe, it, expect, afterEach } from 'vitest';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import * as crypto from 'crypto';
import { probeIndexHealth } from '../src/directory';

let nodeSqliteAvailable = false;
try {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  require('node:sqlite');
  nodeSqliteAvailable = true;
} catch {
  nodeSqliteAvailable = false;
}

function sha256(p: string): string {
  return crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
}

function openWritable(dbPath: string): { exec: (s: string) => void; prepare: (s: string) => any; close: () => void } {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { DatabaseSync } = require('node:sqlite');
  return new DatabaseSync(dbPath);
}

describe.skipIf(!nodeSqliteAvailable)('probeIndexHealth', () => {
  let root: string;
  let dbPath: string;

  function makeDbWithNodes(n: number): void {
    const db = openWritable(dbPath);
    db.exec('CREATE TABLE nodes(id INTEGER PRIMARY KEY, name TEXT)');
    const ins = db.prepare('INSERT INTO nodes(name) VALUES (?)');
    for (let i = 0; i < n; i++) ins.run(`sym${i}`);
    db.close();
  }

  afterEach(() => {
    // A chmod-000 fixture leaves the file unreadable; restore before removal.
    try {
      fs.chmodSync(dbPath, 0o644);
    } catch {
      /* ignore — path may be a directory or already gone */
    }
    fs.rmSync(root, { recursive: true, force: true });
  });

  it('classifies junk text as unreadable (errcode 26)', () => {
    root = fs.mkdtempSync(path.join(os.tmpdir(), 'cg-probe-'));
    fs.mkdirSync(path.join(root, '.codegraph'), { recursive: true });
    dbPath = path.join(root, '.codegraph', 'codegraph.db');
    fs.writeFileSync(dbPath, 'this is junk text, not a sqlite database');
    const r = probeIndexHealth(root);
    expect(r.status).toBe('unreadable');
    expect(r.errcode).toBe(26);
  });

  it('classifies a smashed/truncated db as unreadable (errcode 11)', () => {
    root = fs.mkdtempSync(path.join(os.tmpdir(), 'cg-probe-'));
    fs.mkdirSync(path.join(root, '.codegraph'), { recursive: true });
    dbPath = path.join(root, '.codegraph', 'codegraph.db');
    makeDbWithNodes(5000);
    // Truncate a real db mid-page: SQLite reports "database disk image is
    // malformed" (SQLITE_CORRUPT, errcode 11).
    const buf = fs.readFileSync(dbPath);
    fs.writeFileSync(dbPath, buf.subarray(0, 4096));
    const r = probeIndexHealth(root);
    expect(r.status).toBe('unreadable');
    expect(r.errcode).toBe(11);
  });

  it('classifies a db missing the nodes table as unreadable (errcode 1)', () => {
    root = fs.mkdtempSync(path.join(os.tmpdir(), 'cg-probe-'));
    fs.mkdirSync(path.join(root, '.codegraph'), { recursive: true });
    dbPath = path.join(root, '.codegraph', 'codegraph.db');
    const db = openWritable(dbPath);
    db.exec('CREATE TABLE foo(id INTEGER)');
    db.close();
    const r = probeIndexHealth(root);
    expect(r.status).toBe('unreadable');
    expect(r.errcode).toBe(1);
    expect(r.message).toContain('no such table: nodes');
  });

  it('classifies errcode 1 without "no such table: nodes" as unclassified', () => {
    // A view named `nodes` keeps the COUNT target resolvable by name, but its
    // body calls a function that does not exist — resolution is deferred until
    // query time, so CREATE succeeds and the probe fails with SQLITE_ERROR (1)
    // whose message is about the function, not a missing table.
    root = fs.mkdtempSync(path.join(os.tmpdir(), 'cg-probe-'));
    fs.mkdirSync(path.join(root, '.codegraph'), { recursive: true });
    dbPath = path.join(root, '.codegraph', 'codegraph.db');
    const db = openWritable(dbPath);
    db.exec('CREATE VIEW nodes AS SELECT nosuchfn() AS id');
    db.close();
    const r = probeIndexHealth(root);
    expect(r.status).toBe('unclassified');
    expect(r.errcode).toBe(1);
    expect(r.message).toContain('nosuchfn');
    expect(r.message).not.toContain('no such table: nodes');
  });

  it('classifies a locked db as busy (errcode 5)', () => {
    root = fs.mkdtempSync(path.join(os.tmpdir(), 'cg-probe-'));
    fs.mkdirSync(path.join(root, '.codegraph'), { recursive: true });
    dbPath = path.join(root, '.codegraph', 'codegraph.db');
    makeDbWithNodes(1);
    const holder = openWritable(dbPath);
    holder.exec('BEGIN EXCLUSIVE');
    try {
      const r = probeIndexHealth(root);
      expect(r.status).toBe('busy');
      expect(r.errcode).toBe(5);
    } finally {
      holder.exec('ROLLBACK');
      holder.close();
    }
  });

  it.runIf(process.platform !== 'win32' && process.getuid?.() !== 0)(
    'classifies a chmod-000 db as unclassified (errcode 14)',
    () => {
      root = fs.mkdtempSync(path.join(os.tmpdir(), 'cg-probe-'));
      fs.mkdirSync(path.join(root, '.codegraph'), { recursive: true });
      dbPath = path.join(root, '.codegraph', 'codegraph.db');
      fs.writeFileSync(dbPath, 'x');
      fs.chmodSync(dbPath, 0o000);
      const r = probeIndexHealth(root);
      expect(r.status).toBe('unclassified');
      expect(r.errcode).toBe(14);
    }
  );

  it('classifies a directory at the db path as unclassified (errcode 266)', () => {
    root = fs.mkdtempSync(path.join(os.tmpdir(), 'cg-probe-'));
    fs.mkdirSync(path.join(root, '.codegraph'), { recursive: true });
    dbPath = path.join(root, '.codegraph', 'codegraph.db');
    fs.mkdirSync(dbPath);
    const r = probeIndexHealth(root);
    expect(r.status).toBe('unclassified');
    expect(r.errcode).toBe(266);
  });

  it('classifies a zero-node db as empty', () => {
    root = fs.mkdtempSync(path.join(os.tmpdir(), 'cg-probe-'));
    fs.mkdirSync(path.join(root, '.codegraph'), { recursive: true });
    dbPath = path.join(root, '.codegraph', 'codegraph.db');
    makeDbWithNodes(0);
    const r = probeIndexHealth(root);
    expect(r.status).toBe('empty');
  });

  it('does not mutate an empty db (sha256 unchanged)', () => {
    root = fs.mkdtempSync(path.join(os.tmpdir(), 'cg-probe-'));
    fs.mkdirSync(path.join(root, '.codegraph'), { recursive: true });
    dbPath = path.join(root, '.codegraph', 'codegraph.db');
    makeDbWithNodes(0);
    const before = sha256(dbPath);
    const r = probeIndexHealth(root);
    expect(r.status).toBe('empty');
    expect(sha256(dbPath)).toBe(before);
  });

  it('documents that node:sqlite throws without a numeric errcode', () => {
    // Some node:sqlite throws carry no numeric `errcode` (e.g. a non-string
    // path is coerced and fails before SQLite reports an error). This pins the
    // guard the probe relies on: a throw with no numeric errcode must not crash
    // the catch dispatch.
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const { DatabaseSync } = require('node:sqlite');
    const open = () => new DatabaseSync(12345 as never);
    let caught: unknown;
    try {
      open();
    } catch (err) {
      caught = err;
    }
    expect(caught).toBeTruthy();
    expect(typeof (caught as { errcode?: unknown }).errcode).not.toBe('number');
  });

  it('classifies a db with nodes as usable', () => {
    root = fs.mkdtempSync(path.join(os.tmpdir(), 'cg-probe-'));
    fs.mkdirSync(path.join(root, '.codegraph'), { recursive: true });
    dbPath = path.join(root, '.codegraph', 'codegraph.db');
    makeDbWithNodes(5);
    const r = probeIndexHealth(root);
    expect(r.status).toBe('usable');
  });

  it('does not mutate the db (sha256 unchanged)', () => {
    root = fs.mkdtempSync(path.join(os.tmpdir(), 'cg-probe-'));
    fs.mkdirSync(path.join(root, '.codegraph'), { recursive: true });
    dbPath = path.join(root, '.codegraph', 'codegraph.db');
    makeDbWithNodes(10);
    const before = sha256(dbPath);
    const r = probeIndexHealth(root);
    expect(r.status).toBe('usable');
    expect(sha256(dbPath)).toBe(before);
  });

  it('closes its handle — a writable reopen still works after probe', () => {
    root = fs.mkdtempSync(path.join(os.tmpdir(), 'cg-probe-'));
    fs.mkdirSync(path.join(root, '.codegraph'), { recursive: true });
    dbPath = path.join(root, '.codegraph', 'codegraph.db');
    makeDbWithNodes(3);
    const r = probeIndexHealth(root);
    expect(r.status).toBe('usable');
    const db = openWritable(dbPath);
    const n = db.prepare('SELECT COUNT(*) AS n FROM nodes').get().n;
    expect(n).toBe(3);
    db.close();
  });
});
