import { describe, expect, it } from "vitest";
import indexHtml from "../../index.html?raw";

describe("index html", () => {
  it("declares explicit favicon to avoid /favicon.ico 404 noise", () => {
    expect(indexHtml).toContain('rel="icon"');
    expect(indexHtml).toContain('href="/favicon.svg"');
  });
});
