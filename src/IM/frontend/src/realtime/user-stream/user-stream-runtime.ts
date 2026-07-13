import type { SessionReadiness } from "../../features/auth/auth-session";

export interface UserStreamEvent {
  eventType: string;
  payload: Record<string, unknown>;
  eventId?: number;
}

export interface UserStreamSubscriber {
  onEvent(event: UserStreamEvent): void;
  onRecovery?(): void | Promise<void>;
}

interface SessionSnapshot {
  userId: string | null;
  accessToken: string | null;
}

export interface UserStreamSocket {
  readyState: number;
  onopen: (() => void) | null;
  onmessage: ((event: { data: string }) => void) | null;
  onclose: (() => void) | null;
  onerror: (() => void) | null;
  send(value: string): void;
  close(): void;
}

export interface UserStreamRuntimeDependencies {
  getSession(): SessionSnapshot;
  subscribeSession(listener: () => void): () => void;
  ensureSession(): Promise<SessionReadiness>;
  createSocket(url: string): UserStreamSocket;
  readCursor(userId: string): number;
  writeCursor(userId: string, cursor: number): void;
  sync(): Promise<{ maxEventId: number }>;
  reportError(error: unknown): void;
  resolveUrl(accessToken: string): string;
}

export interface UserStreamRuntime {
  subscribe(subscriber: UserStreamSubscriber): () => void;
}

const SOCKET_OPEN = 1;
const MAX_BACKOFF_EXPONENT = 5;

export function createUserStreamRuntime(dependencies: UserStreamRuntimeDependencies): UserStreamRuntime {
  const subscribers = new Set<UserStreamSubscriber>();
  const memoryCursors = new Map<string, number>();
  let socket: UserStreamSocket | null = null;
  let sessionUnsubscribe: (() => void) | null = null;
  let retryTimer: number | null = null;
  let pingTimer: number | null = null;
  let generation = 0;
  let reconnectAttempt = 0;
  let activeUserId: string | null = null;
  let activeToken: string | null = null;
  let lastOpenedUserId: string | null = null;
  let recoverySignaledGeneration: number | null = null;
  let resyncHandledGeneration: number | null = null;

  function clearTimers(): void {
    if (retryTimer !== null) {
      window.clearTimeout(retryTimer);
      retryTimer = null;
    }
    if (pingTimer !== null) {
      window.clearInterval(pingTimer);
      pingTimer = null;
    }
  }

  function invalidateConnection(resetContinuity: boolean): void {
    generation += 1;
    clearTimers();
    const previous = socket;
    socket = null;
    previous?.close();
    activeUserId = null;
    activeToken = null;
    reconnectAttempt = 0;
    recoverySignaledGeneration = null;
    resyncHandledGeneration = null;
    if (resetContinuity) lastOpenedUserId = null;
  }

  function reportSubscriberError(error: unknown): void {
    dependencies.reportError(error);
  }

  function readCursor(userId: string): number {
    const memoryCursor = memoryCursors.get(userId) ?? 0;
    try {
      const storedCursor = dependencies.readCursor(userId);
      const cursor = Number.isFinite(storedCursor) && storedCursor >= 0
        ? Math.max(memoryCursor, storedCursor)
        : memoryCursor;
      memoryCursors.set(userId, cursor);
      return cursor;
    } catch (error) {
      dependencies.reportError(error);
      return memoryCursor;
    }
  }

  function writeCursor(userId: string, cursor: number): void {
    const current = memoryCursors.get(userId) ?? 0;
    if (!Number.isFinite(cursor) || cursor <= current) return;
    memoryCursors.set(userId, cursor);
    try {
      dependencies.writeCursor(userId, cursor);
    } catch (error) {
      dependencies.reportError(error);
    }
  }

  async function signalRecovery(currentGeneration: number): Promise<void> {
    if (currentGeneration !== generation || recoverySignaledGeneration === currentGeneration) return;
    recoverySignaledGeneration = currentGeneration;
    await Promise.all(
      [...subscribers].map(async (subscriber) => {
        if (!subscriber.onRecovery) return;
        try {
          await subscriber.onRecovery();
        } catch (error) {
          reportSubscriberError(error);
        }
      })
    );
  }

  async function handleResync(currentGeneration: number, userId: string): Promise<void> {
    if (currentGeneration !== generation || resyncHandledGeneration === currentGeneration) return;
    resyncHandledGeneration = currentGeneration;
    try {
      const result = await dependencies.sync();
      if (currentGeneration !== generation) return;
      const current = readCursor(userId);
      if (Number.isFinite(result.maxEventId) && result.maxEventId > current) {
        writeCursor(userId, result.maxEventId);
      }
    } catch (error) {
      if (currentGeneration !== generation) return;
      dependencies.reportError(error);
    }
    await signalRecovery(currentGeneration);
  }

  function parseEvent(frame: Record<string, unknown>): UserStreamEvent | null {
    if (frame.op !== "event" || typeof frame.event_type !== "string" || frame.event_type.length === 0) return null;
    const data = frame.data;
    if (!data || typeof data !== "object" || Array.isArray(data)) return null;
    const payload = data as Record<string, unknown>;
    const rawEventId = typeof frame.event_id === "number" ? frame.event_id : payload.event_id;
    const eventId =
      typeof rawEventId === "number" && Number.isFinite(rawEventId) && rawEventId > 0 ? rawEventId : undefined;
    return { eventType: frame.event_type, payload, ...(eventId === undefined ? {} : { eventId }) };
  }

  function dispatchFrame(raw: string, currentGeneration: number, userId: string): void {
    if (currentGeneration !== generation) return;
    let frame: unknown;
    try {
      frame = JSON.parse(raw);
    } catch (error) {
      dependencies.reportError(error);
      return;
    }
    if (!frame || typeof frame !== "object" || Array.isArray(frame)) return;
    const record = frame as Record<string, unknown>;
    if (record.op === "pong") return;
    if (record.op === "resync_required") {
      void handleResync(currentGeneration, userId);
      return;
    }
    const event = parseEvent(record);
    if (!event) return;
    if (event.eventId !== undefined) {
      const current = readCursor(userId);
      if (event.eventId > current) writeCursor(userId, event.eventId);
    }
    for (const subscriber of [...subscribers]) {
      try {
        subscriber.onEvent(event);
      } catch (error) {
        reportSubscriberError(error);
      }
    }
  }

  function scheduleReconnect(): void {
    if (subscribers.size === 0) return;
    clearTimers();
    const delay = Math.min(30_000, 1000 * 2 ** Math.min(reconnectAttempt, MAX_BACKOFF_EXPONENT));
    reconnectAttempt += 1;
    retryTimer = window.setTimeout(() => {
      retryTimer = null;
      void beginConnection();
    }, delay);
  }

  async function beginConnection(): Promise<void> {
    if (subscribers.size === 0) return;
    const snapshot = dependencies.getSession();
    if (!snapshot.userId || !snapshot.accessToken) {
      invalidateConnection(true);
      return;
    }

    generation += 1;
    const currentGeneration = generation;
    clearTimers();
    const previous = socket;
    socket = null;
    previous?.close();
    activeUserId = snapshot.userId;
    activeToken = snapshot.accessToken;
    recoverySignaledGeneration = null;
    resyncHandledGeneration = null;

    const readiness = await dependencies.ensureSession();
    if (currentGeneration !== generation || subscribers.size === 0) return;
    if (readiness.status === "retry") {
      scheduleReconnect();
      return;
    }
    if (readiness.status === "signed_out") {
      invalidateConnection(true);
      return;
    }
    const latest = dependencies.getSession();
    if (latest.userId !== readiness.userId || latest.accessToken !== readiness.accessToken) return;

    activeUserId = readiness.userId;
    activeToken = readiness.accessToken;
    const nextSocket = dependencies.createSocket(dependencies.resolveUrl(readiness.accessToken));
    socket = nextSocket;
    nextSocket.onopen = () => {
      if (currentGeneration !== generation || socket !== nextSocket) return;
      reconnectAttempt = 0;
      nextSocket.send(
        JSON.stringify({ op: "resume", after_event_id: readCursor(readiness.userId) })
      );
      const recovering = lastOpenedUserId === readiness.userId;
      lastOpenedUserId = readiness.userId;
      pingTimer = window.setInterval(() => {
        if (currentGeneration === generation && nextSocket.readyState === SOCKET_OPEN) {
          nextSocket.send(JSON.stringify({ op: "ping" }));
        }
      }, 25_000);
      if (recovering) void signalRecovery(currentGeneration);
    };
    nextSocket.onmessage = (event) => dispatchFrame(event.data, currentGeneration, readiness.userId);
    nextSocket.onerror = () => dependencies.reportError(new Error("user stream socket error"));
    nextSocket.onclose = () => {
      if (currentGeneration !== generation || socket !== nextSocket) return;
      clearTimers();
      socket = null;
      scheduleReconnect();
    };
  }

  function reconcileSession(): void {
    if (subscribers.size === 0) return;
    const current = dependencies.getSession();
    if (!current.userId || !current.accessToken) {
      invalidateConnection(true);
      return;
    }
    if (current.userId === activeUserId && current.accessToken === activeToken) return;
    void beginConnection();
  }

  return {
    subscribe(subscriber) {
      subscribers.add(subscriber);
      if (subscribers.size === 1) {
        sessionUnsubscribe = dependencies.subscribeSession(reconcileSession);
        void beginConnection();
      }
      let disposed = false;
      return () => {
        if (disposed) return;
        disposed = true;
        subscribers.delete(subscriber);
        if (subscribers.size > 0) return;
        sessionUnsubscribe?.();
        sessionUnsubscribe = null;
        invalidateConnection(true);
      };
    }
  };
}
