import Fastify from "fastify";
import { expect, it, vi } from "vitest";
import { fixture } from "./control-fixture.js";
import { Messaging, registerMessagingRoutes } from "../src/messaging.js";
import { all } from "../src/context.js";

it("resolves all preview mentions before truncation, including previously stored previews", () => {
  const { db, ctx } = fixture();
  ctx.gateway.broadcast = vi.fn();
  const messaging = new Messaging(ctx);
  const targets = ["quality-01234567890123456789012345678901", "engineering-01234567890123456789012345678901"];
  for (const [index, id] of targets.entries()) {
    db.prepare("INSERT INTO users(id,username,display_name,owner_id,created_at) VALUES(?,?,?,?,?)")
      .run(id, id, ["Q · 独立质量", "E · 工程交付"][index], "o1", new Date().toISOString());
    db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('chat',?)").run(id);
  }
  const content = targets.map(id => `<mention type="user" target_id="${id}"/>`).join(" ") + " DELIVERY_OK " + "正文".repeat(100);
  const message = messaging.insertMessage("chat", "u1", "user", content);
  // The persisted legacy preview ends inside the second tag.
  expect(content.slice(0, 120)).toContain('<mention type="user" target_id="engineering-');
  const preview = () => messaging.conversations("u1").find(c => c.id === "chat")!.last_message_preview;
  expect(preview()).toBe(("@Q · 独立质量 @E · 工程交付 DELIVERY_OK " + "正文".repeat(100)).slice(0, 120));
  db.prepare("UPDATE users SET display_name='工程交付新版' WHERE id=?").run(targets[1]);
  expect(preview()).toContain("@工程交付新版");
  expect(messaging.message(message.id).content).toBe(content);
});

it("keeps empty conversations, ordinary text and attachment previews", () => {
  const { ctx } = fixture();
  ctx.gateway.broadcast = vi.fn();
  const messaging = new Messaging(ctx);
  expect(messaging.conversation("chat", "u1").last_message_preview).toBeNull();
  messaging.insertMessage("chat", "u1", "user", "  hello  ");
  expect(messaging.conversation("chat", "u1").last_message_preview).toBe("hello");
  messaging.insertMessage("chat", "u1", "user", "", [{ file_name: "report.pdf" }]);
  expect(messaging.conversation("chat", "u1").last_message_preview).toBe("report.pdf");
});

it("projects the actual sender for group previews, including former and external participants", () => {
  const { db, ctx } = fixture();
  ctx.gateway.broadcast = vi.fn();
  const messaging = new Messaging(ctx);
  const preview = () => messaging.conversation("chat", "u1");
  db.exec("UPDATE conversations SET type='group' WHERE id='chat'; UPDATE users SET display_name='林悦' WHERE id='u2'");
  messaging.insertMessage("chat", "u2", "user", "周六见");
  expect(preview()).toMatchObject({ last_message_sender_name: "林悦", last_message_preview: "周六见" });
  messaging.insertMessage("chat", "u1", "user", "", [{ file_name: "预算.pdf" }], null, "completed", {
    sender_display_name: "飞书成员", sender_source_id: "ou-peer",
  });
  expect(preview()).toMatchObject({ last_message_sender_name: "飞书成员", last_message_preview: "预算.pdf" });
  const external = messaging.insertMessage("chat", "u1", "user", "从飞书发送", [], null, "completed", {
    sender_source_id: "ou-peer",
  });
  expect(preview().last_message_sender_name).toBe("ou-peer");
  const event = messaging.records.createdEvent(external.id);
  expect(JSON.parse(event.payload_json).sender_display_name).toBe("ou-peer");
  messaging.insertMessage("chat", "a1", "agent", "", [], null, "completed", {
    sender_display_name: "读书会助手",
    interactive: { format: "openui", catalog_version: "nano-iui-1", source: 'root = Title("读书会预算")' },
  });
  expect(preview()).toMatchObject({ last_message_sender_name: "读书会助手", last_message_card: { title: "读书会预算" } });
  db.exec("UPDATE conversations SET type='direct' WHERE id='chat'");
  expect(preview().last_message_sender_name).toBeNull();
});

it("retains member order and stale badges even when an Agent profile is missing", () => {
  const { db, ctx } = fixture();
  db.exec(`UPDATE agent_profiles SET is_stale=1 WHERE agent_id='a';
    INSERT INTO users(id,username,display_name,owner_id,created_at) VALUES('gone','agent:gone','Former Agent','o1','now');
    INSERT INTO conversation_participants(conversation_id,user_id) VALUES('chat','gone');`);
  const participants=new Messaging(ctx).conversation('chat','u1').participants;
  expect(participants.map(({user_id,is_stale}: {user_id:string,is_stale:boolean|null})=>[user_id,is_stale]))
    .toEqual([['u1',null],['a1',true],['gone',null]]);
});

it.each(["stale profile", "suspended owner"])("completes an ordinary message when its only Agent has a %s", async reason => {
  const { db, ctx } = fixture();
  ctx.gateway.broadcast = vi.fn();
  db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('chat','u2')").run();
  if (reason === "stale profile") db.prepare("UPDATE agent_profiles SET is_stale=1").run();
  else db.prepare("UPDATE users SET membership_status='suspended' WHERE id='u1'").run();
  const messaging = new Messaging(ctx);
  const message = await messaging.sendMessage({headers:{"x-user":"u2"},params:{conversation_id:"chat"},query:{},body:{sender_user_id:"u2",content:"Keep this conversation usable"}} as any);
  expect(message.delivery_status).toBe("completed");
  expect(all(db, "SELECT * FROM relay_tasks")).toEqual([]);
});

it("returns the same authorized cursor without loading a conversation snapshot", async () => {
  const { db, ctx } = fixture();
  ctx.gateway.broadcast = vi.fn();
  ctx.messaging = new Messaging(ctx);
  ctx.messaging.insertMessage("chat", "u1", "user", "cursor baseline");
  const app = Fastify();
  registerMessagingRoutes(app, ctx);
  try {
    const full = await app.inject("/im/v1/sync");
    expect(full.statusCode).toBe(200);
    expect(full.json().items.map((item: {id: string}) => item.id)).toContain("chat");
    expect(full.json().max_event_id).toBeGreaterThan(0);
    const snapshots = vi.spyOn(ctx.messaging, "conversations");
    const cursor = await app.inject("/im/v1/sync?view=cursor");
    expect(cursor.statusCode).toBe(200);
    expect(cursor.json()).toEqual({ max_event_id: full.json().max_event_id });
    expect(snapshots).not.toHaveBeenCalled();

    db.prepare("UPDATE users SET membership_status='suspended' WHERE id='u1'").run();
    for (const path of ["/im/v1/sync", "/im/v1/sync?view=cursor"])
      expect((await app.inject(path)).statusCode).toBe(403);
  } finally {
    await app.close();
  }
});

it("keeps heavy terminal process out of the opt-in history page and scopes full detail to its conversation", async () => {
  const { db, ctx } = fixture();
  ctx.gateway.broadcast = vi.fn();
  ctx.messaging = new Messaging(ctx);
  const message = ctx.messaging.insertMessage("chat", "a1", "agent", "final reply");
  const running = ctx.messaging.insertMessage("chat", "a1", "agent", "still running", [], null, "running");
  const longOutput = "private tool output ".repeat(8_000);
  const toolCalls = [{ id: "allow", name: "read", status: "completed", output: longOutput },
    { id: "legacy-deny", name: "bash", status: "failed", reason: "denied" }];
  const thinking = [{ seq: 0, text: longOutput }];
  const resolved = { request_id: "p", call_id: "allow", status: "resolved", decision: "allow_once", decided_by: "u1" };
  const open = ["pending", "submitted"].map(status => ({
    request_id: status, call_id: status, status, tool_input: { command: status }, question: "Please review"
  }));
  const permissions = [{ ...resolved, tool_input: { command: "large approval arguments ".repeat(8_000) }, question: longOutput }, ...open];
  db.prepare("UPDATE messages SET tool_calls_json=?,thinking_json=?,permission_request_json=? WHERE id=?")
    .run(JSON.stringify(toolCalls), JSON.stringify(thinking), JSON.stringify(permissions), message.id);
  db.prepare("UPDATE messages SET thinking_json=?,permission_request_json=? WHERE id=?")
    .run(JSON.stringify(thinking), JSON.stringify([{ ...resolved, tool_input: { command: longOutput } }]), running.id);
  const insertApprovalHistory = db.prepare(`
    INSERT INTO messages(id,conversation_id,sender_user_id,sender_type,content,delivery_status,created_at,permission_request_json)
    VALUES (?,'chat','a1','agent','approval-only history','completed',?,?)
  `);
  for (let index = 0; index < 48; index++) {
    insertApprovalHistory.run(`approval-history-${index}`, new Date().toISOString(), JSON.stringify([permissions[0]]));
  }
  db.exec("INSERT INTO conversations(id,title,type,owner_id,creator_id,space_id,created_at) SELECT 'other','Other',type,owner_id,creator_id,space_id,created_at FROM conversations WHERE id='chat'; INSERT INTO conversation_participants(conversation_id,user_id) VALUES('other','u1')");
  const app = Fastify();
  registerMessagingRoutes(app, ctx);
  try {
    const path = "/im/v1/conversations/chat/messages";
    const legacy = await app.inject(path);
    const summary = await app.inject(path + "?view=summary");
    const rows = summary.json().items.map((item: { message: unknown }) => item.message);
    const legacyRows = legacy.json().items.map((item: { message: unknown }) => item.message);
    expect(rows).toHaveLength(50);
    expect(rows[0]).toMatchObject({ id: message.id, content: "final reply",
      process_summary: { tool_count: 2, thinking_count: 1, approval_allow_count: 1, approval_deny_count: 1 } });
    expect(rows[0].permission_requests).toEqual([resolved, ...open]);
    expect(summary.body).not.toContain("large approval arguments");
    expect(legacy.body).toContain("large approval arguments");
    expect(rows[0].tool_calls ?? []).toEqual([]);
    expect(rows[0].thinking ?? []).toEqual([]);
    expect(rows[1]).toEqual(legacyRows[1]);
    expect(summary.body.length).toBeLessThan(legacy.body.length / 2);
    const detail = await app.inject(path + "/" + message.id);
    expect(detail.json()).toMatchObject({ message: legacyRows[0], execution_cleanup_revision: 0 });
    expect((await app.inject("/im/v1/conversations/other/messages/" + message.id)).statusCode).toBe(404);
    expect((await app.inject({ url: path + "/" + message.id, headers: { "x-user": "u2" } })).statusCode).toBe(404);
  } finally {
    await app.close();
  }
});
