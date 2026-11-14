import type { Context } from '@deepseek-ai/cordis';
import { isAgentLoopRequest } from '@deepseek-ai/dsh-llm';
import { defineDomain, domainTable, type DomainSpec, type DomainTableSpec } from '@deepseek-ai/dsh-storage-domain';
import { createHash } from 'node:crypto';
import { z } from 'zod';
import { RecordWrites } from './record-writes.js';

interface Receipt { sessionId: string; inputId: string; pending: boolean }
interface ReceiptDomain extends DomainSpec { tables: { receipts: DomainTableSpec<string, Receipt> } }
const domain: ReceiptDomain = defineDomain({ name:'nano_inbox_delivery', version:1, layout:'per-record',
  tables:{receipts:domainTable(z.object({sessionId:z.string(),inputId:z.string(),pending:z.boolean()}))} });
const key = (sessionId: string, inputId: string) => createHash('sha256').update(JSON.stringify([sessionId,inputId])).digest('hex');

/** Durable model-delivery outbox, projected through the existing Work synchronization. */
export class InboxDelivery {
  private readonly receipts = new Map<string, Map<string, Receipt>>();
  private readonly writes: RecordWrites<Receipt>;
  private readonly ready: Promise<void>;
  private readonly storage;
  constructor(ctx: Context, owner: (sessionId: string) => string | undefined, changed: (sessionId: string) => void) {
    this.storage = ctx.storageDomain.open(domain);
    this.writes = new RecordWrites(async (id, receipt) => { await (await this.storage).table('receipts').put(id,receipt); });
    this.ready = this.storage.then(storage => {
      for (const [, receipt] of storage.table('receipts').entries()) this.remember(receipt);
    });
    const self = this;
    ctx.on('llm/stream', async function* (options, next) {
      const sessionId = isAgentLoopRequest(options) ? options.sessionId : undefined;
      const agentId = sessionId && owner(sessionId);
      if (!sessionId || !agentId) { yield* next(); return; }
      await self.ready;
      const inputIds = [...new Set(options.messages.flatMap(message => {
        const source = message.role === 'user' ? message.source : undefined;
        return source?.kind === 'nano-system' && source.actorId === agentId &&
          ['inbox','inbox-background'].includes(source.channel) && !self.receipts.get(sessionId)?.has(source.messageId) ? [source.messageId] : [];
      }))];
      let confirmed = false;
      for await (const chunk of next()) {
        if (!confirmed && inputIds.length && !options.signal?.aborted &&
            ((chunk.type === 'text-delta' || chunk.type === 'reasoning-delta') && chunk.text.length > 0 ||
              chunk.type === 'tool-call-delta' && chunk.argumentsDelta.length > 0 ||
              chunk.type === 'block-end' && (chunk.block.type === 'tool-call' ? !!chunk.block.name :
                (chunk.block.type === 'text' || chunk.block.type === 'reasoning') && chunk.block.text.length > 0))) {
          for (const inputId of inputIds) {
            const receipt = {sessionId,inputId,pending:true};
            await self.writes.put(key(sessionId,inputId),receipt);
            self.remember(receipt);
          }
          changed(sessionId);
          confirmed = true;
        }
        yield chunk;
      }
    });
    ctx.effect(() => async () => { await this.writes.flush(); await (await this.storage).close(); });
  }
  private remember(receipt: Receipt): void {
    const rows = this.receipts.get(receipt.sessionId) ?? new Map<string, Receipt>();
    rows.set(receipt.inputId,receipt); this.receipts.set(receipt.sessionId,rows);
  }
  /** Return a bounded durable page, retained until the product confirms its own commit. */
  async pending(sessionId: string): Promise<string[]> {
    await this.ready; await this.writes.flush();
    return [...(this.receipts.get(sessionId)?.values() ?? [])].filter(row => row.pending).slice(0,256).map(row => row.inputId);
  }
  /** A lost acknowledgement safely replays the same immutable delivery facts. */
  async confirm(sessionId: string, inputIds: string[]): Promise<void> {
    await this.ready;
    for (const inputId of inputIds) {
      const prior = this.receipts.get(sessionId)?.get(inputId);
      if (!prior?.pending) continue;
      const receipt = {...prior,pending:false};
      await this.writes.put(key(sessionId,inputId),receipt); this.remember(receipt);
    }
  }
  /** Remove receipt identities with their retired native sessions. */
  async forget(sessionIds: ReadonlySet<string>): Promise<void> {
    await this.ready;
    await this.writes.forget((_,receipt) => sessionIds.has(receipt.sessionId));
    const table = (await this.storage).table('receipts');
    for (const id of sessionIds) {
      for (const inputId of this.receipts.get(id)?.keys() ?? []) await table.delete(key(id,inputId));
      this.receipts.delete(id);
    }
  }
}
