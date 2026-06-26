import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useAuthStore } from "../../auth/auth-store";
import {
  addParticipants,
  createConversation,
  createMessage,
  deleteConversation,
  listConversations,
  listMentionCandidates,
  listMessages,
  removeParticipant,
  updateConversation
} from "./chat-api";

function seedAuth() {
  useAuthStore.getState().setSession({
    access_token: "access-test",
    refresh_token: "refresh-test",
    user: {
      id: "user-1",
      username: "alex",
      display_name: "Alex",
      owner_id: "user-1",
      locale: "en",
      default_entry_node_id: null,
      owned_node_ids: [],
      created_at: "2026-01-01T00:00:00Z"
    }
  });
}

describe("chat-api v2", () => {
  beforeEach(() => {
    seedAuth();
    vi.stubGlobal("fetch", vi.fn());
  });
  afterEach(() => {
    useAuthStore.getState().clear();
    vi.unstubAllGlobals();
  });

  function jsonResponse(body: unknown, status = 200): Response {
    return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
  }

  it("listConversations sends Bearer and parses items envelope", async () => {
    const f = fetch as unknown as ReturnType<typeof vi.fn>;
    f.mockResolvedValueOnce(jsonResponse({ items: [{
      id: "c1", title: "Assistant", participants: [], participant_ids: [], type: "direct", direct_kind: "agent",
      owner_id: "user-1", creator_id: "user-1", is_pinned: false, is_muted: false, unread_count: 0,
      last_message_preview: null, last_message_at: null, created_at: "2026-01-01T00:00:00Z"
    }] }));

    const out = await listConversations();
    expect(out).toHaveLength(1);
    expect(out[0]!.id).toBe("c1");
    const call = f.mock.calls[0]!;
    expect(call[0]).toMatch(/\/im\/v1\/conversations$/);
    const headers = new Headers((call[1] as RequestInit).headers);
    expect(headers.get("Authorization")).toBe("Bearer access-test");
  });

  it("listMessages includes mark_as_read=true and parses items", async () => {
    const f = fetch as unknown as ReturnType<typeof vi.fn>;
    f.mockResolvedValueOnce(jsonResponse({ items: [
      { id: "m1", conversation_id: "c1", sender: { type: "user", id: "user-1" }, sender_user_id: "user:user-1", sender_type: "user", content: "hi", attachments: [], delivery_status: "completed", created_at: "2026-01-01T00:00:01Z" }
    ], next_before_message_id: null }));

    const out = await listMessages("c1", { markAsRead: true });
    expect(out.items).toHaveLength(1);
    expect(out.items[0]!.content).toBe("hi");
    expect((f.mock.calls[0]![0] as string)).toContain("mark_as_read=true");
  });

  it("createMessage POSTs actor-first sender payload", async () => {
    const f = fetch as unknown as ReturnType<typeof vi.fn>;
    f.mockResolvedValueOnce(jsonResponse({
      id: "m2", conversation_id: "c1", sender: { type: "user", id: "user-1" }, sender_user_id: "user:user-1",
      sender_type: "user", content: "hello", attachments: [], delivery_status: "sent", created_at: "2026-01-01T00:00:02Z"
    }, 201));

    await createMessage({ conversationId: "c1", content: "hello" });
    const call = f.mock.calls[0]!;
    expect(call[0]).toMatch(/\/im\/v1\/conversations\/c1\/messages$/);
    const init = call[1] as RequestInit;
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      sender: { type: "user", id: "user-1" },
      content: "hello",
      attachments: []
    });
  });

  it("createConversation builds participants with agent and user actors", async () => {
    const f = fetch as unknown as ReturnType<typeof vi.fn>;
    f.mockResolvedValueOnce(jsonResponse({
      id: "g1", title: "Sprint", participants: [
        { type: "user", id: "user-1" }, { type: "agent", id: "agent-a" }, { type: "agent", id: "agent-b" }
      ], participant_ids: ["user:user-1", "agent:agent-a", "agent:agent-b"], type: "group", direct_kind: null,
      owner_id: "user-1", creator_id: "user-1", is_pinned: false, is_muted: false, unread_count: 0,
      last_message_preview: null, last_message_at: null, created_at: "2026-01-01T00:00:03Z"
    }, 201));

    const conv = await createConversation({ title: "Sprint", agentIds: ["agent-a", "agent-b"] });
    expect(conv.id).toBe("g1");
    const body = JSON.parse((f.mock.calls[0]![1] as RequestInit).body as string);
    expect(body.title).toBe("Sprint");
    expect(body.participants).toEqual([
      { type: "user", id: "user-1" },
      { type: "agent", id: "agent-a" },
      { type: "agent", id: "agent-b" }
    ]);
  });

  function groupBody() {
    return {
      id: "g1", title: "Renamed", participants: [
        { type: "user", id: "user-1", user_id: "user-1" },
        { type: "agent", id: "agent-a", user_id: "uuid-a" }
      ], participant_ids: ["user:user-1", "agent:agent-a"], type: "group", direct_kind: null,
      owner_id: "user-1", creator_id: "user-1", is_pinned: false, is_muted: false, unread_count: 0,
      last_message_preview: null, last_message_at: null, created_at: "2026-01-01T00:00:03Z"
    };
  }

  it("updateConversation PATCHes title and returns the conversation", async () => {
    const f = fetch as unknown as ReturnType<typeof vi.fn>;
    f.mockResolvedValueOnce(jsonResponse(groupBody()));

    const conv = await updateConversation("g1", { title: "Renamed" });
    expect(conv.title).toBe("Renamed");
    const call = f.mock.calls[0]!;
    expect(call[0]).toMatch(/\/im\/v1\/conversations\/g1$/);
    const init = call[1] as RequestInit;
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body as string)).toEqual({ title: "Renamed" });
  });

  it("addParticipants POSTs agent actors to the participants endpoint", async () => {
    const f = fetch as unknown as ReturnType<typeof vi.fn>;
    f.mockResolvedValueOnce(jsonResponse(groupBody()));

    const conv = await addParticipants("g1", ["agent-a", "agent-b"]);
    expect(conv.id).toBe("g1");
    const call = f.mock.calls[0]!;
    expect(call[0]).toMatch(/\/im\/v1\/conversations\/g1\/participants$/);
    const init = call[1] as RequestInit;
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      participants: [
        { type: "agent", id: "agent-a" },
        { type: "agent", id: "agent-b" }
      ]
    });
  });

  it("removeParticipant DELETEs by user_id (not agent id)", async () => {
    const f = fetch as unknown as ReturnType<typeof vi.fn>;
    f.mockResolvedValueOnce(new Response(null, { status: 204 }));

    await removeParticipant("g1", "uuid-a");
    const call = f.mock.calls[0]!;
    expect(call[0]).toMatch(/\/im\/v1\/conversations\/g1\/participants\/uuid-a$/);
    expect((call[1] as RequestInit).method).toBe("DELETE");
  });

  it("deleteConversation DELETEs the conversation", async () => {
    const f = fetch as unknown as ReturnType<typeof vi.fn>;
    f.mockResolvedValueOnce(new Response(null, { status: 204 }));

    await deleteConversation("g1");
    const call = f.mock.calls[0]!;
    expect(call[0]).toMatch(/\/im\/v1\/conversations\/g1$/);
    expect((call[1] as RequestInit).method).toBe("DELETE");
  });

  it("removeParticipant throws on a non-ok response", async () => {
    const f = fetch as unknown as ReturnType<typeof vi.fn>;
    f.mockResolvedValueOnce(new Response("nope", { status: 404 }));
    await expect(removeParticipant("g1", "uuid-a")).rejects.toThrow();
  });

  it("listMentionCandidates filters agent list to the conversation's agent participants", async () => {
    const f = fetch as unknown as ReturnType<typeof vi.fn>;
    f.mockResolvedValueOnce(jsonResponse([
      { agent_id: "agent-a", display_name: "Assistant", node_id: "n1", description: "" },
      { agent_id: "agent-b", display_name: "Planner", node_id: "n1", description: "" },
      { agent_id: "agent-c", display_name: "Reviewer", node_id: "n1", description: "" }
    ]));

    const out = await listMentionCandidates({
      conversation: {
        participants: [
          { type: "user", id: "user-1" },
          { type: "agent", id: "agent-a" },
          { type: "agent", id: "agent-c" }
        ]
      }
    });
    expect(out.map((m) => m.agent_id)).toEqual(["agent-a", "agent-c"]);
    expect(out[0]!.initials).toBe("AS");
  });
});
