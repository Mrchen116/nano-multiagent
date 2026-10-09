import { readFile } from 'node:fs/promises';
import { dirname, isAbsolute, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import type { Context } from '@deepseek-ai/cordis';

/** Native Cordis plugins declared by the owner, with paths relative to their manifest. */
export async function mountExtensions(ctx: Context, manifest?: string) {
  if (!manifest) return;
  const source = await readFile(manifest, 'utf8').catch(error => { if (error.code === 'ENOENT') return undefined; throw error; });
  if (source === undefined) return;
  const plugins = JSON.parse(source) as { module: string; config?: unknown }[];
  for (const entry of plugins) {
    const specifier = entry.module.startsWith('.') || isAbsolute(entry.module)
      ? pathToFileURL(resolve(dirname(manifest), entry.module)).href : entry.module;
    const loaded = await import(specifier);
    await ctx.plugin(loaded.default ?? loaded, entry.config).await();
  }
}
