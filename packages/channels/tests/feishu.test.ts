import { expect, it } from 'vitest';
import { parseFeishuMessage } from '../src/feishu.js';

it('preserves post text/image order and only treats the actual bot identity as a mention', () => {
  const event = { sender: { sender_type: 'user', sender_id: { open_id: 'person' } }, message: { message_id: 'm', chat_id: 'chat', chat_type: 'group', message_type: 'post', create_time: '1000',
    mentions: [{ key: '@_user_1', name: 'All', id: { open_id: 'all' } }, { key: '@_user_2', name: 'Bot', id: { open_id: 'bot' } }],
    content: JSON.stringify({ zh_cn: { title: 'Diagram', content: [[{ tag: 'text', text: 'Before @_user_1' }, { tag: 'img', image_key: 'image' }, { tag: 'text', text: 'After' }]] } }) } };
  expect(parseFeishuMessage(event, 'bot')).toMatchObject({ mentioned: true, senderId: 'person', parts: [{ type: 'text', text: 'Diagram\n' }, { type: 'text', text: 'Before @All' }, { type: 'image', key: 'image' }, { type: 'text', text: 'After' }] });
  expect(parseFeishuMessage({ ...event, message: { ...event.message, mentions: event.message.mentions.slice(0, 1) } }, 'bot')?.mentioned).toBe(false);
  expect(parseFeishuMessage({ ...event, sender: { sender_type: 'app', sender_id: { open_id: 'bot' } } }, 'bot')).toBeUndefined();
});

it('uploads data images once while leaving code and remote links inert', async () => {
  const { renderFeishuImages } = await import('../src/feishu.js');
  let uploads = 0; const data = 'data:image/png;base64,aW1hZ2U=';
  const result = await renderFeishuImages(`![one](${data}) ![two](${data})\n\`![code](${data})\`\n![remote](https://example.com/image.png)`, async bytes => { expect(bytes.toString()).toBe('image'); uploads++; return 'img_native'; });
  expect(uploads).toBe(1);
  expect(result).toBe(`![one](img_native) ![two](img_native)\n\`![code](${data})\`\n[remote](https://example.com/image.png)`);
});
