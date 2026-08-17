/**
 * End-to-end guard for an unexpanded `${...}` path (spec component 6).
 *
 * Cursor passes `${workspaceFolder}` literally in agent/background windows
 * (the MCP host never substitutes it). Before the guard, `resolveProjectPath`
 * treated that as "no path given" and fell back to cwd — which walked up to
 * whatever index sat above cwd (in one incident, an accidental multi-GB
 * `$HOME` index). The fix makes a literal template path a hard, non-zero CLI
 * error at both doors (`--path` via `resolveProjectPath`, and `init [path]`)
 * instead of a silent fallback.
 *
 * Exercised against the built binary so the CLI wiring (not just the library)
 * is covered; `spawnSync` (not `execFileSync`) so a non-zero exit is observed
 * rather than thrown.
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { spawnSync } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { snapshotTree } from './fs-snapshot';

const BIN = path.resolve(__dirname, '../dist/bin/codegraph.js');
const TEMPLATE = '${workspaceFolder}';

function runCodegraph(args: string[], cwd: string) {
  return spawnSync(process.execPath, [BIN, ...args], {
    cwd,
    encoding: 'utf-8',
    env: { ...process.env, CODEGRAPH_NO_DAEMON: '1', CODEGRAPH_WASM_RELAUNCHED: '1' },
    timeout: 15000,
  });
}

describe('unexpanded template path refusal', () => {
  let tempDir: string;

  beforeEach(() => {
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'codegraph-unexpanded-'));
  });

  afterEach(() => {
    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  it('refuses an unexpanded path at the status door without falling back to cwd', () => {
    const before = snapshotTree(tempDir);

    // `status` takes the path positionally (`status [path]`) and routes it
    // through resolveProjectPath — the door the guard must close.
    const result = runCodegraph(['status', TEMPLATE], tempDir);

    // Hard error, not a silent cwd fallback.
    expect(result.status).not.toBe(0);
    // The message is on stderr (stdout is the MCP protocol channel elsewhere),
    // and it names the literal template + the fix.
    expect(result.stderr.length).toBeGreaterThan(0);
    expect(result.stderr).toContain(TEMPLATE);
    expect(result.stderr).toContain('Pass a real folder');
    expect(result.stderr).toContain('absolute folder in your MCP config');

    // Nothing was created — no fallback indexed/opened cwd.
    expect(fs.readdirSync(tempDir)).not.toContain(TEMPLATE);
    expect(snapshotTree(tempDir)).toEqual(before);
  });

  it('refuses an unexpanded init path and creates nothing', () => {
    const before = snapshotTree(tempDir);

    const result = runCodegraph(['init', TEMPLATE], tempDir);

    expect(result.status).not.toBe(0);
    expect(result.stderr.length).toBeGreaterThan(0);
    expect(result.stderr).toContain(TEMPLATE);
    expect(result.stderr).toContain('Pass a real folder');
    expect(result.stderr).toContain('absolute folder in your MCP config');

    // No `.codegraph/`, no literal `${workspaceFolder}` entry — anywhere.
    expect(fs.existsSync(path.join(tempDir, TEMPLATE))).toBe(false);
    expect(fs.existsSync(path.join(tempDir, '.codegraph'))).toBe(false);
    expect(snapshotTree(tempDir)).toEqual(before);
  });

  it('still resolves a bare path with no --path on a healthy project', () => {
    // Mini-graph fixture so `explore greet` has something to find.
    fs.writeFileSync(
      path.join(tempDir, 'a.ts'),
      `export function greet(name: string) { return hello(name); }\n` +
        `export function hello(n: string) { return 'hi ' + n; }\n`,
    );
    fs.writeFileSync(
      path.join(tempDir, 'b.ts'),
      `import { greet } from './a';\nexport function main() { return greet('world'); }\n`,
    );

    expect(runCodegraph(['init'], tempDir).status).toBe(0);

    const result = runCodegraph(['explore', 'greet'], tempDir);
    expect(result.status).toBe(0);
    expect(result.stdout).toContain('greet');
  });

  it('refuses an unexpanded --path at the serve door before it can hang', () => {
    const result = runCodegraph(['serve', '--mcp', '--path', TEMPLATE], tempDir);

    // Exits non-zero immediately instead of blocking on stdio MCP transport.
    expect(result.status).not.toBe(0);
    expect(result.stderr.length).toBeGreaterThan(0);
    expect(result.stderr).toContain(TEMPLATE);
    expect(result.stderr).toContain('absolute folder in your MCP config');
  });
});
