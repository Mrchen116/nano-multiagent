import { randomUUID } from 'node:crypto';
import { copyFileSync } from 'node:fs';
import { backup } from 'node:sqlite';
import type { EvaluationHistory } from '@nano/product-contracts';
import { openDatabase } from './db.js';
import { createIdentity } from './identity.js';
import { Gateway } from './gateway.js';
import { Messaging } from './messaging.js';
import { PersonalAgents } from './personal-agent.js';
import { transaction, type ImContext } from './context.js';

interface EvaluationChatOptions {
  path: string;
  snapshot?: string;
  nodeId: string;
  agentId: string;
  ownerId: string;
  bindingId: string;
  conversationId: string;
  rootSessionId: string;
  startTime: number;
}

/** Isolated offline IM storage using the ordinary product query and projection path.
 *
 * No listener, delivery worker or production configuration is started. The caller
 * owns one database per phase and only exposes it through product tools.
 */
export class EvaluationChat {
  private readonly ctx: ImContext;
  private readonly principal: { node_id: string; owner_id: string; node_epoch: number };
  private readonly agentUserId: string;

  /** Create a case database, or a writable copy of its sealed chat state.
   * Args:
   *   options: Isolated database paths and the case's persistent PA relationship.
   */
  constructor(private readonly options: EvaluationChatOptions) {
    if (options.snapshot) copyFileSync(options.snapshot, options.path);
    const db = openDatabase(options.path);
    try {
      const { nodeId, agentId, ownerId, bindingId, conversationId, rootSessionId } = options;
      const at = new Date(options.startTime).toISOString();
      if (!options.snapshot) transaction(db, () => {
        for (const [id, username, name] of [[ownerId, `owner:${ownerId}`, 'Owner'], [agentId, `agent:${agentId}`, 'Personal Assistant']]) {
          db.prepare("INSERT INTO users(id,username,display_name,owner_id,created_at,membership_status,timezone) VALUES(?,?,?,?,?,'active','UTC')")
            .run(id!, username!, name!, ownerId, at);
        }
        db.prepare("INSERT INTO nodes(node_id,owner_id,node_name,status) VALUES(?,?,'Evaluation','online')").run(nodeId, ownerId);
        db.prepare('INSERT INTO node_binding_state(node_id,owner_id,node_epoch) VALUES(?,?,1)').run(nodeId, ownerId);
        db.prepare("INSERT INTO agent_profiles(agent_id,owner_id,node_id,display_name,workspace_root,work_mode,created_at,updated_at) VALUES(?,?,?,'Personal Assistant','','global',?,?)")
          .run(agentId, ownerId, nodeId, at, at);
        db.prepare("INSERT INTO conversations(id,title,type,owner_id,created_at) VALUES(?,'Personal Assistant','direct',?,?)").run(conversationId, ownerId, at);
        for (const id of [ownerId, agentId]) db.prepare('INSERT INTO conversation_participants(conversation_id,user_id) VALUES(?,?)').run(conversationId, id);
        db.prepare("INSERT INTO personal_agent_bindings(binding_id,owner_id,owner_user_id,agent_id,node_id,node_epoch,conversation_id,display_name,request_key,status,created_at) VALUES(?,?,?,?,?,1,?,'Personal Assistant',?,'active',?)")
          .run(bindingId, ownerId, ownerId, agentId, nodeId, conversationId, bindingId, at);
        db.prepare('INSERT INTO pa_policies(binding_id) VALUES(?)').run(bindingId);
      });
      // A cursor belongs to the querying phase, never to another answer replica.
      db.exec('DELETE FROM agent_work_query_snapshots; DELETE FROM pa_source_reads;');
      const secret = randomUUID();
      this.ctx = { db, dbPath: options.path, publicUrl: 'http://evaluation.invalid', jwtSecret: secret, uploadDir: '',
        identity: createIdentity(db, secret) } as ImContext;
      this.ctx.messaging = new Messaging(this.ctx);
      this.ctx.gateway = new Gateway(this.ctx);
      this.ctx.personal = new PersonalAgents(this.ctx);
      this.ctx.gateway.work.register(agentId, rootSessionId, nodeId, { scope: 'global_main' });
      this.principal = { node_id: nodeId, owner_id: ownerId, node_epoch: 1 };
      this.agentUserId = this.ctx.messaging.agentUser(agentId).id;
    } catch (error) { db.close(); throw error; }
  }

  /** Import one arrived segment without replaying the assistant or creating live Inbox work.
   * Args:
   *   session: Original turns and their shared session-level timestamp.
   * Returns:
   *   Stored message IDs in original turn order, for the native trajectory mapping.
   */
  importSession(session: EvaluationHistory['sessions'][number]): string[] {
    return transaction(this.ctx.db, () => session.turns.map(turn => this.insert(turn.role, turn.content, session.timestamp).id));
  }

  /** Store a dialogue turn and the durable version proving its original timestamp.
   * Args:
   *   role: Original participant role.
   *   content: Unmodified message body.
   *   timestamp: Historical UTC instant, never the host's wall clock.
   * Returns:
   *   The ordinary IM message projection.
   */
  append(role: 'user' | 'assistant', content: string, timestamp: number) {
    return transaction(this.ctx.db, () => this.insert(role, content, timestamp));
  }

  private insert(role: 'user' | 'assistant', content: string, timestamp: number) {
    const at = new Date(timestamp).toISOString();
    const message = this.ctx.messaging.records.insert(this.options.conversationId,
      role === 'user' ? this.options.ownerId : this.agentUserId, role === 'user' ? 'user' : 'agent', content, [], null, 'completed',
      { created_at: at, timezone: 'UTC', publish: false });
    // Import both the message and its event at the historical time. Work.query
    // verifies the matching durable event before exposing a frozen Dreaming read.
    this.ctx.db.prepare("UPDATE conversation_events SET created_at=?,payload_json=json_set(payload_json,'$.created_at',?) WHERE message_id=?")
      .run(at, at, message.id);
    return message;
  }

  /** Query through the same authority, pagination and cutoff checks as the live IM.
   * Args:
   *   args: Product conversation query; caller identity is fixed by this instance.
   * Returns:
   *   The ordinary IM query result, including any continuation cursor.
   */
  query(args: Record<string, unknown>) {
    if (args.action === 'create' || args.action === 'join') throw new Error('Evaluation connects only the existing owner chat');
    return this.ctx.gateway.work.query(this.principal, { ...args, agent_id: this.options.agentId, session_id: this.options.rootSessionId });
  }

  /** Resolve the actual stored PA source policy through the product authority check. */
  sources() { return this.ctx.personal!.sources(this.principal, { agent_id: this.options.agentId, action: 'list' }); }

  /** Synchronize task originals against this case's stored PA authority.
   * Args:
   *   args: Ordinary product cursor and pending-message revalidation request.
   * Returns:
   *   The fixed authority range; dialogue-only datasets have no task originals.
   */
  taskContext(args: Record<string, unknown>) {
    const personal = this.ctx.personal!;
    const binding = personal.authority(this.principal, { agent_id: this.options.agentId });
    return this.ctx.messaging.syncTaskContext(this.options.agentId, args.after as number, args.through as number | undefined,
      args.limit as number, id => personal.sourceAllowed(binding, id), args.pending as string[]);
  }

  /** Make a consistent SQLite snapshot; later answer phases always copy it.
   * Args:
   *   path: New sealed database destination owned by this case.
   */
  async snapshot(path: string): Promise<void> { await backup(this.ctx.db, path); }

  /** Close only this phase's handles; no shared service is involved. */
  close(): void { this.ctx.db.close(); }
}
