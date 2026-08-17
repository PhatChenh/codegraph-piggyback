/**
 * Test-only filesystem snapshot helper.
 *
 * Records every entry under a directory as a plain object keyed by the
 * entry's relative name, capturing enough to prove both identity (inode) and
 * content (sha256) across a CLI mutation: a file that was merely touched
 * still shows a new inode, a file whose bytes changed still shows a new
 * sha256, and an unreadable file still shows up (with a sentinel hash instead
 * of a digest — you cannot hash bytes you cannot read).
 *
 * Used by the bucket-4 CLI E2E suites to assert "the mutation touched exactly
 * these names and nothing else."
 */

import * as fs from 'fs';
import * as path from 'path';
import { createHash } from 'crypto';

export type SnapshotEntry =
  | { kind: 'file'; ino: number; sha256?: string; hash?: '<unreadable>' }
  | { kind: 'dir'; ino: number }
  | { kind: 'symlink'; ino: number; target: string };

export type Snapshot = Record<string, SnapshotEntry>;

export function snapshotTree(dir: string): Snapshot {
  const snapshot: Snapshot = {};
  for (const entry of fs.readdirSync(dir)) {
    const full = path.join(dir, entry);
    const stat = fs.lstatSync(full);
    if (stat.isSymbolicLink()) {
      snapshot[entry] = {
        kind: 'symlink',
        ino: stat.ino,
        target: fs.readlinkSync(full),
      };
    } else if (stat.isDirectory()) {
      snapshot[entry] = { kind: 'dir', ino: stat.ino };
    } else if (stat.isFile()) {
      try {
        fs.accessSync(full, fs.constants.R_OK);
      } catch {
        // Unreadable file: we can still observe its identity, but there is no
        // readable content to hash.
        snapshot[entry] = { kind: 'file', ino: stat.ino, hash: '<unreadable>' };
        continue;
      }
      snapshot[entry] = {
        kind: 'file',
        ino: stat.ino,
        sha256: createHash('sha256').update(fs.readFileSync(full)).digest('hex'),
      };
    }
  }
  return snapshot;
}
