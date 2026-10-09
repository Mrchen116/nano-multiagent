import { createHash } from 'node:crypto';
import { Client, WSClient, EventDispatcher } from '@larksuiteoapi/node-sdk';

export interface FeishuConfiguration { appId: string; appSecret: string; botOpenId: string; ownerOpenId?: string; domain?: string }
export interface FeishuMessage {
  messageId: string; chatId: string; senderId: string; isGroup: boolean; mentioned: boolean; time: string;
  parts: ({ type: 'text'; text: string } | { type: 'image'; key: string })[];
}
interface MessageEvent {
  sender: { sender_type: string; sender_id?: { open_id?: string } };
  message: { message_id: string; chat_id: string; chat_type: string; message_type: string; create_time: string; content: string;
    mentions?: { key: string; name: string; id: { open_id?: string } }[] };
}

/** Keep platform identities and content order intact; @all never means @this-bot. */
export function parseFeishuMessage(event: MessageEvent, botId: string): FeishuMessage | undefined {
  const senderId = event.sender.sender_id?.open_id;
  if (!senderId || senderId === botId || event.sender.sender_type !== 'user') return;
  const message = event.message; const mentions = message.mentions ?? [];
  const replace = (text: string) => mentions.reduce((text, mention) => text.split(mention.key).join(`@${mention.name}`), text);
  const body = JSON.parse(message.content) as Record<string, unknown>;
  const parts: FeishuMessage['parts'] = [];
  if (message.message_type === 'text') parts.push({ type: 'text', text: replace(String(body.text ?? '')) });
  if (message.message_type === 'image' && typeof body.image_key === 'string') parts.push({ type: 'image', key: body.image_key });
  if (message.message_type === 'post') {
    const post = (body.content ? body : body.zh_cn ?? body.en_us ?? Object.values(body)[0]) as { title?: string; content?: Record<string, unknown>[][] };
    if (post.title) parts.push({ type: 'text', text: `${post.title}\n` });
    for (const [index, line] of (post.content ?? []).entries()) {
      if (index) parts.push({ type: 'text', text: '\n' });
      for (const item of line) {
        if (item.tag === 'img' && typeof item.image_key === 'string') parts.push({ type: 'image', key: item.image_key });
        else if (item.tag === 'at') parts.push({ type: 'text', text: `@${item.user_name ?? mentions.find(m => m.id.open_id === item.user_id)?.name ?? item.user_id}` });
        else if (typeof item.text === 'string') {
          let text = replace(item.text);
          if (item.tag === 'a' && typeof item.href === 'string') text = `[${text}](${item.href})`;
          if (item.tag === 'code_block') text = `\n\`\`\`${item.language ?? ''}\n${text}\n\`\`\`\n`;
          for (const style of Array.isArray(item.style) ? item.style : []) {
            if (style === 'bold') text = `**${text}**`;
            if (style === 'italic') text = `*${text}*`;
            if (style === 'lineThrough') text = `~~${text}~~`;
          }
          parts.push({ type: 'text', text });
        }
      }
    }
  }
  if (!parts.length) return;
  return { messageId: message.message_id, chatId: message.chat_id, senderId, isGroup: message.chat_type === 'group',
    mentioned: mentions.some(mention => mention.id.open_id === botId), time: message.create_time, parts };
}

/** Official SDK transport; persistence, authorization, and retry decisions belong to the node. */
export class FeishuConnection {
  private readonly client: Client;
  private readonly socket: WSClient;
  private readonly dispatcher: EventDispatcher;
  constructor(readonly config: FeishuConfiguration, private readonly options: {
    receive(message: FeishuMessage): Promise<void>;
    card?(event: unknown): Promise<unknown>;
    status?(state: string): void;
    onError(error: Error): void;
  }) {
    // SDK error objects may include HTTP credentials. Only bounded product errors leave this adapter.
    const logger = { error: () => options.onError(new Error('Feishu SDK transport error')), warn() {}, info() {}, debug() {}, trace() {} };
    const common = { appId: config.appId, appSecret: config.appSecret, domain: config.domain ?? 'https://open.feishu.cn', logger };
    this.client = new Client(common);
    this.dispatcher = new EventDispatcher({ logger });
    this.socket = new WSClient({ ...common, handshakeTimeoutMs: 10000,
      onReady: () => options.status?.('ready'), onReconnected: () => options.status?.('ready'),
      onReconnecting: () => options.status?.('reconnecting'), onError: () => options.status?.('failed') });
  }
  async start(): Promise<void> {
    const response = await this.call(() => this.client.request({ method: 'GET', url: '/open-apis/bot/v3/info' })) as { code?: number; bot?: { open_id?: string } };
    check(response);
    if (response.bot?.open_id !== this.config.botOpenId) throw new Error('Feishu configured bot identity does not match authenticated app');
    await this.socket.start({ eventDispatcher: this.dispatcher.register({
      'im.message.receive_v1': async event => {
        const message = parseFeishuMessage(event, this.config.botOpenId);
        if (message) await this.options.receive(message);
      },
      'card.action.trigger': async (event: unknown) => this.options.card?.(event),
    }) });
  }
  get state() { return this.socket.getConnectionStatus().state; }
  async send(chatId: string, text: string, operationId: string, card?: Record<string, unknown>): Promise<string> {
    const result = await this.call(() => this.client.im.v1.message.create({ params: { receive_id_type: 'chat_id' }, data: {
      receive_id: chatId, msg_type: card ? 'interactive' : 'post',
      content: JSON.stringify(card ?? { zh_cn: { title: '', content: [[{ tag: 'md', text }]] } }),
      uuid: createHash('sha256').update(operationId).digest('hex').slice(0, 32),
    } }));
    check(result); if (!result.data?.message_id) throw new Error('Feishu returned no message identity');
    return result.data.message_id;
  }
  async updateCard(messageId: string, card: Record<string, unknown>): Promise<void> {
    check(await this.call(() => this.client.im.v1.message.patch({ path: { message_id: messageId }, data: { content: JSON.stringify(card) } })));
  }
  async thinking(messageId: string, reactionId?: string): Promise<string | undefined> {
    if (reactionId) { check(await this.call(() => this.client.im.v1.messageReaction.delete({ path: { message_id: messageId, reaction_id: reactionId } }))); return; }
    const result = await this.call(() => this.client.im.v1.messageReaction.create({ path: { message_id: messageId }, data: { reaction_type: { emoji_type: 'THINKING' } } }));
    check(result); return result.data?.reaction_id;
  }
  async image(messageId: string, key: string): Promise<{ data: Buffer; mediaType: string }> {
    const result = await this.call(() => this.client.im.v1.messageResource.get({ path: { message_id: messageId, file_key: key }, params: { type: 'image' } }));
    const chunks: Buffer[] = []; for await (const chunk of result.getReadableStream()) chunks.push(Buffer.from(chunk));
    return { data: Buffer.concat(chunks), mediaType: String(result.headers['content-type'] ?? 'image/png').split(';')[0]! };
  }
  private async call<T>(operation: () => Promise<T>): Promise<T> {
    try { return await operation(); } catch { throw new Error('Feishu request failed; remote outcome may be unknown'); }
  }
  stop(): void { this.socket.close({ force: true }); this.options.status?.('stopped'); }
}
function check(result: { code?: number }): void { if (result.code) throw new Error(`Feishu API rejected request (code ${result.code})`); }
