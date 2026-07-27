import { describe, it, expect, afterEach, beforeEach } from 'vitest';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { unsafeIndexRootReason, findNearestCodeGraphRoot, isUnexpandedTemplatePath } from '../src/directory';

/**
 * Guard for #845: the installer / `init` / `index` must refuse the home
 * directory and filesystem roots, which would otherwise index the entire tree
 * (multi-GB index, watcher churn, pre-1.0 macOS fd exhaustion that crashed the
 * machine). The classic trigger was running the installer from `$HOME`.
 */
describe('unsafeIndexRootReason', () => {
  const tmpDirs: string[] = [];
  afterEach(() => {
    for (const d of tmpDirs.splice(0)) {
      try { fs.rmSync(d, { recursive: true, force: true }); } catch { /* ignore */ }
    }
  });

  it('flags the home directory', () => {
    const reason = unsafeIndexRootReason(os.homedir());
    expect(reason).toBeTruthy();
    expect(reason).toContain('home');
  });

  it('flags a parent of the home directory (broader than home)', () => {
    // dirname(home) is either a parent of home or — for a root-level home like
    // `/root` — the filesystem root; both are unsafe.
    expect(unsafeIndexRootReason(path.dirname(os.homedir()))).toBeTruthy();
  });

  it.runIf(process.platform !== 'win32')('flags the POSIX filesystem root', () => {
    expect(unsafeIndexRootReason('/')).toContain('filesystem root');
  });

  it('allows a normal project directory', () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'cg-unsafe-'));
    tmpDirs.push(dir);
    expect(unsafeIndexRootReason(dir)).toBeNull();
    // …and a nested subdir of it.
    const nested = path.join(dir, 'packages', 'app');
    fs.mkdirSync(nested, { recursive: true });
    expect(unsafeIndexRootReason(nested)).toBeNull();
  });

  it('matches the home directory case-insensitively on macOS/Windows', () => {
    if (process.platform !== 'darwin' && process.platform !== 'win32') return;
    // The FS is case-insensitive there, so an upper-cased home path must still flag.
    expect(unsafeIndexRootReason(os.homedir().toUpperCase())).toBeTruthy();
  });
});

/**
 * The walk-up must never RESOLVE an unsafe root either: an index that already
 * exists at $HOME (created before the init-time guard, or by an unexpanded
 * `${workspaceFolder}` falling through to home) silently captured every
 * session whose path walked up past it — a multi-GB open + a minutes-long
 * catch-up sync that wedged the daemon in a watchdog kill loop.
 */
describe('findNearestCodeGraphRoot skips unsafe roots', () => {
  const tmpDirs: string[] = [];
  let prevHome: string | undefined;
  let prevAllow: string | undefined;

  beforeEach(() => {
    prevHome = process.env.HOME;
    prevAllow = process.env.CODEGRAPH_ALLOW_UNSAFE_ROOT;
    delete process.env.CODEGRAPH_ALLOW_UNSAFE_ROOT;
  });

  afterEach(() => {
    if (prevHome === undefined) delete process.env.HOME;
    else process.env.HOME = prevHome;
    if (prevAllow === undefined) delete process.env.CODEGRAPH_ALLOW_UNSAFE_ROOT;
    else process.env.CODEGRAPH_ALLOW_UNSAFE_ROOT = prevAllow;
    for (const d of tmpDirs.splice(0)) {
      try { fs.rmSync(d, { recursive: true, force: true }); } catch { /* ignore */ }
    }
  });

  /** Fake $HOME with an initialized .codegraph, plus a plain subdir under it. */
  function makeFakeHomeWithIndex(): { home: string; sub: string } {
    const home = fs.mkdtempSync(path.join(os.tmpdir(), 'cg-fake-home-'));
    tmpDirs.push(home);
    fs.mkdirSync(path.join(home, '.codegraph'));
    fs.writeFileSync(path.join(home, '.codegraph', 'codegraph.db'), '');
    const sub = path.join(home, 'work', 'project');
    fs.mkdirSync(sub, { recursive: true });
    return { home, sub };
  }

  it.runIf(process.platform !== 'win32')('does not resolve an index that sits at $HOME', () => {
    const { home, sub } = makeFakeHomeWithIndex();
    process.env.HOME = home; // os.homedir() reads $HOME on POSIX
    expect(findNearestCodeGraphRoot(sub)).toBeNull();
  });

  it.runIf(process.platform !== 'win32')('still resolves a safe project root under that $HOME', () => {
    const { home, sub } = makeFakeHomeWithIndex();
    process.env.HOME = home;
    fs.mkdirSync(path.join(sub, '.codegraph'));
    fs.writeFileSync(path.join(sub, '.codegraph', 'codegraph.db'), '');
    const nested = path.join(sub, 'src', 'deep');
    fs.mkdirSync(nested, { recursive: true });
    expect(findNearestCodeGraphRoot(nested)).toBe(sub);
  });

  it.runIf(process.platform !== 'win32')('CODEGRAPH_ALLOW_UNSAFE_ROOT=1 opts back in', () => {
    const { home, sub } = makeFakeHomeWithIndex();
    process.env.HOME = home;
    process.env.CODEGRAPH_ALLOW_UNSAFE_ROOT = '1';
    expect(findNearestCodeGraphRoot(sub)).toBe(home);
  });
});

describe('isUnexpandedTemplatePath', () => {
  it('flags a literal MCP config variable', () => {
    expect(isUnexpandedTemplatePath('${workspaceFolder}')).toBe(true);
    expect(isUnexpandedTemplatePath('/repo/${workspaceFolder}/sub')).toBe(true);
  });
  it('passes normal paths', () => {
    expect(isUnexpandedTemplatePath('/Users/dev/project')).toBe(false);
    expect(isUnexpandedTemplatePath('C:\\dev\\project')).toBe(false);
  });
});
