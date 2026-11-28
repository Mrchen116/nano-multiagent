import { afterEach, expect, it } from "vitest";
import { existsSync, mkdtempSync, readdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { randomBytes } from "node:crypto";
import sharp from "sharp";
import WebSocket from "ws";
import { createServer } from "../src/server.js";
import { TaskGraphService } from "../src/task-graphs.js";

const cleanups: Array<() => unknown | Promise<unknown>> = [];
afterEach(async () => {
  for (const close of cleanups.splice(0).reverse()) await close();
});

async function createFixture(listen = false) {
  const dir = mkdtempSync(join(tmpdir(), "im-user-avatar-"));
  cleanups.push(() => rmSync(dir, { recursive: true, force: true }));
  const app = await createServer({
    dbPath: join(dir, "im.db"),
    publicUrl: "http://127.0.0.1:18080",
    jwtSecret: "user-avatar-test-secret-32-chars!!",
  });
  cleanups.push(() => app.close());
  const baseUrl = listen ? await app.listen({ host: "127.0.0.1", port: 0 }) : "http://127.0.0.1:18080";
  const register = async (name: string) => app.im.identity.register(name, "password-123", name);
  const req = (token: string, method: any, url: string, payload?: any, headers?: Record<string, string>) =>
    app.inject({
      method,
      url,
      payload,
      headers: { authorization: `Bearer ${token}`, ...headers },
    });
  return { app, db: app.im.db, dir, baseUrl, register, req };
}

async function makePng(width = 320, height = 240, color = { r: 210, g: 110, b: 90 }): Promise<Buffer> {
  return sharp({ create: { width, height, channels: 3, background: color } }).png().toBuffer();
}

it("normalizes static uploads up to 5 MiB into 256x256 EXIF-free WebP, projects to human exits only, and cleans up on replace or delete", async () => {
  const { app, db, dir, register, req } = await createFixture();
  const admin = await register("admin");
  app.im.identity.initializeCompany(admin.user.id);
  const alice = await register("alice");
  await req(alice.access_token, "POST", "/im/v1/company/join", {});
  await req(admin.access_token, "POST", `/im/v1/company/members/${alice.user.id}/approve`, {});
  const aliceFresh = await app.im.identity.login("alice", "password-123");

  // Build a >2 MiB (above root 2 MiB JSON limit, below 5 MiB avatar limit) noisy PNG with EXIF metadata.
  const noisy = randomBytes(900 * 900 * 3);
  const largePng = await sharp(noisy, { raw: { width: 900, height: 900, channels: 3 } })
    .withMetadata({ exif: { IFD0: { Artist: "SecretGPSOwner", Copyright: "PrivateMeta" } } })
    .png({ compressionLevel: 0 })
    .toBuffer();
  expect(largePng.byteLength).toBeGreaterThan(2 * 1024 * 1024);
  expect(largePng.byteLength).toBeLessThan(5 * 1024 * 1024);

  const put1 = await req(aliceFresh.access_token, "PUT", "/im/v1/me/avatar", largePng, { "content-type": "image/png" });
  expect(put1.statusCode, put1.body).toBe(200);
  const v1 = put1.json().avatar_version;
  expect(v1).toMatch(/^[0-9a-f]{12}$/);

  const avatarDir = join(dir, "user-avatars");
  expect(readdirSync(avatarDir).filter(f => !f.startsWith("."))).toHaveLength(1);

  const fetched = await req(admin.access_token, "GET", `/im/v1/users/${alice.user.id}/avatar?v=${v1}`);
  expect(fetched.statusCode).toBe(200);
  expect(fetched.headers["content-type"]).toContain("image/webp");
  expect(fetched.headers["cache-control"]).toBe("private, no-store");
  expect(fetched.headers["x-content-type-options"]).toBe("nosniff");
  expect(fetched.headers["content-security-policy"]).toBe("default-src 'none'");
  const meta = await sharp(fetched.rawPayload).metadata();
  expect({ format: meta.format, width: meta.width, height: meta.height, hasExif: Boolean(meta.exif) }).toEqual({
    format: "webp",
    width: 256,
    height: 256,
    hasExif: false,
  });

  // Updating display_name preserves avatar_version.
  const patched = await req(aliceFresh.access_token, "PATCH", "/im/v1/me", { display_name: "Alice Lin" });
  expect(patched.statusCode).toBe(200);
  expect(patched.json()).toMatchObject({ display_name: "Alice Lin", avatar_version: v1 });
  expect((await req(aliceFresh.access_token, "GET", "/im/v1/auth/me")).json().avatar_version).toBe(v1);
  expect((await req(admin.access_token, "GET", "/im/v1/contacts?kind=human")).json().items).toEqual(
    expect.arrayContaining([expect.objectContaining({ user_id: alice.user.id, avatar_version: v1 })]),
  );
  expect((await req(admin.access_token, "GET", "/im/v1/company/members")).json().members).toEqual(
    expect.arrayContaining([expect.objectContaining({ id: alice.user.id, avatar_version: v1 })]),
  );

  // Chat human exits project avatar_version on primary slots (participants, sender, receipts, thread, tasks) but NOT reply_to or internal messaging.message().
  const group = (await req(admin.access_token, "POST", "/im/v1/conversations", {
    title: "Product",
    type: "group",
    participants: [{ type: "user", id: alice.user.id }],
  })).json();
  expect(group.participants).toEqual(
    expect.arrayContaining([
      expect.objectContaining({ id: alice.user.id, avatar_version: v1 }),
      expect.objectContaining({ id: admin.user.id, avatar_version: null }),
    ]),
  );
  const firstMsg = (await req(aliceFresh.access_token, "POST", `/im/v1/conversations/${group.id}/messages`, {
    sender_user_id: alice.user.id,
    content: "Hello team",
  })).json();
  expect(firstMsg.sender.avatar_version).toBe(v1);

  const replyMsg = (await req(admin.access_token, "POST", `/im/v1/conversations/${group.id}/messages`, {
    sender_user_id: admin.user.id,
    content: "Replying cleanly",
    reply_to_message_id: firstMsg.id,
  })).json();
  expect(replyMsg.sender.avatar_version).toBeNull();
  expect(replyMsg.reply_to.sender).not.toHaveProperty("avatar_version");
  expect(app.im.messaging.message(firstMsg.id).sender).not.toHaveProperty("avatar_version");

  const tasks = new TaskGraphService(db, app.im.messaging);
  const createdTask = (await req(aliceFresh.access_token, "POST", "/im/v1/task-graphs", {
    conversation_id: group.id,
    title: "Ship avatars",
    request_key: "rk-task-1",
    assignee: { type: "user", id: alice.user.id },
  })).json();
  const fetchedTask = (await req(aliceFresh.access_token, "GET", `/im/v1/task-graphs/${createdTask.graph_id}`)).json();
  expect(fetchedTask.root.assignee.avatar_version).toBe(v1);
  expect(fetchedTask.root.created_by.avatar_version).toBe(v1);
  const gatewayTask = tasks.execute({ kind: "user", id: alice.user.id }, "get", { graph_id: createdTask.graph_id, view: "all" });
  expect(gatewayTask.nodes[0].assignee).not.toHaveProperty("avatar_version");

  // Uploading the exact same image again generates a fresh version (A -> B -> A cache busting) and unlinks old file.
  const jpeg = await sharp({ create: { width: 200, height: 200, channels: 3, background: { r: 20, g: 80, b: 160 } } }).jpeg().toBuffer();
  const put2 = await req(aliceFresh.access_token, "PUT", "/im/v1/me/avatar", jpeg, { "content-type": "image/jpeg" });
  const v2 = put2.json().avatar_version;
  expect(v2).not.toBe(v1);
  expect(readdirSync(avatarDir).filter(f => !f.startsWith("."))).toHaveLength(1);

  // Deleting clears columns and disk file idempotently.
  const del = await req(aliceFresh.access_token, "DELETE", "/im/v1/me/avatar");
  expect(del.statusCode).toBe(200);
  expect(del.json().avatar_version).toBeNull();
  expect(readdirSync(avatarDir).filter(f => !f.startsWith("."))).toHaveLength(0);
  expect((await req(aliceFresh.access_token, "DELETE", "/im/v1/me/avatar")).statusCode).toBe(200);
  expect((await req(admin.access_token, "GET", `/im/v1/users/${alice.user.id}/avatar`)).statusCode).toBe(404);
});

it("rejects empty, oversized, animated, mismatched, corrupt, and >4096px images while preserving existing avatar", async () => {
  const { register, req } = await createFixture();
  const user = await register("validator");
  const valid = await makePng(128, 128);
  const initial = (await req(user.access_token, "PUT", "/im/v1/me/avatar", valid, { "content-type": "image/png" })).json();
  expect(initial.avatar_version).toMatch(/^[0-9a-f]{12}$/);

  expect((await req(user.access_token, "PUT", "/im/v1/me/avatar", Buffer.alloc(0), { "content-type": "image/png" })).statusCode).toBe(400);
  expect((await req(user.access_token, "PUT", "/im/v1/me/avatar", Buffer.alloc(5 * 1024 * 1024 + 64, 1), { "content-type": "image/png" })).statusCode).toBe(413);
  const gif = Buffer.from("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7", "base64");
  expect((await req(user.access_token, "PUT", "/im/v1/me/avatar", gif, { "content-type": "image/gif" })).statusCode).toBe(415);
  expect((await req(user.access_token, "PUT", "/im/v1/me/avatar", valid, { "content-type": "image/jpeg" })).statusCode).toBe(415);
  const corruptPng = Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), Buffer.from("corrupt-body")]);
  expect((await req(user.access_token, "PUT", "/im/v1/me/avatar", corruptPng, { "content-type": "image/png" })).statusCode).toBe(422);
  const tooWide = await sharp({ create: { width: 4100, height: 64, channels: 3, background: { r: 0, g: 0, b: 0 } } }).png().toBuffer();
  expect((await req(user.access_token, "PUT", "/im/v1/me/avatar", tooWide, { "content-type": "image/png" })).statusCode).toBe(422);

  // Existing avatar remains intact.
  expect((await req(user.access_token, "GET", "/im/v1/me")).json().avatar_version).toBe(initial.avatar_version);
  expect((await req(user.access_token, "GET", `/im/v1/users/${user.user.id}/avatar`)).statusCode).toBe(200);
});

it("serializes concurrent PUT and DELETE for the same user and enforces selfManagedAuth visibility matrix", async () => {
  const { app, db, dir, register, req } = await createFixture();
  const admin = await register("admin");
  app.im.identity.initializeCompany(admin.user.id);
  const member = await register("member");
  const outsider = await register("outsider"); // personal_space_enabled=1, membership_status='none'
  const applicant = await register("applicant");
  await req(member.access_token, "POST", "/im/v1/company/join", {});
  await req(admin.access_token, "POST", `/im/v1/company/members/${member.user.id}/approve`, {});
  const memberAuth = await app.im.identity.login("member", "password-123");

  // Applicant uploads avatar while personal_space_enabled=1, then joins & loses personal_space to become !accountEnabled pending user.
  const img = await makePng(600, 600);
  await req(applicant.access_token, "PUT", "/im/v1/me/avatar", img, { "content-type": "image/png" });
  await req(memberAuth.access_token, "PUT", "/im/v1/me/avatar", img, { "content-type": "image/png" });
  await req(applicant.access_token, "POST", "/im/v1/company/join", {});
  db.prepare("UPDATE users SET personal_space_enabled=0 WHERE id=?").run(applicant.user.id);
  const pendingAuth = await app.im.identity.login("applicant", "password-123");

  // Unauthenticated & Gateway token -> 401
  expect((await app.inject({ method: "GET", url: `/im/v1/users/${member.user.id}/avatar` })).statusCode).toBe(401);
  db.prepare("INSERT INTO nodes(node_id,owner_id,node_name,status) VALUES('n1',?,'Node','online')").run(admin.user.id);
  db.prepare("INSERT INTO node_binding_state(node_id,owner_id,node_epoch) VALUES('n1',?,1)").run(admin.user.id);
  app.im.gateway.nodes.set("n1", {
    socket: { readyState: 1, bufferedAmount: 0, send() {}, close() {} } as any,
    owner_id: admin.user.id,
    node_id: "n1",
    node_epoch: 1,
    token: "gw-secret-token",
    lastSeen: Date.now(),
  });
  expect((await req("gw-secret-token", "GET", `/im/v1/users/${member.user.id}/avatar`)).statusCode).toBe(401);

  // Pending (!accountEnabled) user reads self -> 200, reads active member -> 404; Admin reads pending user -> 200; Outsider reads member -> 404.
  expect((await req(pendingAuth.access_token, "GET", `/im/v1/users/${applicant.user.id}/avatar`)).statusCode).toBe(200);
  expect((await req(pendingAuth.access_token, "GET", `/im/v1/users/${member.user.id}/avatar`)).statusCode).toBe(404);
  expect((await req(admin.access_token, "GET", `/im/v1/users/${applicant.user.id}/avatar`)).statusCode).toBe(200);
  expect((await req(outsider.access_token, "GET", `/im/v1/users/${member.user.id}/avatar`)).statusCode).toBe(404);
  expect((await req(memberAuth.access_token, "GET", "/im/v1/users/system/avatar")).statusCode).toBe(404);

  // Shared conversation grants read even after peer is suspended.
  const chat = (await req(admin.access_token, "POST", "/im/v1/conversations", {
    title: "ArchiveGroup",
    type: "group",
    participants: [{ type: "user", id: member.user.id }],
  })).json();
  const nonAdminPeer = await register("peer2");
  await req(nonAdminPeer.access_token, "POST", "/im/v1/company/join", {});
  await req(admin.access_token, "POST", `/im/v1/company/members/${nonAdminPeer.user.id}/approve`, {});
  const peer2Auth = await app.im.identity.login("peer2", "password-123");
  await req(admin.access_token, "POST", `/im/v1/conversations/${chat.id}/participants`, {
    participants: [{ type: "user", id: nonAdminPeer.user.id }],
  });
  // Unjoined active company member browsing public ArchiveGroup can also read suspended member's avatar (no false 404 negative cache).
  const publicReader = await register("public_reader");
  await req(publicReader.access_token, "POST", "/im/v1/company/join", {});
  await req(admin.access_token, "POST", `/im/v1/company/members/${publicReader.user.id}/approve`, {});
  const publicReaderAuth = await app.im.identity.login("public_reader", "password-123");

  // Former member who only read a message (recorded in conversation_participation_history / message_receipts without sending), left the group, and got suspended remains readable to group readers.
  const receiptOnlyPeer = await register("receipt_peer");
  await req(receiptOnlyPeer.access_token, "POST", "/im/v1/company/join", {});
  await req(admin.access_token, "POST", `/im/v1/company/members/${receiptOnlyPeer.user.id}/approve`, {});
  const receiptPeerAuth = await app.im.identity.login("receipt_peer", "password-123");
  await req(receiptPeerAuth.access_token, "PUT", "/im/v1/me/avatar", img, { "content-type": "image/png" });
  const privateGroup = (await req(admin.access_token, "POST", "/im/v1/conversations", {
    title: "PrivateHistoryGroup",
    type: "group",
    visibility: "private",
    participants: [
      { type: "user", id: nonAdminPeer.user.id },
      { type: "user", id: receiptOnlyPeer.user.id },
    ],
  })).json();
  const rootMsg = (await req(peer2Auth.access_token, "POST", `/im/v1/conversations/${privateGroup.id}/messages`, {
    sender_user_id: nonAdminPeer.user.id,
    content: "Please acknowledge",
    suppress_relay: true,
  })).json();
  await req(receiptPeerAuth.access_token, "POST", `/im/v1/conversations/${privateGroup.id}/read`, {
    last_read_message_id: rootMsg.id,
  });
  await req(admin.access_token, "DELETE", `/im/v1/conversations/${privateGroup.id}/participants/${receiptOnlyPeer.user.id}`);
  await req(admin.access_token, "POST", `/im/v1/company/members/${receiptOnlyPeer.user.id}/suspend`, {});

  await req(admin.access_token, "POST", `/im/v1/company/members/${member.user.id}/suspend`, {});
  expect((await req(peer2Auth.access_token, "GET", `/im/v1/users/${member.user.id}/avatar`)).statusCode).toBe(200);
  expect((await req(publicReaderAuth.access_token, "GET", `/im/v1/users/${member.user.id}/avatar`)).statusCode).toBe(200);
  expect((await req(peer2Auth.access_token, "GET", `/im/v1/users/${receiptOnlyPeer.user.id}/avatar`)).statusCode).toBe(200);
  expect((await req(publicReaderAuth.access_token, "GET", `/im/v1/users/${receiptOnlyPeer.user.id}/avatar`)).statusCode).toBe(404);

  // Concurrent large PUT followed immediately by DELETE for the same user settles with NULL avatar and 0 files on disk.
  const heavyPng = await makePng(1200, 1200, { r: 90, g: 140, b: 210 });
  const [putRes, delRes] = await Promise.all([
    req(peer2Auth.access_token, "PUT", "/im/v1/me/avatar", heavyPng, { "content-type": "image/png" }),
    req(peer2Auth.access_token, "DELETE", "/im/v1/me/avatar"),
  ]);
  expect(putRes.statusCode).toBe(200);
  expect(delRes.statusCode).toBe(200);
  const finalMe = (await req(peer2Auth.access_token, "GET", "/im/v1/me")).json();
  if (finalMe.avatar_version === null) {
    const row = db.prepare("SELECT avatar_storage_name FROM users WHERE id=?").get(nonAdminPeer.user.id) as any;
    expect(row.avatar_storage_name).toBeNull();
  }
  const referenced = new Set(
    (db.prepare("SELECT avatar_storage_name FROM users WHERE avatar_storage_name IS NOT NULL").all() as any[]).map(r => r.avatar_storage_name),
  );
  const diskFiles = existsSync(join(dir, "user-avatars"))
    ? readdirSync(join(dir, "user-avatars")).filter(f => !f.startsWith("."))
    : [];
  expect(new Set(diskFiles)).toEqual(referenced);
});

it("isolates external shadow senders, broadcasts user.profile_updated, and keeps PA authorizationGuard invariant across avatar edits", async () => {
  const { app, db, baseUrl, register, req } = await createFixture(true);
  const admin = await register("owner");
  app.im.identity.initializeCompany(admin.user.id);
  const peer = await register("colleague");
  const outsider = await register("isolated");
  await req(peer.access_token, "POST", "/im/v1/company/join", {});
  await req(admin.access_token, "POST", `/im/v1/company/members/${peer.user.id}/approve`, {});
  const peerAuth = await app.im.identity.login("colleague", "password-123");

  // Connect WebSockets for peer (visible) and outsider (not visible).
  const openWs = async (token: string) => {
    const ticket = (await req(token, "POST", "/im/v1/auth/ws-ticket")).json().ticket;
    const wsUrl = baseUrl.replace(/^http/, "ws") + `/im/ws/user?ticket=${encodeURIComponent(ticket)}`;
    const ws = new WebSocket(wsUrl, { headers: { origin: "http://127.0.0.1:18080" } });
    cleanups.push(() => ws.close());
    const events: any[] = [];
    ws.on("message", raw => events.push(JSON.parse(String(raw))));
    await new Promise<void>((resolve, reject) => {
      ws.once("open", () => {
        ws.send(JSON.stringify({ op: "resume", after_event_id: 0 }));
        setTimeout(resolve, 40);
      });
      ws.once("error", reject);
    });
    return events;
  };
  const peerEvents = await openWs(peerAuth.access_token);
  const outsiderEvents = await openWs(outsider.access_token);

  // Set up PA binding + owner direct message quoting peer, then capture authorizationGuard BEFORE avatar changes.
  db.prepare("INSERT INTO nodes(node_id,owner_id,node_name,status) VALUES('pa-node',?,'Mac','online')").run(admin.user.id);
  db.prepare("INSERT INTO node_binding_state(node_id,owner_id,node_epoch) VALUES('pa-node',?,1)").run(admin.user.id);
  app.im.gateway.request = async (_n, method, p: any) =>
    method === "node.capabilities.resolve"
      ? { capabilities: { tools: [{ name: "send_message", default_on: true }] } }
      : { status: "applied", operation_id: p.operation_id, candidate_fingerprint: p.candidate_fingerprint, agent: { ...p.agent, workspace_root: "/pa", workspace_is_default: true } };
  const paBinding = (await req(admin.access_token, "POST", "/im/v1/personal-agent", {
    request_key: "pa-init",
    node_id: "pa-node",
    display_name: "PA",
  })).json().binding;

  const peerDirect = app.im.messaging.createConversation(admin.user, {
    title: "DM",
    type: "direct",
    participants: [{ type: "user", id: peer.user.id }],
  });
  const peerMsg = app.im.messaging.insertMessage(peerDirect.id, peer.user.id, "user", "Let us ship", [], null);
  app.im.messaging.insertMessage(paBinding.conversation_id, admin.user.id, "user", "Please follow up", [], null, "completed", {
    reply_to: { message_id: peerMsg.id, sender: peerMsg.sender, content: peerMsg.content, attachments: [] },
  });
  const bindingRow = app.im.personal!.binding(admin.user.owner_id)!;
  const paPrincipal = { node_id: "pa-node", owner_id: admin.user.id, node_epoch: 1 };
  const guardBefore = app.im.personal!.authorizationGuard(bindingRow);
  const obsBefore = JSON.stringify(app.im.personal!.observations(paPrincipal, { agent_id: bindingRow.agent_id, limit: 10 }));

  // Owner uploads avatar -> peer receives user.profile_updated, outsider does NOT, PA authorizationGuard & observations stay byte-identical!
  const png = await makePng(128, 128);
  const uploaded = (await req(admin.access_token, "PUT", "/im/v1/me/avatar", png, { "content-type": "image/png" })).json();
  await req(peerAuth.access_token, "PUT", "/im/v1/me/avatar", png, { "content-type": "image/png" });
  await new Promise(r => setTimeout(r, 50));

  expect(app.im.personal!.authorizationGuard(bindingRow)).toBe(guardBefore);
  const obsAfter = JSON.stringify(app.im.personal!.observations(paPrincipal, { agent_id: bindingRow.agent_id, limit: 10 }));
  expect(obsAfter).toBe(obsBefore);
  expect(obsAfter).not.toContain("avatar_version");
  expect(peerEvents.some(e => e.event_type === "user.profile_updated" && e.data?.user_id === admin.user.id && e.data?.avatar_version === uploaded.avatar_version)).toBe(true);
  expect(outsiderEvents.some(e => e.event_type === "user.profile_updated" && e.data?.user_id === admin.user.id)).toBe(false);

  // External mirrored shadow message under owner's account must NEVER carry owner's avatar_version.
  const shadowConvId = "c_extshadow";
  db.prepare("INSERT INTO conversations(id,title,type,owner_id,creator_id,external_source,external_chat_id,created_at,space_id) VALUES(?,'Feishu','group',?,?,'feishu','feishu:app:chat','2026-01-01','company:default')")
    .run(shadowConvId, admin.user.id, admin.user.id);
  db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES(?,?)").run(shadowConvId, admin.user.id);
  app.im.messaging.insertMessage(shadowConvId, admin.user.id, "user", "External visitor hello", [], null, "completed", {
    sender_source_id: "ou_external_visitor",
    sender_display_name: "External Visitor",
  });
  const shadowHistory = (await req(admin.access_token, "GET", `/im/v1/conversations/${shadowConvId}/messages`)).json();
  expect(shadowHistory.items[0].message.sender.avatar_id).toMatch(/^external:/);
  expect(shadowHistory.items[0].message.sender).not.toHaveProperty("avatar_version");
});
