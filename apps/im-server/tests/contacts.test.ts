import Fastify from 'fastify';
import { afterEach, expect, it } from 'vitest';
import { fixture } from './control-fixture.js';
import { Messaging, registerMessagingRoutes } from '../src/messaging.js';

const apps: ReturnType<typeof Fastify>[] = [];
afterEach(async () => { for (const app of apps.splice(0)) await app.close(); });
function setup() {
  const f = fixture(), app = Fastify(); apps.push(app);
  f.ctx.messaging = new Messaging(f.ctx);
  registerMessagingRoutes(app, f.ctx);
  f.db.exec("UPDATE users SET password_hash='registered',personal_space_enabled=1 WHERE username NOT LIKE 'agent:%'");
  const get = async (url: string) => app.inject({method:'GET',url,headers:{'x-user':'u1'}});
  const agent = (id: string, space = 'company:default', owner = 'o2') => {
    f.db.prepare("INSERT INTO agent_profiles(agent_id,owner_id,node_id,display_name,space_id,created_at,updated_at) VALUES(?,?,'n',?,?, '2026-01-01','2026-01-01')").run(id, owner, `Älpha ${id}`, space);
    f.db.prepare("INSERT INTO users(id,username,display_name,owner_id,created_at) VALUES(?,?,?,?, '2026-01-01')").run(id, `agent:${id}`, id, owner);
  };
  return {...f,app,get,agent};
}

it('paginates visible contacts without gaps across hidden candidates and keeps Unicode search and detail aligned', async () => {
  const {get,agent} = setup();
  const expected: string[] = [];
  for (let i = 0; i < 180; i++) {
    const id = `p${String(i).padStart(3,'0')}`;
    agent(id, i % 3 === 0 ? 'company:default' : 'personal:o2');
    if (i % 3 === 0) expected.push(id);
  }
  const first = (await get('/im/v1/contacts?kind=agent&q=%C3%A4LPHA')).json();
  expect(first.items.map((r:any)=>r.user_id)).toEqual(expected.slice(0,50));
  expect(first.next_cursor).toBe(expected[49]);
  const second = (await get(`/im/v1/contacts?kind=agent&q=%C3%A4LPHA&cursor=${first.next_cursor}`)).json();
  expect(second.items.map((r:any)=>r.user_id)).toEqual(expected.slice(50));
  expect(second.next_cursor).toBeNull();
  expect((await get('/im/v1/contacts/p000')).json()).toEqual(first.items[0]);
  expect((await get('/im/v1/contacts/p001')).statusCode).toBe(404);
  expect((await get('/im/v1/contacts/absent')).statusCode).toBe(404);
  const humans = (await get('/im/v1/contacts?kind=human')).json();
  expect(humans.items.map((r:any)=>r.user_id)).toEqual(['u1','u2']);
  expect((await get('/im/v1/contacts?kind=invalid')).statusCode).toBe(400);
});

it('shares live owner and personal-agent eligibility between list and detail', async () => {
  const {db,get,agent} = setup();
  agent('pa','personal:o2'); agent('stale'); agent('own','personal:o1','o1');
  db.prepare("UPDATE agent_profiles SET is_stale=1 WHERE agent_id='stale'").run();
  db.prepare("INSERT INTO personal_agent_bindings(binding_id,owner_id,owner_user_id,agent_id,node_id,node_epoch,conversation_id,display_name,request_key,status,created_at) VALUES('pa','o2','u2','pa','n',1,'pa-chat','PA','pa','active','2026-01-01')").run();
  expect((await get('/im/v1/contacts/pa')).json()).toMatchObject({user_id:'pa',role:'personal'});
  expect((await get('/im/v1/contacts/pa')).json()).not.toHaveProperty('space_id');
  expect((await get('/im/v1/contacts/stale')).statusCode).toBe(404);
  db.prepare("UPDATE users SET membership_status='suspended' WHERE id='u2'").run();
  expect((await get('/im/v1/contacts/pa')).statusCode).toBe(404);
  expect((await get('/im/v1/contacts?kind=agent')).json().items.map((r:any)=>r.user_id)).toEqual(['a1','own']);
  db.prepare("UPDATE users SET membership_status='none' WHERE id='u1'").run();
  expect((await get('/im/v1/contacts?kind=agent')).json().items.map((r:any)=>r.user_id)).toEqual(['own']);
  expect((await get('/im/v1/contacts/own')).statusCode).toBe(200);
});
