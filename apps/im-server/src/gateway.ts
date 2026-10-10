import { withHumanApproval } from "./messaging.js";
import { randomBytes, randomUUID } from "node:crypto";
import type { FastifyInstance } from "fastify";
import type WebSocket from "ws";
import { all, one, now, fail, transaction, type Row, type ImContext } from "./context.js";
import { TaskGraphService, TaskGraphError } from "./task-graphs.js";
import { Work } from "./work.js";
import {canonicalAgentConfiguration} from "@nano/product-contracts";
type Connection = {
  socket: WebSocket;
  owner_id: string;
  node_id: string;
  node_epoch: number;
  token: string;
  lastSeen: number;
};
type Browser = {
  socket: WebSocket;
  userId: string;
  sessionId: string;
  ready: boolean;
  cursor: number;
};
export class Gateway {
  readonly nodes = new Map<string, Connection>();
  readonly browsers = new Set<Browser>();
  readonly pending = new Map<
    string,
    {
      connection: Connection | undefined;
      responseType: string;
      resolve: (value: Row) => void;
      reject: (err: Error) => void;
      timer: NodeJS.Timeout;
    }
  >();
  readonly work: Work;
  readonly tasks: TaskGraphService;
  channelHandler?: (type: string, payload: Row) => Row | Promise<Row>;
  channelInitialize?: (nodeId: string) => void;
  constructor(readonly ctx: ImContext) {
    this.work = new Work(ctx);
    this.tasks = new TaskGraphService(ctx.db);
  }
  isOnline(id: string) {
    return this.nodes.has(id);
  }
  authenticate(token: string): Row | null {
    for (const c of this.nodes.values())
      if (c.token === token && this.valid(c))
        return {
          owner_id: c.owner_id,
          node_id: c.node_id,
          node_epoch: c.node_epoch,
        };
    return null;
  }
  valid(c: Connection) {
    const r = one(
      this.ctx.db,
      "SELECT b.owner_id,b.node_epoch,u.membership_status FROM node_binding_state b JOIN users u ON u.id=b.owner_id WHERE b.node_id=?",
      c.node_id,
    );
    return (
      !!r &&
      r.owner_id === c.owner_id &&
      r.node_epoch === c.node_epoch &&
      r.membership_status === "active"
    );
  }
  write(socket: WebSocket, frame: Row) {
    if (socket.readyState !== 1) return false;
    if (socket.bufferedAmount > 4 * 1024 * 1024) {
      socket.close(1013, "outbound backlog");
      return false;
    }
    socket.send(JSON.stringify(frame));
    return true;
  }
  send(nodeId: string, frame: Row): boolean {
    const c = this.nodes.get(nodeId);
    return !!c && this.valid(c) && this.write(c.socket, frame);
  }
  request(nodeId: string, type: string, payload: Row): Promise<Row> {
    const requestId = payload.request_id ?? randomUUID();
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(requestId);
        reject(
          Object.assign(new Error("node response timeout"), {
            statusCode: 504,
          }),
        );
      }, 10000);
      const responseTypes: Record<string, string> = {
        "agent.config.get": "agent.config",
        "agent.create": "agent.created",
        "agent.capabilities.resolve": "agent.capabilities",
        "node.capabilities.resolve": "node.capabilities",
      };
      const responseType =
        responseTypes[type] ??
        (type.endsWith(".request")
          ? type === "session.fork.request"
            ? "session.fork.result"
            : type.slice(0, -8)
          : `${type}.result`);
      this.pending.set(requestId, {
        connection: this.nodes.get(nodeId),
        responseType,
        resolve,
        reject,
        timer,
      });
      if (
        !this.send(nodeId, {
          type,
          payload: { ...payload, request_id: requestId },
        })
      ) {
        clearTimeout(timer);
        this.pending.delete(requestId);
        reject(Object.assign(new Error("node offline"), { statusCode: 503 }));
      }
    });
  }
  closeUser(id: string) {
    for (const b of this.browsers) if (b.userId === id) b.socket.close(1008);
  }
  closeSession(id: string) {
    for (const b of this.browsers) if (b.sessionId === id) b.socket.close(1008);
  }
  revokeNode(id: string) {
    this.nodes.get(id)?.socket.close(1008);
    this.nodes.delete(id);
  }
  revokeOwner(id: string) {
    for (const c of this.nodes.values()) if (c.owner_id === id) this.revokeNode(c.node_id);
    this.closeUser(id);
  }
  broadcast(ids: string[], frame: Row) {
    for (const b of this.browsers) {
      if (!b.ready || !ids.includes(b.userId)) continue;
      if (frame.event_id && frame.event_id <= b.cursor) continue;
      if (!this.browserValid(b)) {
        b.socket.close(1008);
        continue;
      }
      if (
        frame.conversation_id &&
        !one(
          this.ctx.db,
          "SELECT 1 FROM conversation_participants WHERE conversation_id=? AND user_id=?",
          frame.conversation_id,
          b.userId,
        )
      )
        continue;
      this.write(b.socket, frame);
      b.cursor = Math.max(b.cursor, frame.event_id ?? 0);
    }
  }
  browserValid(b: Browser) {
    return !!one(
      this.ctx.db,
      "SELECT 1 FROM auth_sessions s JOIN users u ON u.id=s.user_id WHERE s.session_id=? AND s.revoked=0 AND s.epoch=u.auth_epoch AND s.expires_at>? AND u.membership_status='active'",
      b.sessionId,
      Math.floor(Date.now() / 1000),
    );
  }
  replay(b: Browser, cursor: number) {
    const db = this.ctx.db;
    const top = one(db, "SELECT COALESCE(MAX(event_id),0) n FROM conversation_events")!.n;
    const earliest = one(
      db,
      "SELECT MIN(event_id) n FROM conversation_events WHERE created_at>=?",
      new Date(Date.now() - 15 * 60000).toISOString(),
    )?.n;
    if (top - cursor > 2000 || (cursor > 0 && earliest && cursor < earliest - 1)) {
      this.write(b.socket, {
        op: "resync_required",
        reason: top - cursor > 2000 ? "gap_too_large" : "replay_window_expired",
      });
    } else
      for (const e of all(
        db,
        "SELECT e.* FROM conversation_events e JOIN conversation_participants p ON p.conversation_id=e.conversation_id WHERE p.user_id=? AND e.event_id>? AND e.event_id<=? ORDER BY e.event_id",
        b.userId,
        cursor,
        top,
      )) {
        const data = JSON.parse(e.payload_json);
        this.write(b.socket, {
          op: "event",
          event_type: e.event_type,
          event_id: e.event_id,
          conversation_id: e.conversation_id,
          data: {
            ...data,
            event_id: e.event_id,
            conversation_id: e.conversation_id,
            message_id: e.message_id ?? data.message_id,
            delivery_status: e.delivery_status,
            created_at: e.event_type === "message.reconciled" ? data.created_at : e.created_at,
          },
        });
      }
    b.cursor = top;
    b.ready = true;
  }
  register(c: Connection, p: Row): Row {
    const db = this.ctx.db;
    if (p.node_id !== c.node_id || !this.valid(c)) fail(403, "node identity mismatch");
    if (!Array.isArray(p.agents) || p.agents.some((x: unknown) => typeof x !== "string"))
      fail(400, "agents must be strings");
    for (const agent of p.agents) {
      const prior = one(db, "SELECT owner_id,node_id FROM agent_profiles WHERE agent_id=?", agent);
      if (prior && (prior.owner_id !== c.owner_id || prior.node_id !== c.node_id))
        fail(403, "agent identity conflict");
      const existing = one(db, "SELECT work_mode FROM agent_profiles WHERE agent_id=?", agent);
      if (
        p.agent_work_modes?.[agent] &&
        (!["single_thread", "global"].includes(p.agent_work_modes[agent]) ||
          (existing && existing.work_mode !== p.agent_work_modes[agent]))
      )
        fail(400, "work_mode is immutable");
    }
    if (p.credential_key_id || p.credential_public_key) {
      const enrolled = one(db, "SELECT * FROM node_credential_keys WHERE node_id=?", c.node_id);
      if (
        !enrolled ||
        enrolled.key_id !== p.credential_key_id ||
        enrolled.public_key !== p.credential_public_key
      )
        fail(403, "device_key_not_enrolled");
    }
    const old = this.nodes.get(c.node_id);
    if (old && old.socket !== c.socket) old.socket.close(1008, "connection replaced");
    this.nodes.set(c.node_id, c);
    db.prepare(
      `INSERT INTO nodes(node_id,owner_id,node_name,status,last_heartbeat_at,agent_count,version) VALUES(?,?,?,'online',?,?,?) ON CONFLICT(node_id) DO UPDATE SET owner_id=excluded.owner_id,node_name=excluded.node_name,status='online',last_heartbeat_at=excluded.last_heartbeat_at,agent_count=excluded.agent_count,version=excluded.version`,
    ).run(c.node_id, c.owner_id, p.node_name ?? c.node_id, now(), p.agents.length, p.version ?? "");
    db.prepare("UPDATE agent_profiles SET is_stale=1,staled_at=? WHERE node_id=?").run(
      now(),
      c.node_id,
    );
    for (const id of p.agents) {
      const existed = one(db, "SELECT 1 FROM agent_profiles WHERE agent_id=?", id);
      db.prepare(
        `INSERT INTO agent_profiles(agent_id,owner_id,node_id,display_name,workspace_root,work_mode,skills_json,skills_selection_mode,tool_allowlist_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(agent_id) DO UPDATE SET is_stale=0,staled_at=NULL,workspace_root=COALESCE(excluded.workspace_root,workspace_root),updated_at=excluded.updated_at`,
      ).run(
        id,
        c.owner_id,
        c.node_id,
        id,
        p.agent_workspaces?.[id] ?? null,
        p.agent_work_modes?.[id] ?? "single_thread",
        JSON.stringify(p.agent_skills?.[id] ?? []),
        p.agent_skills_selection_modes?.[id] ?? null,
        JSON.stringify(p.agent_tool_allowlist?.[id] ?? []),
        now(),
        now(),
      );
      // Only a first registration seeds local configuration. Reconnect must not
      // replace an existing IM desired revision or a pending configuration operation.
      if (!existed && p.agent_configurations?.[id]) {
        const seed=canonicalAgentConfiguration({...p.agent_configurations[id],agent_id:id,workspace_root:p.agent_workspaces?.[id],work_mode:p.agent_work_modes?.[id]??'single_thread'});
        db.prepare('UPDATE agent_profiles SET display_name=?,group_reply_policy=?,default_model=?,reasoning_effort=?,custom_prompt=?,heartbeat_json=?,features_json=?,skills_json=?,skills_selection_mode=?,tool_allowlist_json=?,model_fallbacks_json=? WHERE agent_id=?').run(seed.display_name,seed.group_reply_policy,seed.default_model,seed.reasoning_effort,seed.custom_prompt,seed.heartbeat_json,JSON.stringify(seed.features),JSON.stringify(seed.skills),seed.skills_selection_mode,JSON.stringify(seed.tool_allowlist),JSON.stringify(seed.model_fallbacks),id);
      }
      const advertised = p.agent_create_operations?.[id];
      const operation = advertised
        ? one(
            db,
            "SELECT * FROM agent_config_operations WHERE operation_id=? AND node_id=? AND agent_id=? AND operation_kind='create'",
            advertised,
            c.node_id,
            id,
          )
        : null;
      if (operation) {
        db.prepare(
          "UPDATE agent_profiles SET registration_seed=1,pending_create_operation_id=?,workspace_is_default=? WHERE agent_id=?",
        ).run(
          advertised,
          p.agent_workspace_is_default?.[id] === undefined
            ? null
            : Number(p.agent_workspace_is_default[id]),
          id,
        );
      }
      this.ctx.messaging.agentUser(id);
    }
    this.broadcast([c.owner_id], {
      op: "event",
      event_type: "node.status_changed",
      data: { node_id: c.node_id, status: "online", last_heartbeat_at: now() },
    });
    return {
      message_type: "node.register",
      im_user_url: this.ctx.publicUrl,
      node_id: c.node_id,
      node_epoch: c.node_epoch,
      gateway_access_token: c.token,
    };
  }
  async handle(c: Connection, type: string, p: Row): Promise<Row> {
    const db = this.ctx.db,
      s = this.ctx.messaging;
    const ack = (extra: Row = {}) => ({
      type: "ack",
      payload: { message_type: type, ...extra },
    });
    if (type === "node.register") {
      const result = this.register(c, p);
      return ack(result);
    }
    if (this.nodes.get(c.node_id) !== c || !this.valid(c) || p.node_id !== c.node_id)
      fail(403, "node_not_registered");
    c.lastSeen = Date.now();
    const waiter = p.request_id ? this.pending.get(p.request_id) : undefined;
    if (waiter && waiter.connection === c && waiter.responseType === type) {
      clearTimeout(waiter.timer);
      this.pending.delete(p.request_id);
      waiter.resolve(p);
      return ack({ request_id: p.request_id });
    }
    if (type === "node.heartbeat") {
      db.prepare(
        "UPDATE nodes SET status=?,last_heartbeat_at=?,last_error=?,agent_count=COALESCE(?,agent_count) WHERE node_id=?",
      ).run(p.status ?? "online", now(), p.last_error ?? null, p.agent_count ?? null, c.node_id);
      return ack({ node_id: c.node_id });
    }
    if (type === "agent.work.append")
      return {
        type: "agent.work.ack",
        payload: this.work.append(c.node_id, p),
      };
    if (type === "task_graph.command") {
      try {
        if (!p.request_id)
          throw new TaskGraphError(
            "invalid_arguments",
            "request_id required",
          );
        return {
          type: "task_graph.result",
          payload: {
            request_id: p.request_id,
            ok: true,
            result: this.tasks.execute(
              {
                kind: "agent",
                id: p.agent_id,
                node_id: c.node_id,
                source_message_id: p.source_message_id,
              },
              p.action,
              p.args ?? {},
            ),
          },
        };
      } catch (e) {
        return {
          type: "task_graph.result",
          payload: {
            request_id: p.request_id,
            ok: false,
            error:
              e instanceof TaskGraphError
                ? e.asDict()
                : {
                    code: "source_unavailable",
                    message: "Task storage is temporarily unavailable",
                  },
          },
        };
      }
    }
    if (type === "conversation.query") {
      try {
        return {
          type: "conversation.query.result",
          payload: {
            request_id: p.request_id,
            ok: true,
            result: this.work.query(c, p),
          },
        };
      } catch (e) {
        return {
          type: "conversation.query.result",
          payload: {
            request_id: p.request_id,
            ok: false,
            error: (e as Error).message,
          },
        };
      }
    }
    if (type.startsWith("channel.") || type === "channels.bootstrap") {
      if (!this.channelHandler) fail(400, "channel control unavailable");
      return this.channelHandler(type, p);
    }
    if (type === "node.delivery_receipt") {
      const relay = one(
        db,
        "SELECT * FROM relay_tasks WHERE relay_task_id=? AND target_node_id=?",
        p.relay_task_id,
        c.node_id,
      );
      if (!relay) fail(404, "relay task not found");
      db.prepare(
        "UPDATE relay_tasks SET status=?,receipt_status=?,receipt_detail=?,updated_at=? WHERE relay_task_id=?",
      ).run(p.delivery_status, p.delivery_status, p.detail ?? null, now(), p.relay_task_id);
      db.prepare("UPDATE messages SET delivery_status=? WHERE id=?").run(
        p.delivery_status === "failed" ? "failed" : "completed",
        relay.message_id,
      );
      s.event(
        relay.conversation_id,
        relay.message_id,
        "relay.delivery_receipt",
        p,
        p.delivery_status,
      );
      return ack({ relay_task_id: p.relay_task_id });
    }
    if (type === "node.streaming_delta") return ack(this.streaming(c, p));
    if (type === "agent.message") {
      const source = String(p.from_session_id ?? "")
        .replace(/^agent:/, "")
        .split("|tool_call:");
      const a = this.requireAgent(c, source[0]!);
      if (
        typeof p.text !== "string" ||
        (!p.text.trim() && !p.background_returns?.length) ||
        typeof p.to !== "string"
      )
        fail(400, "invalid_agent_message");
      const key = source[1] ? `${a.agent_id}:${source[1]}` : null;
      const previous = key
        ? one(db, "SELECT * FROM agent_message_dispatch_log WHERE dispatch_request_key=?", key)
        : undefined;
      if (previous)
        return ack({
          conversation_id: previous.conversation_id,
          message_id: previous.message_id,
          target_kind: previous.target_kind,
          target_id: previous.target_id,
          source_agent_id: a.agent_id,
        });
      const id = s.resolveTarget(a.agent_id, p.to);
      s.access({ ...c, kind: "gateway" }, id, a.agent_id);
      const rawTarget = p.to.replace(/^(?:conversation|agent|user):/, "");
      const targetUser = one(
        db,
        "SELECT * FROM users WHERE id=? OR username=?",
        rawTarget,
        `agent:${rawTarget}`,
      );
      const targetKind =
        p.to.startsWith("conversation:") || rawTarget === id
          ? "conversation_id"
          : targetUser?.username.startsWith("agent:")
            ? "agent_id"
            : "user_id";
      const targetId = targetKind === "agent_id" ? targetUser!.username.slice(6) : rawTarget;
      const m = s.insertMessage(
        id,
        s.agentUser(a.agent_id).id,
        "agent",
        p.text.trim(),
        p.attachments ?? [],
        key,
      );
      if (p.background_returns)
        db.prepare("UPDATE messages SET background_returns_json=? WHERE id=?").run(
          JSON.stringify(p.background_returns),
          m.id,
        );
      if (key)
        db.prepare("INSERT INTO agent_message_dispatch_log VALUES(?,?,?,?,?,?,?)").run(
          key,
          a.agent_id,
          targetKind,
          targetId,
          id,
          m.id,
          now(),
        );
      s.event(
        id,
        m.id,
        "message.completed",
        { content: m.content, token_usage: null },
        "completed",
      );
      if (targetKind === "agent_id") {
        const target = one(db, "SELECT * FROM agent_profiles WHERE agent_id=?", targetId);
        if (target) this.relayMessage(m, target, `agent-dm:${m.id}:${targetId}`);
      }
      this.groupReply(m.id);
      return ack({
        conversation_id: id,
        message_id: m.id,
        target_kind: targetKind,
        target_id: targetId,
        source_agent_id: a.agent_id,
      });
    }
    if (type === "node.system_message") {
      const source =
        p.system_notice?.source_agent_id ??
        p.agent_id ??
        s
          .members(p.conversation_id)
          .find(
            (u) =>
              u.username.startsWith("agent:") &&
              one(
                db,
                "SELECT 1 FROM agent_profiles WHERE agent_id=? AND node_id=?",
                u.username.slice(6),
                c.node_id,
              ),
          )
          ?.username.slice(6);
      const a = this.requireAgent(c, source);
      s.access({ ...c, kind: "gateway" }, p.conversation_id, a.agent_id);
      if (!p.text?.trim()) fail(400, "text required");
      if (p.system_notice) {
        if (
          p.system_notice.kind !== "self_evolution_review" ||
          !Array.isArray(p.system_notice.updated_targets) ||
          p.system_notice.updated_targets.some((x: string) => !["skills", "memory"].includes(x))
        )
          fail(400, "invalid system notice");
      }
      let system = one(db, "SELECT * FROM users WHERE username='system'");
      if (!system) {
        const uid = randomUUID();
        db.prepare(
          "INSERT INTO users(id,username,display_name,owner_id,created_at) VALUES(?,?,?,?,?)",
        ).run(uid, "system", "System", uid, now());
        system = one(db, "SELECT * FROM users WHERE id=?", uid);
      }
      const m = s.insertMessage(
        p.conversation_id,
        system!.id,
        "system",
        p.text,
        [],
        p.idempotency_key ?? null,
      );
      if (p.system_notice) {
        db.prepare("UPDATE messages SET system_notice_json=? WHERE id=?").run(
          JSON.stringify({
            ...p.system_notice,
            source_agent_display_name: a.display_name,
          }),
          m.id,
        );
        s.event(m.conversation_id, m.id, "message.reconciled", s.message(m.id));
      }
      return ack({ message_id: m.id });
    }

    if (type === "agent.config.boundary") {
      const a = this.requireAgent(c, p.agent_id);
      s.access({ ...c, kind: "gateway" }, p.conversation_id, a.agent_id);
      const m = s.message(p.before_message_id);
      if (m.conversation_id !== p.conversation_id) fail(400, "anchor not found");
      let b = one(
        db,
        "SELECT * FROM agent_config_boundaries WHERE conversation_id=? AND before_message_id=? AND runtime_fingerprint=?",
        p.conversation_id,
        p.before_message_id,
        p.runtime_fingerprint,
      );
      if (!b) {
        const id = randomUUID();
        const e = s.event(p.conversation_id, p.before_message_id, "agent.config.changed", {
          id,
          agent_id: p.agent_id,
          before_message_id: p.before_message_id,
          applied_at: p.applied_at ?? now(),
        });
        db.prepare("INSERT INTO agent_config_boundaries VALUES(?,?,?,?,?,?,?,?,?)").run(
          id,
          p.conversation_id,
          p.agent_id,
          p.before_message_id,
          p.runtime_fingerprint,
          p.fingerprint_schema,
          p.profile_version ?? null,
          p.applied_at ?? now(),
          e.event_id,
        );
        b = { boundary_id: id };
      }
      return ack({ request_id: p.request_id, boundary_id: b.boundary_id });
    }
    if (type === "node.report") {
      this.requireAgent(c, p.agent_id);
      const conversation = p.conversation_id ?? (p.message_id ? s.message(p.message_id).conversation_id : undefined);
      if (conversation) s.access({ ...c, kind: "gateway" }, conversation, p.agent_id);
      if (p.usage) {
        if (!p.run_id) fail(400, "run_id_required");
        transaction(db, () => {
          const inserted = db.prepare("INSERT OR IGNORE INTO usage_receipts VALUES(?,?)").run(c.node_id, p.run_id);
          if (!inserted.changes) return;
          const scopes = [[null, null], ...(conversation ? [[conversation, null]] : []), [conversation ?? null, p.agent_id]];
          for (const [conversationId, agentId] of scopes) db.prepare(
            "INSERT INTO usage_metrics(owner_id,conversation_id,agent_id,prompt_tokens,completion_tokens,total_tokens,turns,created_at) VALUES(?,?,?,?,?,?,?,?)",
          ).run(c.owner_id, conversationId, agentId, p.usage.prompt_tokens ?? 0, p.usage.completion_tokens ?? 0,
            p.usage.total_tokens ?? 0, 1, p.completed_at ?? now());
        });
      }
      return ack({ run_id: p.run_id });
    }
    fail(400, "unsupported_message_type");
  }
  requireAgent(c: Connection, id: string): Row {
    const a = one(
      this.ctx.db,
      "SELECT * FROM agent_profiles WHERE agent_id=? AND node_id=? AND owner_id=? AND is_stale=0",
      id,
      c.node_id,
      c.owner_id,
    );
    if (!a) fail(403, "agent_not_accessible");
    return a;
  }
  streaming(c: Connection, p: Row): Row {
    const db = this.ctx.db,
      s = this.ctx.messaging;
    if (p.kind === "turn_start") {
      const a = this.requireAgent(c, p.agent_id);
      if (p.agent_user_id && p.agent_user_id !== s.agentUser(a.agent_id).id)
        fail(403, "agent_user_id does not match source Agent");
      const id = p.conversation_id ?? s.resolveTarget(a.agent_id, p.to_user_id);
      s.access({ ...c, kind: "gateway" }, id, a.agent_id);
      const transition = p.reply_process_transition;
      if (transition?.predecessor_message_id) {
        const predecessor = s.message(transition.predecessor_message_id);
        if (predecessor.conversation_id !== id || predecessor.sender.id !== a.agent_id)
          fail(403, "reply process predecessor must belong to source Agent");
      }
      const m = s.insertMessage(
        id,
        s.agentUser(a.agent_id).id,
        "agent",
        "",
        [],
        p.shadow_message_id ?? p.idempotency_key ?? null,
        "running",
      );
      if (p.background_returns)
        db.prepare("UPDATE messages SET background_returns_json=? WHERE id=?").run(
          JSON.stringify(p.background_returns),
          m.id,
        );
      if (p.reply_process_transition) {
        const t = p.reply_process_transition;
        if (t.predecessor_message_id) {
          if (t.include_handoff)
            this.streaming(c, {
              kind: "reply_process",
              message_id: t.predecessor_message_id,
              item: {
                item_id: `handoff:${t.run_id}:${m.id}`,
                kind: "segment_handoff",
                run_id: t.run_id,
                successor_message_id: m.id,
              },
            });
        }
        this.streaming(c, {
          kind: "reply_process",
          message_id: m.id,
          item: {
            item_id: `revalidation:${t.run_id}:${m.id}`,
            kind: "revalidation",
            run_id: t.run_id,
            source_messages: t.source_messages ?? [],
            predecessor_message_id: t.predecessor_message_id ?? null,
            status: "running",
          },
        });
      }
      return {
        kind: p.kind,
        run_id: p.run_id,
        message_id: m.id,
        conversation_id: id,
      };
    }
    if (p.kind === "run_terminal_reconcile") return { kind: p.kind, run_id: p.run_id };
    const m = s.message(p.message_id);
    if (m.sender_type !== "agent") fail(403, "streaming message must belong to an Agent");
    this.requireAgent(c, m.sender.id);
    s.access({ ...c, kind: "gateway" }, m.conversation_id, m.sender.id);
    let eventType = "",
      data: Row = {};
    if (p.kind === "message_delta") {
      if (p.idempotency_key) {
        const added = db
          .prepare("INSERT OR IGNORE INTO message_delta_idempotency VALUES(?,?)")
          .run(m.id, p.idempotency_key);
        if (!added.changes) return { message_id: m.id };
      }
      if (m.delivery_status !== "running") return { message_id: m.id };
      db.prepare("UPDATE messages SET content=content||? WHERE id=?").run(p.delta_text ?? "", m.id);
      eventType = "message.delta";
      data = {
        delta: p.delta_text ?? "",
        delta_text: p.delta_text ?? "",
        idempotency_key: p.idempotency_key,
      };
    } else if (p.kind === "message_completed") {
      if (!["completed", "failed", undefined].includes(p.delivery_status))
        fail(400, "invalid delivery status");
      db.prepare(
        "UPDATE messages SET content=?,delivery_status=?,token_usage_json=?,elapsed_ms=?,kernel_message_id=?,awaiting_permission_at=NULL WHERE id=?",
      ).run(
        p.final_content ?? m.content,
        p.delivery_status ?? "completed",
        p.token_usage ? JSON.stringify(p.token_usage) : null,
        p.elapsed_ms ?? null,
        p.kernel_message_id ?? null,
        m.id,
      );
      eventType = "message.completed";
      data = { ...s.message(m.id), content: p.final_content ?? m.content };
    } else if (p.kind === "message_discarded") {
      db.prepare("DELETE FROM messages WHERE id=?").run(m.id);
      s.event(m.conversation_id, null, "message.discarded", {
        message_id: m.id,
        reason: p.reason,
      });
      return { message_id: m.id };
    } else if (p.kind === "thinking_segment") {
      const items = m.thinking;
      const item = { seq: p.process_seq ?? items.length, text: p.text ?? "" };
      if (!items.some((x: Row) => x.seq === item.seq)) items.push(item);
      db.prepare("UPDATE messages SET thinking_json=? WHERE id=?").run(JSON.stringify(items), m.id);
      eventType = "thinking.segment";
      data = { segment: item, ...item };
    } else if (["tool_call_upserted", "tool_call_completed"].includes(p.kind)) {
      const items = m.tool_calls,
        item = withHumanApproval({
          ...p.tool_call,
          ...(p.process_seq !== undefined ? { seq: p.process_seq } : {}),
        }, m.permission_requests);
      const i = items.findIndex((x: Row) => x.id === item.id);
      if (i < 0) items.push(item);
      else { item.seq = items[i].seq ?? item.seq; items[i] = { ...items[i], ...item }; }
      db.prepare("UPDATE messages SET tool_calls_json=? WHERE id=?").run(
        JSON.stringify(items),
        m.id,
      );
      eventType = p.kind === "tool_call_completed" ? "tool_call.completed" : "tool_call.upserted";
      data = { tool_call: item };
    } else if (p.kind === "permission_request" || p.kind === "permission_resolved") {
      const items = m.permission_requests,
        item = p.permission_request ?? p;
      const id = item.request_id ?? p.request_id;
      let entry = items.find((x: Row) => x.request_id === id);
      if (!entry) {
        entry = { ...item, request_id: id };
        items.push(entry);
      }
      if (p.kind === "permission_request") {
        if (!p.run_id || !id) fail(400, "run_id and request_id required");
        if (["submitted", "resolved"].includes(entry.status)) return { message_id: m.id };
        const agent = this.requireAgent(c, m.sender.id);
        if (agent.work_mode !== "single_thread")
          fail(400, "global Agent does not expose chat permission cards");
        Object.assign(entry, {
          status: "pending",
          conversation_id: m.conversation_id,
          message_id: m.id,
          agent_id: agent.agent_id,
          node_id: c.node_id,
          node_epoch: c.node_epoch,
          run_id: p.run_id,
        });
      } else Object.assign(entry, { status: "resolved", decision: p.decision });
      db.prepare(
        "UPDATE messages SET permission_request_json=?,awaiting_permission_at=? WHERE id=?",
      ).run(JSON.stringify(items), p.kind === "permission_request" ? now() : null, m.id);
      eventType = p.kind === "permission_request" ? "permission.request" : "permission.resolved";
      data = { ...entry, permission_request: entry };
    } else if (p.kind === "reply_process") {
      const items = m.reply_process;
      const index = items.findIndex((x: Row) => x.item_id === p.item.item_id);
      if (index < 0) items.push(p.item);
      else items[index] = p.item;
      db.prepare("UPDATE messages SET reply_process_json=? WHERE id=?").run(
        JSON.stringify(items),
        m.id,
      );
      eventType = "reply_process.upserted";
      data = { item: p.item };
    } else if (p.kind === "run_heartbeat") {
      eventType = "run.heartbeat";
      data = { source: p.source };
      if (m.awaiting_permission_at)
        db.prepare("UPDATE messages SET awaiting_permission_at=? WHERE id=?").run(now(), m.id);
    } else fail(400, "unsupported streaming kind");
    s.event(
      m.conversation_id,
      m.id,
      eventType,
      data,
      p.delivery_status ?? (p.kind === "message_completed" ? "completed" : m.delivery_status),
    );
    if (p.kind === "message_completed") this.groupReply(m.id);
    return { kind: p.kind, run_id: p.run_id, message_id: m.id };
  }
  relayMessage(m: Row, a: Row, key: string, extra: Row = {}) {
    const db = this.ctx.db,
      s = this.ctx.messaging;
    if (one(db, "SELECT 1 FROM relay_tasks WHERE idempotency_key=?", key)) return;
    const c = s.conversation(m.conversation_id, m.sender_user_id);
    const relay = randomUUID(),
      payload = {
        relay_task_id: relay,
        idempotency_key: key,
        conversation_id: c.id,
        agent_id: a.agent_id,
        message: m,
        sender: m.sender,
        participants: c.participants,
        metadata: {
          conversation_type: c.type,
          participant_agent_ids: c.participants
            .filter((p: Row) => p.type === "agent")
            .map((p: Row) => p.id),
          mentioned_agent_ids: s.mentionedAgents(m.conversation_id, m.content),
          node_epoch:
            one(db, "SELECT node_epoch FROM node_binding_state WHERE node_id=?", a.node_id)
              ?.node_epoch ?? 0,
          ...extra,
        },
      };
    db.prepare("INSERT INTO relay_tasks VALUES(?,?,?,?,?,?,?,?,?,?,?)").run(
      relay,
      m.id,
      c.id,
      a.node_id,
      JSON.stringify(payload),
      key,
      "queued",
      null,
      null,
      now(),
      now(),
    );
    if (this.send(a.node_id, { type: "relay.message", payload }))
      db.prepare("UPDATE relay_tasks SET status='sent' WHERE relay_task_id=?").run(relay);
  }
  groupReply(messageId: string) {
    const s = this.ctx.messaging,
      m = s.message(messageId),
      c = one(this.ctx.db, "SELECT * FROM conversations WHERE id=?", m.conversation_id);
    if (
      c?.type !== "group" ||
      m.sender_type !== "agent" ||
      m.delivery_status !== "completed" ||
      !m.content.trim() ||
      m.content.trim() === "NO_REPLY"
    )
      return;
    for (const u of s.members(c.id)) {
      if (!u.username.startsWith("agent:") || u.id === m.sender_user_id) continue;
      const a = one(
        this.ctx.db,
        "SELECT * FROM agent_profiles WHERE agent_id=? AND is_stale=0",
        u.username.slice(6),
      );
      if (a)
        this.relayMessage(m, a, `agent-reply:${m.id}:${a.agent_id}`, {
          source_agent_id: m.sender.id,
          sender_display_name: m.sender.display_name,
        });
    }
  }
  shutdown() {
    for (const c of this.nodes.values()) c.socket.close(1001);
    for (const b of this.browsers) b.socket.close(1001);
    for (const p of this.pending.values()) {
      clearTimeout(p.timer);
      p.reject(new Error("server stopped"));
    }
    this.pending.clear();
  }
}
export function registerSockets(app: FastifyInstance, ctx: ImContext) {
  const g = ctx.gateway;
  app.get("/im/ws/gateway", { websocket: true }, (socket, req) => {
    const token = (req.headers.authorization ?? "").replace(/^Bearer\s+/i, "");
    const identity = ctx.identity.authenticateRuntime(token);
    if (!identity) {
      socket.close(1008);
      return;
    }
    const c: Connection = {
      ...identity,
      socket,
      token: randomBytes(32).toString("base64url"),
      lastSeen: Date.now(),
    };
    let processing = Promise.resolve();
    let queued = 0,
      windowAt = Date.now(),
      framesInWindow = 0;
    socket.on("message", (raw) => {
      if (Date.now() - windowAt >= 60000) {
        windowAt = Date.now();
        framesInWindow = 0;
      }
      if (++framesInWindow > 3000) {
        socket.close(1013);
        return;
      }
      const bytes = Array.isArray(raw) ? raw.reduce((n, b) => n + b.byteLength, 0) : raw.byteLength;
      if (bytes > 2 * 1024 * 1024 || queued + bytes > 4 * 1024 * 1024) {
        socket.close(1009);
        return;
      }
      queued += bytes;
      processing = processing.then(async () => {
        let frame: Row = {};
        try {
          frame = JSON.parse(raw.toString());
          const result = await g.handle(c, frame.type, frame.payload ?? {});
          g.write(socket, result);
          if (frame.type === "node.register" && result.type === "ack") {
            g.channelInitialize?.(c.node_id);
            for (const row of all(
              ctx.db,
              "SELECT id,permission_request_json FROM messages WHERE permission_request_json LIKE '%submitted%'",
            )) {
              for (const permission of JSON.parse(row.permission_request_json)) {
                if (
                  permission.status === "submitted" &&
                  permission.node_id === c.node_id &&
                  permission.node_epoch === c.node_epoch
                )
                  g.send(c.node_id, {
                    type: "node.streaming_delta",
                    payload: {
                      kind: "permission_response",
                      message_id: row.id,
                      request_id: permission.request_id,
                      decision: permission.decision,
                      reason: permission.reason ?? "",
                    },
                  });
              }
            }
            for (const task of all(
              ctx.db,
              "SELECT * FROM relay_tasks WHERE target_node_id=? AND status IN ('queued','sent','accepted')",
              c.node_id,
            ))
              g.send(c.node_id, {
                type: "relay.message",
                payload: {
                  ...JSON.parse(task.payload_json),
                  relay_task_id: task.relay_task_id,
                },
              });
          }
        } catch (e) {
          g.write(socket, {
            type: "error",
            payload: {
              code: (e as Error).message,
              message_type: frame.type,
              request_id: frame.payload?.request_id,
              journal_id: frame.payload?.journal_id,
            },
          });
          if ((e as any).statusCode === 403) socket.close(1008);
        } finally {
          queued -= bytes;
        }
      });
    });
    socket.on("close", () => {
      if (g.nodes.get(c.node_id) === c) {
        g.nodes.delete(c.node_id);
        ctx.db.prepare("UPDATE nodes SET status='offline' WHERE node_id=?").run(c.node_id);
        g.broadcast([c.owner_id], {
          op: "event",
          event_type: "node.status_changed",
          data: { node_id: c.node_id, status: "offline" },
        });
      }
    });
  });
  app.get("/im/ws/user", { websocket: true }, (socket, req) => {
    const origin = req.headers.origin;
    if (
      ![
        new URL(ctx.publicUrl).origin,
        ...(process.env.IM_BROWSER_ORIGINS ?? "").split(",").map((s) => s.trim()),
      ].includes(origin ?? "")
    ) {
      socket.close(1008);
      return;
    }
    try {
      ctx.identity.rateLimit(`ws:source:${req.ip}`, 30, 60);
    } catch {
      socket.close(1013);
      return;
    }
    const session = ctx.identity.consumeTicket((req.query as Row).ticket ?? "");
    if (!session) {
      socket.close(1008);
      return;
    }
    if ([...g.browsers].filter((b) => b.userId === session.user_id).length >= 5) {
      socket.close(1013);
      return;
    }
    let windowAt = Date.now(),
      framesInWindow = 0;
    const b: Browser = {
      socket,
      userId: session.user_id,
      sessionId: session.session_id,
      ready: false,
      cursor: 0,
    };
    g.browsers.add(b);
    const timer = setTimeout(() => {
      if (g.browserValid(b)) g.replay(b, 0);
      else socket.close(1008);
    }, 30000);
    socket.on("message", (raw) => {
      if (Date.now() - windowAt >= 60000) {
        windowAt = Date.now();
        framesInWindow = 0;
      }
      if (++framesInWindow > 120) {
        socket.close(1013);
        return;
      }
      if (
        (Array.isArray(raw) ? raw.reduce((n, b) => n + b.byteLength, 0) : raw.byteLength) > 65536
      ) {
        socket.close(1009);
        return;
      }
      if (!g.browserValid(b)) {
        socket.close(1008);
        return;
      }
      try {
        const p = JSON.parse(raw.toString());
        if (p.op === "resume") {
          clearTimeout(timer);
          g.replay(
            b,
            Number.isSafeInteger(p.after_event_id) && p.after_event_id >= 0 ? p.after_event_id : 0,
          );
        } else if (p.op === "ping") g.write(socket, { op: "pong" });
      } catch {
        socket.close(1003);
      }
    });
    socket.on("close", () => {
      clearTimeout(timer);
      g.browsers.delete(b);
    });
  });
}
