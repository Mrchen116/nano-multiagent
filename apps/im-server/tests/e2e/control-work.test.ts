import { expect, it } from "vitest";
import { once } from "node:events";
import { start, bind } from "./helpers.js";

it("transports configuration receipts, encrypted channel manifests and global Work over the real socket", async () => {
  const f = await start(),
    g = await bind(f, "node-a", {assistant: {skills: [], tool_allowlist: ["task_graph"], display_name: "Local title", default_model: "deepseek:test", custom_prompt: "Local prompt", reasoning_effort: "high", features: {heartbeat: true}}});
  const mirror = await f.http(
    "GET",
    "/im/v1/agents/assistant/config?source=mirror",
    undefined,
    f.tokens.alice,
  );
  expect(mirror.status, mirror.body).toBe(200);
  expect(mirror.body).toMatchObject({display_name: "Local title", default_model: "deepseek:test", custom_prompt: "Local prompt", reasoning_effort: "high", features: {heartbeat: true}});
  const updated = f.http(
    "PATCH",
    "/im/v1/agents/assistant/config",
    {
      ...mirror.body,
      display_name: "Configured",
      group_reply_policy: "manual",
    },
    f.tokens.alice,
  );
  const apply = await Promise.race([g.frames.next((p) => p.type === "agent.config.apply"), updated.then(r=>{throw new Error(JSON.stringify(r.body));})]);
  expect(apply.payload.candidate_fingerprint).toMatch(/^[a-f0-9]{64}$/);
  // An unrelated response with a matching ID cannot complete this operation.
  expect(
    (
      await g.frames.send("node.heartbeat", {
        node_id: g.node,
        request_id: apply.payload.request_id,
      })
    ).type,
  ).toBe("ack");
  const result = {
    node_id: g.node,
    request_id: apply.payload.request_id,
    operation_id: apply.payload.operation_id,
    candidate_fingerprint: apply.payload.candidate_fingerprint,
    status: "applied",
    agent: apply.payload.agent,
  };
  expect((await g.frames.send("agent.config.apply.result", result)).type).toBe("ack");
  const applied = await updated;
  expect(applied.status, applied.body).toBe(200);
  expect(applied.body.display_name).toBe("Configured");
  expect(applied.body.profile_version).toBe(mirror.body.profile_version + 1);
  await g.frames.send("node.register", {node_id: g.node, agents: ["assistant", "global"], agent_configurations: {assistant: {display_name: "Outdated local"}}});
  expect((await f.http("GET", "/im/v1/agents/assistant/config?source=mirror", undefined, f.tokens.alice)).body.display_name).toBe("Configured");
  const liveRequest = f.http("GET", "/im/v1/agents/assistant/config", undefined, f.tokens.alice);
  const get = await g.frames.next((p) => p.type === "agent.config.get");
  await g.frames.send("agent.config", {
    node_id: g.node,
    request_id: get.payload.request_id,
    agent: result.agent,
  });
  expect((await liveRequest).body.display_name).toBe("Configured");

  expect(
    (
      await g.frames.send("channels.bootstrap", {
        node_id: g.node,
        request_id: "initial-bootstrap",
        items: [],
      })
    ).type,
  ).toBe("channels.bootstrap.result");
  const created = await f.http(
    "POST",
    "/im/v1/agents/assistant/channels",
    {
      provider: "feishu",
      enabled: true,
      config: { app_id: "cli_real_transport" },
      credentials: { mode: "replace", app_secret: "never-return-this-secret" },
    },
    f.tokens.alice,
  );
  expect(created.status, created.body).toBe(201);
  expect(JSON.stringify(created.body)).not.toContain("never-return-this-secret");
  const manifest = await g.frames.next((p) => p.type === "channel.reconcile");
  expect(manifest.payload.channels[0].credential_envelope.ciphertext).toBeTruthy();
  expect(JSON.stringify(manifest)).not.toContain("never-return-this-secret");
  const boot = await g.frames.send("channels.bootstrap", {
    node_id: g.node,
    request_id: "bootstrap",
    items: [],
  });
  expect(boot.type).toBe("channels.bootstrap.result");
  expect(boot.payload.manifest.channels[0].channel_id).toBe(created.body.channel_id);

  const stamp = new Date().toISOString();
  const events = [
    {
      seq: 1,
      event_id: "work-1",
      root_agent_id: "global",
      session_id: "global-session",
      type: "session_registered",
      observed_at: stamp,
      payload: { scope: "global_main" },
    },
    {
      seq: 2,
      event_id: "work-2",
      root_agent_id: "global",
      session_id: "global-session",
      turn_id: "turn-1",
      type: "turn_start",
      observed_at: stamp,
      payload: { run_id: "run-global", origin: "inbox" },
    },
    {
      seq: 3,
      event_id: "work-3",
      root_agent_id: "global",
      session_id: "global-session",
      turn_id: "turn-1",
      type: "tool_start",
      observed_at: stamp,
      payload: { call_id: "call-1", name: "task_graph", arguments: { action: "list" } },
    },
    {
      seq: 4,
      event_id: "work-4",
      root_agent_id: "global",
      session_id: "global-session",
      turn_id: "turn-1",
      type: "tool_end",
      observed_at: stamp,
      payload: { call_id: "call-1", name: "task_graph", presentation: { summary: "2 graphs" } },
    },
    {
      seq: 5,
      event_id: "work-5",
      root_agent_id: "global",
      session_id: "global-session",
      turn_id: "turn-1",
      type: "turn_end",
      observed_at: stamp,
      payload: { completed: true, usage: { prompt_tokens: 100, completion_tokens: 10 } },
    },
  ];
  const append = { node_id: g.node, journal_id: "journal", from_seq: 1, events };
  expect((await g.frames.send("agent.work.append", append)).payload.through_seq).toBe(5);
  expect((await g.frames.send("agent.work.append", append)).payload.through_seq).toBe(5);
  const work = await f.http("GET", "/im/v1/agents/global/work", undefined, f.tokens.bob);
  expect(work.status, work.body).toBe(200);
  expect(work.body.turns).toHaveLength(1);
  expect(work.body.turns[0].status).toBe("completed");
  expect(work.body.turns[0].items[0].payload.output).toBe("2 graphs");
  expect(work.body.latest_main_usage.output).toBe(10);
  const chat = await f.http(
    "POST",
    "/im/v1/conversations",
    { title: "Global chat", type: "direct", participants: [{ type: "agent", id: "global" }] },
    f.tokens.alice,
  );
  const sent = await f.http(
    "POST",
    `/im/v1/conversations/${chat.body.id}/messages`,
    { content: "inspect shared history", sender_user_id: "alice" },
    f.tokens.alice,
  );
  expect(sent.status, sent.body).toBe(201);
  const listing = await g.frames.send("conversation.query", {
    node_id: g.node,
    request_id: "q1",
    agent_id: "global",
    session_id: "global-session",
    action: "list",
  });
  expect(listing.payload.result.conversations[0].history_availability).toBe("im_history");
  const history = await g.frames.send("conversation.query", {
    node_id: g.node,
    request_id: "q2",
    agent_id: "global",
    session_id: "global-session",
    action: "read",
    target: chat.body.id,
  });
  expect(history.payload.result.messages[0].content[0].text).toBe("inspect shared history");
  f.child.kill("SIGTERM");
  await once(f.child, "exit");
  const restored = await start(f.dbPath);
  expect(
    (
      await restored.http(
        "GET",
        "/im/v1/agents/assistant/config?source=mirror",
        undefined,
        f.tokens.alice,
      )
    ).body.display_name,
  ).toBe("Configured");
  expect(
    (await restored.http("GET", "/im/v1/agents/global/work", undefined, f.tokens.bob)).body.turns[0]
      .status,
  ).toBe("completed");
  expect(
    (await restored.http("GET", "/im/v1/agents/assistant/channels", undefined, f.tokens.alice))
      .body[0].channel_id,
  ).toBe(created.body.channel_id);
  expect((await restored.http("GET", "/im/v1/gateway/identity", undefined, g.token)).status).toBe(
    401,
  );
});

it("keeps external shadow identity stable and forks an acknowledged kernel message with copied display history", async () => {
  const f = await start(),
    g = await bind(f);
  const external = {
    agent_id: "assistant",
    external_source: "feishu",
    external_chat_id: "oc-chat",
    title: "Feishu",
  };
  const first = await f.http(
    "POST",
    "/im/v1/conversations/external/find-or-create",
    external,
    g.token,
  );
  expect(first.status, first.body).toBe(201);
  const second = await f.http(
    "POST",
    "/im/v1/conversations/external/find-or-create",
    { ...external, title: "Updated" },
    g.token,
  );
  expect(second.body.id).toBe(first.body.id);
  const path = `/im/v1/conversations/${first.body.id}/external-agent-messages/shadow-1`;
  const snapshot = {
    agent_id: "assistant",
    content: "external answer",
    delivery_status: "completed",
    elapsed_ms: 4,
    kernel_message_id: "kernel-1",
  };
  const message = await f.http("PUT", path, snapshot, g.token);
  expect(message.status, message.body).toBe(200);
  expect((await f.http("PUT", path, snapshot, g.token)).body.id).toBe(message.body.id);
  const forkRequest = f.http(
    "POST",
    `/im/v1/conversations/${first.body.id}/fork`,
    { fork_message_id: message.body.id },
    f.tokens.alice,
  );
  const frame = await g.frames.next((p) => p.type === "session.fork.request");
  expect(frame.payload.fork_point).toEqual({ message_id: "kernel-1" });
  await g.frames.send("session.fork.result", {
    node_id: g.node,
    request_id: frame.payload.request_id,
    ok: true,
    id_map: { "kernel-1": "kernel-2" },
  });
  const forked = await forkRequest;
  expect(forked.status, forked.body).toBe(201);
  const history = await f.http(
    "GET",
    `/im/v1/conversations/${forked.body.id}/messages`,
    undefined,
    f.tokens.alice,
  );
  expect(history.body.items[0].message.content).toBe("external answer");
  expect(history.body.items[0].message.kernel_message_id).toBe("kernel-2");
});

it("returns the node's actual Skill usage envelope through the public endpoint", async () => {
  const f = await start(), g = await bind(f);
  const pending = f.http("GET", "/im/v1/agents/assistant/skills/usage", undefined, f.tokens.alice);
  const request = await g.frames.next(frame => frame.type === "node.skills.usage.request");
  const usage = {
    agent_id: "assistant", node_id: g.node,
    skills: [{ name: "reviewed", source: "F3", state: "archived", use_count: 20 }],
    heatmap_data: Array.from({ length: 30 }, (_, i) => i === 29 ? 1 : 0),
    health: { created_auto_total: 1, active_auto_total: 0, used_auto_total: 1 },
  };
  await g.frames.send("node.skills.usage", { node_id: g.node, request_id: request.payload.request_id, usage });
  const response = await pending;
  expect(response.status, response.body).toBe(200);
  expect(response.body).toEqual({ ...usage, node_online: true });
});
