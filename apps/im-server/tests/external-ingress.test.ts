import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import { ExternalChannels } from '../../../packages/personal-assistant/src/external.js';
import { NodeStore } from '../../../packages/personal-assistant/src/store.js';
import { requestIm } from '../../node/src/im-http.js';
import { createServer } from '../src/server.js';
import type { Connection } from '../src/gateway.js';

it.each([true, false])('mirrors Feishu text and images over the Node HTTP adapter and recovers a lost receipt once (personal=%s)', async personal => {
  const directory = await mkdtemp(join(tmpdir(), 'nano-external-http-'));
  const app = await createServer({ dbPath: join(directory, 'im.sqlite3'), uploadDir: join(directory, 'uploads'),
    publicUrl: 'http://127.0.0.1', jwtSecret: 'isolated-external-http-test-secret' });
  const store = new NodeStore(join(directory, 'node.sqlite3'), 'owner');
  let external: ExternalChannels | undefined;
  try {
    const { db } = app.im, now = new Date().toISOString();
    db.prepare("INSERT INTO users(id,username,display_name,owner_id,created_at,membership_status) VALUES('owner','owner','Owner','owner',?,'active')").run(now);
    db.prepare("INSERT INTO nodes(node_id,owner_id,node_name,status) VALUES('node','owner','Node','online')").run();
    db.prepare("INSERT INTO node_binding_state(node_id,owner_id,node_epoch) VALUES('node','owner',1)").run();
    db.prepare("INSERT INTO agent_profiles(agent_id,owner_id,node_id,display_name,workspace_root,created_at,updated_at) VALUES('agent','owner','node','Assistant','/assistant',?,?)").run(now, now);
    app.im.gateway.nodes.set('node', { node_id: 'node', owner_id: 'owner', node_epoch: 1, token: 'gateway-token',
      socket: { readyState: 1, send() {}, close() {} } } as unknown as Connection);
    if (personal) {
      db.prepare("INSERT INTO conversations(id,title,type,created_at) VALUES('owner-chat','PA','direct',?)").run(now);
      db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('owner-chat','owner')").run();
      db.prepare("INSERT INTO personal_agent_bindings VALUES('binding','owner','owner','agent','node',1,'owner-chat','PA','create','active',NULL,?)").run(now);
      db.prepare("INSERT INTO pa_policies(binding_id) VALUES('binding')").run();
    }
    db.prepare("INSERT INTO agent_channels VALUES('channel','owner','agent','node','feishu',1,'{\"app_id\":\"app\"}','fp',1,'{\"owner_open_id\":\"sender\"}','{}','key',1,1,?,?)").run(now, now);
    const base = await app.listen({ host: '127.0.0.1', port: 0 });
    // Only the provider and runtime are doubles; HTTP, parsing, auth, routes and persistence are real.
    let loseReceipt = true;
    const errors: unknown[] = [];
    const options = { nodeId: 'node', ownerId: 'owner', store, personalAgent: () => personal,
      relay: { ready: true, request: async () => ({ type: 'ack', payload: {} }) },
      im: async (path: string, init?: RequestInit) => {
        const result = await requestIm(base, 'gateway-token', path, init);
        if (loseReceipt && /\/(external-incoming|messages)\?/.test(path)) {
          loseReceipt = false;
          throw new Error('Response lost after IM committed');
        }
        return result;
      },
      receive: async () => {}, permission: async () => {}, onError: (error: unknown) => errors.push(error),
    };
    const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=', 'base64');
    const connection = { config: { appId: 'app', ownerOpenId: 'sender' }, send: async () => 'provider-receipt',
      thinking: async () => undefined, image: async () => ({ data: png, mediaType: 'image/png' }), updateCard: async () => {} };
    external = new ExternalChannels(join(directory, 'external.sqlite3'), options);
    external.add('agent', connection);
    const message = { messageId: 'provider-message', chatId: 'provider-chat', senderId: 'sender', isGroup: false,
      mentioned: false, time: '1000', parts: [{ type: 'text' as const, text: 'Please read this image' }, { type: 'image' as const, key: 'image' }] };
    if (personal) await expect(external.receive('agent', message)).rejects.toThrow('Response lost after IM committed');
    else {
      await external.receive('agent', message);
      await expect(external.recover()).rejects.toThrow('Response lost after IM committed');
    }
    await external.stop();
    external = new ExternalChannels(join(directory, 'external.sqlite3'), options);
    external.add('agent', connection);
    await external.recover();
    await external.receive('agent', message);
    await external.recover();
    const rows = db.prepare("SELECT id,conversation_id,content,sender_source_id,caller_idempotency_key FROM messages WHERE caller_idempotency_key=?").all('shadow:external:agent:app:provider-message');
    expect(rows).toEqual([expect.objectContaining({ content: 'Please read this image[图片]', sender_source_id: 'sender' })]);
    const saved = app.im.messaging.message(rows[0]!.id as string);
    expect(saved.attachments).toHaveLength(1);
    expect(saved.attachments[0].content_type).toBe('image/png');
    if (personal) {
      const events = app.im.personal!.observations({ node_id: 'node', owner_id: 'owner', node_epoch: 1 }, { agent_id: 'agent', binding_id: 'binding', epoch: 1 });
      expect(events.items.filter((event: { message_id: string }) => event.message_id === rows[0]!.id)).toHaveLength(1);
    }
    expect(errors.every(error => String(error).includes('Response lost after IM committed'))).toBe(true);
  } finally {
    await external?.stop();
    store.close();
    await app.close();
    await rm(directory, { recursive: true, force: true });
  }
});
