import { describe, expect, it } from "vitest";

import { mergeMessageWithExisting } from "./chat-workspace-page";
import type { Message } from "./chat-types";

function message(backgroundReturns: unknown[]): Message {
  return {
    id: "m1",
    conversation_id: "c1",
    sender: { type: "agent", id: "agent-a" },
    sender_user_id: "agent:agent-a",
    sender_type: "agent",
    content: "summary",
    attachments: [],
    delivery_status: "completed",
    created_at: "2026-08-10T00:00:00Z",
    permission_requests: [],
    background_returns: backgroundReturns,
  } as Message;
}

describe("background return history merge", () => {
  it("merges stale REST history with live sidecars by task_id without duplicates", () => {
    const fromServer = message([
      {
        seq: 3,
        task_id: "task-1",
        task_type: "workflow",
        status: "completed",
        description: "review",
      },
      {
        seq: 5,
        task_id: "task-3",
        task_type: "subagent",
        status: "completed",
        description: "verify",
      },
    ]);
    const fromLive = message([
      {
        seq: 3,
        task_id: "task-1",
        task_type: "workflow",
        status: "completed",
        description: "review",
        result: "live raw result",
      },
      {
        seq: 4,
        task_id: "task-2",
        task_type: "subagent",
        status: "failed",
        description: "test",
        error: "live raw error",
      },
    ]);

    const merged = mergeMessageWithExisting(fromServer, fromLive);

    expect(merged.background_returns?.map((item) => item.task_id)).toEqual([
      "task-1",
      "task-2",
      "task-3",
    ]);
    expect(merged.background_returns?.[0]?.result).toBe("live raw result");
  });
});
