import { expect, it, vi } from "vitest";
import { fixture } from "./control-fixture.js";
import { Messaging } from "../src/messaging.js";
import { all } from "../src/context.js";

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
