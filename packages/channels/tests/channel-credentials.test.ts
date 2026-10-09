import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { ChannelKey } from '../src/channel-credentials.js';

it('reopens encrypted credentials after restart only under their original owner and revision', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'nano-channel-key-'));
  try {
    const key = await ChannelKey.load(join(directory, 'key.pem'));
    const aad = { owner_id: 'owner', node_id: 'node', agent_id: 'agent', channel_id: 'channel', provider: 'feishu', credential_revision: 1 };
    const envelope = key.seal({ app_secret: 'test-only-secret' }, aad);
    expect(JSON.stringify(envelope)).not.toContain('test-only-secret');
    const restored = await ChannelKey.load(join(directory, 'key.pem'));
    expect(restored.registration).toEqual(key.registration);
    expect(restored.open(envelope, aad)).toEqual({ app_secret: 'test-only-secret' });
    expect(() => restored.open(envelope, { ...aad, owner_id: 'another-owner' })).toThrow('credential envelope invalid');
    expect(() => restored.open(envelope, { ...aad, credential_revision: 2 })).toThrow('credential envelope invalid');
  } finally { await rm(directory, { recursive: true, force: true }); }
});
