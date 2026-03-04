import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

function readIndexHtml(): string {
  const currentDir = path.dirname(fileURLToPath(import.meta.url));
  const indexPath = path.resolve(currentDir, "../../index.html");
  return fs.readFileSync(indexPath, "utf-8");
}

describe("index html", () => {
  it("declares explicit favicon to avoid /favicon.ico 404 noise", () => {
    const html = readIndexHtml();
    expect(html).toContain('rel="icon"');
    expect(html).toContain('href="/favicon.svg"');
  });
});
