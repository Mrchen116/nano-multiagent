import "@testing-library/jest-dom/vitest";

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
