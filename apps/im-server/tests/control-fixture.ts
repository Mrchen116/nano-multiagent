import { Gateway, type Connection } from "../src/gateway.js";
import { afterEach } from "vitest";
import { createIdentity } from "../src/identity.js";
import { openDatabase } from "../src/db.js";
import type { ImContext } from "../src/context.js";
const databases: ReturnType<typeof openDatabase>[] = [];
afterEach(() => {
  for (const db of databases.splice(0)) db.close();
});
export function fixture() {
  const db = openDatabase(":memory:");
  databases.push(db);
  const now = new Date().toISOString();
  for (const [id, username, owner] of [
    ["u1", "alice", "o1"],
    ["u2", "bob", "o2"],
    ["a1", "agent:a", "o1"],
  ])
    db.prepare(
      "INSERT INTO users(id,username,display_name,owner_id,created_at,membership_status,is_company_admin) VALUES(?,?,?,?,?,'active',1)",
    ).run(id, username, id, owner, now);
  db.prepare(
    "INSERT INTO nodes(node_id,owner_id,node_name,status) VALUES('n','o1','Node','online')",
  ).run();
  db.prepare(
    "INSERT INTO agent_profiles(agent_id,owner_id,node_id,display_name,tool_allowlist_json,workspace_root,created_at,updated_at) VALUES('a','o1','n','Agent','[\"task_graph\"]','/agent',?,?)",
  ).run(now, now);
  db.prepare("INSERT INTO conversations(id,title,created_at) VALUES('chat','Chat',?)").run(now);
  for (const user of ["u1", "a1"])
    db.prepare(
      "INSERT INTO conversation_participants(conversation_id,user_id) VALUES('chat',?)",
    ).run(user);
  const identity = createIdentity(db, "control-test-secret");
  identity.authenticateRequest = (req: any) => identity.user(req.headers["x-user"] === "u2" ? "u2" : "u1")!;
  const ctx = {
    db,
    identity,
    publicUrl: 'http://im.test',
    gateway: {
      nodes: new Map(),
      request: async () => null,
      send: () => false,
      isOnline: () => false,
      authenticate: () => null,
    },
  } as unknown as ImContext;
  return { db, ctx };
}

/** Attach a genuine binding/socket seam while preserving each test's RPC handler. */
export function connectFixtureGateway({ctx,db}: ReturnType<typeof fixture>): Connection {
  db.prepare("INSERT OR IGNORE INTO users(id,username,display_name,owner_id,created_at,membership_status) VALUES('o1','owner-binding','Owner','o1',datetime('now'),'active')").run();
  db.prepare("INSERT OR IGNORE INTO node_binding_state(node_id,owner_id,node_epoch) VALUES('n','o1',1)").run();
  const gateway=new Gateway(ctx);
  const connection={node_id:'n',owner_id:'o1',node_epoch:1,socket:{readyState:1}} as Connection;
  ctx.gateway.nodes.set('n',connection);
  ctx.gateway.valid=gateway.valid.bind(gateway);
  return connection;
}
