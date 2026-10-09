import WebSocket from 'ws';

/** Carries the existing IM envelope without translating business payloads. */
export interface ProtocolFrame {
  type: string;
  payload: Record<string, unknown>;
}
/** Preserves registration metadata returned by IM; node_epoch is optional on older IM. */
export interface RegistrationAck extends Record<string, unknown> {
  gateway_access_token?: string;
  node_epoch?: number;
}
export type RelayState = 'stopped' | 'connecting' | 'registering' | 'ready' | 'reconnecting' | 'revoked';
/** Supplies fresh runtime credentials and node registration on every connection attempt. */
export interface RelayCredentials {
  accessToken: string;
  registration: Record<string, unknown>;
}
/** Configures the IM connection. Timing options are milliseconds; callbacks never gate reads. */
export interface WebRelayOptions {
  url: string;
  credentials: () => RelayCredentials | Promise<RelayCredentials>;
  onFrame: (frame: ProtocolFrame) => void | Promise<void>;
  onState?: (state: RelayState) => void | Promise<void>;
  onError?: (error: Error) => void;
  heartbeatPayload?: () => Record<string, unknown>;
  heartbeatIntervalMs?: number;
  ackTimeoutMs?: number;
  reconnectInitialMs?: number;
  reconnectMaxMs?: number;
}
/** A failed send whose delivery status tells the durable owner whether reconciliation is needed. */
export class RelayDeliveryError extends Error {
  constructor(message: string, readonly delivery: 'not-sent' | 'unknown' | 'rejected', readonly code?: string) {
    super(message); this.name = 'RelayDeliveryError';
  }
}
interface Pending {
  frame: ProtocolFrame;
  resolve: (frame: ProtocolFrame) => void;
  reject: (error: Error) => void;
  timer?: ReturnType<typeof setTimeout>;
}
const results: Record<string, [string, string]> = {
  'agent.work.append': ['agent.work.ack', 'journal_id'],
  'conversation.query': ['conversation.query.result', 'request_id'],
  'task_graph.command': ['task_graph.result', 'request_id'],
  'channel.status': ['channel.status.result', 'request_id'],
  'channel.runtime_metadata': ['channel.runtime_metadata.result', 'request_id'],
  'channel.reconcile.result': ['channels.reconcile.result.ack', 'request_id'],
  'channels.bootstrap': ['channels.bootstrap.result', 'request_id'],
};

/** Owns the existing IM socket protocol; durable delivery and retry decisions belong to its caller. */
export class WebRelayConnection {
  private socket?: WebSocket;
  private active?: Pending;
  private queue: Pending[] = [];
  private reconnectTimer?: ReturnType<typeof setTimeout>;
  private heartbeatTimer?: ReturnType<typeof setTimeout>;
  private connectTimer?: ReturnType<typeof setTimeout>;
  private generation = 0;
  private attempt = 0;
  private running = false;
  private startPromise?: Promise<RegistrationAck>;
  private resolveStart?: (ack: RegistrationAck) => void;
  private rejectStart?: (error: Error) => void;
  private currentState: RelayState = 'stopped';
  private currentRegistration?: RegistrationAck;
  private registrationPayload: Record<string, unknown> = {};
  constructor(private readonly options: WebRelayOptions) {}
  get state(): RelayState { return this.currentState; }
  get ready(): boolean { return this.state === 'ready'; }
  get registration(): RegistrationAck | undefined { return this.currentRegistration; }

  /** Connects and resolves after the first registration ACK. Repeated calls share startup. */
  start(): Promise<RegistrationAck> {
    if (this.ready) return Promise.resolve(this.currentRegistration!);
    if (this.running) return this.startPromise!;
    this.running = true;
    this.attempt = 0;
    this.startPromise = new Promise((resolve, reject) => { this.resolveStart = resolve; this.rejectStart = reject; });
    void this.connect();
    return this.startPromise;
  }

  /** Sends one business frame only while registered.
   *
   * Args:
   *   type: Existing IM upstream message type; registration and heartbeat are owned here.
   *   payload: Complete wire payload including node_id and any request/journal identity.
   * Returns:
   *   The matching ACK or typed result frame.
   * Raises:
   *   RelayDeliveryError: Carries rejected, not-sent, or unknown delivery status. The
   *   caller must reconcile unknown delivery before retrying; this transport never replays.
   */
  request(type: string, payload: Record<string, unknown>): Promise<ProtocolFrame> {
    if (!this.ready || type === 'node.register' || type === 'node.heartbeat') {
      return Promise.reject(new RelayDeliveryError('Relay is not ready for this business request', 'not-sent'));
    }
    return this.enqueue({ type, payload });
  }

  /** Cancels timers, rejects outstanding work, and closes the owned socket without replay. */
  async stop(): Promise<void> {
    this.running = false;
    this.generation++;
    this.clearTimers();
    this.failRequests('Relay stopped');
    this.rejectStart?.(new RelayDeliveryError('Relay stopped before registration', 'not-sent'));
    this.resolveStart = undefined; this.rejectStart = undefined;
    this.currentRegistration = undefined;
    const socket = this.socket; this.socket = undefined;
    this.setState('stopped');
    if (socket && socket.readyState !== WebSocket.CLOSED) {
      await new Promise<void>(resolve => { socket.once('close', () => resolve()); socket.terminate(); });
    }
  }

  private async connect(): Promise<void> {
    const generation = ++this.generation;
    this.setState('connecting');
    this.connectTimer = setTimeout(() => this.disconnect(generation, false, 'Connection deadline exceeded'), this.options.ackTimeoutMs ?? 10000);
    try {
      const credentials = await this.options.credentials();
      if (!this.running || generation !== this.generation) return;
      this.registrationPayload = credentials.registration;
      const url = new URL(this.options.url);
      url.protocol = url.protocol === 'https:' || url.protocol === 'wss:' ? 'wss:' : 'ws:';
      url.pathname = '/im/ws/gateway'; url.search = ''; url.hash = '';
      const socket = new WebSocket(url, { headers: { Authorization: `Bearer ${credentials.accessToken}`, 'User-Agent': 'nano-multiagent-gateway' } });
      this.socket = socket;
      socket.on('error', () => { if (generation === this.generation) this.report(new Error('IM WebSocket transport error')); });
      socket.on('unexpected-response', (_request, response) => {
        response.resume();
        this.disconnect(generation, response.statusCode === 401 || response.statusCode === 403, 'IM WebSocket handshake rejected');
      });
      socket.on('close', code => this.disconnect(generation, code === 1008 || code === 4003, 'IM WebSocket disconnected'));
      socket.on('message', data => {
        if (generation !== this.generation) return;
        try {
          const frame: unknown = JSON.parse(data.toString());
          if (!frame || typeof frame !== 'object' || !('type' in frame) || typeof frame.type !== 'string' || !('payload' in frame) || !frame.payload || typeof frame.payload !== 'object' || Array.isArray(frame.payload)) throw new Error('Invalid IM frame');
          this.receive(frame as ProtocolFrame, generation);
        } catch { this.disconnect(generation, false, 'Invalid IM WebSocket frame'); }
      });
      socket.once('open', () => {
        if (generation !== this.generation) return;
        this.setState('registering');
        void this.enqueue({ type: 'node.register', payload: credentials.registration }).then(frame => {
          if (generation !== this.generation) return;
          clearTimeout(this.connectTimer); this.connectTimer = undefined;
          this.currentRegistration = frame.payload;
          this.attempt = 0;
          this.setState('ready');
          this.resolveStart?.(frame.payload);
          this.resolveStart = undefined; this.rejectStart = undefined;
          this.scheduleHeartbeat(generation);
        }).catch(() => this.disconnect(generation, false, 'Node registration rejected'));
      });
    } catch { this.disconnect(generation, false, 'Unable to establish IM connection'); }
  }

  private enqueue(frame: ProtocolFrame): Promise<ProtocolFrame> {
    return new Promise((resolve, reject) => { this.queue.push({ frame, resolve, reject }); this.pump(); });
  }
  private pump(): void {
    if (this.active || this.socket?.readyState !== WebSocket.OPEN) return;
    const pending = this.queue.shift();
    if (!pending) return;
    this.active = pending;
    const generation = this.generation;
    pending.timer = setTimeout(() => this.disconnect(generation, false, 'IM response deadline exceeded'), this.options.ackTimeoutMs ?? 10000);
    try {
      this.socket.send(JSON.stringify(pending.frame), error => {
        if (error) this.disconnect(generation, false, 'IM frame send failed');
      });
    } catch { this.disconnect(generation, false, 'IM frame send failed'); }
  }
  private receive(frame: ProtocolFrame, generation: number): void {
    // Revocation is terminal even if it arrives while no business request is waiting.
    if (frame.type === 'error' && frame.payload.code === 'gateway_owner_mismatch') {
      this.disconnect(generation, true, 'Gateway authority revoked'); return;
    }
    const pending = this.active;
    if (pending && this.matches(pending.frame, frame)) {
      clearTimeout(pending.timer); this.active = undefined;
      if (frame.type === 'error') {
        pending.reject(new RelayDeliveryError('IM rejected the request', 'rejected', String(frame.payload.code ?? 'error')));
        if (pending.frame.type === 'node.register' || pending.frame.type === 'node.heartbeat') {
          this.disconnect(generation, false, 'IM rejected control frame'); return;
        }
      } else pending.resolve(frame);
      this.pump();
      return;
    }
    // User callbacks must not own the receive loop: approval/cancel/ACK frames keep flowing.
    void Promise.resolve().then(() => this.options.onFrame(frame)).catch(error => this.report(error instanceof Error ? error : new Error('IM inbound callback failed')));
  }
  private matches(sent: ProtocolFrame, received: ProtocolFrame): boolean {
    if (received.type === 'error') {
      const key = results[sent.type]?.[1];
      return (received.payload.message_type === undefined || received.payload.message_type === sent.type)
        && (!key || received.payload[key] === undefined || received.payload[key] === sent.payload[key]);
    }
    const typed = results[sent.type];
    if (typed) {
      const [type, key] = typed;
      return received.type === type && sent.payload[key] !== undefined && received.payload[key] === sent.payload[key];
    }
    return received.type === 'ack' && received.payload.message_type === sent.type;
  }
  private scheduleHeartbeat(generation: number): void {
    this.heartbeatTimer = setTimeout(() => {
      if (generation !== this.generation || !this.ready) return;
      if (this.active || this.queue.length) { this.scheduleHeartbeat(generation); return; }
      const payload = this.options.heartbeatPayload?.() ?? {
        node_id: this.registrationPayload.node_id, status: 'online',
        agent_count: Array.isArray(this.registrationPayload.agents) ? this.registrationPayload.agents.length : 0,
      };
      void this.enqueue({ type: 'node.heartbeat', payload }).then(() => {
        if (generation === this.generation) this.scheduleHeartbeat(generation);
      }).catch(() => this.disconnect(generation, false, 'Heartbeat failed'));
    }, this.options.heartbeatIntervalMs ?? 30000);
  }
  private disconnect(generation: number, revoked: boolean, message: string): void {
    if (generation !== this.generation) return;
    this.generation++;
    this.clearTimers();
    const socket = this.socket; this.socket = undefined;
    this.currentRegistration = undefined;
    this.failRequests(message);
    socket?.terminate();
    if (!this.running) return;
    this.report(new Error(message));
    if (revoked) {
      this.running = false;
      this.setState('revoked');
      this.rejectStart?.(new RelayDeliveryError(message, 'rejected', 'authority_revoked'));
      this.resolveStart = undefined; this.rejectStart = undefined;
      return;
    }
    this.setState('reconnecting');
    const delay = Math.min((this.options.reconnectInitialMs ?? 1000) * 2 ** Math.min(this.attempt++, 20), this.options.reconnectMaxMs ?? 30000);
    this.reconnectTimer = setTimeout(() => { void this.connect(); }, delay);
  }
  private failRequests(message: string): void {
    if (this.active) {
      clearTimeout(this.active.timer);
      this.active.reject(new RelayDeliveryError(message, 'unknown')); this.active = undefined;
    }
    for (const pending of this.queue.splice(0)) pending.reject(new RelayDeliveryError(message, 'not-sent'));
  }
  private clearTimers(): void {
    clearTimeout(this.connectTimer); clearTimeout(this.reconnectTimer); clearTimeout(this.heartbeatTimer);
    this.connectTimer = undefined; this.reconnectTimer = undefined; this.heartbeatTimer = undefined;
  }
  private setState(state: RelayState): void {
    this.currentState = state;
    void Promise.resolve().then(() => this.options.onState?.(state)).catch(() => this.report(new Error('IM state callback failed')));
  }
  private report(error: Error): void {
    try { this.options.onError?.(error); } catch { /* Diagnostics must not interrupt protocol cleanup. */ }
  }
}

export { FeishuConnection, parseFeishuMessage, type FeishuConfiguration, type FeishuMessage } from './feishu.js';
