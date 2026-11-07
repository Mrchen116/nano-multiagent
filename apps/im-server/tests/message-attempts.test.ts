import Fastify from 'fastify';
import { describe, expect, it } from 'vitest';
import { fixture } from './control-fixture.js';
import { Messaging } from '../src/messaging.js';
import { assertMessageAttempt, messageAttemptPayload, registerMessageAttemptRoutes } from '../src/message-attempts.js';

describe('human message attempt lookup', () => {
  it('returns only the sender’s committed message while current membership remains', async () => {
    const {ctx, db} = fixture();
    ctx.gateway.broadcast = () => {};
    ctx.messaging = new Messaging(ctx);
    const message = ctx.messaging.insertMessage('chat', 'u1', 'user', 'saved', [], 'attempt');
    db.prepare("INSERT INTO conversation_participants(conversation_id,user_id) VALUES('chat','u2')").run();
    const app = Fastify();
    registerMessageAttemptRoutes(app, ctx);
    try {
      const url = '/im/v1/conversations/chat/message-attempts/attempt';
      expect((await app.inject({url})).json()).toMatchObject({id: message.id, content: 'saved'});
      expect((await app.inject({url, headers:{'x-user':'u2'}})).statusCode).toBe(404);
      expect((await app.inject({url:url.replace('/attempt','/missing')})).statusCode).toBe(404);
      db.prepare("DELETE FROM conversation_participants WHERE conversation_id='chat' AND user_id='u1'").run();
      expect((await app.inject({url})).statusCode).toBe(404);
    } finally { await app.close(); }
  });

  it('rejects a connected runtime principal', async () => {
    const {ctx} = fixture();
    ctx.messaging = new Messaging(ctx);
    ctx.gateway.authenticate = () => ({node_id:'n', owner_id:'o1', node_epoch:1});
    const app = Fastify();
    registerMessageAttemptRoutes(app, ctx);
    try {
      expect((await app.inject({url:'/im/v1/conversations/chat/message-attempts/attempt',headers:{authorization:'Bearer runtime'}})).statusCode).toBe(403);
    } finally { await app.close(); }
  });
});

describe('message creation key reuse', () => {
  const payload = messageAttemptPayload({content:'hello',attachments:[{url:'/im/uploads/one',file_name:'one'}]});
  const saved = {sender_user_id:'u1',sender_type:'user',caller_payload_json:payload};

  it('accepts the same sender and canonical payload regardless of object property order', () => {
    const retry = messageAttemptPayload({attachments:[{file_name:'one',url:'/im/uploads/one'}],content:'hello'});
    expect(() => assertMessageAttempt(saved, 'u1', 'user', retry)).not.toThrow();
  });

  it('treats client background as outside the snapshot identity', () => {
    // The centre freezes the background with the message, so a snapshot field that can no
    // longer change the message must not turn a retry into a conflict.
    const oldRow = JSON.stringify({attachments:[{file_name:'one',url:'/im/uploads/one'}],content:'hello',
      interaction_contexts:[{source_message_id:'card',state:{a:1}}]});
    expect(() => assertMessageAttempt({sender_user_id:'u1',sender_type:'user',caller_payload_json:oldRow}, 'u1', 'user', payload)).not.toThrow();
  });

  it.each([
    ['another sender', 'u2', payload],
    ['new content', 'u1', messageAttemptPayload({content:'changed'})],
    ['new attachments', 'u1', messageAttemptPayload({content:'hello',attachments:[]})],
  ])('rejects %s instead of returning an unrelated existing message', (_label, sender, changed) => {
    expect(() => assertMessageAttempt(saved, sender, 'user', changed)).toThrowError(expect.objectContaining({statusCode:409}));
  });
});

// Persisted before the serializer move at a34af8473 and before the background rule; a retry
// started across that deploy must still match, or every in-flight send would 409.
it('recognizes a historical attempt that also froze private background', () => {
  const payload = messageAttemptPayload({"content":"\u4e2d\u6587\ud83d\ude00\u007f\u0080","attachments":[{"file_name":"\u9644\u4ef6.txt","url":"/im/uploads/a"}]});
  const previous = "{\"attachments\":[{\"file_name\":\"\\u9644\\u4ef6.txt\",\"url\":\"/im/uploads/a\"}],\"content\":\"\\u4e2d\\u6587\ud83d\ude00\u007f\u0080\",\"interaction_contexts\":[{\"source_message_id\":\"card\",\"state\":{\"a\":{\"a\":1,\"b\":2},\"z\":\"\\u9009\\u9879\ud83d\ude00\"}}]}";
  expect(() => assertMessageAttempt({sender_user_id:'u1',sender_type:'user',caller_payload_json:previous}, 'u1', 'user', payload)).not.toThrow();
  expect(() => assertMessageAttempt({sender_user_id:'u1',sender_type:'user',caller_payload_json:previous}, 'u1', 'user',
    messageAttemptPayload({"content":"changed","attachments":[]}))).toThrowError(expect.objectContaining({statusCode:409}));
});
