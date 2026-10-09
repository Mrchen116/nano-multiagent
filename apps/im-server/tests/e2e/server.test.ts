import { expect, it } from "vitest";
import WebSocket from "ws";
import { once } from "node:events";
import { Frames, start, bind, cleanups } from "./helpers.js";
it("serves auth, live node relay, idempotent streaming, private media, task graphs and replay through a real process", async () => {
  const f = await start(),
    g = await bind(f);
  expect((await f.http("GET", "/im/v1/gateway/identity", undefined, g.runtime)).status).toBe(401);
  expect((await f.http("GET", "/im/v1/gateway/identity", undefined, g.token)).status).toBe(200);
  const create = await f.http(
    "POST",
    "/im/v1/conversations",
    {
      title: "Chat",
      type: "direct",
      participants: [{ type: "agent", id: "assistant" }],
    },
    f.tokens.alice,
  );
  expect(create.status, create.body).toBe(201);
  expect(create.body.direct_kind).toBe("user-agent");
  const id = create.body.id;
  expect(
    (await f.http("GET", `/im/v1/conversations/${id}`, undefined, f.tokens.outsider)).status,
  ).toBe(404);
  const ticket = await f.http("POST", "/im/v1/auth/ws-ticket", {}, f.tokens.alice);
  const browser = new WebSocket(
      f.base.replace("http:", "ws:") + `/im/ws/user?ticket=${ticket.body.ticket}`,
      { headers: { Origin: "http://127.0.0.1:8011" } },
    ),
    events = new Frames(browser);
  await once(browser, "open");
  cleanups.push(() => browser.terminate());
  browser.send(JSON.stringify({ op: "resume", after_event_id: 0 }));
  const sent = await f.http(
    "POST",
    `/im/v1/conversations/${id}/messages`,
    { sender_user_id: "alice", content: "hello" },
    f.tokens.alice,
    { "Idempotency-Key": "once" },
  );
  expect(sent.status, sent.body).toBe(201);
  const relay = await g.frames.next((p) => p.type === "relay.message");
  expect(relay.payload.message.id).toBe(sent.body.id);
  expect(relay.payload.metadata.node_epoch).toBe(1);
  const again = await f.http(
    "POST",
    `/im/v1/conversations/${id}/messages`,
    { sender_user_id: "alice", content: "hello" },
    f.tokens.alice,
    { "Idempotency-Key": "once" },
  );
  expect(again.body.id).toBe(sent.body.id);
  const started = await g.frames.send("node.streaming_delta", {
    node_id: g.node,
    kind: "turn_start",
    conversation_id: id,
    agent_id: "assistant",
    idempotency_key: "turn-once",
    run_id: "run",
  });
  expect(started.type, started).toBe("ack");
  const message = started.payload.message_id;
  const retry = await g.frames.send("node.streaming_delta", {
    node_id: g.node,
    kind: "turn_start",
    conversation_id: id,
    agent_id: "assistant",
    idempotency_key: "turn-once",
    run_id: "run",
  });
  expect(retry.payload.message_id).toBe(message);
  for (let i = 0; i < 2; i++)
    expect(
      (
        await g.frames.send("node.streaming_delta", {
          node_id: g.node,
          kind: "message_delta",
          message_id: message,
          delta_text: "answer",
          idempotency_key: "d1",
        })
      ).type,
    ).toBe("ack");
  expect(
    (
      await g.frames.send("node.streaming_delta", {
        node_id: g.node,
        kind: "message_completed",
        message_id: message,
        final_content: "answer",
        elapsed_ms: 5,
        kernel_message_id: "dsh-m1",
        token_usage: { output: 2, context_used: 3, context_window: 100 },
      })
    ).type,
  ).toBe("ack");
  const completed = await events.next((p) => p.event_type === "message.completed");
  expect(completed.data.message_id).toBe(message);
  const history = await f.http(
    "GET",
    `/im/v1/conversations/${id}/messages`,
    undefined,
    f.tokens.alice,
  );
  expect(
    history.body.items.filter((x: any) => x.type === "message").map((x: any) => x.message.content),
  ).toEqual(["hello", "answer"]);
  const upload = await f.http(
    "POST",
    `/im/v1/uploads?conversation_id=${id}&file_name=note.txt`,
    "private contents",
    f.tokens.alice,
    { "content-type": "text/plain" },
  );
  expect(upload.status, upload.body).toBe(201);
  expect((await f.http("GET", upload.body.url, undefined, f.tokens.alice)).body).toBe(
    "private contents",
  );
  expect((await f.http("GET", upload.body.url, undefined, f.tokens.outsider)).status).toBe(404);
  const task = await g.frames.send("task_graph.command", {
    node_id: g.node,
    agent_id: "assistant",
    request_id: "task1",
    action: "create",
    args: {
      title: "Plan",
      mode: "dag",
      request_key: "create",
      conversation_id: id,
    },
  });
  expect(task.payload.ok, task).toBe(true);
  const replay = await g.frames.send("task_graph.command", {
    node_id: g.node,
    agent_id: "assistant",
    request_id: "task2",
    action: "create",
    args: {
      title: "Plan",
      mode: "dag",
      request_key: "create",
      conversation_id: id,
    },
  });
  expect(replay.payload.result).toEqual(task.payload.result);
  expect(
    (
      await f.http(
        "GET",
        `/im/v1/task-graphs/${task.payload.result.graph_id}`,
        undefined,
        f.tokens.bob,
      )
    ).status,
  ).toBe(200);
  const cursor = completed.event_id;
  browser.send(JSON.stringify({ op: "resume", after_event_id: cursor - 1 }));
  expect((await events.next((p) => p.event_id === cursor)).data.content).toBe("answer");
}, 20000);
it("keeps first approval choice and revokes user and machine access at company suspension", async () => {
  const f = await start(),
    g = await bind(f);
  const c = await f.http(
    "POST",
    "/im/v1/conversations",
    {
      title: "Shared",
      type: "group",
      participants: [
        { type: "user", id: "bob" },
        { type: "agent", id: "assistant" },
      ],
    },
    f.tokens.alice,
  );
  const id = c.body.id;
  const started = await g.frames.send("node.streaming_delta", {
    node_id: g.node,
    kind: "turn_start",
    conversation_id: id,
    agent_id: "assistant",
    run_id: "run",
    idempotency_key: "permission-turn",
  });
  const mid = started.payload.message_id;
  await g.frames.send("node.streaming_delta", {
    node_id: g.node,
    kind: "permission_request",
    message_id: mid,
    run_id: "run",
    permission_request: {
      request_id: "ask",
      call_id: "write-call",
      options: [{ id: "allow_once" }, { id: "deny" }],
    },
  });
  const decision = await f.http(
    "POST",
    `/im/v1/conversations/${id}/permissions/ask`,
    { message_id: mid, decision: "allow_once" },
    f.tokens.bob,
  );
  expect(decision.status, decision.body).toBe(200);
  expect(decision.body).toMatchObject({
    status: "submitted",
    decision: "allow_once",
    decided_by: "bob",
  });
  expect(
    (
      await g.frames.next(
        (p) => p.type === "node.streaming_delta" && p.payload.kind === "permission_response",
      )
    ).payload.decision,
  ).toBe("allow_once");
  const late = await f.http(
    "POST",
    `/im/v1/conversations/${id}/permissions/ask`,
    { message_id: mid, decision: "deny" },
    f.tokens.alice,
  );
  expect(late.body.decision).toBe("allow_once");
  await g.frames.send("node.streaming_delta", {node_id:g.node, kind:"permission_resolved", message_id:mid, request_id:"ask", decision:"allow_once"});
  await g.frames.send("node.streaming_delta", {node_id:g.node, kind:"tool_call_completed", message_id:mid, tool_call:{id:"write-call",name:"write",status:"completed",output:"written"}});
  const history = await f.http("GET", `/im/v1/conversations/${id}/messages`, undefined, f.tokens.alice);
  expect(history.body.items.find((item: any) => item.message?.id === mid).message.tool_calls[0].approval).toBe("user_allow");
  expect(
    (await f.http("POST", "/im/v1/company/members/bob/suspend", {}, f.tokens.alice)).status,
  ).toBe(200);
  expect((await f.http("GET", `/im/v1/conversations/${id}`, undefined, f.tokens.bob)).status).toBe(
    401,
  );
  g.socket.close();
  await once(g.socket, "close");
  expect((await f.http("GET", "/im/v1/gateway/identity", undefined, g.token)).status).toBe(401);
}, 20000);
