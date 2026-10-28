import { mkdtemp, rm, writeFile, readFile } from 'node:fs/promises';
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

it('opens fixed pre-refactor IM and node envelopes with Unicode AAD after key reload', async () => {
  // Synthetic historical key/envelopes, generated on a34af8473, not with today's encoder.
  const legacy = JSON.parse(await readFile(new URL('./fixtures/credential-envelopes-v1.json', import.meta.url), 'utf8'));
  const directory = await mkdtemp(join(tmpdir(), 'nano-channel-legacy-'));
  try {
    await writeFile(join(directory, 'key.pem'), legacy.privateKey, {mode: 0o600});
    const key = await ChannelKey.load(join(directory, 'key.pem'));
    for (const envelope of [legacy.imEnvelope, legacy.nodeEnvelope]) {
      expect(key.open(envelope, legacy.aad)).toEqual(legacy.secret);
      expect(() => key.open(envelope, {...legacy.aad, owner_id: 'another-owner'})).toThrow('credential envelope invalid');
      expect(() => key.open(envelope, {...legacy.aad, credential_revision: 8})).toThrow('credential envelope invalid');
    }
    const fresh = key.seal(legacy.secret, legacy.aad);
    const restored = await ChannelKey.load(join(directory, 'key.pem'));
    expect(restored.open(fresh, legacy.aad)).toEqual(legacy.secret);
  } finally { await rm(directory, {recursive: true, force: true}); }
});
