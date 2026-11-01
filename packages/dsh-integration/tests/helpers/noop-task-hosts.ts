import type { RuntimeClient } from '../../lib/client.js';

/** Register explicit empty product hosts for fixtures that have no Task data. */
export function registerNoopTaskHosts(client: RuntimeClient): void {
  client.rpc.handle('product.task_context.prepare', () => ({ messages: [], revoked: [] }));
  client.rpc.handle('product.task_context.commit', () => null);
  client.rpc.handle('product.task_execution.snapshot', () => ({ kind: 'quiescent', tasks: [], repair_task_ids: [] }));
}
