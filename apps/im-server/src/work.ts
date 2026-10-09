import { randomUUID } from "node:crypto";
import type { FastifyInstance } from "fastify";
import {
  all,
  one,
  now,
  fail,
  body,
  params,
  query,
  transaction,
  type Row,
  type ImContext,
} from "./context.js";
export class Work {
  constructor(readonly ctx: ImContext) {
    for (const r of all(ctx.db, "SELECT session_id,turn_id,payload FROM agent_work_turns")) {
      const p = JSON.parse(r.payload);
      if (["running", "waiting_permission"].includes(p.status))
        ctx.db
          .prepare("UPDATE agent_work_turns SET payload=? WHERE session_id=? AND turn_id=?")
          .run(JSON.stringify({ ...p, status: "unknown" }), r.session_id, r.turn_id);
    }
  }
  get db() {
    return this.ctx.db;
  }
  session(root: string, id: string): Row {
    const r = one(
      this.db,
      "SELECT * FROM agent_work_sessions WHERE root_agent_id=? AND session_id=?",
      root,
      id,
    );
    if (!r) fail(404, "scope_not_allowed");
    return { ...JSON.parse(r.payload), ...r };
  }
  register(root: string, session: string, node: string, p: Row) {
    if (!["global_main", "subagent", "workflow", "cron"].includes(p.scope))
      fail(400, "invalid_scope");
    if (["subagent", "workflow"].includes(p.scope)) this.session(root, p.parent_session_id);
    const old = one(this.db, "SELECT * FROM agent_work_sessions WHERE session_id=?", session);
    if (
      old &&
      (old.root_agent_id !== root ||
        old.node_id !== node ||
        old.scope !== p.scope ||
        old.parent_session_id !== (p.parent_session_id ?? null))
    )
      fail(409, "session_identity_conflict");
    if (p.scope === "global_main") {
      const other = one(
        this.db,
        "SELECT session_id FROM agent_work_sessions WHERE root_agent_id=? AND scope='global_main'",
        root,
      );
      if (other && other.session_id !== session) fail(409, "main_session_conflict");
    }
    this.db
      .prepare(
        "INSERT INTO agent_work_sessions VALUES(?,?,?,?,?,?) ON CONFLICT(session_id) DO UPDATE SET payload=excluded.payload",
      )
      .run(session, root, node, p.scope, p.parent_session_id ?? null, JSON.stringify(p));
  }
  append(node: string, p: Row): Row {
    let through =
      one(
        this.db,
        "SELECT through_seq FROM agent_work_journals WHERE node_id=? AND journal_id=?",
        node,
        p.journal_id,
      )?.through_seq ?? 0;
    if (p.from_seq > through + 1)
      return {
        journal_id: p.journal_id,
        through_seq: through,
        expected_seq: through + 1,
      };
    if (!Array.isArray(p.events) || !p.events.length || p.events.length > 100)
      fail(400, "invalid_arguments");
    transaction(this.db, () => {
      for (const [i, e] of p.events.entries()) {
        if (
          e.seq !== p.from_seq + i ||
          !e.event_id ||
          !e.session_id ||
          !e.payload ||
          typeof e.payload !== "object"
        )
          fail(400, "invalid_sequence");
        const profile = one(
          this.db,
          "SELECT * FROM agent_profiles WHERE agent_id=? AND node_id=? AND work_mode='global' AND is_stale=0",
          e.root_agent_id,
          node,
        );
        if (!profile) fail(403, "scope_not_allowed");
        const old = one(
          this.db,
          "SELECT * FROM agent_work_events WHERE node_id=? AND journal_id=? AND seq=?",
          node,
          p.journal_id,
          e.seq,
        );
        if (old) {
          if (
            old.event_id !== e.event_id ||
            old.root_agent_id !== e.root_agent_id ||
            old.session_id !== e.session_id ||
            old.payload !== JSON.stringify(e.payload)
          )
            fail(409, "event_identity_conflict");
          continue;
        }
        if (e.seq !== through + 1) fail(400, "invalid_sequence");
        if (e.type === "session_registered")
          this.register(e.root_agent_id, e.session_id, node, e.payload);
        else this.session(e.root_agent_id, e.session_id);
        if (e.type === "session_linked") {
          if (e.payload.parent_session_id !== e.session_id) fail(403, "scope_not_allowed");
          this.register(e.root_agent_id, e.payload.child_session_id, node, {
            ...e.payload,
            scope: e.payload.workflow_run_id ? "workflow" : "subagent",
            parent_session_id: e.session_id,
          });
        }
        const result = this.db
          .prepare(
            "INSERT INTO agent_work_events(node_id,journal_id,seq,event_id,root_agent_id,session_id,turn_id,type,observed_at,payload) VALUES(?,?,?,?,?,?,?,?,?,?)",
          )
          .run(
            node,
            p.journal_id,
            e.seq,
            e.event_id,
            e.root_agent_id,
            e.session_id,
            e.turn_id ?? null,
            e.type,
            e.observed_at ?? now(),
            JSON.stringify(e.payload),
          );
        this.project(e, Number(result.lastInsertRowid));
        through = e.seq;
      }
      this.db
        .prepare(
          "INSERT INTO agent_work_journals VALUES(?,?,?) ON CONFLICT(node_id,journal_id) DO UPDATE SET through_seq=excluded.through_seq",
        )
        .run(node, p.journal_id, through);
    });
    for (const root of new Set<string>(p.events.map((e: Row) => e.root_agent_id))) {
      const users = all(
        this.db,
        "SELECT id FROM users WHERE membership_status='active' AND password_hash IS NOT NULL",
      ).map((u) => u.id);
      this.ctx.gateway.broadcast(users, {
        op: "event",
        event_type: "agent.work.updated",
        data: { agent_id: root, revision: this.revision(root) },
      });
    }
    return { journal_id: p.journal_id, through_seq: through };
  }
  project(e: Row, revision: number) {
    const p = e.payload,
      kind = e.type,
      session = e.session_id;
    let turnId = e.turn_id;
    if (!turnId && p.run_id && !["cron_trigger", "cron_delivery"].includes(kind))
      turnId = one(
        this.db,
        "SELECT turn_id FROM agent_work_turns WHERE session_id=? AND json_extract(payload,'$.run_id')=? ORDER BY seq DESC LIMIT 1",
        session,
        p.run_id,
      )?.turn_id;
    if (!turnId) {
      if (
        [
          "control_result",
          "recording_degraded",
          "model_fallback",
          "cron_trigger",
          "cron_delivery",
        ].includes(kind)
      )
        this.db
          .prepare("INSERT INTO agent_work_items VALUES(?,?,?,?,?,?,?,?)")
          .run(
            session,
            "",
            e.event_id,
            revision,
            kind,
            e.observed_at ?? null,
            JSON.stringify(p),
            revision,
          );
      return;
    }
    const prior = one(
      this.db,
      "SELECT * FROM agent_work_turns WHERE session_id=? AND turn_id=?",
      session,
      turnId,
    );
    const turn = prior
      ? JSON.parse(prior.payload)
      : {
          session_id: session,
          turn_id: turnId,
          status: "unknown",
          usage: null,
          source_refs: [],
        };
    if (kind === "inbox_wake_admitted")
      turn.trigger = { kind: "inbox", submission_id: p.submission_id };
    if (["turn_started", "turn_start"].includes(kind))
      Object.assign(turn, {
        status: "running",
        origin: p.origin,
        trigger: p.trigger,
        model_id: p.model_id ?? p.model,
        run_id: p.run_id,
        started_at: p.started_at ?? e.observed_at,
      });
    if (["turn_end", "run_completed", "run_failed", "run_cancelled"].includes(kind)) {
      Object.assign(turn, {
        status:
          p.status ??
          (["cancelled", "aborted", "interrupted"].includes(p.stop_reason) ||
          kind === "run_cancelled"
            ? "interrupted"
            : p.completed === false || p.error || kind === "run_failed"
              ? "failed"
              : "completed"),
        finished_at: p.finished_at ?? e.observed_at,
        elapsed_ms: p.elapsed_ms ?? p.duration_ms,
        model_id: p.model ?? turn.model_id,
      });
      if (p.usage)
        turn.usage = {
          ...p.usage,
          context_used: p.usage.context_used ?? p.usage.prompt_tokens,
          output: p.usage.output ?? p.usage.completion_tokens,
          context_window: p.context_window ?? p.usage.context_window,
        };
    }
    if (kind === "permission_request") turn.status = "waiting_permission";
    if (kind === "permission_resolved" && turn.status === "waiting_permission") {
      turn.status = one(
        this.db,
        "SELECT 1 FROM agent_work_items WHERE session_id=? AND turn_id=? AND kind='permission' AND item_id!=? AND json_extract(payload,'$.status')='pending'",
        session,
        turnId,
        `permission:${p.request_id}`,
      )
        ? "waiting_permission"
        : "running";
    }
    if (p.source_refs) turn.source_refs = p.source_refs;
    this.db
      .prepare(
        "INSERT INTO agent_work_turns VALUES(?,?,?,?) ON CONFLICT(session_id,turn_id) DO UPDATE SET payload=excluded.payload",
      )
      .run(session, turnId, prior?.seq ?? revision, JSON.stringify(turn));
    if (
      [
        "turn_started",
        "turn_start",
        "turn_end",
        "tool_result_committed",
        "turn_input_committed",
        "run_heartbeat",
        "inbox_wake_admitted",
      ].includes(kind)
    )
      return;
    const call = p.call_id ?? p.tool_call_id;
    const itemKind =
      [
        "tool_start",
        "tool_end",
        "draft_withheld",
        "message_sent",
        "dispatch_confirmed",
        "inbox_read_committed",
      ].includes(kind) && call
        ? "tool"
        : ["permission_request", "permission_resolved"].includes(kind)
          ? "permission"
          : kind;
    const id =
      itemKind === "tool"
        ? `tool:${call}`
        : itemKind === "permission"
          ? `permission:${p.request_id}`
          : ["message", "message_delta", "text_delta"].includes(kind) && p.message_id
            ? `message:${p.message_id}`
            : e.event_id;
    const old = one(
      this.db,
      "SELECT * FROM agent_work_items WHERE session_id=? AND turn_id=? AND item_id=?",
      session,
      turnId,
      id,
    );
    const payload = old ? JSON.parse(old.payload) : {};
    if (itemKind === "tool") {
      if (["tool_start", "tool_end"].includes(kind)) {
        Object.assign(payload, p, {
          input: p.arguments ?? payload.input ?? {},
          reason: p.reason_code,
          id: call,
          status:
            kind === "tool_start" ? "running" : p.error || p.is_error ? "failed" : "completed",
          output: p.presentation?.summary ?? payload.output,
          name: p.name ?? p.tool_name ?? payload.name ?? "tool",
        });
        for (const key of ["label", "summary", "detail", "emoji"])
          if (p.presentation?.[key] !== undefined) payload[key] = p.presentation[key];
      } else (payload.work_facts ??= []).push({ type: kind, ...p });
    } else if (itemKind === "permission") {
      Object.assign(payload, p.permission_request ?? p, {
        node_epoch:
          one(
            this.db,
            "SELECT b.node_epoch FROM node_binding_state b JOIN agent_work_sessions s ON s.node_id=b.node_id WHERE s.session_id=?",
            session,
          )?.node_epoch ?? 0,
        status: kind === "permission_resolved" ? "resolved" : "pending",
      });
    } else if (["message_delta", "text_delta"].includes(kind))
      payload.text = (payload.text ?? "") + (p.text ?? p.delta ?? "");
    else Object.assign(payload, p);
    payload.seq = old?.seq ?? revision;
    this.db
      .prepare(
        "INSERT INTO agent_work_items VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(session_id,turn_id,item_id) DO UPDATE SET payload=excluded.payload,revision=excluded.revision",
      )
      .run(
        session,
        turnId,
        id,
        payload.seq,
        itemKind,
        e.observed_at ?? null,
        JSON.stringify(payload),
        revision,
      );
  }
  items(root: string, session: string, turn: string, after = 0, limit = 100): Row {
    this.session(root, session);
    const rows = all(
      this.db,
      "SELECT * FROM agent_work_items WHERE session_id=? AND turn_id=? AND seq>? ORDER BY seq LIMIT ?",
      session,
      turn,
      after,
      limit + 1,
    );
    return {
      items: rows.slice(0, limit).map((r) => ({
        item_id: r.item_id,
        seq: r.seq,
        kind: r.kind,
        observed_at: r.observed_at,
        revision: r.revision,
        payload: JSON.parse(r.payload),
      })),
      next_cursor: rows.length > limit ? String(rows[limit - 1]!.seq) : null,
    };
  }
  turns(root: string, session: string, before?: string, limit = 20): Row {
    const registered = this.session(root, session);
    const anchor = before
      ? one(
          this.db,
          "SELECT seq FROM agent_work_turns WHERE session_id=? AND turn_id=?",
          session,
          before,
        )?.seq
      : Number.MAX_SAFE_INTEGER;
    if (anchor === undefined) fail(400, "invalid_cursor");
    const rows = all(
      this.db,
      "SELECT * FROM agent_work_turns WHERE session_id=? AND seq<? ORDER BY seq DESC LIMIT ?",
      session,
      anchor,
      limit + 1,
    );
    return {
      turns: rows.slice(0, limit).map((r) => {
        const page = this.items(root, session, r.turn_id);
        return {
          ...JSON.parse(r.payload),
          scope: registered.scope,
          items: page.items,
          next_items_cursor: page.next_cursor,
        };
      }),
      control_items: this.items(root, session, "").items,
      next_cursor: rows.length > limit ? rows[limit - 1]!.turn_id : null,
    };
  }
  revision(root: string) {
    return one(
      this.db,
      "SELECT COALESCE(MAX(revision),0) n FROM agent_work_events WHERE root_agent_id=?",
      root,
    )!.n;
  }
  view(root: string, before?: string, limit = 20): Row {
    const sessions = all(this.db, "SELECT * FROM agent_work_sessions WHERE root_agent_id=?", root),
      main = sessions.find((s) => s.scope === "global_main")?.session_id ?? null;
    const page = main ? this.turns(root, main, before, limit) : { turns: [], next_cursor: null };
    let latest = null;
    for (const r of main
      ? all(
          this.db,
          "SELECT payload FROM agent_work_turns WHERE session_id=? ORDER BY seq DESC",
          main,
        )
      : []) {
      const t = JSON.parse(r.payload);
      if (t.usage) {
        latest = {
          session_id: main,
          turn_id: t.turn_id,
          model_id: t.model_id,
          ...t.usage,
        };
        break;
      }
    }
    const agent = one(this.db, "SELECT node_id FROM agent_profiles WHERE agent_id=?", root)!;
    const online = this.ctx.gateway.isOnline(agent.node_id);
    let state = page.turns[0]?.status ?? "idle";
    if (["completed", "failed", "interrupted"].includes(state)) state = "idle";
    if (!online && ["running", "waiting_permission"].includes(state)) state = "unknown";
    return {
      root_agent_id: root,
      main_session_id: main,
      revision: this.revision(root),
      latest_main_usage: latest,
      main_execution: state,
      node_connection_state: online ? "online" : "offline",
      control_items: main ? this.items(root, main, "").items : [],
      other_executions: sessions
        .filter((s) => s.scope !== "global_main")
        .map((s) => {
          const x = { ...JSON.parse(s.payload), ...s };
          delete x.payload;
          return x;
        }),
      ...page,
    };
  }
  query(c: Row, p: Row): Row {
    const agent = one(
        this.db,
        "SELECT * FROM agent_profiles WHERE agent_id=? AND node_id=? AND is_stale=0",
        p.agent_id,
        c.node_id,
      ),
      session = this.session(p.agent_id, p.session_id);
    if (!agent || session.node_id !== c.node_id || session.scope !== "global_main")
      fail(403, "scope_not_allowed");
    const limit = p.limit ?? 20;
    if (
      !Number.isInteger(limit) ||
      limit < 1 ||
      limit > 50 ||
      !["list", "read", "info", "describe"].includes(p.action)
    )
      fail(400, "invalid_arguments");
    const s = this.ctx.messaging,
      uid = s.agentUser(p.agent_id).id,
      conversations = s.conversations(uid);
    const members = (id: string) =>
      s.members(id).map((u) => ({
        id: u.id,
        name: u.display_name,
        kind: u.username.startsWith("agent:") ? "agent" : "user",
        ...(u.username.startsWith("agent:") ? { agent_id: u.username.slice(6) } : {}),
      }));
    if (p.action === "describe")
      return {
        conversations: conversations
          .filter((r) => (p.targets ?? []).includes(r.id))
          .map((r) => ({
            target: r.id,
            name: r.title,
            kind: r.type,
            channel: r.external_source ?? "web",
            participants: members(r.id),
          })),
      };
    const target = conversations.find((r) => r.id === p.target);
    if (p.action === "info") {
      if (!target) fail(404, "target_not_accessible");
      return {
        target: p.target,
        name: target.title,
        type: target.type,
        channel: target.external_source ?? "web",
        members: members(p.target).map((m) => ({
          user_id: m.id,
          name: m.name,
          type: m.kind,
          mention: `<mention type="user" target_id="${m.id}"/>`,
        })),
      };
    }
    const identity = {
      agent: p.agent_id,
      action: p.action,
      target: p.target ?? null,
      query: p.query ?? null,
    };
    let cursor: Row | undefined, snapshot: Row | undefined;
    if (p.cursor) {
      try {
        cursor = JSON.parse(Buffer.from(p.cursor, "base64url").toString());
        const r = one(
          this.db,
          "SELECT data FROM agent_work_query_snapshots WHERE snapshot_id=?",
          cursor!.snapshot,
        );
        if (!r) throw Error();
        snapshot = JSON.parse(r.data);
        if (
          !Number.isInteger(cursor!.offset) ||
          cursor!.offset < 0 ||
          !Number.isInteger(cursor!.part) ||
          cursor!.part < 0 ||
          Object.keys(identity).some((k) => snapshot![k] !== identity[k as keyof typeof identity])
        )
          throw Error();
      } catch {
        fail(400, "invalid_cursor");
      }
    }
    const next = (ids: string[], offset: number, part = 0) => {
      const id = cursor?.snapshot ?? randomUUID();
      if (!cursor)
        this.db
          .prepare("INSERT INTO agent_work_query_snapshots VALUES(?,?)")
          .run(id, JSON.stringify({ ...identity, ids }));
      return Buffer.from(JSON.stringify({ snapshot: id, offset, part })).toString("base64url");
    };
    if (p.action === "list") {
      const filtered = conversations.filter(
        (r) =>
          !p.query ||
          r.title.toLowerCase().includes(p.query.toLowerCase()) ||
          members(r.id).some((m) => m.name.toLowerCase().includes(p.query.toLowerCase())),
      );
      const ids: string[] = snapshot?.ids ?? filtered.map((r) => r.id),
        byId = new Map(filtered.map((r) => [r.id, r]));
      let offset = cursor?.offset ?? 0;
      const page = [];
      while (offset < ids.length && page.length < limit) {
        const r = byId.get(ids[offset++]!);
        if (r)
          page.push({
            target: r.id,
            name: r.title,
            kind: r.type,
            channel: r.external_source ?? "web",
            participants: members(r.id),
            latest_message_at: r.last_message_at,
            history_availability: "im_history",
          });
      }
      return {
        conversations: page,
        has_more: offset < ids.length,
        next_cursor: offset < ids.length ? next(ids, offset) : null,
      };
    }
    if (!target) fail(404, "target_not_accessible");
    if (p.before_message_id && cursor) fail(400, "invalid_arguments");
    let messages = all(
      this.db,
      "SELECT id FROM messages WHERE conversation_id=? AND sender_type IN ('user','agent') ORDER BY rowid",
      p.target,
    )
      .map((r) => s.message(r.id))
      .filter((m) => m.content || m.attachments.length);
    if (p.before_message_id) {
      const i = messages.findIndex((m) => m.id === p.before_message_id);
      if (i < 0) fail(404, "target_not_accessible");
      messages = messages.slice(0, i);
    }
    const ids: string[] = snapshot?.ids ?? messages.map((m) => m.id).reverse(),
      byId = new Map(messages.map((m) => [m.id, m]));
    let offset = cursor?.offset ?? 0,
      part = cursor?.part ?? 0,
      budget = 24000,
      images = 0;
    const page = [];
    while (offset < ids.length && page.length < limit) {
      const m = byId.get(ids[offset]!);
      if (!m) {
        offset++;
        part = 0;
        continue;
      }
      const parts: Row[] = [];
      for (let i = 0; i < m.content.length; i += 24000)
        parts.push({ type: "text", text: m.content.slice(i, i + 24000) });
      parts.push(
        ...m.attachments.map((a: Row) => ({
          type: a.content_type?.startsWith("image/") ? "image" : "attachment",
          ...a,
        })),
      );
      while (part < parts.length && page.length < limit) {
        const content = parts[part]!,
          cost = content.text?.length ?? 0;
        if (cost > budget || (content.type === "image" && images >= 4)) break;
        budget -= cost;
        if (content.type === "image") images++;
        page.push({
          message_id: m.id,
          sender: {
            id: m.sender_user_id,
            name: m.sender.display_name,
            kind: target.external_source && m.sender_type === "user" ? "external" : m.sender_type,
            ...(target.external_source && m.sender_type === "user"
              ? {
                  channel: target.external_source,
                  ...(m.sender_source_id ? { source_id: m.sender_source_id } : {}),
                }
              : {}),
          },
          source_time: m.created_at,
          source: {
            channel: target.external_source ?? "web",
            conversation_id: p.target,
            reply_target: p.target,
          },
          part_key: String(part),
          content: [content],
          complete_message: parts.length === 1,
        });
        part++;
      }
      if (part < parts.length) break;
      offset++;
      part = 0;
    }
    return {
      target: p.target,
      name: target.title,
      kind: target.type,
      channel: target.external_source ?? "web",
      messages: page,
      history_scope: "im_history",
      has_more: offset < ids.length,
      next_cursor: offset < ids.length ? next(ids, offset, part) : null,
    };
  }
}
export function registerWorkRoutes(app: FastifyInstance, ctx: ImContext) {
  const db = ctx.db,
    w = ctx.gateway.work;
  function profile(req: any, owner = false) {
    const user = ctx.identity.authenticateRequest(req),
      id = params(req).agent_id;
    const p = one(
      db,
      "SELECT * FROM agent_profiles WHERE agent_id=? AND is_stale=0 AND work_mode='global'",
      id,
    );
    if (!p || (owner && p.owner_id !== user.owner_id)) fail(404, "agent_not_accessible");
    return p;
  }
  app.get("/im/v1/agents/:agent_id/work", (req) => {
    const p = profile(req),
      q = query(req);
    return w.view(p.agent_id, q.before_turn, Math.min(50, Math.max(1, Number(q.limit ?? 20))));
  });
  app.get("/im/v1/agents/:agent_id/work/sessions/:session_id/turns", (req) => {
    profile(req);
    const p = params(req),
      q = query(req);
    return w.turns(
      p.agent_id,
      p.session_id,
      q.before_turn,
      Math.min(50, Math.max(1, Number(q.limit ?? 20))),
    );
  });
  app.get("/im/v1/agents/:agent_id/work/sessions/:session_id/turns/:turn_id/items", (req) => {
    profile(req);
    const p = params(req),
      q = query(req);
    return w.items(
      p.agent_id,
      p.session_id,
      p.turn_id,
      Number(q.after_seq ?? 0),
      Math.min(200, Math.max(1, Number(q.limit ?? 100))),
    );
  });
  app.post("/im/v1/agents/:agent_id/work/permissions/:request_id", async (req) => {
    const a = profile(req, true),
      id = params(req).request_id,
      b = body(req);
    const item = all(
      db,
      "SELECT i.*,s.node_id FROM agent_work_items i JOIN agent_work_sessions s USING(session_id) WHERE s.root_agent_id=? AND i.item_id=?",
      a.agent_id,
      `permission:${id}`,
    ).find((r) => {
      const p = JSON.parse(r.payload),
        t = one(
          db,
          "SELECT payload FROM agent_work_turns WHERE session_id=? AND turn_id=?",
          r.session_id,
          r.turn_id,
        );
      return (
        p.status === "pending" &&
        p.node_epoch ===
          (one(db, "SELECT node_epoch FROM node_binding_state WHERE node_id=?", r.node_id)
            ?.node_epoch ?? 0) &&
        t &&
        ["running", "waiting_permission", "unknown"].includes(JSON.parse(t.payload).status)
      );
    });
    if (!item) fail(409, "request_ended");
    if (!JSON.parse(item.payload).options?.some((o: Row) => o.id === b.decision))
      fail(409, "invalid_decision");
    const result = await ctx.gateway.request(a.node_id, "agent.work.permission", {
      request_id: id,
      root_agent_id: a.agent_id,
      session_id: item.session_id,
      decision: b.decision,
      reason: b.reason ?? "",
    });
    if (!result.ok) fail(409, result.error ?? "request_ended");
    return { ok: true, request_id: id };
  });
  app.get("/im/v1/metrics/usage", (req) => {
    const p = ctx.identity.authenticateRequest(req),
      q = query(req),
      clauses = ["owner_id=?"],
      args = [p.owner_id];
    for (const key of ["conversation_id", "agent_id"])
      if (q[key]) {
        clauses.push(`${key}=?`);
        args.push(q[key]);
      }
    return all(
      db,
      `SELECT owner_id,conversation_id,agent_id,SUM(turns) turns,SUM(prompt_tokens) prompt_tokens,SUM(completion_tokens) completion_tokens,SUM(total_tokens) total_tokens,MAX(created_at) last_used_at FROM usage_metrics WHERE ${clauses.join(" AND ")} GROUP BY owner_id,conversation_id,agent_id ORDER BY last_used_at DESC`,
      ...args,
    ).map((r) => ({
      ...r,
      scope: r.agent_id ? "agent" : r.conversation_id ? "conversation" : "owner",
      scope_id: r.agent_id ?? r.conversation_id ?? r.owner_id,
    }));
  });
}
