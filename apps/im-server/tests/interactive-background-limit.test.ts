import { describe, expect, it, vi } from 'vitest';

import { fixture } from './control-fixture.js';
import { Messaging } from '../src/messaging.js';
import { all, one } from '../src/context.js';
import { MAX_INTERACTION_BACKGROUND_BYTES } from '../src/interaction-background.js';

const interactive = {format:'openui', catalog_version:'nano-iui-1', source:`$note = ""
root = Form([TextArea($note, "备注"), Button("继续", @SendToChat("继续"))])`};
const human = {id:'u1', username:'alice'};
const tooLarge = {statusCode:422, detail:{code:'interaction_background_too_large'}};

function setup(count: number, value = 'small') {
  const {db, ctx} = fixture(); ctx.gateway.broadcast = vi.fn(); ctx.gateway.send = () => true;
  const messaging = new Messaging(ctx); ctx.messaging = messaging;
  db.prepare("UPDATE conversations SET type='direct' WHERE id='chat'").run();
  const save = (id: string, note: string) => messaging.interactions.writeDraft({
    headers:{'x-user':'u1'}, params:{conversation_id:'chat', message_id:id}, query:{},
    body:{expected_draft_revision:one(db,'SELECT draft_revision FROM interaction_drafts WHERE source_message_id=?',id)?.draft_revision ?? 0, state:{'$note':note}},
  } as any);
  const cards = Array.from({length:count}, (_, index) => {
    const card = messaging.insertMessage('chat','a1','agent',`探索 ${index + 1}`,[],null,'completed',{interactive});
    save(card.id, value);
    return card.id;
  });
  const send = (key: string, extra: Record<string, unknown> = {}) => messaging.sendMessage({
    headers:{'x-user':'u1','idempotency-key':key}, params:{conversation_id:'chat'}, query:{},
    body:{sender_user_id:'u1',content:'保留正文',...extra},
  } as any);
  const relays = () => all(db,'SELECT payload_json FROM relay_tasks ORDER BY rowid').map(row => JSON.parse(row.payload_json));
  return {db, messaging, cards, save, send, relays};
}

describe('ordinary-send background group budget', () => {
  it('rejects the whole oversized group without creating or consuming a message, then recovers after shrinking', async () => {
    const {db, messaging, cards, save, send, relays} = setup(3, 'x'.repeat(12000));
    // Each saved state is below 16 KiB; the model-visible fields repeat its value.
    const drafts = all(db,'SELECT * FROM interaction_drafts ORDER BY rowid');
    expect(drafts.every(row => Buffer.byteLength(row.state_json,'utf8') < 16384)).toBe(true);
    const messages = all(db,'SELECT * FROM messages ORDER BY rowid');
    const timezone = one(db,"SELECT timezone FROM users WHERE id='u1'")?.timezone;
    await expect(send('oversized', {timezone:'Asia/Shanghai'})).rejects.toMatchObject(tooLarge);
    expect(all(db,'SELECT * FROM messages ORDER BY rowid')).toEqual(messages);
    expect(all(db,'SELECT * FROM interaction_drafts ORDER BY rowid')).toEqual(drafts);
    expect(all(db,'SELECT * FROM interaction_background_discards')).toEqual([]);
    expect(one(db,"SELECT timezone FROM users WHERE id='u1'")?.timezone).toBe(timezone);
    expect(relays()).toEqual([]);
    expect(() => messaging.background.pending(human,'chat')).toThrow();

    for (const id of cards) save(id, '缩短后的内容');
    await send('after-shrinking');
    expect(relays()).toHaveLength(1);
    expect(relays()[0].metadata.interaction_contexts.map((item: any) => item.source_message_id)).toEqual(cards);
    expect(relays()[0].metadata.interaction_contexts.every((item: any) => item.state.$note === '缩短后的内容')).toBe(true);
    expect(messaging.background.pending(human,'chat')).toEqual([]);
  });

  it('does not truncate to a fixed number of small cards', async () => {
    const {cards, send, relays} = setup(5);
    await send('five-cards');
    expect(relays()[0].metadata.interaction_contexts.map((item: any) => item.source_message_id)).toEqual(cards);
  });

  it.each([0,1])('uses the final JSON array boundary including punctuation (extra bytes: %s)', async extra => {
    const {messaging, send, relays} = setup(1);
    const base = messaging.background.pending(human,'chat')[0]!;
    const context = {...base, state:{padding:''}, fields:[]};
    const overhead = Buffer.byteLength(JSON.stringify([context]),'utf8');
    // Isolate aggregate serialization from the separate per-card input-state validator.
    context.state.padding = 'x'.repeat(MAX_INTERACTION_BACKGROUND_BYTES - overhead + extra);
    vi.spyOn(messaging.interactions,'background').mockReturnValue(context);
    if (extra) {
      await expect(send('over-boundary')).rejects.toMatchObject(tooLarge);
      expect(relays()).toEqual([]);
    } else {
      await send('at-boundary');
      expect(Buffer.byteLength(JSON.stringify(relays()[0].metadata.interaction_contexts),'utf8')).toBe(MAX_INTERACTION_BACKGROUND_BYTES);
    }
  });

  it.each(['中','"\\\n'])('counts UTF-8 and JSON escaping instead of raw character length (%j)', async symbol => {
    const {messaging, send, relays} = setup(1);
    const base = messaging.background.pending(human,'chat')[0]!;
    const context = {...base, state:{padding:symbol.repeat(symbol.length === 1 ? 22000 : 16000)}, fields:[]};
    expect(context.state.padding.length).toBeLessThan(MAX_INTERACTION_BACKGROUND_BYTES);
    expect(Buffer.byteLength(JSON.stringify([context]),'utf8')).toBeGreaterThan(MAX_INTERACTION_BACKGROUND_BYTES);
    vi.spyOn(messaging.interactions,'background').mockReturnValue(context);
    await expect(send('encoded-overflow')).rejects.toMatchObject(tooLarge);
    expect(relays()).toEqual([]);
  });

  it('restores an existing send before considering newer oversized drafts', async () => {
    const {db, messaging, cards, save, send, relays} = setup(3);
    const first = await send('original');
    const frozen = relays();
    for (const id of cards) save(id, 'x'.repeat(12000));
    db.prepare('UPDATE interaction_drafts SET updated_at=?').run(new Date(Date.parse(first.created_at) + 10).toISOString());
    expect(() => messaging.background.pending(human,'chat')).toThrow();
    expect((await send('original')).id).toBe(first.id);
    expect(relays()).toEqual(frozen);
    expect(all(db,"SELECT * FROM messages WHERE sender_type='user'")).toHaveLength(1);
  });

  it('keeps explicit submission independent of the ordinary group limit and consumes the pending window', async () => {
    const {messaging, cards, send, relays} = setup(3, 'x'.repeat(12000));
    expect(() => messaging.background.pending(human,'chat')).toThrow();
    const message = await send('explicit', {interaction_reply:{source_message_id:cards[0],state:{'$note':'明确提交'}}});
    expect(message.interaction_reply?.source_message_id).toBe(cards[0]);
    expect(relays()[0].metadata.interaction_contexts).toBeUndefined();
    expect(messaging.background.pending(human,'chat')).toEqual([]);
  });
});
