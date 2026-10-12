import type { FastifyInstance } from 'fastify';
import { createReadStream, existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import type { ImContext } from './context.js';
import { fail } from './context.js';

const quote = (value: string) => "'" + value.replaceAll("'", "'\\''") + "'";
export const defaultReleaseDirectory = fileURLToPath(new URL('../../../dist/node-release/', import.meta.url));

/** Publish one service-matched computer installer without depending on request Host. */
export function installMaterials(origin: string, directory: string) {
  const base = new URL(origin).origin;
  const available = existsSync(join(directory, 'manifest.json')) && existsSync(join(directory, 'nano-node.tgz'));
  const command = `curl -fsSL ${quote(base + '/install.sh')} -o /tmp/nano-install.sh && bash /tmp/nano-install.sh`;
  return { available, origin: base, command, script_url: base + '/install.sh' };
}
export function registerInstallRoutes(app: FastifyInstance, ctx: ImContext, directory: string) {
  app.get('/install.sh', (_req, reply) => {
    if (!installMaterials(ctx.publicUrl, directory).available) fail(503, 'Computer installer is not published yet');
    const template = readFileSync(new URL('../assets/install.sh', import.meta.url), 'utf8');
    return reply.header('Cache-Control', 'no-store').type('text/x-shellscript')
      .send(template.replace('__NANO_ORIGIN__', quote(new URL(ctx.publicUrl).origin)));
  });
  for (const file of ['manifest.json', 'nano-node.tgz']) {
    app.get('/install/' + file, (_req, reply) => {
      if (!installMaterials(ctx.publicUrl, directory).available) fail(503, 'Computer installer is not published yet');
      return reply.header('Cache-Control', 'no-store').type(file.endsWith('.json') ? 'application/json' : 'application/gzip')
        .send(createReadStream(join(directory, file)));
    });
  }
}
