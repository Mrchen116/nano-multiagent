import { describe, expect, it } from "vitest";

import { resolveChatApiMode } from "./chat-api";

describe("chat api mode", () => {
  it("defaults to mock under test runtime", () => {
    expect(resolveChatApiMode({ runtimeMode: "test" })).toBe("mock");
  });

  it("uses explicit env override first", () => {
    expect(resolveChatApiMode({ runtimeMode: "production", explicitMode: "im" })).toBe("im");
    expect(resolveChatApiMode({ runtimeMode: "production", explicitMode: "mock" })).toBe("mock");
  });
});
