/**
 * server-instructions — four byte-static instruction strings plus the
 * busy-first selector that maps an MCP index tri-state to the right
 * `initialize` payload (Bucket 5 spec component 1).
 *
 * The selector returns the BUSY copy BEFORE switching on `state` so a busy
 * index can never collapse into the empty copy. UNINDEXED is reworded to
 * "no usable index" and must NOT claim a missing `.codegraph/` directory
 * (the CLI still owns the directory-absence wording). EMPTY must not reuse
 * the "inactive this session" framing — tools stay listed there.
 */

import { describe, it, expect } from 'vitest';
import {
  SERVER_INSTRUCTIONS,
  SERVER_INSTRUCTIONS_UNINDEXED,
  SERVER_INSTRUCTIONS_INDEX_EMPTY,
  SERVER_INSTRUCTIONS_INDEX_BUSY,
  instructionsForMcpIndex,
} from '../src/mcp/server-instructions';

describe('instructionsForMcpIndex', () => {
  it('returns BUSY when busy, regardless of state', () => {
    expect(instructionsForMcpIndex({ state: 'index_empty', busy: true })).toBe(SERVER_INSTRUCTIONS_INDEX_BUSY);
  });

  it('returns EMPTY when empty and not busy', () => {
    expect(instructionsForMcpIndex({ state: 'index_empty', busy: false })).toBe(SERVER_INSTRUCTIONS_INDEX_EMPTY);
  });

  it('returns the full playbook when usable and not busy', () => {
    expect(instructionsForMcpIndex({ state: 'usable', busy: false })).toBe(SERVER_INSTRUCTIONS);
  });

  it('returns UNINDEXED when missing and not busy', () => {
    expect(instructionsForMcpIndex({ state: 'index_missing', busy: false })).toBe(SERVER_INSTRUCTIONS_UNINDEXED);
  });
});

describe('SERVER_INSTRUCTIONS_UNINDEXED copy', () => {
  it('contains "no usable index"', () => {
    expect(SERVER_INSTRUCTIONS_UNINDEXED).toContain('no usable index');
  });

  it('does not claim a missing `.codegraph/` directory', () => {
    expect(SERVER_INSTRUCTIONS_UNINDEXED).not.toContain('no `.codegraph/` directory');
  });
});

describe('SERVER_INSTRUCTIONS_INDEX_EMPTY copy', () => {
  it('does not say "inactive this session"', () => {
    expect(SERVER_INSTRUCTIONS_INDEX_EMPTY).not.toContain('inactive this session');
  });

  it('names `codegraph init` for the user to run', () => {
    expect(SERVER_INSTRUCTIONS_INDEX_EMPTY).toContain('codegraph init');
  });
});

describe('SERVER_INSTRUCTIONS_INDEX_BUSY copy', () => {
  it('says "Retry later"', () => {
    expect(SERVER_INSTRUCTIONS_INDEX_BUSY).toContain('Retry later');
  });
});
