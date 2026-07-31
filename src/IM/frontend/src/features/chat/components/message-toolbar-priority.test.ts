// @vitest-environment node
// @ts-expect-error Node builtins are available in the Vitest runtime without @types/node.
import { readFileSync } from "node:fs";
import { expect, it } from "vitest";

const globalCss = readFileSync(new URL("../../../styles/global.css", import.meta.url), "utf8");

it("gives a hovered code block priority over the message toolbar without hiding keyboard focus", () => {
  expect(globalCss).toMatch(
    /\.chat-bubble-card:has\(\.im-code-block:hover\)\s+\.chat-message-toolbar:not\(:focus-within\)\s*\{[^}]*opacity:\s*0;[^}]*pointer-events:\s*none;/s
  );
});
