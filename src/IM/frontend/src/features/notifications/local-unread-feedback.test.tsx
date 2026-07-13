import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import type { Conversation } from "../chat/chat-types";
import {
  clearLocalUnreadFeedback,
  markLocalUnreadFeedback,
  resetLocalUnreadFeedback,
  useLocalUnreadFeedback
} from "./local-unread-feedback";

function conversation(unreadCount: number): Conversation {
  return {
    id: "conv-1",
    title: "Agent",
    participants: [],
    participant_ids: [],
    type: "direct",
    direct_kind: "agent",
    owner_id: "user-a",
    creator_id: "user-a",
    is_pinned: false,
    is_muted: false,
    unread_count: unreadCount,
    last_message_preview: "done",
    last_message_at: "2026-07-13T08:00:00Z",
    created_at: "2026-07-13T07:00:00Z"
  };
}

describe("local unread feedback", () => {
  beforeEach(resetLocalUnreadFeedback);

  it("survives a server unread=0 refresh until this tab opens the conversation", () => {
    const { result, rerender } = renderHook(
      ({ item }) => useLocalUnreadFeedback([item]),
      { initialProps: { item: conversation(0) } }
    );
    act(() => markLocalUnreadFeedback("conv-1"));
    expect(result.current[0]?.unread_count).toBe(1);

    rerender({ item: conversation(0) });
    expect(result.current[0]?.unread_count).toBe(1);

    act(() => clearLocalUnreadFeedback("conv-1"));
    expect(result.current[0]?.unread_count).toBe(0);
  });

  it("never lowers an authoritative unread count", () => {
    markLocalUnreadFeedback("conv-1");
    const { result } = renderHook(() => useLocalUnreadFeedback([conversation(3)]));
    expect(result.current[0]?.unread_count).toBe(3);
  });
});
