import { mkdtemp, rm, stat } from 'node:fs/promises';
import http from 'node:http';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { expect, it } from 'vitest';
import {
  WeChatConnection,
  WeChatLoginCoordinator,
  assertWeChatAllowedUrl,
  chunkWeChatText,
  decryptAesEcb,
  encryptAesEcb,
  filterWeChatMarkdown,
  isValidWeChatRedirectHost,
  parseWeChatAesKey,
  parseWeChatApiJson,
  purgeWeChatChannelState,
  type WeChatInboundMessage,
} from '../src/index.js';

function startMockILinkServer(handler: (req: http.IncomingMessage, body: string, res: http.ServerResponse) => void) {
  const server = http.createServer((req, res) => {
    let body = '';
    req.setEncoding('utf8');
    req.on('data', chunk => { body += chunk; });
    req.on('end', () => handler(req, body, res));
  });
  return new Promise<{ url: string; close: () => Promise<void> }>(resolve => {
    server.listen(0, '127.0.0.1', () => {
      const addr = server.address() as { port: number };
      resolve({
        url: `http://127.0.0.1:${addr.port}`,
        close: () => new Promise<void>(done => server.close(() => done())),
      });
    });
  });
}

it('guards WeChat origins against SSRF, supports E2E loopback override, and parses lossless uint64 IDs', () => {
  expect(assertWeChatAllowedUrl('https://ilinkai.weixin.qq.com/ilink/bot/getupdates').hostname).toBe('ilinkai.weixin.qq.com');
  expect(assertWeChatAllowedUrl('https://novac2c.cdn.weixin.qq.com/c2c/download?encrypted_query_param=abc').hostname).toBe('novac2c.cdn.weixin.qq.com');
  expect(() => assertWeChatAllowedUrl('http://ilinkai.weixin.qq.com/ilink/bot/getupdates')).toThrow();
  expect(() => assertWeChatAllowedUrl('https://evil-weixin.qq.com.attacker.test/ilink')).toThrow();
  expect(() => assertWeChatAllowedUrl('https://127.0.0.1:9999/ilink')).toThrow();

  const env = { NANO_WECHAT_E2E_BASE_URL: 'http://127.0.0.1:18999' };
  expect(assertWeChatAllowedUrl('http://127.0.0.1:18999/ilink/bot/getupdates', env).port).toBe('18999');
  expect(() => assertWeChatAllowedUrl('http://127.0.0.1:19000/ilink/bot/getupdates', env)).toThrow();

  expect(isValidWeChatRedirectHost('sh-ilinkai.weixin.qq.com')).toBe(true);
  expect(isValidWeChatRedirectHost('attacker.example.com')).toBe(false);
  expect(isValidWeChatRedirectHost('127.0.0.1:18999', env)).toBe(true);

  const parsed = parseWeChatApiJson<{ message_id: string; nested: { svr_id: string; text: string } }>(
    '{"message_id":900719925474099312,"nested":{"svr_id":1844674407370955161,"text":"\\"svr_id\\":123"}}',
  );
  expect(parsed.message_id).toBe('900719925474099312');
  expect(parsed.nested.svr_id).toBe('1844674407370955161');
  expect(parsed.nested.text).toBe('"svr_id":123');
});

it('parses all three AES-128-ECB key encodings and round-trips ciphertext', () => {
  const raw = Buffer.from('0123456789abcdef0123456789abcdef', 'hex');
  const hexKey = raw.toString('hex');
  const b64Raw = raw.toString('base64');
  const b64Hex = Buffer.from(hexKey, 'ascii').toString('base64');

  expect(parseWeChatAesKey(hexKey)).toEqual(raw);
  expect(parseWeChatAesKey(b64Raw)).toEqual(raw);
  expect(parseWeChatAesKey(b64Hex)).toEqual(raw);

  const plain = Buffer.from('Hello WeChat media payload!');
  const cipher = encryptAesEcb(plain, raw);
  expect(decryptAesEcb(cipher, raw)).toEqual(plain);
});

it('filters unsupported WeChat markdown and chunks long text without breaking code fences', () => {
  const filtered = filterWeChatMarkdown(
    '##### 小标题\n这是**重点**与*中文斜体*以及*English*和~~删除线~~还有![图](https://a.com/x.png)\n```ts\nconst x = "*keep* ~~me~~";\n```',
  );
  expect(filtered).not.toContain('##### ');
  expect(filtered).toContain('**重点**');
  expect(filtered).toContain('中文斜体');
  expect(filtered).not.toContain('*中文斜体*');
  expect(filtered).toContain('*English*');
  expect(filtered).toContain('删除线');
  expect(filtered).not.toContain('~~删除线~~');
  expect(filtered).not.toContain('![图]');
  expect(filtered).toContain('const x = "*keep* ~~me~~";');

  const codeLines = Array.from({ length: 160 }, (_, idx) => `const value_${idx} = "${'x'.repeat(24)}";`).join('\n');
  const longMessage = `前导说明段落。\n\n\`\`\`ts\n${codeLines}\n\`\`\`\n\n结尾总结。`;
  const chunks = chunkWeChatText(longMessage, 800);
  expect(chunks.length).toBeGreaterThan(2);
  for (const chunk of chunks) {
    expect(Array.from(chunk).length).toBeLessThanOrEqual(800);
    const fenceCount = chunk.split('\n').filter(line => line.trim().startsWith('```')).length;
    expect(fenceCount % 2).toBe(0);
  }
});

it('drives WeChatLoginCoordinator through redirect, wrong/correct PIN, auto-expiry, binded_redirect, and cancel', async () => {
  let qrCalls = 0;
  let lastQrBody = '';
  const statusQueue: Record<string, unknown>[] = [];
  const seenStatusUrls: string[] = [];

  const twin = await startMockILinkServer((req, body, res) => {
    const url = req.url ?? '';
    if (url.startsWith('/ilink/bot/get_bot_qrcode')) {
      qrCalls++;
      lastQrBody = body;
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ qrcode: `qr_${qrCalls}`, qrcode_img_content: `https://weixin.qq.com/x/qr_${qrCalls}` }));
      return;
    }
    if (url.startsWith('/ilink/bot/get_qrcode_status')) {
      seenStatusUrls.push(url);
      const next = statusQueue.shift() ?? { status: 'wait' };
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(next));
      return;
    }
    res.writeHead(404);
    res.end();
  });

  const env = { NANO_WECHAT_E2E_BASE_URL: twin.url };
  const host = new URL(twin.url).host;
  const coordinator = new WeChatLoginCoordinator({
    env,
    pollIntervalMs: 15,
    pollTimeoutMs: 500,
    resolveLocalCredentials: channelId => channelId === 'ch_valid'
      ? { bot_token: 'reused_tok', bot_id: 'bot_reused', owner_user_id: 'wx_reused', base_url: twin.url, revoked: false }
      : channelId === 'ch_revoked'
        ? { bot_token: 'dead_tok', bot_id: 'bot_dead', owner_user_id: 'wx_dead', base_url: twin.url, revoked: true }
        : undefined,
    listLocalTokens: () => ['reused_tok'],
  });

  try {
    // 1. Scan -> valid IDC redirect -> PIN required -> wrong PIN -> right PIN -> confirmed
    statusQueue.push(
      { status: 'scaned' },
      { status: 'scaned_but_redirect', redirect_host: host },
      { status: 'need_verifycode' },
    );
    const started = await coordinator.handle({ action: 'start', agent_id: 'agent-1' });
    expect(started.state).toBe('waiting_scan');
    expect(started.qr_svg).toContain('<svg');

    await new Promise(r => setTimeout(r, 90));
    const needPin = await coordinator.handle({ action: 'status', agent_id: 'agent-1', setup_id: started.setup_id! });
    expect(needPin.state).toBe('need_verify_code');
    expect(needPin.error_code).toBeUndefined();

    statusQueue.push({ status: 'confirmed_but_need_verifycode' });
    const wrongPin = await coordinator.handle({ action: 'verify_code', agent_id: 'agent-1', setup_id: started.setup_id!, code: '000000' });
    expect(wrongPin.state).toBe('need_verify_code');
    expect(wrongPin.error_code).toBe('wrong_verify_code');
    expect(seenStatusUrls.some(u => u.includes('verify_code=000000'))).toBe(true);

    statusQueue.push({
      status: 'confirmed',
      bot_token: 'fresh_token_99',
      ilink_bot_id: 'wxbot_99',
      ilink_user_id: 'wxid_owner_99',
      baseurl: twin.url,
    });
    const confirmed = await coordinator.handle({ action: 'verify_code', agent_id: 'agent-1', setup_id: started.setup_id!, code: '482916' });
    expect(confirmed.state).toBe('confirmed');
    expect(confirmed.binding).toEqual({
      bot_token: 'fresh_token_99',
      bot_id: 'wxbot_99',
      owner_user_id: 'wxid_owner_99',
      base_url: twin.url,
    });

    // 2. Reject SSRF redirect_host
    statusQueue.push({ status: 'scaned_but_redirect', redirect_host: 'evil.attacker.invalid' });
    const ssrf = await coordinator.handle({ action: 'start', agent_id: 'agent-1' });
    await new Promise(r => setTimeout(r, 50));
    const ssrfStatus = await coordinator.handle({ action: 'status', agent_id: 'agent-1', setup_id: ssrf.setup_id! });
    expect(ssrfStatus.state).toBe('failed');
    expect(ssrfStatus.error_code).toBe('invalid_redirect_host');

    // 3. binded_redirect with valid local token reuses credentials; with revoked token restarts QR with empty local_token_list
    statusQueue.push({ status: 'binded_redirect' });
    const rebindValid = await coordinator.handle({ action: 'start', agent_id: 'agent-1', editing_channel_id: 'ch_valid' });
    await new Promise(r => setTimeout(r, 50));
    const rebindValidStatus = await coordinator.handle({ action: 'status', agent_id: 'agent-1', setup_id: rebindValid.setup_id! });
    expect(rebindValidStatus.state).toBe('confirmed');
    expect(rebindValidStatus.binding?.bot_token).toBe('reused_tok');

    statusQueue.push({ status: 'binded_redirect' }, { status: 'wait' });
    const rebindRevoked = await coordinator.handle({ action: 'start', agent_id: 'agent-1', editing_channel_id: 'ch_revoked' });
    await new Promise(r => setTimeout(r, 60));
    const rebindRevokedStatus = await coordinator.handle({ action: 'status', agent_id: 'agent-1', setup_id: rebindRevoked.setup_id! });
    expect(rebindRevokedStatus.state).toBe('waiting_scan');
    expect(JSON.parse(lastQrBody).local_token_list).toEqual([]);
    await coordinator.handle({ action: 'cancel', agent_id: 'agent-1', setup_id: rebindRevoked.setup_id! });

    // 4. Auto-renew expired up to 3 times, then surface expired
    statusQueue.push({ status: 'expired' }, { status: 'expired' }, { status: 'expired' }, { status: 'expired' });
    const exp = await coordinator.handle({ action: 'start', agent_id: 'agent-1' });
    await new Promise(r => setTimeout(r, 120));
    const expStatus = await coordinator.handle({ action: 'status', agent_id: 'agent-1', setup_id: exp.setup_id! });
    expect(expStatus.state).toBe('expired');
  } finally {
    await coordinator.stop();
    await twin.close();
  }
});

it('enforces single-poller stop-before-start, owner-only gate, typing indicator, -14 revocation stop, and state purge', async () => {
  const stateDir = await mkdtemp(join(tmpdir(), 'nano-wechat-state-'));
  let activePolls = 0;
  let maxConcurrentPolls = 0;
  const sentMessages: { to: string; text: string }[] = [];
  const typingEvents: number[] = [];
  let releasePoll: ((payload: Record<string, unknown>) => void) | undefined;
  const queuedUpdates: Record<string, unknown>[] = [];

  const twin = await startMockILinkServer((req, body, res) => {
    const url = req.url ?? '';
    if (url === '/ilink/bot/getupdates') {
      activePolls++;
      maxConcurrentPolls = Math.max(maxConcurrentPolls, activePolls);
      const done = () => { if (activePolls > 0) activePolls--; };
      req.on('close', done);
      if (queuedUpdates.length > 0) {
        const next = queuedUpdates.shift()!;
        done();
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(next));
        return;
      }
      releasePoll = payload => {
        done();
        if (!res.writableEnded) {
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify(payload));
        }
      };
      return;
    }
    if (url === '/ilink/bot/sendmessage') {
      const parsed = JSON.parse(body) as { msg: { to_user_id: string; item_list?: { text_item?: { text?: string } }[] } };
      sentMessages.push({
        to: parsed.msg.to_user_id,
        text: parsed.msg.item_list?.[0]?.text_item?.text ?? '',
      });
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end('{"ret":0,"message_id":900719925474099999}');
      return;
    }
    if (url === '/ilink/bot/getconfig') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ ret: 0, typing_ticket: 'ticket_abc' }));
      return;
    }
    if (url === '/ilink/bot/sendtyping') {
      const parsed = JSON.parse(body) as { status: number };
      typingEvents.push(parsed.status);
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ ret: 0 }));
      return;
    }
    res.writeHead(404);
    res.end();
  });

  const env = { NANO_WECHAT_E2E_BASE_URL: twin.url };
  const received: WeChatInboundMessage[] = [];
  const statuses: unknown[] = [];

  queuedUpdates.push({
    ret: 0,
    get_updates_buf: 'cursor_1',
    msgs: [
      {
        message_id: '1001',
        from_user_id: 'stranger_wxid',
        message_type: 1,
        create_time_ms: 1700000000000,
        context_token: 'ctx_stranger',
        item_list: [{ type: 1, text_item: { text: '我是陌生人' } }],
      },
      {
        message_id: '1002',
        from_user_id: 'stranger_wxid',
        message_type: 1,
        create_time_ms: 1700000001000,
        context_token: 'ctx_stranger',
        item_list: [{ type: 1, text_item: { text: '第二条陌生人消息（应被限频）' } }],
      },
      {
        message_id: '1003',
        from_user_id: 'owner_wxid',
        message_type: 1,
        create_time_ms: 1700000002000,
        context_token: 'ctx_owner_1',
        item_list: [{ type: 1, text_item: { text: '你好助手' } }],
      },
    ],
  });

  const makeConn = (credentialRevision = 1) => new WeChatConnection({
    channelId: 'ch_wx_1',
    botId: 'wxbot_1',
    botToken: 'tok_1',
    ownerUserId: 'owner_wxid',
    baseUrl: twin.url,
    stateRoot: stateDir,
    credentialRevision,
    env,
    typingIntervalMs: 30,
  }, {
    receive: async msg => { received.push(msg); },
    status: s => { statuses.push(s); },
    onError: () => {},
  });

  const first = makeConn(1);
  try {
    await first.start();
    await new Promise(r => setTimeout(r, 80));

    // Stranger got rate-limited once and never entered received
    expect(received).toHaveLength(1);
    expect(received[0]?.senderId).toBe('owner_wxid');
    expect(received[0]?.parts).toEqual([{ type: 'text', text: '你好助手' }]);
    expect(sentMessages.filter(m => m.to === 'stranger_wxid')).toHaveLength(1);

    // File permissions on state SQLite are 0600
    const dbStat = await stat(join(stateDir, 'ch_wx_1.sqlite3'));
    expect(dbStat.mode & 0o777).toBe(0o600);

    // Typing indicator lifecycle: start -> renew -> cancel
    await first.setTyping('owner_wxid', true);
    await new Promise(r => setTimeout(r, 45));
    await first.setTyping('owner_wxid', false);
    expect(typingEvents[0]).toBe(1);
    expect(typingEvents.at(-1)).toBe(2);

    // Outbound send uses stored context_token
    const msgId = await first.send('owner_wxid', '收到，**主人**！', 'op-1');
    expect(msgId).toBe('900719925474099999');
    expect(sentMessages.at(-1)).toEqual({ to: 'owner_wxid', text: '收到，**主人**！' });

    // Stop first poller while getupdates is hanging, then start second: maxConcurrentPolls stays 1!
    await first.stop();
    expect(activePolls).toBe(0);

    const second = makeConn(1);
    await second.start();
    await new Promise(r => setTimeout(r, 40));
    expect(maxConcurrentPolls).toBe(1);

    // Trigger -14 token revocation: stops immediately without looping
    releasePoll?.({ ret: -14, errcode: -14, errmsg: 'session timeout' });
    await new Promise(r => setTimeout(r, 60));
    expect(activePolls).toBe(0);
    expect(statuses).toContainEqual(expect.objectContaining({
      state: 'failed',
      code: 'wechat_token_revoked',
    }));
    await second.stop();

    // purgeWeChatChannelState deletes sqlite3 + wal/shm
    await purgeWeChatChannelState(stateDir, 'ch_wx_1');
    await expect(stat(join(stateDir, 'ch_wx_1.sqlite3'))).rejects.toThrow();
  } finally {
    await first.stop();
    await twin.close();
    await rm(stateDir, { recursive: true, force: true });
  }
});
