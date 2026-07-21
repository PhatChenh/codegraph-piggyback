/**
 * codegraph_explore — empty-index / wrong-tree warning (Wave E).
 *
 * Empty-index or wrong-tree queries used to return a silent "No relevant code
 * found" — indistinguishable from a healthy no-match — and a worker looping on
 * the same query burns a whole session (agent_village §2/§9/§11). When the
 * index is empty or belongs to a different git working tree, the result must
 * carry an explicit warning so the model stops calling.
 *
 * Healthy no-match (populated index + a name that doesn't exist) MUST stay
 * silent — false positives teach abandonment (see server-instructions).
 *
 * Tests drive real `CodeGraph` + real `ToolHandler.execute()` against temp
 * dirs; the wrong-tree case uses real `git worktree add` (no mocking), same
 * as worktree-detection.test.ts.
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { execFileSync } from 'child_process';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import CodeGraph from '../src/index';
import { ToolHandler } from '../src/mcp/tools';

function git(cwd: string, ...args: string[]): void {
  execFileSync('git', args, { cwd, stdio: ['ignore', 'ignore', 'ignore'] });
}

/** realpath so macOS /var → /private/var symlinking doesn't break equality. */
function real(p: string): string {
  return fs.realpathSync(path.resolve(p));
}

describe('codegraph_explore — empty-index / wrong-tree warning', () => {
  describe('empty index', () => {
    let testDir: string;
    let cg: CodeGraph;
    let handler: ToolHandler;

    beforeEach(() => {
      testDir = fs.mkdtempSync(path.join(os.tmpdir(), 'cg-empty-explore-'));
      // Empty project dir — no files written. initSync alone (no indexAll) leaves
      // the index with 0 nodes / 0 files, which is exactly the silent-empty case.
      cg = CodeGraph.initSync(testDir, { config: { include: ['**/*.ts'], exclude: [] } });
      handler = new ToolHandler(cg);
    });

    afterEach(() => {
      try { cg.destroy(); } catch { /* best effort */ }
      if (fs.existsSync(testDir)) fs.rmSync(testDir, { recursive: true, force: true });
    });

    it('returns an explicit warning when the index is empty', async () => {
      // Sanity: the test setup really produced an empty index.
      expect(cg.getStats().nodeCount).toBe(0);

      const res = await handler.execute('codegraph_explore', { query: 'anything' });
      const text = res.content[0].text;

      expect(res.isError).toBeFalsy();
      // Warning is surfaced IN the result so the model sees it and breaks the loop.
      expect(text).toMatch(/index is empty|0 nodes indexed/i);
      // The original no-match message is still present (kept as the second line).
      expect(text).toContain('No relevant code found');
      // The fix is named — agent must be able to act on it without guessing.
      expect(text).toContain('codegraph init');
    });

    it('returns the warning via projectPath too (same code path)', async () => {
      // An agent in another cwd that passes projectPath explicitly should get
      // the same warning — the empty-index check must not depend on
      // defaultProjectHint / cwd.
      const res = await handler.execute('codegraph_explore', {
        query: 'anything',
        projectPath: testDir,
      });
      const text = res.content[0].text;
      expect(text).toMatch(/index is empty|0 nodes indexed/i);
    });
  });

  describe('wrong-tree (issue #155 family, Wave E)', () => {
    let mainRepo: string;
    let worktree: string;
    let cg: CodeGraph;
    let handler: ToolHandler;

    beforeEach(async () => {
      mainRepo = fs.mkdtempSync(path.join(os.tmpdir(), 'cg-empty-wt-main-'));
      git(mainRepo, 'init', '-q');
      git(mainRepo, 'config', 'user.email', 'test@example.com');
      git(mainRepo, 'config', 'user.name', 'Test');
      git(mainRepo, 'config', 'commit.gpgsign', 'false');
      fs.mkdirSync(path.join(mainRepo, 'src'));
      // Populated index in the MAIN checkout so the agent in the worktree
      // walks up to a non-empty parent index — the empty-index branch above
      // can't fire, isolating the wrong-tree branch under test.
      fs.writeFileSync(
        path.join(mainRepo, 'src', 'feature.ts'),
        'export function mainOnly() { return 1; }\n',
      );
      git(mainRepo, 'add', '.');
      git(mainRepo, 'commit', '-q', '-m', 'init');

      cg = CodeGraph.initSync(mainRepo);
      await cg.indexAll();

      // Nested worktree — walks up to the main checkout's .codegraph, the
      // exact "borrowed another worktree's index" case detectWorktreeIndexMismatch
      // was built for.
      worktree = path.join(mainRepo, 'wt');
      git(mainRepo, 'worktree', 'add', '-q', '-b', 'feature', worktree);

      handler = new ToolHandler(cg);
    });

    afterEach(() => {
      try { cg.destroy(); } catch { /* best effort */ }
      try { git(mainRepo, 'worktree', 'remove', '--force', worktree); } catch { /* best effort */ }
      if (fs.existsSync(mainRepo)) fs.rmSync(mainRepo, { recursive: true, force: true });
    });

    it('emits the wrong-tree warning when explore returns zero results', async () => {
      handler.setDefaultProjectHint(worktree);

      // Query for a symbol that doesn't exist in the main checkout's index —
      // findRelevantContext returns an empty subgraph, triggering the empty-result
      // branch we just added. The wrong-tree detector still fires because
      // worktree ≠ mainRepo.
      const res = await handler.execute('codegraph_explore', {
        query: 'nonexistentSymbolName',
      });
      const text = res.content[0].text;

      expect(res.isError).toBeFalsy();
      expect(text).toContain('different git worktree');
      expect(text).toContain(real(mainRepo));
      expect(text).toContain(real(worktree));
      expect(text).toContain('codegraph init');
      // Original no-match message is still in the payload.
      expect(text).toContain('No relevant code found');
    });

    it('does NOT warn on a healthy no-match against a populated index', async () => {
      // Same handler, same populated mainRepo index, but the default project
      // hint is the MAIN checkout itself — no worktree mismatch. The query
      // misses, but the index is healthy and populated. This must stay silent
      // so agents don't learn to ignore a real "no match" signal.
      handler.setDefaultProjectHint(mainRepo);

      const res = await handler.execute('codegraph_explore', {
        query: 'definitelyNotASymbol',
      });
      const text = res.content[0].text;

      expect(res.isError).toBeFalsy();
      expect(text).toContain('No relevant code found');
      // CRITICAL: no warning on a legitimate no-match against a healthy
      // populated index. The index is non-empty and not borrowed, so both
      // detection branches must return null/0.
      expect(text).not.toMatch(/index is empty|0 nodes indexed/);
      expect(text).not.toContain('different git worktree');
    });

    it('does NOT warn on a healthy no-match against the populated index (own projectPath)', async () => {
      // Same idea, but the agent passes projectPath explicitly (= mainRepo)
      // instead of relying on the default hint. Same code path through
      // worktreeMismatchFor, same no-warning expectation.
      const res = await handler.execute('codegraph_explore', {
        query: 'definitelyNotASymbol',
        projectPath: mainRepo,
      });
      const text = res.content[0].text;

      expect(text).toContain('No relevant code found');
      expect(text).not.toMatch(/index is empty|different git worktree/);
    });
  });
});
