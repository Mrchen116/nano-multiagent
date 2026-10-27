import WebSocket from 'ws';
import { randomUUID } from 'node:crypto';
import http from 'node:http';
import https from 'node:https';

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
export type RelayState = 'stopped' | 'connecting' | 'registering' | 'ready' | 'reconnecting' | 'revoked' | 'upgrade_required';
/** Safe connection lifecycle facts; payloads, credentials and URLs are never included. */
export interface RelayDiagnostic {
  timestamp: string;
  node_id?: string;
  connection: number;
  event: 'connecting' | 'registering' | 'ready' | 'transport_error' | 'disconnected' | 'retry_scheduled' | 'stopped';
  phase: 'connect' | 'register' | 'heartbeat' | 'receive' | 'send' | 'stop';
  attempt: number;
  reason?: string;
  error_type?: string;
  close_code?: number;
  close_reason?: string;
  http_status?: number;
  delay_ms?: number;
  outage_ms?: number;
  revoked?: boolean;
}
type DiagnosticDetails = Partial<Pick<RelayDiagnostic, 'reason' | 'error_type' | 'close_code' | 'close_reason' | 'http_status' | 'delay_ms' | 'outage_ms' | 'revoked' | 'attempt'>>;
const safeCloseReasons = new Set(['heartbeat_timeout', 'authority_revoked', 'server_shutdown', 'connection replaced', 'revoked']);
const safeTransportCodes = new Set(['ECONNREFUSED', 'ECONNRESET', 'ENOTFOUND', 'ETIMEDOUT', 'EHOSTUNREACH', 'ENETUNREACH', 'EAI_AGAIN']);
function errorType(error: unknown): string {
  return error instanceof TypeError ? 'TypeError' : error instanceof RangeError ? 'RangeError' : 'Error';
}
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
  onDiagnostic?: (event: RelayDiagnostic) => void;
  requiredCapabilities?: string[];
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
  control: boolean;
}
const results: Record<string, [string, string]> = {
  'agent.work.append': ['agent.work.ack', 'journal_id'],
  'conversation.query': ['conversation.query.result', 'request_id'],
  'task_graph.command': ['task_graph.result', 'request_id'],
  'task.execution.snapshot': ['task.execution.snapshot.result','request_id'],
  'task.execution.scopes': ['task.execution.scopes.result','request_id'],
  'task.execution.pause': ['task.execution.pause.result','request_id'],
  'channel.status': ['channel.status.result', 'request_id'],
  'channel.runtime_metadata': ['channel.runtime_metadata.result', 'request_id'],
  'channel.reconcile.result': ['channels.reconcile.result.ack', 'request_id'],
  'channels.bootstrap': ['channels.bootstrap.result', 'request_id'],
};

/** Owns the existing IM socket protocol; durable delivery and retry decisions belong to its caller. */
export class WebRelayConnection {
  private socket?: WebSocket;
  private readonly pending = new Map<string, Pending>();
  private correlated = false;
  private readonly serverRequests = new Set<string>();
  private lastAgent = '';
  private readySince = 0;
  private heartbeatFailures = 0;
  private heartbeatSuccesses = 0;
  private queue: Pending[] = [];
  private reconnectTimer?: ReturnType<typeof setTimeout>;
  private heartbeatTimer?: ReturnType<typeof setTimeout>;
  private connectTimer?: ReturnType<typeof setTimeout>;
  private generation = 0;
  private attempt = 0;
  private outageStartedAt?: number;
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
    this.outageStartedAt = undefined;
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
  request(type: string, payload: Record<string, unknown>, options: {priority?:'control'|'normal'} = {}): Promise<ProtocolFrame> {
    if (!this.ready || type === 'node.register' || type === 'node.heartbeat') {
      return Promise.reject(new RelayDeliveryError('Relay is not ready for this business request', 'not-sent'));
    }
    const preserve = typeof payload.request_id === 'string' && this.serverRequests.delete(payload.request_id);
    return this.enqueue({ type, payload: this.correlated && !preserve ? {...payload,request_id:randomUUID()} : payload },options.priority);
  }

  /** Cancels timers, rejects outstanding work, and closes the owned socket without replay. */
  async stop(): Promise<void> {
    if (this.state !== 'stopped') this.diagnose('stopped', 'stop');
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
    this.diagnose('connecting', 'connect');
    this.connectTimer = setTimeout(() => this.disconnect(generation, false, 'Connection deadline exceeded', { error_type: 'TimeoutError' }), this.options.ackTimeoutMs ?? 10000);
    try {
      const credentials = await this.options.credentials();
      if (!this.running || generation !== this.generation) return;
      this.registrationPayload = credentials.registration;
      const url = new URL(this.options.url);
      url.protocol = url.protocol === 'https:' || url.protocol === 'wss:' ? 'wss:' : 'ws:';
      url.pathname = '/im/ws/gateway'; url.search = ''; url.hash = '';
      // ws supplies createConnection, so Node otherwise bypasses its global agent.
      const socket = new WebSocket(url, { agent: url.protocol === 'wss:' ? https.globalAgent : http.globalAgent,
        headers: { Authorization: `Bearer ${credentials.accessToken}`, 'User-Agent': 'nano-multiagent-gateway' } });
      this.socket = socket;
      socket.on('error', (error: Error & { code?: string }) => {
        if (generation !== this.generation) return;
        this.diagnose('transport_error', this.phase(), { error_type: 'WebSocketError',
          reason: error.code && safeTransportCodes.has(error.code) ? error.code : 'transport_error' });
        this.report(new Error('IM WebSocket transport error'));
      });
      socket.on('unexpected-response', (_request, response) => {
        response.resume();
        this.disconnect(generation, response.statusCode === 401 || response.statusCode === 403, 'IM WebSocket handshake rejected', { error_type: 'HTTPError', http_status: response.statusCode });
      });
      socket.on('close', (code, reason) => {
        const text = reason.toString();
        this.disconnect(generation, code === 1008 || code === 4003, 'IM WebSocket disconnected', {
          close_code: code, close_reason: !text || safeCloseReasons.has(text) ? text : '[redacted]',
        });
      });
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
        this.diagnose('registering', 'register');
        void this.enqueue({ type: 'node.register', payload: credentials.registration }).then(frame => {
          if (generation !== this.generation) return;
          clearTimeout(this.connectTimer); this.connectTimer = undefined;
          if (this.options.requiredCapabilities?.some(key=>frame.payload[key]!==1)) {
            this.running=false;this.generation++;this.clearTimers();this.failRequests('IM upgrade required');
            this.socket=undefined;socket.terminate();this.setState('upgrade_required');
            this.rejectStart?.(new RelayDeliveryError('IM upgrade required','rejected','upgrade_required'));
            this.resolveStart=undefined;this.rejectStart=undefined;return;
          }
          this.currentRegistration = frame.payload;
          this.diagnose('ready', 'register', this.outageStartedAt === undefined ? {} : { outage_ms: Date.now() - this.outageStartedAt });
          this.outageStartedAt = undefined;
          this.correlated = frame.payload.relay_request_ids === 1;
          this.readySince = Date.now(); this.heartbeatFailures = 0; this.heartbeatSuccesses = 0;
          this.setState('ready');
          this.resolveStart?.(frame.payload);
          this.resolveStart = undefined; this.rejectStart = undefined;
          this.scheduleHeartbeat(generation);
        }).catch(() => this.disconnect(generation, false, 'Node registration rejected'));
      });
    } catch (error) { this.disconnect(generation, false, 'Unable to establish IM connection', { error_type: errorType(error) }); }
  }

  private control(type: string): boolean {
    return type === 'node.register' || type === 'node.heartbeat' || type === 'node.delivery_receipt'
      || type === 'agent.session.ensure' || type === 'agent.message.status' || type.includes('cancel') || type.includes('permission');
  }
  private agent(frame: ProtocolFrame): string {
    // Publications carry the same Agent identity in their stable operation scope.
    return String(frame.payload.agent_id ?? (typeof frame.payload.from_session_id === 'string' ? frame.payload.from_session_id.split('|')[0] : ''));
  }
  private enqueue(frame: ProtocolFrame, priority?:'control'|'normal'): Promise<ProtocolFrame> {
    const control = priority==='control' || priority!=='normal' && (this.control(frame.type) || frame.type==='node.streaming_delta' && String(frame.payload.kind).startsWith('permission_'));
    // Server-initiated request IDs are retained in their response frames.
    frame = { type: frame.type, payload: { ...frame.payload, request_id: frame.payload.request_id ?? randomUUID() } };
    if ((!control && this.queue.filter(item => !item.control).length >= 256) || this.queue.length >= 258
      || this.pending.has(String(frame.payload.request_id)) || this.queue.some(item => item.frame.payload.request_id === frame.payload.request_id)) {
      return Promise.reject(new RelayDeliveryError('Relay request window is full', 'not-sent'));
    }
    return new Promise((resolve, reject) => { this.queue.push({ frame, control, resolve, reject }); this.pump(); });
  }
  private pump(): void {
    if (this.socket?.readyState !== WebSocket.OPEN) return;
    const limit = this.correlated ? 8 : 1;
    while (this.pending.size < limit) {
      const ordinary = [...this.pending.values()].filter(item => !item.control).length;
      let index = this.queue.findIndex(item => item.control);
      if (index < 0) {
        if (this.correlated && ordinary >= 6) return;
        const agents = [...new Set(this.queue.map(item => this.agent(item.frame)))];
        const next = agents[(agents.indexOf(this.lastAgent) + 1) % agents.length];
        index = this.queue.findIndex(item => this.agent(item.frame) === next);
      }
      const pending = this.queue.splice(index, 1)[0];
      if (!pending) return;
      if (!pending.control) this.lastAgent = this.agent(pending.frame);
      const id = String(pending.frame.payload.request_id);
      const generation = this.generation;
      this.pending.set(id, pending);
      pending.timer = setTimeout(() => {
        if (generation !== this.generation || !this.pending.delete(id)) return;
        pending.reject(new RelayDeliveryError('IM response deadline exceeded', 'unknown'));
        if (pending.frame.type === 'node.register') this.disconnect(generation, false, 'Node registration timeout', {error_type:'TimeoutError'});
        else this.pump();
      }, this.options.ackTimeoutMs ?? 10000);
      try {
        this.socket.send(JSON.stringify(pending.frame), error => {
          if (error) this.disconnect(generation, false, 'IM frame send failed');
        });
      } catch { this.disconnect(generation, false, 'IM frame send failed'); return; }
    }
  }
  private receive(frame: ProtocolFrame, generation: number): void {
    if (frame.type === 'error' && frame.payload.code === 'gateway_owner_mismatch') {
      this.disconnect(generation, true, 'Gateway authority revoked'); return;
    }
    const id = frame.payload.request_id;
    const pending = this.correlated
      ? (typeof id === 'string' ? this.pending.get(id) : undefined)
      : [...this.pending.values()].find(item => this.matches(item.frame, frame));
    if (pending && this.matches(pending.frame, frame)) {
      clearTimeout(pending.timer); this.pending.delete(String(pending.frame.payload.request_id));
      if (frame.type === 'error') {
        const code = String(frame.payload.code ?? 'error');
        pending.reject(new RelayDeliveryError(`IM rejected the request: ${code}`, 'rejected', code));
        if (pending.frame.type === 'node.register') { this.disconnect(generation, false, 'IM rejected registration'); return; }
      } else pending.resolve(frame);
      this.pump(); return;
    }
    if (typeof frame.payload.request_id==='string' && frame.type!=='ack' && frame.type!=='error' && !frame.type.endsWith('.result')) this.serverRequests.add(frame.payload.request_id);
    void Promise.resolve().then(() => this.options.onFrame(frame)).catch(error => this.report(error instanceof Error ? error : new Error('IM inbound callback failed')));
  }
  private matches(sent: ProtocolFrame, received: ProtocolFrame): boolean {
    if (received.type === 'error') {
      const key = sent.type.startsWith('pa.') ? 'request_id' : results[sent.type]?.[1];
      return (received.payload.message_type === undefined || received.payload.message_type === sent.type)
        && (!key || received.payload[key] === undefined || received.payload[key] === sent.payload[key]);
    }
    const typed = sent.type.startsWith('pa.') ? [`${sent.type}.result`, 'request_id'] : results[sent.type];
    if (typed) {
      const [type, key] = typed;
      return received.type === type && sent.payload[key] !== undefined && received.payload[key] === sent.payload[key];
    }
    return received.type === 'ack' && received.payload.message_type === sent.type;
  }
  private scheduleHeartbeat(generation: number): void {
    this.heartbeatTimer = setTimeout(() => {
      if (generation !== this.generation || !this.ready) return;
      this.scheduleHeartbeat(generation);
      if ([...this.pending.values(), ...this.queue].some(item => item.frame.type === 'node.heartbeat')) return;
      const payload = this.options.heartbeatPayload?.() ?? {
        node_id: this.registrationPayload.node_id, status: 'online',
        agent_count: Array.isArray(this.registrationPayload.agents) ? this.registrationPayload.agents.length : 0,
      };
      void this.enqueue({ type: 'node.heartbeat', payload }).then(() => {
        if (generation !== this.generation) return;
        this.heartbeatFailures = 0; this.heartbeatSuccesses++;
        if (Date.now() - this.readySince >= 60000 && this.heartbeatSuccesses >= 2) this.attempt = 0;
      }).catch(() => {
        if (generation === this.generation && ++this.heartbeatFailures >= 2) {
          this.diagnose('transport_error', 'heartbeat', {error_type:'TimeoutError'});
          this.disconnect(generation, false, 'Heartbeat failed', {error_type:'TimeoutError'});
        }
      });
    }, this.options.heartbeatIntervalMs ?? 30000);
  }
  private disconnect(generation: number, revoked: boolean, message: string, details: DiagnosticDetails = {}): void {
    if (generation !== this.generation) return;
    this.outageStartedAt ??= Date.now();
    this.diagnose('disconnected', this.phase(), { reason: message, error_type: 'Error', revoked, ...details });
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
    const delay = Math.round(Math.min((this.options.reconnectInitialMs ?? 1000) * 2 ** Math.min(this.attempt++, 20) * (0.8 + Math.random() * 0.4), this.options.reconnectMaxMs ?? 30000));
    this.diagnose('retry_scheduled', 'connect', { attempt: this.attempt, delay_ms: delay });
    this.reconnectTimer = setTimeout(() => { void this.connect(); }, delay);
  }
  private phase(): RelayDiagnostic['phase'] {
    if (this.currentState === 'connecting') return 'connect';
    if (this.currentState === 'registering') return 'register';
    if ([...this.pending.values()].some(item => item.frame.type === 'node.heartbeat')) return 'heartbeat';
    return this.pending.size ? 'send' : 'receive';
  }
  private diagnose(event: RelayDiagnostic['event'], phase: RelayDiagnostic['phase'], details: DiagnosticDetails = {}): void {
    try {
      this.options.onDiagnostic?.({ timestamp: new Date().toISOString(),
        node_id: typeof this.registrationPayload.node_id === 'string' ? this.registrationPayload.node_id : undefined,
        connection: this.generation, event, phase, attempt: this.attempt + 1, ...details });
    } catch { /* A diagnostic sink cannot change connection lifecycle behavior. */ }
  }
  private failRequests(message: string): void {
    for (const pending of this.pending.values()) {
      clearTimeout(pending.timer); pending.reject(new RelayDeliveryError(message, 'unknown'));
    }
    this.pending.clear(); this.correlated = false; this.serverRequests.clear();
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
export { ChannelKey, type ChannelAad, type CredentialEnvelope } from './channel-credentials.js';
