/**
 * Known-answer + mutation tests for the test-only `snapshotTree` helper.
 *
 * The known-answer digest is a fixed oracle: the fixture file
 * `fixtures/bkt4-known-answer.txt` holds exactly the bytes
 * `bkt4-known-answer-v1\n`, whose sha256 is the literal below. The expected
 * hex is pasted here verbatim (never computed by calling the helper) so that
 * a helper which silently returns `''` (or the wrong digest) fails this test
 * rather than ratifying itself.
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { snapshotTree } from './fs-snapshot';

const FIXTURE = path.resolve(__dirname, 'fixtures', 'bkt4-known-answer.txt');

// sha256 of the literal bytes `bkt4-known-answer-v1\n` (UTF-8).
const KNOWN_ANSWER_SHA256 =
  '0f1838a54d465456862a5d44d65cecbc043a495897a45777a4986d8a3d1a2cdb';

describe('snapshotTree known-answer', () => {
  let tempDir: string;

  beforeEach(() => {
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'codegraph-snapshot-'));
  });

  afterEach(() => {
    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  it('matches the committed known-answer fixture against the pasted oracle', () => {
    fs.copyFileSync(FIXTURE, path.join(tempDir, 'bkt4-known-answer.txt'));
    const snap = snapshotTree(tempDir);
    expect(snap['bkt4-known-answer.txt'].kind).toBe('file');
    const entry = snap['bkt4-known-answer.txt'] as { sha256?: string };
    expect(entry.sha256).toBe(KNOWN_ANSWER_SHA256);
  });

  it('mutating a byte changes the sha256', () => {
    fs.writeFileSync(path.join(tempDir, 'f.txt'), 'bkt4-known-answer-v1\n');
    const before = snapshotTree(tempDir);
    fs.writeFileSync(path.join(tempDir, 'f.txt'), 'bkt4-known-answer-v2\n');
    const after = snapshotTree(tempDir);
    const a = before['f.txt'] as { sha256?: string };
    const b = after['f.txt'] as { sha256?: string };
    expect(a.sha256).toBe(KNOWN_ANSWER_SHA256);
    expect(b.sha256).not.toBe(a.sha256);
  });

  it('adding an entry adds a key', () => {
    fs.writeFileSync(path.join(tempDir, 'a.txt'), 'a\n');
    const before = snapshotTree(tempDir);
    expect(Object.keys(before)).toEqual(['a.txt']);
    fs.writeFileSync(path.join(tempDir, 'b.txt'), 'b\n');
    const after = snapshotTree(tempDir);
    expect(Object.keys(after).sort()).toEqual(['a.txt', 'b.txt']);
  });

  it('replacing a file with a symlink changes kind and records target', () => {
    const target = path.join(tempDir, 'real.txt');
    fs.writeFileSync(target, 'x\n');
    const link = path.join(tempDir, 'entry.txt');
    fs.writeFileSync(link, 'old bytes\n');
    const before = snapshotTree(tempDir);
    expect(before['entry.txt'].kind).toBe('file');

    fs.rmSync(link);
    fs.symlinkSync('real.txt', link);
    const after = snapshotTree(tempDir);
    expect(after['entry.txt'].kind).toBe('symlink');
    const entry = after['entry.txt'] as { target: string };
    expect(entry.target).toBe('real.txt');
  });

  it.runIf(process.platform !== 'win32' && process.getuid?.() !== 0)(
    'records an unreadable file as {ino, hash:<unreadable>} without hashing',
    () => {
      const p = path.join(tempDir, 'secret.txt');
      fs.writeFileSync(p, 'bkt4-known-answer-v1\n');
      fs.chmodSync(p, 0o000);
      try {
        const snap = snapshotTree(tempDir);
        const entry = snap['secret.txt'];
        expect(entry.kind).toBe('file');
        expect(entry).toHaveProperty('ino');
        expect(entry).toHaveProperty('hash', '<unreadable>');
        expect(entry).not.toHaveProperty('sha256');
      } finally {
        fs.chmodSync(p, 0o600);
      }
    },
  );
});
