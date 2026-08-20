/**
 * Session door — initialize + tools/list follow the mapper's tri-state without
 * waiting on the engine for the list (Bucket 5 Step 3 / spec components 1+2
 * wired into the session).
 *
 * `resolveMcpIndexState` is mocked so each test drives a specific tri-state;
 * the engine is a stub whose `ensureInitialized` may be kicked off (legal,
 * #172 G-03) but must NEVER gate `tools/list`. MUST-1 asserts the list
 * deep-equals `getStaticTools()` (the static surface), not the engine's
 * dynamic `getTools()` — and that the list returns even while
 * `ensureInitialized` never resolves. MUST-3 asserts a busy index yields
 * exactly the BUSY instructions constant.
 *
 * No real DB fixtures here (Step 2's mcp-index-state.test.ts owns the
 * mapper→probe mapping). This file owns the session's reaction to each mapped
 * state.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import { MCPSession } from '../src/mcp/session';
import { MCPEngine } from '../src/mcp/engine';
import {
  JsonRpcRequest,
  JsonRpcTransport,
  JsonRpcResponse,
  MessageHandler,
} from '../src/mcp/transport';
import {
  SERVER_INSTRUCTIONS,
  SERVER_INSTRUCTIONS_UNINDEXED,
  SERVER_INSTRUCTIONS_INDEX_EMPTY,
  SERVER_INSTRUCTIONS_INDEX_BUSY,
} from '../src/mcp/server-instructions';
import { getStaticTools } from '../src/mcp/tools';

vi.mock('../src/mcp/index-state', () => ({
  resolveMcpIndexState: vi.fn(),
}));

import { resolveMcpIndexState } from '../src/mcp/index-state';

type TriState = {
  state: 'index_missing' | 'index_empty' | 'usable';
  busy: boolean;
  root: string | null;
};

class StubTransport implements JsonRpcTransport {
  handler: MessageHandler | null = null;
  sent: Array<{ id: string | number; result?: unknown; error?: unknown }> = [];

  start(handler: MessageHandler): void {
    this.handler = handler;
  }

  stop(): void {}

  send(response: JsonRpcResponse): void {
    this.sent.push({ id: response.id, result: response.result, error: response.error });
  }

  notify(_method: string, _params?: unknown): void {}

  request(_method: string, _params?: unknown, _timeoutMs?: number): Promise<unknown> {
    return Promise.resolve(undefined);
  }

  sendResult(id: string | number, result: unknown): void {
    this.sent.push({ id, result });
  }

  sendError(id: string | number | null, code: number, message: string, data?: unknown): void {
    this.sent.push({ id, error: { code, message, data } });
  }
}

function makeEngine(opts: {
  ensureInitialized?: () => Promise<void>;
  hasDefaultCodeGraph?: () => boolean;
  getTools?: () => unknown;
} = {}) {
  const ensureInitialized = vi.fn(opts.ensureInitialized ?? (() => Promise.resolve()));
  const hasDefaultCodeGraph = vi.fn(opts.hasDefaultCodeGraph ?? (() => true));
  const getToolHandler = vi.fn(() => ({
    getTools: vi.fn(opts.getTools ?? (() => [{ name: 'codegraph_engine_tool' }])),
    execute: vi.fn(),
  }));
  const engine = {
    ensureInitialized,
    hasDefaultCodeGraph,
    getToolHandler,
    getProjectPath: vi.fn(() => null),
    retryInitializeSync: vi.fn(),
  } as unknown as MCPEngine;
  return { engine, ensureInitialized, hasDefaultCodeGraph, getToolHandler };
}

/** Resolve `promise` or the literal 'timeout' after `ms` — proves a call did NOT hang. */
function withTimeout<T>(promise: Promise<T>, ms: number): Promise<T | 'timeout'> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => resolve('timeout'), ms);
    promise.then(
      (value) => {
        clearTimeout(timer);
        resolve(value);
      },
      (err) => {
        clearTimeout(timer);
        reject(err);
      },
    );
  });
}

describe('MCPSession door (Bucket 5 Step 3)', () => {
  let fixture: string;

  beforeEach(() => {
    fixture = fs.mkdtempSync(path.join(os.tmpdir(), 'cg-mcp-session-'));
  });

  afterEach(() => {
    vi.resetAllMocks();
    fs.rmSync(fixture, { recursive: true, force: true });
  });

  function makeSession(engine: MCPEngine) {
    const transport = new StubTransport();
    const session = new MCPSession(transport, engine, { explicitProjectPath: fixture });
    session.start();
    return { transport, session };
  }

  function initializeRequest(id = 1): JsonRpcRequest {
    return { jsonrpc: '2.0', id, method: 'initialize', params: { rootUri: 'file://' + fixture } };
  }

  function toolsListRequest(id = 2): JsonRpcRequest {
    return { jsonrpc: '2.0', id, method: 'tools/list' };
  }

  it('initialize picks instructions via the mapper and kicks ensureInitialized AFTER sendResult (#172)', async () => {
    vi.mocked(resolveMcpIndexState).mockReturnValue({ state: 'usable', busy: false, root: fixture } satisfies TriState);
    const { engine, ensureInitialized } = makeEngine();
    const { transport } = makeSession(engine);

    // Ordering proof: the moment ensureInitialized runs, the initialize reply
    // must already be on the wire.
    ensureInitialized.mockImplementation(() => {
      expect(transport.sent.some((r) => r.id === 1 && r.result !== undefined)).toBe(true);
      return Promise.resolve();
    });

    await transport.handler!(initializeRequest());

    expect(resolveMcpIndexState).toHaveBeenCalledWith(fixture);
    expect(transport.sent[0]!.result).toEqual(
      expect.objectContaining({ instructions: SERVER_INSTRUCTIONS }),
    );
    expect(ensureInitialized).toHaveBeenCalledWith(fixture);
  });

  it('MUST-3: busy index → initialize.instructions === SERVER_INSTRUCTIONS_INDEX_BUSY', async () => {
    vi.mocked(resolveMcpIndexState).mockReturnValue({ state: 'index_empty', busy: true, root: fixture } satisfies TriState);
    const { engine } = makeEngine();
    const { transport } = makeSession(engine);

    await transport.handler!(initializeRequest());

    expect(transport.sent[0]!.result).toEqual(
      expect.objectContaining({ instructions: SERVER_INSTRUCTIONS_INDEX_BUSY }),
    );
  });

  it('MUST-1: tools/list returns static tools while ensureInitialized never resolves, without touching the engine', async () => {
    vi.mocked(resolveMcpIndexState).mockReturnValue({ state: 'index_empty', busy: true, root: fixture } satisfies TriState);
    const { engine } = makeEngine({
      // Never settles — if the list awaited the engine, it would hang.
      ensureInitialized: () => new Promise(() => {}),
    });
    const { transport } = makeSession(engine);

    await transport.handler!(initializeRequest());
    expect(engine.ensureInitialized).toHaveBeenCalledWith(fixture);

    const outcome = await withTimeout(transport.handler!(toolsListRequest()), 1000);
    expect(outcome).not.toBe('timeout');

    const listResp = transport.sent.find((r) => r.id === 2)!;
    // MUST-1: deep-equals the STATIC surface — never the engine's getTools().
    expect((listResp.result as { tools: unknown }).tools).toEqual(getStaticTools());
    expect(engine.getToolHandler).not.toHaveBeenCalled();
    expect(engine.hasDefaultCodeGraph).not.toHaveBeenCalled();
  });

  it('empty index → EMPTY instructions, static tools still listed', async () => {
    vi.mocked(resolveMcpIndexState).mockReturnValue({ state: 'index_empty', busy: false, root: fixture } satisfies TriState);
    const { engine } = makeEngine();
    const { transport } = makeSession(engine);

    await transport.handler!(initializeRequest());
    expect(transport.sent[0]!.result).toEqual(
      expect.objectContaining({ instructions: SERVER_INSTRUCTIONS_INDEX_EMPTY }),
    );

    await transport.handler!(toolsListRequest());
    expect((transport.sent.find((r) => r.id === 2)!.result as { tools: unknown }).tools).toEqual(
      getStaticTools(),
    );
  });

  it('missing index (root null) → UNINDEXED instructions, EMPTY tool list', async () => {
    vi.mocked(resolveMcpIndexState).mockReturnValue({ state: 'index_missing', busy: false, root: null });
    const { engine } = makeEngine();
    const { transport } = makeSession(engine);

    await transport.handler!(initializeRequest());
    const instructions = (transport.sent[0]!.result as { instructions: string }).instructions;
    expect(instructions).toBe(SERVER_INSTRUCTIONS_UNINDEXED);
    expect(instructions).toContain('no usable index');

    await transport.handler!(toolsListRequest());
    expect((transport.sent.find((r) => r.id === 2)!.result as { tools: unknown[] }).tools).toEqual([]);
  });

  it('junk/corrupt index (root present, mapped missing) → UNINDEXED instructions, EMPTY tool list', async () => {
    vi.mocked(resolveMcpIndexState).mockReturnValue({ state: 'index_missing', busy: false, root: fixture });
    const { engine } = makeEngine();
    const { transport } = makeSession(engine);

    await transport.handler!(initializeRequest());
    expect(transport.sent[0]!.result).toEqual(
      expect.objectContaining({ instructions: SERVER_INSTRUCTIONS_UNINDEXED }),
    );

    await transport.handler!(toolsListRequest());
    expect((transport.sent.find((r) => r.id === 2)!.result as { tools: unknown[] }).tools).toEqual([]);
  });

  it('probe throw with a root present (mapper resolves usable) → full playbook + static tools', async () => {
    vi.mocked(resolveMcpIndexState).mockReturnValue({ state: 'usable', busy: false, root: fixture } satisfies TriState);
    const { engine } = makeEngine();
    const { transport } = makeSession(engine);

    await transport.handler!(initializeRequest());
    expect(transport.sent[0]!.result).toEqual(
      expect.objectContaining({ instructions: SERVER_INSTRUCTIONS }),
    );

    await transport.handler!(toolsListRequest());
    expect((transport.sent.find((r) => r.id === 2)!.result as { tools: unknown }).tools).toEqual(
      getStaticTools(),
    );
  });

  it('tools/list re-resolves the mapper from explicitProjectPath and never consults the engine', async () => {
    vi.mocked(resolveMcpIndexState).mockReturnValue({ state: 'usable', busy: false, root: fixture } satisfies TriState);
    const { engine } = makeEngine();
    const { transport } = makeSession(engine);

    await transport.handler!(toolsListRequest());

    expect(resolveMcpIndexState).toHaveBeenCalledWith(fixture);
    expect(engine.getToolHandler).not.toHaveBeenCalled();
    expect(engine.hasDefaultCodeGraph).not.toHaveBeenCalled();
    expect(engine.ensureInitialized).not.toHaveBeenCalled();
  });
});
