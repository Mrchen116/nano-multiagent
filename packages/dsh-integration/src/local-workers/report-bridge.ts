import { createServer, createConnection } from 'node:net';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createInterface } from 'node:readline';
import { randomUUID } from 'node:crypto';

/** Bind one stdio MCP server to one worker's parent via a private local socket. */
export async function workerReportBridge(report: (id: string, message: string) => Promise<void>) {
  const dir = await mkdtemp(join(tmpdir(), 'nano-w-'));
  const path = join(dir, 'report.sock');
  const server = createServer((socket) => {
    socket.on('error', () => {});
    const lines = createInterface({ input: socket });
    lines.once('line', async (line) => {
      try {
        const { id, message } = JSON.parse(line);
        if (typeof id !== 'string' || typeof message !== 'string' || !message.trim())
          throw new Error('A report needs a message');
        await report(id, message);
        socket.end('{"ok":true}\n');
      } catch (error) {
        socket.end(JSON.stringify({ error: String(error) }) + '\n');
      }
    });
  });
  try {
    await new Promise<void>((resolve, reject) => {
      server.once('error', reject);
      server.listen(path, resolve);
    });
  } catch (error) {
    await rm(dir, { recursive: true, force: true });
    throw error;
  }
  return {
    mcp: { command: process.execPath, args: [fileURLToPath(import.meta.url), '--mcp', path], env: {} },
    close: async () => {
      server.close();
      await rm(dir, { recursive: true, force: true });
    },
  };
}

async function serveStdio(path: string) {
  const connection = randomUUID();
  const tools = [
    {
      name: 'send_message',
      description: 'Send a question or material update to the Global Agent that assigned this work.',
      inputSchema: {
        type: 'object',
        properties: { message: { type: 'string' } },
        required: ['message'],
        additionalProperties: false,
      },
    },
  ];
  for await (const line of createInterface({ input: process.stdin })) {
    let request;
    try {
      request = JSON.parse(line);
    } catch {
      continue;
    }
    if (request.id === undefined) continue;
    const envelope = { jsonrpc: '2.0', id: request.id };
    try {
      let result: unknown;
      if (request.method === 'initialize')
        result = {
          protocolVersion: request.params.protocolVersion,
          capabilities: { tools: {} },
          serverInfo: { name: 'nano-parent', version: '1' },
        };
      else if (request.method === 'tools/list') result = { tools };
      else if (request.method === 'ping') result = {};
      else if (request.method === 'tools/call' && request.params?.name === 'send_message') {
        await new Promise<void>((resolve, reject) => {
          const socket = createConnection(path);
          socket.once('error', reject);
          socket.once('connect', () =>
            socket.write(
              JSON.stringify({
                id: connection + ':' + request.id,
                message: request.params.arguments?.message,
              }) + '\n',
            ),
          );
          const lines = createInterface({ input: socket });
          lines.once('line', (line) => {
            try {
              const reply = JSON.parse(line);
              if (!reply.ok) throw new Error(reply.error);
              resolve();
            } catch (error) {
              reject(error);
            } finally {
              socket.destroy();
            }
          });
          socket.once('close', () => reject(new Error('Parent report connection closed')));
        });
        result = { content: [{ type: 'text', text: 'Delivered to your parent.' }] };
      } else {
        process.stdout.write(
          JSON.stringify({ ...envelope, error: { code: -32601, message: 'Unknown MCP method' } }) + '\n',
        );
        continue;
      }
      process.stdout.write(JSON.stringify({ ...envelope, result }) + '\n');
    } catch (error) {
      process.stdout.write(
        JSON.stringify({ ...envelope, error: { code: -32603, message: String(error) } }) + '\n',
      );
    }
  }
}

if (process.argv[1] === fileURLToPath(import.meta.url) && process.argv[2] === '--mcp')
  await serveStdio(process.argv[3]!);
