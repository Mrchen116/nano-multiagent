import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { openDatabase } from '../src/db.js';
import Fastify from 'fastify';
import { expect, it } from 'vitest';
import { canonicalAgentConfiguration, agentConfigurationFingerprint } from '@nano/product-contracts';
import { candidateFingerprint, registerControlRoutes } from '../src/control.js';
import { fixture } from './control-fixture.js';

it('saves, preserves omitted mode, clears inheritance and rejects invalid approval choices through the API', async () => {
  const {ctx, db} = fixture();
  const app = Fastify();
  app.setErrorHandler((error: any, _req, reply) => reply.code(error.statusCode ?? 500).send({detail: error.message}));
  registerControlRoutes(app, ctx);
  ctx.gateway.request = async (_node, _action, payload) => ({status: 'applied', operation_id: payload.operation_id, candidate_fingerprint: payload.candidate_fingerprint, agent: payload.agent});
  const patch = (profile_version: number, fields: Record<string, unknown>) => app.inject({method: 'PATCH', url: '/im/v1/agents/a/config', payload: {display_name: 'Agent', group_reply_policy: 'manual', profile_version, ...fields}});
  try {
    const created = await app.inject({method: 'POST', url: '/im/v1/nodes/n/agents', payload: {agent_id: 'b', display_name: 'Second', workspace_root: '/b', group_reply_policy: 'manual', skills: [], approval_mode: 'cc'}});
    expect(created.statusCode).toBe(201);
    expect(created.json().approval_mode).toBe('cc');
    for (const [version, fields, expected] of [[1, {approval_mode: 'codex'}, 'codex'], [2, {}, 'codex'], [3, {approval_mode: 'cc'}, 'cc'], [4, {approval_mode: null}, null]] as const) {
      const response = await patch(version, fields);
      expect(response.statusCode).toBe(200);
      expect(response.json().approval_mode).toBe(expected);
      expect(db.prepare("SELECT approval_mode FROM agent_profiles WHERE agent_id='a'").get()?.approval_mode).toBe(expected);
    }
    expect(db.prepare("SELECT approval_mode FROM agent_profiles WHERE agent_id='b'").get()?.approval_mode).toBe('cc');
    expect((await patch(5, {approval_mode: 'nano'})).statusCode).toBe(422);
    const before = db.prepare("SELECT * FROM agent_profiles WHERE agent_id='a'").get();
    ctx.gateway.request = async () => null as any;
    expect((await patch(5, {approval_mode: 'codex'})).statusCode).toBe(503);
    expect(db.prepare("SELECT * FROM agent_profiles WHERE agent_id='a'").get()).toEqual(before);
  } finally { await app.close(); }
});

it('uses the same fingerprints on IM and Node including explicit strategy changes', () => {
  const base = {agent_id: 'a', display_name: '中文', skills: []};
  for (const approval_mode of [undefined, null, 'cc', 'codex']) {
    const payload = {...base, approval_mode};
    expect(candidateFingerprint(payload)).toBe(agentConfigurationFingerprint(payload));
    expect(canonicalAgentConfiguration(payload).approval_mode).toBe(approval_mode ?? null);
  }
  expect(candidateFingerprint(base)).toBe(candidateFingerprint({...base, approval_mode: null}));
  expect(candidateFingerprint({...base, approval_mode: 'cc'})).not.toBe(candidateFingerprint({...base, approval_mode: 'codex'}));
});


it('upgrades existing profiles to inherited mode without rewriting their saved settings', () => {
  const directory = mkdtempSync(join(tmpdir(), 'nano-approval-schema-'));
  const path = join(directory, 'im.db');
  let db = openDatabase(path);
  try {
    db.prepare("INSERT INTO agent_profiles(agent_id,owner_id,display_name,created_at,updated_at) VALUES('legacy','owner','Original','then','then')").run();
    db.exec("ALTER TABLE agent_profiles DROP COLUMN approval_mode; DELETE FROM schema_migrations WHERE version='agent-approval-mode-v1'");
    db.close();
    db = openDatabase(path);
    expect(db.prepare("SELECT display_name,approval_mode,profile_version FROM agent_profiles WHERE agent_id='legacy'").get()).toEqual({display_name: 'Original', approval_mode: null, profile_version: 1});
    db.prepare("UPDATE agent_profiles SET approval_mode='codex'").run();
    db.close();
    db = openDatabase(path);
    expect(db.prepare("SELECT approval_mode FROM agent_profiles WHERE agent_id='legacy'").get()?.approval_mode).toBe('codex');
  } finally { db.close(); rmSync(directory, {recursive: true, force: true}); }
});
