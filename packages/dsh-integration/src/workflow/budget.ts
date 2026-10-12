import type {} from "@deepseek-ai/dsh-llm-retry";
import { lastAssistantStreamChunk } from "@deepseek-ai/dsh-llm";
import type { SessionEvent } from "@deepseek-ai/dsh-session";

/** Incremental settlement accounting with native last-sample and retry boundaries. */
export function outputTokens(
  events: readonly SessionEvent[],
  turns?: readonly number[],
): number {
  let total = 0;
  let last: { turn: number; step: number; output: number } | undefined;
  for (const event of events) {
    if (event.type === "llm/retry-started") {
      if (last?.turn === event.data.turn && last.step === event.data.step)
        last = undefined;
      continue;
    }
    if (
      event.type !== "assistant/message" &&
      event.type !== "assistant/attempt"
    )
      continue;
    if (turns && !turns.includes(event.data.turn)) continue;
    const usage =
      (event.type === "assistant/message" && event.data.usage) ||
      lastAssistantStreamChunk(event.data.stream, "usage")?.usage;
    if (!usage) continue;
    const previous =
      last?.turn === event.data.turn && last.step === event.data.step
        ? last.output
        : 0;
    total += usage.outputTokens - previous;
    last = {
      turn: event.data.turn,
      step: event.data.step,
      output: usage.outputTokens,
    };
  }
  return total;
}
