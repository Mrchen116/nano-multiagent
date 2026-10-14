import { randomBytes } from 'node:crypto';
import type { DatabaseSync } from 'node:sqlite';

type ObjectValue = Record<string, unknown>;

/** Store durable model references without replacing the product's access checks.
 *
 * Args:
 *   db: Owner-bound Node database; mappings share its backup and lifetime.
 */
export class ToolReferences {
  constructor(private readonly db: DatabaseSync) {
    db.exec(`CREATE TABLE IF NOT EXISTS tool_references (
      reference TEXT PRIMARY KEY, agent_id TEXT NOT NULL, kind TEXT NOT NULL, value TEXT NOT NULL,
      UNIQUE(agent_id,kind,value)
    )`);
  }

  private reference(agent: string, kind: string, value: string, prefix: string): string {
    const existing = this.db.prepare('SELECT reference FROM tool_references WHERE agent_id=? AND kind=? AND value=?').get(agent, kind, value) as { reference: string } | undefined;
    if (existing) return existing.reference;
    while (true) {
      const reference = prefix + randomBytes(4).toString('hex');
      const inserted = this.db.prepare('INSERT OR IGNORE INTO tool_references VALUES(?,?,?,?)').run(reference, agent, kind, value);
      if (inserted.changes) return reference;
      const raced = this.db.prepare('SELECT reference FROM tool_references WHERE agent_id=? AND kind=? AND value=?').get(agent, kind, value) as { reference: string } | undefined;
      if (raced) return raced.reference;
    }
  }

  private resolve(agent: string, kind: string, reference: string): string {
    const row = this.db.prepare('SELECT value FROM tool_references WHERE reference=? AND agent_id=? AND kind=?').get(reference, agent, kind) as { value: string } | undefined;
    if (!row) throw new Error('Unknown tool reference or reference outside this Agent/tool scope');
    return row.value;
  }

  /** Resolve a short target while continuing to accept saved full routing IDs.
   *
   * Args:
   *   agent: Trusted product Agent identity, not a model-supplied scope.
   *   target: Tool target, optionally prefixed with conversation:.
   * Returns:
   *   Canonical routing target; ordinary IM IDs pass through.
   * Raises:
   *   Error: A short reference is unknown or belongs to another Agent.
   */
  resolveTarget(agent: string, target: string): string {
    const prefix = target.startsWith('conversation:') ? 'conversation:' : '';
    const value = target.slice(prefix.length);
    return prefix + (value.startsWith('c_f_') ? this.resolve(agent, 'conversation', value) : value);
  }

  private target(agent: string, value: unknown): unknown {
    if (typeof value !== 'string') return value;
    const target = value.replace(/^conversation:/, '');
    // A separate namespace cannot collide with the IM server's c_<8 characters> IDs.
    return target.startsWith('external:') ? this.reference(agent, 'conversation', target, 'c_f_') : value;
  }

  /** Decode routing fields without changing content or native DSH IDs.
   *
   * Args:
   *   agent: Trusted product Agent identity.
   *   method: Product method; cursor references are isolated by method.
   *   args: Model arguments, retained without mutation.
   * Returns:
   *   Arguments for the existing authoritative handler and its access checks.
   * Raises:
   *   Error: A compact target/cursor is unknown or outside this scope.
   */
  arguments(agent: string, method: string, args: ObjectValue): ObjectValue {
    if (!['inbox', 'conversations', 'send_message', 'send_message.context', 'task_graph'].includes(method)) return args;
    return { ...args,
      ...(typeof args.target === 'string' ? { target: this.resolveTarget(agent, args.target) } : {}),
      ...(typeof args.cursor === 'string' && args.cursor.startsWith('p_') ? { cursor: this.resolve(agent, `cursor:${method}`, args.cursor) } : {}),
    };
  }

  /** Present compact references without changing canonical delivery or query records.
   *
   * Args:
   *   agent: Trusted product Agent identity.
   *   method: Product method whose known response fields are projected.
   *   value: Canonical result; user content and unknown methods pass through.
   * Returns:
   *   Model-visible result with stable references and duplicate send targets removed.
   * Side Effects:
   *   Persists new mappings before returning them to the model.
   */
  result(agent: string, method: string, value: unknown): unknown {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return value;
    const body = { ...value } as ObjectValue;
    const cursor = (object: ObjectValue): ObjectValue => ({ ...object,
      ...(typeof object.next_cursor === 'string' ? { next_cursor: this.reference(agent, `cursor:${method}`, object.next_cursor, 'p_') } : {}),
    });
    const conversation = (object: ObjectValue): ObjectValue => ({ ...object,
      ...('target' in object ? { target: this.target(agent, object.target) } : {}),
      ...('id' in object ? { id: this.target(agent, object.id) } : {}),
    });
    if (method === 'inbox') {
      if (Array.isArray(body.sources)) body.sources = body.sources.map(source => conversation(source));
      if ('target' in body) body.target = this.target(agent, body.target);
      return cursor(body);
    }
    if (method === 'conversations') {
      if (Array.isArray(body.conversations)) body.conversations = body.conversations.map(item => conversation(item));
      const result = cursor(conversation(body));
      if (result.id === result.target) delete result.id;
      return result;
    }
    if (method === 'task_graph' && body.result && typeof body.result === 'object') return { ...body, result: cursor(body.result as ObjectValue) };
    if (method === 'send_message') {
      body.target = this.target(agent, body.target);
      if ('conversation_id' in body) body.conversation_id = this.target(agent, body.conversation_id);
      if (typeof body.target === 'string' && body.target.replace(/^conversation:/, '') === body.conversation_id) delete body.conversation_id;
      if (Array.isArray(body.inbox_targets)) body.inbox_targets = body.inbox_targets.map(target => this.target(agent, target));
      return body;
    }
    return value;
  }
}
