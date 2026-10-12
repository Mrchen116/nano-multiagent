import type { FastifyInstance } from 'fastify';
import { all, body, fail, one, params, type ImContext, type Row } from './context.js';
import { installMaterials } from './install.js';

const fields = (row: Row, names: string[]) => Object.fromEntries(names.filter(name => row[name] !== undefined).map(name => [name, row[name]]));
/** Keep setup credentials confined to the request; only public status crosses back. */
function setupStatus(value: Row) {
  return {
    models: (value.models ?? []).map((m: Row) => fields(m, ['provider', 'model'])),
    catalog: (value.catalog ?? []).map((p: Row) => fields(p, ['provider', 'models'])),
    default_model: value.default_model ?? '',
    workspace_base: value.workspace_base ?? '',
    discovered: {
      codex: value.discovered?.codex === true,
      ...(value.discovered?.proxy ? { proxy: fields(value.discovered.proxy, ['base_url', 'models', 'protocol']) } : {}),
    },
    ...(value.operation ? { operation: fields(value.operation, ['id', 'state', 'code', 'url', 'message']) } : {}),
  };
}

/** Bridge first-run setup to the currently owned node over its existing connection. */
export function registerOnboardingRoutes(app: FastifyInstance, ctx: ImContext, releaseDirectory: string) {
  app.get('/im/v1/onboarding', req => {
    const user = ctx.identity.authenticateRequest(req);
    return {
      nodes: all(ctx.db, 'SELECT node_id,node_name,alias,status FROM nodes WHERE owner_id=? ORDER BY rowid', user.owner_id),
      agents: all(ctx.db, 'SELECT agent_id,display_name,node_id,default_model,workspace_root,work_mode FROM agent_profiles WHERE owner_id=? AND is_stale=0 ORDER BY rowid', user.owner_id),
      install: installMaterials(ctx.publicUrl, releaseDirectory),
    };
  });
  app.post('/im/v1/nodes/:node_id/setup', async req => {
    const user = ctx.identity.authenticateRequest(req), nodeId = params(req).node_id;
    const owned = () => {
      ctx.identity.authenticateRequest(req);
      if (!one(ctx.db, 'SELECT 1 FROM nodes WHERE node_id=? AND owner_id=?', nodeId, user.owner_id)) fail(404, 'node_id not found');
    };
    owned();
    const input = body(req);
    if (!['status', 'configure', 'login', 'cancel'].includes(input.action)) fail(422, 'invalid setup action');
    const payload = fields(input, ['action', 'provider', 'protocol', 'base_url', 'model', 'api_key']);
    for (const value of Object.values(payload)) if (typeof value !== 'string') fail(422, 'setup values must be text');
    const result = await ctx.gateway.request(nodeId, 'node.setup.request', payload);
    owned();
    if (result.error_code) fail(503, 'Computer setup is unavailable. Reconnect your computer and retry.');
    return setupStatus(result);
  });
}
