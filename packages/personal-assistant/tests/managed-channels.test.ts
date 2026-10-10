import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createHash } from 'node:crypto';
import { DatabaseSync } from 'node:sqlite';
import { expect, it } from 'vitest';
import { ChannelKey, type ProtocolFrame } from '@nano/channels';
import { ManagedChannels, type ChannelManifest, type ManagedChannel } from '../src/managed-channels.js';

it('validates whole generations before changing listeners and recovers encrypted desired state offline', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'nano-managed-')); const key = await ChannelKey.load(join(directory, 'key')); const path = join(directory, 'state.sqlite3');
  let ready = false; const events: string[] = []; const frames: ProtocolFrame[] = [];
  const options = { nodeId: 'node', ownerId: 'owner', key, hasAgent: (id: string) => ['a', 'b'].includes(id), remove: (id: string) => { events.push(`remove:${id}`); }, onError: () => {},
    relay: { get ready() { return ready; }, async request(type: string, payload: Record<string, unknown>) { frames.push({ type, payload }); return { type: 'result', payload: type === 'channel.reconcile.result' ? { head_outcome: 'accepted', removal_token_outcomes: [] } : { outcome: 'accepted' } }; } },
    create: (item: ManagedChannel, secret: Record<string, string>, callbacks: { status(state: string): void }) => {
      expect(secret.app_secret).toBe('sensitive');
      return { async start() { events.push(`start:${item.agent_id}:${item.channel_revision}`); callbacks.status('ready'); }, stop() { events.push(`stop:${item.agent_id}`); } };
    },
  };
  const item = (id: string, revision = 1): ManagedChannel => ({ channel_id: id, agent_id: id, node_id: 'node', provider: 'feishu', enabled: true, config: { app_id: id }, provider_runtime: {}, credential_key_id: key.registration.credential_key_id,
    credential_revision: revision, channel_revision: revision, provider_identity_revision: 1, provider_identity_fingerprint: createHash('sha256').update(`feishu\0${id}`).digest('hex'),
    credential_envelope: key.seal({ app_secret: 'sensitive' }, { owner_id: 'owner', node_id: 'node', agent_id: id, channel_id: id, provider: 'feishu', credential_revision: revision }),
  });
  const manifest = (revision: number, channels: ManagedChannel[]): ChannelManifest => ({ request_id: `r${revision}`, node_id: 'node', owner_id: 'owner', manifest_revision: revision, channels, removals: [] });
  const apply = (manager: ManagedChannels, value: ChannelManifest) => manager.handle({ type: 'channel.reconcile', payload: value as unknown as Record<string, unknown> });
  let manager = new ManagedChannels(path, options);
  try {
    const first = manifest(1, [item('a')]); await apply(manager, first); await apply(manager, first);
    expect(events).toEqual(['start:a:1']);
    const invalid = item('b'); invalid.credential_revision = 2;
    await expect(apply(manager, manifest(2, [item('a', 2), invalid]))).rejects.toThrow();
    expect(events).toEqual(['start:a:1']);
    await manager.stop(); events.length = 0;
    manager = new ManagedChannels(path, options); manager.seed([{ agentId: 'b', enabled: true, appId: 'wrong', appSecret: 'wrong' }]); await manager.start();
    expect(events).toEqual(['start:a:1']);
    await apply(manager, manifest(2, [item('a', 2)]));
    expect(events).toEqual(['start:a:1', 'remove:a', 'stop:a', 'start:a:2']);
    await apply(manager, { ...manifest(3, []), removals: [{ removal_token: 'delete-a', channel_id: 'a', deletion_manifest_revision: 3 }] });
    await apply(manager, manifest(4, [])); ready = true; await manager.flush();
    expect(frames.some(frame => JSON.stringify(frame.payload).includes('delete-a'))).toBe(true);
    expect(JSON.stringify(frames)).not.toContain('sensitive');
    const statuses = frames.filter(frame => frame.type === 'channel.status');
    expect(statuses[0]?.payload).toMatchObject({ status_sequence: 1, instance_started: true });
    const db = new DatabaseSync(path); expect(JSON.stringify(db.prepare('SELECT * FROM state').all())).not.toContain('sensitive'); db.close();
  } finally { await manager.stop(); await rm(directory, { recursive: true, force: true }); }
});
