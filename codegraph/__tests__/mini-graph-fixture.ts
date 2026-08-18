/**
 * Shared mini-graph fixture for the CLI end-to-end suites.
 *
 * A two-file TypeScript project with a call chain `main -> greet -> hello`
 * (`main` calls `greet` from `b.ts`, `greet` calls `hello` from `a.ts`), plus
 * an import edge between the two files — enough structure to prove a repair
 * rebuilt a real graph, not just recreated empty tables. The sources were
 * previously inlined in `index-command.test.ts` (the #874 regression suite);
 * they live here now so every E2E suite writes the exact same bytes from one
 * constant (Hold 6).
 */

export const MINI_GRAPH_FILES: Record<string, string> = {
  'a.ts':
    `export function greet(name: string) { return hello(name); }\n` +
    `export function hello(n: string) { return 'hi ' + n; }\n`,
  'b.ts':
    `import { greet } from './a';\nexport function main() { return greet('world'); }\n`,
};

export const MINI_GRAPH_SYMBOLS = {
  greet: 'greet',
  hello: 'hello',
  main: 'main',
} as const;
