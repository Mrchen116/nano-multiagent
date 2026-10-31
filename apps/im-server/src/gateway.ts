import { sortedJsonAscii } from '@nano/product-contracts/serialization';
import { NodeRpc } from './node-rpc.js';
import { catalogReads } from './catalog-reads.js';
import { isRecord } from './node-rpc-values.js';
import { AgentLifecycles, lifecycle, lifecycleAllows, requireLifecycle } from './agent-lifecycle.js';
import { conversationAccess } from './conversation-access.js';
import { accountEnabled, defaultSpace, canAccessSpace, canActorAccess, ownerAccount, agentAvailable } from "./identity.js";
import { ChatStreaming } from './chat-streaming.js';
import type { ChatStreamReceipt } from '@nano/product-contracts';
import { randomBytes, randomUUID } from "node:crypto";
import type { FastifyInstance } from "fastify";
import type WebSocket from "ws";
import { all, one, now, fail, transaction, type Row, type ImContext } from "./context.js";
import { TaskGraphService, TaskGraphError } from "./task-graphs.js";
import { Work } from "./work.js";
import {canonicalAgentConfiguration, interactiveResponse, decodeAgentPublication, type AgentPublication} from "@nano/product-contracts";
import { TrajectoryObservers } from './trajectory.js';
export type Connection = {
  socket: WebSocket;
  owner_id: string;
  node_id: string;
  node_epoch: number;
  token: string;
  lastSeen: number;
  agent_lifecycle_v1?: boolean;
};
type Browser = {
  socket: WebSocket;
  userId: string;
  sessionId: string;
  ready: boolean;
  cursor: number;
};
export class Gateway {
  private readonly chat: ChatStreaming<Connection>;
  readonly nodes = new Map<string, Connection>();
  readonly browsers = new Set<Browser>();
  private readonly rpc = new NodeRpc<Connection>({
    current: nodeId => this.nodes.get(nodeId),
    send: (nodeId, frame) => this.send(nodeId, frame),
    updating: nodeId => !!this.ctx.updates?.gate(nodeId),
  });
  readonly request = this.rpc.request;
  readonly work: Work;
  readonly trajectory: TrajectoryObservers;
  readonly tasks: TaskGraphService;
  channelHandler?: (type: string, payload: Row) => Row | Promise<Row>;
  channelInitialize?: (nodeId: string) => void;
  constructor(readonly ctx: ImContext) {
    this.chat=new ChatStreaming(ctx.db,ctx.messaging?.records,{
      requireAgent:(connection,id)=>{const agent=this.requireAgent(connection,id);return {agent_id:agent.agent_id,work_mode:agent.work_mode};},
      requirePersonalConversation:(agentId,cid)=>{const binding=one(ctx.db,'SELECT * FROM personal_agent_bindings WHERE agent_id=?',agentId);if(binding&&!ctx.personal!.ownerConversation(binding,cid))fail(403,'personal_reviewed_delivery_required');},
      agentUserId:id=>ctx.messaging.agentUser(id).id,resolveTarget:(id,target)=>ctx.messaging.resolveTarget(id,target),
      access:(connection,cid,id)=>{ctx.messaging.access({...connection,kind:'gateway'},cid,id,'write');},groupReply:id=>this.groupReply(id),
    });
    this.work = new Work(ctx);
    this.trajectory = new TrajectoryObservers(ctx);
    this.tasks = new TaskGraphService(ctx.db,ctx.messaging,undefined,{
      runtime:async agentId=>{
        const agent=one(ctx.db,'SELECT node_id FROM agent_profiles WHERE agent_id=? AND is_stale=0',agentId);
        const connection=agent&&this.nodes.get(agent.node_id);
        if(!connection||!this.valid(connection))return {state:'offline'};
        const result=await this.request(agent.node_id,'task.execution.state',{agent_id:agentId});
        return {state:result.state==='running'||result.state==='idle'?result.state:'unknown'};
      },
      inspect:async input=>{
        const agent=one(ctx.db,'SELECT node_id FROM agent_profiles WHERE agent_id=? AND is_stale=0',input.agent_id);
        if(!agent)throw new Error('Task owner is unavailable');
        const proof=await this.request(agent.node_id,'task.wait.validate',input);
        if(proof.error)throw new Error(proof.error);
        if (typeof proof.valid !== 'boolean' || typeof proof.checked_at !== 'string') throw new Error('Invalid task wait inspection');
        return {...proof, valid:proof.valid, checked_at:proof.checked_at};
      },
      changed:change=>{
        for(const row of all(ctx.db,'SELECT agent_id,node_id FROM agent_profiles WHERE is_stale=0')) if(change.agent_ids.includes(row.agent_id))
          this.send(row.node_id,{type:'task.execution.changed',payload:{...change,agent_id:row.agent_id}});
      },
    });
    for(const state of all(ctx.db,"SELECT * FROM agent_lifecycle WHERE desired='disabled'"))this.tasks.freezeAgent(state.agent_id,state.actor_user_id,state.revision,false);
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
      "SELECT b.owner_id,b.node_epoch,u.membership_status,u.personal_space_enabled FROM node_binding_state b JOIN users u ON u.id=b.owner_id WHERE b.node_id=?",
      c.node_id,
    );
    return (
      !!r &&
      r.owner_id === c.owner_id &&
      r.node_epoch === c.node_epoch &&
      accountEnabled(r)
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
    if(frame.type==='agent.work.permission'&&!lifecycleAllows(this.ctx.db,frame.payload.root_agent_id,frame.payload.lifecycle_revision))return false;
    if (frame.type === "relay.message") {
      if (this.ctx.updates?.gate(nodeId)) return false;
      const p = frame.payload;
      const profile = one(this.ctx.db, "SELECT * FROM agent_profiles WHERE agent_id=? AND node_id=?", p.agent_id, nodeId);
      const conversation = one(this.ctx.db, "SELECT * FROM conversations WHERE id=?", p.conversation_id);
      if(!profile||!lifecycleAllows(this.ctx.db,profile.agent_id,p.lifecycle_revision))return false;
      if (!agentAvailable(this.ctx.db, profile) || !conversation || !canActorAccess(this.ctx.db,this.ctx.messaging.agentUser(profile!.agent_id).id,conversation.space_id)) return false;
    }
    if (frame.type === "node.streaming_delta" && frame.payload?.kind === "permission_response") {
      const message = one(this.ctx.db, "SELECT m.conversation_id,u.username FROM messages m JOIN users u ON u.id=m.sender_user_id WHERE m.id=?", frame.payload.message_id);
      const profile = message?.username?.startsWith("agent:") ? one(this.ctx.db, "SELECT * FROM agent_profiles WHERE agent_id=? AND node_id=?", message.username.slice(6), nodeId) : undefined;
      const conversation = message ? one(this.ctx.db, "SELECT space_id FROM conversations WHERE id=?", message.conversation_id) : undefined;
      if (!agentAvailable(this.ctx.db, profile) || !conversation || profile!.space_id !== conversation.space_id || !lifecycleAllows(this.ctx.db,profile!.agent_id,frame.payload.lifecycle_revision)) return false;
    }
    return !!c && this.valid(c) && this.write(c.socket, frame);
  }
  closeUser(id: string) {
    this.trajectory.closeUser(id);
    for (const b of this.browsers) if (b.userId === id) b.socket.close(1008);
  }
  closeSession(id: string) {
    this.trajectory.closeSession(id);
    for (const b of this.browsers) if (b.sessionId === id) b.socket.close(1008);
  }
  /** Persist loss of the current connection before closing its transport.
   *
   * Args:
   *   connection: Socket owner; a replaced connection cannot take its successor offline.
   *   reason: Local diagnostic category, never remote payload text.
   */
  disconnect(connection: Connection, reason = "connection_closed") {
    this.rpc.disconnect(connection);
    this.trajectory.closeDevice(connection);
    if (this.nodes.get(connection.node_id) !== connection) return;
    this.nodes.delete(connection.node_id);
    this.ctx.messaging.delivery.disconnect(connection.node_id);
    this.ctx.db.prepare("UPDATE nodes SET status='offline',last_error=? WHERE node_id=?")
      .run(reason, connection.node_id);
    this.publishNodeStatus(connection, "offline", { last_error: reason });
  }
  private publishNodeStatus(connection: Connection, status: string, extra: Row = {}) {
    this.broadcast([connection.owner_id], {
      op: "event", event_type: "node.status_changed",
      data: { node_id: connection.node_id, status, ...extra },
    });
    // Agent detail has its own cache consumer; node events alone leave its badge stale.
    for (const agent of all(this.ctx.db,
      "SELECT agent_id FROM agent_profiles WHERE node_id=? AND owner_id=? AND is_stale=0",
      connection.node_id, connection.owner_id)) {
      this.broadcast([connection.owner_id], {
        op: "event", event_type: "agent.status_changed",
        data: { agent_id: agent.agent_id, node_id: connection.node_id, status },
      });
    }
  }
  revokeNode(id: string) {
    const connection = this.nodes.get(id);
    if (!connection) return;
    this.disconnect(connection, "authority_revoked");
    connection.socket.close(1008, "authority_revoked");
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
      const conversationId = frame.conversation_id ?? frame.data?.conversation_id;
      if (conversationId) {
        const conversation = one(this.ctx.db, "SELECT space_id FROM conversations WHERE id=?", conversationId);
        // Membership removal/deletion notifications contain no protected content.
        if (conversation && !canActorAccess(this.ctx.db, b.userId, conversation.space_id)) continue;
      }
      if (frame.event_type === "agent.work.updated") {
        const profile = one(this.ctx.db, "SELECT * FROM agent_profiles WHERE agent_id=?", frame.data?.agent_id);
        if (!profile || !canAccessSpace(this.ctx.identity.user(b.userId), profile.space_id)) continue;
      }
      if (frame.conversation_id && !conversationAccess(this.ctx.db,frame.conversation_id,b.userId)) continue;
      this.write(b.socket, frame);
      b.cursor = Math.max(b.cursor, frame.event_id ?? 0);
    }
  }
  browserValid(b: Pick<Browser, 'sessionId'>) {
    return !!one(
      this.ctx.db,
      "SELECT 1 FROM auth_sessions s JOIN users u ON u.id=s.user_id WHERE s.session_id=? AND s.revoked=0 AND s.epoch=u.auth_epoch AND s.expires_at>? AND (u.personal_space_enabled=1 OR u.membership_status='active')",
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
        "SELECT * FROM conversation_events WHERE event_id>? AND event_id<=? ORDER BY event_id",
        cursor,
        top,
      )) {
        if (!conversationAccess(db,e.conversation_id,b.userId)) continue;
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
    // Presence is transient: close the gap between the browser's HTTP snapshot
    // and this subscription without adding status rows to the chat event cursor.
    for (const node of all(db,
      "SELECT node_id,status,last_heartbeat_at,last_error FROM nodes WHERE owner_id=?", b.userId)) {
      this.write(b.socket, { op: "event", event_type: "node.status_changed", data: node });
    }
    for (const agent of all(db,
      "SELECT a.agent_id,a.node_id,n.status FROM agent_profiles a JOIN nodes n ON n.node_id=a.node_id AND n.owner_id=a.owner_id WHERE a.owner_id=? AND a.is_stale=0", b.userId)) {
      this.write(b.socket, { op: "event", event_type: "agent.status_changed", data: agent });
    }
  }
  register(c: Connection, p: Row): Row {
    const db = this.ctx.db;
    if (p.node_id !== c.node_id || !this.valid(c)) fail(403, "node identity mismatch");
    if (!Array.isArray(p.agents) || p.agents.some((x: unknown) => typeof x !== "string"))
      fail(400, "agents must be strings");
    // A restored PA no longer belongs to this node; keep its ordinary Agents reconnectable.
    p={...p,agents:p.agents.filter((id:string)=>{
      const b=one(db,'SELECT owner_id,node_id FROM personal_agent_bindings WHERE agent_id=?',id);
      return !b || b.owner_id!==c.owner_id || b.node_id===c.node_id;
    })};
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
    c.agent_lifecycle_v1=p.capabilities?.agent_lifecycle_v1===true;
    this.nodes.set(c.node_id, c);
    db.prepare(
      `INSERT INTO nodes(node_id,owner_id,node_name,status,last_heartbeat_at,agent_count,version) VALUES(?,?,?,'online',?,?,?) ON CONFLICT(node_id) DO UPDATE SET owner_id=excluded.owner_id,node_name=excluded.node_name,status='online',last_error=NULL,last_heartbeat_at=excluded.last_heartbeat_at,agent_count=excluded.agent_count,version=excluded.version`,
    ).run(c.node_id, c.owner_id, p.node_name ?? c.node_id, now(), p.agents.length, p.version ?? "");
    this.ctx.updates?.register(c, p.release);
    db.prepare("UPDATE agent_profiles SET is_stale=1,staled_at=? WHERE node_id=?").run(
      now(),
      c.node_id,
    );
    for (const id of p.agents) {
      const existed = one(db, "SELECT 1 FROM agent_profiles WHERE agent_id=?", id);
      db.prepare(
        `INSERT INTO agent_profiles(agent_id,owner_id,node_id,display_name,workspace_root,work_mode,skills_json,skills_selection_mode,tool_allowlist_json,created_at,updated_at,space_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(agent_id) DO UPDATE SET is_stale=0,staled_at=NULL,workspace_root=COALESCE(excluded.workspace_root,workspace_root),updated_at=excluded.updated_at`,
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
        defaultSpace(ownerAccount(db, c.owner_id)!),
      );
      // Only a first registration seeds local configuration. Reconnect must not
      // replace an existing IM desired revision or a pending configuration operation.
      if (!existed && p.agent_configurations?.[id]) {
        const seed=canonicalAgentConfiguration({...p.agent_configurations[id],agent_id:id,workspace_root:p.agent_workspaces?.[id],work_mode:p.agent_work_modes?.[id]??'single_thread'});
        db.prepare('UPDATE agent_profiles SET display_name=?,group_reply_policy=?,default_model=?,reasoning_effort=?,approval_mode=?,custom_prompt=?,heartbeat_json=?,features_json=?,skills_json=?,skills_selection_mode=?,tool_allowlist_json=?,model_fallbacks_json=? WHERE agent_id=?').run(seed.display_name,seed.group_reply_policy,seed.default_model,seed.reasoning_effort,seed.approval_mode,seed.custom_prompt,seed.heartbeat_json,JSON.stringify(seed.features),JSON.stringify(seed.skills),seed.skills_selection_mode,JSON.stringify(seed.tool_allowlist),JSON.stringify(seed.model_fallbacks),id);
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
      if(!c.agent_lifecycle_v1&&lifecycle(db,id).desired==='disabled')db.prepare("UPDATE agent_lifecycle SET observed='stop_unconfirmed',error_code='node_upgrade_required',error_detail='Update this node to confirm all managed execution has stopped' WHERE agent_id=?").run(id);
      this.ctx.messaging.agentUser(id);
    }
    this.publishNodeStatus(c, "online", { last_heartbeat_at: now(), last_error: null });
    return {
      message_type: "node.register",
      relay_request_ids:1, work_sync_http:1,
      agent_lifecycle_v1:1, agent_lifecycles:p.agents.map((id:string)=>lifecycle(db,id)),
      im_user_url: this.ctx.publicUrl,
      node_id: c.node_id,
      node_epoch: c.node_epoch,
      gateway_access_token: c.token,
      owner_timezone: one(db, "SELECT timezone FROM users WHERE id=?", c.owner_id)?.timezone ?? null,
      personal_agents:all(db,"SELECT * FROM personal_agent_bindings WHERE owner_id=? AND node_id=? AND node_epoch=?",c.owner_id,c.node_id,c.node_epoch),
    };
  }
  private readonly taskWrites=new Map<string,Set<Promise<Row>>>();
  async handle(c:Connection,type:string,p:Row):Promise<Row> {
    const key=`${c.node_id}:${p.agent_id}`;
    // A timed-out client does not cancel its server-side write. Stop waits for that
    // outcome before its atomic pause, including PA-reviewed commits.
    if(type==='task.execution.pause')await Promise.allSettled([...(this.taskWrites.get(key)??[])]);
    const work=this.handleFrame(c,type,p);
    if(type==='pa.action.commit'||type==='task_graph.command'&&['create','apply','delete'].includes(p.action)) {
      const writes=this.taskWrites.get(key)??new Set<Promise<Row>>();this.taskWrites.set(key,writes);writes.add(work);
      void work.finally(()=>{writes.delete(work);if(!writes.size)this.taskWrites.delete(key);}).catch(()=>{});
    }
    return work;
  }
  private async handleFrame(c: Connection, type: string, p: Row): Promise<Row> {
    const db = this.ctx.db,
      s = this.ctx.messaging;
    const ack = (extra: Row = {}) => ({
      type: "ack",
      payload: { message_type: type, request_id:p.request_id, ...extra },
    });
    if (type === "node.register") {
      const result = this.register(c, p);
      return ack(result);
    }
    if (this.nodes.get(c.node_id) !== c || !this.valid(c) || p.node_id !== c.node_id)
      fail(403, "node_not_registered");
    c.lastSeen = Date.now();
    if(type==='agent.lifecycle.report') {
      this.requireAgent(c,p.agent_id);
      if(!c.agent_lifecycle_v1)fail(409,'node_upgrade_required');
      new AgentLifecycles(this.ctx).report(p.agent_id,p);return ack();
    }
    if(type==='task.execution.frozen_schedules') {
      this.requireAgent(c,p.agent_id);
      return ack({schedule_ids:all(db,'SELECT schedule_id FROM task_lifecycle_schedules WHERE agent_id=?',p.agent_id).map(row=>row.schedule_id)});
    }
    const effect=type==='agent.message'||type==='agent.config.boundary'||type==='task_graph.command'&&['create','apply','delete'].includes(p.action)||['pa.source.admit','pa.incident.report','pa.action.prepare','pa.action.review-result','pa.action.commit'].includes(type);
    if(effect) {
      const agentId=type==='agent.message'?String(p.from_session_id??'').replace(/^agent:/,'').split('|tool_call:')[0]:p.agent_id;
      this.requireAgent(c,agentId);requireLifecycle(db,agentId,p.lifecycle_revision);
    }
    if (type === 'node.capabilities.changed') { catalogReads(this.ctx).invalidateNode(c.node_id); return ack(); }
    if (this.rpc.accept(c, type, p)) return ack({request_id:p.request_id});
    if (type.startsWith("pa.")) {
      try { return {type:`${type}.result`,payload:{request_id:p.request_id,ok:true,result:await this.ctx.personal!.handle(c,type,p)}}; }
      catch(error) { const e=error as any;return {type:`${type}.result`,payload:{request_id:p.request_id,ok:false,error:{code:e.detail??"personal_operation_failed",message:e.message}}}; }
    }
    if (type === "node.heartbeat") {
      db.prepare(
        "UPDATE nodes SET status=?,last_heartbeat_at=?,last_error=?,agent_count=COALESCE(?,agent_count) WHERE node_id=?",
      ).run(p.status ?? "online", now(), p.last_error ?? null, p.agent_count ?? null, c.node_id);
      // Pending observations survive transient review failures. Existing heartbeats retry them without a new user message.
      if((p.status??'online')==='online') for(const binding of all(db,`SELECT DISTINCT b.* FROM personal_agent_bindings b
        JOIN pa_source_events e ON e.binding_id=b.binding_id
        WHERE b.node_id=? AND b.status='active' AND e.state IN ('pending','received')`,c.node_id)) this.ctx.personal?.wake(binding);
      return ack({ node_id: c.node_id });
    }
    if (type === "agent.work.append")
      return {
        type: "agent.work.ack",
        payload: this.work.append(c.node_id, p),
      };
    if(['task.execution.snapshot','task.execution.pause','task.execution.scopes'].includes(type)) {
      try {
        const actor={kind:'agent' as const,id:p.agent_id,node_id:c.node_id};
        const binding=one(db,'SELECT 1 FROM personal_agent_bindings WHERE agent_id=?',p.agent_id)?this.ctx.personal!.authority(c,{agent_id:p.agent_id}):undefined;
        const policy=binding?{ownerUserId:binding.owner_user_id,sourceAllowed:(id:string)=>this.ctx.personal!.sourceAllowed(binding,id)}:undefined;
        const result=type==='task.execution.scopes'?this.tasks.executionScopes(actor,policy):type==='task.execution.snapshot'?this.tasks.executionSnapshot(actor,p.conversation_id,policy):this.tasks.pauseExecution(actor,p.conversation_id,p.request_key,policy);
        return {type:`${type}.result`,payload:{request_id:p.request_id,ok:true,result}};
      } catch(error) {return {type:`${type}.result`,payload:{request_id:p.request_id,ok:false,error:error instanceof TaskGraphError?error.asDict():{code:'source_unavailable',message:String(error)}}};}
    }
    if (type === "task_graph.command") {
      try {
        const personal=one(db,"SELECT conversation_id FROM personal_agent_bindings WHERE agent_id=?",p.agent_id);
        if(personal && ["create","apply","delete"].includes(p.action)) {
          const destination=p.action==='create'?p.args?.conversation_id:one(db,"SELECT conversation_id FROM task_graphs WHERE graph_id=?",p.args?.graph_id??"")?.conversation_id;
          if(destination!==personal.conversation_id)throw new TaskGraphError("personal_reviewed_delivery_required","Shared task changes require reviewed delivery");
        }
        if (!p.request_id)
          throw new TaskGraphError(
            "invalid_arguments",
            "request_id required",
          );
        if(personal && ['get','list','activity'].includes(p.action)) {
          const pa=this.ctx.personal!,binding=pa.authority(c,{agent_id:p.agent_id});
          return {type:'task_graph.result',payload:{request_id:p.request_id,ok:true,result:this.tasks.readPersonal(
            {kind:'agent',id:p.agent_id,node_id:c.node_id},binding.owner_user_id,p.action,p.args??{},id=>pa.sourceAllowed(binding,id))}};
        }
        return {
          type: "task_graph.result",
          payload: {
            request_id: p.request_id,
            ok: true,
            result: await this.tasks.executeChecked(
              {
                kind: "agent",
                id: p.agent_id,
                node_id: c.node_id,
                source_message_id: p.source_message_id,
                lifecycle_revision:p.lifecycle_revision,
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
      const targetAgent = this.requireAgent(c, JSON.parse(relay.payload_json).agent_id);
      s.access({ ...c, kind: "gateway" }, relay.conversation_id, targetAgent.agent_id);
      if (!['sent','accepted','completed','failed'].includes(p.delivery_status)) fail(400,'invalid_delivery_status');
      if (relay.status === 'completed' || relay.status === 'failed' || relay.receipt_status === p.delivery_status || (relay.receipt_status==='accepted' && p.delivery_status==='sent')) return ack({relay_task_id:p.relay_task_id});
      if (relay.status === "cancelled") return ack({relay_task_id:p.relay_task_id});
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
      s.delivery.receipt(c.node_id,p.relay_task_id);
      return ack({ relay_task_id: p.relay_task_id });
    }
    if (type === "node.streaming_delta") return ack(this.streaming(c, p));
    if (type === 'agent.session.ensure') {
      const agent=this.requireAgent(c,String(p.agent_id));
      if(agent.work_mode!=='global' || typeof p.session_id!=='string' || !p.session_id)fail(400,'invalid_scope');
      this.work.register(agent.agent_id,p.session_id,c.node_id,{scope:'global_main',title:agent.display_name});
      return ack({session_id:p.session_id});
    }
    if (type === 'agent.message.status') {
      const agent=this.requireAgent(c,String(p.agent_id));
      const previous=one(db,'SELECT * FROM agent_message_dispatch_log WHERE dispatch_request_key=? AND source_agent_id=?',`${agent.agent_id}:${String(p.operation_id)}`,agent.agent_id);
      if(!previous)return ack({found:false});
      s.access({...c,kind:'gateway'},previous.conversation_id,agent.agent_id);
      return ack({found:true,conversation_id:previous.conversation_id,message_id:previous.message_id,target_kind:previous.target_kind,target_id:previous.target_id,source_agent_id:agent.agent_id});
    }
    if (type === 'agent.message') {
      const source=String(p.from_session_id??'').replace(/^agent:/,'').split('|tool_call:');
      const agent=this.requireAgent(c,source[0]!);
      if(p.reply_draft!==undefined)fail(422,'reply_draft is retired; use ComposeMessage');
      let publication:AgentPublication;
      try {publication=decodeAgentPublication(p);}catch(error){fail(400,(error as Error).message);}
      return ack(s.publishAgent({...c,kind:'gateway'},agent.agent_id,source[1],publication));
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
      requireLifecycle(db,a.agent_id,p.lifecycle_revision);
      const personal=one(db,"SELECT * FROM personal_agent_bindings WHERE agent_id=?",a.agent_id);
      if(personal && !this.ctx.personal!.ownerConversation(personal,p.conversation_id))fail(403,"personal_reviewed_delivery_required");
      s.access({ ...c, kind: "gateway" }, p.conversation_id, a.agent_id, "write");
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
        "completed",
        { system_notice: p.system_notice ? { ...p.system_notice, source_agent_display_name: a.display_name } : undefined },
      );
      return ack({ message_id: m.id });
    }

    if (type === "agent.config.boundary") {
      const a = this.requireAgent(c, p.agent_id);
      s.access({ ...c, kind: "gateway" }, p.conversation_id, a.agent_id, "write");
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
    if (!agentAvailable(this.ctx.db, a)) fail(403, "agent_not_accessible");
    if(one(this.ctx.db,'SELECT 1 FROM personal_agent_bindings WHERE agent_id=?',id)) this.ctx.personal!.authority(c,{agent_id:id});
    return a!;
  }
  streaming(c:Connection,p:unknown):ChatStreamReceipt {return this.chat.receive(c,p);}
  relayMessage(m: Row, a: Row, key: string, extra: Row = {}, options: {deferDelivery?: boolean} = {}) {
    const db = this.ctx.db,
      s = this.ctx.messaging;
    const conversation = one(db, "SELECT space_id FROM conversations WHERE id=?", m.conversation_id);
    if (!conversation || lifecycle(db,a.agent_id).desired!=='enabled' || !agentAvailable(db, a) || !canActorAccess(db,s.agentUser(a.agent_id).id,conversation.space_id)) return;
    const personal=one(db,'SELECT * FROM personal_agent_bindings WHERE agent_id=?',a.agent_id);
    if(personal && !this.ctx.personal!.messageAllowed(personal,m)) return;
    if (one(db, "SELECT 1 FROM relay_tasks WHERE idempotency_key=?", key)) return;
    // Delegated PA sends preserve their author even when only the recipient is a member.
    const c = s.conversation(m.conversation_id, s.agentUser(a.agent_id).id);
    const relay = randomUUID(),
      payload = {
        lifecycle_revision:lifecycle(db,a.agent_id).revision,
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
    if (!options.deferDelivery) s.delivery.drain(a.node_id);
  }
  /** Persist group recipients inside the caller transaction when delivery is deferred. */
  groupReply(messageId: string, options: {deferDelivery?: boolean} = {}) {
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
        }, options);
    }
  }
  shutdown() {
    this.rpc.close();
    this.trajectory.shutdown();
    this.ctx.messaging.delivery.stop();
    for (const c of this.nodes.values()) {
      this.disconnect(c, "server_shutdown");
      c.socket.close(1001, "server_shutdown");
    }
    for (const b of this.browsers) b.socket.close(1001);
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
    let registration = Promise.resolve();
    let inFlight=0;
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
      if (++inFlight>16) {socket.close(1013);return;}
      const process = async () => {
        let frame: Row = {};
        try {
          const decoded: unknown = JSON.parse(raw.toString());
          if (!isRecord(decoded) || typeof decoded.type !== 'string'
            || decoded.payload != null && !isRecord(decoded.payload)) fail(400, 'invalid_message');
          frame = decoded;
          if(frame.type!=='node.register')await registration;
          const result = await g.handle(c, frame.type, frame.payload ?? {});
          g.write(socket, {...result,payload:{...result.payload,request_id:frame.payload?.request_id}});
          if (frame.type === "node.register" && result.type === "ack") {
            ctx.updates?.reconnect(c);
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
                      lifecycle_revision:permission.lifecycle_revision,
                      kind: "permission_response",
                      message_id: row.id,
                      request_id: permission.request_id,
                      decision: permission.decision,
                      reason: permission.reason ?? "",
                    },
                  });
              }
            }
            ctx.messaging.delivery.drain(c.node_id);
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
          if ((e as any).statusCode === 403 && !g.valid(c)) socket.close(1008);
        } finally {
          queued -= bytes; inFlight--;
        }
      };
      const task=process();
      if (!g.nodes.has(c.node_id)) registration=task;
      void task;
    });
    socket.on("close", () => g.disconnect(c));
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
