import http from 'node:http';
import { randomUUID } from 'node:crypto';

function extractText(content) {
  if (typeof content === 'string') return content;
  if (Array.isArray(content)) {
    return content
      .map((part) => {
        if (typeof part === 'string') return part;
        if (part && typeof part.text === 'string') return part.text;
        return '';
      })
      .join('\n');
  }
  return '';
}

function sendSseText(res, model, text) {
  const id = `chatcmpl-${randomUUID().slice(0, 12)}`;
  res.writeHead(200, {
    'Content-Type': 'text/event-stream; charset=utf-8',
    'Cache-Control': 'no-cache',
    Connection: 'keep-alive',
  });
  res.write(
    `data: ${JSON.stringify({
      id,
      object: 'chat.completion.chunk',
      created: Math.floor(Date.now() / 1000),
      model,
      choices: [{ index: 0, delta: { role: 'assistant', content: text }, finish_reason: null }],
    })}\n\n`,
  );
  res.write(
    `data: ${JSON.stringify({
      id,
      object: 'chat.completion.chunk',
      created: Math.floor(Date.now() / 1000),
      model,
      choices: [{ index: 0, delta: {}, finish_reason: 'stop' }],
      usage: { prompt_tokens: 64, completion_tokens: 16, total_tokens: 80 },
    })}\n\n`,
  );
  res.end('data: [DONE]\n\n');
}

function sendSseToolCalls(res, model, calls) {
  const id = `chatcmpl-${randomUUID().slice(0, 12)}`;
  res.writeHead(200, {
    'Content-Type': 'text/event-stream; charset=utf-8',
    'Cache-Control': 'no-cache',
    Connection: 'keep-alive',
  });
  res.write(
    `data: ${JSON.stringify({
      id,
      object: 'chat.completion.chunk',
      created: Math.floor(Date.now() / 1000),
      model,
      choices: [
        {
          index: 0,
          delta: {
            role: 'assistant',
            tool_calls: calls.map((c, idx) => ({
              index: idx,
              id: c.id ?? `call_${randomUUID().replace(/-/g, '').slice(0, 12)}`,
              type: 'function',
              function: {
                name: c.name,
                arguments: typeof c.arguments === 'string' ? c.arguments : JSON.stringify(c.arguments),
              },
            })),
          },
          finish_reason: null,
        },
      ],
    })}\n\n`,
  );
  res.write(
    `data: ${JSON.stringify({
      id,
      object: 'chat.completion.chunk',
      created: Math.floor(Date.now() / 1000),
      model,
      choices: [{ index: 0, delta: {}, finish_reason: 'tool_calls' }],
      usage: { prompt_tokens: 120, completion_tokens: 32, total_tokens: 152 },
    })}\n\n`,
  );
  res.end('data: [DONE]\n\n');
}

function findLatestUnreadTarget(messages) {
  for (let i = messages.length - 1; i >= 0; i--) {
    const m = messages[i];
    if (m.role !== 'user') continue;
    const text = extractText(m.content);
    const lines = text.trim().split('\n');
    for (let j = lines.length - 1; j >= 0; j--) {
      const line = lines[j].trim();
      if (!line.startsWith('{')) continue;
      try {
        const parsed = JSON.parse(line);
        if (Array.isArray(parsed.sources) && parsed.sources.length > 0 && parsed.sources[0].target) {
          return parsed.sources[0].target;
        }
      } catch {}
    }
  }
  return null;
}

function parseLatestInboxRead(messages) {
  let inboxToolIdx = -1;
  let inboxPayload = null;
  for (let i = messages.length - 1; i >= 0; i--) {
    const m = messages[i];
    if (m.role === 'tool') {
      const txt = extractText(m.content).trim();
      const firstLine = txt.split('\n').find((line) => line.trim().startsWith('{')) ?? txt;
      try {
        const parsed = JSON.parse(firstLine);
        if (parsed && typeof parsed.target === 'string' && Array.isArray(parsed.messages)) {
          inboxToolIdx = i;
          inboxPayload = parsed;
          break;
        }
      } catch {}
    }
  }
  if (!inboxPayload) return null;

  const subsequentCalls = [];
  for (let i = inboxToolIdx + 1; i < messages.length; i++) {
    const m = messages[i];
    if (m.role === 'assistant' && Array.isArray(m.tool_calls)) {
      for (const tc of m.tool_calls) {
        subsequentCalls.push(tc.function?.name ?? tc.name ?? '');
      }
    }
  }
  return { inboxPayload, inboxToolIdx, subsequentCalls };
}

export async function startSseLlmServer({ host = '127.0.0.1', port = 0, bigCommand } = {}) {
  const defaultBigCmd =
    bigCommand ??
    (process.platform === 'win32'
      ? `powershell.exe -NoProfile -Command "[Console]::Write('WINBIG' * 3100000)"`
      : `python3 -c "import sys; sys.stdout.write('WINBIG' * 3100000)"`);

  const requests = [];
  const server = http.createServer(async (req, res) => {
    if (req.method === 'GET' && req.url === '/health') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ ok: true, requests: requests.length }));
      return;
    }
    let raw = '';
    for await (const chunk of req) raw += chunk;
    let body = {};
    try {
      body = JSON.parse(raw);
    } catch {
      res.writeHead(400);
      res.end('invalid json');
      return;
    }

    const model = body.model ?? 'crewden-qa-model';
    const messages = Array.isArray(body.messages) ? body.messages : [];
    const tools = Array.isArray(body.tools) ? body.tools : [];
    const toolNames = new Set(tools.map((t) => t?.function?.name ?? t?.name).filter(Boolean));
    const systemText = messages
      .filter((m) => m.role === 'system' || m.role === 'developer')
      .map((m) => extractText(m.content))
      .join('\n');

    requests.push({
      url: req.url,
      model,
      messageCount: messages.length,
      toolCount: toolNames.size,
      roles: messages.map((m) => m.role),
      lastMsgPreview: JSON.stringify(messages.at(-1)).slice(0, 400),
      sysPreview: systemText.slice(0, 160),
    });

    // 1. Auto-mode tool approval classifier (<block>no</block>) or DSH JSON policy
    if (systemText.includes('<block>') || systemText.includes('security policy classifier')) {
      return sendSseText(res, model, '<block>no</block><reason>Safe local QA operation</reason>');
    }
    if (systemText.startsWith('REVIEW_POLICY')) {
      return sendSseText(res, model, '{"risk":"low","decision":"allow","reason":"Safe local QA operation"}');
    }

    // 2. Personal Assistant input/action review JSON contract
    if (systemText.includes('Return one JSON object only')) {
      if (systemText.includes('"decisions":[')) {
        const allUserText = messages.map((m) => extractText(m.content)).join('\n');
        const itemMatches = [...allUserText.matchAll(/"item"\s*:\s*(\d+)/g)].map((m) => Number(m[1]));
        const uniqueItems = [...new Set(itemMatches)].sort((a, b) => a - b);
        const items = uniqueItems.length > 0 ? uniqueItems : [1];
        return sendSseText(
          res,
          model,
          JSON.stringify({
            decisions: items.map((item) => ({ item, decision: 'allow', reason: 'Ordinary user conversation' })),
          }),
        );
      }
      return sendSseText(res, model, '{"decision":"allow","reason":"Authorized owner conversation"}');
    }

    // 3. Model connection probe or non-tool completion
    if (!toolNames.has('inbox') && !toolNames.has('send_message')) {
      return sendSseText(res, model, 'READY');
    }

    // 4. Global Personal Assistant loop
    const lastMsg = messages.at(-1);
    if (lastMsg?.role === 'user' && toolNames.has('inbox')) {
      const target = findLatestUnreadTarget(messages);
      if (target) {
        return sendSseToolCalls(res, model, [{ name: 'inbox', arguments: { action: 'read', target } }]);
      }
    }

    const latestRead = parseLatestInboxRead(messages);
    if (latestRead) {
      const { inboxPayload, subsequentCalls } = latestRead;
      const target = inboxPayload.target;
      const lastHumanMsg = [...(inboxPayload.messages ?? [])]
        .reverse()
        .find((m) => m.sender_type === 'user' || m.sender?.type === 'user');
      const promptText = extractText(lastHumanMsg?.content);

      if (subsequentCalls.includes('send_message')) {
        return sendSseText(res, model, 'Completed.');
      }

      if (promptText.includes('BIG_TRAJECTORY_TEST')) {
        if (!subsequentCalls.includes('read')) {
          const scriptPath = process.platform === 'win32' ? 'scripts/deploy.bat' : 'scripts/deploy.sh';
          return sendSseToolCalls(res, model, [
            { name: 'read', arguments: { file_path: 'reports/win-summary.md' } },
            { name: 'read', arguments: { file_path: scriptPath } },
          ]);
        }
        if (!subsequentCalls.includes('bash')) {
          return sendSseToolCalls(res, model, [{ name: 'bash', arguments: { command: defaultBigCmd } }]);
        }
        return sendSseToolCalls(res, model, [
          { name: 'send_message', arguments: { target, text: '已完成Windows本地轨迹验证' } },
        ]);
      }

      const addMatch = promptText.match(/(\d+)\s*\+\s*(\d+)/);
      const replyText = addMatch ? String(Number(addMatch[1]) + Number(addMatch[2])) : '42';
      return sendSseToolCalls(res, model, [{ name: 'send_message', arguments: { target, text: replyText } }]);
    }

    return sendSseText(res, model, 'Done.');
  });

  await new Promise((r) => server.listen(port, host, r));
  const actualPort = server.address().port;
  return {
    port: actualPort,
    baseUrl: `http://${host === '0.0.0.0' ? '127.0.0.1' : host}:${actualPort}/v1`,
    requests,
    close: () => new Promise((r) => server.close(() => r())),
  };
}
