import net from 'node:net';
import { createInterface } from 'node:readline';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { TrajectoryValueDecoder } from '@nano/product-contracts';
import { LocalNodeBridge } from '../src/local-bridge.js';

it('streams >16MiB subagent trajectory payloads over local IPC without 1MiB relay cutoff and enforces owner_id', async () => {
  const dir = await mkdtemp(join(tmpdir(), 'nano-bridge-'));
  const configPath = join(dir, 'config.yaml');
  const largeOutput = 'X'.repeat(18 * 1024 * 1024); // 18 MiB (> 16 MiB WorkSync cap!)
  const closedObservers: string[] = [];

  const bridge = new LocalNodeBridge({
    configPath,
    nodeId: 'node-local',
    ownerId: () => 'owner-alice',
    nodeEpoch: () => 7,
    ready: () => true,
    connected: () => true,
    bindings: () => [
      {
        sessionId: 'root-session-e1',
        conversationId: 'global:e1',
        agentId: 'e1',
        ownerId: 'owner-alice',
        cwd: dir,
        revision: 'r1',
      },
    ],
    runtime: {
      request: async (method: string, params: unknown) => {
        const p = params as Record<string, unknown>;
        if (method === 'trajectory.prepare') {
          expect(p.rootSessionId).toBe('root-session-e1');
          expect(p.sessionId).toBe('unsynced-subagent-fork-1');
          return { version: '0.2.1-alpha.1', initialCatalog: { runs: 2 } };
        }
        if (method === 'trajectory.call') {
          if (p.method === 'trajectory/attachment-source') {
            return { ok: true, value: { sources: [{ kind: 'workspace', path: 'charts/plot.png' }] } };
          }
          if (p.method === 'session/attachment') {
            expect(p.attachmentAuthorized).toBe(true);
            return { ok: true, value: { mimeType: 'image/png', dataBase64: 'YWJj' } };
          }
          return { ok: true, value: { records: [{ toolOutput: largeOutput }] } };
        }
        if (method === 'trajectory.close') {
          closedObservers.push(String(p.observerId));
          return { closed: true };
        }
        throw new Error(`Unexpected method ${method}`);
      },
    },
  });

  await bridge.start();
  try {
    const socket = net.connect(bridge.address);
    await new Promise<void>((resolve, reject) => {
      socket.once('connect', resolve);
      socket.once('error', reject);
    });
    const decoder = new TrajectoryValueDecoder();
    const frames: Record<string, unknown>[] = [];
    let onFrame: (() => void) | undefined;
    const rl = createInterface({ input: socket, crlfDelay: Infinity });
    rl.on('line', line => {
      const raw = JSON.parse(line) as Record<string, unknown>;
      if (raw.type === 'trajectory-fragment') {
        const assembled = decoder.push(raw as never) as Record<string, unknown> | undefined;
        if (assembled) {
          frames.push(assembled);
          onFrame?.();
        }
      } else {
        frames.push(raw);
        onFrame?.();
      }
    });

    const waitFor = async (predicate: (f: Record<string, unknown>) => boolean) => {
      for (;;) {
        const found = frames.find(predicate);
        if (found) return found;
        await new Promise<void>(r => { onFrame = r; });
      }
    };

    // 1. Foreign owner is rejected at the local bridge boundary (R2-R1).
    socket.write(
      JSON.stringify({
        id: 'bad-owner',
        method: 'local.trajectory.prepare',
        observerId: 'obs-foreign',
        agentId: 'e1',
        sessionId: 'unsynced-subagent-fork-1',
        ownerId: 'owner-bob',
        nodeEpoch: 7,
      }) + '\n',
    );
    const rejected = await waitFor(f => f.id === 'bad-owner');
    expect(rejected).toMatchObject({ ok: false, code: 'foreign_owner' });

    // 2. Legitimate owner prepares unsynced child session and streams an 18 MiB payload intact.
    socket.write(
      JSON.stringify({
        id: 'prep-ok',
        method: 'local.trajectory.prepare',
        observerId: 'obs-1',
        agentId: 'e1',
        sessionId: 'unsynced-subagent-fork-1',
        ownerId: 'owner-alice',
        nodeEpoch: 7,
      }) + '\n',
    );
    const readyFrame = await waitFor(f => f.type === 'ready' && f.observerId === 'obs-1');
    expect(readyFrame).toMatchObject({ version: '0.2.1-alpha.1' });

    socket.write(
      JSON.stringify({
        method: 'local.trajectory.request',
        observerId: 'obs-1',
        request: { type: 'call', requestId: 'req-18mb', method: 'session/page', params: {} },
      }) + '\n',
    );
    const resultFrame = await waitFor(f => f.type === 'result' && f.requestId === 'req-18mb');
    const output = ((resultFrame.value as { value: { records: { toolOutput: string }[] } }).value.records[0]!).toolOutput;
    expect(output.length).toBe(largeOutput.length);

    // 3. Enforces read-only method allowlist and blocks spoofed `request.attachmentAuthorized` unless host sets `hostAttachmentAuthorized: true`.
    socket.write(
      JSON.stringify({
        method: 'local.trajectory.request',
        observerId: 'obs-1',
        request: { type: 'call', requestId: 'req-write', method: 'session/mutate', params: {} },
      }) + '\n',
    );
    const readOnlyErr = await waitFor(f => f.type === 'error' && f.requestId === 'req-write');
    expect(readOnlyErr).toMatchObject({ code: 'read_only' });

    socket.write(
      JSON.stringify({
        method: 'local.trajectory.request',
        observerId: 'obs-1',
        request: {
          type: 'call',
          requestId: 'req-spoof-att',
          method: 'session/attachment',
          params: { args: { request: { attachmentId: 'att-1' } } },
          attachmentAuthorized: true,
        },
      }) + '\n',
    );
    const spoofErr = await waitFor(f => f.type === 'error' && f.requestId === 'req-spoof-att');
    expect(spoofErr).toMatchObject({ code: 'attachment_forbidden' });

    socket.write(
      JSON.stringify({
        id: 'att-src-1',
        method: 'local.trajectory.attachment_sources',
        observerId: 'obs-1',
        params: { args: { request: { attachmentId: 'att-1' } } },
      }) + '\n',
    );
    const srcRes = await waitFor(f => f.id === 'att-src-1');
    expect(srcRes).toMatchObject({ ok: true, sources: [{ kind: 'workspace', path: 'charts/plot.png' }] });

    socket.write(
      JSON.stringify({
        method: 'local.trajectory.request',
        observerId: 'obs-1',
        hostAttachmentAuthorized: true,
        request: {
          type: 'call',
          requestId: 'req-ok-att',
          method: 'session/attachment',
          params: { args: { request: { attachmentId: 'att-1' } } },
        },
      }) + '\n',
    );
    const attOk = await waitFor(f => f.type === 'result' && f.requestId === 'req-ok-att');
    expect(attOk).toMatchObject({ type: 'result' });

    socket.destroy();
    await expect.poll(() => closedObservers).toContain('obs-1');
  } finally {
    await bridge.close();
    await rm(dir, { recursive: true, force: true });
  }
});
