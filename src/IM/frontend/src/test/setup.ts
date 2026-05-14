import "@testing-library/jest-dom/vitest";

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

export {};
