// @vitest-environment node
// @ts-expect-error Node builtins are available in the Vitest runtime without @types/node.
import { readFileSync } from "node:fs";
import { expect, it } from "vitest";

const globalCss = readFileSync(new URL("../../../styles/global.css", import.meta.url), "utf8");

it("defines explicit dark-card contrast for web search results", () => {
  expect(globalCss).toMatch(
    /\.chat-tool-detail-search\s*\{[^}]*background:\s*oklch\(0\.07 0\.01 240\)/s
  );
  expect(globalCss).toMatch(
    /\.chat-tool-detail-search-title\s*\{[^}]*color:\s*oklch\(0\.7 0\.12 250\)/s
  );
  expect(globalCss).toMatch(
    /\.chat-tool-detail-search-snippet\s*\{[^}]*color:\s*oklch\(0\.65 0\.02 240\)/s
  );
});
