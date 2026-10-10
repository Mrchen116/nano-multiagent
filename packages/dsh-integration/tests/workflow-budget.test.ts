import { expect, it } from "vitest";
import type { SessionEvent } from "@deepseek-ai/dsh-session";
import { outputTokens } from "../src/workflow/budget.js";

it("replaces final usage within one attempt, includes retries, and keeps later human turns separate", () => {
  const settlement = (
    type: string,
    turn: number,
    step: number,
    outputs: number[],
  ) => ({
    type,
    data: {
      turn,
      step,
      stream: outputs.map((outputTokens) => ({
        type: "chunk",
        chunk: { type: "usage", usage: { inputTokens: 0, outputTokens } },
      })),
    },
  });
  const events = [
    settlement("assistant/attempt", 1, 1, [1, 3]),
    settlement("assistant/message", 1, 1, [4]),
    { type: "llm/retry-started", data: { turn: 1, step: 1 } },
    settlement("assistant/message", 1, 1, [2, 5]),
    settlement("assistant/message", 1, 2, [7]),
    settlement("assistant/message", 2, 1, [99]),
  ] as SessionEvent[];
  expect(outputTokens(events, [1])).toBe(16);
  expect(outputTokens(events)).toBe(115);
});
