import net from 'node:net';
import { chmod, rm } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { dirname, join } from 'node:path';
import { createInterface } from 'node:readline';
import { encodeTrajectoryValue, type SessionBinding, type TrajectoryScope } from '@nano/product-contracts';
import type { PartitionRuntime } from './runtime-partitions.js';

/** Compute the current-user local IPC endpoint path for a node configuration file. */
export function localNodeBridgeEndpoint(configPath: string): string {
  if (process.platform === 'win32') {
    const digest = createHash('sha256').update(configPath.toLowerCase()).digest('hex').slice(0, 24);
    return `\\\\.\\pipe\\crewden-desktop-node-${digest}`;
  }
  const digest = createHash('sha256').update(configPath).digest('hex').slice(0, 20);
  const candidate = join(dirname(configPath), '.desktop-node.sock');
  // Unix domain sockets have a ~104 byte sun_path limit on macOS; fall back to TMPDIR when deep.
  if (Buffer.byteLength(candidate) <= 96) return candidate;
  return join(process.env.TMPDIR ?? '/tmp', `crewden-node-${digest}.sock`);
}

export interface LocalNodeBridgeOptions {
  configPath: string;
  nodeId: string;
  ownerId: () => string;
  nodeEpoch: () => number | undefined;
  ready: () => boolean;
  connected: () => boolean;
  bindings: () => readonly SessionBinding[];
  runtime: Pick<PartitionRuntime, 'request'>;
  activeTasks?: () => number;
}

/** Same-user local IPC server for Crewden Desktop trajectory streaming and live status reads. */
export class LocalNodeBridge {
  private server?: net.Server;
  private readonly endpoint: string;
  private readonly connections = new Set<net.Socket>();

  constructor(private readonly options: LocalNodeBridgeOptions) {
    this.endpoint = localNodeBridgeEndpoint(options.configPath);
  }

  get address(): string {
    return this.endpoint;
  }

  async start(): Promise<void> {
    if (process.platform !== 'win32') {
      await rm(this.endpoint, { force: true });
    }
    const server = net.createServer(socket => this.handleConnection(socket));
    await new Promise<void>((resolve, reject) => {
      server.once('error', reject);
      server.listen(this.endpoint, () => {
        server.removeListener('error', reject);
        resolve();
      });
    });
    if (process.platform !== 'win32') {
      await chmod(this.endpoint, 0o600).catch(() => {});
    }
    server.unref();
    this.server = server;
  }

  async close(): Promise<void> {
    for (const socket of this.connections) {
      socket.destroy();
    }
    this.connections.clear();
    if (this.server) {
      const server = this.server;
      this.server = undefined;
      await new Promise<void>(resolve => server.close(() => resolve()));
    }
    if (process.platform !== 'win32') {
      await rm(this.endpoint, { force: true }).catch(() => {});
    }
  }

  private handleConnection(socket: net.Socket): void {
    this.connections.add(socket);
    const activeObservers = new Set<string>();
    let writeChain = Promise.resolve();
    const sendFrame = (frame: unknown): Promise<void> => {
      writeChain = writeChain.then(
        () =>
          new Promise<void>((resolve, reject) => {
            if (socket.destroyed || !socket.writable) {
              resolve();
              return;
            }
            socket.write(JSON.stringify(frame) + '\n', error => (error ? reject(error) : resolve()));
          }),
      ).catch(() => {});
      return writeChain;
    };

    const sendChunked = async (frame: unknown): Promise<void> => {
      for (const part of encodeTrajectoryValue(frame)) {
        if (socket.destroyed || !socket.writable) return;
        await sendFrame(part);
      }
    };

    const rl = createInterface({ input: socket, crlfDelay: Infinity });
    rl.on('line', line => {
      if (!line.trim()) return;
      void this.dispatchLine(line, activeObservers, sendFrame, sendChunked).catch(error => {
        void sendFrame({
          type: 'bridge_error',
          message: error instanceof Error ? error.message : String(error),
        });
      });
    });

    const cleanup = () => {
      this.connections.delete(socket);
      rl.close();
      for (const observerId of activeObservers) {
        void this.options.runtime.request('trajectory.close', { observerId }).catch(() => {});
      }
      activeObservers.clear();
    };
    socket.once('close', cleanup);
    socket.on('error', () => {});
  }

  private async dispatchLine(
    line: string,
    activeObservers: Set<string>,
    sendFrame: (frame: unknown) => Promise<void>,
    sendChunked: (frame: unknown) => Promise<void>,
  ): Promise<void> {
    const msg = JSON.parse(line) as Record<string, unknown>;
    const method = String(msg.method ?? '');
    const rpcId = typeof msg.id === 'string' ? msg.id : undefined;

    if (method === 'local.ping') {
      await sendFrame({
        id: rpcId,
        ok: true,
        result: {
          node_id: this.options.nodeId,
          owner_id: this.options.ownerId(),
          node_epoch: this.options.nodeEpoch() ?? null,
          ready: this.options.ready(),
          connected: this.options.connected(),
          pid: process.pid,
          active_tasks: this.options.activeTasks?.() ?? 0,
        },
      });
      return;
    }

    if (method === 'local.trajectory.prepare') {
      const observerId = String(msg.observerId ?? '');
      const agentId = String(msg.agentId ?? '');
      const sessionId = String(msg.sessionId ?? '');
      const ownerId = String(msg.ownerId ?? '');
      const nodeEpoch = typeof msg.nodeEpoch === 'number' ? msg.nodeEpoch : undefined;
      if (!observerId || !agentId || !sessionId || !ownerId) {
        await sendFrame({ id: rpcId, ok: false, code: 'invalid_params', message: 'Missing trajectory parameters' });
        return;
      }
      if (ownerId !== this.options.ownerId()) {
        await sendFrame({ id: rpcId, ok: false, code: 'foreign_owner', message: 'Local node belongs to another owner' });
        return;
      }
      const currentEpoch = this.options.nodeEpoch();
      if (nodeEpoch !== undefined && currentEpoch !== undefined && nodeEpoch !== currentEpoch) {
        await sendFrame({ id: rpcId, ok: false, code: 'epoch_mismatch', message: 'Node binding epoch changed' });
        return;
      }
      const binding = this.options
        .bindings()
        .find(item => item.agentId === agentId && item.ownerId === ownerId && item.conversationId === `global:${agentId}`);
      if (!binding) {
        await sendFrame({ id: rpcId, ok: false, code: 'not_found', message: '该执行不可访问' });
        return;
      }
      const scope: TrajectoryScope = {
        observerId,
        rootAgentId: agentId,
        rootSessionId: binding.sessionId,
        sessionId,
        ownerId,
        nodeId: this.options.nodeId,
        nodeEpoch: currentEpoch ?? nodeEpoch ?? 0,
      };
      try {
        const prepared = await this.options.runtime.request('trajectory.prepare', scope);
        activeObservers.add(observerId);
        await sendChunked({ type: 'ready', observerId, ...(prepared as object) });
      } catch (error) {
        await sendFrame({
          type: 'failed',
          observerId,
          message: error instanceof Error ? error.message : String(error),
        });
      }
      return;
    }

    if (method === 'local.trajectory.attachment_sources') {
      const observerId = String(msg.observerId ?? '');
      if (!observerId || !activeObservers.has(observerId)) {
        await sendFrame({ id: rpcId, ok: false, code: 'invalid_observer', message: 'Observer not active' });
        return;
      }
      try {
        const raw = await this.options.runtime.request(
          'trajectory.call' as Parameters<PartitionRuntime['request']>[0],
          {
            observerId,
            method: 'trajectory/attachment-source',
            params: msg.params,
          } as never,
        );
        const sources = (raw as { value?: { sources?: unknown[] } } | null)?.value?.sources ?? [];
        await sendFrame({
          id: rpcId,
          ok: true,
          sources: Array.isArray(sources) ? sources : [],
        });
      } catch (error) {
        await sendFrame({
          id: rpcId,
          ok: false,
          code: 'attachment_source_failed',
          message: error instanceof Error ? error.message : String(error),
        });
      }
      return;
    }

    if (method === 'local.trajectory.request') {
      const observerId = String(msg.observerId ?? '');
      const request = msg.request as Record<string, unknown> | undefined;
      if (!observerId || !activeObservers.has(observerId) || !request || typeof request.requestId !== 'string') {
        return;
      }
      const reqType = String(request.type ?? '');
      if (!['call', 'open', 'next', 'abort'].includes(reqType)) return;
      const reqMethod = typeof request.method === 'string' ? request.method : '';
      if (
        ['call', 'open'].includes(reqType) &&
        ![
          'trajectory/runs',
          'session/list',
          'session/page',
          'session/projections',
          'session/attachment',
          'session/control',
          'session/follow',
        ].includes(reqMethod)
      ) {
        await sendChunked({
          type: 'error',
          observerId,
          requestId: request.requestId,
          code: 'read_only',
          message: '只允许读取原生轨迹',
        });
        return;
      }
      if (reqType === 'call' && reqMethod === 'session/attachment' && msg.hostAttachmentAuthorized !== true) {
        await sendChunked({
          type: 'error',
          observerId,
          requestId: request.requestId,
          code: 'attachment_forbidden',
          message: '无法验证附件访问权限',
        });
        return;
      }
      try {
        const value = await this.options.runtime.request(
          `trajectory.${reqType}` as Parameters<PartitionRuntime['request']>[0],
          {
            observerId,
            method: request.method,
            params: request.params,
            streamId: request.streamId,
            ...(reqType === 'open' && request.initialBatch === true ? { initialBatch: true } : {}),
            ...(reqMethod === 'session/attachment' && msg.hostAttachmentAuthorized === true
              ? { attachmentAuthorized: true }
              : {}),
          } as never,
        );
        await sendChunked({
          type: 'result',
          observerId,
          requestId: request.requestId,
          value,
        });
      } catch (error) {
        await sendChunked({
          type: 'error',
          observerId,
          requestId: request.requestId,
          code: String(error).includes('generation_changed') ? 'generation_changed' : 'trajectory_read_failed',
          message: error instanceof Error ? error.message : String(error),
        });
      }
      return;
    }

    if (method === 'local.trajectory.close') {
      const observerId = String(msg.observerId ?? '');
      if (observerId && activeObservers.delete(observerId)) {
        await this.options.runtime.request('trajectory.close', { observerId }).catch(() => {});
      }
      await sendFrame({ id: rpcId, ok: true });
      return;
    }

    await sendFrame({ id: rpcId, ok: false, code: 'unknown_method', message: `Unknown method: ${method}` });
  }
}
