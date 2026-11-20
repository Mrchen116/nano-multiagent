import type { FastifyInstance } from 'fastify';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import type { ImContext } from './context.js';
import { fail } from './context.js';
import { parseReleaseManifest } from '@nano/product-contracts';

const quote = (value: string) => "'" + value.replaceAll("'", "'\\''") + "'";
export const defaultReleaseDirectory = fileURLToPath(new URL('../../../dist/node-release/', import.meta.url));

/** Read the selected platform's verified metadata.
 *
 * Args:
 *   directory: Deployment's release selection directory.
 *   platform: Registered platform, or undefined for the original Unix package.
 * Returns:
 *   Manifest matching the requested platform, or null when unavailable.
 */
export function releaseManifest(directory: string, platform?: string) {
  if (platform !== undefined && platform !== 'win32-x64') return null;
  const filename = platform === 'win32-x64' ? 'manifest.win32-x64.json' : 'manifest.json';
  try {
    const manifest = parseReleaseManifest(JSON.parse(readFileSync(join(directory, filename), 'utf8')));
    return manifest?.platform === platform ? manifest : null;
  } catch { return null; }
}

/** Format the Unix recovery command using the configured public IM origin. */
export function unixInstallCommand(origin: string) {
  return `curl -fsSL ${quote(new URL(origin).origin + '/install.sh')} -o /tmp/nano-install.sh && bash /tmp/nano-install.sh`;
}

/** Describe the explicitly selected installer using only validated release metadata.
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
  const windows = releaseManifest(directory, 'win32-x64');
  const windows_x64 = windows?.platform === 'win32-x64' && new URL(base).protocol === 'https:'
    ? { download_url: windows.installer.download_url, connect_url: `crewden://connect?origin=${encodeURIComponent(base)}` }
    : null;
  return { available, origin: base, command: unixInstallCommand(base), script_url: base + '/install.sh', windows_x64 };
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
  app.get('/install/manifest.win32-x64.json', (_req, reply) => {
    const manifest = releaseManifest(directory, 'win32-x64');
    if (!manifest) fail(503, 'Windows installer is not published yet');
    return reply.header('Cache-Control', 'no-store').send(manifest);
  });
  // Old scripts still request the IM path; redirect without reading the archive.
  app.get('/install/nano-node.tgz', (_req, reply) => {
    const manifest = releaseManifest(directory);
    if (!manifest) fail(503, 'Computer installer is not published yet');
    return reply.header('Cache-Control', 'no-store').redirect(manifest.download_url, 302);
  });
}
