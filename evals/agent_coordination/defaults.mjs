/** Apply the same capability defaults as the IM Agent creation form. */
import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { changeCapability, validateCapabilities } from '../../packages/product-contracts/lib/capabilities.js';

const run = process.argv[2];
const ports = readFileSync(join(run, '.e2e-ports.env'), 'utf8');
const base = ports.match(/^export IM_URL=(.+)$/m)?.[1];
if (!base) throw new Error('Isolated IM URL is missing');

let token;
async function request(method, route, body) {
  const response = await fetch(base + route, {
    method,
    headers: { 'content-type': 'application/json', ...(token ? { authorization: 'Bearer ' + token } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`${method} ${route}: HTTP ${response.status} ${await response.text()}`);
  return response.json();
}

// The E2E readiness check just used the same login endpoint.
await new Promise(resolve => setTimeout(resolve, 1200));
({ access_token: token } = await request('POST', '/im/v1/auth/login', { username: 'nano', password: 'nano1234' }));
const profiles = {};
for (const id of ['coord-a', 'coord-b']) {
  const route = '/im/v1/agents/' + id;
  const caps = await request('GET', route + '/capabilities');
  const saved = await request('GET', route + '/config');
  const catalog = { features: caps.features, tools: caps.tools.map(t => t.name),
    skills: caps.skills.map(s => s.name), fixed_tools: caps.fixed_tools };
  let draft = {
    work_mode: 'global', skills: [], skills_selection_mode: 'explicit_denylist',
    features: Object.fromEntries(caps.features.map(f => [f.key, f.default_on])),
    tool_allowlist: caps.tools.filter(t => t.default_on).map(t => t.name),
  };
  for (const feature of caps.features.filter(f => f.default_on)) {
    const next = changeCapability(draft, { kind: 'feature', name: feature.key, enabled: true }, catalog);
    if (next.blocks.length) throw new Error(`Cannot enable default ${feature.key}: ${JSON.stringify(next.blocks)}`);
    draft = next.draft;
  }
  const blocks = validateCapabilities(draft, catalog);
  if (blocks.length) throw new Error('Invalid default capability selection: ' + JSON.stringify(blocks));
  await request('PATCH', route + '/config', { ...saved, ...draft });
  const applied = await request('GET', route + '/config');
  const current = await request('GET', route + '/capabilities');
  const tools = [...new Set([...applied.tool_allowlist, ...current.fixed_tools])].sort();
  const expectedTools = [...new Set([...draft.tool_allowlist, ...catalog.fixed_tools])].sort();
  if (applied.work_mode !== 'global' || applied.skills_selection_mode !== draft.skills_selection_mode ||
      applied.skills.length || JSON.stringify(tools) !== JSON.stringify(expectedTools) ||
      caps.features.some(f => applied.features[f.key] !== draft.features[f.key])) {
    throw new Error(id + ' did not retain default capability selection');
  }
  profiles[id] = { work_mode: applied.work_mode, features: applied.features, tools,
    skills_selection_mode: applied.skills_selection_mode, skills: current.skills.map(s => s.name).sort(),
    workspace: applied.workspace_root, model: applied.default_model, effort: applied.reasoning_effort };
}
const comparable = ({ workspace, ...profile }) => profile;
if (JSON.stringify(comparable(profiles['coord-a'])) !== JSON.stringify(comparable(profiles['coord-b'])))
  throw new Error('A/B effective capability snapshots differ');
writeFileSync(join(run, 'defaults.json'), JSON.stringify(profiles, null, 2));
