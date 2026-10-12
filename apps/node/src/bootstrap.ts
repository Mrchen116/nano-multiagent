import { access } from 'node:fs/promises';
import { createHash, randomUUID } from 'node:crypto';
import { homedir, hostname } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { dump } from 'js-yaml';
import { NodeConfiguration } from './configuration.js';
import { atomicPrivate } from './lifecycle.js';

/** Create a dormant node for one hosted IM, preserving any existing connection. */
export async function bootstrapNode(origin: string, path?: string): Promise<NodeConfiguration> {
  const url = new URL(origin);
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password)
    throw new Error('Use the HTTP(S) address of your Nano IM service');
  const root = resolve(process.env.NANO_INSTALL_ROOT ?? join(homedir(), '.nanoassistant'));
  const connection = createHash('sha256').update(url.origin).digest('hex').slice(0, 16);
  const configPath = resolve(path ?? join(root, 'connections', connection, 'config.yaml'));
  try {
    await access(configPath);
    const existing = await NodeConfiguration.read(configPath);
    if (new URL(existing.value.im_service.url).origin !== url.origin)
      throw new Error('This configuration belongs to another IM service; choose a different config path');
    return existing;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error;
  }
  const directory = dirname(configPath);
  await atomicPrivate(configPath, dump({
    node: { node_id: `computer-${randomUUID().slice(0, 8)}`, user_id: '', node_name: hostname(), workspace_base: join(directory, 'workspaces') },
    im_service: { url: url.origin, token: '' },
    agents: [],
    llm: { default_model: '', providers: [] },
    gateway: { environment: { NANO_OWNER_CONFIG_ROOT: directory }, ...(process.env.NANO_INSTALL_AUTOSTART === '0' ? { autostart: false } : {}) },
  }, { noRefs: true }));
  return NodeConfiguration.read(configPath);
}
