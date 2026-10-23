import { expect, it, vi } from "vitest";
import { fixture } from "./control-fixture.js";
import { Messaging } from "../src/messaging.js";
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
