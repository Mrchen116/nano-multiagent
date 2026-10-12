import { createHmac, randomUUID } from "node:crypto";
import type { FastifyInstance } from "fastify";
import {
  all,
  one,
  now,
  chatId,
  fail,
  body,
  params,
  query,
  transaction,
  type Row,
  type ImContext,
} from "./context.js";
export function registerConversationActions(app: FastifyInstance, ctx: ImContext) {
  const s = ctx.messaging,
    db = ctx.db;
  app.post("/im/v1/conversations/external/find-or-create", (req, reply) => {
    const p = s.principal(req),
      b = body(req);
    if (p.kind !== "gateway") fail(401, "gateway credential required");
    const a = one(
      db,
      "SELECT * FROM agent_profiles WHERE agent_id=? AND node_id=? AND owner_id=? AND is_stale=0",
      b.agent_id,
      p.node_id,
      p.owner_id,
    );
    if (!a) fail(404, "agent_id not found");
    if (!b.external_source?.trim() || !b.external_chat_id?.trim() || !b.title?.trim())
      fail(422, "external source, chat and title required");
    const user = s.agentUser(a.agent_id);
    if (b.participant_ids?.length) {
      const expected = new Set([p.owner_id, `agent:${a.agent_id}`]);
      if (
        b.participant_ids.length !== 2 ||
        b.participant_ids.some((x: string) => !expected.has(x.replace(/^user:/, "")))
      )
        fail(400, "shadow participants must match node owner and Agent");
    }
    let c = one(
      db,
      "SELECT * FROM conversations WHERE external_source=? AND external_chat_id=? AND config_agent_id=?",
      b.external_source,
      b.external_chat_id,
      a.agent_id,
    );
    if (c && c.owner_id !== p.owner_id) fail(404, "conversation not accessible");
    if (!c) {
      const id = chatId("c_");
      transaction(db, () => {
        db.prepare(
          "INSERT INTO conversations(id,title,type,owner_id,creator_id,config_agent_id,config_profile_version,external_source,external_chat_id,target_node_id,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        ).run(
          id,
          b.title,
          b.is_group ? "group" : "direct",
          p.owner_id,
          p.owner_id,
          a.agent_id,
          a.profile_version,
          b.external_source,
          b.external_chat_id,
          p.node_id,
          now(),
        );
        for (const uid of [p.owner_id, user.id])
          db.prepare(
            "INSERT INTO conversation_participants(conversation_id,user_id) VALUES(?,?)",
          ).run(id, uid);
      });
      c = one(db, "SELECT * FROM conversations WHERE id=?", id)!;
      reply.code(201);
    } else {
      if (!c.title_is_custom)
        db.prepare("UPDATE conversations SET title=? WHERE id=?").run(b.title, c.id);
      reply.code(200);
    }
    return s.conversation(c.id, p.owner_id);
  });
  app.put(
    "/im/v1/conversations/:conversation_id/external-agent-messages/:shadow_message_id",
    (req) => {
      const p = s.principal(req),
        b = body(req),
        r = params(req);
      if (p.kind !== "gateway") fail(401, "gateway credential required");
      const c = s.access(p, r.conversation_id, b.agent_id);
      if (!c.external_source || c.config_agent_id !== b.agent_id)
        fail(404, "external conversation not accessible");
      if (
        !["completed", "failed"].includes(b.delivery_status) ||
        !Number.isInteger(b.elapsed_ms) ||
        b.elapsed_ms < 0
      )
        fail(422, "terminal snapshot required");
      const key = r.shadow_message_id;
      const m = s.insertMessage(
        c.id,
        s.agentUser(b.agent_id).id,
        "agent",
        b.content ?? "",
        [],
        key,
        b.delivery_status,
      );
      db.prepare(
        "UPDATE messages SET content=?,thinking_json=?,tool_calls_json=?,token_usage_json=?,elapsed_ms=?,delivery_status=?,kernel_message_id=? WHERE id=?",
      ).run(
        b.content ?? "",
        JSON.stringify(b.thinking ?? []),
        JSON.stringify(b.tool_calls ?? []),
        b.token_usage ? JSON.stringify(b.token_usage) : null,
        b.elapsed_ms,
        b.delivery_status,
        b.kernel_message_id ?? null,
        m.id,
      );
      const result = s.message(m.id);
      s.event(c.id, m.id, "message.reconciled", { ...result, message_id: m.id }, b.delivery_status);
      return result;
    },
  );
  app.get("/im/v1/conversations/:conversation_id/commands", async (req) => {
    const p = ctx.identity.authenticateRequest(req),
      id = params(req).conversation_id;
    s.access(p, id);
    const actors = s.members(id).filter((u) => u.username.startsWith("agent:"));
    const items = await Promise.all(
      actors.map(async (actor) => {
        const agentId = actor.username.slice(6),
          a = one(db, "SELECT * FROM agent_profiles WHERE agent_id=? AND is_stale=0", agentId);
        const result: Row = {
          agent_id: agentId,
          display_name: a?.display_name ?? actor.display_name,
          status: "unavailable",
          skills: [],
          commands: [],
        };
        if (!a?.node_id || !a.workspace_root) return result;
        try {
          const response = await ctx.gateway.request(a.node_id, "agent.config.get", {
              agent_id: agentId,
            }),
            config = response.agent ?? response;
          const cap = await ctx.gateway.request(a.node_id, "agent.capabilities.resolve", {
            agent_id: agentId,
            workspace_root: a.workspace_root,
          });
          const allowed = config.skills ?? JSON.parse(a.skills_json),
            mode =
              config.skills_selection_mode ??
              a.skills_selection_mode ??
              (allowed.length ? "explicit_allowlist" : "default_discovery");
          result.skills = (cap.capabilities?.skills ?? cap.skills ?? [])
            .filter((x: Row) => mode === "default_discovery" || allowed.includes(x.name))
            .map((x: Row) => ({
              skill_key: createHmac("sha256", ctx.jwtSecret)
                .update(
                  "nano-im:conversation-skill:v1\0" +
                    JSON.stringify([
                      a.node_id,
                      x.location ? "location" : "name",
                      x.location ?? x.name,
                    ]),
                )
                .digest("hex"),
              name: x.name,
              description: x.description ?? "",
            }));
          result.commands = (cap.capabilities?.commands ?? cap.commands ?? [])
            .filter((x: Row) => typeof x.name === "string" && x.name.trim())
            .map((x: Row) => ({
              name: x.name.trim(),
              description: x.description?.trim() ?? "",
            }));
          result.status = "available";
        } catch {}
        return result;
      }),
    );
    s.access(ctx.identity.authenticateRequest(req), id);
    const current = new Set(s.members(id).map((u) => u.username));
    return { items: items.filter((x) => current.has(`agent:${x.agent_id}`)) };
  });
  app.post("/im/v1/conversations/distill-prompt", async (req, reply) => {
    const p = ctx.identity.authenticateRequest(req),
      b = body(req);
    if (
      !Array.isArray(b.sources) ||
      !b.sources.length ||
      !["agent", "global"].includes(b.target_scope)
    )
      fail(422, "invalid distill sources");
    let node: string | undefined;
    const sources = [];
    for (const source of b.sources) {
      s.access(p, source.conversation_id);
      const c = s.conversation(source.conversation_id, p.id),
        a = one(
          db,
          "SELECT * FROM agent_profiles WHERE agent_id=? AND owner_id=? AND work_mode='single_thread' AND is_stale=0",
          source.source_agent_id,
          p.owner_id,
        );
      if (c.run_state !== "idle" || c.source_agent_id !== source.source_agent_id || !a?.node_id)
        fail(409, "selected source is unavailable");
      if (node && node !== a.node_id) fail(409, "selected sources must belong to one Gateway");
      node = a.node_id;
      sources.push({
        conversation_id: c.id,
        source_agent_id: a.agent_id,
        ...(c.external_source
          ? {
              external_source: c.external_source,
              external_chat_id: c.external_chat_id,
            }
          : {}),
      });
    }
    const execution = one(
      db,
      "SELECT * FROM agent_profiles WHERE agent_id=? AND owner_id=? AND node_id=? AND work_mode='single_thread' AND is_stale=0",
      b.execution_agent_id,
      p.owner_id,
      node,
    );
    if (!execution) fail(409, "execution agent must belong to selected Gateway");
    const r = await ctx.gateway.request(node!, "node.distill.prompt.request", {
      sources,
      execution_agent_id: b.execution_agent_id,
      target_scope: b.target_scope,
    });
    if (!r.prompt?.trim()) fail(409, r.message ?? "selected Gateway cannot distill these sources");
    const fresh = ctx.identity.authenticateRequest(req);
    for (const source of sources) s.access(fresh, source.conversation_id);
    const c = s.createConversation(
      fresh,
      {
        title: `Skill distill · ${execution.display_name}`,
        type: "direct",
        participants: [{ type: "agent", id: execution.agent_id }],
      },
      true,
    );
    db.prepare("UPDATE conversations SET target_node_id=? WHERE id=?").run(node!, c.id);
    reply.code(201);
    return { conversation: s.conversation(c.id, fresh.id), prompt: r.prompt };
  });
  app.post("/im/v1/conversations/:conversation_id/fork", async (req, reply) => {
    const p = ctx.identity.authenticateRequest(req),
      id = params(req).conversation_id;
    s.access(p, id);
    const c = s.conversation(id, p.id);
    if (c.direct_kind !== "user-agent") fail(400, "fork is only available in direct agent chats");
    const agent = c.participants.find((x: Row) => x.type === "agent"),
      a = one(db, "SELECT * FROM agent_profiles WHERE agent_id=? AND is_stale=0", agent.id)!;
    const history = all(db, "SELECT * FROM messages WHERE conversation_id=? ORDER BY rowid", id),
      index = history.findIndex((m) => m.id === body(req).fork_message_id),
      anchor = history[index];
    if (
      !anchor ||
      anchor.sender_type !== "agent" ||
      anchor.delivery_status !== "completed" ||
      !anchor.kernel_message_id
    )
      fail(400, "this message does not support fork");
    if (!ctx.gateway.isOnline(a.node_id)) fail(409, "agent offline, cannot fork");
    const branch = s.createConversation(
      p,
      {
        title: a.display_name,
        type: "direct",
        participants: [{ type: "agent", id: a.agent_id }],
      },
      true,
    );
    try {
      const result = await ctx.gateway.request(a.node_id, "session.fork.request", {
        source_conversation_id: id,
        new_conversation_id: branch.id,
        agent_id: a.agent_id,
        fork_point: { message_id: anchor.kernel_message_id },
        ...(c.external_source
          ? {
              source_external_source: c.external_source,
              source_external_chat_id: c.external_chat_id,
            }
          : {}),
      });
      if (!result.ok) fail(502, result.error ?? "fork delegation failed");
      const fresh = ctx.identity.authenticateRequest(req);
      s.access(fresh, id);
      if (
        one(db, "SELECT profile_version FROM agent_profiles WHERE agent_id=?", a.agent_id)
          ?.profile_version !== a.profile_version
      )
        fail(409, "Agent configuration changed; retry fork");
      transaction(db, () => {
        const ids = new Map<string, string>(),
          base = Date.now() - index;
        for (const [i, m] of history.slice(0, index + 1).entries()) {
          const copy: Row = {
            ...m,
            id: randomUUID().replaceAll("-", ""),
            conversation_id: branch.id,
            content: s.copyReferences(id, branch.id, m.content),
            attachments_json: JSON.stringify(
              JSON.parse(m.attachments_json).map((x: Row) => ({
                ...x,
                url: s.copyReferences(id, branch.id, x.url),
              })),
            ),
            kernel_message_id: result.id_map?.[m.kernel_message_id] ?? null,
            created_at: new Date(base + i).toISOString(),
            caller_idempotency_key: null,
          };
          const keys = Object.keys(copy);
          db.prepare(
            `INSERT INTO messages(${keys.join(",")}) VALUES(${keys.map(() => "?").join(",")})`,
          ).run(...keys.map((k) => copy[k]));
          ids.set(m.id, copy.id);
        }
        for (const [source, target] of ids) {
          const m = history.find((x) => x.id === source)!;
          const process = JSON.parse(m.reply_process_json ?? "[]").map((x: Row) => ({
            ...x,
            predecessor_message_id: ids.get(x.predecessor_message_id) ?? x.predecessor_message_id,
            successor_message_id: ids.get(x.successor_message_id) ?? x.successor_message_id,
            source_messages: (x.source_messages ?? []).map((r: Row) => ({
              ...r,
              message_id: ids.get(r.message_id) ?? r.message_id,
            })),
          }));
          db.prepare("UPDATE messages SET reply_process_json=? WHERE id=?").run(
            JSON.stringify(process),
            target,
          );
        }
        for (const b of all(
          db,
          "SELECT * FROM agent_config_boundaries WHERE conversation_id=?",
          id,
        )) {
          const target = ids.get(b.before_message_id);
          if (target) {
            const boundary = randomUUID(),
              event = s.event(branch.id, target, "agent.config.changed", {
                id: boundary,
                agent_id: b.agent_id,
                before_message_id: target,
                applied_at: b.applied_at,
              });
            db.prepare("INSERT INTO agent_config_boundaries VALUES(?,?,?,?,?,?,?,?,?)").run(
              boundary,
              branch.id,
              b.agent_id,
              target,
              b.runtime_fingerprint,
              b.fingerprint_schema,
              b.profile_version,
              b.applied_at,
              event.event_id,
            );
          }
        }
        const latest = one(
          db,
          "SELECT content,created_at FROM messages WHERE conversation_id=? ORDER BY rowid DESC LIMIT 1",
          branch.id,
        );
        if (latest)
          db.prepare(
            "UPDATE conversations SET last_message_preview=?,last_message_at=? WHERE id=?",
          ).run(latest.content.slice(0, 120), latest.created_at, branch.id);
      });
      reply.code(201);
      return s.conversation(branch.id, p.id);
    } catch (e) {
      if (!one(db, "SELECT 1 FROM messages WHERE conversation_id=?", branch.id))
        db.prepare("DELETE FROM conversations WHERE id=?").run(branch.id);
      throw e;
    }
  });
  app.post("/im/v1/conversations/:conversation_id/permissions/:request_id", (req) => {
    const user = ctx.identity.authenticateRequest(req),
      r = params(req),
      b = body(req);
    s.access(user, r.conversation_id);
    const m = s.message(b.message_id);
    if (m.conversation_id !== r.conversation_id) fail(409, "message_id not found");
    const card = m.permission_requests.find((x: Row) => x.request_id === r.request_id);
    if (!card) fail(409, "request_id not found");
    const epoch =
      one(db, "SELECT node_epoch FROM node_binding_state WHERE node_id=?", card.node_id)
        ?.node_epoch ?? 0;
    if ((card.node_epoch ?? 0) !== epoch)
      fail(409, "permission execution belongs to a revoked device session");
    if (["submitted", "resolved"].includes(card.status))
      return {
        status: card.status,
        request_id: r.request_id,
        decision: card.decision,
        decided_by: card.decided_by,
      };
    const a = one(
      db,
      "SELECT a.* FROM agent_profiles a JOIN users u ON u.username='agent:'||a.agent_id JOIN conversation_participants p ON p.user_id=u.id WHERE p.conversation_id=? AND a.agent_id=? AND a.node_id=? AND a.work_mode='single_thread' AND a.is_stale=0",
      r.conversation_id,
      card.agent_id,
      card.node_id,
    );
    if (!a || card.status !== "pending") fail(409, "permission participants unavailable");
    if (!card.options?.some((x: Row) => x.id === b.decision))
      fail(409, "decision is not an option for this request");
    Object.assign(card, {
      status: "submitted",
      decision: b.decision,
      decided_by: user.id,
      reason: b.reason?.trim() ?? null,
    });
    db.prepare("UPDATE messages SET permission_request_json=? WHERE id=?").run(
      JSON.stringify(m.permission_requests),
      m.id,
    );
    s.event(
      r.conversation_id,
      m.id,
      "permission.submitted",
      {
        request_id: r.request_id,
        status: "submitted",
        decision: b.decision,
        decided_by: user.id,
      },
      "running",
    );
    ctx.gateway.send(card.node_id, {
      type: "node.streaming_delta",
      payload: {
        kind: "permission_response",
        message_id: m.id,
        request_id: r.request_id,
        decision: card.decision,
        reason: card.reason ?? "",
      },
    });
    return {
      status: "submitted",
      request_id: r.request_id,
      decision: card.decision,
      decided_by: user.id,
    };
  });
}
