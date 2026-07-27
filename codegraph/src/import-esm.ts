/**
 * Dynamic import helper — tsc compiles `import()` to `require()` in CJS mode,
 * which fails for ESM-only packages (@clack/prompts). The Function-constructor
 * indirection bypasses that transformation; the body is a constant string, so
 * no user input can ever reach it.
 *
 * Kept in this dedicated module ON PURPOSE: the repo's security scan
 * (writ SEC-INJ-CMD-002) rightly flags `new Function` and blocks tool-edits to
 * any file containing it. Isolating the one legitimate use here keeps the
 * frequently-edited consumers (bin/codegraph.ts, installer/index.ts) editable.
 * Do not inline this back into a consumer file.
 */
// eslint-disable-next-line @typescript-eslint/no-implied-eval
export const importESM = new Function('specifier', 'return import(specifier)') as (
  specifier: string
) => Promise<typeof import('@clack/prompts')>;
