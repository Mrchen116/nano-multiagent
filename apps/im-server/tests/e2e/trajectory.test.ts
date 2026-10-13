import { expect, it } from 'vitest';
import { once } from 'node:events';
import WebSocket from 'ws';
import { bind, cleanups, Frames, start } from './helpers.js';

it('pairs a shared Work reader separately from device traffic and revokes both observer ends', async () => {
  const f = await start(), device = await bind(f);
  await device.frames.send('agent.work.append', { node_id: device.node, journal_id: 'native-work', from_seq: 1,
    events: [{ seq: 1, event_id: 'register', root_agent_id: 'global', session_id: 'main-native', type: 'session_registered', observed_at: new Date().toISOString(), payload: { scope: 'global_main' } }] });
  const ticket = await f.http('POST', '/im/v1/auth/ws-ticket', {}, f.tokens.bob);
  const browser = new WebSocket(f.base.replace('http:', 'ws:') + `/im/ws/agent-trajectory?ticket=${ticket.body.ticket}&agent_id=global&session_id=main-native`, { origin: 'http://127.0.0.1:8011' });
  cleanups.push(() => browser.terminate());
  const browserFrames = new Frames(browser);
  const prepare = await device.frames.next(frame => frame.type === 'trajectory.prepare');
  expect(prepare.payload.scope).toMatchObject({ rootAgentId: 'global', sessionId: 'main-native', ownerId: 'alice' });
  const url = f.base.replace('http:', 'ws:') + `/im/ws/node-trajectory?ticket=${prepare.payload.ticket}`;
  const node = new WebSocket(url), nodeFrames = new Frames(node);
  cleanups.push(() => node.terminate());
  await once(node, 'open');
  node.send(JSON.stringify({ type: 'ready', observerId: prepare.payload.scope.observerId, version: '0.2.1-alpha.1' }));
  expect((await browserFrames.next()).type).toBe('ready');
  const reused = new WebSocket(url); cleanups.push(() => reused.terminate());
  expect((await once(reused, 'close'))[0]).toBe(1008);
  browser.send(JSON.stringify({ type: 'call', requestId: 'read', method: 'session/list', params: {}, attachmentAuthorized: true }));
  expect(await nodeFrames.next()).toEqual({ type: 'call', requestId: 'read', method: 'session/list', params: {} });
  // An observer waiting for a response cannot block the original heartbeat ACK.
  expect((await device.frames.send('node.heartbeat', { node_id: device.node })).type).toBe('ack');
  node.send(JSON.stringify({ type: 'result', observerId: prepare.payload.scope.observerId, requestId: 'read', value: { ok: true, value: { items: [] } } }));
  expect((await browserFrames.next()).requestId).toBe('read');
  browser.send(JSON.stringify({ type: 'call', requestId: 'runs', method: 'trajectory/runs', params: {} }));
  expect(await nodeFrames.next()).toEqual({ type: 'call', requestId: 'runs', method: 'trajectory/runs', params: {} });
  node.send(JSON.stringify({ type: 'result', observerId: prepare.payload.scope.observerId, requestId: 'runs', value: { ok: true, value: [] } }));
  expect(await browserFrames.next()).toMatchObject({ requestId: 'runs', value: { ok: true, value: [] } });
  browser.send(JSON.stringify({ type: 'call', requestId: 'cancel', method: 'session/cancel', params: {} }));
  expect(await browserFrames.next()).toMatchObject({ requestId: 'cancel', code: 'read_only' });
  // Shared Work visibility does not grant access to another user's private chat images.
  for (const shared of [false, true]) {
    const chat = await f.http('POST', '/im/v1/conversations', { title: 'Image provenance', type: shared ? 'group' : 'direct', participants: [{ type: 'agent', id: 'assistant' }, ...(shared ? [{ type: 'user', id: 'bob' }] : [])] }, f.tokens.alice);
    expect(chat.status, chat.body).toBe(201);
    const upload = await f.http('POST', `/im/v1/conversations/${chat.body.id}/images?file_name=proof.png`, Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAKAAAABaCAIAAACwpMoFAAABNklEQVR4nO3ZwQmAMBQFwVRjY5ZtB9qD2ILkILgZ+PdJ2OMb235N33He08f9xh2rfXg1V+C4K3DcFTjuChx3BY67AsddgeOuwHFX4LgrcNwVOO4KHHcFjrvjj4/mvj+B467AcVfguCtw3BU47gocdwWOuwLHXYHjrsBxV+C4K3DcFTjuChx37cFxV+C4K3DcFTjuChx3BY67AsddgeOuwHFX4LgrcNwVOO4KHHcFjrsCx117cNwVOO4KHHcFjrsCx12B467AcVfguCtw3BU47gocdwWOuwLHXYHjrsBx1x4cdwWOuwLHXYHjrsBxV+C4K3DcFTjuChx3BY67AsddgeOuwHFX4LgrcNy1B8ddgeOuwHFX4LgrcNwVOO4KHHcFjrsCx12B467AcVfguCtw3BU47gocdx+RTJHLcoVInQAAAABJRU5ErkJggg==', 'base64'), f.tokens.alice, { 'content-type': 'image/png', 'Idempotency-Key': 'proof' });
    expect(upload.status, upload.body).toBe(201);
    const message = await f.http('POST', `/im/v1/conversations/${chat.body.id}/messages`, { sender_user_id: 'alice', content: 'Image', attachments: [upload.body] }, f.tokens.alice);
    expect(message.status, message.body).toBe(201);
    const requestId = `image-${shared}`;
    browser.send(JSON.stringify({ type: 'call', requestId, method: 'session/attachment', params: { args: { request: { attachmentId: 'native-image' } } }, attachmentAuthorized: true }));
    expect((await nodeFrames.next()).method).toBe('trajectory/attachment-source');
    node.send(JSON.stringify({ type: 'result', observerId: prepare.payload.scope.observerId, requestId, value: { ok: true, value: { sources: [{ kind: 'chat', conversationId: chat.body.id, messageId: message.body.id, url: upload.body.url }] } } }));
    if (!shared) expect(await browserFrames.next()).toMatchObject({ type: 'error', requestId, code: 'attachment_forbidden' });
    else {
      expect(await nodeFrames.next()).toMatchObject({ type: 'call', method: 'session/attachment', requestId, attachmentAuthorized: true });
      node.send(JSON.stringify({ type: 'result', observerId: prepare.payload.scope.observerId, requestId, value: { ok: true, value: { data: 'authorized-bytes' } } }));
      expect((await browserFrames.next()).value.value.data).toBe('authorized-bytes');
    }
  }
  const browserClosed = once(browser, 'close'), nodeClosed = once(node, 'close');
  device.socket.terminate();
  expect((await browserClosed)[0]).toBe(1011);
  expect((await nodeClosed)[0]).toBe(1011);
}, 30_000);

it('rejects an execution outside the selected Work before asking the node', async () => {
  const f = await start(); await bind(f);
  const ticket = await f.http('POST', '/im/v1/auth/ws-ticket', {}, f.tokens.bob);
  const socket = new WebSocket(f.base.replace('http:', 'ws:') + `/im/ws/agent-trajectory?ticket=${ticket.body.ticket}&agent_id=global&session_id=not-this-agent`, { origin: 'http://127.0.0.1:8011' });
  cleanups.push(() => socket.terminate());
  const frames = new Frames(socket);
  expect((await frames.next()).type).toBe('failed');
  expect((await once(socket, 'close'))[0]).toBe(1008);
}, 30_000);
