import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createUserStreamRuntime, type UserStreamRuntimeDependencies } from "./user-stream-runtime";

class FakeSocket {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static instances: FakeSocket[] = [];

  readonly url: string;
  readyState = FakeSocket.CONNECTING;
  sent: string[] = [];
  closed = false;
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(url: string) {
    this.url = url;
    FakeSocket.instances.push(this);
  }

  open(): void {
    this.readyState = FakeSocket.OPEN;
    this.onopen?.();
  }

  message(value: unknown): void {
    this.onmessage?.({ data: JSON.stringify(value) });
  }

  disconnect(): void {
    this.readyState = 3;
    this.onclose?.();
  }

  send(value: string): void {
    this.sent.push(value);
  }

  close(): void {
    this.closed = true;
    this.readyState = 3;
  }
}

interface MutableSession {
  userId: string | null;
  accessToken: string | null;
}

function setup(overrides: Partial<UserStreamRuntimeDependencies> = {}) {
  const session: MutableSession = { userId: "user-a", accessToken: "token-a" };
  const listeners = new Set<() => void>();
  const errors: unknown[] = [];
  const sync = vi.fn(async () => ({ maxEventId: 0 }));
  const ensureSession = vi.fn(async () => ({ status: "ready", userId: session.userId!, accessToken: session.accessToken! } as const));
  const dependencies: UserStreamRuntimeDependencies = {
    getSession: () => ({ ...session }),
    subscribeSession: (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    ensureSession,
    createSocket: (url) => new FakeSocket(url),
    readCursor: (userId) => Number(sessionStorage.getItem(`cursor:${userId}`) ?? "0"),
    writeCursor: (userId, cursor) => sessionStorage.setItem(`cursor:${userId}`, String(cursor)),
    sync,
    reportError: (error) => errors.push(error),
    resolveUrl: (token) => `ws://im.test/im/ws/user?token=${token}`,
    ...overrides
  };
  const runtime = createUserStreamRuntime(dependencies);
  return {
    runtime,
    session,
    errors,
    sync,
    ensureSession,
    updateSession(next: MutableSession) {
      session.userId = next.userId;
      session.accessToken = next.accessToken;
      for (const listener of listeners) listener();
    }
  };
}

async function settle(): Promise<void> {
  await Promise.resolve();
  await Promise.resolve();
}

describe("user stream runtime", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    sessionStorage.clear();
    FakeSocket.instances = [];
  });

  afterEach(() => {
    vi.useRealTimers();
    sessionStorage.clear();
  });

  it("shares one socket across subscribers, resumes from the user cursor, and stops after the last idempotent dispose", async () => {
    sessionStorage.setItem("cursor:user-a", "41");
    const { runtime } = setup();
    const disposeA = runtime.subscribe({ onEvent: vi.fn() });
    const disposeB = runtime.subscribe({ onEvent: vi.fn() });
    await settle();

    expect(FakeSocket.instances).toHaveLength(1);
    const socket = FakeSocket.instances[0]!;
    socket.open();
    expect(socket.sent).toContain(JSON.stringify({ op: "resume", after_event_id: 41 }));

    disposeA();
    expect(socket.closed).toBe(false);
    disposeA();
    disposeB();
    expect(socket.closed).toBe(true);
    await vi.advanceTimersByTimeAsync(60_000);
    expect(FakeSocket.instances).toHaveLength(1);
  });

  it("pings while live and reconnects with bounded backoff plus one recovery signal", async () => {
    const recovered = vi.fn(async () => undefined);
    const { runtime, ensureSession } = setup();
    runtime.subscribe({ onEvent: vi.fn(), onRecovery: recovered });
    await settle();
    const first = FakeSocket.instances[0]!;
    first.open();

    await vi.advanceTimersByTimeAsync(25_000);
    expect(first.sent).toContain(JSON.stringify({ op: "ping" }));
    first.disconnect();
    await vi.advanceTimersByTimeAsync(999);
    expect(FakeSocket.instances).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(1);
    await settle();
    expect(ensureSession).toHaveBeenCalledTimes(2);
    const second = FakeSocket.instances[1]!;
    second.open();
    await settle();
    expect(recovered).toHaveBeenCalledTimes(1);
  });

  it.each(["retry", "signed_out"] as const)("honors %s readiness without opening a socket", async (status) => {
    const ensureSession = vi.fn(async () => ({ status } as const));
    const { runtime } = setup({ ensureSession });
    runtime.subscribe({ onEvent: vi.fn() });
    await settle();
    expect(FakeSocket.instances).toHaveLength(0);
    if (status === "retry") {
      await vi.advanceTimersByTimeAsync(1000);
      await settle();
      expect(ensureSession).toHaveBeenCalledTimes(2);
    } else {
      await vi.advanceTimersByTimeAsync(60_000);
      expect(ensureSession).toHaveBeenCalledTimes(1);
    }
  });

  it("replaces the generation on token/user change and ignores stale socket callbacks", async () => {
    const events = vi.fn();
    const { runtime, updateSession } = setup();
    runtime.subscribe({ onEvent: events });
    await settle();
    const oldSocket = FakeSocket.instances[0]!;
    oldSocket.open();

    updateSession({ userId: "user-b", accessToken: "token-b" });
    await settle();
    expect(oldSocket.closed).toBe(true);
    const nextSocket = FakeSocket.instances[1]!;
    expect(nextSocket.url).toContain("token-b");
    oldSocket.message({ op: "event", event_type: "message.created", data: { event_id: 99 } });
    oldSocket.disconnect();
    await vi.advanceTimersByTimeAsync(60_000);
    expect(events).not.toHaveBeenCalled();
    expect(FakeSocket.instances).toHaveLength(2);
  });

  it("advances persistent cursors monotonically before isolating subscriber failures", async () => {
    const healthy = vi.fn();
    const broken = vi.fn(() => {
      throw new Error("subscriber failed");
    });
    const { runtime, errors } = setup();
    runtime.subscribe({ onEvent: broken });
    runtime.subscribe({ onEvent: healthy });
    await settle();
    const socket = FakeSocket.instances[0]!;
    socket.open();

    socket.message({ op: "event", event_type: "message.created", data: { event_id: 7, content: "hello" } });
    socket.message({ op: "event", event_type: "message.delta", data: { event_id: 5 } });
    socket.message({ op: "event", event_type: "node.status_changed", data: { node_id: "n-1" } });
    socket.message({ op: "event", event_type: 42, data: { event_id: 100 } });

    expect(sessionStorage.getItem("cursor:user-a")).toBe("7");
    expect(healthy).toHaveBeenCalledTimes(3);
    expect(errors).toHaveLength(3);
  });

  it("keeps resume, event dispatch, ping, and in-tab cursor continuity when storage throws", async () => {
    const received = vi.fn();
    const storageError = new DOMException("blocked", "SecurityError");
    const { runtime, errors } = setup({
      readCursor: () => {
        throw storageError;
      },
      writeCursor: () => {
        throw storageError;
      }
    });
    runtime.subscribe({ onEvent: received });
    await settle();

    const first = FakeSocket.instances[0]!;
    expect(() => first.open()).not.toThrow();
    expect(first.sent).toContain(JSON.stringify({ op: "resume", after_event_id: 0 }));
    expect(() =>
      first.message({ op: "event", event_type: "message.created", data: { event_id: 7, content: "visible" } })
    ).not.toThrow();
    expect(received).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(25_000);
    expect(first.sent).toContain(JSON.stringify({ op: "ping" }));
    first.disconnect();
    await vi.advanceTimersByTimeAsync(1000);
    await settle();
    const second = FakeSocket.instances[1]!;
    expect(() => second.open()).not.toThrow();
    expect(second.sent).toContain(JSON.stringify({ op: "resume", after_event_id: 7 }));
    expect(errors.length).toBeGreaterThan(0);
  });

  it("aligns resync with max cursor and settles isolated recovery callbacks once per generation", async () => {
    sessionStorage.setItem("cursor:user-a", "12");
    let releaseSync!: (value: { maxEventId: number }) => void;
    const sync = vi.fn(() => new Promise<{ maxEventId: number }>((resolve) => {
      releaseSync = resolve;
    }));
    const recovered = vi.fn(async () => undefined);
    const brokenRecovery = vi.fn(async () => {
      throw new Error("recovery failed");
    });
    const { runtime, errors } = setup({ sync });
    runtime.subscribe({ onEvent: vi.fn(), onRecovery: recovered });
    runtime.subscribe({ onEvent: vi.fn(), onRecovery: brokenRecovery });
    await settle();
    const socket = FakeSocket.instances[0]!;
    socket.open();

    socket.message({ op: "resync_required" });
    socket.message({ op: "resync_required" });
    expect(sync).toHaveBeenCalledTimes(1);
    releaseSync({ maxEventId: 20 });
    await settle();

    expect(sessionStorage.getItem("cursor:user-a")).toBe("20");
    expect(recovered).toHaveBeenCalledTimes(1);
    expect(brokenRecovery).toHaveBeenCalledTimes(1);
    expect(errors).toHaveLength(1);
    socket.message({ op: "resync_required" });
    await settle();
    expect(sync).toHaveBeenCalledTimes(1);
  });

  it("does not let stale resync completion mutate a new user's cursor", async () => {
    let releaseSync!: (value: { maxEventId: number }) => void;
    const sync = vi.fn(() => new Promise<{ maxEventId: number }>((resolve) => {
      releaseSync = resolve;
    }));
    const { runtime, updateSession } = setup({ sync });
    runtime.subscribe({ onEvent: vi.fn(), onRecovery: vi.fn() });
    await settle();
    const socket = FakeSocket.instances[0]!;
    socket.open();
    socket.message({ op: "resync_required" });

    updateSession({ userId: "user-b", accessToken: "token-b" });
    await settle();
    releaseSync({ maxEventId: 50 });
    await settle();

    expect(sessionStorage.getItem("cursor:user-a")).toBeNull();
    expect(sessionStorage.getItem("cursor:user-b")).toBeNull();
  });
});
