import { mkdtemp, readFile, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { ChannelKey, type CredentialEnvelope } from '../../../packages/channels/src/channel-credentials.js';
import { sortedJsonUtf8 } from '@nano/product-contracts/serialization';
import { describe, expect, it } from "vitest";
import Fastify from "fastify";
import {
  createDecipheriv,
  createPrivateKey,
  createPublicKey,
  diffieHellman,
  generateKeyPairSync,
  hkdfSync,
} from "node:crypto";
import { Messaging } from "../src/messaging.js";
import { TaskGraphService } from "../src/task-graphs.js";
import { ChannelService, sealChannelSecret } from "../src/channels.js";
import { ConfigOperations, candidateFingerprint, profileResponse, registerControlRoutes } from "../src/control.js";
import { one, type ImContext, type Row } from "../src/context.js";
import { fixture } from "./control-fixture.js";
function taskMessaging(db: any) {
  const ctx = {db,gateway:{broadcast:()=>{},send:()=>false}} as unknown as ImContext;
  return new Messaging(ctx);
}
const actor = { kind: "agent" as const, id: "a", node_id: "n" };
describe('capability configuration responsibility guards', () => {
  it('returns only authorized usage counts and fails closed when the runtime cannot confirm', async () => {
    const {db,ctx}=fixture();
    const service=new TaskGraphService(db,taskMessaging(db));
    service.execute({kind:'user',id:'u1'},'create',{title:'Private task contents',mode:'dag',conversation_id:'chat',request_key:'usage',status:'doing',assignee:{type:'agent',id:'a'}});
    ctx.gateway.request=async()=>({usage:{checked_at:'now',active_schedules:2,busy:[{kind:'feature',name:'heartbeat'}],internal:'not public'}});
    const app=Fastify();
    app.setErrorHandler((error:any,_req,reply)=>reply.code(error.statusCode??500).send({detail:error.detail??error.message}));
    registerControlRoutes(app,ctx);
    try {
      const response=await app.inject({method:'GET',url:'/im/v1/agents/a/capability-usage'});
      expect(response.statusCode).toBe(200);
      expect(response.json()).toEqual({checked_at:'now',active_tasks:1,active_schedules:2,busy:[{kind:'feature',name:'heartbeat'}]});
      expect((await app.inject({method:'GET',url:'/im/v1/agents/a/capability-usage',headers:{'x-user':'u2'}})).statusCode).toBe(404);
      ctx.gateway.request=async()=>null as any;
      expect((await app.inject({method:'GET',url:'/im/v1/agents/a/capability-usage'})).json()).toMatchObject({detail:{code:'capability_usage_unavailable'}});
    } finally {await app.close();}
  });
  it('rejects Task withdrawal before sending or saving while any owned task is doing', async () => {
    const {db,ctx}=fixture();
    const service=new TaskGraphService(db,taskMessaging(db));
    service.execute({kind:'user',id:'u1'},'create',{title:'Still working',mode:'dag',conversation_id:'chat',request_key:'guard',status:'doing',assignee:{type:'agent',id:'a'}});
    let sent=false;ctx.gateway.request=async()=>{sent=true;return null as any;};
    const previous=one(db,"SELECT * FROM agent_profiles WHERE agent_id='a'")!;
    await expect(new ConfigOperations(ctx).update(previous,{...profileResponse(previous,true),features:{intelligent_ui:false,task_graph:false,memory_curation:false,skill_creation:false,cron_scheduling:false,heartbeat:false},tool_allowlist:[]},'o1')).rejects.toMatchObject({statusCode:409,detail:{code:'capability_in_use',blocks:[{code:'active_tasks',target:{kind:'feature',name:'task_graph'}}]}});
    expect(sent).toBe(false);
    expect(one(db,'SELECT 1 FROM agent_config_operations')).toBeUndefined();
    expect(one(db,"SELECT * FROM agent_profiles WHERE agent_id='a'")).toEqual(previous);
  });
  it('fences new doing responsibility while withdrawal is pending and allows non-running work', async () => {
    const {db,ctx}=fixture();
    ctx.gateway.request=async()=>null as any;
    const previous=one(db,"SELECT * FROM agent_profiles WHERE agent_id='a'")!;
    await expect(new ConfigOperations(ctx).update(previous,{...profileResponse(previous,true),features:{intelligent_ui:false,task_graph:false,memory_curation:false,skill_creation:false,cron_scheduling:false,heartbeat:false},tool_allowlist:[]},'o1')).rejects.toThrow();
    const service=new TaskGraphService(db,taskMessaging(db));
    const args={title:'New work',mode:'dag',conversation_id:'chat',request_key:'new',assignee:{type:'agent',id:'a'}};
    expect(()=>service.execute({kind:'user',id:'u1'},'create',{...args,status:'doing'})).toThrow('configuration');
    expect(service.execute({kind:'user',id:'u1'},'create',{...args,status:'todo'}).graph_id).toBeTruthy();
  });
  it('rejects a final snapshot with incomplete dependencies', async () => {
    const {db,ctx}=fixture(),p=one(db,"SELECT * FROM agent_profiles WHERE agent_id='a'")!;
    await expect(new ConfigOperations(ctx).update(p,{...profileResponse(p,true),features:{task_graph:true,cron_scheduling:false}},'o1')).rejects.toMatchObject({statusCode:422,detail:{code:'invalid_capability_dependencies'}});
    expect(one(db,'SELECT 1 FROM agent_config_operations')).toBeUndefined();
  });
});
describe("company task graph atomic storage", () => {
  it("rolls back invalid DAG mutations and replays receipts after graph deletion", () => {
    const { db } = fixture(),
      s = new TaskGraphService(db, taskMessaging(db));
    const created = s.execute(actor, "create", {
      title: "计划",
      mode: "dag",
      request_key: "create",
      conversation_id: "chat",
    });
    const args = {
      graph_id: created.graph_id,
      base_revision: 1,
      request_key: "edit",
      change_note: "",
      conversation_id: "chat",
      operations: [
        { op: "add_task", client_ref: "first", container_id: "n1", title: "A" },
        {
          op: "add_task",
          client_ref: "second",
          container_id: "n1",
          title: "B",
        },
        { op: "add_dependency", from: "@first", to: "@second" },
      ],
    };
    const applied = s.execute(actor, "apply", args);
    expect(applied.client_refs).toEqual({ first: "n2", second: "n3" });
    expect(s.execute(actor, "apply", args)).toEqual(applied);
    expect(() =>
      s.execute(actor, "apply", {
        ...args,
        base_revision: 2,
        request_key: "bad",
        operations: [{ op: "add_dependency", from: "n3", to: "n2" }],
      }),
    ).toThrow("cycle");
    expect(one(db, "SELECT revision FROM task_graphs")?.revision).toBe(2);
    expect(
      one(db, "SELECT 1 FROM task_graph_mutation_receipts WHERE request_key='bad'"),
    ).toBeUndefined();
    expect(() => s.execute({kind:"user",id:"u2"},"get",{graph_id:created.graph_id,view:"all"})).toThrow("not accessible");
    expect(() =>
      s.execute({ kind: "user", id: "u2" }, "activity", {
        conversation_id: "chat",
      }),
    ).toThrow("not accessible");
    const deletion = {
      graph_id: created.graph_id,
      base_revision: 2,
      request_key: "delete",
    };
    const receipt = s.execute(actor, "delete", deletion);
    expect(receipt.deleted).toBe(true);
    expect(one(db, "SELECT 1 FROM task_graphs")).toBeUndefined();
    expect(s.execute(actor, "delete", deletion)).toEqual(receipt);
    expect(() => s.execute(actor, "delete", { ...deletion, base_revision: 3 })).toThrow(
      "original parameters",
    );
  });
  it.each([undefined, '对', '直接删！'])('keeps deletion scope, identity and revision checks after contextual confirmation %s', confirmation => {
    const { db } = fixture(), service = new TaskGraphService(db, taskMessaging(db));
    const created = service.execute(actor, 'create', {title:'计划',mode:'dag',request_key:'create',conversation_id:'chat'});
    service.execute(actor, 'apply', {graph_id:created.graph_id,base_revision:1,request_key:'children',change_note:'',operations:[
      {op:'add_task',client_ref:'child',container_id:'n1',title:'Remove',mode:'dag'},
      {op:'add_task',client_ref:'grandchild',container_id:'@child',title:'Nested'},
      {op:'add_task',client_ref:'sibling',container_id:'n1',title:'Keep'},
    ]});
    if (confirmation) db.prepare("INSERT INTO messages(id,conversation_id,sender_user_id,sender_type,content,delivery_status,created_at) VALUES('confirmation','chat','u1','user',?,'completed',?)").run(confirmation,new Date().toISOString());
    const caller = {...actor,...(confirmation?{source_message_id:'confirmation'}:{})};
    const args = {graph_id:created.graph_id,node_id:'n2',base_revision:2,request_key:'delete-child'};
    expect(()=>service.execute(caller,'delete',{...args,base_revision:1})).toThrow('current graph');
    expect(()=>service.execute({...caller,source_message_id:'invented'},'delete',args)).toThrow('not accessible');
    db.prepare('UPDATE agent_profiles SET is_stale=1').run();
    expect(()=>service.execute(caller,'delete',args)).toThrow('not accessible');
    db.prepare('UPDATE agent_profiles SET is_stale=0').run();
    const receipt = service.execute(caller,'delete',args);
    expect(receipt.deleted_ids).toEqual(['n2','n3']);
    expect(service.execute(caller,'delete',args)).toEqual(receipt);
    const graph = service.execute(actor,'get',{graph_id:created.graph_id,view:'all'});
    expect(graph.nodes.map((node:any)=>node.id)).toEqual(['n1','n4']);
  });
  it("denies disabled task tool and inactive owners", () => {
    const { db } = fixture(),
      s = new TaskGraphService(db, taskMessaging(db));
    db.prepare("UPDATE agent_profiles SET tool_allowlist_json='[]'").run();
    expect(() => s.execute(actor, "create", { title: "x", mode: "dag", request_key: "c" })).toThrow(
      "not accessible",
    );
  });
});
describe("encrypted channel control", () => {
  it("seals authenticated envelope, enforces revisions, status generations and deletion ACKs", () => {
    const { db } = fixture(),
      s = new ChannelService(db),
      keys = generateKeyPairSync("x25519");
    const pub = Buffer.from(keys.publicKey.export({ format: "jwk" }).x!, "base64url").toString(
      "base64",
    );
    db.prepare(
      "INSERT INTO node_credential_keys(node_id,owner_id,key_id,algorithm,public_key,updated_at) VALUES('n','o1','key','X25519',?,?)",
    ).run(pub, new Date().toISOString());
    const c = s.create("o1", "a", {
      provider: "feishu",
      enabled: true,
      config: { app_id: "app123" },
      credentials: { mode: "replace", app_secret: "top secret" },
    });
    expect(JSON.stringify(c.resource)).not.toContain("top secret");
    expect(c.resource.sync_state).toBe("pending");
    const raw = one(db, "SELECT * FROM agent_channels")!;
    expect(JSON.stringify(raw)).not.toContain("top secret");
    const envelope = JSON.parse(raw.credential_envelope_json);
    const ep = createPublicKey({
      key: {
        kty: "OKP",
        crv: "X25519",
        x: Buffer.from(envelope.ephemeral_public_key, "base64").toString("base64url"),
      },
      format: "jwk",
    });
    const key = Buffer.from(
      hkdfSync(
        "sha256",
        diffieHellman({ privateKey: keys.privateKey, publicKey: ep }),
        Buffer.from(envelope.salt, "base64"),
        Buffer.from("nano-multiagent/channel-envelope-v1"),
        32,
      ),
    );
    const bytes = Buffer.from(envelope.ciphertext, "base64");
    const decipher = createDecipheriv("aes-256-gcm", key, Buffer.from(envelope.nonce, "base64"));
    decipher.setAuthTag(bytes.subarray(-16));
    decipher.setAAD(
      Buffer.from(
        sortedJsonUtf8({
          owner_id: "o1",
          node_id: "n",
          agent_id: "a",
          channel_id: raw.channel_id,
          provider: "feishu",
          credential_revision: 1,
        }),
      ),
    );
    expect(
      JSON.parse(
        Buffer.concat([decipher.update(bytes.subarray(0, -16)), decipher.final()]).toString(),
      ),
    ).toEqual({ app_secret: "top secret" });
    expect(() =>
      s.update("o1", "a", raw.channel_id, {
        channel_revision: 1,
        enabled: true,
        config: { app_id: "changed" },
        credentials: { mode: "keep" },
      }),
    ).toThrow("channel_credentials_required");
    const status = {
      node_id: "n",
      channel_id: raw.channel_id,
      channel_revision: 1,
      runtime_incarnation: "r1",
      status_sequence: 1,
      instance_started: true,
      connection_state: "connected",
    };
    expect(s.recordStatus(status).outcome).toBe("accepted");
    expect(s.recordStatus(status).outcome).toBe("already_current");
    s.recordReconcile({
      node_id: "n",
      manifest_revision: 1,
      outcome: "applied",
    });
    expect(s.list("o1", "a")[0].sync_state).toBe("applied");
    const deletion = s.delete("o1", "a", raw.channel_id, 1);
    expect(s.manifest("n")!.channels).toHaveLength(0);
    expect(s.recordStatus(status).outcome).toBe("terminal_channel_removed");
    expect(() =>
      s.create("o1", "a", {
        provider: "feishu",
        config: { app_id: "x" },
        credentials: { mode: "replace", app_secret: "s" },
      }),
    ).toThrow("channel_deletion_pending");
    const removal = deletion.manifest.removals[0];
    const ack = s.recordReconcile({
      node_id: "n",
      manifest_revision: 2,
      outcome: "applied",
      removal_outcomes: [{ ...removal, outcome: "applied" }],
    });
    expect(ack.removal_token_outcomes[0].outcome).toBe("accepted");
    expect(s.list("o1", "a")).toEqual([]);
  });
});
describe("recoverable config operations and HTTP boundary", () => {
  it("matches the existing Python candidate hash including non-ASCII text", () => {
    expect(
      candidateFingerprint({
        agent_id: "a",
        display_name: "中文😀",
        skills: [],
        custom_prompt: "职责",
        heartbeat_json: '{"every":"30m"}',
      }),
    ).toBe("2bb798132ba2284d21b57f6d5913f82a6eb525c4a838112473759e682c06016e");
  });
  it("creates canonical agent identity once and persists applied receipt recovery", async () => {
    const { db, ctx } = fixture(),
      ops = new ConfigOperations(ctx);
    let creates = 0;
    ctx.gateway.request = async (_n, action, p) => {
      if (action === "agent.create") creates++;
      return {
        status: "applied",
        operation_id: p.operation_id,
        candidate_fingerprint: p.candidate_fingerprint,
        agent: {
          ...p.agent,
          workspace_root: "/canonical/new-agent",
          workspace_is_default: true,
        },
      };
    };
    const created = await ops.create(
      {
        agent_id: "new-agent",
        display_name: "New",
        skills: [],
        tool_allowlist: [],
        features: {intelligent_ui:false,task_graph:false,memory_curation:false,skill_creation:false,cron_scheduling:false,heartbeat:false},
        group_reply_policy: "manual",
      },
      "o1",
      "n",
    );
    expect(created.profile_version).toBe(1);
    expect(created.workspace_root).toBe("/canonical/new-agent");
    expect(created.workspace_is_default).toBe(true);
    expect(
      one(db, "SELECT display_name FROM users WHERE username='agent:new-agent'")?.display_name,
    ).toBe("New");
    await expect(ops.create({ agent_id: "new-agent" }, "o1", "n")).rejects.toMatchObject({
      statusCode: 409,
    });
    expect(creates).toBe(1);
    ctx.gateway.broadcast = () => {};
    const messaging = new Messaging(ctx);
    const group = {title: "Own group", type: "group", participants: [{type: "agent", id: "new-agent"}]};
    const createdGroup = messaging.createConversation(ctx.identity.user("u1")!, group);
    expect(createdGroup.type).toBe("group");
    expect(messaging.mentionedAgents(createdGroup.id, `<mention type="user" target_id="${messaging.agentUser("new-agent").id}"/> ping`)).toEqual(["new-agent"]);
    expect(() => messaging.createConversation(ctx.identity.user("u2")!, group)).toThrow("agent not accessible");
  });
  it("keeps pending durable after lost ACK and commits canonical result on recovery", async () => {
    const { db, ctx } = fixture(),
      ops = new ConfigOperations(ctx);
    let saved: Row | undefined;
    ctx.gateway.request = async (_node, action, payload) => {
      if (action === "agent.config.apply")
        saved = {
          status: "applied",
          operation_id: payload.operation_id,
          candidate_fingerprint: payload.candidate_fingerprint,
          agent: payload.agent,
        };
      return null as any;
    };
    const p = one(db, "SELECT * FROM agent_profiles")!,
      candidate = {
        agent_id: "a",
        owner_id: "o1",
        display_name: "修改",
        description: "new",
        skills: [],
        tool_allowlist: ["task_graph"],
        group_reply_policy: "manual",
        default_model: "model",
        model_fallbacks: [],
        reasoning_effort: null,
        approval_mode: "codex",
        work_mode: "single_thread",
        workspace_root: "/agent",
        features: {intelligent_ui:false,task_graph:false,memory_curation:false,skill_creation:false,cron_scheduling:false,heartbeat:false},
        custom_prompt: null,
        heartbeat_json: null,
      };
    await expect(ops.update(p, candidate, "o1")).rejects.toMatchObject({
      statusCode: 503,
    });
    expect(one(db, "SELECT display_name FROM agent_profiles")?.display_name).toBe("Agent");
    expect(one(db, "SELECT status FROM agent_config_operations")?.status).toBe("pending");
    ctx.gateway.request = async () => saved!;
    const result = await new ConfigOperations(ctx).recover("a", "o1");
    expect(result?.display_name).toBe("修改");
    expect(result?.profile_version).toBe(2);
    expect(result?.approval_mode).toBe("codex");
    expect(one(db, "SELECT status FROM agent_config_operations")?.status).toBe("committed");
  });
  it("compensates Gateway after profile CAS loses while preserving concurrent values", async () => {
    const { db, ctx } = fixture(),
      ops = new ConfigOperations(ctx);
    const calls: Row[] = [];
    ctx.gateway.request = async (_n, action, p) => {
      calls.push(p);
      if (calls.length === 1)
        db.prepare("UPDATE agent_profiles SET display_name='Concurrent',approval_mode='cc',profile_version=2").run();
      return {
        status: "applied",
        operation_id: p.operation_id,
        candidate_fingerprint: p.candidate_fingerprint,
        agent: p.agent,
      };
    };
    const p = one(db, "SELECT * FROM agent_profiles")!;
    await expect(
      ops.update(
        p,
        {
          ...profileResponse(p,true),
          agent_id: "a",
          display_name: "Candidate",
          approval_mode: "codex",
          workspace_root: "/agent",
          tool_allowlist: JSON.parse(p.tool_allowlist_json),
        },
        "o1",
      ),
    ).rejects.toMatchObject({ statusCode: 409 });
    expect(calls).toHaveLength(2);
    expect(calls[1].agent.display_name).toBe("Concurrent");
    expect(calls[1].agent.approval_mode).toBe("cc");
    expect(one(db, "SELECT display_name FROM agent_profiles")?.display_name).toBe("Concurrent");
    expect(
      one(db, "SELECT status FROM agent_config_operations WHERE operation_kind='compensation'")
        ?.status,
    ).toBe("committed");
  });
  it("routes enforce owner scope, expose no retired prompt, and degrade offline previews", async () => {
    const { ctx } = fixture(),
      app = Fastify();
    app.setErrorHandler((e: any, _q, r) =>
      r.code(e.statusCode ?? 500).send({ detail: e.detail ?? e.message }),
    );
    registerControlRoutes(app, ctx);
    const auth = { authorization: "Bearer token" };
    const mine = await app.inject({
      method: "GET",
      url: "/im/v1/agents/a/config?source=mirror",
      headers: auth,
    });
    expect(mine.statusCode).toBe(200);
    expect(mine.json().system_prompt).toBeUndefined();
    const other = await app.inject({
      method: "GET",
      url: "/im/v1/agents/a/config?source=mirror",
      headers: { ...auth, "x-user": "u2" },
    });
    expect(other.statusCode).toBe(404);
    const list = await app.inject({
      method: "GET",
      url: "/im/v1/agents",
      headers: { ...auth, "x-user": "u2" },
    });
    expect(list.json()).toEqual([]);
    const heartbeat = await app.inject({
      method: "GET",
      url: "/im/v1/agents/a/heartbeat-md",
      headers: auth,
    });
    expect(heartbeat.json()).toEqual({ content: "", node_online: false });
    await app.close();
  });
});

 describe('Skill denylist migration', () => {
  it.each([
    ['explicit_allowlist', ['keep'], ['blocked']],
    ['explicit_allowlist', [], ['keep', 'blocked']],
    ['default_discovery', [], []],
  ])('preserves %s selections through a versioned configuration operation', async (mode, skills, disabled) => {
    const {db, ctx}=fixture(); const app=Fastify();
    db.prepare('UPDATE agent_profiles SET skills_json=?,skills_selection_mode=?').run(JSON.stringify(skills),mode);
    ctx.gateway.authenticate=()=>({node_id:'n',owner_id:'o1'}) as any;
    const requests: Row[]=[];
    ctx.gateway.request=async (_node,action,payload)=>{
      if(action==='agent.capabilities.resolve')return {capabilities:{skills:[{name:'keep'},{name:'blocked'}]}};
      requests.push(payload);
      return {status:'applied',operation_id:payload.operation_id,candidate_fingerprint:payload.candidate_fingerprint,agent:payload.agent};
    };
    registerControlRoutes(app,ctx);
    try {
      const result=await app.inject({method:'POST',url:'/im/v1/agents/a/skills/migrate',headers:{authorization:'Bearer runtime'},payload:{profile_version:1}});
      expect(result.statusCode,result.body).toBe(200);
      expect(result.json()).toMatchObject({skills:disabled,skills_selection_mode:'explicit_denylist',profile_version:2});
      expect(requests).toHaveLength(1);
      const saved=one(db,'SELECT * FROM agent_profiles WHERE agent_id=?','a')!;
      expect(JSON.parse(saved.skills_json)).toEqual(disabled);
      expect(candidateFingerprint(requests[0].agent)).toBe(requests[0].candidate_fingerprint);
      const retry=await app.inject({method:'POST',url:'/im/v1/agents/a/skills/migrate',headers:{authorization:'Bearer runtime'},payload:{profile_version:1}});
      expect(retry.json()).toMatchObject({skills:disabled,profile_version:2});
      expect(requests).toHaveLength(1);
    }finally{await app.close();}
  });
});


it('finishes migration after recovering a pending legacy configuration operation', async () => {
  const {db, ctx} = fixture(); const app = Fastify();
  db.prepare("UPDATE agent_profiles SET skills_json='[\"keep\"]',skills_selection_mode='explicit_allowlist'").run();
  ctx.gateway.authenticate = () => ({node_id:'n',owner_id:'o1'}) as any;
  let recover = false; const calls: string[] = [];
  ctx.gateway.request = async (_node, action, payload) => {
    calls.push(action);
    if (action === 'agent.capabilities.resolve') return {capabilities:{skills:[{name:'keep'},{name:'blocked'}]}};
    if (!recover) return {status:'pending'};
    const op = one(db,'SELECT * FROM agent_config_operations WHERE operation_id=?',payload.operation_id)!;
    return {status:'applied',operation_id:op.operation_id,candidate_fingerprint:op.candidate_fingerprint,agent:JSON.parse(op.candidate_json)};
  };
  const p = one(db,'SELECT * FROM agent_profiles')!;
  await expect(new ConfigOperations(ctx).update(p,{...profileResponse(p,true),display_name:'Recovered edit'},'o1')).rejects.toMatchObject({statusCode:503});
  recover = true; calls.length = 0; registerControlRoutes(app,ctx);
  try {
    const result = await app.inject({method:'POST',url:'/im/v1/agents/a/skills/migrate',headers:{authorization:'Bearer runtime'},payload:{profile_version:1}});
    expect(result.statusCode,result.body).toBe(200);
    expect(result.json()).toMatchObject({display_name:'Recovered edit',skills_selection_mode:'explicit_denylist',skills:['blocked'],profile_version:3});
    expect(calls).toEqual(['agent.config.operation.status','agent.capabilities.resolve','agent.config.apply']);
    expect(one(db,'SELECT skills_selection_mode FROM agent_profiles')?.skills_selection_mode).toBe('explicit_denylist');
  } finally { await app.close(); }
});

it("preserves workspace tool availability in the Agent capabilities response", async () => {
  const {ctx} = fixture();
  ctx.gateway.request = async () => ({capabilities:{tools:[{name:"expense_summary",description:"Monthly expenses",source_group:"workspace",enabled:true,default_on:false}]}});
  const app=Fastify();registerControlRoutes(app,ctx);
  try {
    const response=await app.inject({method:"GET",url:"/im/v1/agents/a/capabilities"});
    expect(response.statusCode).toBe(200);
    expect(response.json().tools).toContainEqual(expect.objectContaining({name:"expense_summary",source_group:"workspace",enabled:true,default_on:false}));
  } finally {await app.close();}
});

it('seals Unicode credentials for the real ChannelKey consumer with unchanged AAD and plaintext bytes', async () => {
  const legacy = JSON.parse(await readFile(new URL('../../../packages/channels/tests/fixtures/credential-envelopes-v1.json', import.meta.url), 'utf8'));
  const directory = await mkdtemp(join(tmpdir(), 'nano-channel-interop-'));
  try {
    await writeFile(join(directory, 'key.pem'), legacy.privateKey, {mode: 0o600});
    const recipient = await ChannelKey.load(join(directory, 'key.pem'));
    const envelope = sealChannelSecret(recipient.registration.credential_public_key, legacy.secret, legacy.aad) as CredentialEnvelope;
    expect(recipient.open(envelope, legacy.aad)).toEqual(legacy.secret);
    // Independent decryption pins bytes, so JSON.parse cannot hide changed escapes.
    const remote = createPublicKey({key:{kty:'OKP',crv:'X25519',x:Buffer.from(envelope.ephemeral_public_key,'base64').toString('base64url')},format:'jwk'});
    const shared = diffieHellman({privateKey:createPrivateKey(legacy.privateKey),publicKey:remote});
    const key = hkdfSync('sha256',shared,Buffer.from(envelope.salt,'base64'),'nano-multiagent/channel-envelope-v1',32);
    const decipher = createDecipheriv('aes-256-gcm',Buffer.from(key),Buffer.from(envelope.nonce,'base64'));
    const bytes = Buffer.from(envelope.ciphertext,'base64');
    decipher.setAAD(Buffer.from(legacy.aadBytes));
    decipher.setAuthTag(bytes.subarray(-16));
    expect(Buffer.concat([decipher.update(bytes.subarray(0,-16)),decipher.final()]).toString('utf8')).toBe(legacy.secretBytes);
  } finally { await rm(directory,{recursive:true,force:true}); }
});
