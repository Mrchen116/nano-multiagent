import { describe, expect, it } from "vitest";
import Fastify from "fastify";
import {
  createDecipheriv,
  createPublicKey,
  diffieHellman,
  generateKeyPairSync,
  hkdfSync,
} from "node:crypto";
import { Messaging } from "../src/messaging.js";
import { TaskGraphService, canonicalJson } from "../src/task-graphs.js";
import { ChannelService, sealChannelSecret } from "../src/channels.js";
import { ConfigOperations, candidateFingerprint, registerControlRoutes } from "../src/control.js";
import { one, type ImContext, type Row } from "../src/context.js";
import { fixture } from "./control-fixture.js";
const actor = { kind: "agent" as const, id: "a", node_id: "n" };
describe("company task graph atomic storage", () => {
  it("rolls back invalid DAG mutations and replays receipts after graph deletion", () => {
    const { db } = fixture(),
      s = new TaskGraphService(db);
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
    const other = s.execute({ kind: "user", id: "u2" }, "get", {
      graph_id: created.graph_id,
      view: "all",
    });
    expect(other.nodes[0].last_chat_id).toBeNull();
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
    const { db } = fixture(), service = new TaskGraphService(db);
    const created = service.execute(actor, 'create', {title:'计划',mode:'dag',request_key:'create'});
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
      s = new TaskGraphService(db);
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
        canonicalJson({
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
    const createdGroup = messaging.createConversation({id: "u1", owner_id: "o1"}, group);
    expect(createdGroup.type).toBe("group");
    expect(messaging.mentionedAgents(createdGroup.id, `<mention type="user" target_id="${messaging.agentUser("new-agent").id}"/> ping`)).toEqual(["new-agent"]);
    expect(() => messaging.createConversation({id: "u2", owner_id: "o2"}, group)).toThrow("agent not accessible");
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
        work_mode: "single_thread",
        workspace_root: "/agent",
        features: {},
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
    expect(one(db, "SELECT status FROM agent_config_operations")?.status).toBe("committed");
  });
  it("compensates Gateway after profile CAS loses while preserving concurrent values", async () => {
    const { db, ctx } = fixture(),
      ops = new ConfigOperations(ctx);
    const calls: Row[] = [];
    ctx.gateway.request = async (_n, action, p) => {
      calls.push(p);
      if (calls.length === 1)
        db.prepare("UPDATE agent_profiles SET display_name='Concurrent',profile_version=2").run();
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
          agent_id: "a",
          display_name: "Candidate",
          workspace_root: "/agent",
          tool_allowlist: ["task_graph"],
        },
        "o1",
      ),
    ).rejects.toMatchObject({ statusCode: 409 });
    expect(calls).toHaveLength(2);
    expect(calls[1].agent.display_name).toBe("Concurrent");
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
