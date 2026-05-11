import { afterEach, describe, expect, it, vi } from "vitest";

import { isDocumentHidden, subscribeDocumentVisibility } from "./document-visibility";

afterEach(() => {
  vi.restoreAllMocks();
  Object.defineProperty(document, "visibilityState", {
    configurable: true,
    get: () => "visible"
  });
});

function setVisibility(state: DocumentVisibilityState) {
  Object.defineProperty(document, "visibilityState", {
    configurable: true,
    get: () => state
  });
}

describe("document-visibility", () => {
  it("isDocumentHidden mirrors document.visibilityState", () => {
    setVisibility("visible");
    expect(isDocumentHidden()).toBe(false);
    setVisibility("hidden");
    expect(isDocumentHidden()).toBe(true);
  });

  it("subscribeDocumentVisibility fires callback on visibilitychange", () => {
    const listener = vi.fn();
    const unsubscribe = subscribeDocumentVisibility(listener);

    setVisibility("hidden");
    document.dispatchEvent(new Event("visibilitychange"));
    expect(listener).toHaveBeenCalledWith(true);

    setVisibility("visible");
    document.dispatchEvent(new Event("visibilitychange"));
    expect(listener).toHaveBeenLastCalledWith(false);

    unsubscribe();
    listener.mockClear();
    setVisibility("hidden");
    document.dispatchEvent(new Event("visibilitychange"));
    expect(listener).not.toHaveBeenCalled();
  });
});
