import WebSocket from 'ws';
import { TRAJECTORY_MAX_BYTES, type RuntimePort, type TrajectoryRequest, type TrajectoryScope } from '@nano/product-contracts';

/** Owns outbound readers independently of the device's business ACK queue. */
export class NodeTrajectory {
  private readonly sockets = new Map<string, WebSocket>();
  constructor(private readonly options: { imUrl: string; runtime: RuntimePort; valid: (scope: TrajectoryScope) => boolean }) {}

  /** Pair a short-lived observer with the configured IM, never a supplied destination. */
  prepare(scope: TrajectoryScope, ticket: string): void {
    this.close(scope.observerId);
    if (!this.options.valid(scope)) return;
    const url = new URL(this.options.imUrl);
    url.protocol = ['https:', 'wss:'].includes(url.protocol) ? 'wss:' : 'ws:';
    url.pathname = '/im/ws/node-trajectory'; url.search = ''; url.hash = '';
    url.searchParams.set('ticket', ticket);
    const socket = new WebSocket(url);
    this.sockets.set(scope.observerId, socket);
    let initialized = false;
    const active = () => this.sockets.get(scope.observerId) === socket && this.options.valid(scope);
    const write = (value: unknown) => {
      const text = JSON.stringify(value);
      if (!active() || socket.readyState !== WebSocket.OPEN) return;
      if (Buffer.byteLength(text) > TRAJECTORY_MAX_BYTES || socket.bufferedAmount + Buffer.byteLength(text) > TRAJECTORY_MAX_BYTES) { this.close(scope.observerId); return; }
      socket.send(text);
    };
    socket.once('open', () => {
      void this.options.runtime.request('trajectory.prepare', scope).then(value => {
        initialized = true;
        if (!active()) { void this.options.runtime.request('trajectory.close', { observerId: scope.observerId }).catch(() => {}); return; }
        write({ type: 'ready', observerId: scope.observerId, ...value as object });
      }).catch(error => { write({ type: 'failed', observerId: scope.observerId, message: String(error) }); socket.close(1011); });
    });
    socket.on('message', raw => {
      const bytes = Array.isArray(raw) ? raw.reduce((size, item) => size + item.byteLength, 0) : raw.byteLength;
      if (!active() || !initialized || bytes > TRAJECTORY_MAX_BYTES) { this.close(scope.observerId); return; }
      let request: TrajectoryRequest;
      try { request = JSON.parse(raw.toString()); }
      catch { this.close(scope.observerId); return; }
      if (!['call', 'open', 'next', 'abort'].includes(request.type) || typeof request.requestId !== 'string') { this.close(scope.observerId); return; }
      // A long next must not delay abort or another reader.
      void this.options.runtime.request(`trajectory.${request.type}`, {
        observerId: scope.observerId, method: request.method, params: request.params, streamId: request.streamId,
        ...((request as TrajectoryRequest & { attachmentAuthorized?: boolean }).attachmentAuthorized ? { attachmentAuthorized: true } : {}),
      }).then(value => write({ type: 'result', observerId: scope.observerId, requestId: request.requestId, value }))
        .catch(error => write({ type: 'error', observerId: scope.observerId, requestId: request.requestId,
          code: String(error).includes('generation_changed') ? 'generation_changed' : 'trajectory_read_failed', message: error instanceof Error ? error.message : String(error) }));
    });
    socket.on('error', () => this.close(scope.observerId));
    socket.once('close', () => {
      if (this.sockets.get(scope.observerId) === socket) this.sockets.delete(scope.observerId);
      if (initialized) void this.options.runtime.request('trajectory.close', { observerId: scope.observerId }).catch(() => {});
    });
  }

  close(observerId: string): void {
    const socket = this.sockets.get(observerId);
    this.sockets.delete(observerId);
    socket?.terminate();
  }
  closeAll(): void { for (const id of this.sockets.keys()) this.close(id); }
}
