import type { RuntimeClient } from '../../lib/client.js';

/** Explicit context host for fixtures whose Task snapshot is supplied separately. */
export function registerNoopTaskContext(client: RuntimeClient): void {
  client.rpc.handle('product.task_context.prepare', () => ({ messages: [], revoked: [] }));
  client.rpc.handle('product.task_context.commit', () => null);
}
