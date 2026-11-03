import type { FastifyInstance } from 'fastify';
import type { ImContext } from './context.js';
import { GET as wiki } from './open-intelligent-resources/wiki.js';
import { GET as imageSearch } from './open-intelligent-resources/image-search.js';
import { GET as streetRoute } from './open-intelligent-resources/street-route.js';

/** Mount upstream public-resource lookups behind the existing Nano identity. */
export function registerIntelligentUIResources(app: FastifyInstance, ctx: ImContext): void {
  for (const [name, handler] of Object.entries({wiki, 'image-search': imageSearch, 'street-route': streetRoute})) {
    app.get(`/im/v1/intelligent-ui/api/${name}`, async (req, reply) => {
      const principal = ctx.messaging.principal(req);
      ctx.identity.rateLimit(`intelligent-ui:${principal.id}`, 60, 60);
      const result = await handler(new Request(new URL(req.url, ctx.publicUrl)));
      reply.code(result.status);
      return reply.type('application/json').send(await result.text());
    });
  }
}
