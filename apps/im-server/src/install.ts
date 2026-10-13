import type { FastifyInstance } from 'fastify';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import type { ImContext } from './context.js';
import { fail } from './context.js';

const quote = (value: string) => "'" + value.replaceAll("'", "'\\''") + "'";
export const defaultReleaseDirectory = fileURLToPath(new URL('../../../dist/node-release/', import.meta.url));

function releaseManifest(directory: string) {
  try {
    const value = JSON.parse(readFileSync(join(directory, 'manifest.json'), 'utf8'));
    if (!value || typeof value.version !== 'string' || typeof value.sha256 !== 'string'
      || !/^[a-f0-9]{40}$/.test(value.version) || !/^[a-f0-9]{64}$/.test(value.sha256)
      || value.package !== 'nano-node.tgz' || value.node_major !== 24 || value.pnpm_version !== '11.7.0'
      || value.download_url !== `https://github.com/Mrchen116/nano-multiagent/releases/download/node-${value.version}/nano-node.tgz`) return null;
    return value;
  } catch { return null; }
}

/** Describe the service-matched installer using only validated release metadata.
 *
 * Args:
 *   origin: Configured public IM URL; request Host must not influence commands.
 *   directory: Deployment directory containing the verified manifest.
 * Returns:
 *   Installation availability and a shell-quoted command for this IM.
 */
export function installMaterials(origin: string, directory: string) {
  const base = new URL(origin).origin;
  const available = releaseManifest(directory) !== null;
  const command = `curl -fsSL ${quote(base + '/install.sh')} -o /tmp/nano-install.sh && bash /tmp/nano-install.sh`;
  return { available, origin: base, command, script_url: base + '/install.sh' };
}

/** Register metadata and script routes without serving package bytes.
 *
 * Args:
 *   app: IM HTTP server.
 *   ctx: IM context with the configured public URL.
 *   directory: Deployment directory containing the verified manifest.
 */
export function registerInstallRoutes(app: FastifyInstance, ctx: ImContext, directory: string) {
  app.get('/install.sh', (_req, reply) => {
    if (!releaseManifest(directory)) fail(503, 'Computer installer is not published yet');
    const template = readFileSync(new URL('../assets/install.sh', import.meta.url), 'utf8');
    return reply.header('Cache-Control', 'no-store').type('text/x-shellscript')
      .send(template.replace('__NANO_ORIGIN__', quote(new URL(ctx.publicUrl).origin)));
  });
  app.get('/install/manifest.json', (_req, reply) => {
    const manifest = releaseManifest(directory);
    if (!manifest) fail(503, 'Computer installer is not published yet');
    return reply.header('Cache-Control', 'no-store').send(manifest);
  });
  // Old scripts still request the IM path; redirect without reading the archive.
  app.get('/install/nano-node.tgz', (_req, reply) => {
    const manifest = releaseManifest(directory);
    if (!manifest) fail(503, 'Computer installer is not published yet');
    return reply.header('Cache-Control', 'no-store').redirect(manifest.download_url, 302);
  });
}
