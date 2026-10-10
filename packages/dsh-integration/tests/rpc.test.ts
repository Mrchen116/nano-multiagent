import { PassThrough } from 'node:stream';
import { describe, expect, it } from 'vitest';
import { RpcPeer } from '../src/rpc.js';

function peers() {
  const toRuntime = new PassThrough();
  const toNode = new PassThrough();
  return [new RpcPeer(toNode, toRuntime), new RpcPeer(toRuntime, toNode)] as const;
}

describe('runtime control transport', () => {
  it('handles an approval answer while a reverse product callback is waiting', async () => {
    const [node, runtime] = peers();
    let release!: (value: unknown) => void;
    node.handle('product.call', () => new Promise(resolve => { release = resolve; }));
    runtime.handle('submit', () => runtime.request('product.call', { tool: 'send' }));
    runtime.handle('approval.answer', () => { release({ sent: true }); return { accepted: true }; });
    const completion = node.request('submit', {});
    await expect(node.request('approval.answer', {})).resolves.toEqual({ accepted: true });
    await expect(completion).resolves.toEqual({ sent: true });
    node.close(); runtime.close();
  });

  it('rejects unresolved calls on disconnect without resending them', async () => {
    const [node, runtime] = peers();
    runtime.handle('submit', () => new Promise(() => {}));
    const pending = node.request('submit', { inputId: 'stable-input' });
    const failed = expect(pending).rejects.toThrow('closed');
    node.close();
    await failed;
    runtime.close();
  });
});
