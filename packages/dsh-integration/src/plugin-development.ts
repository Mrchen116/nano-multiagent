import { existsSync, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, resolve } from 'node:path';

const require = createRequire(import.meta.url);
const topics = {
  tool: { packages: ['@deepseek-ai/dsh-tools'], supported: 'Register new workspace tools with parameters, output schema/render and execute. Do not shadow existing tools or bypass their permissions.' },
  prompt: { packages: ['@deepseek-ai/dsh-system-prompt'], supported: 'Contribute uniquely named section/context entries. Do not use complete, shadow host sections, suppress runtime context or change identity/approval/delivery rules.' },
  service: { packages: ['@deepseek-ai/cordis', '@deepseek-ai/cordis-plugin-loader'], supported: 'Provide plugin-private services inside a shared group with isolate. Own resources through ctx.effect cleanup. Each Agent preset mounts its own instance; workspace installation state is shared.' },
  events: { packages: ['@deepseek-ai/cordis', '@deepseek-ai/dsh-tools', '@deepseek-ai/dsh-scope'], supported: 'Passively observe scope-filtered tools/result, filtering your own tool names. Do not mutate frozen results or dispatch more tools from the observer. tools/change and system-prompt/change are unfiltered, not private workspace events. File watchers must target explicit workspace data and close on disposal.' },
  compaction: { packages: ['@deepseek-ai/dsh-compaction', '@deepseek-ai/dsh-compaction-basic'], supported: 'Use an isolated compaction provider. Prefer BasicCompactionEngine configuration or its public summarize hook; preserve native transactions, cancellation and tool pairing. Verify automatic and manual compaction and fallback after disable.' },
} as const;

export type PluginApiTopic = keyof typeof topics;
export const pluginApiTopics = Object.keys(topics) as PluginApiTopic[];

interface Manifest {
  version: string;
  exports: Record<string, string | { types?: string }>;
}

function installedPackage(name: string) {
  const manifestPath = require.resolve(`${name}/package.json`);
  const manifest = JSON.parse(readFileSync(manifestPath, 'utf8')) as Manifest;
  const packageDir = dirname(manifestPath);
  const types = Object.entries(manifest.exports).flatMap(([entry, target]) => {
    if (typeof target === 'string' || !target.types) return [];
    const path = resolve(packageDir, target.types);
    if (!existsSync(path)) throw new Error(`Declared public types are missing: ${name}${entry} (${path})`);
    return [{ import: entry === '.' ? name : name + entry.slice(1), path }];
  });
  const readme = resolve(packageDir, 'README.md');
  return { name, version: manifest.version, packageDir, ...(existsSync(readme) ? { readme } : {}), types };
}

/** Locate current public package documentation for a supported plugin topic.
 *
 * Args:
 *   workspace: Trusted workspace selected by the node configuration.
 *   topic: Supported authoring topic, never an arbitrary package or file path.
 *
 * Returns:
 *   Installed versions and public documentation paths without runtime configuration values.
 */
export function describePluginApi(workspace: string, topic?: PluginApiTopic) {
  if (!topic || !Object.hasOwn(topics, topic)) throw new Error(`describe_api requires topic: ${pluginApiTopics.join(', ')}`);
  const runtime = JSON.parse(readFileSync(require.resolve('@deepseek-ai/dsh/package.json'), 'utf8')) as Manifest;
  return { workspace, runtimeVersion: runtime.version, topic, supported: topics[topic].supported,
    boundary: 'Public declarations may include host APIs outside Nano support. Use nano-plugin-development when available. Workspace scope is not an OS sandbox for untrusted JavaScript.',
    packages: topics[topic].packages.map(installedPackage) };
}
