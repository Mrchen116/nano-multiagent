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
  it("tracks visibility changes until the listener unsubscribes", () => {
    setVisibility("visible");
    expect(isDocumentHidden()).toBe(false);
    const listener = vi.fn();
    const unsubscribe = subscribeDocumentVisibility(listener);

    setVisibility("hidden");
    expect(isDocumentHidden()).toBe(true);
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
