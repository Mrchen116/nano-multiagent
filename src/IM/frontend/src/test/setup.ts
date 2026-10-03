import "@testing-library/jest-dom/vitest";
import { beforeEach } from "vitest";

import { resetComposerStores } from "../features/chat/components/composer-draft-store";

// jsdom 27 + node 25 expose `localStorage` as a plain object missing the Storage API
// (no getItem/setItem/clear), so install an in-memory polyfill before tests touch it.
function installStoragePolyfill(target: { localStorage?: unknown; sessionStorage?: unknown }) {
  const make = () => {
    const data = new Map<string, string>();
    return {
      get length() {
        return data.size;
      },
      clear() {
        data.clear();
      },
      getItem(key: string): string | null {
        return data.has(key) ? data.get(key)! : null;
      },
      setItem(key: string, value: string) {
        data.set(key, String(value));
      },
      removeItem(key: string) {
        data.delete(key);
      },
      key(index: number): string | null {
        return Array.from(data.keys())[index] ?? null;
      }
    };
  };
  if (typeof (target.localStorage as { getItem?: unknown })?.getItem !== "function") {
    Object.defineProperty(target, "localStorage", { configurable: true, writable: true, value: make() });
  }
  if (typeof (target.sessionStorage as { getItem?: unknown })?.getItem !== "function") {
    Object.defineProperty(target, "sessionStorage", { configurable: true, writable: true, value: make() });
  }
}

if (typeof window !== "undefined") {
  installStoragePolyfill(window as unknown as { localStorage?: unknown; sessionStorage?: unknown });
}
installStoragePolyfill(globalThis as unknown as { localStorage?: unknown; sessionStorage?: unknown });

if (typeof window !== "undefined") {
  Object.defineProperty(window, "AbortController", {
    configurable: true,
    writable: true,
    value: globalThis.AbortController
  });
  Object.defineProperty(window, "AbortSignal", {
    configurable: true,
    writable: true,
    value: globalThis.AbortSignal
  });
}

const NativeRequest = globalThis.Request;

if (typeof NativeRequest === "function") {
  class RequestWithNormalizedSignal extends NativeRequest {
    constructor(input: ConstructorParameters<typeof Request>[0], init?: ConstructorParameters<typeof Request>[1]) {
      const nextInit = init && "signal" in init ? { ...init, signal: undefined } : init;
      super(input, nextInit);
    }
  }

  Object.defineProperty(globalThis, "Request", {
    configurable: true,
    writable: true,
    value: RequestWithNormalizedSignal
  });
}

if (typeof window !== "undefined" && typeof globalThis.Request === "function") {
  Object.defineProperty(window, "Request", {
    configurable: true,
    writable: true,
    value: globalThis.Request
  });
}

beforeEach(() => {
  resetComposerStores();
});

// jsdom has no Web Locks; serialize callbacks like the browser's exclusive lock.
let sessionLockTail: Promise<unknown> = Promise.resolve();
Object.defineProperty(navigator, "locks", { configurable: true, value: {
  request(_name: string, operation: () => Promise<unknown>) {
    const result = sessionLockTail.then(operation);
    sessionLockTail = result.catch(() => undefined);
    return result;
  }
} });
class TestBroadcastChannel {
  static channels = new Set<TestBroadcastChannel>();
  onmessage: ((event: { data: unknown }) => void) | null = null;
  constructor(readonly name: string) { TestBroadcastChannel.channels.add(this); }
  postMessage(data: unknown) {
    for (const channel of TestBroadcastChannel.channels) {
      if (channel !== this && channel.name === this.name) channel.onmessage?.({ data });
    }
  }
  close() { TestBroadcastChannel.channels.delete(this); }
}
Object.defineProperty(globalThis, "BroadcastChannel", { configurable: true, value: TestBroadcastChannel });
