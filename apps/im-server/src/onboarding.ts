import type { FastifyInstance } from 'fastify';
import { all, body, fail, one, params, type ImContext, type Row } from './context.js';
import { installMaterials } from './install.js';
import { catalogReads } from './catalog-reads.js';

const fields = (row: Row, names: string[]) => Object.fromEntries(names.filter(name => row[name] !== undefined).map(name => [name, row[name]]));
/** Keep setup credentials confined to the request; only public status crosses back. */
function setupStatus(value: Row) {
  const error = (item: Row) => ({...fields(item, ['code', 'message']), ...(Array.isArray(item.dependencies) ? {dependencies: item.dependencies.map((dep: Row) => fields(dep, ['agent_id', 'display_name']))} : {})});
  return {
    revision: value.revision ?? '', ...(value.catalog_error ? {catalog_error: value.catalog_error} : {}),
    services: (value.services ?? []).map((p: Row) => ({...fields(p, ['provider', 'display_name', 'native', 'source', 'protocol', 'base_url', 'credential_stored']), models: (p.models ?? []).map((m: Row) => fields(m, ['name', 'id', 'display_name', 'context_window', 'max_tokens', 'input']))})),
    models: (value.models ?? []).map((m: Row) => fields(m, ['provider', 'model', 'display_name'])),
    catalog: (value.catalog ?? []).map((p: Row) => ({...fields(p, ['provider', 'display_name']), models: (p.models ?? []).map((m: Row) => fields(m, ['id', 'name', 'contextWindow', 'maxTokens', 'inputModalities']))})),
    default_model: value.default_model ?? '', workspace_base: value.workspace_base ?? '',
    ...(value.operation ? {operation: {...fields(value.operation, ['id', 'state', 'code', 'url', 'message']), ...(value.operation.error ? {error: error(value.operation.error)} : {})}} : {}),
    ...(value.error ? {error: error(value.error)} : {}),
  };
}

/** Bridge first-run setup to the currently owned node over its existing connection. */
export function registerOnboardingRoutes(app: FastifyInstance, ctx: ImContext, releaseDirectory: string, iosDownloadUrl?: string) {
  const revisions = new WeakMap<object,string>();
  app.get('/im/v1/onboarding', req => {
    const user = ctx.identity.authenticateRequest(req);
    return {
      nodes: all(ctx.db, 'SELECT node_id,node_name,alias,status FROM nodes WHERE owner_id=? ORDER BY rowid', user.owner_id),
      agents: all(ctx.db, 'SELECT agent_id,display_name,node_id,default_model,workspace_root,work_mode FROM agent_profiles WHERE owner_id=? AND is_stale=0 ORDER BY rowid', user.owner_id),
      install: installMaterials(ctx.publicUrl, releaseDirectory, iosDownloadUrl),
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
    if (!['status', 'save', 'remove', 'login', 'cancel'].includes(input.action)) fail(422, 'invalid setup action');
    const payload = fields(input, ['action', 'revision', 'provider', 'source', 'display_name', 'protocol', 'base_url', 'model', 'api_key']);
    for (const value of Object.values(payload)) if (typeof value !== 'string') fail(422, 'setup values must be text');
    if (input.models !== undefined) {
      if (!Array.isArray(input.models) || input.models.some((m: unknown) => !m || typeof m !== 'object' || Array.isArray(m))) fail(422, 'models must be an array');
      payload.models = input.models.map((model: Row) => {
        const item = fields(model, ['id', 'display_name', 'context_window', 'max_tokens', 'input']);
        if (typeof item.id !== 'string' || (item.display_name !== undefined && typeof item.display_name !== 'string')) fail(422, 'model IDs and names must be text');
        for (const key of ['context_window', 'max_tokens']) if (item[key] !== undefined && (!Number.isSafeInteger(item[key]) || item[key] <= 0)) fail(422, 'token limits must be positive integers');
        if (item.input !== undefined && (!Array.isArray(item.input) || item.input.some((value: unknown) => !['text', 'image'].includes(String(value))))) fail(422, 'invalid model input');
        return item;
      });
    }
    const connection = ctx.gateway.nodes.get(nodeId);
    if (['save','remove','login'].includes(input.action)) catalogReads(ctx).invalidateNode(nodeId);
    const result = await ctx.gateway.request(nodeId, 'node.setup.request', {...payload, action:input.action});
    if (connection && ctx.gateway.nodes.get(nodeId) === connection && typeof result.revision === 'string') {
      if (revisions.get(connection) !== result.revision) catalogReads(ctx).invalidateNode(nodeId);
      revisions.set(connection,result.revision);
    }
    if (['save','remove'].includes(input.action) && !result.error && !result.error_code) catalogReads(ctx).invalidateNode(nodeId);
    owned();
    if (result.error_code) fail(503, 'Computer setup is unavailable. Reconnect your computer and retry.');
    return setupStatus(result);
  });
  // Transiently bridge Daily Chrome pairing to the owned online node; never persist or log the extension token.
  app.post('/im/v1/nodes/:node_id/browser', async (req, reply) => {
    reply.header('Cache-Control', 'no-store');
    const user = ctx.identity.authenticateRequest(req);
    const nodeId = params(req).node_id;
    const owned = () => {
      ctx.identity.authenticateRequest(req);
      if (!one(ctx.db, 'SELECT 1 FROM nodes WHERE node_id=? AND owner_id=?', nodeId, user.owner_id)) {
        fail(404, 'node_id not found');
      }
    };
    owned();
    const input = body(req);
    const action = input.action;
    if (!['status', 'open-guide', 'pair', 'disconnect'].includes(action)) {
      fail(400, { code: 'invalid_browser_action', message: 'Unsupported browser pairing action' });
    }
    const profile = input.profile;
    if (profile !== undefined && typeof profile !== 'string') {
      fail(400, { code: 'invalid_browser_profile', message: 'Browser profile must be text' });
    }
    let rpcPayload:
      | { action: 'status'; profile?: string }
      | { action: 'open-guide'; profile?: string; target?: 'auto' | 'store' | 'token' }
      | { action: 'pair'; profile?: string; token: string }
      | { action: 'disconnect' };
    if (action === 'status') {
      rpcPayload = { action: 'status', ...(profile !== undefined ? { profile } : {}) };
    } else if (action === 'open-guide') {
      if (input.target !== undefined && !['auto', 'store', 'token'].includes(input.target)) {
        fail(400, { code: 'invalid_browser_action', message: 'Invalid browser guide target' });
      }
      rpcPayload = {
        action: 'open-guide',
        ...(profile !== undefined ? { profile } : {}),
        ...(input.target !== undefined ? { target: input.target } : {}),
      };
    } else if (action === 'pair') {
      if (typeof input.token !== 'string' || !input.token.trim()) {
        fail(422, { code: 'invalid_browser_token', message: 'Paste the token shown by the official Playwright Extension' });
      }
      rpcPayload = {
        action: 'pair',
        ...(profile !== undefined ? { profile } : {}),
        token: input.token,
      };
    } else {
      rpcPayload = { action: 'disconnect' };
    }
    const result = await ctx.gateway.request(nodeId, 'node.browser.request', rpcPayload);
    owned();
    if (result.error) {
      const code = result.error.code;
      const status = code === 'invalid_browser_profile' || code === 'invalid_browser_action' ? 400 : 422;
      fail(status, { code, message: result.error.message });
    }
    if (result.error_code || !result.browser) {
      fail(503, 'Browser pairing is unavailable on this computer. Ensure the node is online and updated.');
    }
    const rawBrowser = result.browser as Row;
    return {
      browser: {
        ...fields(rawBrowser, [
          'supported',
          'state',
          'chrome_installed',
          'chrome_running',
          'chrome_version_ok',
          'paired_profile',
          'selected_profile',
          'extension_installed',
          'last_checked_at',
        ]),
        profiles: Array.isArray(rawBrowser.profiles)
          ? rawBrowser.profiles.map((p: Row) => fields(p, ['profile', 'extension_installed']))
          : [],
      },
      ...(result.opened === 'store' || result.opened === 'token' ? { opened: result.opened } : {}),
    };
  });
}
