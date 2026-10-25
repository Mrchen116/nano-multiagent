import { Service, type Context } from '@deepseek-ai/cordis';
import { defineDomain, domainTable, type DomainSpec, type DomainTableSpec } from '@deepseek-ai/dsh-storage-domain';
import { realpath } from 'node:fs/promises';
import { resolve, relative, isAbsolute } from 'node:path';
import { z } from 'zod';

export type AttachmentSource = { kind: 'chat'; conversationId: string; messageId: string; url: string } | { kind: 'workspace'; path: string };
interface SourcesDomain extends DomainSpec { tables: { sources: DomainTableSpec<string, AttachmentSource[]> } }
export const trajectorySourcesDomain: SourcesDomain = defineDomain({ name: 'nano_trajectory_sources', version: 1, layout: 'per-record', tables: { sources: domainTable(z.array(z.any())) } });
declare module '@deepseek-ai/cordis' { interface Context { nanoTrajectoryAttachments: TrajectoryAttachments } }

/** Persists provenance identities, never attachment bytes or arbitrary viewer paths. */
export class TrajectoryAttachments extends Service {
  private readonly domain;
  private writes = Promise.resolve();
  constructor(ctx: Context) {
    super(ctx, 'nanoTrajectoryAttachments');
    this.domain = ctx.storageDomain.open(trajectorySourcesDomain);
    ctx.effect(() => async () => { await this.writes; await (await this.domain).close(); });
    ctx.on('tools/result', (exec, result) => {
      if (exec.name !== 'read_image' || result.isError || !exec.agent?.session.header.cwd) return;
      const path = (exec.arguments as { file_path?: string }).file_path;
      if (!path) return;
      const sessionId = exec.agent.id, cwd = exec.agent.session.header.cwd;
      const content = result.content;
      this.enqueue(async () => {
        const root = await realpath(cwd), target = await realpath(resolve(cwd, path));
        const inside = relative(root, target);
        if (inside.startsWith('..') || isAbsolute(inside)) return;
        await this.put(sessionId, content, content.map(() => ({ kind: 'workspace', path: inside })));
      });
    });
  }

  /** Record trusted admission metadata alongside the normalized native attachment references. */
  record(sessionId: string, content: readonly unknown[], sources: readonly (AttachmentSource | null)[]): Promise<void> {
    this.enqueue(() => this.put(sessionId, content, sources));
    return this.writes;
  }

  async read(sessionId: string, attachmentId: string): Promise<AttachmentSource[]> {
    await this.writes;
    return (await (await this.domain).table('sources').get(this.key(sessionId, attachmentId))) ?? [];
  }

  private key(sessionId: string, attachmentId: string) { return Buffer.from(JSON.stringify([sessionId, attachmentId])).toString('base64url'); }
  private enqueue(write: () => Promise<void>): void {
    // Provenance is an auxiliary read gate: a missing/deleted source denies its
    // preview, but must never poison admission of subsequent business inputs.
    this.writes = this.writes.then(write).catch(error => this.ctx.logger.warn('Trajectory attachment provenance unavailable: %s', String(error)));
  }
  private async put(sessionId: string, content: readonly unknown[], sources: readonly (AttachmentSource | null)[]) {
    const table = (await this.domain).table('sources');
    for (const [index, value] of content.entries()) {
      const block = value as { type?: string; attachment?: { attachmentId?: string } }, source = sources[index];
      if (block.type !== 'image' || !block.attachment?.attachmentId || !source) continue;
      const key = this.key(sessionId, block.attachment.attachmentId), existing = await table.get(key) ?? [];
      if (!existing.some(item => JSON.stringify(item) === JSON.stringify(source))) await table.put(key, [...existing, source]);
    }
  }
}

/** Legacy inline images cannot bypass provenance authorization through the history stream. */
export function withoutInlineImages(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(withoutInlineImages);
  if (!value || typeof value !== 'object') return value;
  const object = value as Record<string, unknown>;
  if (object.type === 'image' && ('data' in object || 'url' in object)) return { type: 'text', text: '[图片：无法验证附件访问权限]' };
  return Object.fromEntries(Object.entries(object).map(([key, item]) => [key, withoutInlineImages(item)]));
}
