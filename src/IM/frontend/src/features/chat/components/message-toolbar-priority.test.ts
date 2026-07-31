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

it("layers the white message toolbar above a code-copy button when their corners overlap", () => {
  const zIndexOf = (selector: string) =>
    Number(
      globalCss.match(
        new RegExp(`${selector}\\s*\\{[^}]*z-index:\\s*(\\d+);`, "s")
      )?.[1]
    );

  expect(zIndexOf("\\.chat-message-toolbar")).toBeGreaterThan(zIndexOf("\\.im-code-copy"));
});
