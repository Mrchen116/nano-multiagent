import { DatabaseSync } from 'node:sqlite';
import { createHash } from 'node:crypto';
import type { FeishuMessage } from '@nano/channels';
import type { RelayInput } from '@nano/product-contracts';

export interface ExternalChat { id: string; agentId: string; appId: string; chatId: string; isGroup: boolean; sourceId: string; shadowId?: string }
export interface ExternalOutput { id: string; chatId: string; operationId: string; reply?: string; state: string; platformId?: string; imId?: string }

/** Separate facts for platform delivery and IM projection; one can succeed without the other. */
export class ExternalStore {
  private readonly db: DatabaseSync;
  constructor(path: string) {
    this.db = new DatabaseSync(path);
    this.db.exec(`PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL;
      CREATE TABLE IF NOT EXISTS chats(id TEXT PRIMARY KEY,agent_id TEXT NOT NULL,body TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS inbound(id TEXT PRIMARY KEY,chat_id TEXT NOT NULL,body TEXT NOT NULL,accepted INTEGER NOT NULL DEFAULT 0,mirror TEXT,reaction TEXT);
      CREATE TABLE IF NOT EXISTS outputs(id TEXT PRIMARY KEY,chat_id TEXT NOT NULL,operation_id TEXT UNIQUE NOT NULL,reply TEXT,state TEXT NOT NULL DEFAULT 'prepared',platform_id TEXT,im_id TEXT);
      CREATE TABLE IF NOT EXISTS frames(id TEXT PRIMARY KEY,output_id TEXT NOT NULL,body TEXT NOT NULL,mirrored INTEGER NOT NULL DEFAULT 0);
      CREATE TABLE IF NOT EXISTS images(url TEXT PRIMARY KEY,agent_id TEXT NOT NULL,data BLOB NOT NULL,media_type TEXT NOT NULL,uploaded TEXT);
      CREATE TABLE IF NOT EXISTS approvals(request_id TEXT PRIMARY KEY,output_id TEXT NOT NULL,platform_id TEXT,body TEXT NOT NULL,settled INTEGER NOT NULL DEFAULT 0);
    `);
    // A crash after dispatch has no trustworthy platform result. Recovery must never blindly send it again.
    this.db.exec("UPDATE outputs SET state='unknown' WHERE state='sending'");
  }
  chat(id: string): ExternalChat | undefined {
    const row = this.db.prepare('SELECT body FROM chats WHERE id=? OR json_extract(body,\'$.shadowId\')=?').get(id, id) as { body: string } | undefined;
    return row && JSON.parse(row.body) as ExternalChat;
  }
  chats(): ExternalChat[] { return (this.db.prepare('SELECT body FROM chats').all() as { body: string }[]).map(row => JSON.parse(row.body) as ExternalChat); }
  saveChat(chat: ExternalChat): void { this.db.prepare('INSERT INTO chats VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body').run(chat.id, chat.agentId, JSON.stringify(chat)); }
  saveInbound(id: string, chatId: string, message: FeishuMessage, input: RelayInput): void {
    this.db.prepare('INSERT OR IGNORE INTO inbound(id,chat_id,body) VALUES(?,?,?)').run(id, chatId, JSON.stringify({ message, input }));
  }
  inbound() { return (this.db.prepare('SELECT id,chat_id AS chatId,body,accepted,mirror,reaction FROM inbound ORDER BY rowid').all() as { id: string; chatId: string; body: string; accepted: number; mirror: string | null; reaction: string | null }[]).map(row => ({ ...row, ...JSON.parse(row.body) as { message: FeishuMessage; input: RelayInput } })); }
  updateInput(id: string, message: FeishuMessage, input: RelayInput): void { this.db.prepare('UPDATE inbound SET body=? WHERE id=?').run(JSON.stringify({ message, input }), id); }
  accept(id: string): void { this.db.prepare('UPDATE inbound SET accepted=1 WHERE id=?').run(id); }
  mirrorInput(id: string, messageId: string): void { this.db.prepare('UPDATE inbound SET mirror=? WHERE id=?').run(messageId, id); }
  reaction(id: string, reaction: string | null): void { this.db.prepare('UPDATE inbound SET reaction=? WHERE id=?').run(reaction, id); }
  output(id: string): ExternalOutput | undefined {
    return this.db.prepare('SELECT id,chat_id AS chatId,operation_id AS operationId,reply,state,platform_id AS platformId,im_id AS imId FROM outputs WHERE id=?').get(id) as unknown as ExternalOutput | undefined;
  }
  prepare(chatId: string, operationId: string, reply?: string): ExternalOutput {
    const id = `external:${createHash('sha256').update(operationId).digest('hex')}`;
    this.db.prepare('INSERT OR IGNORE INTO outputs(id,chat_id,operation_id,reply) VALUES(?,?,?,?)').run(id, chatId, operationId, reply ?? null);
    return this.output(id)!;
  }
  settle(id: string, state: string, platformId?: string): void { this.db.prepare('UPDATE outputs SET state=?,platform_id=coalesce(?,platform_id) WHERE id=?').run(state, platformId ?? null, id); }
  mirrorOutput(id: string, imId: string): void { this.db.prepare('UPDATE outputs SET im_id=? WHERE id=?').run(imId, id); }
  frame(outputId: string, body: Record<string, unknown>): void {
    const encoded = JSON.stringify(body); const key = createHash('sha256').update(`${outputId}:${encoded}`).digest('hex');
    this.db.prepare('INSERT OR IGNORE INTO frames(id,output_id,body) VALUES(?,?,?)').run(key, outputId, encoded);
  }
  pendingFrames() { return (this.db.prepare('SELECT id,output_id AS outputId,body FROM frames WHERE mirrored=0 ORDER BY rowid').all() as { id: string; outputId: string; body: string }[]).map(row => ({ ...row, body: JSON.parse(row.body) as Record<string, unknown> })); }
  confirmFrame(id: string): void { this.db.prepare('UPDATE frames SET mirrored=1 WHERE id=?').run(id); }
  image(url: string, agentId: string): { data: Buffer; mediaType: string; uploaded: string | null } | undefined {
    const row = this.db.prepare('SELECT data,media_type AS mediaType,uploaded FROM images WHERE url=? AND agent_id=?').get(url, agentId) as { data: Uint8Array; mediaType: string; uploaded: string | null } | undefined;
    return row && { ...row, data: Buffer.from(row.data) };
  }
  saveImage(url: string, agentId: string, data: Buffer, mediaType: string): void { this.db.prepare('INSERT OR IGNORE INTO images(url,agent_id,data,media_type) VALUES(?,?,?,?)').run(url, agentId, data, mediaType); }
  uploaded(url: string, attachment: unknown): void { this.db.prepare('UPDATE images SET uploaded=? WHERE url=?').run(JSON.stringify(attachment), url); }
  approval(requestId: string, outputId: string, body: Record<string, unknown>, platformId?: string): void {
    this.db.prepare('INSERT INTO approvals(request_id,output_id,body,platform_id) VALUES(?,?,?,?) ON CONFLICT(request_id) DO UPDATE SET platform_id=coalesce(excluded.platform_id,platform_id)').run(requestId, outputId, JSON.stringify(body), platformId ?? null);
  }
  approvals() { return (this.db.prepare('SELECT request_id AS requestId,output_id AS outputId,platform_id AS platformId,body,settled FROM approvals').all() as { requestId: string; outputId: string; platformId: string | null; body: string; settled: number }[]).map(row => ({ ...row, body: JSON.parse(row.body) as Record<string, unknown> })); }
  settleApproval(requestId: string): void { this.db.prepare('UPDATE approvals SET settled=1 WHERE request_id=?').run(requestId); }
  close(): void { this.db.close(); }
}
