import { createServer, createConnection, type Socket } from 'node:net';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createInterface } from 'node:readline';
import { randomUUID } from 'node:crypto';
import type { ComputerContent } from '../computer/backend.js';

type ComputerCall = (args: unknown, signal: AbortSignal) => Promise<ComputerContent[]>;

const reportTool = {
  name: 'send_message',
  description: 'Send a question or material update to the Global Agent that assigned this work.',
  inputSchema: {type: 'object', properties: {message: {type: 'string'}}, required: ['message'], additionalProperties: false},
};
const computerTool = {
  name: 'computer_use',
  description: 'Use your assigned browser tab or desktop window. Start with status or describe for actions and inputs.',
  inputSchema: {
    type: 'object', properties: {
      surface: {enum: ['browser', 'desktop']}, action: {type: 'string'}, input: {type: 'object'},
    }, required: ['surface', 'action'], additionalProperties: false,
  },
};

/** Bind this activation's stdio tools to host callbacks through a private local socket. */
export async function workerReportBridge(report: (id: string, message: string) => Promise<void>, computer?: ComputerCall) {
  const dir = await mkdtemp(join(tmpdir(), 'nano-w-'));
  const path = join(dir, 'report.sock');
  const key = computer ? randomUUID() : undefined;
  const connections = new Set<Socket>();
  const server = createServer(socket => {
    connections.add(socket);
    const pending = new AbortController();
    socket.on('error', () => {});
    socket.once('close', () => { connections.delete(socket); pending.abort(); });
    const lines = createInterface({input: socket});
    lines.once('line', async line => {
      try {
        const request = JSON.parse(line);
        let content: ComputerContent[];
        if (request.tool === computerTool.name && computer && request.key === key) {
          const args = request.args;
          if (!args || typeof args !== 'object' || !['browser', 'desktop'].includes(args.surface) ||
              typeof args.action !== 'string' || !args.action ||
              Object.keys(args).some(name => !['surface', 'action', 'input'].includes(name)) ||
              ('input' in args && (!args.input || typeof args.input !== 'object' || Array.isArray(args.input))))
            throw new Error('Invalid arguments for the assigned computer tool');
          content = await computer(args, pending.signal);
        } else if (request.tool === reportTool.name && typeof request.id === 'string' &&
            typeof request.args?.message === 'string' && request.args.message.trim()) {
          await report(request.id, request.args.message);
          content = [{type: 'text', text: 'Delivered to your parent.'}];
        } else throw new Error('Worker tool or binding is unavailable');
        socket.end(JSON.stringify({content}) + '\n');
      } catch (error) {
        socket.end(JSON.stringify({error: String(error)}) + '\n');
      }
    });
  });
  try {
    await new Promise<void>((resolve, reject) => {
      server.once('error', reject);
      server.listen(path, resolve);
    });
  } catch (error) {
    await rm(dir, {recursive: true, force: true});
    throw error;
  }
  const command = process.execPath;
  const script = fileURLToPath(import.meta.url);
  return {
    mcp: {command, args: [script, '--mcp', path], env: {}},
    computer: key ? {command, args: [script, '--computer-mcp', path], env: {NANO_WORKER_MCP_KEY: key}} : undefined,
    close: async () => {
      server.close();
      for (const socket of connections) socket.destroy();
      await rm(dir, {recursive: true, force: true});
    },
  };
}

async function serveStdio(path: string, computer: boolean) {
  const connection = randomUUID();
  const tool = computer ? computerTool : reportTool;
  const sockets = new Map<string | number, Socket>();
  const output = (id: string | number, body: object) =>
    process.stdout.write(JSON.stringify({jsonrpc: '2.0', id, ...body}) + '\n');
  try {
    for await (const line of createInterface({input: process.stdin})) {
      let request;
      try { request = JSON.parse(line); } catch { continue; }
      const {id, method, params} = request;
      if (method === 'notifications/cancelled') sockets.get(params?.requestId)?.destroy();
      if (typeof id !== 'string' && typeof id !== 'number') continue;
      if (method === 'tools/call' && params?.name === tool.name) {
        if (sockets.has(id)) continue;
        const socket = createConnection(path);
        sockets.set(id, socket);
        let answered = false;
        socket.on('error', () => {});
        socket.once('connect', () => socket.write(JSON.stringify({
          id: connection + ':' + id, tool: tool.name, args: params.arguments,
          ...(computer ? {key: process.env.NANO_WORKER_MCP_KEY} : {}),
        }) + '\n'));
        createInterface({input: socket}).once('line', reply => {
          answered = true;
          try {
            const result = JSON.parse(reply);
            if (result.error) throw new Error(result.error);
            output(id, {result: {content: result.content}});
          } catch (error) {
            output(id, {result: {isError: true, content: [{type: 'text', text: String(error)}]}});
          } finally { socket.destroy(); }
        });
        socket.once('close', () => {
          sockets.delete(id);
          if (!answered) output(id, {error: {code: -32603, message: 'Worker tool connection closed'}});
        });
      } else if (method === 'initialize') {
        output(id, {result: {
          protocolVersion: params.protocolVersion, capabilities: {tools: {}},
          serverInfo: {name: computer ? 'nano-computer' : 'nano-parent', version: '1'},
        }});
      } else if (method === 'tools/list') output(id, {result: {tools: [tool]}});
      else if (method === 'ping') output(id, {result: {}});
      else output(id, {error: {code: -32601, message: 'Unknown MCP method'}});
    }
  } finally {
    for (const socket of sockets.values()) socket.destroy();
  }
}

if (process.argv[1] === fileURLToPath(import.meta.url) && ['--mcp', '--computer-mcp'].includes(process.argv[2]!))
  await serveStdio(process.argv[3]!, process.argv[2] === '--computer-mcp');
